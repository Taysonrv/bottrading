"""One pre-fixed BTC/1h hypothesis for 20 fictitious USDT; offline only.

EMA20/50 cross above EMA200, existing ATR filter, one 2% stop/5% target,
maximum 48 hours. No partial exits, AI score or parameter search.
"""
import argparse
from collections import Counter
from dataclasses import asdict,dataclass,replace
from decimal import Decimal as D
import hashlib
import json
from pathlib import Path
import statistics
import math
import time
import uuid
from spot_engine.config import load_settings
from spot_engine.data import Candle,History,PublicBinance,load_history,retry
from spot_engine.main import normalized_rules,save
from spot_engine.risk import Rules,amount,decimal_policy
from spot_engine.execution import floor,ceil
from spot_engine.strategy import analyze
from spot_engine.v3_position_plan import filters


@dataclass(frozen=True)
class Policy:
    capital:D=D('20')
    budget:D=D('6')
    risk:D=D('.01')
    stop:D=D('.02')
    target:D=D('.05')
    daily:D=D('.03')
    drawdown:D=D('.10')
    max_bars:int=48

    def __post_init__(self):
        for name in ('capital','budget','risk','stop','target','daily','drawdown'):
            amount(getattr(self,name),positive=True)
        if type(self.max_bars) is not int:raise ValueError('INVALID_TIME_STOP')
        # Fixed experiment: replacing parameters creates a different hypothesis.
        if (self.capital,self.budget,self.risk,self.stop,self.target,self.daily,self.drawdown,self.max_bars)!=(D(20),D(6),D('.01'),D('.02'),D('.05'),D('.03'),D('.1'),48):
            raise ValueError('FIXED_EXPERIMENT_PARAMETERS')


def hourly(history):
    """Aggregate complete UTC groups of four, reject gaps before aggregation."""
    if history.timeframe!='15m' or not history.candles:raise ValueError('15M_SOURCE_REQUIRED')
    rows=[];group=[];last=None
    for c in history.candles:
        if c.open_ms%900000 or c.open_ms+900000>history.observed_ms:
            raise ValueError('SOURCE_NOT_CLOSED_OR_ALIGNED')
        if last is not None and c.open_ms!=last+900000:raise ValueError('SOURCE_GAP')
        last=c.open_ms
        if c.open_ms%3600000==0:group=[c]
        elif group:group.append(c)
        if len(group)==4:
            rows.append(Candle(group[0].open_ms,group[0].open,max(b.high for b in group),
                min(b.low for b in group),group[-1].close,math.fsum(b.volume for b in group)))
            group=[]
    if not rows:raise ValueError('NO_COMPLETE_UTC_HOUR')
    return History(history.symbol,'1h',rows[0].open_ms,rows[-1].open_ms+3600000,
        history.observed_ms,tuple(rows),0,0)


@decimal_policy
def proposal(rules,cash,equity,ask,remaining,*,fee=D('.001'),slip=D('.001')):
    for v in (cash,equity,ask):amount(v,positive=True)
    for v in (remaining,fee,slip):amount(v)
    if fee>D('.01') or slip>D('.01'):raise ValueError('COST_LIMIT')
    p=Policy();entry=ceil(ask*(1+slip),rules.price_tick)
    stop=floor(entry*(1-p.stop),rules.price_tick);target=ceil(entry*(1+p.target),rules.price_tick)
    stop_fill=floor(stop*(1-slip),rules.price_tick);target_fill=floor(target*(1-slip),rules.price_tick)
    if not 0<stop_fill<entry<target:return dict(reason='PRICE_FILTER',approved=False)
    unit_cost=entry*(1+fee);unit_loss=unit_cost-stop_fill*(1-fee)
    available=min(cash,p.budget,equity*D('.4'))
    risk_budget=min(equity*p.risk,remaining)
    quantity=floor(min(available/unit_cost,risk_budget/unit_loss,rules.max_qty,rules.max_notional/entry),rules.qty_step)
    if not all(filters(rules,quantity,v) for v in (entry,stop_fill,target_fill)):
        return dict(reason='MINIMUM_LOT_OR_PROTECTION_FILTER',approved=False)
    cost=quantity*unit_cost;loss=quantity*unit_loss;rr=(target_fill*(1-fee)-unit_cost)/unit_loss
    if rr<D('1.5'):return dict(reason='NET_RR_TOO_LOW',approved=False)
    if cost>available or loss>risk_budget:raise ValueError('ROUNDING_BUDGET_ERROR')
    return dict(reason='HYPOTHETICAL_PLAN',entry=str(entry),stop=str(stop),target=str(target),
        quantity=str(quantity),cost=str(cost),estimated_stop_loss=str(loss),net_rr=str(rr),
        approved=False,execution_authorized=False)


@decimal_policy
def run(history,rules,*,fee=D('.001'),slip=D('.001')):
    if history.timeframe!='1h' or history.symbol!=rules.symbol:raise ValueError('MATCHING_HOURLY_DATA_REQUIRED')
    p=Policy();cfg=replace(load_settings({}),mode='backtest',symbol=history.symbol,timeframe='1h',
        capital=p.capital,max_order_notional=p.budget,stop_loss_fraction=p.stop,take_profit_fraction=p.target,
        ema_fast=20,ema_slow=50,ema_trend=200,atr_period=14,
        atr_min_fraction=D('.001'),atr_max_fraction=D('.05'),risk_per_trade=p.risk,
        daily_loss_limit=p.daily,max_drawdown=p.drawdown,max_positions=1)
    signals=analyze(history,cfg);warmup=600
    if len(signals)<=warmup:raise ValueError('INSUFFICIENT_WARMUP')
    for v in (fee,slip):amount(v)
    if fee>D('.01') or slip>D('.01'):raise ValueError('COST_LIMIT')
    cash=peak=previous=day_base=p.capital;day=None;daily_halt=dd_halt=False
    pos=None;trades=[];returns=[];fees=D(0);max_dd=D(0);candidates=0;rejects=Counter();exit_blocks=0
    def mark(price):
        return cash+(D(pos['quantity'])*floor(price*(1-slip),rules.price_tick)*(1-fee) if pos else D(0))
    def sell(price,reason,timestamp):
        nonlocal cash,pos,fees,exit_blocks
        q=D(pos['quantity'])
        if not filters(rules,q,price):exit_blocks+=1;return False
        charge=q*price*fee;proceeds=q*price-charge;pnl=proceeds-D(pos['cost'])
        cash+=proceeds;fees+=charge
        trades.append(dict(entry_ms=pos['opened_ms'],exit_ms=timestamp,entry=pos['entry'],
            exit=str(price),quantity=str(q),pnl=str(pnl),reason=reason,approved=False))
        pos=None;return True
    bars=history.candles
    for i in range(warmup,len(bars)):
        b=bars[i];o=D(str(b.open));c=D(str(b.close));had_position=pos is not None
        equity=mark(o);today=b.open_ms//86400000
        if day!=today:day=today;day_base=equity;daily_halt=False
        peak=max(peak,equity);daily_halt|=equity<=day_base*(1-p.daily);dd_halt|=equity<=peak*(1-p.drawdown)
        if had_position:
            pos['bars']+=1;stop=D(pos['stop']);target=D(pos['target'])
            if o<=stop:sell(floor(o*(1-slip),rules.price_tick),'STOP_GAP',b.open_ms)
            elif daily_halt or dd_halt:sell(floor(o*(1-slip),rules.price_tick),'RISK_EXIT',b.open_ms)
        elif signals[i-1].action=='ENTER_LONG':
            candidates+=1
            if daily_halt or dd_halt:rejects['RISK_HALT']+=1
            else:
                remaining=max(D(0),min(equity-day_base*(1-p.daily),equity-peak*(1-p.drawdown)))
                plan=proposal(rules,cash,equity,o,remaining,fee=fee,slip=slip)
                if plan['reason']!='HYPOTHETICAL_PLAN':rejects[plan['reason']]+=1
                else:
                    pos=dict(plan,opened_ms=b.open_ms,bars=1)
                    cash-=D(plan['cost']);fees+=D(plan['quantity'])*D(plan['entry'])*fee
        if pos:
            stop=D(pos['stop']);target=D(pos['target'])
            if D(str(b.low))<=stop:
                sell(floor(min(o,stop)*(1-slip),rules.price_tick),'STOP',b.open_ms+3600000)
            elif D(str(b.high))>=target:
                sell(floor(target*(1-slip),rules.price_tick),'TARGET',b.open_ms+3600000)
            elif pos['bars']>=p.max_bars:
                sell(floor(c*(1-slip),rules.price_tick),'TIME_STOP',b.open_ms+3600000)
        equity=mark(c);peak=max(peak,equity);max_dd=max(max_dd,1-equity/peak)
        daily_halt|=equity<=day_base*(1-p.daily);dd_halt|=max_dd>=p.drawdown
        returns.append(float(equity/previous-1));previous=equity
    if pos:sell(floor(D(str(bars[-1].close))*(1-slip),rules.price_tick),'END_LIQUIDATION',history.end_ms)
    equity=mark(D(str(bars[-1].close)));net=sum((D(t['pnl']) for t in trades),D(0))
    book_cost=D(pos['cost']) if pos else D(0)
    if abs(cash+book_cost-p.capital-net)>D('1e-60'):raise ValueError('CASHFLOW_MISMATCH')
    wins=sum((D(t['pnl']) for t in trades if D(t['pnl'])>0),D(0));losses=-sum((D(t['pnl']) for t in trades if D(t['pnl'])<0),D(0))
    sigma=statistics.stdev(returns) if len(returns)>1 else 0.
    return dict(symbol=history.symbol,timeframe='1h',capital=str(p.capital),final_equity=str(equity),cash=str(cash),
        net_return=float(equity/p.capital-1),net_realized=str(net),fees=str(fees),max_drawdown=float(max_dd),
        closed_trades=len(trades),entry_candidates=candidates,rejected_candidates=dict(rejects),blocked_exit_attempts=exit_blocks,
        position_open=bool(pos),drawdown_latched=dd_halt,
        win_rate=sum(D(t['pnl'])>0 for t in trades)/len(trades) if trades else None,
        profit_factor=float(wins/losses) if losses else None,
        sharpe_zero_rf=statistics.mean(returns)/sigma*math.sqrt(365.25*24) if sigma else None,
        buy_hold_return=float(D(str(bars[-1].close))*(1-slip)*(1-fee)/(D(str(bars[warmup].open))*(1+slip)*(1+fee))-1),
        exit_reasons=dict(Counter(t['reason'] for t in trades)),trades=trades,
        fee_rate=str(fee),slippage_rate=str(slip),approved=False,execution_authorized=False)


def evaluate(history,rules):
    hours=hourly(history);warmup=600;remaining=len(hours.candles)-warmup
    if remaining<4*warmup:raise ValueError('FOUR_SUBSTANTIAL_WINDOWS_REQUIRED')
    scenarios=[]
    for name,multiplier in [('base',1),('double_costs',2)]:
        fee=slip=D('.001')*multiplier
        full=run(hours,rules,fee=fee,slip=slip);full.pop('trades')
        windows=[]
        for i in range(4):
            start=warmup+remaining*i//4;end=warmup+remaining*(i+1)//4
            bars=hours.candles[start-warmup:end]
            part=History(hours.symbol,'1h',bars[0].open_ms,bars[-1].open_ms+3600000,hours.observed_ms,bars,0,0)
            row=run(part,rules,fee=fee,slip=slip);row.pop('trades')
            windows.append(dict(start_ms=hours.candles[start].open_ms,end_ms=part.end_ms,**row))
        scenarios.append(dict(name=name,continuous=full,windows=windows))
    base=scenarios[0];positive=sum(w['net_return']>0 for w in base['windows'])
    return dict(scope='SINGLE_EXIT_FIXED_HYPOTHESIS_RESEARCH',updated_ms=int(time.time()*1000),
        symbol=hours.symbol,timeframe='1h',source_bars=len(history.candles),hourly_bars=len(hours.candles),
        policy={k:str(v) for k,v in asdict(Policy()).items()},parameter_variants=1,cost_scenarios=2,
        filter_assumptions={k:str(v) if isinstance(v,D) else v for k,v in asdict(rules).items()},
        scenarios=scenarios,positive_base_windows=positive,
        verdict='REJECTED' if base['continuous']['net_return']<=0 or positive<3 else 'PRELIMINARY_ONLY_NOT_VALIDATED',
        approved=False,execution_authorized=False,
        limitations=['Previously inspected BTC sample; time blocks are not independent untouched OOS.',
            'Current LIMIT filters held constant in the past: counterfactual feasibility, not historical exchange validation.',
            'No spread, queue, latency or displayed liquidity reconstruction; fills are hypothetical market exits.',
            'Only full UTC hours from complete consecutive 15m bars; first/last incomplete hour omitted.',
            'Signals use preceding closed hour, fill next open; stop first on intrabar stop/target ambiguity.',
            'No EMA opposite-signal exit: 2% stop, 5% target or 48-hour maximum hold, full quantity only.',
            'Each window resets 20 USDT and risk; do not sum or compound independent window returns.',
            'Budget6 USDT is a new offline policy, not a change to the active portfolio or V3.',
            'Daily/DD risk sees opens and closes; gaps can exceed estimated stop loss.',
            'Filter-blocked exits retain inventory and are reported; no automatic liquidation guarantee.'])


def main():
    p=argparse.ArgumentParser(description='Uma hipótese Spot/1h/saída única/20 USDT, somente pesquisa.')
    p.add_argument('--csv',type=Path,required=True);p.add_argument('--data-dir',type=Path,default=Path(__file__).resolve().parent)
    args=p.parse_args();history=load_history(args.csv)
    if history.symbol!='BTC/USDT':p.error('Hipótese pré-fixada BTC/USDT; outros pares exigem novo estudo.')
    client=PublicBinance();info=retry(lambda:client.fetch_symbol_info(history.symbol));now=int(retry(client.fetch_time))
    rules=normalized_rules(info,history.symbol,now)
    report=evaluate(history,rules)
    report.update(run_id=uuid.uuid4().hex,csv_sha256=hashlib.sha256(args.csv.read_bytes()).hexdigest(),
        source_hashes={name:hashlib.sha256((Path(__file__).parent/name).read_bytes()).hexdigest() for name in
            ('single_exit_research.py','spot_engine/strategy.py','spot_engine/config.py','spot_engine/risk.py')})
    folder=args.data_dir/'reports/local/single-exit-research';folder.mkdir(parents=True,exist_ok=True)
    with (folder/(report['run_id']+'.json')).open('x',encoding='utf-8') as output:json.dump(report,output,indent=2,allow_nan=False)
    save(folder/'latest.json',report)
    for s in report['scenarios']:
        print(json.dumps(dict(scenario=s['name'],continuous=s['continuous'],windows=[dict(return_=w['net_return'],trades=w['closed_trades']) for w in s['windows']]),allow_nan=False))
    print(report['verdict'])


if __name__=='__main__':main()
