"""작은 native frame으로 parent별 재사용·재개·pixel 일치 검증을 시험한다."""
import json
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import box, mapping

from services.datahub.connectors.onemap.boundary import PROVINCES, sha256
from services.datahub.sentinel.completeness import BANDS
from services.datahub.sentinel.held import run_held_audit


def write_tif(path,values,affine):
    with rasterio.open(path,'w',driver='GTiff',height=values.shape[1],width=values.shape[2],
        count=values.shape[0],dtype=str(values.dtype),crs='EPSG:6933',transform=affine,nodata=0) as ds:
        ds.write(values)


def fixture(tmp_path):
    ref=tmp_path/'reference'
    ref.mkdir()
    parent=ref/'image.tif'
    affine=from_origin(0,2600,10,10)
    values=np.ones((6,260,260),dtype='uint16')
    write_tif(parent,values,affine)
    crops={}
    assets={}
    for band in BANDS+('SCL',):
        path=ref/(band+'.tif')
        data=np.full((1,130,130),4 if band=='SCL' else 1,dtype='uint8')
        write_tif(path,data,from_origin(0,2600,20,20))
        uri='https://example.test/'+band+'.tif'
        crops['raw-'+band+'.tif']={'path':str(path),'sha256':sha256(path),'source':uri}
        assets[band]={'href':uri}
    stac=ref/'stac.json'
    stac.write_text(json.dumps({'id':'synthetic-scene','properties':{'datetime':'2021-06-01'},'assets':assets}))
    patch=ref/'patch.tif'
    write_tif(patch,values[:,:256,:256],affine)
    row={'province':'banten','year':2021,'scene_id':'synthetic-scene','bands':list(BANDS),
        'image_path':str(patch),'patch_sha256':{'image':sha256(patch)},'window_in_source':[0,0,256,256],
        'quality_status':'quality_eligible','source_window':{'path':str(parent),'sha256':sha256(parent)},
        'source_crops':crops,'stac_item':{'path':str(stac),'sha256':sha256(stac)}}
    manifest=ref/'manifest.json'
    manifest.write_text(json.dumps({'scenes':[row]}))
    ledger=ref/'ledger.json'
    ledger.write_text('{}')
    boundary=tmp_path/'boundary.geojson'
    boundary.write_text(json.dumps({'type':'FeatureCollection','features':[
        {'type':'Feature','properties':{'province_id':p},'geometry':mapping(box(i,.0,i+.02,.02))}
        for i,p in enumerate(PROVINCES)]}))
    receipt={'boundary':{'path':str(boundary),'sha256':sha256(boundary)}}
    return ref,receipt,manifest,ledger,patch


def test_held_audit_includes_unpatched_edges_and_can_resume_checkpoints(tmp_path):
    ref,receipt,manifest,ledger,patch=fixture(tmp_path)
    output=tmp_path/'audit'
    result=run_held_audit(ref,receipt,manifest,sha256(manifest),ledger,sha256(ledger),output)
    assert result['verified_joint_patch_count']==1 and result['verified_parent_frames']==1
    assert result['local_unpatched_remainder_pixels_included']==260*260-256*256
    assert result['cell_count']==36 and not result['collector_started']
    assert result['reference_ledger_unchanged'] and not result['full_spatial_coverage']
    # 최종화 직전 중단을 모사한다. source·checkpoint는 그대로 두고 파생 최종화 파일만 제거한다.
    (output/'completeness.json').unlink()
    (output/'exact-missing-queue.geojson').unlink()
    again=run_held_audit(ref,receipt,manifest,sha256(manifest),ledger,sha256(ledger),output)
    assert again['verified_joint_patch_count']==1
    patch.write_bytes(b'fixture-drift')
    with pytest.raises(ValueError,match='SOURCE_PIN_MISMATCH'):
        run_held_audit(ref,receipt,manifest,sha256(manifest),ledger,sha256(ledger),output)
