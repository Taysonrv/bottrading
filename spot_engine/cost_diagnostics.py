"""Controlled cost-sensitivity audit, not a causal additive attribution."""
from collections import Counter
from dataclasses import asdict,replace
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import uuid
from .backtest import run
from .config import load_settings
from .data import load_history
from .layered_research import series
from .temporal_validation import windows


def evaluate(history,count=4):
    cfg=replace(load_settings({'TRADING_TIMEFRAME':history.timeframe}),mode='backtest',
                symbol=history.symbol,max_order_notional=Decimal('6'))
    scenarios=(('no_costs',Decimal(0),Decimal(0)),
               ('fees_only',cfg.fee_rate,Decimal(0)),
               ('slippage_only',Decimal(0),cfg.slippage_rate),
               ('base',cfg.fee_rate,cfg.slippage_rate))
    rows=[]
    for start,end,part in windows(history,cfg,count):
        mask=[r['candidate']=='RESEARCH_BUY' for r in series(part,cfg)]
        for scenario,fee,slip in scenarios:
            costs=replace(cfg,fee_rate=fee,slippage_rate=slip)
            for name,entry_mask in (('ema_atr',None),('layered_v1',mask)):
                metrics=run(part,costs,entry_mask=entry_mask)
                trades=metrics.pop('trades');metrics.pop('equity_curve')
                reasons=dict(Counter(t['reason'] for t in trades))
                rows.append(dict(strategy=name,scenario=scenario,start_ms=start,end_ms=end,
                    fee_rate=str(fee),slippage_rate=str(slip),exit_reasons=reasons,
                    mean_closed_trade_pnl=sum(t['pnl'] for t in trades)/len(trades) if trades else None,
                    **metrics))
    return dict(approved=False,execution_authorized=False,scope='EXPLORATORY_COST_SENSITIVITY',
                symbol=history.symbol,timeframe=history.timeframe,evaluated_configurations=8,
                source_start_ms=history.start_ms,source_end_ms=history.end_ms,rows=rows,
                settings={k:str(v) for k,v in asdict(cfg).items()},
                caveats=['No-cost case is an unrealizable diagnostic baseline, not an executable strategy.',
                  'Changing costs can change entries, stops, quantities and risk halts; return differences are not additive attribution.',
                  'Four cost scenarios times two fixed rules; additional to prior research, not independent unseen validation.',
                  'One pair; separate initial 20 USDT per window. Do not sum or compound window returns.',
                  'All candle-model limitations remain: no historical filters, book, spread or LIMIT queue.',
                  'Exit-reason counts describe this simulator, not the active paper ledger.'])


def main():
    import argparse
    parser=argparse.ArgumentParser(description='Diagnóstico de custos offline, sem ordens ou aprovação.')
    parser.add_argument('--csv',type=Path,required=True)
    parser.add_argument('--windows',type=int,default=4)
    args=parser.parse_args()
    result=evaluate(load_history(args.csv),args.windows)
    result['csv_sha256']=hashlib.sha256(args.csv.read_bytes()).hexdigest()
    result['source_hashes']={n:hashlib.sha256(Path(__file__).with_name(n).read_bytes()).hexdigest()
        for n in ('config.py','strategy.py','backtest.py','data.py','layered_research.py','temporal_validation.py','cost_diagnostics.py')}
    folder=Path(__file__).resolve().parent.parent/'reports/local/cost-diagnostics';folder.mkdir(parents=True,exist_ok=True)
    path=folder/(uuid.uuid4().hex+'.json')
    with path.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2,allow_nan=False)
    for row in result['rows']:
        print(f"{row['strategy']} {row['scenario']} retorno={row['net_return']:.2%}; ciclos={row['closed_trades']}; saídas={row['exit_reasons']}")
    print('SEM APROVAÇÃO. Relatório: '+str(path))


if __name__=='__main__':main()
