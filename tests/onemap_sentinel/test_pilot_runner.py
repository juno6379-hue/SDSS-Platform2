import json
from pathlib import Path

from affine import Affine
import numpy as np

from test_pin_planner import fixture as planner_fixture
from services.datahub.connectors.onemap.boundary import sha256
from services.datahub.sentinel import pilot
from services.datahub.sentinel.pin_planner import build_single_pilot_plan
from services.datahub.sentinel.remote import TransferError


def fixture(tmp_path,monkeypatch):
    kwargs=planner_fixture(tmp_path)
    history=tmp_path/'historical.json'
    history.write_text('{}')
    folder=tmp_path/'legacy'
    folder.mkdir()
    ledger=folder/'global-ledger.json'
    ledger.write_text(json.dumps({'version':1,'historical_ledgers':[{'path':str(history),'sha256':sha256(history)}],
        'historical_charged_bytes':0,'additional_maximum_bytes':64*1024**2,
        'new_charged_bytes':0,'external_research_metadata_body_bytes':0,'batches':{},'rate_limit_active':False}))
    plan_path=tmp_path/'plan.json'
    build_single_pilot_plan(**{**kwargs,'expected_ledger_sha':sha256(ledger)},output=plan_path)
    monkeypatch.setattr(pilot,'WORKSPACE_ROOT',tmp_path)
    return plan_path,ledger,tmp_path/'evidence/onemap_sentinel/run',tmp_path/'data/raw/sentinel-pilots'


class FakeRemote:
    def __init__(self,maximum,spacing):
        self.body_bytes=10
        self.request_count=8
        self.measurement_complete=True
        self.rate_limit=None
        self.events=[]
        self.stopped=False
    def seal_assets(self,plan):
        return {k:{**v,'etag':'"fixture"','size':123456} for k,v in plan['assets'].items()}


def fake_read(remote,asset):
    band=Path(asset['source_uri']).stem
    remote.body_bytes+=100
    remote.request_count+=1
    col,row,width,height=asset['window']
    array=np.full((height,width),4 if band=='SCL' else 1000,dtype='uint8' if band=='SCL' else 'uint16')
    return array,{'driver':'GTiff','width':width,'height':height,'count':1,'dtype':str(array.dtype),
                  'crs':asset['crs'],'transform':Affine(*asset['transform'])@Affine.translation(col,row),
                  'nodata':0,'compress':'deflate'}


def test_readonly_runner_has_no_remote_or_ledger_write(tmp_path,monkeypatch):
    plan,ledger,evidence,raw=fixture(tmp_path,monkeypatch)
    before=sha256(ledger)
    result=pilot.run_pilot(plan,sha256(plan),ledger,evidence,raw,collector_scan=lambda:[])
    assert result['remote_requests']==0 and result['ledger_writes']==0
    assert sha256(ledger)==before and not evidence.exists() and not raw.exists()


def test_single_success_settles_measured_and_preserves_source_data(tmp_path,monkeypatch):
    plan,ledger,evidence,raw=fixture(tmp_path,monkeypatch)
    result=pilot.run_pilot(plan,sha256(plan),ledger,evidence,raw,execute=True,
        remote_factory=FakeRemote,read_window=fake_read,collector_scan=lambda:[])
    assert result['status']=='VERIFIED_REAL' and len(result['assets'])==7
    assert result['qa']['clear_fraction']==1 and not result['learning_ready']
    assert result['ledger_charge_bytes']==710 and result['subsequent_pilots_started']==0
    state=json.loads(ledger.read_text())
    assert state['new_charged_bytes']==710
    assert not (ledger.parent/'global-ledger.execution.lock').exists()
    assert (evidence/'sealed-plan.json').exists()


def test_first_failure_stops_remaining_assets_and_no_retry(tmp_path,monkeypatch):
    plan,ledger,evidence,raw=fixture(tmp_path,monkeypatch)
    called=[]
    def failing(remote,asset):
        band=Path(asset['source_uri']).stem
        called.append(band)
        if band=='B04':
            raise TransferError('synthetic first failure')
        return fake_read(remote,asset)
    result=pilot.run_pilot(plan,sha256(plan),ledger,evidence,raw,execute=True,
        remote_factory=FakeRemote,read_window=failing,collector_scan=lambda:[])
    assert called==['B02','B03','B04'] and result['status']=='BLOCKED'
    assert len(result['assets'])==2 and result['ledger_charge_bytes']==210


def test_429_unknown_measurement_charges_reservation_and_opens_global_circuit(tmp_path,monkeypatch):
    plan,ledger,evidence,raw=fixture(tmp_path,monkeypatch)
    def failing(remote,asset):
        remote.measurement_complete=False
        remote.rate_limit={'http_status':429,'retry_after':'120'}
        raise TransferError('synthetic HTTP429')
    result=pilot.run_pilot(plan,sha256(plan),ledger,evidence,raw,execute=True,
        remote_factory=FakeRemote,read_window=failing,collector_scan=lambda:[])
    state=json.loads(ledger.read_text())
    assert result['status']=='BLOCKED' and result['ledger_charge_bytes']==32*1024**2
    assert state['rate_limit_active'] and state['last_rate_limit']['retry_after']=='120'
