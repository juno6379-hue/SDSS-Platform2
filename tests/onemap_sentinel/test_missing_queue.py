import json
from shapely.geometry import box, mapping
import pytest

from services.datahub.connectors.onemap.boundary import sha256
from services.datahub.sentinel.completeness import BANDS
from services.datahub.sentinel.queue import derive_missing_targets, plan_missing_batch


def queue(path, note='first'):
    features = []
    for province, size in [('banten', 1), ('west_java', 2)]:
        features.append({'type':'Feature','geometry':mapping(box(0,0,size*1000,1000)),
            'properties':{'province':province,'year':2021,'reason':'MISSING_SIMULTANEOUS_SIX_BANDS_SCL',
                          'required_bands':list(BANDS)+['SCL']}})
    path.write_text(json.dumps({'type':'FeatureCollection','note':note,
        'crs':{'properties':{'name':'EPSG:6933'}},'features':features}))
    return path


def test_target_identity_is_stable_across_receipt_only_changes(tmp_path):
    first = queue(tmp_path/'first.json')
    a = derive_missing_targets(first, sha256(first))
    second = queue(tmp_path/'second.json', 'new timestamp; same geometry')
    b = derive_missing_targets(second, sha256(second))
    assert [x['target_id'] for x in a] == [x['target_id'] for x in b]
    assert a[0]['queue']['sha256'] != b[0]['queue']['sha256']
    assert len(derive_missing_targets(second, sha256(second), existing_target_ids=[a[0]['target_id']])) == 1
    assert not a[0]['executable']


def test_plan_never_promotes_geometry_only_targets_to_execution(tmp_path):
    path = queue(tmp_path/'queue.json')
    targets = derive_missing_targets(path, sha256(path))
    result = plan_missing_batch(targets, ledger={'additional_maximum_bytes':2**30,
        'new_charged_bytes':0, 'batches':{}}, ledger_sha='a', current_ledger_sha='a',
        active_collectors=0, lock_exists=False, disk_free_bytes=2**30)
    assert result['status'] == 'BLOCKED'
    assert 'EXACT_SCENE_ASSET_WINDOW_PINS_MISSING' in result['errors']
    assert not result['collector_started']


def test_queue_pin_and_maximum_are_enforced(tmp_path):
    path = queue(tmp_path/'queue.json')
    with pytest.raises(ValueError, match='QUEUE_PIN'):
        derive_missing_targets(path, 'wrong')
    with pytest.raises(ValueError, match='TARGET_COUNT'):
        derive_missing_targets(path, sha256(path), maximum=7)
