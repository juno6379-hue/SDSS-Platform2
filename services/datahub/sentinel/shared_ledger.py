"""기존 전역원장과 동일 lock protocol을 쓰는 CAS reservation adapter.

명시 writable 모드의 원장 JSON/동일 디렉터리 temp·lock만 수정한다.
과거 원장·RAW·CAS 객체·기존 pending을 초기화하거나 환불하지 않는다.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from services.datahub.connectors.onemap.boundary import sha256


class LedgerError(RuntimeError):
    """CAS·동시성·예산·중복·승인 경계가 충족되지 않은 작업."""


def _hash(data):
    return hashlib.sha256(data).hexdigest()


def _integer(value, low, high, name):
    if type(value) is not int or not low<=value<=high:
        raise LedgerError(name)


def active_collectors():
    """현재 PID를 제외하고 알려진 수집 entrypoint를 실제 OS에서 확인한다."""
    pattern=(r'collect_samples|collect_training|collect_first_group|run_guarded_full_tile|'
             r'run_provisional_full_tile|sentinel\.(?:pilot|coverage_batch)|'
             r'services\.(?:datahub\.westjava_native|lcluc\.banten_sentinel_native)')
    if os.name=='nt':
        command="Get-CimInstance Win32_Process | Where-Object {$_.Name -match 'python'} | Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress"
        result=subprocess.run(['powershell','-NoProfile','-Command',command],capture_output=True,text=True,
                              encoding='utf-8',errors='replace',timeout=20,check=True)
        rows=json.loads(result.stdout or '[]')
        if isinstance(rows,dict):
            rows=[rows]
        return [r for r in rows if r['ProcessId']!=os.getpid() and re.search(pattern,r.get('CommandLine') or '')]
    result=subprocess.run(['ps','-eo','pid,args'],capture_output=True,text=True,timeout=10,check=True)
    return [{'ProcessId':int(line.split(None,1)[0]),'CommandLine':line.split(None,1)[1]}
            for line in result.stdout.splitlines()[1:] if len(line.split(None,1))==2
            and int(line.split(None,1)[0])!=os.getpid() and re.search(pattern,line)]


@contextmanager
def exclusive_os_lock(path):
    """O_EXCL marker는 legacy와 공유하고 실제 OS lock도 유지한다. stale 삭제 금지."""
    path=Path(path)
    if path.is_symlink():
        raise LedgerError('LOCK_SYMLINK_NOT_ALLOWED')
    fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_RDWR)
    token=json.dumps({'pid':os.getpid(),'nonce':uuid.uuid4().hex}).encode()
    locked=False
    try:
        os.write(fd,token)
        os.fsync(fd)
        os.lseek(fd,0,os.SEEK_SET)
        if os.name=='nt':
            import msvcrt
            msvcrt.locking(fd,msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        locked=True
        yield token.decode()
    finally:
        if locked:
            os.lseek(fd,0,os.SEEK_SET)
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(fd,msvcrt.LK_UNLCK,1)
            else:
                import fcntl
                fcntl.flock(fd,fcntl.LOCK_UN)
        os.close(fd)
        if path.exists():
            if path.read_bytes()!=token:
                raise LedgerError('LOCK_OWNER_CHANGED_MANUAL_REVIEW')
            path.unlink()


class SharedLedger:
    def __init__(self,path,*,writable=False,collector_scan=active_collectors):
        self.path=Path(path).resolve()
        self.lock=self.path.with_suffix('.lock')
        self.execution_lock=self.path.with_name('global-ledger.execution.lock')
        self.writable=writable
        self.collector_scan=collector_scan
        self.owner=None

    def snapshot(self,expected_sha):
        if not re.fullmatch('[0-9a-f]{64}',expected_sha):
            raise LedgerError('LEDGER_SHA_REQUIRED')
        raw=self.path.read_bytes()
        if _hash(raw)!=expected_sha:
            raise LedgerError('LEDGER_CAS_MISMATCH')
        state=json.loads(raw)
        _integer(state['additional_maximum_bytes'],1,4*1024**3,'GLOBAL_BUDGET_INVALID')
        _integer(state['new_charged_bytes'],0,state['additional_maximum_bytes'],'GLOBAL_USAGE_INVALID')
        for previous in state['historical_ledgers']:
            if sha256(Path(previous['path']))!=previous['sha256']:
                raise LedgerError('HISTORICAL_LEDGER_PIN_DRIFT')
        total=state.get('external_research_metadata_body_bytes',0)
        _integer(total,0,state['additional_maximum_bytes'],'METADATA_USAGE_INVALID')
        for batch in state['batches'].values():
            _integer(batch['reserved_bytes'],1,2*1024**3,'HISTORICAL_RESERVATION_INVALID')
            _integer(batch['charged_bytes'],0,batch['reserved_bytes'],'HISTORICAL_CHARGE_INVALID')
            total+=batch['charged_bytes']
        if total!=state['new_charged_bytes']:
            raise LedgerError('GLOBAL_USAGE_SUM_MISMATCH')
        return state

    def preflight(self,expected_sha,reserve_bytes,*,key=None,config_sha=None):
        state=self.snapshot(expected_sha)
        _integer(reserve_bytes,1,32*1024**2,'PILOT_RESERVATION_LIMIT')
        errors=[]
        processes=self.collector_scan()
        if processes:
            errors.append('ACTIVE_COLLECTOR')
        if self.execution_lock.exists() and self.owner is None:
            errors.append('LEGACY_EXECUTION_LOCK_EXISTS')
        if self.lock.exists():
            errors.append('LEGACY_LEDGER_LOCK_EXISTS')
        if state.get('rate_limit_active'):
            errors.append('GLOBAL_HTTP429_CIRCUIT')
        remaining=state['additional_maximum_bytes']-state['new_charged_bytes']
        if reserve_bytes>remaining:
            errors.append('GLOBAL_BUDGET_INSUFFICIENT')
        free=shutil.disk_usage(self.path.parent).free
        if free<reserve_bytes*4:
            errors.append('DISK_INSUFFICIENT')
        if key in state['batches']:
            old=state['batches'][key]
            errors.append('IDEMPOTENCY_KEY_ALREADY_'+old['status'].upper())
            if config_sha and old['config_sha256']!=config_sha:
                errors.append('IDEMPOTENCY_CONFIG_CONFLICT')
        return {'status':'BLOCKED' if errors else 'PREFLIGHT_READY','errors':errors,
                'ledger_sha256':expected_sha,'remaining_bytes':remaining,'reservation_bytes':reserve_bytes,
                'active_collectors':processes,'free_bytes':free,
                'preexisting_pending':[k for k,v in state['batches'].items() if v['status']=='pending']}

    @contextmanager
    def execution_lease(self):
        if not self.writable:
            raise LedgerError('READ_ONLY_LEDGER_ADAPTER')
        if self.owner is not None or self.collector_scan():
            raise LedgerError('ACTIVE_COLLECTOR_OR_REENTRANT_LEASE')
        with exclusive_os_lock(self.execution_lock) as owner:
            self.owner=owner
            try:
                yield
            finally:
                self.owner=None

    def _mutate(self,expected_sha,change):
        if not self.writable or self.owner is None:
            raise LedgerError('WRITABLE_EXECUTION_LEASE_REQUIRED')
        with exclusive_os_lock(self.lock):
            state=self.snapshot(expected_sha)
            change(state)
            state['updated_at']=datetime.now(timezone.utc).isoformat()
            raw=(json.dumps(state,ensure_ascii=False,indent=2)+'\n').encode()
            temp=self.path.with_name('.'+self.path.name+'.'+uuid.uuid4().hex+'.tmp')
            try:
                with temp.open('xb') as handle:
                    handle.write(raw)
                    handle.flush()
                    os.fsync(handle.fileno())
                if sha256(self.path)!=expected_sha:
                    raise LedgerError('LEDGER_CAS_DRIFT_BEFORE_REPLACE')
                os.replace(temp,self.path)
            finally:
                if temp.exists():
                    temp.unlink()
            return _hash(raw)

    def reserve(self,expected_sha,key,config_sha,reserved_bytes):
        _integer(reserved_bytes,1,32*1024**2,'PILOT_RESERVATION_LIMIT')
        if not re.fullmatch('[a-zA-Z0-9_-]{8,120}',key) or not re.fullmatch('[0-9a-f]{64}',config_sha):
            raise LedgerError('IDEMPOTENCY_ARGUMENT_INVALID')
        def change(state):
            if state.get('rate_limit_active') or self.collector_scan():
                raise LedgerError('COLLECTOR_OR_429_ACTIVE')
            if key in state['batches']:
                raise LedgerError('IDEMPOTENCY_KEY_EXISTS_NO_DUPLICATE_RESERVATION')
            if state['new_charged_bytes']+reserved_bytes>state['additional_maximum_bytes']:
                raise LedgerError('GLOBAL_BUDGET_INSUFFICIENT')
            state['new_charged_bytes']+=reserved_bytes
            state['batches'][key]={'status':'pending','reserved_bytes':reserved_bytes,
                'charged_bytes':reserved_bytes,'config_sha256':config_sha,'owner':self.owner,
                'io_started':False,'adapter':'sdss2-shared-ledger/1.0'}
        return self._mutate(expected_sha,change)

    def mark_io_started(self,expected_sha,key):
        def change(state):
            batch=state['batches'][key]
            if batch['status']!='pending' or batch.get('owner')!=self.owner:
                raise LedgerError('RESERVATION_OWNERSHIP_MISMATCH')
            batch['io_started']=True
        return self._mutate(expected_sha,change)

    def settle(self,expected_sha,key,charged,receipt_path,*,measurement_complete,rate_limit=None):
        def change(state):
            batch=state['batches'][key]
            if batch['status']!='pending' or batch.get('owner')!=self.owner:
                raise LedgerError('PENDING_OWNERSHIP_REQUIRED')
            _integer(charged,0,batch['reserved_bytes'],'SETTLEMENT_OUT_OF_RESERVATION')
            if not measurement_complete and charged!=batch['reserved_bytes']:
                raise LedgerError('UNKNOWN_TRANSFER_CANNOT_BE_REFUNDED')
            state['new_charged_bytes']-=batch['reserved_bytes']-charged
            batch.update(status='settled',charged_bytes=charged,report_path=str(receipt_path),
                         measurement_complete=measurement_complete)
            if rate_limit:
                state.update(rate_limit_active=True,last_rate_limit=rate_limit)
        return self._mutate(expected_sha,change)

    def release_before_io(self,expected_sha,key,reason):
        def change(state):
            batch=state['batches'][key]
            if batch['status']!='pending' or batch.get('owner')!=self.owner:
                raise LedgerError('PENDING_OWNERSHIP_REQUIRED')
            if batch.get('io_started'):
                raise LedgerError('RELEASE_FORBIDDEN_AFTER_IO')
            state['new_charged_bytes']-=batch['reserved_bytes']
            batch.update(status='settled',charged_bytes=0,measurement_complete=True,
                         report_path='CANCELLED_BEFORE_IO:'+str(reason)[:200])
        return self._mutate(expected_sha,change)
