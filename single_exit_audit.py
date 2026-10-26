"""Reproduce a saved experiment and reconcile every hypothetical cashflow.

No strategy search, new market download, wallet access, inference or orders.
Cost attribution holds the original path, quantities and price levels fixed;
it is not a zero-cost counterfactual strategy backtest.
"""
import argparse
from collections import Counter
import csv
from dataclasses import asdict
from datetime import datetime,timezone
from decimal import Decimal as D
import hashlib
import json
from pathlib import Path
import time
import uuid
from spot_engine.risk import Rules,decimal_policy
from spot_engine.data import load_history
from spot_engine.main import save
from single_exit_research import Policy,hourly,run

ZERO=D(0)


def utc(ms):return datetime.fromtimestamp(ms/1000,timezone.utc).isoformat()


class Audit:
    def __init__(self,slip):
        self.slip=slip;self.active=None;self.rows=[];self.rejections=Counter();self.blocked=0

    @decimal_policy
    def __call__(self,event):
        kind=event['kind']
        if kind=='REJECTION':self.rejections[event['reason']]+=1;return
        if kind=='EXIT_BLOCKED':self.blocked+=1;return
        if kind=='ENTRY':
            if self.active is not None:raise ValueError('AUDIT_OVERLAPPING_POSITION')
            plan=event['plan'];self.active=dict(entry_ms=event['entry_ms'],entry=plan['entry'],
                quantity=plan['quantity'],cost=plan['cost'],stop=plan['stop'],target=plan['target'],
                entry_reference=event['reference'],entry_fee=event['fee'],
                signal_ms=event['signal_ms'],signal_atr_fraction=event['signal_atr_fraction'],
                estimated_stop_loss=plan['estimated_stop_loss'],net_rr_at_entry=plan['net_rr'],
                lowest=None,highest=None,bars=0,ambiguous_bars=0)
            return
        if self.active is None or event['entry_ms']!=self.active['entry_ms']:
            raise ValueError('AUDIT_POSITION_MISMATCH')
        a=self.active
        if kind=='RANGE':
            lo=D(event['low']);hi=D(event['high'])
            a['lowest']=lo if a['lowest'] is None else min(a['lowest'],lo)
            a['highest']=hi if a['highest'] is None else max(a['highest'],hi)
            a['bars']+=1;a['ambiguous_bars']+=int(event['ambiguous_stop_target'])
            return
        if kind!='EXIT':raise ValueError('AUDIT_EVENT_DOMAIN')
        q=D(a['quantity']);entry=D(a['entry']);exit=D(event['price'])
        er=D(a['entry_reference']);xr=D(event['reference'])
        if q!=D(event['quantity']):raise ValueError('AUDIT_NOT_FULL_EXIT')
        ef=D(a['entry_fee']);xf=D(event['fee']);fees=ef+xf
        gross=q*(exit-entry);net=D(event['pnl'])
        reference=q*(xr-er)
        entry_slip=q*er*self.slip;entry_tick=q*(entry-er*(1+self.slip))
        exit_slip=q*xr*self.slip;exit_tick=q*(xr*(1-self.slip)-exit)
        execution=entry_slip+entry_tick+exit_slip+exit_tick
        if min(entry_tick,exit_tick)<0:raise ValueError('AUDIT_ADVERSE_ROUNDING')
        if abs(gross-fees-net)>D('1e-60') or abs(reference-execution-fees-net)>D('1e-60'):
            raise ValueError('AUDIT_COST_RECONCILIATION')
        row=dict(trade_id=len(self.rows)+1,symbol='BTC/USDT',entry_ms=a['entry_ms'],exit_ms=event['time_ms'],
            entry_utc=utc(a['entry_ms']),exit_utc=utc(event['time_ms']),reason=event['reason'],
            quantity=str(q),entry=str(entry),exit=str(exit),entry_reference=str(er),exit_reference=str(xr),
            reference_price_pnl=str(reference),fill_gross_pnl=str(gross),
            entry_fee=str(ef),exit_fee=str(xf),fees=str(fees),entry_slippage=str(entry_slip),
            exit_slippage=str(exit_slip),entry_tick_impact=str(entry_tick),exit_tick_impact=str(exit_tick),
            execution_impact=str(execution),net_pnl=str(net),
            recorded_duration_hours=(event['time_ms']-a['entry_ms'])/3600000,
            full_bar_mae_bound=float(a['lowest']/entry-1) if a['lowest'] is not None else None,
            full_bar_mfe_bound=float(a['highest']/entry-1) if a['highest'] is not None else None,
            ambiguous_stop_target_bars=a['ambiguous_bars'],
            signal_ms=a['signal_ms'],signal_atr_fraction=a['signal_atr_fraction'],
            estimated_stop_loss=a['estimated_stop_loss'],net_rr_at_entry=a['net_rr_at_entry'],
            approved=False,execution_authorized=False)
        self.rows.append(row);self.active=None


@decimal_policy
def aggregate(rows):
    keys=('reference_price_pnl','fill_gross_pnl','entry_slippage','exit_slippage',
          'entry_tick_impact','exit_tick_impact','execution_impact','fees','net_pnl')
    sums={k:sum((D(r[k]) for r in rows),ZERO) for k in keys}
    if abs(sums['reference_price_pnl']-sums['execution_impact']-sums['fees']-sums['net_pnl'])>D('1e-60'):
        raise ValueError('AUDIT_AGGREGATE_MISMATCH')
    wins=[D(r['net_pnl']) for r in rows if D(r['net_pnl'])>0]
    losses=[D(r['net_pnl']) for r in rows if D(r['net_pnl'])<0]
    average_win=sum(wins,ZERO)/len(wins) if wins else None
    average_loss=-sum(losses,ZERO)/len(losses) if losses else None
    return dict(trades=len(rows),wins=len(wins),losses=len(losses),
        breakeven_trades=sum(D(r['net_pnl'])==0 for r in rows),
        win_rate=len(wins)/len(rows) if rows else None,
        average_net_win=str(average_win) if average_win is not None else None,
        average_net_loss=str(average_loss) if average_loss is not None else None,
        descriptive_breakeven_win_rate=float(average_loss/(average_win+average_loss))
            if average_win is not None and average_loss is not None else None,
        gross_fill_wins_turned_net_losses=sum(D(r['fill_gross_pnl'])>0 and D(r['net_pnl'])<0 for r in rows),
        reference_wins_turned_net_losses=sum(D(r['reference_price_pnl'])>0 and D(r['net_pnl'])<0 for r in rows),
        mean_recorded_duration_hours=sum(r['recorded_duration_hours'] for r in rows)/len(rows) if rows else None,
        **{k:str(v) for k,v in sums.items()})


def compare(result,expected):
    differences=[k for k,v in expected.items() if k not in result or result[k]!=v]
    if differences:raise ValueError('BASELINE_REPRODUCTION_FAILED:'+','.join(differences))


def audit(history,baseline):
    if baseline.get('scope')!='SINGLE_EXIT_FIXED_HYPOTHESIS_RESEARCH':raise ValueError('BASELINE_SCOPE')
    if baseline['policy']!={k:str(v) for k,v in asdict(Policy()).items()}:raise ValueError('BASELINE_POLICY_CHANGED')
    if history.symbol!='BTC/USDT':raise ValueError('BASELINE_SYMBOL')
    raw=baseline['filter_assumptions']
    rules=Rules(**{k:v if k in ('symbol','observed_ms') else D(v) for k,v in raw.items()})
    h=hourly(history)
    if len(h.candles)!=baseline['hourly_bars'] or len(history.candles)!=baseline['source_bars']:
        raise ValueError('BASELINE_BAR_COUNT')
    scenarios=[]
    for name in ('base','double_costs'):
        candidates=[s for s in baseline['scenarios'] if s['name']==name]
        if len(candidates)!=1:raise ValueError('BASELINE_SCENARIO')
        expected=candidates[0]['continuous'];fee=D(expected['fee_rate']);slip=D(expected['slippage_rate'])
        journal=Audit(slip);result=run(h,rules,fee=fee,slip=slip,audit=journal)
        compare(result,expected)
        if journal.active is not None or result['position_open']:raise ValueError('AUDIT_OPEN_INVENTORY')
        totals=aggregate(journal.rows)
        if D(totals['net_pnl'])!=D(result['net_realized']) or D(totals['fees'])!=D(result['fees']):
            raise ValueError('AUDIT_SESSION_CASHFLOW')
        if journal.rejections!=result['rejected_candidates'] or journal.blocked!=result['blocked_exit_attempts']:
            raise ValueError('AUDIT_REJECTIONS')
        by_reason=[dict(reason=reason,**aggregate([r for r in journal.rows if r['reason']==reason]))
                   for reason in sorted({r['reason'] for r in journal.rows})]
        months=sorted({r['entry_utc'][:7] for r in journal.rows})
        by_month=[dict(entry_month_utc=month,**aggregate([r for r in journal.rows if r['entry_utc'].startswith(month)])) for month in months]
        scenarios.append(dict(name=name,baseline_reproduced=True,summary=totals,by_exit_reason=by_reason,
            by_entry_month=by_month,rejections=dict(journal.rejections),trades=journal.rows,
            approved=False,execution_authorized=False))
    return dict(scope='SINGLE_EXIT_SAME_PATH_CASHFLOW_AUDIT',updated_ms=int(time.time()*1000),
        baseline_reproduced=True,parameters_changed=False,strategy_variants_added=0,scenarios=scenarios,
        approved=False,execution_authorized=False,
        limitations=['Same previously inspected BTC sample and the exact saved constant-filter assumptions.',
            'Reference PnL minus assumed slippage/tick impact minus fees equals recorded net PnL on the SAME frozen path.',
            'This accounting is not a no-cost strategy backtest; removing costs changes paths, sizes, filters and risk.',
            'OHLC reference prices are not observed executable bid/ask quotes or measured market impact.',
            'Recorded durations use model bar timestamps, not exact intrabar fills.',
            'MAE/MFE are full-candle bounds; extrema may occur after the modeled intrabar exit.',
            'Monthly groups and realized break-even rate are descriptive, not discovered trading filters or future estimates.',
            'No independent untouched data, new strategy, significance or profitability approval is created.'])


def write_csv(path,rows):
    keys=('trade_id','symbol','entry_utc','exit_utc','reason','quantity','entry','exit',
          'reference_price_pnl','fill_gross_pnl','entry_slippage','exit_slippage',
          'entry_tick_impact','exit_tick_impact','fees','net_pnl','recorded_duration_hours',
          'full_bar_mae_bound','full_bar_mfe_bound','ambiguous_stop_target_bars')
    with path.open('x',encoding='utf-8',newline='') as out:
        writer=csv.DictWriter(out,fieldnames=keys,extrasaction='ignore',lineterminator='\n')
        writer.writeheader();writer.writerows(rows)


def main():
    p=argparse.ArgumentParser(description='Auditoria offline de operação por operação, sem retunar a estratégia.')
    p.add_argument('--csv',type=Path,required=True);p.add_argument('--baseline',type=Path,required=True)
    p.add_argument('--data-dir',type=Path,default=Path(__file__).resolve().parent);args=p.parse_args()
    baseline=json.loads(args.baseline.read_text(encoding='utf-8-sig'))
    csv_hash=hashlib.sha256(args.csv.read_bytes()).hexdigest()
    if csv_hash!=baseline['csv_sha256']:p.error('CSV diferente do experimento original.')
    report=audit(load_history(args.csv),baseline);report['run_id']=uuid.uuid4().hex
    report['csv_sha256']=csv_hash
    report['baseline_canonical_sha256']=hashlib.sha256(json.dumps(baseline,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    root=Path(__file__).resolve().parent
    report['source_hashes']={name:hashlib.sha256((root/name).read_bytes()).hexdigest()
        for name in ('single_exit_audit.py','single_exit_research.py','spot_engine/strategy.py','spot_engine/config.py')}
    folder=args.data_dir/'reports/local/single-exit-audit';folder.mkdir(parents=True,exist_ok=True)
    with (folder/(report['run_id']+'.json')).open('x',encoding='utf-8') as out:json.dump(report,out,allow_nan=False,indent=2)
    for scenario in report['scenarios']:
        write_csv(folder/(report['run_id']+'-'+scenario['name']+'.csv'),scenario['trades'])
    save(folder/'latest.json',report)
    print(json.dumps(dict(baseline_reproduced=True,scenarios=[dict(name=s['name'],summary=s['summary'],by_reason=s['by_exit_reason']) for s in report['scenarios']]),allow_nan=False))
    print(str(folder/(report['run_id']+'.json')))


if __name__=='__main__':main()
