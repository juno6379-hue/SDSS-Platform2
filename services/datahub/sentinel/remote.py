"""고정 COG의 HEAD/ETag/Range를 검증하는 제한 전송기. GDAL 직접 network는 사용하지 않는다."""
from collections import OrderedDict
from datetime import datetime, timezone
from http.client import IncompleteRead
import io
import json
import re
import time
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, HTTPRedirectHandler, build_opener

from .pin_planner import asset_uri, canonical_sha


class TransferError(RuntimeError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        raise TransferError('HTTP_REDIRECT_NOT_ALLOWED')


class RemoteIO:
    """한 pilot 누적본문·횟수·간격·첫 실패 회로. SAS는 메모리에서만 유지한다."""
    def __init__(self,maximum_bytes,*,spacing=2,transport=None):
        if type(maximum_bytes) is not int or not 1<=maximum_bytes<=32*1024**2 or not 0<=spacing<=10:
            raise ValueError('REMOTE_BUDGET_OR_SPACING_INVALID')
        self.maximum=maximum_bytes
        self.spacing=spacing
        self.transport=transport
        self.body_bytes=0
        self.request_count=0
        self.last_at=0
        self.stopped=False
        self.measurement_complete=True
        self.rate_limit=None
        self.events=[]
        self.tokens={}

    def _send(self,method,url,headers,limit):
        with build_opener(NoRedirect()).open(Request(url,method=method,headers=headers),timeout=20) as response:
            response_headers={k.lower():v for k,v in response.headers.items()}
            length=response_headers.get('content-length')
            if method=='GET' and length is not None and int(length)>limit:
                self.measurement_complete=False
                raise TransferError('DECLARED_BODY_EXCEEDS_REQUEST_BUDGET')
            raw=b'' if method=='HEAD' else response.read(limit)
            if method=='GET' and ((length is not None and len(raw)!=int(length))
                                 or (length is None and len(raw)==limit)):
                self.body_bytes+=len(raw)
                self.measurement_complete=False
                raise TransferError('INCOMPLETE_OR_AMBIGUOUS_BODY')
            return response.status,response_headers,raw

    def request(self,method,url,headers,limit):
        p=urlsplit(url)
        if p.hostname=='planetarycomputer.microsoft.com':
            if p.scheme!='https' or p.netloc!=p.hostname or p.query or not re.fullmatch(
                r'/api/sas/v1/token/sentinel2l2a0[1-9]/sentinel2-l2',p.path):
                raise TransferError('TOKEN_ENDPOINT_NOT_ALLOWED')
        else:
            asset_uri(url.split('?',1)[0])
        if self.stopped:
            raise TransferError('FIRST_FAILURE_CIRCUIT_OPEN')
        if method not in ('GET','HEAD') or self.request_count>=80:
            self.stopped=True
            raise TransferError('METHOD_OR_REQUEST_COUNT_LIMIT')
        remaining=self.maximum-self.body_bytes
        if type(limit) is not int or limit<0 or limit>remaining or (method=='GET' and limit==0):
            self.stopped=True
            raise TransferError('REMOTE_CUMULATIVE_BUDGET_EXCEEDED')
        wait=self.spacing-(time.monotonic()-self.last_at)
        if wait>0:
            time.sleep(wait)
        self.last_at=time.monotonic()
        self.request_count+=1
        event={'method':method,'request_host':p.hostname,'request_path':p.path,'body_bytes':0}
        try:
            status,response_headers,raw=(self.transport or self._send)(method,url,
                {'Accept-Encoding':'identity','Cache-Control':'no-cache','Pragma':'no-cache',**headers},limit)
            self.body_bytes+=len(raw)
            event.update(http_status=status,body_bytes=len(raw),content_range=response_headers.get('content-range'))
            if len(raw)>limit or self.body_bytes>self.maximum:
                self.measurement_complete=False
                raise TransferError('UNTRUSTED_RESPONSE_EXCEEDS_BUDGET')
            if status==429:
                self.rate_limit={**event,'retry_after':response_headers.get('retry-after')}
                raise TransferError('HTTP429_STOP')
            if status not in (200,206):
                raise TransferError('HTTP_STATUS_'+str(status))
            return status,response_headers,raw
        except HTTPError as exc:
            event['http_status']=exc.code
            self.measurement_complete=False
            if exc.code==429:
                self.rate_limit={**event,'retry_after':(exc.headers or {}).get('Retry-After')}
            self.stopped=True
            raise TransferError('HTTP_STATUS_'+str(exc.code)) from None
        except IncompleteRead as exc:
            self.body_bytes+=len(exc.partial)
            self.measurement_complete=False
            self.stopped=True
            raise TransferError('INCOMPLETE_BODY') from None
        except Exception:
            self.stopped=True
            if not isinstance(__import__('sys').exc_info()[1],TransferError):
                self.measurement_complete=False
            raise
        finally:
            self.events.append(event)

    def signed(self,uri):
        asset_uri(uri)
        p=urlsplit(uri)
        account=p.hostname.split('.')[0]
        cached=self.tokens.get(account)
        now=datetime.now(timezone.utc).timestamp()
        if not cached or cached['expiry']<=now+120:
            endpoint='https://planetarycomputer.microsoft.com/api/sas/v1/token/'+account+'/sentinel2-l2'
            _,_,raw=self.request('GET',endpoint,{},min(64*1024,self.maximum-self.body_bytes))
            data=json.loads(raw)
            expiry=datetime.fromisoformat(data['msft:expiry'].replace('Z','+00:00'))
            token=data['token'].lstrip('?')
            if expiry.tzinfo is None or expiry.timestamp()<=now+120 or 'sig=' not in token:
                self.stopped=True
                raise TransferError('TOKEN_EXPIRY_OR_SCHEMA_INVALID')
            cached={'expiry':expiry.timestamp(),'token':token}
            self.tokens[account]=cached
        return uri+'?'+cached['token']

    def seal_assets(self,plan):
        sealed={}
        for band,asset in plan['assets'].items():
            signed=self.signed(asset['source_uri'])
            status,headers,raw=self.request('HEAD',signed,{},0)
            etag=headers.get('etag','')
            size=int(headers.get('content-length','0'))
            if status!=200 or raw or not 0<size<=2*1024**3 or not re.fullmatch(r'"[A-Za-z0-9_-]+"',etag):
                self.stopped=True
                raise TransferError('HEAD_ASSET_PIN_INVALID')
            sealed[band]={**asset,'etag':etag,'size':size,'live_pin_status':'HEAD_VERIFIED',
                          'head_metadata_sha256':canonical_sha({'etag':etag,'size':size,'last_modified':headers.get('last-modified')})}
        return sealed


class PinnedRangeReader(io.RawIOBase):
    def __init__(self,remote,asset,block_size=128*1024):
        super().__init__()
        self.remote=remote
        self.asset=asset
        self.size=asset['size']
        self.name=asset['source_uri']
        self.mode='rb'
        self.position=0
        self.block_size=block_size
        self.cache=OrderedDict()
        self.last_error=None

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.position

    def seek(self,offset,whence=0):
        position=offset if whence==0 else self.position+offset if whence==1 else self.size+offset if whence==2 else -1
        if position<0:
            raise ValueError('INVALID_COG_SEEK')
        self.position=position
        return position

    def read(self,size=-1):
        size=max(0,self.size-self.position) if size<0 else min(size,max(0,self.size-self.position))
        if size>4*1024**2:
            self.remote.stopped=True
            raise TransferError('UNBOUNDED_COG_READ_FORBIDDEN')
        if size==0:
            return b''
        blocks=list(range(self.position//self.block_size,(self.position+size-1)//self.block_size+1))
        missing=[b for b in blocks if b not in self.cache]
        try:
            while missing:
                first=last=missing.pop(0)
                while missing and missing[0]==last+1 and (missing[0]-first+1)*self.block_size<=4*1024**2:
                    last=missing.pop(0)
                start=first*self.block_size
                end=min(self.size,(last+1)*self.block_size)-1
                n=end-start+1
                status,headers,raw=self.remote.request('GET',self.remote.signed(self.name),
                    {'Range':f'bytes={start}-{end}','If-Match':self.asset['etag']},n)
                expected=f'bytes {start}-{end}/{self.size}'
                if (status!=206 or headers.get('etag')!=self.asset['etag']
                        or headers.get('content-range')!=expected or len(raw)!=n):
                    raise TransferError('RANGE_ETAG_BODY_PIN_MISMATCH: expected='+expected+
                                        '; actual='+str(headers.get('content-range'))[:100])
                for block in range(first,last+1):
                    local=block*self.block_size-start
                    self.cache[block]=raw[local:local+self.block_size]
            data=b''.join(self.cache[b] for b in blocks)
            offset=self.position%self.block_size
            self.position+=size
            # 필요 현재 block은 유지하고 오래된 범위만 제거한다.
            while len(self.cache)>64:
                self.cache.popitem(last=False)
            return data[offset:offset+size]
        except Exception as exc:
            self.remote.stopped=True
            self.last_error=exc
            raise

    def readinto(self,buffer):
        data=self.read(len(buffer))
        buffer[:len(data)]=data
        return len(data)
