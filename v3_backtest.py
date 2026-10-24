"""V3 candle-model diagnostic: causal signals + sizing + three-part exits.

Requires explicitly supplied filter assumptions. Today's filters projected
backward are NOT historical execution data or an independent validation set.
Never authorizes execution or touches the running observer/portfolio.
"""
import argparse
from collections import Counter
from dataclasses import asdict, replace
from decimal import Decimal as D
import hashlib
import json
import math
from pathlib import Path
import statistics
import time
import uuid
from spot_engine.data import load_history
from spot_engine.execution import floor
from spot_engine.risk import Rules, amount, decimal_policy
from spot_engine.main import save
from spot_engine.v3_position_plan import Budget
from v3_engine.context import MultiTimeframeContext
from v3_engine.strategies import evaluate
from v3_engine.risk_v3 import plan_entry
from v3_engine.risk_state import assess
from v3_engine.position import open_position, advance
from v3_engine.engine_v3 import identity


def rules_from_snapshot(snapshot,symbol):
    if snapshot.get('scope')!='PUBLIC_FILTER_FEASIBILITY_NOT_BACKTEST':raise ValueError('FILTER_PROVENANCE_REQUIRED')
    rows=[r for r in snapshot.get('pairs',[]) if r.get('symbol')==symbol and r.get('status')=='OK']
    if len(rows)!=1:raise ValueError('ONE_FILTER_SNAPSHOT_PER_SYMBOL_REQUIRED')
    raw=rows[0]['normalized_rules']
    values={k:v if k in ('symbol','observed_ms') else D(v) for k,v in raw.items()}
    return Rules(**values)


@decimal_policy
def run(history,rules,*,capital=D('20'),fee=D('.001'),slip=D('.001')):
    if history.timeframe!='15m' or history.symbol!=rules.symbol:raise ValueError('MATCHING_15M_HISTORY_REQUIRED')
    if not history.candles or history.candles[-1].open_ms+900000>history.observed_ms:raise ValueError('CLOSED_HISTORY_REQUIRED')
    amount(capital,positive=True);amount(fee);amount(slip)
    if fee>D('.01') or slip>D('.01'):raise ValueError('COST_LIMIT')
    ctx=MultiTimeframeContext(history.symbol);prior=None;position=None;risk=None
    cash=capital;fees=D(0);peak=capital;max_dd=D(0);previous=capital
    ready_bars=0;candidates=0;rejections=Counter();trades=[];events=[];returns=[]
    first_open=None;last=None
    for candle in history.candles:
        if prior and prior['ready']:
            ready_bars+=1;first_open=first_open or candle.open;last=candle
            # Use only the previous CLOSED state for entry or dynamic stop ATR.
            now=candle.open_ms;atr=D(str(prior['atr14']));signal=evaluate(prior)
            marked=D(0) if position is None else D(position['remaining'])*floor(D(str(candle.open))*(1-slip),rules.price_tick)*(1-fee)
            assessment=assess(risk,equity=cash+marked,now_ms=now);risk=assessment['state']
            if position is None and signal.action=='ENTER':
                candidates+=1
                if not assessment['can_enter']:rejections[assessment['reason']]+=1
                else:
                    equity=cash
                    budget=Budget(equity,cash,D(0),D(0),
                        max(D(0),equity-D(risk['day_base'])*D('.97')),
                        max(D(0),equity-D(risk['peak'])*D('.90')))
                    # Counterfactual constant filter scenario, NOT a claim that
                    # today's metadata was observable on this historical bar.
                    scenario_rules=replace(rules,observed_ms=now)
                    plan=plan_entry(scenario_rules,budget,ask=D(str(candle.open)),atr=atr,
                        score=signal.score,now_ms=now,quote_ms=now,fee=fee,slip=slip)
                    if not plan['valid_research_plan']:rejections[plan['reason']]+=1
                    else:
                        position=open_position(plan,now,fee,slip)
                        cash-=D(plan['estimated_cost']);fees+=D(plan['quantity'])*D(plan['entry'])*fee
            if position:
                position,exits=advance(position,candle,as_of_ms=now+900000,atr=atr,tick=rules.price_tick,
                    risk_halted=not assessment['can_enter'],
                    opposite=prior['ema'][9]<prior['ema'][21] or prior['regime']=='CRISIS')
                for e in exits:
                    q=D(e['quantity']);price=D(e['assumed_fill'])
                    cash+=q*price*(1-fee);fees+=q*price*fee
                    events.append(dict(timestamp_ms=now+900000,**e))
                if position['closed']:
                    pnl=D(position['realized'])
                    trades.append(dict(entry_ms=position['opened_ms'],exit_ms=now+900000,
                        pnl=str(pnl),execution_authorized=False))
                    assessment=assess(risk,equity=cash,now_ms=now+900000,closed_trade_pnl=pnl)
                    risk=assessment['state'];position=None
            marked=D(0) if position is None else D(position['remaining'])*floor(D(str(candle.close))*(1-slip),rules.price_tick)*(1-fee)
            equity=cash+marked;peak=max(peak,equity);max_dd=max(max_dd,1-equity/peak)
            returns.append(float(equity/previous-1));previous=equity
            risk=assess(risk,equity=equity,now_ms=now+900000)['state']
        prior=ctx.update_15m(candle,candle.open_ms+900000)
    if not ready_bars:raise ValueError('INSUFFICIENT_V3_HIGHER_TIMEFRAME_WARMUP')
    if position:
        # Explicit hypothetical final liquidation, never an open gain counted as
        # a completed profitable cycle. No extra future candle is invented.
        q=D(position['remaining']);p=floor(D(str(last.close))*(1-slip),rules.price_tick)
        proceeds=q*p*(1-fee);pnl=D(position['realized'])+proceeds-D(position['remaining_cost'])
        cash+=proceeds;fees+=q*p*fee
        events.append(dict(reason='END_LIQUIDATION',quantity=str(q),assumed_fill=str(p),
            pnl=str(proceeds-D(position['remaining_cost'])),timestamp_ms=last.open_ms+900000,execution_authorized=False))
        trades.append(dict(entry_ms=position['opened_ms'],exit_ms=last.open_ms+900000,pnl=str(pnl),execution_authorized=False))
    net=sum((D(t['pnl']) for t in trades),D(0))
    if abs(cash-capital-net)>D('1e-60'):raise ValueError('RESEARCH_CASHFLOW_MISMATCH')
    winners=sum((D(t['pnl']) for t in trades if D(t['pnl'])>0),D(0))
    losers=-sum((D(t['pnl']) for t in trades if D(t['pnl'])<0),D(0))
    sigma=statistics.stdev(returns) if len(returns)>1 else 0.
    return dict(scope='V3_COUNTERFACTUAL_CONSTANT_FILTER_CANDLE_MODEL',symbol=history.symbol,
        capital=str(capital),final_equity=str(cash),net_pnl=str(net),net_return=float(cash/capital-1),
        fees=str(fees),max_drawdown=float(max_dd),ready_bars=ready_bars,candidate_count=candidates,
        rejected_candidates=dict(rejections),closed_trades=len(trades),trades=trades,exit_events=events,
        win_rate=sum(D(t['pnl'])>0 for t in trades)/len(trades) if trades else None,
        profit_factor=float(winners/losers) if losers else None,
        sharpe_zero_rf=statistics.mean(returns)/sigma*math.sqrt(365.25*96) if sigma else None,
        buy_hold_return=float(D(str(last.close))*(1-slip)*(1-fee)/(D(str(first_open))*(1+slip)*(1+fee))-1),
        filter_assumptions={k:str(v) if isinstance(v,D) else v for k,v in asdict(rules).items()},
        fee_rate=str(fee),slippage_rate=str(slip),approved=False,execution_authorized=False,
        verdict='NO_TRADES_NOT_VALIDATED' if not trades else 'EXPLORATORY_ONLY_NOT_VALIDATED',
        limitations=['Constant present-day filters projected backward: counterfactual, not historical execution validation.',
            'Prior closed signal enters at next open plus slippage; no spread/orderbook/queue/latency reconstruction.',
            'Stop first in intrabar ambiguity; new trailing/breakeven applies next candle.',
            'Synthetic market exits may not pass future exchange filters or liquidity requirements.',
            'Risk limits are observed at opens and closes, not continuous intrabar equity.',
            'One pair and previously inspected history; no independent OOS or multi-pair portfolio claim.',
            'Zero trades is not evidence of profitability, low risk or strategy validation.',
            'Score is not a probability; external macro/funding/flow filters remain unconnected.'])


def main():
    p=argparse.ArgumentParser(description='Diagnóstico V3 offline, filtros constantes explicitamente contrafactuais.')
    p.add_argument('--csv',type=Path,required=True);p.add_argument('--filter-snapshot',type=Path,required=True)
    p.add_argument('--data-dir',type=Path,default=Path(__file__).resolve().parent)
    args=p.parse_args();history=load_history(args.csv)
    snapshot=json.loads(args.filter_snapshot.read_text(encoding='utf-8'))
    result=run(history,rules_from_snapshot(snapshot,history.symbol))
    result.update(run_id=uuid.uuid4().hex,csv_sha256=hashlib.sha256(args.csv.read_bytes()).hexdigest(),
        filter_snapshot_sha256=hashlib.sha256(args.filter_snapshot.read_bytes()).hexdigest(),
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),v3_identity=identity())
    result['updated_ms']=int(time.time()*1000)
    folder=args.data_dir/'reports/local/v3-backtest';folder.mkdir(parents=True,exist_ok=True)
    path=folder/(result['run_id']+'.json')
    with path.open('x',encoding='utf-8') as output:json.dump(result,output,indent=2,allow_nan=False)
    save(folder/'latest.json',{k:v for k,v in result.items() if k not in ('trades','exit_events')})
    print(json.dumps({k:result[k] for k in ('candidate_count','closed_trades','rejected_candidates','net_return','verdict','approved')}))
    print(str(path))


if __name__=='__main__':main()
