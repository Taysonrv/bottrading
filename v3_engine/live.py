"""Separate bounded forward observer. Public market data, no paper fills.

Bootstrap: 152 days of 15m bars to preserve causal 4H/daily aggregation.
Only new closed bars are subsequently downloaded. All failures invalidate
current health; no previous success is represented as a current reading.
"""
import argparse
from collections import deque
import hashlib
import json
from pathlib import Path
import time
from spot_engine.main import single_runner, save, parse_book
from spot_engine.data import PublicBinance, retry
from . import SYMBOLS
from .context import MultiTimeframeContext
from .collector import ParallelCollector
from .engine_v3 import identity
from .strategies import evaluate
from .shadow_bridge import shadow_observe

STEP=900000


class Observer:
    def __init__(self, root, symbols=SYMBOLS):
        self.root=Path(root);self.symbols=tuple(symbols)
        if not self.symbols or len(set(self.symbols))!=len(self.symbols) or any(s not in SYMBOLS for s in self.symbols):raise ValueError('V3_UNIVERSE_ONLY')
        self.folder=self.root/'reports/local/v3-runs';self.folder.mkdir(parents=True,exist_ok=True)
        self.identity=hashlib.sha256((identity()+json.dumps(self.symbols)).encode()).hexdigest()
        path=self.folder/'session.json'
        if path.exists():
            old=json.loads(path.read_text(encoding='utf-8'))
            if old['identity']!=self.identity:raise ValueError('V3_IDENTITY_CHANGED_ARCHIVE_REQUIRED')
        else:
            save(path,dict(identity=self.identity,symbols=self.symbols,created_ms=int(time.time()*1000),
                execution_authorized=False,mode='OBSERVE_ONLY'))
        self.contexts={s:MultiTimeframeContext(s) for s in self.symbols}
        self.cutoff=None;self.recent=deque(maxlen=50);self.shadows=deque(maxlen=50)
        self.emitted={}
        # Restart requires fresh coverage; no claim of uninterrupted observation.
        self.coverage=0.;self.previous_ok=None;self.clock=None

    def stopped(self):return (self.root/'STOP').exists() or (self.folder/'STOP').exists()

    def cycle(self, collector, now):
        started=time.monotonic()
        if type(now) is not int or self.clock is not None and now<self.clock:raise ValueError('CLOCK_REVERSED')
        self.clock=now
        if self.stopped():return self.publish(now,[],False,'STOP',0,0)
        cutoff=now//STEP*STEP;needs=self.cutoff!=cutoff
        candle_ms=0.;history={}
        if needs:
            then=time.monotonic()
            start=(cutoff-152*96*STEP) if self.cutoff is None else self.cutoff
            history=collector.fetch_candles_batch('15m',start,cutoff)
            candle_ms=(time.monotonic()-then)*1000
        then=time.monotonic();books=collector.fetch_books();book_ms=(time.monotonic()-then)*1000
        rows=[];okay=True
        for symbol in self.symbols:
            try:
                if self.stopped():raise ValueError('STOP')
                if needs:
                    h=history[symbol]
                    if isinstance(h,Exception):raise h
                    # Rebuild a failed symbol from full history next cycle; do
                    # not reuse a partially mutated context after a gap/error.
                    for c in h.candles:self.contexts[symbol].update_15m(c,c.open_ms+STEP)
                state=self.contexts[symbol].state()
                if state.get('decision_ms')!=cutoff:raise ValueError('STALE_CANDLE')
                raw=books[symbol]
                if isinstance(raw,Exception):raise raw
                parse_book(raw,symbol)
                signal=evaluate(state).report();signal.update(symbol=symbol,timestamp_ms=cutoff)
                new_signal=needs and self.emitted.get(symbol)!=cutoff
                if new_signal:
                    self.recent.append(signal);self.emitted[symbol]=cutoff
                shadow=None
                if new_signal and signal['action']=='ENTER':
                    shadow=shadow_observe(signal,state,log_dir=self.root/'reports/local/shadow-log')
                    self.shadows.append(shadow)
                rows.append(dict(symbol=symbol,status='OK',regime_v3=state['regime'],
                    score_estimate=signal['score'],state=state,signal=signal,
                    shadow_observation=shadow,execution_authorized=False))
                if not state['ready']:okay=False
            except Exception:
                okay=False
                rows.append(dict(symbol=symbol,status='DATA_UNAVAILABLE',execution_authorized=False))
        if needs:
            if all(r['status']=='OK' for r in rows):self.cutoff=cutoff
            else:
                # A fresh bootstrap is deliberate after a partial failed batch.
                self.cutoff=None;self.contexts={s:MultiTimeframeContext(s) for s in self.symbols}
        # Initial bootstrap is not coverage: its first healthy timestamp is at
        # completion, rather than the server timestamp fetched before download.
        finished=now+int((time.monotonic()-started)*1000)
        if okay and self.previous_ok is not None and 0<=finished-self.previous_ok<=45000:
            self.coverage+=(finished-self.previous_ok)/1000
        self.previous_ok=finished if okay else None
        return self.publish(finished,rows,okay,'OBSERVING' if okay else 'DATA_UNAVAILABLE',
            book_ms,candle_ms,(time.monotonic()-started)*1000,collector.timings)

    def publish(self,now,rows,okay,reason,book_ms,candle_ms,latency=0,timings=None):
        row=dict(mode='PAPER',phase='OBSERVE_ONLY',source='PUBLIC_REST_FORWARD',identity=self.identity,
            updated_ms=now,reason=reason,healthy=okay,pairs=rows,signals=list(reversed(self.recent)),
            shadow_observation=list(reversed(self.shadows)),
            forward_observation_hours=self.coverage/3600,observed_48h=self.coverage>=48*3600,
            manual_signals_reviewed=0,approved=False,execution_authorized=False,
            capital=None,cash=None,equity=None,pnl=None,units='0',buy_fills=0,sell_fills=0,real_orders=0,
            cycle_latency_ms=latency,book_fetch_latency_ms=book_ms,candle_update_latency_ms=candle_ms,
            slowest_symbol=max(timings,key=timings.get) if timings else None,
            warning='SLOW_CYCLE' if latency>12000 else None)
        for folder in (self.folder,self.root/'reports/local/v3-status'):
            folder.mkdir(parents=True,exist_ok=True);save(folder/'latest.json',row)
        return row


def main():
    p=argparse.ArgumentParser(description='Observador V3 público separado; nunca executa ordens.')
    p.add_argument('--data-dir',type=Path,required=True);p.add_argument('--hours',type=int,default=48)
    p.add_argument('--once',action='store_true');p.add_argument('--pairs',nargs='+',default=list(SYMBOLS))
    args=p.parse_args()
    if not 1<=args.hours<=72:p.error('Duração de 1 a 72 horas.')
    folder=args.data_dir/'reports/local/v3-runs'
    with single_runner(folder/'runner.lock'):
        observer=Observer(args.data_dir,args.pairs)
        observer.publish(int(time.time()*1000),[],False,'BOOTSTRAPPING_152_DAYS',0,0)
        clock=PublicBinance();end=time.monotonic()+args.hours*3600
        with ParallelCollector(args.pairs) as collector:
            failures=0
            try:
                while time.monotonic()<end and not observer.stopped():
                    try:
                        report=observer.cycle(collector,int(retry(clock.fetch_time)))
                    except Exception:
                        observer.previous_ok=None
                        report=observer.publish(int(time.time()*1000),[],False,'PUBLIC_DATA_UNAVAILABLE',0,0)
                    print(json.dumps({k:report[k] for k in ('reason','updated_ms','forward_observation_hours')},allow_nan=False),flush=True)
                    if args.once:break
                    failures=0 if report['healthy'] else min(failures+1,5)
                    delay=15 if not failures else min(600,15*2**failures)
                    for _ in range(delay):
                        if observer.stopped():break
                        time.sleep(1)
            finally:
                observer.publish(int(time.time()*1000),[],False,'STOP' if observer.stopped() else 'OBSERVER_ENDED',0,0)


if __name__=='__main__':main()
