"""119개 parent를 기준으로 native mask를 재사용하는 재개 가능한 원본 감사."""
from collections import defaultdict
import json
from pathlib import Path
import shutil

import numpy as np
import rasterio
from rasterio.windows import Window
import shapely
from shapely.geometry import shape

from services.datahub.connectors.onemap.boundary import PROVINCES, read_pin, sha256, write_json_new
from .completeness import BANDS, _project, simultaneous_support, grid_completeness, missing_queue_item, grid_completeness_lower_bound


def _save_geometry(path, geometry):
    with path.open('xb') as handle:
        handle.write(geometry.wkb)
    return {'path':str(path), 'sha256':sha256(path)}


def run_held_audit(reference_root, boundary_receipt, manifest, manifest_sha, ledger, ledger_sha, output, *, grid_mode='strict'):
    reference_root, output = Path(reference_root).resolve(), Path(output).resolve()
    if output.is_relative_to(reference_root) or reference_root.is_relative_to(output):
        raise ValueError('OUTPUT_MUST_NOT_WRITE_REFERENCE_ROOT')
    output.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(output).free < 1024**3:
        raise ValueError('AUDIT_DISK_INSUFFICIENT')
    read_pin(manifest, manifest_sha, reference_root)
    read_pin(ledger, ledger_sha, reference_root)
    pins = {'manifest':manifest_sha, 'ledger':ledger_sha,
            'boundary':boundary_receipt['boundary']['sha256']}
    plan_path = output/'input-pins.json'
    if plan_path.exists():
        if json.loads(plan_path.read_text()) != pins:
            raise ValueError('RESUME_PIN_DRIFT')
    else:
        write_json_new(plan_path, pins)
    rows = json.loads(Path(manifest).read_text(encoding='utf-8'))['scenes']
    groups, counts = defaultdict(list), defaultdict(lambda: {'physical':0,'eligible':0})
    for row in rows:
        groups[row['source_window']['path']].append(row)
        key = (row['province'],int(row['year']))
        counts[key]['physical'] += Path(row['image_path']).is_file()
        counts[key]['eligible'] += row.get('quality_status') == 'quality_eligible'
    cache = output/'native-checkpoints'
    cache.mkdir(exist_ok=True)
    by_cell, verified_pins = defaultdict(list), {}
    total_verified_patches, remainder_pixels = 0, 0
    for index, (parent_path, patches) in enumerate(groups.items(), 1):
        row = patches[0]
        identity = sha256_bytes(parent_path.encode())[:24]
        checkpoint = cache/(identity+'.json')
        if checkpoint.exists():
            result = json.loads(checkpoint.read_text(encoding='utf-8'))
            if result['input_pins'] != pins:
                raise ValueError('NATIVE_CHECKPOINT_PIN_DRIFT')
            for item in result['verified_files']:
                read_pin(Path(item['path']), item['sha256'], reference_root)
            for item in result['geometry'].values():
                if sha256(Path(item['path'])) != item['sha256']:
                    raise ValueError('GEOMETRY_CHECKPOINT_PIN_DRIFT')
        else:
            # checkpoint JSON이 commit되기 전 중단된 파생 WKB만 제거한다. 원본에는 접근하지 않는다.
            for kind in ('footprint','present','clear'):
                orphan = cache/(identity+'-'+kind+'.wkb')
                orphan.resolve().relative_to(cache.resolve())
                if orphan.exists():
                    orphan.unlink()
            file_pins = {}
            def checked(path, expected):
                path = read_pin(Path(path), expected, reference_root)
                file_pins[str(path)] = expected
                return path
            parent = checked(parent_path, row['source_window']['sha256'])
            stac = checked(row['stac_item']['path'], row['stac_item']['sha256'])
            source = json.loads(stac.read_text(encoding='utf-8'))
            province, year = row['province'], int(row['year'])
            if source['id'] != row['scene_id'] or int(source['properties']['datetime'][:4]) != year:
                raise ValueError('PARENT_SCENE_YEAR_MISMATCH')
            for band in BANDS + ('SCL',):
                crop = row['source_crops']['raw-'+band+'.tif']
                checked(crop['path'], crop['sha256'])
                if crop['source'].split('?',1)[0] != source['assets'][band]['href'].split('?',1)[0]:
                    raise ValueError('NATIVE_SOURCE_URI_MISMATCH')
            with rasterio.open(parent, 'r') as parent_ds:
                if parent_ds.count != 6 or max(parent_ds.width,parent_ds.height)>2048:
                    raise ValueError('PARENT_SIZE_OR_BANDS_INVALID')
                data = parent_ds.read()
                windows = set()
                for patch in patches:
                    if (patch['province'] != province or int(patch['year']) != year
                            or patch['scene_id'] != row['scene_id'] or tuple(patch['bands']) != BANDS):
                        raise ValueError('PATCH_GROUP_METADATA_MISMATCH')
                    image = checked(patch['image_path'], patch['patch_sha256']['image'])
                    x,y,w,h = patch['window_in_source']
                    if (x,y,w,h) in windows:
                        raise ValueError('DUPLICATE_PARENT_WINDOW')
                    windows.add((x,y,w,h))
                    with rasterio.open(image,'r') as patch_ds:
                        if (patch_ds.crs != parent_ds.crs or patch_ds.transform != parent_ds.window_transform(Window(x,y,w,h))
                                or not np.array_equal(patch_ds.read(), data[:,y:y+h,x:x+w])):
                            raise ValueError('PATCH_PARENT_PIXEL_OR_GRID_MISMATCH')
                expected = {(x,y,256,256) for y in range(0,parent_ds.height-255,256)
                            for x in range(0,parent_ds.width-255,256)}
                if windows != expected:
                    raise ValueError('UNACCOUNTED_FULL_PARENT_PATCH_WINDOWS')
                remainder = parent_ds.width*parent_ds.height-len(patches)*256*256
            scl = Path(row['source_crops']['raw-SCL.tif']['path'])
            support = simultaneous_support(parent, BANDS, scl)
            geometries = {k:_save_geometry(cache/(identity+'-'+k+'.wkb'),support[k])
                          for k in ('footprint','present','clear')}
            result = {'input_pins':pins,'province':province,'year':year,'parent_path':str(parent),
                      'verified_patch_count':len(patches),'remainder_native_pixels':remainder,
                      'geometry':geometries,'verified_files':[{'path':p,'sha256':s} for p,s in file_pins.items()]}
            write_json_new(checkpoint,result)
        total_verified_patches += result['verified_patch_count']
        remainder_pixels += result['remainder_native_pixels']
        by_cell[(result['province'],result['year'])].append(result)
        verified_pins.update({x['path']:x['sha256'] for x in result['verified_files']})
        if index%10 == 0 or index==len(groups):
            print(json.dumps({'verified_parent_frames':index,'verified_patches':total_verified_patches}),flush=True)
    boundary_path = Path(boundary_receipt['boundary']['path'])
    if sha256(boundary_path) != pins['boundary']:
        raise ValueError('BOUNDARY_PIN_DRIFT')
    boundary_doc = json.loads(boundary_path.read_text(encoding='utf-8'))
    boundaries, repairs = {}, []
    for feature in boundary_doc['features']:
        name = feature['properties']['province_id']
        projected = _project(shape(feature['geometry']),'EPSG:4326')
        if not projected.is_valid:
            fixed = shapely.make_valid(projected)
            delta = abs(projected.area-fixed.area)
            if delta > max(1.0,projected.area*1e-9):
                raise ValueError('PROJECTION_REPAIR_AREA_EXCEEDED')
            repairs.append({'province':name,'area_change_m2':delta,'source_changed':False})
            projected = fixed
        boundaries[name] = projected
    if grid_mode not in ('strict','conservative-lower-bound'):
        raise ValueError('GRID_MODE_INVALID')
    strict_dir=output/'cell-checkpoints'
    cell_dir = strict_dir if grid_mode=='strict' else output/'cell-checkpoints-lower-bound'
    cell_dir.mkdir(exist_ok=True)
    cells, queue = [], []
    for province in PROVINCES:
        for year in range(2020,2026):
            key = (province,year)
            cell_id = province+'-'+str(year)
            path = cell_dir/(cell_id+'.json')
            strict_path=strict_dir/(cell_id+'.json')
            if grid_mode=='conservative-lower-bound' and not path.exists() and strict_path.exists():
                path=strict_path
            if path.exists():
                saved = json.loads(path.read_text(encoding='utf-8'))
                if saved['input_pins'] != pins:
                    raise ValueError('CELL_CHECKPOINT_PIN_DRIFT')
                for item in saved['geometry'].values():
                    if sha256(Path(item['path']))!=item['sha256']:
                        raise ValueError('CELL_GEOMETRY_DRIFT')
                if sha256(Path(saved['cell']['required_grid']['path']))!=saved['cell']['required_grid']['sha256']:
                    raise ValueError('CELL_GRID_DRIFT')
                cell = saved['cell']
                if grid_mode=='conservative-lower-bound':
                    cell={**cell,'full_cell_metric_semantics':'CONSERVATIVE_LOWER_BOUND',
                          'preserved_strict_checkpoint':str(path) if path==strict_path else None}
                present, clear = [shapely.from_wkb(Path(saved['geometry'][k]['path']).read_bytes()) for k in ('present','clear')]
            else:
                b = boundaries[province]
                footprint,present,clear = [shapely.union_all([shapely.from_wkb(Path(r['geometry'][k]['path']).read_bytes())
                    for r in by_cell[key]]).intersection(b) for k in ('footprint','present','clear')]
                grid_function=grid_completeness if grid_mode=='strict' else grid_completeness_lower_bound
                flags,affine,metrics = grid_function(b,present,clear)
                grid = cell_dir/(cell_id+'.tif')
                with rasterio.open(grid,'w',driver='GTiff',count=1,height=flags.shape[0],width=flags.shape[1],
                    dtype='uint8',crs='EPSG:6933',transform=affine,compress='deflate') as ds:
                    ds.write(flags,1)
                cell = {'province':province,'year':year,'physical_patch_records':counts[key]['physical'],
                    'manifest_quality_eligible':counts[key]['eligible'],
                    'verified_six_band_scl_patches':sum(r['verified_patch_count'] for r in by_cell[key]),
                    'verified_parent_frames':len(by_cell[key]),'minimum_patch_threshold':28,
                    'minimum_patch_met':counts[key]['eligible']>=28,'boundary_area_m2':b.area,
                    'footprint_area_m2':footprint.area,'simultaneous_present_area_m2':present.area,
                    'clear_joint_area_m2':clear.area,'present_coverage_pct':100*present.area/b.area,
                    'clear_coverage_pct':100*clear.area/b.area,'missing_joint_area_m2':b.difference(present).area,
                    'required_grid':{'path':str(grid),'sha256':sha256(grid)},**metrics}
                geometries = {k:_save_geometry(cell_dir/(cell_id+'-'+k+'.wkb'),g)
                              for k,g in [('present',present),('clear',clear)]}
                write_json_new(path,{'input_pins':pins,'cell':cell,'geometry':geometries})
            cells.append(cell)
            queue.extend(missing_queue_item(province,year,boundaries[province],present,clear,pins))
            print(json.dumps({'completed_cells':len(cells),'province':province,'year':year}),flush=True)
    queue_path = output/'exact-missing-queue.geojson'
    write_json_new(queue_path,{'type':'FeatureCollection','crs':{'type':'name','properties':{'name':'EPSG:6933'}},'features':queue})
    read_pin(manifest,manifest_sha,reference_root)
    read_pin(ledger,ledger_sha,reference_root)
    result = {'status':'VERIFIED_REAL','scope':'MANIFEST_PATCHES_AND_REFERENCED_HELD_PARENT_FRAMES',
        'source_pins':pins,'physical_records':sum(c['physical_patch_records'] for c in cells),
        'manifest_quality_eligible':sum(c['manifest_quality_eligible'] for c in cells),
        'verified_joint_patch_count':total_verified_patches,'verified_parent_frames':len(groups),
        'local_unpatched_remainder_pixels_included':remainder_pixels,
        'minimum_patch_cells_met':sum(c['minimum_patch_met'] for c in cells),'cell_count':len(cells),
        'full_spatial_coverage':all(c['missing_joint_area_m2']<=.01 for c in cells),
        'grid_mode':grid_mode,'grid_used_for_collection_decision':False,
        'cells':cells,'failures':[],'projection_repairs':repairs,
        'missing_queue':{'path':str(queue_path),'sha256':sha256(queue_path),'features':len(queue)},
        'verified_files':[{'path':p,'sha256':s} for p,s in verified_pins.items()],
        'remote_downloads':0,'ledger_writes':0,'collector_started':False,'reference_ledger_unchanged':True,
        'training_ready':False,'boundary_authority_approval_pending':True}
    write_json_new(output/'completeness.json',result)
    return result


def sha256_bytes(data):
    import hashlib
    return hashlib.sha256(data).hexdigest()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference-root',type=Path,required=True)
    parser.add_argument('--boundary-receipt',type=Path,required=True)
    parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--manifest-sha256',required=True)
    parser.add_argument('--ledger',type=Path,required=True)
    parser.add_argument('--ledger-sha256',required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--grid-mode',choices=['strict','conservative-lower-bound'],default='strict')
    a=parser.parse_args()
    r=run_held_audit(a.reference_root,json.loads(a.boundary_receipt.read_text(encoding='utf-8')),
        a.manifest,a.manifest_sha256,a.ledger,a.ledger_sha256,a.output,grid_mode=a.grid_mode)
    print(json.dumps({k:r[k] for k in ('status','physical_records','verified_joint_patch_count','verified_parent_frames','minimum_patch_cells_met')}))
