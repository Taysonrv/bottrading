"""One new frozen entry hypothesis; offline research, never an order engine."""
import argparse
from dataclasses import replace
from decimal import Decimal as D
import hashlib
import json
from pathlib import Path
import uuid
from spot_engine.data import load_history
from spot_engine.main import save
from spot_engine.risk import Rules
from spot_engine.strategy import analyze
from single_exit_research import evaluate

ROOT=Path(__file__).resolve().parent


def pullback_signals(history,cfg):
    indicators=analyze(history,cfg)
    result=[]
    for i,current in enumerate(indicators):
        enter=False
        if i and current.ready:
            previous=indicators[i-1]
            b=history.candles[i];prior=history.candles[i-1]
            enter=(previous.ready and previous.ema_fast>previous.ema_slow>previous.ema_trend
                and current.ema_fast>current.ema_slow>current.ema_trend
                and prior.close<=previous.ema_fast and b.close>current.ema_fast
                and b.close>b.open and current.atr_fraction is not None
                and .001<=current.atr_fraction<=.02)
        result.append(replace(current,action='ENTER_LONG' if enter else 'HOLD',
                              reason='PULLBACK_RECOVERY' if enter else 'WAIT_PULLBACK'))
    return tuple(result)


def main():
    p=argparse.ArgumentParser(description='Pullback BTC/1h: estudo exploratório offline de uma hipótese congelada.')
    p.add_argument('--csv',type=Path,required=True)
    p.add_argument('--baseline',type=Path,default=ROOT/'research_results/single-exit-20261025.json')
    p.add_argument('--data-dir',type=Path,default=ROOT)
    args=p.parse_args()
    plan_path=ROOT/'experiments/pullback_20_plan.json'
    plan=json.loads(plan_path.read_text(encoding='utf-8'))
    baseline=json.loads(args.baseline.read_text(encoding='utf-8-sig'))
    csv_hash=hashlib.sha256(args.csv.read_bytes()).hexdigest()
    if csv_hash!=baseline['csv_sha256']:p.error('Use a mesma amostra exploratória identificada no baseline.')
    history=load_history(args.csv)
    if history.symbol!='BTC/USDT':p.error('Hipótese congelada BTC/USDT.')
    raw=baseline['filter_assumptions']
    rules=Rules(**{k:v if k in ('symbol','observed_ms') else D(v) for k,v in raw.items()})
    report=evaluate(history,rules,signal_generator=pullback_signals)
    failed=any(s['continuous']['net_return']<=0 or s['continuous']['position_open']
        or s['continuous']['blocked_exit_attempts'] or s['continuous']['drawdown_latched']
        or any(w['position_open'] or w['blocked_exit_attempts'] or w['drawdown_latched'] for w in s['windows'])
        for s in report['scenarios'])
    report['verdict']='REJECTED' if failed or report['positive_base_windows']<3 else 'PRELIMINARY_ONLY_NOT_VALIDATED'
    report.update(scope='PULLBACK_20_EXPLORATORY_RESEARCH',hypothesis=plan['id'],run_id=uuid.uuid4().hex,
        plan_sha256=hashlib.sha256(plan_path.read_bytes()).hexdigest(),csv_sha256=csv_hash,
        independent_validation=False,approved=False,execution_authorized=False)
    report['source_hashes']={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
        for name in ('pullback_research.py','single_exit_research.py','spot_engine/strategy.py','spot_engine/config.py')}
    report['limitations'].append('One additional hypothesis after inspecting failed EMA results; same sample is exploration, not independent validation.')
    folder=args.data_dir/'reports/local/pullback-research';folder.mkdir(parents=True,exist_ok=True)
    with (folder/(report['run_id']+'.json')).open('x',encoding='utf-8') as out:json.dump(report,out,indent=2,allow_nan=False)
    save(folder/'latest.json',report)
    print(json.dumps({k:report[k] for k in ('hypothesis','verdict','positive_base_windows','approved')}))
    for s in report['scenarios']:
        print(json.dumps(dict(name=s['name'],net_return=s['continuous']['net_return'],trades=s['continuous']['closed_trades'],
            windows=[w['net_return'] for w in s['windows']],fees=s['continuous']['fees'])))


if __name__=='__main__':main()
