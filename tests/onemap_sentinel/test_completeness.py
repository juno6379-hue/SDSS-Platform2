"""합성 영역·작은 실제 TIFF로 동시 완전성·누락 큐·안전 Gate를 시험한다."""
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import box, shape

from services.datahub.sentinel.completeness import (
    BANDS, simultaneous_support, grid_completeness, missing_queue_item, guarded_batch_preflight,
    grid_completeness_lower_bound,
)
from services.datahub.connectors.onemap.boundary import read_pin, sha256


def raster(path, values, transform, nodata=0):
    with rasterio.open(path, "w", driver="GTiff", height=values.shape[1], width=values.shape[2],
                       count=values.shape[0], dtype=str(values.dtype), crs="EPSG:6933",
                       transform=transform, nodata=nodata) as out:
        out.write(values)


def test_simultaneous_six_bands_and_scl_not_scl_only(tmp_path):
    image, scl = tmp_path / 'six.tif', tmp_path / 'scl.tif'
    values = np.ones((6, 10, 10), dtype='uint16')
    values[5, :, :5] = 0
    raster(image, values, from_origin(0, 100, 10, 10))
    classes = np.full((1, 10, 10), 4, dtype='uint8')
    classes[:, :5, 5:] = 9
    raster(scl, classes, from_origin(0, 100, 10, 10))
    result = simultaneous_support(image, BANDS, scl)
    assert result['present_pixels'] == 50 and result['clear_pixels'] == 25
    assert result['present'].area == 5000 and result['clear'].area == 2500
    assert result['footprint'].area == 10000


def test_missing_band_metadata_cannot_be_inferred_from_count(tmp_path):
    with pytest.raises(ValueError, match='SIX_EXACT_BANDS'):
        simultaneous_support(tmp_path/'x', ['B02'] * 6, tmp_path/'y')


def test_scl_footprint_outside_image_is_not_coverage(tmp_path):
    image, scl = tmp_path/'image.tif', tmp_path/'scl.tif'
    raster(image, np.ones((6, 10, 10), dtype='uint16'), from_origin(0, 100, 10, 10))
    raster(scl, np.full((1, 10, 10), 4, dtype='uint8'), from_origin(1000, 100, 10, 10))
    result = simultaneous_support(image, BANDS, scl)
    assert result['present_pixels'] == 0 and result['footprint'].area == 0


def test_partial_grid_is_not_full_and_duplicate_coverage_does_not_add():
    boundary, present = box(0, 0, 2000, 1000), box(0, 0, 1500, 1000)
    flags, affine, result = grid_completeness(boundary, present, box(0, 0, 1000, 1000))
    assert result['required_touched_grid_cells'] == 2
    assert result['fully_present_cells'] == 1
    assert result['fully_clear_cells'] == 1
    assert result['any_present_cells'] == 2
    assert flags[0, 1] & 2 == 0


def test_exact_missing_queue_excludes_existing_support_and_boundary_outside():
    boundary, present, clear = box(0, 0, 2000, 1000), box(0, 0, 1000, 1000), box(0, 0, 500, 1000)
    rows = missing_queue_item('banten', 2021, boundary, present, clear, {'boundary':'x'})
    assert len(rows) == 2
    missing = shape(rows[0]['geometry'])
    assert missing.area == 1_000_000 and missing.intersection(present).area == 0
    assert missing.difference(boundary).area == 0
    assert rows[0]['properties']['scene_id'] is None


def test_fast_spatial_index_preserves_holes_and_partial_cells_across_blocks():
    boundary = box(0,0,20000,2000).difference(box(8250,250,8750,750))
    present = boundary.difference(box(10000,0,10500,2000))
    clear = present.difference(box(12000,0,13000,2000))
    _,_,result = grid_completeness(boundary,present,clear)
    assert result['required_touched_grid_cells']==40
    assert result['fully_present_cells']==38 and result['any_present_cells']==40
    assert result['fully_clear_cells']==36 and result['any_clear_cells']==38


@pytest.mark.parametrize('edge',[500,1000,1500])
def test_conservative_grid_never_promotes_a_partial_cell(edge):
    boundary=box(0,0,2000,1000)
    present=box(0,0,edge,1000)
    flags,affine,result=grid_completeness_lower_bound(boundary,present,present)
    _,_,strict=grid_completeness(boundary,present,present)
    assert result['fully_present_cells']<=strict['fully_present_cells']
    assert result['grid_rule']=='CONSERVATIVE_LOWER_BOUND_REPORT_ONLY'
    assert not result['grid_used_for_collection_decision']
    for row,col in zip(*np.nonzero(flags&2)):
        x,y=affine@(int(col),int(row))
        assert box(x,y-1000,x+1000,y).intersection(boundary).difference(present).area<=.01


def test_reporting_grid_does_not_change_the_exact_missing_queue():
    boundary,present,clear=box(0,0,2000,1000),box(0,0,1500,1000),box(0,0,500,1000)
    before=missing_queue_item('banten',2021,boundary,present,clear,{})
    grid_completeness_lower_bound(boundary,present,clear)
    after=missing_queue_item('banten',2021,boundary,present,clear,{})
    assert before==after


def preflight(**updates):
    values = dict(ledger={'additional_maximum_bytes':1024**3,'new_charged_bytes':1,'rate_limit_active':False},
                  ledger_sha256='a', observed_ledger_sha256='a', active_collectors=0,
                  lock_exists=False, disk_free_bytes=1024**3, candidate_keys=['new'],
                  existing_keys=['old'], reserve_bytes=1024, shared_reservation_writable=False)
    return guarded_batch_preflight(**{**values, **updates})


def test_readonly_reference_cannot_start_with_new_local_budget():
    result = preflight()
    assert result['status'] == 'BLOCKED' and not result['collector_started']
    assert 'READ_ONLY_REFERENCE_LEDGER_NO_AUTHORIZED_RESERVATION_ADAPTER' in result['errors']


@pytest.mark.parametrize('changes,error', [
    ({'observed_ledger_sha256':'changed'}, 'LEDGER_PIN_DRIFT'),
    ({'active_collectors':1}, 'ACTIVE_COLLECTOR_OR_LOCK'),
    ({'active_collectors':None}, 'ACTIVE_COLLECTOR_STATUS_UNKNOWN'),
    ({'lock_exists':True}, 'ACTIVE_COLLECTOR_OR_LOCK'),
    ({'candidate_keys':['old']}, 'DUPLICATE_CANDIDATE'),
    ({'candidate_keys':['same','same']}, 'EXACT_DISTINCT_CANDIDATES_REQUIRED'),
    ({'reserve_bytes':True}, 'BATCH_BUDGET_INVALID'),
    ({'reserve_bytes':128*1024**2}, 'BATCH_BUDGET_INVALID'),
    ({'disk_free_bytes':0}, 'DISK_INSUFFICIENT'),
    ({'ledger':{'additional_maximum_bytes':1024**3,'new_charged_bytes':1,'rate_limit_active':True}}, 'GLOBAL_HTTP429_CIRCUIT'),
])
def test_guard_reasons(changes, error):
    assert error in preflight(**changes)['errors']


def test_reference_pin_and_path_containment(tmp_path):
    root = tmp_path/'reference'
    root.mkdir()
    raw = root/'source.json'
    raw.write_text('{}')
    assert read_pin(raw, sha256(raw), root) == raw
    with pytest.raises(ValueError, match='SOURCE_PIN'):
        read_pin(raw, 'bad', root)
    other = tmp_path/'outside'
    other.write_text('{}')
    with pytest.raises(ValueError):
        read_pin(other, sha256(other), root)
