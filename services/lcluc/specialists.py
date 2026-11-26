"""Same-year specialist classification and traceable layer precedence."""

from hashlib import sha256

from pydantic import Field, model_validator

from services.lcluc.annual_inputs import Input, Pin, Provenance, Sha

GROUPS = {"coastal": (105, 131), "rice": (140,), "plantation": (135, 109)}
NAMES = {105: "맹그로브", 131: "양식장", 140: "논", 135: "팜유", 109: "목재조림"}
# Codes above 100 are project output codes. Lower codes remain the base model's Esri classes.
ELIGIBLE = {105: (2, 4), 131: (1, 4, 5), 140: (4, 5), 135: (2, 5), 109: (2, 5)}
FOLDER = "data/raw/annual-lcluc/specialists/banten"


class SpecialistLayer(Provenance):
    class_code: int
    year: int
    label_year: int
    mask: Pin
    training_labels: Pin
    model_sha256: Sha


class SpecialistIntake(Input):
    year: int
    base_sha256: Sha
    approval_id: str = Field(min_length=1)
    layers: list[SpecialistLayer] = Field(min_length=1, max_length=len(NAMES))

    @model_validator(mode="after")
    def validate_layers(self):
        codes = {layer.class_code for layer in self.layers}
        if (len(codes) != len(self.layers) or not codes <= NAMES.keys()
                or any(layer.year != self.year or layer.label_year != self.year for layer in self.layers)):
            raise ValueError("SPECIALIST_LAYER_CLASS_OR_YEAR_INVALID")
        return self


def fit_specialist(group, features, observed_codes, trained_on, label_year, imagery_year):
    """Fit a thematic RF on explicit target and surveyed background labels (code 0)."""
    import numpy as np

    from services.lcluc.classifiers import ClassificationDomain, fit_annual_forest

    codes = (0, *sorted(GROUPS[group]))
    if label_year != imagery_year or features.ndim != 2 or features.shape[1] != 6 or len(features) != len(observed_codes):
        raise ValueError("SPECIALIST_YEAR_OR_FEATURES_INVALID")
    if not np.isfinite(features).all() or set(np.unique(observed_codes)) != set(codes):
        raise ValueError("SPECIALIST_TRAINING_CLASS_COVERAGE_REQUIRED")
    taxonomy = sha256((group + repr(codes)).encode()).hexdigest()
    digest = sha256(trained_on.encode())
    digest.update(features.tobytes())
    digest.update(observed_codes.tobytes())
    return fit_annual_forest(features, observed_codes, ClassificationDomain(group, taxonomy, codes),
                             digest.hexdigest(), fixture=False)


def merge(base, ordered_masks, nodata):
    """Retain the first eligible specialist per pixel and audit eligible overlaps."""
    import numpy as np

    result = base.copy()
    claims = np.zeros(base.shape, dtype="uint8")
    rows = []
    for code, mask in ordered_masks:
        if mask.shape != base.shape or not np.isin(mask, [0, 1, 255]).all():
            raise ValueError("SPECIALIST_BINARY_MASK_OR_GRID_INVALID")
        qualified = (mask == 1) & (base != nodata) & np.isin(base, ELIGIBLE[code])
        accepted = qualified & (claims == 0)
        claims[qualified] += 1
        result[accepted] = code
        rows.append({"code": code, "name": NAMES[code], "pixels": int(accepted.sum())})
    return result, rows, int((claims > 1).sum())


def intake(store, original):
    folder = store.safe_path(f"{FOLDER}/{original['year']}")
    raw = (folder / "integration.json").read_bytes()
    plan = SpecialistIntake.model_validate_json(raw)
    if plan.year != original["year"] or plan.base_sha256 != original["classification"]["sha256"]:
        raise ValueError("SPECIALIST_BASE_YEAR_OR_SHA_MISMATCH")
    layers = [(layer.class_code, layer.mask.local(folder)) for layer in plan.layers]
    for layer in plan.layers:
        layer.training_labels.local(folder)
    return plan, layers, sha256(raw).hexdigest()


def integrate(store, original, base_path):
    import rasterio

    from services.lcluc.annual_rasters import atomic_output, raster_profile
    from services.lcluc.banten_sentinel_explorer import receipt
    from services.lcluc.province_esri import write_json

    plan, layers, run_id = intake(store, original)
    folder = store.safe_path(f"data/curated/lcluc/hierarchy/{run_id}")
    folder.mkdir(parents=True, exist_ok=True)
    with rasterio.open(base_path) as raster:
        grid = {key: getattr(raster, key) for key in ("width", "height", "crs", "transform")}
        masks = []
        for code, path in layers:
            with rasterio.open(path) as mask:
                if mask.count != 1 or any(getattr(mask, key) != value for key, value in grid.items()):
                    raise ValueError("SPECIALIST_LAYER_GRID_MISMATCH")
                masks.append((code, mask.read(1)))
        result, rows, overlaps = merge(raster.read(1), masks, raster.nodata)
        output = folder / "integrated.tif"
        with atomic_output(output) as staged, rasterio.open(staged, "w", **raster_profile(grid, 1, "uint16", raster.nodata)) as target:
            target.write(result, 1)
    pin = receipt(output) | {"path": output.relative_to(store.root).as_posix()}
    report = {"id": run_id, "status": "REVIEW_CANDIDATE", "year": plan.year, "layers": rows,
              "overlaps": overlaps, "manifest": plan.model_dump(mode="json"), "asset": pin}
    write_json(folder / "report.json", report)
    return report
