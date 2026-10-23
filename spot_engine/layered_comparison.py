"""Fixed-rule exploratory comparison, never approval or portfolio simulation."""
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


def compare(history,count=4):
    cfg=replace(load_settings({'TRADING_TIMEFRAME':history.timeframe}),mode='backtest',
                symbol=history.symbol,max_order_notional=Decimal('6'))
    rows=[]
    for start,end,part in windows(history,cfg,count):
        mask=[row['candidate']=='RESEARCH_BUY' for row in series(part,cfg)]
        for scenario,multiplier in (('base',1),('double_costs',2)):
            costs=replace(cfg,fee_rate=cfg.fee_rate*multiplier,slippage_rate=cfg.slippage_rate*multiplier)
            for name,entry_mask in (('ema_atr',None),('layered_v1',mask)):
                metrics=run(part,costs,entry_mask=entry_mask)
                metrics.pop('trades');metrics.pop('equity_curve')
                rows.append(dict(strategy=name,scenario=scenario,start_ms=start,end_ms=end,**metrics))
    return dict(approved=False,execution_authorized=False,scope='FIXED_RULE_SINGLE_PAIR_COMPARISON',
                symbol=history.symbol,timeframe=history.timeframe,evaluated_variants=4,
                source_start_ms=history.start_ms,source_end_ms=history.end_ms,
                two_year_horizon=history.end_ms-history.start_ms>=int(2*365.25*86400000),
                settings={k:str(v) for k,v in asdict(cfg).items()},rows=rows,
                limitations=['Not a six-pair shared-wallet test; one independent 20-USDT experiment per window.',
                    'Fixed parameters, no optimization, no independent unseen holdout or walk-forward fitting.',
                    'Previously inspected history may be contaminated by research selection.',
                    'No historical exchange filters, order book, limit queue or partial-fill reconstruction.',
                    'Entries at next open; stops/targets use candle assumptions. Does not reproduce active LIMIT fills.',
                    'Report includes losing and zero-trade windows; never grants approval.'])


def main():
    import argparse
    parser=argparse.ArgumentParser(description='Comparação offline EMA vs. cinco camadas; sem ordens.')
    parser.add_argument('--csv',type=Path,required=True)
    parser.add_argument('--windows',type=int,default=4)
    args=parser.parse_args()
    result=compare(load_history(args.csv),args.windows)
    result['csv_sha256']=hashlib.sha256(args.csv.read_bytes()).hexdigest()
    result['source_hashes']={n:hashlib.sha256(Path(__file__).with_name(n).read_bytes()).hexdigest()
         for n in ('config.py','strategy.py','data.py','backtest.py','layered_research.py','layered_comparison.py','temporal_validation.py')}
    folder=Path(__file__).resolve().parent.parent/'reports/local/layered-comparison';folder.mkdir(parents=True,exist_ok=True)
    path=folder/(uuid.uuid4().hex+'.json')
    with path.open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=True,allow_nan=False,indent=2)
    for row in result['rows']:
        print(f"{row['strategy']} {row['scenario']} retorno={row['net_return']:.2%} buy&hold={row['buy_hold_return']:.2%} ciclos={row['closed_trades']}")
    print('EXPLORATÓRIO, SEM APROVAÇÃO. Relatório: '+str(path))


if __name__=='__main__':main()
