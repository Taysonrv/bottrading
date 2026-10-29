"""Expanded 12-pair observation; does not alter a running wallet or authorize orders."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import time
from spot_engine.data import PublicBinance,retry
from spot_engine.scanner import scan
from spot_engine.main import save,single_runner

ROOT=Path(__file__).resolve().parent
SYMBOLS=('BTC/USDT','ETH/USDT','SOL/USDT','BNB/USDT','XRP/USDT','DOGE/USDT',
         'ADA/USDT','LINK/USDT','AVAX/USDT','LTC/USDT','DOT/USDT','NEAR/USDT')


def cycle(client,state=None):
    now=int(retry(client.fetch_time))
    report=scan(client,now,'15m',symbols=SYMBOLS)
    state={} if state is None else state
    counts=Counter(state.get('signal_counts',{}));last=dict(state.get('last_bars',{}))
    if state.get('last_updated_ms',0)>now:raise ValueError('CLOCK_REVERSED')
    for row in report['pairs']:
        if row['status']!='OK':continue
        key=row['symbol'];bar=row['candle_close_ms']
        if bar>last.get(key,-1):
            if row['action']=='ENTER_LONG':counts[key]+=1
            last[key]=bar
    report.update(scope='EXPANDED_RADAR_OBSERVATION_ONLY',simulated_orders=0,
        signal_counts=dict(counts),last_bars=last,last_updated_ms=now,
        execution_authorized=False,approved=False,
        note='12 watched pairs; signals are observations, not trades. Existing six-pair wallet unchanged.')
    return report


def main():
    p=argparse.ArgumentParser(description='Radar ampliado independente; não compra nem vende.')
    p.add_argument('--data-dir',type=Path,default=ROOT)
    p.add_argument('--watch',action='store_true',help='Coleta por até 24h; sem esta opção faz uma coleta.')
    args=p.parse_args();folder=args.data_dir/'reports/local/expanded-radar';folder.mkdir(parents=True,exist_ok=True)
    identity=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with single_runner(folder/'runner.lock'):
        path=folder/'latest.json';state={}
        if path.exists():
            state=json.loads(path.read_text(encoding='utf-8'))
            if state.get('identity')!=identity:raise ValueError('RADAR_IDENTITY_CHANGED')
        end=time.monotonic()+86400;client=PublicBinance()
        while time.monotonic()<end and not (args.data_dir/'STOP').exists() and not (folder/'STOP').exists():
            try:
                state=cycle(client,state);state['identity']=identity;state['healthy']=True;save(path,state)
                save(folder/'health.json',dict(healthy=True,updated_ms=state['last_updated_ms'],reason='OBSERVING'))
                print(json.dumps(dict(pairs=len(state['pairs']),ok=sum(r['status']=='OK' for r in state['pairs']),
                    entry_signals=state['signal_counts'],execution_authorized=False)),flush=True)
            except Exception:
                # Never present an old success as current data after failure.
                save(folder/'health.json',dict(healthy=False,updated_ms=int(time.time()*1000),reason='PUBLIC_DATA_OR_STATE_ERROR'))
                if not args.watch:raise
            if not args.watch:break
            for _ in range(60):
                if (args.data_dir/'STOP').exists() or (folder/'STOP').exists():break
                time.sleep(1)


if __name__=='__main__':main()
