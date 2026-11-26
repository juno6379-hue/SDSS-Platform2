from dataclasses import replace
from hashlib import sha256
from types import SimpleNamespace

import pytest

from services.lcluc import classifiers as lc

np = pytest.importorskip("numpy")
pytest.importorskip("pyproj")

CODES = (2001, 50011)
DOMAIN = lc.ClassificationDomain("synthetic-two-class", "a" * 64, CODES, (2500,))
SETTINGS = lc.ClassifierSettings(
    forest_trees=8, forest_max_depth=4, forest_samples_per_class=35, unet_epochs=12
)


def patch(index, split, *, year=2023, source=None, scene_id=None, west=None):
    rng = np.random.default_rng(index + 10)
    width = 16
    columns = np.broadcast_to(np.arange(width), (width, width))
    labels = np.where(columns < width // 2, CODES[0], CODES[1]).astype("uint16")
    labels[1, 1] = 2500
    labels[3, 3] = 65535
    image = (rng.integers(1, 30, (6, width, width)) + np.where(columns < 8, 100, 450)).astype(
        "int16"
    )
    image[0, 2, 2] = -32768
    scl = np.full((width, width), 4, dtype="uint8")
    scl[0, 0] = 9
    transform = (20, 0, 1000 * index if west is None else west, 0, -20, 10000)
    tile = lc.SceneTile(
        tile_id=f"tile-{index}",
        scene_id=scene_id or f"scene-{index}",
        year=year,
        image=image,
        scl=scl,
        crs="EPSG:6933",
        transform=transform,
        source_sha256=sha256(str(index).encode()).hexdigest(),
        normalization_sha256="b" * 64,
        scale=(0.0001,) * 6,
        offset=(0.0,) * 6,
        image_nodata=(-32768,) * 6,
        scl_crs="EPSG:6933",
        scl_transform=transform,
    )
    reference = lc.LabelSource(
        source or ("held-fixture" if split == "test" else "development-fixture"),
        "2023-field-fixture",
        year,
        sha256(("labels" + str(index)).encode()).hexdigest(),
        DOMAIN.sha256,
        "independent_ground_truth" if split == "test" else "weak_reference",
        65535,
        "EPSG:6933",
        transform,
    )
    return lc.TrainingPatch(tile, labels, reference, split)


@pytest.fixture
def patches():
    return [
        *(patch(index, "train") for index in range(3)),
        patch(3, "validation"),
        patch(4, "test"),
    ]


def test_approved_execution_is_required(patches):
    with pytest.raises(ValueError, match="TRAINING_APPROVAL_REQUIRED"):
        lc.fit_compare(patches, domain=DOMAIN, settings=SETTINGS)


def test_taxonomy_keeps_explicit_native_themes():
    taxonomy = SimpleNamespace(
        version="test",
        sha256="b" * 64,
        thematic_codes=CODES,
        qa_codes=(2500,),
        nodata=65535,
        approval_status="BLOCKED",
    )
    domain = lc.ClassificationDomain.from_taxonomy(taxonomy)
    assert domain.codes == CODES and domain.qa_codes == (2500,) and domain.nodata == 65535


@pytest.mark.parametrize(
    "replacement, message",
    [
        (lambda: patch(4, "test", scene_id="scene-0"), "SCENE_SPLIT_LEAKAGE"),
        (lambda: patch(4, "test", west=20), "SPATIAL_SPLIT_LEAKAGE"),
        (lambda: patch(4, "test", source="development-fixture"), "INDEPENDENT_LABEL_SOURCE_REUSED"),
        (lambda: patch(4, "test", source="WorldCover"), "WORLDCOVER_YEAR_MISMATCH"),
    ],
)
def test_invalid_holdout_is_rejected_before_fitting(patches, replacement, message):
    patches[-1] = replacement()
    with pytest.raises(ValueError, match=message):
        lc.fit_compare(patches, domain=DOMAIN, settings=SETTINGS, fixture=True)


def test_worldcover_source_title_year_cannot_be_masked_by_version_spelling(patches):
    item = patch(0, "train", source="ESA WorldCover 2021", year=2020)
    patches[0] = replace(item, reference=replace(item.reference, version="v2.0.0"))
    with pytest.raises(ValueError, match="WORLDCOVER_YEAR_MISMATCH"):
        lc.fit_compare(patches, domain=DOMAIN, settings=SETTINGS, fixture=True)


def test_deliberate_future_holdout_must_be_chronological(patches):
    with pytest.raises(ValueError, match="TEMPORAL_HOLDOUT_LEAKAGE"):
        lc.fit_compare(
            patches, domain=DOMAIN, settings=replace(SETTINGS, temporal_holdout=True), fixture=True
        )


@pytest.mark.parametrize("raster", ["scl", "label"])
def test_same_shape_shifted_grid_is_rejected(patches, raster):
    p = patches[-1]
    shifted = (*p.tile.transform[:2], p.tile.transform[2] + 20, *p.tile.transform[3:])
    patches[-1] = (
        replace(p, tile=replace(p.tile, scl_transform=shifted))
        if raster == "scl"
        else replace(p, reference=replace(p.reference, transform=shifted))
    )
    with pytest.raises(ValueError, match=raster.upper() + "_GRID_MISMATCH"):
        lc.fit_compare(patches, domain=DOMAIN, settings=SETTINGS, fixture=True)


def test_materialized_fingerprint_binds_pixel_bytes(patches):
    digest = lc.dataset_sha256(patches)
    assert lc.dataset_sha256(list(reversed(patches))) == digest
    patches[0].tile.image[0, 1, 2] += 1
    assert lc.dataset_sha256(patches) != digest


def test_two_actual_algorithms_share_holdout_and_restore_without_pickle(patches):
    pytest.importorskip("sklearn")
    pytest.importorskip("torch")
    output = lc.fit_compare(patches, domain=DOMAIN, settings=SETTINGS, fixture=True)
    report = output.report
    assert report["status"] == "TESTED_SYNTHETIC"
    assert (
        not report["scientific_accuracy_validated"]
        and not report["selection"]["test_used_for_selection"]
    )
    assert not report["selection"]["release_approved"]
    assert report["training_pixel_counts_by_class"] == [372, 384]
    assert report["forest_training_pixel_counts_by_class"] == [35, 35]
    assert report["split_tiles"]["test"] == [patches[-1].tile.tile_id]
    test_tile = patches[-1].tile
    for method, model in output.models.items():
        holdout = report["candidate_evaluations"][method]["test"]
        assert holdout["independent_accuracy"] is None
        assert holdout["metric_kind"] == "synthetic_fixture"
        assert holdout["metrics"]["eligible_pixels"] == 252
        assert holdout["metrics"]["mean_iou"] >= 0.5
        valid = model.predict(test_tile)
        assert valid.classes[0, 0] == valid.classes[2, 2] == 65535
        assert np.isnan(valid.entropy[0, 0]) and np.isnan(valid.confidence[2, 2])
        assert set(np.unique(valid.classes[valid.valid])) == set(CODES)
        assert np.allclose(valid.probabilities[:, valid.valid].sum(axis=0), 1.0)
        assert np.all((valid.entropy[valid.valid] >= 0) & (valid.entropy[valid.valid] <= 1.000001))
        raw = model.artifact_bytes()
        observed_sha = sha256(raw).hexdigest()
        assert report["candidate_artifact_sha256"][method] == observed_sha
        with pytest.raises(ValueError, match="ARTIFACT_SHA_MISMATCH"):
            lc.load_artifact(raw + b"changed", observed_sha)
        replica = lc.load_artifact(raw, observed_sha).predict(test_tile)
        assert np.array_equal(replica.classes, valid.classes)
        assert np.allclose(replica.probabilities, valid.probabilities, equal_nan=True)
