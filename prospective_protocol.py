"""Local preregistration and immutable future OHLCV snapshots; no trading."""
import argparse
from dataclasses import asdict
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import time
from spot_engine.data import PublicBinance,download,retry,Candle,milliseconds
from spot_engine.main import single_runner,save
from system_status import read

ROOT=Path(__file__).resolve().parent
HOUR=3600000
BUFFER=300000
FILES=('prospective_protocol.py','donchian_strategy.py','experiments/prospective_donchian_plan.json',
       'single_exit_research.py','spot_engine/strategy.py','spot_engine/config.py','spot_engine/data.py','spot_engine/risk.py','spot_engine/execution.py')


def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def utc(ms):return datetime.fromtimestamp(ms/1000,timezone.utc).isoformat()
def fingerprint():return {name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in FILES}


def immutable(path,value):
    with path.open('x',encoding='utf-8') as f:
        json.dump(value,f,indent=2,allow_nan=False);f.flush();os.fsync(f.fileno())


def folder(root):return Path(root)/'reports/local/prospective'


def registration(root):
    path=folder(root)/'registration.json'
    if path.stat().st_size>100000:raise ValueError('REGISTRATION_SIZE_LIMIT')
    value=json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value,dict):raise ValueError('INVALID_REGISTRATION')
    body={k:v for k,v in value.items() if k!='protocol_sha256'}
    if digest(body)!=value.get('protocol_sha256'):raise ValueError('REGISTRATION_HASH_MISMATCH')
    if value['implementation_hashes']!=fingerprint():raise ValueError('PROTOCOL_CODE_CHANGED')
    start=value['start_ms'];end=value['end_ms'];registered=value['registered_ms']
    if not all(type(v) is int for v in (start,end,registered)) or not 0<=registered<start or start!=((registered+BUFFER)//HOUR+1)*HOUR or end-start!=30*24*HOUR:
        raise ValueError('INVALID_RESERVED_WINDOW')
    if value['hypothesis']!=json.loads((ROOT/'experiments/prospective_donchian_plan.json').read_text(encoding='utf-8')):
        raise ValueError('REGISTERED_SPEC_CHANGED')
    return value


def register(root,now_ms):
    milliseconds(now_ms)
    if now_ms<600*HOUR:raise ValueError('INSUFFICIENT_WARMUP_HORIZON')
    place=folder(root);place.mkdir(parents=True,exist_ok=True)
    spec=json.loads((ROOT/'experiments/prospective_donchian_plan.json').read_text(encoding='utf-8'))
    expected=dict(window_days=30,symbol='BTC/USDT',timeframe='1h',channel_bars=20,ema_trend=200,atr_period=14,
        warmup_bars=600,stop_fraction='0.02',target_fraction='0.05',max_holding_bars=48,capital_usdt='20',
        max_entry_cost_usdt='6',risk_fraction='0.01',daily_loss_fraction='0.03',drawdown_fraction='0.10',
        fee_each_side='0.001',slippage_each_side='0.001',parameter_variants=1,minimum_closed_cycles=30,execution_authorized=False)
    if any(spec.get(k)!=v for k,v in expected.items()):raise ValueError('FIXED_PROTOCOL_REQUIRED')
    start=((now_ms+BUFFER)//HOUR+1)*HOUR
    milliseconds(start+30*24*HOUR)
    value=dict(scope='LOCAL_PROSPECTIVE_DATA_PROTOCOL',registered_ms=now_ms,start_ms=start,end_ms=start+30*24*HOUR,
        registered_utc=utc(now_ms),start_utc=utc(start),end_utc=utc(start+30*24*HOUR),
        hypothesis=spec,implementation_hashes=fingerprint(),clock_source='BINANCE_PUBLIC_SERVER_TIME',
        external_notarization=False,execution_authorized=False)
    value['protocol_sha256']=digest(value)
    immutable(place/'registration.json',value)
    save(place/'latest.json',dict(scope=value['scope'],status='REGISTERED_WAITING',updated_ms=now_ms,
        hypothesis_id=spec['id'],start_ms=start,end_ms=value['end_ms'],future_bars=0,
        protocol_sha256=value['protocol_sha256'],execution_authorized=False,validated=False))
    return value


def read_state(root):
    path=folder(root)/'state.json'
    if path.exists() and path.stat().st_size>10000:raise ValueError('STATE_SIZE_LIMIT')
    value=json.loads(path.read_text(encoding='utf-8')) if path.exists() else dict(last_end_ms=0,last_sha256=None)
    if not isinstance(value,dict) or type(value.get('last_end_ms')) is not int or value['last_end_ms']<0:
        raise ValueError('INVALID_COLLECTION_STATE')
    if not value['last_end_ms'] and value.get('last_sha256') is not None:raise ValueError('INVALID_COLLECTION_STATE')
    return value


def read_batch(root,end,reg):
    if type(end) is not int or end<=0:raise ValueError('INVALID_BATCH_END')
    path=folder(root)/'data'/(str(end)+'.json')
    if path.stat().st_size>1000000:raise ValueError('BATCH_SIZE_LIMIT')
    raw=path.read_bytes()
    value=json.loads(raw)
    if not isinstance(value,dict):raise ValueError('INVALID_BATCH')
    if value.get('protocol_sha256')!=reg['protocol_sha256'] or value.get('end_ms')!=end:raise ValueError('BATCH_PROTOCOL_MISMATCH')
    observed=milliseconds(value['observed_ms']);start=reg['start_ms']-600*HOUR
    if not reg['start_ms']<end<=reg['end_ms'] or end%HOUR or observed<end:raise ValueError('BATCH_TIME_DOMAIN')
    candles=value.get('candles')
    if not isinstance(candles,list) or len(candles)!=(end-start)//HOUR or value.get('warmup_bars')!=600:raise ValueError('BATCH_COVERAGE')
    for i,row in enumerate(candles):
        c=Candle(**row)
        if c.open_ms!=start+i*HOUR:raise ValueError('BATCH_GAP')
    return value,hashlib.sha256(raw).hexdigest()


def collect(root,client):
    reg=registration(root);now=int(retry(client.fetch_time));end=min(now//HOUR*HOUR,reg['end_ms']);place=folder(root)
    state=read_state(root);last=state.get('last_end_ms')
    if type(last) is not int or last<0 or (last and (last%HOUR or not reg['start_ms']<last<=reg['end_ms'])):
        raise ValueError('INVALID_COLLECTION_STATE')
    if not last and state.get('last_sha256') is not None:raise ValueError('INVALID_COLLECTION_STATE')
    if now<reg['registered_ms'] or end<last:raise ValueError('COLLECTION_CLOCK_REVERSED')
    previous=None
    if last:
        previous,sha=read_batch(root,last,reg)
        if sha!=state.get('last_sha256'):raise ValueError('BATCH_HASH_MISMATCH')
        if previous['observed_ms']>now:raise ValueError('BATCH_OBSERVED_IN_FUTURE')
    status='WAITING_FIRST_FUTURE_CLOSE' if end<=reg['start_ms'] else 'COLLECTED_FUTURE_DATA'
    if end>reg['start_ms'] and end>last:
        data=place/'data';data.mkdir(exist_ok=True)
        if any(p.stem not in (str(last),str(end)) and (not p.stem.isdigit() or int(p.stem)>last) for p in data.glob('*.json')):
            raise ValueError('UNINDEXED_BATCH_REQUIRES_REVIEW')
        history=download(client,'BTC/USDT','1h',reg['start_ms']-600*HOUR,end)
        candles=[asdict(c) for c in history.candles]
        if previous and candles[:len(previous['candles'])]!=previous['candles']:raise ValueError('PAST_CANDLE_REVISION')
        value=dict(protocol_sha256=reg['protocol_sha256'],end_ms=end,observed_ms=history.observed_ms,
            previous_sha256=state.get('last_sha256'),warmup_bars=600,candles=candles,
            source='Binance public OHLCV; not executable quotes',execution_authorized=False)
        path=data/(str(end)+'.json')
        if path.exists():
            stored,_=read_batch(root,end,reg)
            if stored['candles']!=candles or stored['previous_sha256']!=value['previous_sha256']:raise ValueError('EXISTING_BATCH_CONFLICT')
        else:immutable(path,value)
        sha=hashlib.sha256(path.read_bytes()).hexdigest()
        state=dict(last_end_ms=end,last_sha256=sha);save(place/'state.json',state);last=end
    if now>=reg['end_ms']:status='WINDOW_CLOSED_DATA_ONLY'
    report=dict(scope='LOCAL_PROSPECTIVE_DATA_PROTOCOL',updated_ms=now,status=status,hypothesis_id=reg['hypothesis']['id'],
        start_ms=reg['start_ms'],end_ms=reg['end_ms'],future_bars=max(0,(last-reg['start_ms'])//HOUR) if last else 0,
        protocol_sha256=reg['protocol_sha256'],last_end_ms=last or None,last_sha256=state.get('last_sha256'),
        orders=0,closed_cycles=None,validated=False,execution_authorized=False,
        note='Future data reservation only; no evaluation, paper orders, scheduler or automatic promotion.')
    save(place/'latest.json',report);return report


def view(root,now_ms=None):
    place=folder(root)
    if not (place/'registration.json').exists():return dict(available=False,status='NOT_REGISTERED',execution_authorized=False)
    try:
        reg=registration(root);state=read_state(root)
        if state.get('last_end_ms'):
            _,sha=read_batch(root,state['last_end_ms'],reg)
            if sha!=state.get('last_sha256'):raise ValueError('BATCH_HASH_MISMATCH')
        latest=read(place/'latest.json');now=int(time.time()*1000) if now_ms is None else now_ms
        health=read(place/'health.json')
        last=state.get('last_end_ms',0)
        return dict(latest,available=True,local_hashes_match=True,health=health,
            hypothesis_id=reg['hypothesis']['id'],start_ms=reg['start_ms'],end_ms=reg['end_ms'],
            future_bars=(last-reg['start_ms'])//HOUR if last else 0,
            validated=False,execution_authorized=False,last_snapshot_verified=bool(last),
            collection_due_local_estimate=min(now//HOUR*HOUR,reg['end_ms'])>max(reg['start_ms'],state.get('last_end_ms',0)),
            note='Local integrity check and future data reservation; not external notarization, trading or validation.')
    except (OSError,ValueError,KeyError,TypeError,ArithmeticError):
        return dict(available=False,status='PROTOCOL_INTEGRITY_ERROR',validated=False,execution_authorized=False)


def verify_all(root):
    reg=registration(root);place=folder(root);previous=None;last_sha=None;last_end=0;count=0
    paths=list((place/'data').glob('*.json')) if (place/'data').exists() else []
    if any(not p.stem.isdigit() for p in paths):raise ValueError('UNRECOGNIZED_DATA_FILE')
    for path in sorted(paths,key=lambda p:int(p.stem)):
        end=int(path.stem);value,sha=read_batch(root,end,reg)
        if value['previous_sha256']!=last_sha:raise ValueError('BATCH_CHAIN_MISMATCH')
        if previous and value['candles'][:len(previous['candles'])]!=previous['candles']:raise ValueError('BATCH_PREFIX_MISMATCH')
        previous=value;last_sha=sha;last_end=end;count+=1
    state=read_state(root)
    if state.get('last_end_ms')!=last_end or state.get('last_sha256')!=last_sha:raise ValueError('INDEX_CHAIN_MISMATCH')
    return dict(batches=count,future_bars=max(0,(last_end-reg['start_ms'])//HOUR) if count else 0,
        local_chain_verified=True,external_notarization=False,validated=False,execution_authorized=False)


def main():
    p=argparse.ArgumentParser(description='Registro local e coleta manual futura; sem ordens.')
    p.add_argument('--data-dir',type=Path,required=True)
    p.add_argument('--register',action='store_true');p.add_argument('--collect',action='store_true')
    p.add_argument('--verify',action='store_true');args=p.parse_args()
    place=folder(args.data_dir);place.mkdir(parents=True,exist_ok=True)
    with single_runner(place/'runner.lock'):
        client=PublicBinance() if args.register or args.collect else None
        if args.register:
            r=register(args.data_dir,int(retry(client.fetch_time)))
            print(json.dumps({k:r[k] for k in ('registered_utc','start_utc','end_utc','protocol_sha256')}))
        if args.collect:
            try:
                report=collect(args.data_dir,client)
                save(place/'health.json',dict(healthy=True,updated_ms=int(time.time()*1000),reason=report['status']))
                print(json.dumps(report))
            except Exception as error:
                save(place/'health.json',dict(healthy=False,updated_ms=int(time.time()*1000),reason='COLLECTION_OR_PROTOCOL_ERROR',error_type=type(error).__name__))
                raise SystemExit('Coleta recusada; registros anteriores preservados. Confira integridade, conexão e prazo.') from None
        if args.verify:print(json.dumps(verify_all(args.data_dir)))
        if not args.register and not args.collect and not args.verify:print(json.dumps(registration(args.data_dir),indent=2))


if __name__=='__main__':main()
