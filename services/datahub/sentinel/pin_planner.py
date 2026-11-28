"""정확한 누락 polygon 안의 단일 scene·7asset·pixel window를 결정적으로 고정한다."""
import hashlib
import json
import math
from pathlib import Path
from urllib.parse import unquote, urlsplit

import numpy as np
import shapely
from affine import Affine
from pyproj import Transformer
from rasterio.windows import from_bounds
from shapely.geometry import Polygon, mapping, shape

from services.datahub.connectors.onemap.boundary import sha256, write_json_new

from .completeness import BANDS, _project


def canonical_sha(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def asset_uri(value):
    p=urlsplit(value)
    if (p.scheme!='https' or p.netloc not in {
        f'sentinel2l2a0{i}.blob.core.windows.net' for i in range(1,10)}
        or p.query or p.fragment or not p.path.startswith('/sentinel2-l2/')
        or any(v in ('.','..') for v in unquote(p.path).split('/'))
        or any(ord(c)<32 for c in unquote(p.path))):
        raise ValueError('UNSIGNED_PINNED_SENTINEL_ASSET_URI_REQUIRED')
    return value


def _window_polygon(affine,window,crs):
    col,row,width,height=window
    pts=[]
    corners=[(col,row),(col+width,row),(col+width,row+height),(col,row+height),(col,row)]
    for a,b in zip(corners[:-1],corners[1:], strict=True):
        for t in np.linspace(0,1,33)[:-1]:
            pts.append(affine@(a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t))
    return _project(Polygon(pts),crs)


def select_window_plans(*,queue_path,queue_sha,queue_size,boundary_path,boundary_sha,
                        scenes_path,scenes_sha,native_checkpoints,expected_ledger_sha,
                        existing_keys=(),expected_features=72,priority_cells=None,maximum=1,
                        previously_attempted=None):
    queue_path,boundary_path,scenes_path=map(Path,(queue_path,boundary_path,scenes_path))
    if (queue_path.stat().st_size!=queue_size or queue_size>512*1024**2 or sha256(queue_path)!=queue_sha
            or sha256(boundary_path)!=boundary_sha or sha256(scenes_path)!=scenes_sha):
        raise ValueError('QUEUE_BOUNDARY_OR_SCENE_MANIFEST_PIN_DRIFT')
    queue=json.loads(queue_path.read_text(encoding='utf-8'))
    if len(queue['features'])!=expected_features or queue['crs']['properties']['name']!='EPSG:6933':
        raise ValueError('EXACT_QUEUE_SCHEMA_OR_COUNT_MISMATCH')
    boundaries={f['properties']['province_id']:_project(shape(f['geometry']),'EPSG:4326')
                for f in json.loads(boundary_path.read_text(encoding='utf-8'))['features']}
    boundaries={k:(g if g.is_valid else shapely.make_valid(g)) for k,g in boundaries.items()}
    scenes=json.loads(scenes_path.read_text(encoding='utf-8'))['scenes']
    groups={}
    for row in scenes:
        groups.setdefault((row['province'],int(row['year']),row['scene_id']),row)
    physical={}
    for p in sorted(Path(native_checkpoints).glob('*.json')):
        cached=json.loads(p.read_text(encoding='utf-8'))
        ref=cached['geometry']['footprint']
        if sha256(Path(ref['path']))!=ref['sha256']:
            raise ValueError('PHYSICAL_FOOTPRINT_PIN_DRIFT')
        physical.setdefault((cached['province'],cached['year']),[]).append(shapely.from_wkb(Path(ref['path']).read_bytes()))
    features=[(i,f) for i,f in enumerate(queue['features'])
              if f['properties']['reason']=='MISSING_SIMULTANEOUS_SIX_BANDS_SCL']
    if priority_cells is None:
        features.sort(key=lambda v:(-v[1]['properties']['missing_area_m2'],v[1]['properties']['province'],v[1]['properties']['year']))
    else:
        order={key:index for index,key in enumerate(priority_cells)}
        def key_of(value):
            p=value[1]['properties']
            return p['province'],int(p['year'])
        features=sorted((v for v in features if key_of(v) in order),key=lambda v:order[key_of(v)])
    plans=[]
    attempted=previously_attempted or {}
    rejection=[]
    for feature_index,feature in features:
        props=feature['properties']
        province,year=props['province'],int(props['year'])
        if props['required_bands']!=list(BANDS)+['SCL'] or props['source_pins']['boundary']!=boundary_sha:
            raise ValueError('QUEUE_ASSETS_OR_BOUNDARY_PROOF_MISMATCH')
        missing=shape(feature['geometry'])
        held=shapely.union_all([*physical.get((province,year),[]),*attempted.get((province,year),[])])
        source_rows=[r for (p,y,s),r in groups.items() if (p,y)==(province,year)]
        source_rows.sort(key=lambda r:r['scene_id'])
        for source_row in source_rows:
            stac_path=Path(source_row['stac_item_path'])
            # migrated CAS 이름 자체가 content pin이다. fixture도 동일한 계약을 쓴다.
            if sha256(stac_path)!=stac_path.name:
                raise ValueError('STAC_CAS_PIN_DRIFT')
            stac=json.loads(stac_path.read_text(encoding='utf-8'))
            if (stac.get('collection')!='sentinel-2-l2a' or stac['id']!=source_row['scene_id']
                    or int(stac['properties']['datetime'][:4])!=year):
                raise ValueError('STAC_SCENE_YEAR_MISMATCH')
            crs='EPSG:'+str(stac['properties']['proj:epsg'])
            available=missing.intersection(boundaries[province]).intersection(_project(shape(stac['geometry']),'EPSG:4326')).difference(held)
            interior=available.buffer(-2500)
            if interior.is_empty:
                rejection.append({'scene':stac['id'],'reason':'NO_UNDOWNLOADED_INTERIOR_256_WINDOW'})
                continue
            center=interior.representative_point()
            x,y=Transformer.from_crs('EPSG:6933',crs,always_xy=True).transform(center.x,center.y)
            b02=stac['assets']['B02']
            affine=Affine(*b02['proj:transform'][:6])
            if affine.b or affine.d or affine.a!=10 or affine.e!=-10:
                raise ValueError('UNSUPPORTED_B02_GRID')
            px,py=(~affine)@(x,y)
            window=[math.floor(px)-128,math.floor(py)-128,256,256]
            roi=_window_polygon(affine,window,crs)
            if not missing.covers(roi) or not boundaries[province].covers(roi) or roi.intersection(held).area>0.01:
                rejection.append({'scene':stac['id'],'reason':'SNAPPED_WINDOW_NOT_EXACTLY_MISSING'})
                continue
            left,top=affine@(window[0],window[1])
            right,bottom=affine@(window[0]+256,window[1]+256)
            assets={}
            for band in BANDS+('SCL',):
                asset=stac['assets'][band]
                transform=Affine(*asset['proj:transform'][:6])
                fractional=from_bounds(left,bottom,right,top,transform)
                col,row=math.floor(fractional.col_off),math.floor(fractional.row_off)
                w=math.ceil(fractional.col_off+fractional.width)-col
                h=math.ceil(fractional.row_off+fractional.height)-row
                size=asset['proj:shape']
                if min(col,row)<0 or col+w>size[1] or row+h>size[0] or max(w,h)>258:
                    raise ValueError('ASSET_WINDOW_OUT_OF_PINNED_GRID')
                assets[band]={'source_uri':asset_uri(asset['href']),'stac_asset_sha256':canonical_sha(asset),
                    'window':[col,row,w,h],'shape':size,'transform':list(transform)[:6],'crs':crs,
                    'etag':None,'size':None,'live_pin_status':'HEAD_REQUIRED_BEFORE_RANGE_GET'}
            identity={'province':province,'year':year,'scene_id':stac['id'],'B02_window':window,'assets':list(assets)}
            key='sdss2-pilot-'+canonical_sha(identity)
            if key in existing_keys:
                rejection.append({'scene':stac['id'],'reason':'IDEMPOTENCY_KEY_ALREADY_EXISTS'})
                continue
            result={'schema_version':'sentinel-single-window-pin-plan/1.0','status':'PLANNED_HEAD_PIN_SEAL_REQUIRED',
                'idempotency_key':key,'province':province,'year':year,'scene_id':stac['id'],
                'datetime':stac['properties']['datetime'],'queue':{'path':str(queue_path.resolve()),'sha256':queue_sha,
                    'bytes':queue_size,'feature_index':feature_index},
                'boundary':{'path':str(boundary_path.resolve()),'sha256':boundary_sha},
                'stac':{'path':str(stac_path.resolve()),'sha256':sha256(stac_path)},
                'scene_manifest':{'path':str(scenes_path.resolve()),'sha256':scenes_sha},
                'target_projected_geometry':mapping(roi),'target_crs':'EPSG:6933','B02_window':window,
                'target_affine':list(affine@Affine.translation(window[0],window[1]))[:6],
                'native_crs':crs,'assets':assets,'expected_current_ledger_sha256':expected_ledger_sha,
                'reservation_bytes':32*1024**2,'maximum_pilots':1,'request_spacing_seconds':2,
                'stop_on_first_failure':True,'stop_on_429':True,'same_scene_all_assets':True,
                'physical_held_footprint_overlap_m2':roi.intersection(held).area,
                'qa_minimum_clear_fraction':0.8,'independent_ground_truth':False,'learning_ready':False,
                'acceptance_blockers':['BIG_AUTHORITY_APPROVAL_PENDING','FULL_SPATIAL_COVERAGE_FALSE',
                                       'INDEPENDENT_GROUND_TRUTH_UNVERIFIED'],
                'rejected_candidates':rejection,'remote_downloads':0}
            plans.append(result)
            if len(plans)==maximum:
                return plans
            break
    return plans


def build_single_pilot_plan(*,output,**inputs):
    plans=select_window_plans(**inputs)
    if not plans:
        raise ValueError('NO_LOCAL_PINNED_SCENE_FOR_EXACT_MISSING_WINDOW')
    write_json_new(Path(output),plans[0])
    return plans[0]
