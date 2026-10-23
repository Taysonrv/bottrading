"""Sampled availability estimates, independent of trading and wallet state.

Recent heartbeats at two adjacent samples are evidence, not proof of continuous
uptime. Long sampling gaps stay UNKNOWN; no retroactive credit is created.
"""
import argparse
import math
from contextlib import contextmanager
from pathlib import Path
import threading
import time
from spot_engine.main import save,single_runner
from system_status import build,read


def sample(root,now=None):
    root=Path(root);now=time.time() if now is None else now
    if type(now) not in (int,float) or not 0<=now<1e12:raise ValueError('INVALID_TIME')
    health=build(root,now);execution=health['execution']
    state='RECENT' if execution['fresh'] and health['market']['fresh'] else 'STOPPED' if execution['phase']=='STOPPED' else 'UNKNOWN'
    path=root/'reports/local/operation-health.json';s=read(path)
    if path.exists():
        if s.get('version')!=1 or type(s.get('updated')) not in (int,float) or not math.isfinite(s['updated']) or not 0<=s['updated']<=now:raise ValueError('INVALID_CHECKPOINT')
        if type(s.get('started')) not in (int,float) or not math.isfinite(s['started']) or not 0<=s['started']<=s['updated'] or s.get('state') not in ('RECENT','STOPPED','UNKNOWN') or not isinstance(s.get('transitions'),list):raise ValueError('INVALID_CHECKPOINT')
        for key in ('recent_seconds','stopped_seconds','unknown_seconds'):
            if type(s.get(key)) not in (int,float) or not 0<=s[key]<1e12:raise ValueError('INVALID_CHECKPOINT')
        delta=now-s['updated']
        category=state.lower()+'_seconds' if delta<=45 and s['state']==state else 'unknown_seconds'
        s[category]+=delta
        if delta>45:s['last_gap_seconds']=delta
    else:
        s=dict(version=1,started=now,recent_seconds=0,stopped_seconds=0,unknown_seconds=0,last_gap_seconds=None,transitions=[])
    if s.get('state')!=state:
        s['transitions']=(s.get('transitions',[])+[dict(time=now,state=state,reason=execution.get('reason'))])[-50:]
    s.update(updated=now,state=state,execution_phase=execution['phase'],reason=execution.get('reason'),
             execution_age_seconds=execution['age_seconds'],market_age_seconds=health['market']['age_seconds'])
    path.parent.mkdir(parents=True,exist_ok=True);save(path,s)
    return s


@contextmanager
def service(root):
    stopping=threading.Event()
    with single_runner(Path(root)/'reports/local/operation-health.lock'):
        def work():
            while not stopping.is_set():
                try:sample(root)
                except Exception:pass
                stopping.wait(15)
        worker=threading.Thread(target=work,daemon=True,name='operation-health');worker.start()
        try:yield
        finally:stopping.set();worker.join(timeout=1)


def main():
    parser=argparse.ArgumentParser(description='Observação de disponibilidade; nunca inicia trading.')
    parser.add_argument('--data-dir',type=Path,default=Path(__file__).resolve().parent)
    args=parser.parse_args()
    with service(args.data_dir):
        try:
            while True:time.sleep(1)
        except KeyboardInterrupt:pass


if __name__=='__main__':main()
