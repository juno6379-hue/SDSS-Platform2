from datetime import datetime,timezone,timedelta
import json
from unittest.mock import Mock

import pytest

from services.datahub.sentinel.remote import RemoteIO,PinnedRangeReader,TransferError

URI='https://sentinel2l2a01.blob.core.windows.net/sentinel2-l2/synthetic/B02.tif'


def token():
    return json.dumps({'token':'se=future&sig=synthetic',
        'msft:expiry':(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()}).encode()


def asset():
    return {'source_uri':URI,'size':16,'etag':'"test"'}


def test_sas_cache_is_per_container_and_not_in_events():
    transport=Mock(return_value=(200,{},token()))
    client=RemoteIO(4096,spacing=0,transport=transport)
    a=client.signed(URI)
    b=client.signed(URI.replace('B02','B03'))
    assert '?se=' in a and '?se=' in b and transport.call_count==1
    assert 'sig=' not in json.dumps(client.events)


def test_range_uses_etag_exact_content_range_and_caches_blocks():
    def transport(method,url,headers,limit):
        if 'api/sas' in url:
            return 200,{},token()
        assert headers['If-Match']=='"test"' and headers['Range']=='bytes=0-7'
        return 206,{'etag':'"test"','content-range':'bytes 0-7/16'},b'abcdefgh'
    client=RemoteIO(4096,spacing=0,transport=transport)
    reader=PinnedRangeReader(client,asset(),block_size=8)
    assert reader.read(4)==b'abcd'
    reader.seek(1)
    assert reader.read(3)==b'bcd'
    assert client.request_count==2


@pytest.mark.parametrize('headers',[
    {'etag':'"changed"','content-range':'bytes 0-7/16'},
    {'etag':'"test"','content-range':'bytes 8-15/16'},
])
def test_range_mismatch_trips_first_failure_circuit(headers):
    transport=Mock(side_effect=[(200,{},token()),(206,headers,b'abcdefgh')])
    client=RemoteIO(4096,spacing=0,transport=transport)
    reader=PinnedRangeReader(client,asset(),block_size=8)
    with pytest.raises(TransferError,match='PIN_MISMATCH'):
        reader.read(4)
    with pytest.raises(TransferError,match='CIRCUIT_OPEN'):
        client.request('HEAD',URI,{},0)
    assert transport.call_count==2


def test_429_stops_next_request_and_preserves_retry_after():
    transport=Mock(return_value=(429,{'retry-after':'120'},b''))
    client=RemoteIO(100,spacing=0,transport=transport)
    with pytest.raises(TransferError,match='429'):
        client.request('HEAD',URI,{},0)
    assert client.rate_limit['retry_after']=='120'
    with pytest.raises(TransferError,match='CIRCUIT_OPEN'):
        client.request('HEAD',URI,{},0)
    assert transport.call_count==1


def test_unknown_timeout_is_not_measurement_complete():
    client=RemoteIO(100,spacing=0,transport=Mock(side_effect=TimeoutError('fixture')))
    with pytest.raises(TimeoutError):
        client.request('GET',URI,{},50)
    assert client.stopped and not client.measurement_complete


def test_unbounded_read_rejected_without_http():
    transport=Mock()
    client=RemoteIO(8*1024**2,spacing=0,transport=transport)
    reader=PinnedRangeReader(client,{**asset(),'size':16*1024**2})
    with pytest.raises(TransferError,match='UNBOUNDED_COG'):
        reader.read()
    transport.assert_not_called()


def test_rasterio_reads_real_tiff_via_only_bounded_custom_transport():
    import numpy as np
    from affine import Affine
    from rasterio.io import MemoryFile
    from services.datahub.sentinel.pilot import read_asset_window
    affine=Affine(10,0,500000,0,-10,1000000)
    with MemoryFile() as memory:
        with memory.open(driver='GTiff',width=256,height=256,count=1,dtype='uint16',
                         crs='EPSG:32648',transform=affine) as ds:
            ds.write(np.full((1,256,256),1234,dtype='uint16'))
        raw=memory.read()
    def transport(method,url,headers,limit):
        if 'api/sas' in url:
            return 200,{},token()
        start,end=map(int,headers['Range'].removeprefix('bytes=').split('-'))
        return 206,{'etag':'"test"','content-range':f'bytes {start}-{end}/{len(raw)}'},raw[start:end+1]
    client=RemoteIO(1024**2,spacing=0,transport=transport)
    sealed={**asset(),'size':len(raw),'shape':[256,256],'transform':list(affine)[:6],
            'crs':'EPSG:32648','window':[10,20,64,64]}
    array,profile=read_asset_window(client,sealed)
    assert array.shape==(64,64) and (array==1234).all()
    assert client.body_bytes<1024**2 and client.request_count<10
