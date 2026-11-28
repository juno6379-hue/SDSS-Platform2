"""읽기 전용 원본 감사와 exact polygon 누락 큐. 원격 수집·원장 쓰기는 없다."""
import json
import math
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import numpy as np
import rasterio
import shapely
from pyproj import Transformer
from rasterio.features import rasterize, shapes
from rasterio.transform import from_origin
from rasterio.warp import Resampling, reproject
from shapely.geometry import Polygon, box, mapping, shape

from services.datahub.connectors.onemap.boundary import PROVINCES, read_pin, sha256, write_json_new

BANDS = ("B02", "B03", "B04", "B08", "B11", "B12")
CLEAR = (4, 5, 6, 7, 11)


@lru_cache(maxsize=32)
def _projector(source):
    return Transformer.from_crs(source, "EPSG:6933", always_xy=True)


def _project(geometry, source):
    # Python 좌표별 재귀 변환 대신 Shapely2/pyproj 배열 경로를 사용한다.
    return shapely.transform(geometry, _projector(str(source)).transform, interleaved=False)


def _quad(dataset):
    # 경계곡선을 과도하게 직선화하지 않도록 각 변을 32개 구간으로 나눈다.
    points = []
    for start, end in [((0, 0), (dataset.width, 0)), ((dataset.width, 0), (dataset.width, dataset.height)),
                       ((dataset.width, dataset.height), (0, dataset.height)), ((0, dataset.height), (0, 0))]:
        for t in np.linspace(0, 1, 33)[:-1]:
            points.append(dataset.transform @ (start[0] + (end[0] - start[0]) * t,
                                               start[1] + (end[1] - start[1]) * t))
    return _project(Polygon(points), dataset.crs)


def _mask_geometry(mask, transform, crs):
    if not mask.any():
        return Polygon()
    polygons = [shape(g) for g, value in shapes(mask.astype("uint8"), mask=mask, transform=transform) if value == 1]
    # 긴 native pixel 변도 10m 이하로 분할해 parent/patch 경계 위치에 따른 투영 차이를 줄인다.
    return _project(shapely.segmentize(shapely.union_all(polygons), 10.0), crs)


def simultaneous_support(image_path: Path, band_names, scl_path: Path, scl_cache=None):
    """실제 raster mask와 동일 scene SCL을 image의 native 격자에서 교차한다."""
    if len(band_names) != 6 or set(band_names) != set(BANDS):
        raise ValueError("SIX_EXACT_BANDS_REQUIRED")
    with rasterio.open(image_path, "r") as image, rasterio.open(scl_path, "r") as scl:
        if image.count != 6 or scl.count != 1 or not image.crs or not scl.crs:
            raise ValueError("RASTER_BANDS_OR_CRS_INVALID")
        if max(image.width, image.height) > 2048 or max(scl.width, scl.height) > 8192:
            raise ValueError("LOCAL_RASTER_SIZE_LIMIT")
        values = image.read()
        finite = np.all(np.isfinite(values), axis=0)
        valid = np.all(image.read_masks() > 0, axis=0) & finite
        aligned = np.zeros((image.height, image.width), dtype="uint8")
        raw_scl = scl.read(1) if scl_cache is None else scl_cache
        reproject(raw_scl, aligned, src_transform=scl.transform, src_crs=scl.crs,
                  dst_transform=image.transform, dst_crs=image.crs, resampling=Resampling.nearest,
                  src_nodata=0, dst_nodata=0)
        present = valid & (aligned >= 1) & (aligned <= 11)
        clear = present & np.isin(aligned, CLEAR)
        footprint = _quad(image).intersection(_quad(scl))
        return {"footprint": footprint, "present": _mask_geometry(present, image.transform, image.crs),
                "clear": _mask_geometry(clear, image.transform, image.crs),
                "native_pixels": int(present.size), "present_pixels": int(present.sum()),
                "clear_pixels": int(clear.sum()), "image_crs": str(image.crs),
                "image_resolution": list(image.res)}


def grid_completeness(boundary, present, clear, resolution=1000):
    """누락 polygon과 동일한 1km index를 만든다. 부분 피복을 완전으로 세지 않는다."""
    if type(resolution) is not int or not 100 <= resolution <= 10000:
        raise ValueError("GRID_RESOLUTION_INVALID")
    left, bottom, right, top = boundary.bounds
    left, bottom = math.floor(left / resolution) * resolution, math.floor(bottom / resolution) * resolution
    right, top = math.ceil(right / resolution) * resolution, math.ceil(top / resolution) * resolution
    width, height = int((right - left) / resolution), int((top - bottom) / resolution)
    if width * height > 4_000_000:
        raise ValueError("REQUIRED_GRID_SIZE_LIMIT")
    transform = from_origin(left, top, resolution, resolution)
    required = rasterize([(mapping(boundary), 1)], out_shape=(height, width), transform=transform,
                         all_touched=True, dtype="uint8")
    # 1=required, 2=fully present, 4=fully clear, 8=partially present, 16=partially clear.
    flags = required.copy()
    fully = [0, 0]
    partial = [0, 0]
    for bit, geometry, index in [(2, present, 0), (4, clear, 1)]:
        if geometry.is_empty:
            continue
        touched = rasterize([(mapping(geometry), 1)], out_shape=(height, width), transform=transform,
                            all_touched=True, dtype="uint8") & required
        bins = defaultdict(list)
        for row, col in zip(*np.nonzero(touched), strict=True):
            bins[(int(row) // 8, int(col) // 8)].append((int(row), int(col)))
        parts = list(shapely.get_parts(geometry))
        tree = shapely.STRtree(parts)
        # 전 주의 큰 polygon을 매1km셀마다 intersection하지 않고 8×8셀 영역으로 먼저 자른다.
        for (block_row, block_col), cells in bins.items():
            x, y = transform @ (block_col * 8, block_row * 8)
            block = box(x, y - 8 * resolution, x + 8 * resolution, y)
            local_parts = [parts[int(i)].intersection(block) for i in tree.query(block)]
            local = shapely.union_all(local_parts)
            local_boundary = boundary.intersection(block)
            shapely.prepare(local)
            shapely.prepare(local_boundary)
            for row, col in cells:
                x, y = transform @ (col, row)
                rectangle = box(x, y - resolution, x + resolution, y)
                cell = rectangle if local_boundary.covers(rectangle) else rectangle.intersection(local_boundary)
                if cell.area <= 0:
                    continue
                covered = cell.area if local.covers(cell) else cell.intersection(local).area
                if covered > 0:
                    flags[row, col] |= 8 if index == 0 else 16
                    partial[index] += 1
                if cell.area - covered <= 0.01:
                    flags[row, col] |= bit
                    fully[index] += 1
    return flags, transform, {"required_touched_grid_cells": int(required.sum()),
            "fully_present_cells": fully[0], "fully_clear_cells": fully[1],
            "any_present_cells": partial[0], "any_clear_cells": partial[1],
            "grid_rule": "BOUNDARY_INTERSECTING_GRID; FULL_REQUIRES_ENTIRE_CLIPPED_CELL; 0.01m2 numeric tolerance"}


def missing_queue_item(province, year, boundary, present, clear, pins):
    """점/중심 샘플이 아닌 고정 geometry의 차집합을 큐에 보존한다."""
    return [{"type": "Feature", "geometry": mapping(geometry), "properties": {
        "province": province, "year": year, "reason": reason, "required_bands": list(BANDS) + ["SCL"],
        "missing_area_m2": geometry.area, "crs": "EPSG:6933", "source_pins": pins,
        "scene_id": None, "status": "PLANNED_GEOMETRY_NOT_EXECUTABLE_NO_SCENE_PIN"}}
        for reason, geometry in [("MISSING_SIMULTANEOUS_SIX_BANDS_SCL", boundary.difference(present)),
                                 ("PRESENT_BUT_NOT_CLEAR", present.difference(clear))] if not geometry.is_empty]


def grid_completeness_lower_bound(boundary, present, clear, resolution=1000):
    """보고용 full-cell 하한. 원격 수집 결정에는 native exact polygon만 사용한다."""
    if type(resolution) is not int or not 100<=resolution<=10000:
        raise ValueError('GRID_RESOLUTION_INVALID')
    left,bottom,right,top=boundary.bounds
    left,bottom=math.floor(left/resolution)*resolution,math.floor(bottom/resolution)*resolution
    right,top=math.ceil(right/resolution)*resolution,math.ceil(top/resolution)*resolution
    width,height=int((right-left)/resolution),int((top-bottom)/resolution)
    if width*height>4_000_000:
        raise ValueError('REQUIRED_GRID_SIZE_LIMIT')
    affine=from_origin(left,top,resolution,resolution)
    def touched(geometry):
        if geometry.is_empty:
            return np.zeros((height,width),dtype='uint8')
        return rasterize([(mapping(geometry),1)],out_shape=(height,width),transform=affine,
                         all_touched=True,dtype='uint8')
    required=touched(boundary)
    flags=required.copy()
    full_counts,any_counts=[],[]
    for bit,any_bit,geometry in [(2,8,present),(4,16,clear)]:
        any_support=touched(geometry)&required
        # gap의 경계선 접촉만 있어도 full에서 빼므로 과소계수 가능, partial의 full 승격은 없다.
        gap=touched(boundary.difference(geometry))
        full=any_support&(~gap.astype(bool))
        flags[any_support.astype(bool)]|=any_bit
        flags[full.astype(bool)]|=bit
        full_counts.append(int(full.sum()))
        any_counts.append(int(any_support.sum()))
    return flags,affine,{'required_touched_grid_cells':int(required.sum()),
        'fully_present_cells':full_counts[0],'fully_clear_cells':full_counts[1],
        'any_present_cells':any_counts[0],'any_clear_cells':any_counts[1],
        'grid_rule':'CONSERVATIVE_LOWER_BOUND_REPORT_ONLY',
        'full_cell_error_direction':'MAY_UNDERCOUNT_BOUNDARY_TOUCH; NEVER_PROMOTE_PARTIAL',
        'grid_used_for_collection_decision':False,'coverage_area_and_queue_source':'EXACT_NATIVE_GEOMETRY'}


def guarded_batch_preflight(*, ledger, ledger_sha256, observed_ledger_sha256,
                            active_collectors, lock_exists, disk_free_bytes, candidate_keys,
                            existing_keys, reserve_bytes, shared_reservation_writable=False):
    """읽기 전용 전역원장을 다른 repo의 새 예산으로 우회하지 않는다."""
    errors = []
    if active_collectors is None:
        errors.append("ACTIVE_COLLECTOR_STATUS_UNKNOWN")
    if ledger_sha256 != observed_ledger_sha256:
        errors.append("LEDGER_PIN_DRIFT")
    if active_collectors or lock_exists:
        errors.append("ACTIVE_COLLECTOR_OR_LOCK")
    if ledger.get("rate_limit_active"):
        errors.append("GLOBAL_HTTP429_CIRCUIT")
    remaining = ledger["additional_maximum_bytes"] - ledger["new_charged_bytes"]
    if type(reserve_bytes) is not int or not 0 < reserve_bytes <= 64 * 1024 * 1024 or reserve_bytes > remaining:
        errors.append("BATCH_BUDGET_INVALID")
    if disk_free_bytes < reserve_bytes * 4:
        errors.append("DISK_INSUFFICIENT")
    if not candidate_keys or len(candidate_keys) > 6 or len(set(candidate_keys)) != len(candidate_keys):
        errors.append("EXACT_DISTINCT_CANDIDATES_REQUIRED")
    if set(candidate_keys) & set(existing_keys):
        errors.append("DUPLICATE_CANDIDATE")
    if not shared_reservation_writable:
        errors.append("READ_ONLY_REFERENCE_LEDGER_NO_AUTHORIZED_RESERVATION_ADAPTER")
    return {"status": "BLOCKED" if errors else "PREFLIGHT_READY_NOT_STARTED", "errors": errors,
            "remaining_global_bytes": remaining, "reserve_bytes": reserve_bytes,
            "stop_on_first_failure": True, "stop_on_429": True, "collector_started": False}


def audit(reference_root: Path, boundary_receipt: dict, manifest: Path, expected_manifest_sha: str,
          ledger_path: Path, expected_ledger_sha: str, output: Path, *, minimum_patches=28):
    """실제 1779여개 patch를 순차 처리하며 참조 저장소 파일은 읽기만 한다."""
    reference_root, output = Path(reference_root).resolve(), Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError("AUDIT_OUTPUT_NOT_EMPTY")
    if shutil.disk_usage(output).free < 1024 ** 3:
        raise ValueError("LOCAL_AUDIT_DISK_INSUFFICIENT")
    manifest = read_pin(manifest, expected_manifest_sha, reference_root)
    ledger_path = read_pin(ledger_path, expected_ledger_sha, reference_root)
    rows = json.loads(manifest.read_text(encoding="utf-8"))["scenes"]
    boundary = json.loads(Path(boundary_receipt["boundary"]["path"]).read_text(encoding="utf-8"))
    if sha256(Path(boundary_receipt["boundary"]["path"])) != boundary_receipt["boundary"]["sha256"]:
        raise ValueError("BOUNDARY_RECEIPT_DRIFT")
    boundaries, projection_repairs = {}, []
    for feature in boundary["features"]:
        province = feature["properties"]["province_id"]
        original = shape(feature["geometry"])
        if not original.is_valid:
            raise ValueError("INVALID_SOURCE_BOUNDARY")
        projected = _project(original, "EPSG:4326")
        if not projected.is_valid:
            corrected = shapely.make_valid(projected)
            delta = abs(corrected.area - projected.area)
            if delta > max(1.0, projected.area * 1e-9):
                raise ValueError("PROJECTED_BOUNDARY_REPAIR_AREA_EXCEEDS_NUMERIC_TOLERANCE")
            projection_repairs.append({"province": province, "method": "make_valid_after_projection_only",
                "source_changed": False, "before_area_m2": projected.area,
                "after_area_m2": corrected.area, "absolute_area_change_m2": delta})
            projected = corrected
        boundaries[province] = projected
    grouped = defaultdict(lambda: {"physical": 0, "eligible": 0, "verified": 0,
                                   "footprints": [], "present": [], "clear": []})
    failures, verified_files, scl_cache, seen_images = [], {}, {}, set()
    def checked(path, expected):
        key = str(Path(path).resolve())
        if key not in verified_files:
            verified_files[key] = str(read_pin(Path(path), expected, reference_root))
        elif sha256_cache[key] != expected:
            raise ValueError("CONFLICTING_FILE_PIN")
        sha256_cache[key] = expected
        return Path(verified_files[key])
    sha256_cache = {}
    for index, row in enumerate(rows):
        province, year = row.get("province") or row.get("aoi"), int(row["year"])
        if province not in boundaries or not 2020 <= year <= 2025:
            raise ValueError("MANIFEST_CELL_OUT_OF_SCOPE")
        group = grouped[(province, year)]
        image = Path(row.get("image_path", ""))
        if image.is_file():
            group["physical"] += 1
        group["eligible"] += row.get("quality_status") == "quality_eligible"
        try:
            image = checked(image, row["patch_sha256"]["image"])
            # 같은 파일/scene을 여러 행으로 적어 coverage를 부풀리지 않는다.
            identity = (province, year, str(image))
            if identity in seen_images:
                raise ValueError("DUPLICATE_IMAGE_RECORD")
            seen_images.add(identity)
            scl = row["source_crops"]["raw-SCL.tif"]
            scl_path = checked(Path(scl["path"]), scl["sha256"])
            stac = row["stac_item"]
            stac_path = checked(Path(stac["path"]), stac["sha256"])
            source = json.loads(stac_path.read_text(encoding="utf-8"))
            if source["id"] != row["scene_id"] or int(source["properties"]["datetime"][:4]) != year:
                raise ValueError("SCENE_OR_YEAR_MISMATCH")
            for band in BANDS + ("SCL",):
                crop = row["source_crops"][f"raw-{band}.tif"]
                checked(Path(crop["path"]), crop["sha256"])
                if crop["source"].split("?", 1)[0] != source["assets"][band]["href"].split("?", 1)[0]:
                    raise ValueError("SOURCE_BAND_STAC_URI_MISMATCH")
            if str(scl_path) not in scl_cache:
                with rasterio.open(scl_path, "r") as dataset:
                    scl_cache[str(scl_path)] = dataset.read(1)
            support = simultaneous_support(image, row["bands"], scl_path, scl_cache[str(scl_path)])
            for field, destination in [("footprint", "footprints"), ("present", "present"), ("clear", "clear")]:
                group[destination].append(support[field])
            group["verified"] += 1
        except (KeyError, ValueError, OSError, rasterio.errors.RasterioError) as exc:
            failures.append({"index": index, "province": province, "year": year,
                             "type": type(exc).__name__, "message": str(exc)[:500]})
        if (index + 1) % 200 == 0:
            print(json.dumps({"checked_patch_rows": index + 1, "failed": len(failures)}), flush=True)
    cells, queue = [], []
    pins = {"manifest": expected_manifest_sha, "ledger": expected_ledger_sha,
            "boundary": boundary_receipt["boundary"]["sha256"]}
    for province in PROVINCES:
        for year in range(2020, 2026):
            group, boundary_geom = grouped[(province, year)], boundaries[province]
            footprint, present, clear = [shapely.union_all(group[field]).intersection(boundary_geom)
                                        for field in ("footprints", "present", "clear")]
            grid, affine, counts = grid_completeness(boundary_geom, present, clear)
            grid_path = output / f"{province}-{year}-required-and-support.tif"
            with rasterio.open(grid_path, "w", driver="GTiff", height=grid.shape[0], width=grid.shape[1],
                               count=1, dtype="uint8", crs="EPSG:6933", transform=affine,
                               compress="deflate") as dataset:
                dataset.write(grid, 1)
            cell = {"province": province, "year": year, "physical_patch_records": group["physical"],
                    "manifest_quality_eligible": group["eligible"], "verified_six_band_scl_patches": group["verified"],
                    "minimum_patch_threshold": minimum_patches,
                    "minimum_patch_met": group["eligible"] >= minimum_patches,
                    "boundary_area_m2": boundary_geom.area, "footprint_area_m2": footprint.area,
                    "simultaneous_present_area_m2": present.area, "clear_joint_area_m2": clear.area,
                    "present_coverage_pct": 100 * present.area / boundary_geom.area,
                    "clear_coverage_pct": 100 * clear.area / boundary_geom.area,
                    "missing_joint_area_m2": boundary_geom.difference(present).area,
                    "required_grid": {"path": str(grid_path), "sha256": sha256(grid_path)}, **counts}
            cells.append(cell)
            queue.extend(missing_queue_item(province, year, boundary_geom, present, clear, pins))
    queue_path = output / "exact-missing-queue.geojson"
    write_json_new(queue_path, {"type": "FeatureCollection", "crs": {"type": "name", "properties": {"name": "EPSG:6933"}},
                                "features": queue})
    # 한 바이트라도 바뀌면 현재 snapshot의 완료 판정을 내리지 않는다.
    read_pin(manifest, expected_manifest_sha, reference_root)
    read_pin(ledger_path, expected_ledger_sha, reference_root)
    result = {"schema_version": "onemap-sentinel-completeness/1.0",
              "status": "VERIFIED_REAL_LOCAL_AUDIT" if not failures else "BLOCKED_SOURCE_ERRORS_PARTIAL_AUDIT",
              "acquired_at": datetime.now(timezone.utc).isoformat(), "source_pins": pins,
              "physical_records": sum(x["physical_patch_records"] for x in cells),
              "manifest_quality_eligible": sum(x["manifest_quality_eligible"] for x in cells),
              "verified_joint_patch_count": sum(x["verified_six_band_scl_patches"] for x in cells),
              "minimum_patch_cells_met": sum(x["minimum_patch_met"] for x in cells),
              "full_spatial_coverage": all(x["missing_joint_area_m2"] <= 0.01 for x in cells),
              "cells": cells, "failures": failures, "verified_file_count": len(verified_files),
              "missing_queue": {"path": str(queue_path), "sha256": sha256(queue_path), "features": len(queue)},
              "remote_downloads": 0, "ledger_writes": 0, "collector_started": False,
              "reference_ledger_unchanged": True, "training_ready": False,
              "boundary_authority_approval_pending": True,
              "projection_topology_repairs": projection_repairs,
              "notes": ["1km grid is an inventory index; exact missing polygon uses native pixel masks",
                        "SWIR resampled to10m is not new native10m observation", "No label reused as independent ground truth"]}
    write_json_new(output / "completeness.json", result)
    return result
