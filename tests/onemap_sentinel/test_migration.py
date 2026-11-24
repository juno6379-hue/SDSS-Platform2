import json
from pathlib import Path

import pytest

from services.datahub.connectors.onemap.boundary import sha256
from services.datahub.sentinel.migration import execute_migration, probe_same_volume_hardlink


def plan_fixture(tmp_path):
    reference = tmp_path/'reference'
    reference.mkdir()
    source = reference/'image.bin'
    source.write_bytes(b'verified-fixture-data')
    manifest = reference/'manifest.json'
    manifest.write_text('{}')
    audit = tmp_path/'audit.json'
    audit.write_text('{"status":"VERIFIED_REAL"}')
    store = tmp_path/'new-store'
    value = {'status':'PLANNED','store':str(store),'reference_root':str(reference),
        'selected_unique_bytes':source.stat().st_size,'maximum_copy_bytes':1024,
        'source_manifest':{'path':str(manifest),'sha256':sha256(manifest)},
        'verified_audit':{'path':str(audit),'sha256':sha256(audit)},'scenes':[],
        'reference_ledger':{'path':str(manifest),'sha256':sha256(manifest)},
        'objects':[{'sha256':sha256(source),'bytes':source.stat().st_size,
                    'sources':[str(source)],'roles':['fixture']} ]}
    path = tmp_path/'plan.json'
    path.write_text(json.dumps(value))
    return path,source,store


def test_copy_is_content_addressed_and_original_drift_does_not_propagate(tmp_path):
    plan,source,store = plan_fixture(tmp_path)
    checksum = sha256(source)
    receipt = execute_migration(plan,sha256(plan),tmp_path/'receipt.json')
    target = store/checksum
    assert receipt['copied_objects']==1 and target.read_bytes()==source.read_bytes()
    assert receipt['source_writes']==0 and receipt['remote_downloads']==0
    source.write_bytes(b'original-fixture-later-changed')
    assert target.read_bytes()==b'verified-fixture-data'


def test_existing_cas_duplicate_reused_and_bad_cas_never_overwritten(tmp_path):
    plan,source,store = plan_fixture(tmp_path)
    store.mkdir()
    target = store/sha256(source)
    target.write_bytes(source.read_bytes())
    receipt = execute_migration(plan,sha256(plan),tmp_path/'receipt.json')
    assert receipt['reused_objects']==1 and receipt['copied_objects']==0
    target.write_bytes(b'changed-cas')
    with pytest.raises(ValueError,match='CAS_OBJECT_DRIFT'):
        execute_migration(plan,sha256(plan),tmp_path/'second-receipt.json')
    assert target.read_bytes()==b'changed-cas'


def test_source_drift_removes_partial_and_records_failure(tmp_path):
    plan,source,store = plan_fixture(tmp_path)
    source.write_bytes(b'wrong-source')
    with pytest.raises(ValueError,match='SHA_DRIFT'):
        execute_migration(plan,sha256(plan),tmp_path/'receipt.json')
    assert not list(store.glob('*.part-*'))
    assert not list(store.glob('.*.part-*'))
    assert list(tmp_path.glob('migration-failure-*.json'))
    assert source.read_bytes()==b'wrong-source'


def test_same_volume_link_probe_uses_only_new_synthetic_files(tmp_path):
    result = probe_same_volume_hardlink(tmp_path/'store')
    assert result['policy_selected']=='COPY' and not result['source_reference_touched']
    if result['supported']:
        assert result['drift_propagates']
    assert not list((tmp_path/'store').iterdir())
