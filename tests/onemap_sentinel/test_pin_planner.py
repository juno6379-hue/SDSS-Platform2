import hashlib
import json

from affine import Affine
from pyproj import Transformer
from shapely.geometry import box,mapping
from shapely.ops import transform
import pytest

from services.datahub.connectors.onemap.boundary import sha256
from services.datahub.sentinel.completeness import BANDS,_project
from services.datahub.sentinel.pin_planner import build_single_pilot_plan,asset_uri


def fixture(tmp_path):
    crs='EPSG:32648'
    native=box(500000,979520,520480,1000000)
    geography=transform(Transformer.from_crs(crs,'EPSG:4326',always_xy=True).transform,native)
    boundary=tmp_path/'boundary.json'
    boundary.write_text(json.dumps({'features':[{'properties':{'province_id':'banten'},'geometry':mapping(geography)}]}))
    bsha=sha256(boundary)
    queue=tmp_path/'queue.json'
    queue.write_text(json.dumps({'crs':{'properties':{'name':'EPSG:6933'}},'features':[{
        'geometry':mapping(_project(native,crs)), 'properties':{'province':'banten','year':2021,
        'required_bands':list(BANDS)+['SCL'],'source_pins':{'boundary':bsha},
        'reason':'MISSING_SIMULTANEOUS_SIX_BANDS_SCL','missing_area_m2':native.area}}]}))
    assets={}
    for band in BANDS+('SCL',):
        gsd=20 if band in ('B11','B12','SCL') else 10
        assets[band]={'href':'https://sentinel2l2a01.blob.core.windows.net/sentinel2-l2/synthetic/'+band+'.tif',
                     'proj:shape':[20480//gsd]*2,'proj:transform':list(Affine(gsd,0,500000,0,-gsd,1000000))[:6]}
    item={'id':'S2A_MSIL2A_20210601_SYNTHETIC','collection':'sentinel-2-l2a',
          'properties':{'datetime':'2021-06-01T00:00:00Z','proj:epsg':32648},
          'geometry':mapping(geography),'assets':assets}
    raw=json.dumps(item).encode()
    stac=tmp_path/hashlib.sha256(raw).hexdigest()
    stac.write_bytes(raw)
    scenes=tmp_path/'scenes.json'
    scenes.write_text(json.dumps({'scenes':[{'province':'banten','year':2021,'scene_id':item['id'],
                                            'stac_item_path':str(stac)}]}))
    native_dir=tmp_path/'native'
    native_dir.mkdir()
    return dict(queue_path=queue,queue_sha=sha256(queue),queue_size=queue.stat().st_size,
        boundary_path=boundary,boundary_sha=bsha,scenes_path=scenes,scenes_sha=sha256(scenes),
        native_checkpoints=native_dir,expected_ledger_sha='a'*64,expected_features=1)


def test_deterministic_scene_asset_windows_and_stable_idempotency(tmp_path):
    kwargs=fixture(tmp_path)
    first=build_single_pilot_plan(**kwargs,output=tmp_path/'first.json')
    second=build_single_pilot_plan(**{**kwargs,'expected_ledger_sha':'b'*64},output=tmp_path/'second.json')
    assert first['idempotency_key']==second['idempotency_key']
    assert first['B02_window']==second['B02_window']
    assert set(first['assets'])==set(BANDS+('SCL',)) and first['maximum_pilots']==1
    assert first['physical_held_footprint_overlap_m2']==0
    assert all(a['etag'] is None and a['size'] is None for a in first['assets'].values())
    assert first['remote_downloads']==0 and not first['learning_ready']
    with pytest.raises(ValueError,match='NO_LOCAL_PINNED_SCENE'):
        build_single_pilot_plan(**kwargs,output=tmp_path/'duplicate.json',existing_keys=[first['idempotency_key']])


def test_queue_size_sha_and_boundary_are_preconditions(tmp_path):
    kwargs=fixture(tmp_path)
    with pytest.raises(ValueError,match='PIN_DRIFT'):
        build_single_pilot_plan(**{**kwargs,'queue_size':kwargs['queue_size']+1},output=tmp_path/'none.json')
    assert not (tmp_path/'none.json').exists()


@pytest.mark.parametrize('url',[
    'https://evil.invalid/sentinel2-l2/x',
    'http://sentinel2l2a01.blob.core.windows.net/sentinel2-l2/x',
    'https://sentinel2l2a01.blob.core.windows.net/sentinel2-l2/%2e%2e/x',
    'https://sentinel2l2a01.blob.core.windows.net/sentinel2-l2/x?sig=secret',
])
def test_unknown_signed_or_traversal_asset_is_rejected(url):
    with pytest.raises(ValueError,match='PINNED_SENTINEL_ASSET_URI'):
        asset_uri(url)
