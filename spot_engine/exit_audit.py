"""Offline exit comparison with frozen signals, private reconciled trade journal."""
import argparse
import csv
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path
import uuid
from .data import load_history
from .risk import Rules
from .minute_research import simulate
from .pullback_research import hourly,Pullback,H,WARMUP
from .scanner import SYMBOLS
from .main import save


def compare(bars,rules,baseline):
    strategy=Pullback();intents=[];atrs=[]
    for c in bars:
        intents.append(strategy.update(c));atrs.append(strategy.atr)
    n=len(bars)-WARMUP
    if n<2400:raise ValueError('Short history')
    scenarios=[];trades=[];changes=[]
    for mode in ('fixed','trailing'):
        for label,mult in [('base',1),('double_costs',2)]:
            rows=[]
            for j in range(4):
                result=simulate(bars,intents,WARMUP+n*j//4,WARMUP+n*(j+1)//4,rules,
                                fee=.001*mult,slip=.001*mult,step_ms=H,
                                exit_mode=mode,atrs=atrs,journal=True)
                journal=result.pop('trade_journal');stop_changes=result.pop('stop_changes')
                for t in journal:trades.append(dict(mode=mode,cost_scenario=label,window=j+1,**t))
                for t in stop_changes:changes.append(dict(mode=mode,cost_scenario=label,window=j+1,**t))
                result['gross_pnl']=sum(t['gross_pnl'] for t in journal)
                result['closed_trade_fees']=sum(t['fees'] for t in journal)
                result['closed_trade_slippage']=sum(t['slippage_cost'] for t in journal)
                result['closed_trade_net']=sum(t['net_pnl'] for t in journal)
                if not result['remaining_units'] and not math.isclose(result['net_return']*20,result['closed_trade_net'],abs_tol=1e-9):
                    raise ValueError('Wallet and journal differ')
                if mode=='fixed':
                    prior=next(s for s in baseline['scenarios'] if s['name']==label)['windows'][j]
                    for key in ('net_return','closed_trades','fees','remaining_units'):
                        if not math.isclose(result[key],prior[key],abs_tol=1e-10):raise ValueError('Baseline regression')
                rows.append(result)
            scenarios.append(dict(name=mode+'_'+label,windows=rows))
    return scenarios,trades,changes


def main():
    parser=argparse.ArgumentParser(description='Auditoria offline de saídas. Nenhuma ordem.')
    parser.add_argument('--data-dir',type=Path,required=True)
    parser.add_argument('--baseline-dir',type=Path,required=True)
    args=parser.parse_args()
    folder=Path(__file__).resolve().parent.parent/'reports/local/spot-exit-audit'/uuid.uuid4().hex
    (folder/'reports').mkdir(parents=True)
    index=dict(scope='EXIT_POLICY_AUDIT',approved=False,rows=[])
    for symbol in SYMBOLS:
        paths=list(args.data_dir.glob(symbol.replace('/','-')+'-15m-*.csv'))
        if len(paths)!=1:raise ValueError('One source per pair required')
        baseline=json.loads((args.baseline_dir/(symbol.replace('/','-')+'.json')).read_text(encoding='utf-8'))
        history=load_history(paths[0])
        if hashlib.sha256(paths[0].read_bytes()).hexdigest()!=baseline['csv_sha256']:raise ValueError('Source mismatch')
        r=baseline['rules'];rules=Rules(**{k:(int(v) if k=='observed_ms' else v if k=='symbol' else Decimal(v)) for k,v in r.items()})
        scenarios,trades,changes=compare(hourly(history),rules,baseline)
        journal_path=folder/(symbol.replace('/','-')+'-trades.csv')
        columns=['mode','cost_scenario','window','signal_close_ms','entry_candle_open_ms','entry_reason',
                 'raw_entry','entry','entry_fee','initial_stop','target','exit_candle_open_ms','exit_reference',
                 'exit_price','exit_reason','quantity','gross_pnl','slippage_cost','fees','net_pnl']
        with journal_path.open('x',encoding='utf-8',newline='') as output:
            writer=csv.DictWriter(output,fieldnames=columns);writer.writeheader();writer.writerows(trades)
        save(folder/(symbol.replace('/','-')+'-stop-updates.json'),changes)
        report=dict(scope='CHRONOLOGICAL_EXPLORATORY_AUDIT',approved=False,symbol=symbol,timeframe='1h',
                    strategy='PULLBACK_FIXED_VS_TRAILING_3ATR',scenarios=scenarios,
                    journal_sha256=hashlib.sha256(journal_path.read_bytes()).hexdigest(),
                    csv_sha256=baseline['csv_sha256'],
                    source_hashes={f:hashlib.sha256(Path(__file__).with_name(f).read_bytes()).hexdigest()
                                   for f in ('exit_audit.py','minute_research.py','pullback_research.py')},
                    caveats=['Identical signal stream, not identical fills: one-position occupancy changes subsequent entries.',
                             'Trailing stop=max(previous stop,closed-hour close minus3ATR); effective next hour, never same-bar high.',
                             'Baseline fixed exits reproduced before comparison; no strategy approval.',
                             'Historical reused sample, current lot/minimum, no historical spread, tick rounding, queue or latency.',
                             'Gross PnL uses pre-slippage reference prices; actual net subtracts slippage and both fees.',
                             'Intrabar exit timestamps are unknown; journal records containing candle open, not exact fill time.'])
        save(folder/'reports'/(symbol.replace('/','-')+'.json'),report)
        row=dict(symbol=symbol,baseline_reproduced=True,scenarios=[dict(name=s['name'],returns=[w['net_return'] for w in s['windows']],
                 gross=sum(w['gross_pnl'] for w in s['windows']),fees=sum(w['closed_trade_fees'] for w in s['windows']),
                 slippage=sum(w['closed_trade_slippage'] for w in s['windows'])) for s in scenarios])
        index['rows'].append(row);save(folder/'index.json',index)
        print(json.dumps(row),flush=True)
    print('Auditoria concluída: '+str(folder),flush=True)


if __name__=='__main__':main()
