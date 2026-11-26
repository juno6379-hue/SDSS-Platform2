"""CPU baselines for LCLUC. This API consumes already aligned, evidence-pinned tiles."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from functools import cache
from importlib.metadata import version
from threading import Lock
from typing import Any, Literal

from services.mlops.gates import REQUIRED_BANDS, DataReadiness, MLOpsPolicy, evaluate_training_gate

CLEAR_SCL = (4, 5, 6)
SPLITS = ("train", "validation", "test")
_NO_DATA = 65535
_SHA = re.compile(r"[a-f0-9]{64}")
_TORCH_LOCK = Lock()
LabelKind = Literal["weak_reference", "independent_ground_truth"]
Split = Literal["train", "validation", "test"]


@cache
def _numpy():
    import numpy

    return numpy


def _canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, allow_nan=False, separators=(",", ":")).encode()


@dataclass(frozen=True)
class ClassificationDomain:
    """Classifier view of a pinned taxonomy. Only thematic classes enter the output head."""

    version: str
    sha256: str
    codes: tuple[int, ...]
    qa_codes: tuple[int, ...] = ()
    nodata: int = _NO_DATA
    approval_status: str = "BLOCKED"

    def __post_init__(self):
        all_codes = self.codes + self.qa_codes + (self.nodata,)
        if (
            not self.version.strip()
            or not _SHA.fullmatch(self.sha256)
            or len(self.codes) < 2
            or any(type(code) is not int or not 0 <= code <= 65535 for code in all_codes)
            or len(set(all_codes)) != len(all_codes)
        ):
            raise ValueError("CLASSIFICATION_TAXONOMY_INVALID")

    @classmethod
    def from_taxonomy(cls, taxonomy):
        return cls(
            version=taxonomy.version,
            sha256=taxonomy.sha256,
            codes=tuple(taxonomy.thematic_codes),
            qa_codes=tuple(taxonomy.qa_codes),
            nodata=taxonomy.nodata,
            approval_status=taxonomy.approval_status,
        )


@dataclass(frozen=True)
class SceneTile:
    tile_id: str
    scene_id: str
    year: int
    image: Any  # (6, rows, columns), with explicit product scale and offset.
    scl: Any  # (rows, columns), aligned upstream using nearest-neighbor reprojection.
    crs: str
    transform: tuple[float, float, float, float, float, float]  # Affine a, b, c, d, e, f.
    source_sha256: str
    normalization_sha256: str
    scale: tuple[float, ...]
    offset: tuple[float, ...]
    image_nodata: tuple[float | None, ...]
    scl_crs: str
    scl_transform: tuple[float, float, float, float, float, float]
    bands: tuple[str, ...] = REQUIRED_BANDS


@dataclass(frozen=True)
class LabelSource:
    source_id: str
    version: str
    year: int
    sha256: str
    taxonomy_sha256: str
    kind: LabelKind
    nodata: int
    crs: str
    transform: tuple[float, float, float, float, float, float]


@dataclass(frozen=True)
class TrainingPatch:
    tile: SceneTile
    labels: Any
    reference: LabelSource
    split: Split


@dataclass(frozen=True)
class TrainingApproval:
    """Approval record loaded by a trusted caller, with both dataset hashes pinned."""

    approval_id: str
    manifest_sha256: str
    materialized_sha256: str


@dataclass(frozen=True)
class ClassifierSettings:
    seed: int = 42
    forest_trees: int = 48
    forest_max_depth: int = 18
    forest_samples_per_class: int = 25000
    unet_epochs: int = 6
    learning_rate: float = 0.003
    temporal_holdout: bool = False

    def __post_init__(self):
        bounds = (
            (self.seed, 0, 2**32 - 1),
            (self.forest_trees, 1, 256),
            (self.forest_max_depth, 1, 64),
            (self.forest_samples_per_class, 1, 100000),
            (self.unet_epochs, 1, 50),
        )
        if any(
            type(value) is not int or not lower <= value <= upper for value, lower, upper in bounds
        ):
            raise ValueError("CLASSIFIER_SETTINGS_OUT_OF_RANGE")
        if not 0.0 < self.learning_rate <= 0.1:
            raise ValueError("CLASSIFIER_LEARNING_RATE_INVALID")


@dataclass(frozen=True)
class Prediction:
    classes: Any  # (rows, columns), native thematic class ID or domain NoData.
    valid: Any  # Boolean mask for prediction and probability outputs.
    probabilities: Any  # (classes, rows, columns), ordered by codes. NaN outside valid.
    confidence: Any  # Top class probability, uncalibrated.
    entropy: Any  # Normalized categorical entropy, uncalibrated.
    codes: tuple[int, ...]
    taxonomy_sha256: str


def _bytes_hash(values, digest):
    np = _numpy()
    values = np.asarray(values)
    if values.dtype.kind not in "biuf":
        raise ValueError("CLASSIFIER_NUMERIC_RASTER_REQUIRED")
    digest.update(_canonical([values.dtype.name, values.shape]))
    contiguous = np.ascontiguousarray(values.astype(values.dtype.newbyteorder("<"), copy=False))
    digest.update(memoryview(contiguous).cast("B"))


def dataset_sha256(patches) -> str:
    """Hash tile and label bytes, physical normalization and split identity."""

    digest = hashlib.sha256()
    ordered = sorted(patches, key=lambda patch: patch.tile.tile_id)
    digest.update(_canonical(len(ordered)))
    for patch in ordered:
        tile = patch.tile
        digest.update(
            _canonical(
                [
                    tile.tile_id,
                    tile.scene_id,
                    tile.year,
                    tile.crs,
                    tile.transform,
                    tile.source_sha256,
                    tile.normalization_sha256,
                    tile.bands,
                    tile.scale,
                    tile.offset,
                    tile.image_nodata,
                    tile.scl_crs,
                    tile.scl_transform,
                    patch.split,
                    asdict(patch.reference),
                ]
            )
        )
        for array in (tile.image, tile.scl, patch.labels):
            _bytes_hash(array, digest)
    return digest.hexdigest()


def _grid(tile, shape):
    np = _numpy()
    from pyproj import CRS
    from pyproj.exceptions import CRSError

    try:
        crs = CRS.from_user_input(tile.crs)
    except (CRSError, ValueError, TypeError) as error:
        raise ValueError("CLASSIFIER_PROJECTED_METRIC_CRS_REQUIRED") from error
    if not crs.is_projected or any(
        axis.unit_conversion_factor != 1.0 for axis in crs.axis_info[:2]
    ):
        raise ValueError("CLASSIFIER_PROJECTED_METRIC_CRS_REQUIRED")
    transform = np.asarray(tile.transform)
    if transform.shape != (6,) or not np.isfinite(transform).all():
        raise ValueError("CLASSIFIER_INVALID_TRANSFORM")
    a, b, c, d, e, f = transform
    if not (a > 0 and e < 0 and b == d == 0):
        raise ValueError("CLASSIFIER_NORTH_UP_GRID_REQUIRED")
    height, width = shape
    bounds = (float(c), float(f + e * height), float(c + a * width), float(f))
    return crs, bounds


def _require_aligned(tile, crs, transform, code):
    np = _numpy()
    from pyproj import CRS
    from pyproj.exceptions import CRSError

    try:
        transform = np.asarray(transform, dtype="float64")
        same_crs = CRS.from_user_input(tile.crs).equals(CRS.from_user_input(crs))
    except (CRSError, TypeError, ValueError) as error:
        raise ValueError(code) from error
    if (
        transform.shape != (6,)
        or not same_crs
        or not np.allclose(transform, tile.transform, rtol=0, atol=1e-7)
    ):
        raise ValueError(code)


def _scene(tile):
    np = _numpy()
    image, scl = np.asarray(tile.image), np.asarray(tile.scl)
    if (
        tuple(tile.bands) != REQUIRED_BANDS
        or image.ndim != 3
        or image.shape[0] != len(REQUIRED_BANDS)
        or image.dtype.kind not in "fiu"
        or scl.dtype.kind not in "ui"
        or scl.shape != image.shape[1:]
        or min(scl.shape) < 4
    ):
        raise ValueError("CLASSIFIER_ALIGNED_SIX_BAND_SCL_REQUIRED")
    _require_aligned(tile, tile.scl_crs, tile.scl_transform, "CLASSIFIER_SCL_GRID_MISMATCH")
    if np.any((scl > 11) & (scl != 255)) or np.any(scl < 0):
        raise ValueError("CLASSIFIER_SCL_CODE_UNRECOGNIZED")
    if (
        type(tile.year) is not int
        or not 2015 <= tile.year <= 2100
        or not tile.tile_id.strip()
        or not tile.scene_id.strip()
        or not _SHA.fullmatch(tile.source_sha256)
        or not _SHA.fullmatch(tile.normalization_sha256)
    ):
        raise ValueError("CLASSIFIER_SOURCE_EVIDENCE_REQUIRED")
    scale, offset = (
        np.asarray(tile.scale, dtype="float64"),
        np.asarray(tile.offset, dtype="float64"),
    )
    if (
        scale.shape != offset.shape
        or scale.shape != (6,)
        or len(tile.image_nodata) != 6
        or (scale <= 0).any()
        or not (np.isfinite(scale).all() and np.isfinite(offset).all())
        or any(value is not None and not np.isfinite(value) for value in tile.image_nodata)
    ):
        raise ValueError("CLASSIFIER_PRODUCT_NORMALIZATION_INVALID")

    valid = np.isin(scl, CLEAR_SCL) & np.isfinite(image).all(axis=0)
    for band_index, nodata in enumerate(tile.image_nodata):
        if nodata is not None:
            valid &= image[band_index] != nodata
    with np.errstate(over="ignore", invalid="ignore"):
        physical = (image * scale[:, None, None] + offset[:, None, None]).astype("float32")
    if not np.isfinite(physical[:, valid]).all():
        raise ValueError("CLASSIFIER_PRODUCT_NORMALIZATION_OUT_OF_RANGE")
    physical[:, ~valid] = 0
    return physical, valid


def _encoded_labels(patch, domain, raster_valid):
    np = _numpy()
    reference = patch.reference
    labels = np.asarray(patch.labels)
    if labels.dtype.kind not in "iu" or labels.shape != raster_valid.shape:
        raise ValueError("CLASSIFIER_ALIGNED_INTEGER_LABELS_REQUIRED")
    if (
        type(reference.year) is not int
        or reference.year != patch.tile.year
        or reference.taxonomy_sha256 != domain.sha256
        or not _SHA.fullmatch(reference.sha256)
        or not reference.source_id.strip()
        or not reference.version.strip()
        or type(reference.nodata) is not int
        or reference.nodata in domain.codes + domain.qa_codes
    ):
        raise ValueError("CLASSIFIER_LABEL_SOURCE_OR_YEAR_MISMATCH")
    _require_aligned(
        patch.tile, reference.crs, reference.transform, "CLASSIFIER_LABEL_GRID_MISMATCH"
    )
    key = re.sub(r"[^a-z0-9]", "", reference.source_id.lower())
    if "worldcover" in key:
        version = re.sub(r"[^a-z0-9]", "", reference.version.lower())
        tags = key + ":" + version
        known_years = {
            year
            for year, release in ((2020, "v100"), (2021, "v200"))
            if str(year) in tags or release in tags
        }
        if known_years != {reference.year}:
            raise ValueError("CLASSIFIER_WORLDCOVER_YEAR_MISMATCH")
    if reference.kind not in {"weak_reference", "independent_ground_truth"}:
        raise ValueError("CLASSIFIER_LABEL_KIND_UNRECOGNIZED")
    prior_products = ("worldcover", "esri", "dynamicworld", "klhk", "onemap")
    if reference.kind == "independent_ground_truth" and any(x in key for x in prior_products):
        raise ValueError("CLASSIFIER_INDEPENDENT_REFERENCE_REQUIRED")
    if not np.isin(labels, (*domain.codes, *domain.qa_codes, reference.nodata)).all():
        raise ValueError("CLASSIFIER_LABEL_CODE_OUTSIDE_TAXONOMY")
    ordered = sorted((code, i) for i, code in enumerate(domain.codes))
    codes, indices = map(np.asarray, zip(*ordered, strict=True))
    thematic = raster_valid & np.isin(labels, codes)
    encoded = np.full(labels.shape, -1, dtype=np.int32)
    encoded[thematic] = indices[np.searchsorted(codes, labels[thematic])]
    return encoded


def _intersects(left, right):
    return min(left[2], right[2]) > max(left[0], right[0]) and min(left[3], right[3]) > max(
        left[1], right[1]
    )


def _audit(patches, domain, settings):
    np = _numpy()
    by_split = {name: [] for name in SPLITS}
    footprints = {name: [] for name in SPLITS}
    reference_kinds = {name: set() for name in SPLITS}
    reference_ids = {name: set() for name in SPLITS}
    scene_splits = {}
    source_splits = {}
    reference_hashes = {name: set() for name in SPLITS}
    imagery_usable = {name: [0, 0] for name in SPLITS}
    known_ids = set()
    dataset_crs = None
    training_counts = np.zeros(len(domain.codes), dtype=np.int64)
    for patch in patches:
        tile = patch.tile
        if patch.split not in SPLITS or tile.tile_id in known_ids:
            raise ValueError("CLASSIFIER_INVALID_OR_DUPLICATE_SPLIT_TILE")
        known_ids.add(tile.tile_id)
        if scene_splits.setdefault(tile.scene_id, patch.split) != patch.split:
            raise ValueError("CLASSIFIER_SCENE_SPLIT_LEAKAGE")
        if source_splits.setdefault(tile.source_sha256, patch.split) != patch.split:
            raise ValueError("CLASSIFIER_SOURCE_HASH_SPLIT_LEAKAGE")
        _, valid = _scene(tile)
        labels = _encoded_labels(patch, domain, valid)
        if not (labels >= 0).any():
            raise ValueError("CLASSIFIER_SPLIT_TILE_HAS_NO_VALID_LABELS")
        crs, bounds = _grid(tile, valid.shape)
        dataset_crs = dataset_crs or crs
        if not crs.equals(dataset_crs):
            raise ValueError("CLASSIFIER_COMMON_PROJECTED_CRS_REQUIRED")
        footprints[patch.split].append(bounds)
        by_split[patch.split].append(patch)
        reference_kinds[patch.split].add(patch.reference.kind)
        reference_ids[patch.split].add(re.sub(r"[^a-z0-9]", "", patch.reference.source_id.lower()))
        reference_hashes[patch.split].add(patch.reference.sha256)
        imagery_usable[patch.split][0] += int(valid.sum())
        imagery_usable[patch.split][1] += int(valid.size)
        if patch.split == "train":
            training_counts += np.bincount(labels[labels >= 0], minlength=len(domain.codes))

    if any(not by_split[split] for split in SPLITS):
        raise ValueError("CLASSIFIER_TRAIN_VALIDATION_TEST_REQUIRED")
    if any(len(reference_kinds[split]) != 1 for split in SPLITS[1:]):
        raise ValueError("CLASSIFIER_EVALUATION_REFERENCE_KINDS_MIXED")
    for position, first in enumerate(SPLITS):
        for second in SPLITS[position + 1 :]:
            if any(_intersects(a, b) for a in footprints[first] for b in footprints[second]):
                raise ValueError("CLASSIFIER_SPATIAL_SPLIT_LEAKAGE")
    if reference_kinds["test"] == {"independent_ground_truth"} and (
        reference_ids["test"] & (reference_ids["train"] | reference_ids["validation"])
        or reference_hashes["test"] & (reference_hashes["train"] | reference_hashes["validation"])
    ):
        raise ValueError("CLASSIFIER_INDEPENDENT_LABEL_SOURCE_REUSED")
    if settings.temporal_holdout and (
        max(item.tile.year for item in (*by_split["train"], *by_split["validation"]))
        >= min(item.tile.year for item in by_split["test"])
    ):
        raise ValueError("CLASSIFIER_TEMPORAL_HOLDOUT_LEAKAGE")
    if not training_counts.all():
        raise ValueError("CLASSIFIER_TRAINING_CLASS_MISSING")
    return by_split, training_counts, imagery_usable


def _normalized(patch, domain, mean, deviation):
    image, valid = _scene(patch.tile)
    labels = _encoded_labels(patch, domain, valid)
    image = (image - mean[:, None, None]) / deviation[:, None, None]
    image[:, ~valid] = 0.0
    if not _numpy().isfinite(image).all():
        raise ValueError("CLASSIFIER_STANDARDIZED_INPUT_OUT_OF_RANGE")
    return image, labels


def _normalization(train, domain):
    np = _numpy()
    totals, squares = np.zeros(6), np.zeros(6)
    count = 0
    for patch in train:
        image, raster_valid = _scene(patch.tile)
        labels = _encoded_labels(patch, domain, raster_valid)
        values = image[:, labels >= 0].astype("float64")
        totals += values.sum(axis=1)
        squares += np.square(values).sum(axis=1)
        count += values.shape[1]
    mean = totals / count
    variance = np.maximum(squares / count - np.square(mean), 0)
    deviation = np.where(variance > 1e-12, np.sqrt(variance), 1.0)
    return mean.astype("float32"), deviation.astype("float32")


def _fit_forest(train, domain, mean, deviation, settings):
    np = _numpy()
    rng = np.random.default_rng(settings.seed)
    classes = range(len(domain.codes))
    cap = settings.forest_samples_per_class
    reservoirs = {i: (np.empty(0), np.empty((0, 6), dtype="float32")) for i in classes}
    for patch in train:
        image, labels = _normalized(patch, domain, mean, deviation)
        for i in classes:
            selected = labels == i
            values = image[:, selected].T
            keys = rng.random(values.shape[0])
            old_keys, old_values = reservoirs[i]
            keys = np.concatenate((keys, old_keys))
            values = np.concatenate((values, old_values), axis=0)
            if len(keys) > cap:
                sample = np.argpartition(keys, cap - 1)[:cap]
                keys, values = keys[sample], values[sample]
            reservoirs[i] = keys, values

    features = np.concatenate([reservoirs[i][1] for i in classes])
    counts = [len(reservoirs[i][0]) for i in classes]
    labels = np.repeat(np.asarray(list(classes)), counts)
    return _forest_estimator(features, labels, settings), counts


def _forest_estimator(features, labels, settings):
    from sklearn.ensemble import RandomForestClassifier

    forest = RandomForestClassifier(
        n_estimators=settings.forest_trees,
        max_depth=settings.forest_max_depth,
        random_state=settings.seed,
        n_jobs=1,
    )
    forest.fit(features, labels)
    return forest


def fit_annual_forest(features, labels, domain, fingerprint, *, fixture):
    """Fit the CPU candidate on window-sampled, QA-filtered annual reflectance."""
    np = _numpy()
    codes, encoded = np.unique(labels, return_inverse=True)
    if len(codes) < 2 or not set(codes).issubset(domain.codes):
        raise ValueError("TRAINING_CLASSES_INSUFFICIENT")
    domain = ClassificationDomain(
        domain.version, domain.sha256, tuple(map(int, codes)), domain.qa_codes,
        domain.nodata, domain.approval_status,
    )
    mean = features.mean(axis=0)
    deviation = np.maximum(features.std(axis=0), 1e-6)
    forest = _forest_estimator((features - mean) / deviation, encoded, ClassifierSettings())
    return FittedClassifier(
        "random_forest", domain, mean, deviation, _forest_parameters(forest), fingerprint,
        "TESTED_SYNTHETIC" if fixture else "VERIFIED_REAL",
    )


def _network(torch, classes):
    nn = torch.nn

    def block(a, b):
        return nn.Sequential(
            nn.Conv2d(a, b, 3, padding=1),
            nn.ReLU(),
            nn.Conv2d(b, b, 3, padding=1),
            nn.ReLU(),
        )

    class TinyUNet(nn.Module):
        def __init__(self):
            super().__init__()
            self.enc1 = block(6, 8)
            self.enc2 = block(8, 16)
            self.middle = block(16, 32)
            self.dec2 = block(48, 16)
            self.dec1 = block(24, 8)
            self.head = nn.Conv2d(8, classes, 1)

        def forward(self, x):
            fn = nn.functional
            a = self.enc1(x)
            b = self.enc2(fn.max_pool2d(a, 2))
            c = self.middle(fn.max_pool2d(b, 2))
            up_c = fn.interpolate(c, size=b.shape[-2:], mode="bilinear", align_corners=False)
            d = self.dec2(torch.cat((up_c, b), 1))
            up_d = fn.interpolate(d, size=a.shape[-2:], mode="bilinear", align_corners=False)
            return self.head(self.dec1(torch.cat((up_d, a), 1)))

    with torch.device("cpu"):
        return TinyUNet().to(dtype=torch.float32)


def _fit_unet(train, domain, mean, deviation, settings):
    np = _numpy()
    import torch

    rng = np.random.default_rng(settings.seed)
    with _TORCH_LOCK, torch.random.fork_rng(devices=[]):
        threads = torch.get_num_threads()
        torch.set_num_threads(1)
        try:
            torch.random.default_generator.manual_seed(settings.seed)
            net = _network(torch, len(domain.codes))
            optimizer = torch.optim.Adam(net.parameters(), lr=settings.learning_rate)
            for _ in range(settings.unet_epochs):
                for index in rng.permutation(len(train)):
                    image, labels = _normalized(train[index], domain, mean, deviation)
                    optimizer.zero_grad(set_to_none=True)
                    prediction = net(torch.from_numpy(image[None]))
                    loss = torch.nn.functional.cross_entropy(
                        prediction, torch.from_numpy(labels[None]).long(), ignore_index=-1
                    )
                    loss.backward()
                    optimizer.step()
            net.eval()
        finally:
            torch.set_num_threads(threads)
    return net


def _forest_parameters(forest):
    np = _numpy()
    arrays = {
        name: []
        for name in (
            "forest_left",
            "forest_right",
            "forest_feature",
            "forest_threshold",
            "forest_probability",
        )
    }
    offsets = [0]
    for estimator in forest.estimators_:
        tree = estimator.tree_
        start = offsets[-1]
        arrays["forest_left"].append(
            np.where(tree.children_left < 0, -1, tree.children_left + start)
        )
        arrays["forest_right"].append(
            np.where(tree.children_right < 0, -1, tree.children_right + start)
        )
        arrays["forest_feature"].append(tree.feature)
        arrays["forest_threshold"].append(tree.threshold)
        raw = tree.value[:, 0, :]
        arrays["forest_probability"].append(
            (raw / raw.sum(axis=1, keepdims=True)).astype("float32")
        )
        offsets.append(start + tree.node_count)
    return {key: np.concatenate(values) for key, values in arrays.items()} | {
        "forest_offsets": np.asarray(offsets, dtype=np.int64),
    }


def _forest_proba(arrays, features):
    np = _numpy()
    offsets = arrays["forest_offsets"]
    left, right = arrays["forest_left"], arrays["forest_right"]
    split_feature, threshold = arrays["forest_feature"], arrays["forest_threshold"]
    values = arrays["forest_probability"]
    probability = np.zeros((len(features), values.shape[1]), dtype="float64")
    for start in offsets[:-1]:
        nodes = np.full(len(features), start, dtype=np.int64)
        while True:
            active = np.flatnonzero(left[nodes] >= 0)
            if not len(active):
                break
            inner = nodes[active]
            to_left = features[active, split_feature[inner]] <= threshold[inner]
            nodes[active] = np.where(to_left, left[inner], right[inner])
        probability += values[nodes]
    return (probability / (len(offsets) - 1)).astype("float32")


def _network_proba(parameters, image, class_count):
    import torch

    with _TORCH_LOCK, torch.random.fork_rng(devices=[]):
        threads = torch.get_num_threads()
        torch.set_num_threads(1)
        try:
            network = _network(torch, class_count)
            tensors = {
                key.removeprefix("unet_"): torch.from_numpy(value.copy())
                for key, value in parameters.items()
            }
            network.load_state_dict(tensors, strict=True)
            network.eval()
            with torch.inference_mode():
                return torch.softmax(network(torch.from_numpy(image[None]))[0], dim=0).numpy()
        finally:
            torch.set_num_threads(threads)


@dataclass(frozen=True)
class FittedClassifier:
    method: Literal["random_forest", "tiny_unet"]
    domain: ClassificationDomain
    mean: Any
    deviation: Any
    parameters: dict[str, Any]
    dataset_sha256: str
    evidence_status: str

    def predict_forest_reflectance(self, image):
        """Apply the annual mosaic's existing finite-pixel mask."""
        np = _numpy()
        valid = np.isfinite(image).all(axis=0)
        classes = np.full(valid.shape, self.domain.nodata, dtype=np.uint16)
        confidence = np.full(valid.shape, np.nan, dtype="float32")
        if valid.any():
            features = (image[:, valid].T - self.mean) / self.deviation
            probability = _forest_proba(self.parameters, features)
            classes[valid] = np.asarray(self.domain.codes)[probability.argmax(axis=1)]
            confidence[valid] = probability.max(axis=1)
        return classes, confidence

    def predict(self, tile: SceneTile) -> Prediction:
        np = _numpy()
        image, valid = _scene(tile)
        _grid(tile, valid.shape)
        image = (image - self.mean[:, None, None]) / self.deviation[:, None, None]
        image[:, ~valid] = 0.0
        if not np.isfinite(image[:, valid]).all():
            raise ValueError("CLASSIFIER_STANDARDIZED_INPUT_OUT_OF_RANGE")

        shape = (len(self.domain.codes), *valid.shape)
        probabilities = np.full(shape, np.nan, dtype="float32")
        classes = np.full(valid.shape, self.domain.nodata, dtype=np.uint16)
        confidence = np.full(valid.shape, np.nan, dtype="float32")
        entropy = np.full(valid.shape, np.nan, dtype="float32")
        if valid.any():
            if self.method == "random_forest":
                prob = _forest_proba(self.parameters, image[:, valid].T).T
            elif self.method == "tiny_unet":
                prob = _network_proba(self.parameters, image, len(self.domain.codes))[:, valid]
            else:
                raise ValueError("CLASSIFIER_UNKNOWN_METHOD")
            if not np.isfinite(prob).all():
                raise ValueError("CLASSIFIER_OUTPUT_NONFINITE")
            probabilities[:, valid] = prob
            max_indices = np.argmax(prob, axis=0)
            classes[valid] = np.asarray(self.domain.codes, dtype=np.uint16)[max_indices]
            confidence[valid] = np.max(prob, axis=0)
            entropy[valid] = -np.sum(prob * np.log(np.clip(prob, 1e-12, 1.0)), axis=0) / np.log(
                len(self.domain.codes)
            )
        return Prediction(
            classes,
            valid,
            probabilities,
            confidence,
            entropy,
            self.domain.codes,
            self.domain.sha256,
        )

    def artifact_bytes(self) -> bytes:
        """A NumPy archive of typed arrays and JSON metadata. No pickle or executable object."""
        from io import BytesIO

        np = _numpy()
        metadata = _canonical(
            {
                "schema_version": "lcluc-classifier-artifact/1",
                "method": self.method,
                "domain": asdict(self.domain),
                "dataset_sha256": self.dataset_sha256,
                "evidence_status": self.evidence_status,
            }
        )
        stream = BytesIO()
        np.savez_compressed(
            stream,
            metadata=np.frombuffer(metadata, dtype=np.uint8),
            mean=self.mean,
            deviation=self.deviation,
            **self.parameters,
        )
        return stream.getvalue()


def _validate_artifact_parameters(method, parameters, class_count):
    np = _numpy()
    if method == "tiny_unet":
        import torch

        with _TORCH_LOCK, torch.random.fork_rng(devices=[]):
            expected = _network(torch, class_count).state_dict()
        if parameters.keys() != {"unet_" + key for key in expected}:
            raise ValueError("CLASSIFIER_ARTIFACT_TENSOR_KEYS_INVALID")
        for key, tensor in expected.items():
            array = parameters["unet_" + key]
            if (
                array.dtype != np.float32
                or array.shape != tuple(tensor.shape)
                or not np.isfinite(array).all()
            ):
                raise ValueError("CLASSIFIER_ARTIFACT_TENSOR_INVALID")
        return
    names = ("left", "right", "feature", "threshold", "offsets", "probability")
    if parameters.keys() != {"forest_" + name for name in names}:
        raise ValueError("CLASSIFIER_ARTIFACT_FOREST_KEYS_INVALID")
    left, right, feature, threshold, offsets, p = (parameters["forest_" + name] for name in names)
    if (
        left.ndim != 1
        or offsets.ndim != 1
        or not 2 <= len(offsets) <= 257
        or any(a.dtype.kind != "i" for a in (left, right, feature, offsets))
        or any(a.shape != left.shape for a in (right, feature, threshold))
        or not np.isfinite(threshold).all()
        or p.shape != (len(left), class_count)
        or not np.isfinite(p).all()
        or np.any(p < 0)
        or not np.allclose(p.sum(axis=1), 1)
        or offsets[0] != 0
        or offsets[-1] != len(left)
        or not (np.diff(offsets) > 0).all()
        or np.any((left == -1) != (right == -1))
    ):
        raise ValueError("CLASSIFIER_ARTIFACT_FOREST_INVALID")
    for start, end in zip(offsets[:-1], offsets[1:], strict=True):
        inner = np.flatnonzero(left[start:end] != -1) + start
        if (
            np.any(left[inner] <= inner)
            or np.any(right[inner] <= inner)
            or np.any(left[inner] >= end)
            or np.any(right[inner] >= end)
            or np.any((feature[inner] < 0) | (feature[inner] >= 6))
        ):
            raise ValueError("CLASSIFIER_ARTIFACT_TREE_INVALID")


def load_artifact(raw: bytes, expected_sha256: str) -> FittedClassifier:
    """Restore a verified immutable blob and validate every model parameter."""
    from io import BytesIO
    from math import prod
    from zipfile import ZipFile

    np = _numpy()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("CLASSIFIER_ARTIFACT_SHA_MISMATCH")
    with ZipFile(BytesIO(raw)) as archive:
        entries = archive.infolist()
        if (
            not 4 <= len(entries) <= 50
            or len({member.filename for member in entries}) != len(entries)
            or sum(member.file_size for member in entries) > 256 * 1024**2
            or any(not re.fullmatch(r"[A-Za-z0-9_.]+\.npy", member.filename) for member in entries)
        ):
            raise ValueError("CLASSIFIER_ARTIFACT_ARCHIVE_INVALID")
        # Verify the claimed array size before NumPy can allocate it.
        for member in entries:
            with archive.open(member) as handle:
                header_version = np.lib.format.read_magic(handle)
                if header_version == (1, 0):
                    shape, _, dtype = np.lib.format.read_array_header_1_0(handle)
                elif header_version == (2, 0):
                    shape, _, dtype = np.lib.format.read_array_header_2_0(handle)
                else:
                    raise ValueError("CLASSIFIER_ARTIFACT_ARRAY_HEADER_INVALID")
                if (
                    dtype.hasobject
                    or handle.tell() + prod(shape) * dtype.itemsize != member.file_size
                ):
                    raise ValueError("CLASSIFIER_ARTIFACT_ARRAY_SIZE_INVALID")
    with np.load(BytesIO(raw), allow_pickle=False, max_header_size=10000) as bundle:
        meta_raw = bundle["metadata"]
        if meta_raw.dtype != np.uint8 or meta_raw.ndim != 1 or len(meta_raw) > 8192:
            raise ValueError("CLASSIFIER_ARTIFACT_METADATA_INVALID")
        meta = json.loads(meta_raw.tobytes().decode())
        method = meta.get("method")
        if (
            meta.get("schema_version") != "lcluc-classifier-artifact/1"
            or method not in {"random_forest", "tiny_unet"}
            or not _SHA.fullmatch(meta.get("dataset_sha256", ""))
            or meta.get("evidence_status") not in {"TESTED_SYNTHETIC", "VERIFIED_REAL"}
        ):
            raise ValueError("CLASSIFIER_ARTIFACT_METADATA_INVALID")
        raw_domain = meta["domain"]
        domain = ClassificationDomain(
            **{
                **raw_domain,
                "codes": tuple(raw_domain["codes"]),
                "qa_codes": tuple(raw_domain["qa_codes"]),
            }
        )
        mean, deviation = bundle["mean"], bundle["deviation"]
        if any(
            a.dtype != np.float32 or a.shape != (6,) or not np.isfinite(a).all()
            for a in (mean, deviation)
        ) or np.any(deviation <= 0):
            raise ValueError("CLASSIFIER_ARTIFACT_NORMALIZATION_INVALID")
        parameters = {
            key: bundle[key] for key in bundle.files if key not in {"metadata", "mean", "deviation"}
        }
    _validate_artifact_parameters(method, parameters, len(domain.codes))
    return FittedClassifier(
        method, domain, mean, deviation, parameters, meta["dataset_sha256"], meta["evidence_status"]
    )


@dataclass(frozen=True)
class Comparison:
    models: dict[str, FittedClassifier]
    report: dict[str, Any]


def _metrics(matrix, codes):
    np = _numpy()
    rows = matrix.sum(axis=1)
    columns = matrix.sum(axis=0)
    diagonal = matrix.diagonal()
    total = int(rows.sum())
    result = []
    for i, code in enumerate(codes):
        truth, predicted, matched = int(rows[i]), int(columns[i]), int(diagonal[i])
        union = truth + predicted - matched
        result.append(
            {
                "class_code": code,
                "reference_pixels": truth,
                "predicted_pixels": predicted,
                "f1": 2 * matched / (truth + predicted) if union else None,
                "iou": matched / union if union else None,
            }
        )

    def average(name):
        values = [row[name] for row in result if row[name] is not None]
        return float(np.mean(values)) if values else None

    return {
        "eligible_pixels": total,
        "class_codes": list(codes),
        "confusion_matrix_reference_rows": matrix.tolist(),
        "overall_accuracy": int(diagonal.sum()) / total if total else None,
        "macro_f1": average("f1"),
        "mean_iou": average("iou"),
        "per_class": result,
    }


def _evaluate(model, patches, fixture):
    np = _numpy()
    codes = model.domain.codes
    matrix = np.zeros((len(codes), len(codes)), dtype=np.int64)
    for patch in patches:
        prediction = model.predict(patch.tile)
        expected = _encoded_labels(patch, model.domain, prediction.valid)
        eligible = expected >= 0
        predicted = np.argmax(prediction.probabilities[:, eligible], axis=0)
        steps = len(codes)
        counts = np.bincount(expected[eligible] * steps + predicted, minlength=steps**2)
        matrix += counts.reshape(matrix.shape)
    metric = _metrics(matrix, codes)
    kind = patches[0].reference.kind
    if kind == "weak_reference":
        metric["overall_reference_agreement"] = metric.pop("overall_accuracy")
    return {
        "reference_kind": kind,
        "metric_kind": "synthetic_fixture"
        if fixture
        else (
            "independent_accuracy"
            if kind == "independent_ground_truth"
            else "weak_reference_agreement"
        ),
        "reference_sources": sorted(
            {(p.reference.source_id, p.reference.version) for p in patches}
        ),
        "metrics": metric,
        "independent_accuracy": metric
        if not fixture and kind == "independent_ground_truth"
        else None,
    }


def fit_compare(
    patches,
    *,
    domain: ClassificationDomain,
    settings: ClassifierSettings = ClassifierSettings(),
    fixture: bool = False,
    readiness: DataReadiness | None = None,
    approval: TrainingApproval | None = None,
) -> Comparison:
    """Fit two CPU candidates. Use validation for selection, the same test for both."""
    ordered = sorted(patches, key=lambda patch: patch.tile.tile_id)
    if type(fixture) is not bool or (fixture and (readiness is not None or approval is not None)):
        raise ValueError("CLASSIFIER_FIXTURE_SCOPE_CONFLICT")
    if not fixture:
        if readiness is None or approval is None or not approval.approval_id.strip():
            raise ValueError("CLASSIFIER_TRAINING_APPROVAL_REQUIRED")
        if domain.approval_status != "APPROVED":
            raise ValueError("CLASSIFIER_CLASS_TAXONOMY_NOT_APPROVED")
        decision = evaluate_training_gate(readiness)
        if not decision.allowed:
            raise ValueError("CLASSIFIER_TRAINING_GATE:" + ",".join(decision.blockers))
        if readiness.manifest_sha256 != approval.manifest_sha256:
            raise ValueError("CLASSIFIER_TRAINING_MANIFEST_SHA_MISMATCH")

    splits, training_counts, imagery_usable = _audit(ordered, domain, settings)
    fingerprint = dataset_sha256(ordered)
    if not fixture and (
        fingerprint != approval.materialized_sha256
        or tuple(len(splits[split]) for split in SPLITS)
        != (readiness.train_patches, readiness.validation_patches, readiness.test_patches)
    ):
        raise ValueError("CLASSIFIER_TRAINING_DATASET_DRIFT")

    if not fixture:
        pixels_valid = sum(count[0] for count in imagery_usable.values())
        pixels_total = sum(count[1] for count in imagery_usable.values())
        if pixels_valid / pixels_total < MLOpsPolicy().min_valid_pixel_ratio:
            raise ValueError("CLASSIFIER_ACTUAL_SCL_COVERAGE_INSUFFICIENT")

    mean, deviation = _normalization(splits["train"], domain)
    forest, forest_counts = _fit_forest(splits["train"], domain, mean, deviation, settings)
    unet = _fit_unet(splits["train"], domain, mean, deviation, settings)
    state = "TESTED_SYNTHETIC" if fixture else "VERIFIED_REAL"
    models = {
        "random_forest": FittedClassifier(
            "random_forest",
            domain,
            mean,
            deviation,
            _forest_parameters(forest),
            fingerprint,
            state,
        ),
        "tiny_unet": FittedClassifier(
            "tiny_unet",
            domain,
            mean,
            deviation,
            {
                "unet_" + key: value.detach().numpy().copy()
                for key, value in unet.state_dict().items()
            },
            fingerprint,
            state,
        ),
    }
    evaluations = {
        name: {split: _evaluate(model, splits[split], fixture) for split in SPLITS[1:]}
        for name, model in models.items()
    }
    winner = min(
        evaluations,
        key=lambda name: (-evaluations[name]["validation"]["metrics"]["mean_iou"], name),
    )
    if dataset_sha256(ordered) != fingerprint:
        raise ValueError("CLASSIFIER_TRAINING_DATASET_DRIFT")
    return Comparison(
        models=models,
        report={
            "schema_version": "lcluc-classifier-comparison/1",
            "status": state,
            "dataset_sha256": fingerprint,
            "source_manifest_sha256": None if fixture else readiness.manifest_sha256,
            "training_approval_id": None if fixture else approval.approval_id,
            "taxonomy_sha256": domain.sha256,
            "taxonomy_version": domain.version,
            "class_codes": list(domain.codes),
            "qa_excluded_codes": list(domain.qa_codes),
            "nodata": domain.nodata,
            "band_order": list(REQUIRED_BANDS),
            "clear_scl_codes": list(CLEAR_SCL),
            "settings": asdict(settings),
            "split_tiles": {split: [p.tile.tile_id for p in splits[split]] for split in SPLITS},
            "training_pixel_counts_by_class": training_counts.tolist(),
            "imagery_quality": {
                split: {"valid": valid, "total": total, "valid_fraction": valid / total}
                for split, (valid, total) in imagery_usable.items()
            },
            "runtime_versions": {
                package: version(package)
                for package in ("numpy", "scikit-learn", "torch", "pyproj")
            },
            "forest_training_pixel_counts_by_class": forest_counts,
            "candidate_evaluations": evaluations,
            "candidate_artifact_sha256": {
                name: hashlib.sha256(model.artifact_bytes()).hexdigest()
                for name, model in models.items()
            },
            "selection": {
                "criterion": "validation_mean_iou_then_method_name",
                "recommended_candidate": winner,
                "test_used_for_selection": False,
                "release_approved": False,
            },
            "independent_test_metrics_measured": bool(
                not fixture
                and all(v["test"]["independent_accuracy"] is not None for v in evaluations.values())
            ),
            "scientific_accuracy_validated": False,
            "uncertainty": {
                "outputs": ["top_class_probability", "normalized_categorical_entropy"],
                "calibration_status": "NOT_CALIBRATED",
                "independent_accuracy_is_separate": True,
            },
        },
    )
