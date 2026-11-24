"""검증된 참조 집합만 content-addressed 새 저장소로 copy한다. 원본을 이동하지 않는다."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import uuid

from services.datahub.connectors.onemap.boundary import read_pin, sha256, write_json_new
from .completeness import BANDS


def build_migration_plan(reference_root, manifest, expected_manifest_sha, boundary_receipt,
                         store, output, *, audit_receipt, expected_audit_sha, maximum_bytes=8*1024**3):
    reference_root, store = Path(reference_root).resolve(), Path(store).resolve()
    if type(maximum_bytes) is not int or not 0<maximum_bytes<=8*1024**3:
        raise ValueError('BOUNDED_LOCAL_COPY_BUDGET_REQUIRED')
    if store.is_relative_to(reference_root) or reference_root.is_relative_to(store):
        raise ValueError('MIGRATION_TARGET_MUST_NOT_BE_REFERENCE')
    manifest = read_pin(Path(manifest),expected_manifest_sha,reference_root)
    doc = json.loads(manifest.read_text(encoding='utf-8'))
    audit_receipt = Path(audit_receipt)
    if sha256(audit_receipt) != expected_audit_sha:
        raise ValueError('VERIFIED_AUDIT_PIN_REQUIRED')
    audit = json.loads(audit_receipt.read_text(encoding='utf-8'))
    if (audit['status']!='VERIFIED_REAL' or audit['source_pins']['manifest']!=expected_manifest_sha
            or audit['verified_joint_patch_count']!=len(doc['scenes'])):
        raise ValueError('COMPLETE_VERIFIED_AUDIT_REQUIRED')
    reference_ledger = reference_root/'data/first-group-training-budget/global-ledger.json'
    read_pin(reference_ledger,audit['source_pins']['ledger'],reference_root)
    objects, aliases = {}, {}
    boundary_root = Path(boundary_receipt['boundary']['path']).parent.resolve()
    def add(path, expected, role):
        path = Path(path).resolve()
        if str(path) in aliases:
            if aliases[str(path)]!=expected:
                raise ValueError('SOURCE_ALIAS_HASH_CONFLICT')
            item = objects[expected]
            if role not in item['roles']:
                item['roles'].append(role)
            return item['target']
        allowed = reference_root if path.is_relative_to(reference_root) else boundary_root
        read_pin(path,expected,allowed)
        size = path.stat().st_size
        if str(path) in aliases and aliases[str(path)] != expected:
            raise ValueError('SOURCE_ALIAS_HASH_CONFLICT')
        aliases[str(path)] = expected
        item = objects.setdefault(expected,{'sha256':expected,'bytes':size,'sources':[],
            'target':str(store/expected),'roles':[]})
        if item['bytes'] != size:
            raise ValueError('HASH_SIZE_CONFLICT')
        if str(path) not in item['sources']:
            item['sources'].append(str(path))
        if role not in item['roles']:
            item['roles'].append(role)
        return str(store/expected)
    add(manifest,expected_manifest_sha,'immutable_original_aggregate_manifest')
    scenes = []
    calibration_cache = {}
    for index,row in enumerate(doc['scenes']):
        paths = {}
        for field,hash_key in [('image_path','image'),('label_path','label'),('quality_mask_path','quality')]:
            paths[field] = add(row[field],row['patch_sha256'][hash_key],'patch_'+hash_key)
        parent = row['source_window']
        paths['parent_image_path'] = add(parent['path'],parent['sha256'],'parent_six_band_image')
        paths['stac_item_path'] = add(row['stac_item']['path'],row['stac_item']['sha256'],'stac_item')
        native = {}
        for band in BANDS+('SCL',):
            source = row['source_crops']['raw-'+band+'.tif']
            native[band] = {'path':add(source['path'],source['sha256'],'native_'+band),
                            'sha256':source['sha256'],'source_uri':source['source']}
        calibration = row['calibration']
        paths['calibration_raw_path'] = add(calibration['path'],calibration['sha256'],'calibration_evidence')
        if calibration['sha256'] not in calibration_cache:
            calibration_cache[calibration['sha256']] = json.loads(Path(calibration['path']).read_text(encoding='utf-8'))
        evidence = calibration_cache[calibration['sha256']]
        xml = Path(evidence['source_metadata_path'])
        if not xml.is_absolute():
            xml = reference_root/'data'/xml
        paths['product_metadata_path'] = add(xml,evidence['source_metadata_sha256'],'official_product_xml')
        normalized = {k:row.get(k) for k in ('province','year','scene_id','source_group','datetime','bands',
            'logical_bands','quality_status','split','spatial_location_id','patch_id','window_in_source',
            'label_source','label_year','label_dataset_version','label_source_url','taxonomy_signature')}
        normalized.update(paths)
        normalized.update(source_manifest_row=index,source_manifest_sha256=expected_manifest_sha,
            native_assets=native,normalization={**row['normalization'],
                'evidence_path':paths['calibration_raw_path'],'source_metadata_path':paths['product_metadata_path']},
            raw_reference_label_crop_included=False,training_ready=False)
        scenes.append(normalized)
    for item in boundary_receipt['files']:
        add(item['path'],item['sha256'],'BIG_boundary_snapshot')
    total = sum(x['bytes'] for x in objects.values())
    free = shutil.disk_usage(store.parent if store.parent.exists() else Path.cwd()).free
    plan = {'schema_version':'selected-content-addressed-migration/1.0','status':'PLANNED',
        'created_at':datetime.now(timezone.utc).isoformat(),'reference_root':str(reference_root),
        'source_manifest':{'path':str(manifest),'sha256':expected_manifest_sha},'store':str(store),
        'verified_audit':{'path':str(audit_receipt),'sha256':expected_audit_sha},
        'reference_ledger':{'path':str(reference_ledger),'sha256':audit['source_pins']['ledger']},
        'policy':'COPY_TEMP_POST_SHA_ATOMIC_COMMIT_NO_SOURCE_HARDLINK','maximum_copy_bytes':maximum_bytes,
        'selected_patch_rows':len(scenes),'unique_object_count':len(objects),'source_alias_count':len(aliases),
        'selected_unique_bytes':total,'free_bytes_before':free,'minimum_required_free_bytes':total*2,
        'remote_downloads':0,'source_writes':0,'objects':list(objects.values()),'scenes':scenes,
        'exclusions':['failed_requests','old_duplicate_outputs','unselected_datasets','large_raw_reference_label_crops']}
    if total > maximum_bytes or free < total*2:
        plan['status'] = 'BLOCKED_LOCAL_COPY_BUDGET_OR_DISK'
    write_json_new(Path(output),plan)
    return plan


def probe_same_volume_hardlink(store):
    """새 store의 작은 임시 파일만으로 링크와 drift를 검증한다. 실제 원본에는 링크하지 않는다."""
    store = Path(store).resolve()
    store.mkdir(parents=True,exist_ok=True)
    token = uuid.uuid4().hex
    original,linked = store/('.probe-source-'+token),store/('.probe-link-'+token)
    original.write_bytes(b'probe-one')
    result = {'supported':False,'source_reference_touched':False,'policy_selected':'COPY'}
    try:
        os.link(original,linked)
        original.write_bytes(b'probe-two')
        result.update(supported=True,drift_propagates=linked.read_bytes()==b'probe-two')
    except OSError as exc:
        result['error_type'] = type(exc).__name__
    finally:
        for path in (linked,original):
            path.resolve().relative_to(store)
            if path.exists():
                path.unlink()
    return result


def execute_migration(plan_path, expected_plan_sha, receipt_path):
    plan_path,receipt_path = Path(plan_path),Path(receipt_path)
    if sha256(plan_path) != expected_plan_sha or receipt_path.exists():
        raise ValueError('PLAN_PIN_OR_IMMUTABLE_RECEIPT_CONFLICT')
    plan = json.loads(plan_path.read_text(encoding='utf-8'))
    if plan['status'] != 'PLANNED':
        raise ValueError('MIGRATION_PLAN_BLOCKED')
    if sha256(Path(plan['verified_audit']['path']))!=plan['verified_audit']['sha256']:
        raise ValueError('VERIFIED_AUDIT_PIN_DRIFT')
    if sha256(Path(plan['reference_ledger']['path']))!=plan['reference_ledger']['sha256']:
        raise ValueError('REFERENCE_LEDGER_PIN_DRIFT')
    store,reference = Path(plan['store']).resolve(),Path(plan['reference_root']).resolve()
    if store.is_relative_to(reference) or reference.is_relative_to(store):
        raise ValueError('MIGRATION_TARGET_MUST_NOT_BE_REFERENCE')
    store.mkdir(parents=True,exist_ok=True)
    if plan['selected_unique_bytes'] > plan['maximum_copy_bytes'] or shutil.disk_usage(store).free < plan['selected_unique_bytes']*2:
        raise ValueError('MIGRATION_DISK_OR_BUDGET_CHANGED')
    lock = store/'.migration.lock'
    descriptor = os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    receipts, copied, reused = [],0,0
    current_temp = None
    try:
        probe = probe_same_volume_hardlink(store)
        for index,item in enumerate(plan['objects'],1):
            digest = item['sha256']
            if len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest):
                raise ValueError('INVALID_CONTENT_ADDRESS')
            source,target = Path(item['sources'][0]),store/digest
            if target.is_symlink() or source.is_symlink() or target.resolve().parent!=store:
                raise ValueError('MIGRATION_PATH_OR_SYMLINK_INVALID')
            if target.exists():
                if target.stat().st_nlink>1:
                    raise ValueError('EXISTING_CAS_HARDLINK_NOT_ALLOWED')
                if target.stat().st_size!=item['bytes'] or sha256(target)!=digest:
                    raise ValueError('EXISTING_CAS_OBJECT_DRIFT')
                if source.stat().st_size!=item['bytes'] or sha256(source)!=digest:
                    raise ValueError('REUSED_OBJECT_SOURCE_DRIFT')
                reused+=1
            else:
                current_temp=store/('.'+digest+'.part-'+uuid.uuid4().hex)
                value=hashlib.sha256()
                transferred=0
                with source.open('rb') as original,current_temp.open('xb') as output:
                    for block in iter(lambda:original.read(1024*1024),b''):
                        transferred+=len(block)
                        if transferred>item['bytes']:
                            raise ValueError('SOURCE_SIZE_DRIFT')
                        value.update(block)
                        output.write(block)
                    output.flush()
                    os.fsync(output.fileno())
                if transferred!=item['bytes'] or value.hexdigest()!=digest or sha256(current_temp)!=digest:
                    raise ValueError('SOURCE_OR_POST_COPY_SHA_DRIFT')
                # Windows rename는 기존 target을 덮어쓰지 않는다. POSIX도 link로 같은 성질을 유지한다.
                if os.name=='nt':
                    os.rename(current_temp,target)
                else:
                    os.link(current_temp,target)
                    current_temp.unlink()
                current_temp=None
                copied+=1
            receipts.append({'source':str(source),'source_aliases':item['sources'],'source_sha256':digest,
                'target':str(target),'target_sha256':digest,'bytes':item['bytes'],'policy':'COPY',
                'verified_at':datetime.now(timezone.utc).isoformat()})
            if index%500==0:
                print(json.dumps({'migration_objects':index,'total':len(plan['objects'])}),flush=True)
        if sha256(Path(plan['source_manifest']['path']))!=plan['source_manifest']['sha256']:
            raise ValueError('SOURCE_MANIFEST_CHANGED_DURING_MIGRATION')
        if sha256(Path(plan['reference_ledger']['path']))!=plan['reference_ledger']['sha256']:
            raise ValueError('REFERENCE_LEDGER_CHANGED_DURING_MIGRATION')
        receipt={'status':'VERIFIED_REAL','scope':'SELECTED_LOCAL_COPY_NOT_NEW_ACQUISITION',
            'plan_sha256':expected_plan_sha,'completed_at':datetime.now(timezone.utc).isoformat(),
            'copied_objects':copied,'reused_objects':reused,'unique_bytes':plan['selected_unique_bytes'],
            'objects':receipts,'source_writes':0,'remote_downloads':0,'hardlink_probe':probe}
        write_json_new(receipt_path,receipt)
        write_json_new(receipt_path.with_name('migrated-scene-manifest.json'),{
            'status':'VERIFIED_REAL','source_manifest_sha256':plan['source_manifest']['sha256'],
            'migration_receipt_sha256':sha256(receipt_path),'scenes':plan['scenes'],
            'learning_ready':False,'independent_ground_truth':False})
        return receipt
    except Exception as exc:
        if current_temp is not None:
            current_temp.resolve().relative_to(store)
            if current_temp.exists():
                current_temp.unlink()
        failure={'status':'BLOCKED','error_type':type(exc).__name__,'error':str(exc),
            'completed_verified_objects':len(receipts),'partial_removed':True,'source_writes':0}
        write_json_new(receipt_path.with_name('migration-failure-'+uuid.uuid4().hex+'.json'),failure)
        raise
    finally:
        os.close(descriptor)
        lock.unlink()
