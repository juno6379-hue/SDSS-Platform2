import json
from unittest.mock import patch

import pytest

from services.datahub.connectors.onemap.boundary import sha256
from services.datahub.sentinel.shared_ledger import LedgerError,SharedLedger


def fixture(tmp_path,writable=True,scan=lambda:[]):
    previous=tmp_path/'history.json'
    previous.write_text('{}')
    path=tmp_path/'global-ledger.json'
    state={'version':1,'historical_ledgers':[{'path':str(previous),'sha256':sha256(previous)}],
        'historical_charged_bytes':3,'additional_maximum_bytes':1024**2,'combined_maximum_bytes':1024**2+3,
        'new_charged_bytes':7,'external_research_metadata_body_bytes':2,'rate_limit_active':False,
        'batches':{'preexisting-unknown':{'status':'pending','reserved_bytes':5,'charged_bytes':5,
                                      'config_sha256':'b'*64}}}
    path.write_text(json.dumps(state))
    return SharedLedger(path,writable=writable,collector_scan=scan),path,previous


def test_readonly_preflight_does_not_write_or_create_locks(tmp_path):
    adapter,path,_=fixture(tmp_path,writable=False)
    original=path.read_bytes()
    result=adapter.preflight(sha256(path),128)
    assert result['status']=='PREFLIGHT_READY' and path.read_bytes()==original
    assert not adapter.lock.exists() and not adapter.execution_lock.exists()
    with pytest.raises(LedgerError,match='READ_ONLY'):
        with adapter.execution_lease():
            pass


def test_reserve_mark_settle_preserves_unknown_past_pending(tmp_path):
    adapter,path,history=fixture(tmp_path)
    original_history=history.read_bytes()
    with adapter.execution_lease():
        before=sha256(path)
        reserved=adapter.reserve(before,'pilot-test-1','a'*64,128)
        assert reserved==sha256(path) and reserved!=before
        assert adapter.snapshot(reserved)['new_charged_bytes']==135
        started=adapter.mark_io_started(reserved,'pilot-test-1')
        settled=adapter.settle(started,'pilot-test-1',20,'receipt.json',measurement_complete=True)
        state=adapter.snapshot(settled)
        assert state['new_charged_bytes']==27
        assert state['batches']['preexisting-unknown']['status']=='pending'
        assert history.read_bytes()==original_history
    assert not adapter.execution_lock.exists() and not adapter.lock.exists()


def test_idempotent_key_never_double_reserves_and_cas_conflict_cannot_write(tmp_path):
    adapter,path,_=fixture(tmp_path)
    with adapter.execution_lease():
        before=sha256(path)
        after=adapter.reserve(before,'pilot-test-1','a'*64,128)
        with pytest.raises(LedgerError,match='CAS_MISMATCH'):
            adapter.reserve(before,'pilot-test-2','a'*64,128)
        with pytest.raises(LedgerError,match='IDEMPOTENCY_KEY_EXISTS'):
            adapter.reserve(after,'pilot-test-1','a'*64,128)
        assert sha256(path)==after


def test_os_execution_lock_is_exclusive_and_never_removes_other_owner(tmp_path):
    adapter,path,_=fixture(tmp_path)
    second=SharedLedger(path,writable=True,collector_scan=lambda:[])
    with adapter.execution_lease():
        with pytest.raises(FileExistsError):
            with second.execution_lease():
                pass
        assert adapter.execution_lock.exists()


def test_release_only_before_any_io_and_no_unknown_refund(tmp_path):
    adapter,path,_=fixture(tmp_path)
    with adapter.execution_lease():
        h=adapter.reserve(sha256(path),'pilot-test-1','a'*64,128)
        h=adapter.release_before_io(h,'pilot-test-1','operator cancelled before IO')
        assert adapter.snapshot(h)['new_charged_bytes']==7
        h=adapter.reserve(h,'pilot-test-2','a'*64,128)
        h=adapter.mark_io_started(h,'pilot-test-2')
        with pytest.raises(LedgerError,match='RELEASE_FORBIDDEN_AFTER_IO'):
            adapter.release_before_io(h,'pilot-test-2','not allowed')
        with pytest.raises(LedgerError,match='UNKNOWN_TRANSFER'):
            adapter.settle(h,'pilot-test-2',1,'error.json',measurement_complete=False)
        h=adapter.settle(h,'pilot-test-2',128,'error.json',measurement_complete=False)
        assert adapter.snapshot(h)['new_charged_bytes']==135


def test_429_circuit_and_retry_after_persist(tmp_path):
    adapter,path,_=fixture(tmp_path)
    with adapter.execution_lease():
        h=adapter.reserve(sha256(path),'pilot-test-1','a'*64,128)
        h=adapter.mark_io_started(h,'pilot-test-1')
        h=adapter.settle(h,'pilot-test-1',128,'429.json',measurement_complete=False,
                         rate_limit={'http_status':429,'retry_after':'3600'})
        assert adapter.snapshot(h)['last_rate_limit']['retry_after']=='3600'
        with pytest.raises(LedgerError,match='429_ACTIVE'):
            adapter.reserve(h,'pilot-test-2','a'*64,128)


def test_failed_atomic_replace_keeps_original_and_removes_only_temp(tmp_path):
    adapter,path,_=fixture(tmp_path)
    original=path.read_bytes()
    with adapter.execution_lease(),patch('services.datahub.sentinel.shared_ledger.os.replace',side_effect=OSError('fixture')):
        with pytest.raises(OSError):
            adapter.reserve(sha256(path),'pilot-test-1','a'*64,128)
    assert path.read_bytes()==original and not list(tmp_path.glob('.*.tmp'))


def test_active_collector_and_historical_drift_fail_closed(tmp_path):
    adapter,path,history=fixture(tmp_path,scan=lambda:[{'ProcessId':999}])
    assert 'ACTIVE_COLLECTOR' in adapter.preflight(sha256(path),128)['errors']
    history.write_text('changed')
    with pytest.raises(LedgerError,match='HISTORICAL_LEDGER_PIN_DRIFT'):
        adapter.snapshot(sha256(path))
