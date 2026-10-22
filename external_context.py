"""Keyless, cached market context. Never imported by strategy or execution.

Public market data only; no wallet addresses, account balances or secrets sent.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime
import json
import math
from pathlib import Path
import time
import threading
import urllib.request
import urllib.error
from spot_engine.main import save,single_runner
from system_status import read

COINS={'btc-bitcoin':'BTC','eth-ethereum':'ETH','sol-solana':'SOL','bnb-binance-coin':'BNB','xrp-xrp':'XRP','doge-dogecoin':'DOGE'}
NETWORKS=('bsc','polygon_pos','solana')
INTERVALS={'alternative':21600,'coinpaprika':900,'geckoterminal':900}


def number(value,positive=False):
    if isinstance(value,bool):raise ValueError('INVALID_NUMBER')
    result=float(value)
    if not math.isfinite(result) or result<0 or positive and result==0:raise ValueError('INVALID_NUMBER')
    return result


def timestamp(value,now_ms):
    parsed=datetime.fromisoformat(value.replace('Z','+00:00'))
    if parsed.tzinfo is None:raise ValueError('MISSING_TIMEZONE')
    stamp=int(parsed.timestamp()*1000)
    if not 0<stamp<=now_ms+60000:raise ValueError('INVALID_TIMESTAMP')
    return stamp


def fetch(url):
    request=urllib.request.Request(url,headers={'Accept':'application/json','User-Agent':'SpotLab-context/1.0'})
    with urllib.request.urlopen(request,timeout=8) as response:
        body=response.read(2000001)
        if len(body)>2000000:raise ValueError('RESPONSE_LIMIT')
        return json.loads(body)


def fear(raw,now_ms):
    if raw.get('metadata',{}).get('error'):raise ValueError('PROVIDER_ERROR')
    row=raw['data'][0];value=number(row['value']);stamp=int(row['timestamp'])*1000
    if value>100 or not value.is_integer() or not 0<stamp<=now_ms+60000:raise ValueError('INVALID_INDEX')
    return dict(value=int(value),source_ms=stamp,scope='Bitcoin daily sentiment; not an entry signal')


def ticker(raw,identity,now_ms):
    if raw['id']!=identity or raw['symbol']!=COINS[identity]:raise ValueError('WRONG_ASSET')
    usd=raw['quotes']['USD']
    return dict(symbol=COINS[identity],usd_price=number(usd['price'],True),
                volume_24h_usd=number(usd['volume_24h']),source_ms=timestamp(raw['last_updated'],now_ms))


def pools(raw,network):
    rows=raw['data']
    if not isinstance(rows,list) or len(rows)>100:raise ValueError('INVALID_POOLS')
    result=[]
    for row in rows:
        if row.get('type')!='pool':continue
        a=row['attributes'];name=a['name']
        if not isinstance(name,str) or len(name)>200:raise ValueError('INVALID_POOL_NAME')
        result.append(dict(network=network,name=name,liquidity_usd=number(a['reserve_in_usd']),
                           volume_24h_usd=number(a['volume_usd']['h24'])))
    return sorted(result,key=lambda r:r['liquidity_usd'],reverse=True)[:3]


def collect(provider,get,now_ms):
    if provider=='alternative':return fear(get('https://api.alternative.me/fng/?limit=1'),now_ms)
    if provider=='coinpaprika':
        return dict(tickers=[ticker(get('https://api.coinpaprika.com/v1/tickers/'+identity),identity,now_ms) for identity in COINS])
    if provider=='geckoterminal':
        rows=[];states={};limited=False
        for network in NETWORKS:
            if limited:states[network]='DEFERRED_RATE_LIMIT';continue
            try:
                rows.extend(pools(get('https://api.geckoterminal.com/api/v2/networks/'+network+'/pools?page=1'),network))
                states[network]='OK'
            except Exception as error:
                limited=isinstance(error,urllib.error.HTTPError) and error.code==429
                states[network]='RATE_LIMITED' if limited else 'UNAVAILABLE'
        return dict(pools=rows,networks=states,rate_limited=limited,partial=any(v!='OK' for v in states.values()),
                    scope='Sample of first page per network, not wallet holdings or all DEX liquidity')
    raise ValueError('UNKNOWN_PROVIDER')


def cycle(root,get=fetch,now=None):
    root=Path(root);now=time.time() if now is None else now;ms=int(now*1000)
    path=root/'reports/local/external-context.json';report=read(path)
    sources=report.get('sources',{})
    if not isinstance(sources,dict):sources={}
    for provider,interval in INTERVALS.items():
        old=sources.get(provider,{})
        due=old.get('next_attempt_ms',0)
        if type(due) is int and due>ms:continue
        try:
            data=collect(provider,get,ms)
            sources[provider]=dict(status='PARTIAL' if data.get('partial') else 'OK',data=data,fetched_ms=ms,last_attempt_ms=ms,
                                   next_attempt_ms=ms+max(interval,3600 if data.get('rate_limited') else interval)*1000)
        except Exception as error:
            # Never print raw HTTP errors or response bodies. Stale cache is
            # retained with explicit failure, not promoted to fresh data.
            limited=isinstance(error,urllib.error.HTTPError) and error.code==429
            sources[provider]=dict(status='RATE_LIMITED' if limited else 'UNAVAILABLE',data=old.get('data'),
                fetched_ms=old.get('fetched_ms'),last_attempt_ms=ms,next_attempt_ms=ms+max(interval,3600 if limited else interval)*1000)
    report=dict(mode='CONTEXT_ONLY',execution_authorized=False,updated_ms=ms,sources=sources)
    path.parent.mkdir(parents=True,exist_ok=True);save(path,report)
    return report


@contextmanager
def service(root):
    """Optional collector; provider failures are isolated from trading."""
    stop=threading.Event();folder=Path(root)/'reports/local'
    with single_runner(folder/'external-context.lock'):
        def work():
            while not stop.is_set():
                try:cycle(root)
                except Exception:pass
                stop.wait(60)
        worker=threading.Thread(target=work,daemon=True,name='external-context');worker.start()
        try:yield
        finally:stop.set();worker.join(timeout=1)


def main():
    parser=argparse.ArgumentParser(description='Free public APIs, informational only, no trading or keys.')
    parser.add_argument('--data-dir',type=Path,default=Path(__file__).resolve().parent)
    parser.add_argument('--watch',action='store_true')
    args=parser.parse_args();folder=args.data_dir/'reports/local'
    with single_runner(folder/'external-context.lock'):
        while True:
            result=cycle(args.data_dir)
            print(json.dumps({k:v['status'] for k,v in result['sources'].items()}),flush=True)
            if not args.watch:return
            time.sleep(60)


if __name__=='__main__':main()
