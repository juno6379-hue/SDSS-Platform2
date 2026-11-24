"""단일6밴드+SCL pilot. 기본read-only, 명시execute만 공유원장 예약과 원격IO를 수행한다."""
from datetime import datetime, timezone
import json
from pathlib import Path
import re

from affine import Affine
import numpy as np
import rasterio
from rasterio.windows import Window
from rasterio.warp import reproject,Resampling

from services.datahub.connectors.onemap.boundary import sha256,write_json_new
from .completeness import BANDS,CLEAR
from .pin_planner import canonical_sha,asset_uri
from .remote import RemoteIO,PinnedRangeReader
from .shared_ledger import SharedLedger

WORKSPACE_ROOT=Path(__file__).resolve().parents[3]


def _safe_error(exc):
    return re.sub(r'https://[^\s\"\']+','https://<redacted>',str(exc))[:600]


def validate_plan(path,expected_sha):
    path=Path(path)
    if sha256(path)!=expected_sha:
        raise ValueError('PILOT_PLAN_PIN_DRIFT')
    plan=json.loads(path.read_text(encoding='utf-8'))
    if (plan['schema_version']!='sentinel-single-window-pin-plan/1.0' or plan['maximum_pilots']!=1
        or list(plan['assets'])!=list(BANDS)+['SCL'] or not plan['stop_on_first_failure']
        or not plan['stop_on_429'] or plan['reservation_bytes']>32*1024**2
        or plan['B02_window'][2:]!=[256,256]):
        raise ValueError('SINGLE_BOUNDED_PILOT_POLICY_REQUIRED')
    for name in ('boundary','stac','scene_manifest'):
        if sha256(Path(plan[name]['path']))!=plan[name]['sha256']:
            raise ValueError('PILOT_'+name.upper()+'_PIN_DRIFT')
    q=plan['queue']
    if Path(q['path']).stat().st_size!=q['bytes'] or sha256(Path(q['path']))!=q['sha256']:
        raise ValueError('PILOT_EXACT_QUEUE_PIN_DRIFT')
    stac=json.loads(Path(plan['stac']['path']).read_text(encoding='utf-8'))
    if stac['id']!=plan['scene_id']:
        raise ValueError('PILOT_SCENE_PIN_MISMATCH')
    for band,asset in plan['assets'].items():
        asset_uri(asset['source_uri'])
        if canonical_sha(stac['assets'][band])!=asset['stac_asset_sha256']:
            raise ValueError('PILOT_ASSET_STAC_PIN_DRIFT')
    identity={'province':plan['province'],'year':plan['year'],'scene_id':plan['scene_id'],
              'B02_window':plan['B02_window'],'assets':list(plan['assets'])}
    if plan['idempotency_key']!='sdss2-pilot-'+canonical_sha(identity):
        raise ValueError('PILOT_IDEMPOTENCY_KEY_NOT_DETERMINISTIC')
    return plan


def read_asset_window(remote,asset):
    reader=PinnedRangeReader(remote,asset)
    uri=asset['source_uri']
    def opener(path,mode='r'):
        if path!=uri:
            raise FileNotFoundError('UNREQUESTED_COG_SIDECAR')
        return reader
    try:
        with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR'):
            with rasterio.open(uri,opener=opener) as dataset:
                if (dataset.count!=1 or list(dataset.shape)!=asset['shape']
                    or str(dataset.crs)!=asset['crs'] or list(dataset.transform)[:6]!=asset['transform']):
                    raise ValueError('REMOTE_RASTER_PROFILE_STAC_MISMATCH')
                window=Window(*asset['window'])
                array=dataset.read(1,window=window)
                profile={'driver':'GTiff','count':1,'width':array.shape[1],'height':array.shape[0],
                    'dtype':str(array.dtype),'crs':dataset.crs,'transform':dataset.window_transform(window),
                    'nodata':0,'compress':'deflate'}
        return array,profile
    except Exception:
        if reader.last_error:
            raise reader.last_error
        raise


def _write_tif(path,array,profile):
    if Path(path).exists():
        raise ValueError('IMMUTABLE_PILOT_RAW_ALREADY_EXISTS')
    with rasterio.open(path,'w',**profile) as dataset:
        dataset.write(array if array.ndim==3 else array[None,:,:])


def run_pilot(plan_path,plan_sha,ledger_path,evidence_dir,raw_root,*,execute=False,
              remote_factory=RemoteIO,read_window=read_asset_window,collector_scan=None):
    plan=validate_plan(plan_path,plan_sha)
    kwargs={} if collector_scan is None else {'collector_scan':collector_scan}
    adapter=SharedLedger(ledger_path,writable=execute,**kwargs)
    before=plan['expected_current_ledger_sha256']
    preflight=adapter.preflight(before,plan['reservation_bytes'],key=plan['idempotency_key'],config_sha=plan_sha)
    if not execute:
        return {**preflight,'asset_pin_state':'HEAD_REQUIRED_NOT_EXECUTED','remote_requests':0,
                'ledger_writes':0,'acceptance_blockers':plan['acceptance_blockers']}
    if preflight['status']!='PREFLIGHT_READY':
        raise ValueError('PILOT_PREFLIGHT_BLOCKED:'+','.join(preflight['errors']))
    evidence_dir=Path(evidence_dir).resolve()
    evidence_dir.relative_to(WORKSPACE_ROOT/'evidence/onemap_sentinel')
    Path(raw_root).resolve().relative_to(WORKSPACE_ROOT/'data/raw/sentinel-pilots')
    evidence_dir.mkdir(parents=True,exist_ok=True)
    if any(evidence_dir.iterdir()):
        raise ValueError('PILOT_EVIDENCE_NOT_EMPTY')
    raw_dir=Path(raw_root).resolve()/plan['idempotency_key']
    if raw_dir.exists():
        raise ValueError('DUPLICATE_RAW_PILOT_DIRECTORY')
    write_json_new(evidence_dir/'preflight.json',preflight)
    write_json_new(evidence_dir/'ledger-before.json',adapter.snapshot(before))
    events=[]
    client=None
    assets=[]
    qa=None
    error=None
    current=before
    with adapter.execution_lease():
        # lease 획득 중 legacy가 먼저 갱신해도 CAS로 중지하며 오래된 SHA로 덮어쓰지 않는다.
        current=adapter.reserve(current,plan['idempotency_key'],plan_sha,plan['reservation_bytes'])
        events.append({'action':'reserve','before_sha256':before,'after_sha256':current,
                       'bytes':plan['reservation_bytes']})
        try:
            raw_dir.mkdir(parents=True,exist_ok=False)
            previous=current
            current=adapter.mark_io_started(current,plan['idempotency_key'])
            events.append({'action':'mark_io_started','before_sha256':previous,'after_sha256':current})
            client=remote_factory(plan['reservation_bytes'],spacing=plan['request_spacing_seconds'])
            sealed=client.seal_assets(plan)
            sealed_plan={**plan,'assets':sealed,'status':'HEAD_SEALED','source_plan_sha256':plan_sha,
                         'sealed_at':datetime.now(timezone.utc).isoformat()}
            write_json_new(evidence_dir/'sealed-plan.json',sealed_plan)
            image=np.zeros((6,256,256),dtype='uint16')
            aligned_scl=np.zeros((256,256),dtype='uint8')
            target=Affine(*plan['target_affine'])
            for index,band in enumerate(BANDS+('SCL',)):
                array,profile=read_window(client,sealed[band])
                if array.shape!=(sealed[band]['window'][3],sealed[band]['window'][2]):
                    raise ValueError('CROPPED_WINDOW_SHAPE_MISMATCH')
                native_path=raw_dir/('native-'+band+'.tif')
                _write_tif(native_path,array,profile)
                assets.append({'band':band,'path':str(native_path),'sha256':sha256(native_path),
                    'source_uri':sealed[band]['source_uri'],'source_etag':sealed[band]['etag'],
                    'source_size':sealed[band]['size'],'window':sealed[band]['window']})
                destination=aligned_scl if band=='SCL' else image[index]
                reproject(array,destination,src_transform=profile['transform'],src_crs=profile['crs'],
                    dst_transform=target,dst_crs=plan['native_crs'],src_nodata=0,dst_nodata=0,
                    resampling=Resampling.nearest if band=='SCL' else Resampling.bilinear)
            clear=(np.all(image>0,axis=0)&np.isin(aligned_scl,CLEAR))
            qa={'pixel_count':int(clear.size),'clear_pixels':int(clear.sum()),
                'clear_fraction':float(clear.mean()),'minimum_clear_fraction':plan['qa_minimum_clear_fraction'],
                'status':'PASS' if clear.mean()>=plan['qa_minimum_clear_fraction'] else 'INSUFFICIENT',
                'same_scene_all_assets':True,'independent_accuracy_measured':False}
            profile={'driver':'GTiff','count':6,'width':256,'height':256,'dtype':'uint16',
                'crs':plan['native_crs'],'transform':target,'nodata':0,'compress':'deflate'}
            _write_tif(raw_dir/'image.tif',image,profile)
            _write_tif(raw_dir/'aligned-SCL.tif',aligned_scl,{**profile,'count':1,'dtype':'uint8'})
            _write_tif(raw_dir/'quality.tif',clear.astype('uint8'),{**profile,'count':1,'dtype':'uint8'})
        except Exception as exc:
            error={'type':type(exc).__name__,'message':_safe_error(exc)}
            if client:
                client.stopped=True
        measured=client.body_bytes if client else 0
        known=client.measurement_complete if client else True
        rate=client.rate_limit if client else None
        charge=measured if known else plan['reservation_bytes']
        if charge>plan['reservation_bytes']:
            charge=plan['reservation_bytes']
            known=False
        good=error is None and qa and qa['status']=='PASS' and len(assets)==7
        receipt={'status':'VERIFIED_REAL' if good else 'BLOCKED','execution_status':'PILOT_QA_PASS' if good else 'PILOT_STOPPED',
            'idempotency_key':plan['idempotency_key'],'plan_sha256':plan_sha,
            'scene_id':plan['scene_id'],'province':plan['province'],'year':plan['year'],
            'assets':assets,'qa':qa,'error':error,'remote_body_bytes_read':measured,
            'remote_request_count':client.request_count if client else 0,
            'measurement_complete':known,'ledger_charge_bytes':charge,'http429':rate,
            'http_events':client.events if client else [],'reservation_bytes':plan['reservation_bytes'],
            'sealed_plan_sha256':sha256(evidence_dir/'sealed-plan.json') if (evidence_dir/'sealed-plan.json').exists() else None,
            'full_remote_assets_downloaded':False,'source_CAS_modified':False,'learning_ready':False,
            'maximum_pilots':1,'subsequent_pilots_started':0,'acceptance_blockers':plan['acceptance_blockers'],
            'completed_at':datetime.now(timezone.utc).isoformat()}
        receipt_path=evidence_dir/'data-receipt.json'
        write_json_new(receipt_path,receipt)
        previous=current
        current=adapter.settle(current,plan['idempotency_key'],charge,str(receipt_path),
                               measurement_complete=known,rate_limit=rate)
        events.append({'action':'settle','before_sha256':previous,'after_sha256':current,'bytes':charge})
        write_json_new(evidence_dir/'ledger-after.json',adapter.snapshot(current))
        result={**receipt,'ledger_before_sha256':before,'ledger_after_sha256':current,
                'ledger_events':events,'data_receipt_sha256':sha256(receipt_path),
                'remaining_global_bytes':adapter.snapshot(current)['additional_maximum_bytes']-adapter.snapshot(current)['new_charged_bytes']}
        write_json_new(evidence_dir/'result.json',result)
    return result


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',type=Path,required=True)
    parser.add_argument('--plan-sha256',required=True)
    parser.add_argument('--ledger',type=Path,required=True)
    parser.add_argument('--evidence-dir',type=Path,required=True)
    parser.add_argument('--raw-root',type=Path,required=True)
    parser.add_argument('--execute',action='store_true')
    a=parser.parse_args()
    r=run_pilot(a.plan,a.plan_sha256,a.ledger,a.evidence_dir,a.raw_root,execute=a.execute)
    print(json.dumps({k:r.get(k) for k in ('status','execution_status','remote_body_bytes_read',
        'ledger_charge_bytes','remaining_global_bytes','http429','ledger_after_sha256')}))
