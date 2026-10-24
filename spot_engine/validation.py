"""Fixed-rule rolling OOS audit and trade-cashflow bootstrap; never execution.

Training blocks are context/warmup only: no parameter search is performed.
Overlapping OOS windows are not independent trials or a compound portfolio.
"""
import argparse
from dataclasses import asdict, replace
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import random
import uuid
from .backtest import run
from .config import load_settings
from .data import History, load_history

TRAIN=17520; TEST=5840; STEP=2920
SCENARIOS=(('no_costs','0','0'),('fees_only','.001','0'),
           ('slippage_only','0','.001'),('base','.001','.001'),('stress','.002','.002'))


def percentile(values, p):
    ordered=sorted(values); x=(len(ordered)-1)*p; low=int(x)
    return ordered[low]+(ordered[min(low+1,len(ordered)-1)]-ordered[low])*(x-low)


def bootstrap(trades, capital, seed, samples=1000):
    if type(seed) is not int or type(samples) is not int or not 100<=samples<=10000:
        raise ValueError('BOOTSTRAP_ARGUMENTS')
    if capital<=0: raise ValueError('INVALID_CAPITAL')
    pnls=[t['pnl'] for t in trades]
    if not pnls:
        return dict(seed=seed,samples=samples,trades=0,percentiles=None,robust=False,
                    method='IID_FIXED_CASHFLOW_SUM_DIVIDED_BY_STARTING_CAPITAL')
    rng=random.Random(seed)
    returns=[sum(rng.choices(pnls,k=len(pnls)))/capital for _ in range(samples)]
    ps={name:percentile(returns,p) for name,p in
        (('p5',.05),('p25',.25),('p50',.5),('p75',.75),('p95',.95))}
    return dict(seed=seed,samples=samples,trades=len(pnls),percentiles=ps,
                robust=ps['p25']>-.05,
                method='IID_FIXED_CASHFLOW_SUM_DIVIDED_BY_STARTING_CAPITAL')


def rolling(history, settings, train=TRAIN, test=TEST, step=STEP):
    if history.timeframe!='15m': raise ValueError('ROLLING_REQUIRES_15M')
    if min(train,test,step)<=0: raise ValueError('INVALID_WINDOWS')
    warmup=max(3*settings.ema_trend,settings.atr_period+1)
    if train<warmup: raise ValueError('TRAIN_SHORTER_THAN_WARMUP')
    for start in range(train,len(history.candles)-test+1,step):
        end=start+test; bars=history.candles[start-warmup:end]
        part=History(history.symbol,'15m',bars[0].open_ms,bars[-1].open_ms+900000,
                     history.observed_ms,bars,0,0)
        yield dict(train_start_ms=history.candles[start-train].open_ms,
                   train_end_ms=history.candles[start].open_ms,
                   test_start_ms=history.candles[start].open_ms,test_end_ms=part.end_ms),part


def phase1(metrics, boot):
    def greater(k,v): return metrics.get(k) is not None and metrics[k]>v
    return (metrics['net_return']>0 and metrics['closed_trades']>=30
        and greater('win_rate',.45) and greater('profit_factor',1.3)
        and metrics['max_drawdown']<.15 and greater('sharpe_zero_rf',.5)
        and boot['robust'])


def evaluate(history, seed=1729):
    cfg=replace(load_settings({}),mode='backtest',symbol=history.symbol,timeframe=history.timeframe,
                max_order_notional=Decimal('5'))
    parts=list(rolling(history,cfg))
    if len(parts)<3: raise ValueError('AT_LEAST_THREE_ROLLING_CYCLES_REQUIRED')
    rows=[]; inherited=[]
    for i,(bounds,part) in enumerate(parts):
        for name,fee,slip in SCENARIOS:
            m=run(part,replace(cfg,fee_rate=Decimal(fee),slippage_rate=Decimal(slip)))
            b=bootstrap(m.pop('trades'),m['capital'],seed+i)
            m.pop('equity_curve'); inherited=m['limitations']
            rows.append(dict(**bounds,scenario=name,fee_rate=fee,slippage_rate=slip,
                bootstrap=b,passes_phase1_window=phase1(m,b) if name=='base' else False,
                **m,execution_authorized=False))
    base=[r for r in rows if r['scenario']=='base']
    passed=sum(r['passes_phase1_window'] for r in base)>=3
    return dict(symbol=history.symbol,windows=rows,approved=False,execution_authorized=False,
                settings={k:str(v) for k,v in asdict(cfg).items()},
                approved_phase1=passed,phase1_passing_windows=sum(r['passes_phase1_window'] for r in base),
                limitations=inherited+[
                'Walk-forward em amostra única por par; não substituir aprovação independente.',
                'Fixed settings: training is context only, not parameter fitting.',
                'Window lengths approximate 6/2/1 months using bar counts, not calendar months.',
                'OOS windows overlap; do not count them as independent or compound their returns.',
                'IID cashflow bootstrap ignores serial dependence, position sizing changes and risk halts.',
                'No-cost scenario is an unrealizable counterfactual.',
                'Phase1 is only a research screen: 30+ trades required per passing window; no broker approval.',
                'Phase2: separate paper session, 30+ trades, mean score >=70, no drawdown halt.',
                'Phase3: 2-4 weeks of separate Testnet; never automatically started.'])


def main():
    p=argparse.ArgumentParser(description='Rolling OOS + bootstrap; offline, sem execução.')
    p.add_argument('--pairs',nargs='+',required=True);p.add_argument('--timeframe',choices=['15m'],default='15m')
    p.add_argument('--csv-dir',type=Path,required=True);p.add_argument('--seed',type=int,default=1729)
    args=p.parse_args(); wanted=[s if '/' in s else s[:-4]+'/USDT' for s in args.pairs]
    histories={}; paths={}
    for path in sorted(args.csv_dir.glob('*.csv')):
        h=load_history(path)
        if h.symbol in wanted and h.timeframe==args.timeframe:
            if h.symbol in histories: p.error('Mais de um CSV por par; use diretório sem ambiguidade.')
            histories[h.symbol]=h;paths[h.symbol]=path
    if len(set(wanted))!=len(wanted) or set(histories)!=set(wanted):p.error('CSV de cada par necessário, sem duplicados.')
    results=[]
    for symbol in wanted:
        row=evaluate(histories[symbol],args.seed)
        row['csv_sha256']=hashlib.sha256(paths[symbol].read_bytes()).hexdigest();results.append(row)
    report=dict(pipeline_version='rolling-fixed-1',run_id=uuid.uuid4().hex,
        timestamp_utc=datetime.now(timezone.utc).isoformat(),pairs_tested=wanted,seed=args.seed,
        per_pair=results,approved=False,execution_authorized=False,
        aggregate=dict(overall_approved=False,phase1_screen_passed=all(r['approved_phase1'] for r in results),
            blocking_reasons=['Independent validation, separate paper and Testnet remain mandatory.']))
    report['source_hashes']={name:hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
        for name in ('validation.py','backtest.py','strategy.py','data.py','config.py')}
    folder=Path(__file__).resolve().parent.parent/'reports/local/validation';folder.mkdir(parents=True,exist_ok=True)
    path=folder/(report['run_id']+'.json')
    with path.open('x',encoding='utf-8') as stream:json.dump(report,stream,indent=2,allow_nan=False)
    print(json.dumps(dict(path=str(path),approved=False,phase1=[r['approved_phase1'] for r in results])))


if __name__=='__main__':main()
