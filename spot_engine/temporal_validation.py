"""Fixed-rule chronological audit. Previously inspected data is not fresh holdout.

Each non-overlapping evaluation window starts with hypothetical capital and
preceding warmup bars. Results are separate experiments, never one equity curve.
"""
from dataclasses import asdict, replace
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import uuid
from .backtest import run
from .config import load_settings
from .data import History, interval, load_history


def windows(history, settings, count=4):
    if type(count) is not int or not 2 <= count <= 12:
        raise ValueError('Use de 2 a 12 janelas.')
    warmup=max(3*settings.ema_trend,settings.atr_period+1)
    remaining=len(history.candles)-warmup
    if remaining<count*warmup:
        raise ValueError('Cada janela exige ao menos um aquecimento de duração avaliada.')
    if history.symbol!=settings.symbol or history.timeframe!=settings.timeframe:
        raise ValueError('Histórico incompatível.')
    step=interval(settings.symbol,settings.timeframe)
    result=[]
    for i in range(count):
        start=warmup+remaining*i//count
        end=warmup+remaining*(i+1)//count
        bars=history.candles[start-warmup:end]
        part=History(history.symbol,history.timeframe,bars[0].open_ms,
                     bars[-1].open_ms+step,history.observed_ms,bars,0,0)
        result.append((history.candles[start].open_ms,part.end_ms,part))
    return result


def evaluate(history, settings, count=4):
    parts=windows(history,settings,count)
    scenarios=[]
    for name,multiplier in [('base',1),('double_costs',2)]:
        cfg=replace(settings,fee_rate=settings.fee_rate*multiplier,
                    slippage_rate=settings.slippage_rate*multiplier)
        rows=[]
        for start,end,part in parts:
            metrics=run(part,cfg)
            metrics.pop('trades');metrics.pop('equity_curve')
            rows.append(dict(start_ms=start,end_ms=end,**metrics))
        scenarios.append(dict(name=name,fee_rate=str(cfg.fee_rate),slippage_rate=str(cfg.slippage_rate),
                              positive_windows=sum(r['net_return']>0 for r in rows),
                              beat_buy_hold_windows=sum(r['net_return']>r['buy_hold_return'] for r in rows),
                              windows=rows))
    return dict(approved=False,scope='CHRONOLOGICAL_EXPLORATORY_AUDIT',
                symbol=settings.symbol,timeframe=settings.timeframe,
                evaluated_variants=2,scenarios=scenarios,
                caveats=['Fixed EMA/ATR settings; no parameter fitting or choosing the winning window.',
                         'Source history already inspected: these are not independent unseen tests.',
                         'Each window restarts hypothetical cash/risk; do not compound these returns.',
                         'Warmup precedes each window and does not generate historical fills.',
                         'All candle-model limitations apply; no live or paper engine approval.',
                         'Does not validate other pairs or timeframes, nor guarantee future profit.'])


def main():
    import argparse
    parser=argparse.ArgumentParser(description='Auditoria cronológica offline; sem ordens.')
    parser.add_argument('--csv',type=Path,required=True)
    parser.add_argument('--windows',type=int,default=4)
    args=parser.parse_args()
    history=load_history(args.csv)
    cfg=replace(load_settings({}),mode='backtest',symbol=history.symbol,
                timeframe=history.timeframe,max_order_notional=Decimal('6'))
    report=evaluate(history,cfg,args.windows)
    report['settings']={k:str(v) for k,v in asdict(cfg).items()}
    report['csv_sha256']=hashlib.sha256(args.csv.read_bytes()).hexdigest()
    report['source_hashes']={name:hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                             for name in ('config.py','strategy.py','backtest.py','temporal_validation.py')}
    folder=Path(__file__).resolve().parent.parent/'reports/local/spot-validation'
    folder.mkdir(parents=True,exist_ok=True)
    path=folder/(uuid.uuid4().hex+'.json')
    with path.open('x',encoding='utf-8') as output:
        json.dump(report,output,ensure_ascii=False,indent=2,allow_nan=False)
    for scenario in report['scenarios']:
        print(scenario['name'])
        for row in scenario['windows']:
            print(f"  retorno={row['net_return']:.2%}; buy&hold={row['buy_hold_return']:.2%}; trades={row['closed_trades']}")
    print('Sem aprovação. Relatório: '+str(path))


if __name__=='__main__':
    main()
