"""Offline observation replay, isolated from wallets, orders and the live bot.

Does not count historical elapsed time as 48 hours of forward observation.
"""
import argparse
from collections import Counter, deque
import hashlib
import json
from pathlib import Path
import time
import uuid
from spot_engine.data import load_history
from .context import replay
from .strategies import evaluate
from . import VERSION, SYMBOLS


def identity():
    # Read-only dependencies are also hashed: a research change cannot silently
    # resume output under an old provenance hash. There is no trading session.
    package = Path(__file__).parent
    spot = package.parent/'spot_engine'
    paths = sorted(package.glob('*.py')) + [spot/name for name in
        ('data.py','v3_research.py','risk.py','execution.py','v3_position_plan.py')]
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.parent.name.encode()+b'/'+path.name.encode()+b'\0'+path.read_bytes())
    return digest.hexdigest()


def observe(history, stop=None):
    counts = Counter(); actions = Counter(); recent = deque(maxlen=50)
    last = None; bars = 0; candidates = 0; ready = 0; candidate_samples = []
    started = time.perf_counter()
    for state in replay(history):
        if stop is not None and Path(stop).exists():
            reason = 'STOP'; break
        signal = evaluate(state).report()
        signal.update(symbol=history.symbol,timestamp_ms=state['decision_ms'])
        counts[signal['regime']] += 1; actions[signal['action']] += 1
        candidates += signal['action'] == 'ENTER'; ready += state['ready']; bars += 1
        if signal['action'] == 'ENTER' and len(candidate_samples) < 1000:
            candidate_samples.append(signal)
        recent.append(signal); last = state
    else: reason = 'REPLAY_COMPLETE'
    return dict(pipeline_version=VERSION,run_id=str(uuid.uuid4()),identity=identity(),
        mode='PAPER',phase='OBSERVE_ONLY',reason=reason,source='OFFLINE_CSV',
        symbol=history.symbol,updated_ms=int(time.time()*1000),
        bars=bars,ready_bars=ready,regime_counts=dict(counts),action_counts=dict(actions),
        research_candidates=candidates,candidate_samples=candidate_samples,
        candidate_samples_truncated=candidates>len(candidate_samples),
        signals=list(reversed(recent)),last_state=last,
        cycle_latency_ms=(time.perf_counter()-started)*1000,
        capital=None,equity=None,pnl=None,cash=None,units='0',buy_fills=0,sell_fills=0,
        forward_observation_hours=0,manual_signals_reviewed=0,
        validation=dict(observation_48h=False,three_historical_regimes=len(set(counts)-{'UNKNOWN'})>=3,
                        ten_signals_reviewed=False),
        approved=False,execution_authorized=False,real_orders=0,
        limitations=['Historical replay is not a 48h forward test.',
            'No position lifecycle, partial fills, trailing or broker integration.',
            'Candidate counts are not trades, accuracy or profitability.',
            'Regimes from rules do not establish predictive accuracy.',
            'This attachment variant differs from the original four V3 hypotheses.'])


def main():
    parser = argparse.ArgumentParser(description='V3 observação CSV, sem carteira ou execução.')
    parser.add_argument('--csv',type=Path,required=True)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--stop-root',type=Path,default=Path.cwd())
    args = parser.parse_args()
    history = load_history(args.csv)
    if history.symbol not in SYMBOLS: parser.error('Universo V3: BTC/ETH/SOL/BNB USDT.')
    if args.output:
        target = args.output.resolve()
        allowed = (Path(__file__).resolve().parent.parent/'reports/local/v3-status').resolve()
        if not target.is_relative_to(allowed) or target.suffix != '.json':
            parser.error('Output permitido somente em reports/local/v3-status/*.json')
        if target.exists(): parser.error('Use arquivo novo; relatórios anteriores são preservados.')
    result = observe(history,args.stop_root/'STOP')
    payload = json.dumps(result,ensure_ascii=False,allow_nan=False,indent=2)
    if args.output:
        target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('x',encoding='utf-8') as stream: stream.write(payload+'\n')
    print(payload)


if __name__ == '__main__': main()
