"""Read-only projection of exploratory EMA reports; never approves execution."""
import json
import math
import csv
import hashlib
import io
from pathlib import Path


def trade_journal(report_path, expected_hash):
    """Bounded verified CSV. Never accept a path supplied by the report body."""
    try:
        path=report_path.parent.parent/(report_path.stem+'-trades.csv')
        if path.stat().st_size>2_000_000:raise ValueError
        raw=path.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=expected_hash:raise ValueError
        groups={}
        for count,row in enumerate(csv.DictReader(io.StringIO(raw.decode('utf-8')))):
            if count>=10000:raise ValueError
            mode=row['mode'];cost=row['cost_scenario'];reason=row['exit_reason']
            if mode not in ('fixed','trailing') or cost not in ('base','double_costs') or reason not in ('STOP','STOP_GAP','TARGET','END_LIQUIDATION'):raise ValueError
            record=dict(reason=reason,window=int(row['window']),entry_ms=int(row['entry_candle_open_ms']),exit_ms=int(row['exit_candle_open_ms']))
            if not 1<=record['window']<=4 or not 0<=record['entry_ms']<=record['exit_ms']:raise ValueError
            for key in ('quantity','entry','exit_price','gross_pnl','slippage_cost','fees','net_pnl'):
                value=float(row[key])
                if not math.isfinite(value):raise ValueError
                record[key]=value
            if min(record['quantity'],record['entry'],record['exit_price'])<=0 or min(record['fees'],record['slippage_cost'])<0:raise ValueError
            if not math.isclose(record['net_pnl'],record['gross_pnl']-record['fees']-record['slippage_cost'],abs_tol=1e-9):raise ValueError
            key=mode+'_'+cost
            group=groups.setdefault(key,dict(scenario=key,count=0,gross=0.,fees=0.,slippage=0.,net=0.,reasons={},trades=[]))
            group['count']+=1
            for total,field in (('gross','gross_pnl'),('fees','fees'),('slippage','slippage_cost'),('net','net_pnl')):group[total]+=record[field]
            group['reasons'][reason]=group['reasons'].get(reason,0)+1
            group['trades'].append(record)
        for group in groups.values():
            group['trades']=sorted(group['trades'],key=lambda t:(t['exit_ms'],t['entry_ms']),reverse=True)[:30]
        return dict(available=True,groups=list(groups.values()))
    except (OSError,ValueError,KeyError,TypeError,UnicodeError,csv.Error):
        return dict(available=False,groups=[])


def load(root):
    folders=[Path(root).resolve()/'reports/local/spot-validation']
    local=Path(__file__).resolve().parent/'reports/local/spot-validation'
    if local not in folders: folders.append(local)
    for base in (Path(root).resolve(),Path(__file__).resolve().parent):
        for family in ('spot-universe','spot-minute','spot-pullback','spot-exit-audit'):
            batches=base/'reports/local'/family
            if batches.is_dir():
                for batch in sorted(batches.iterdir(),key=lambda p:p.stat().st_mtime,reverse=True)[:3]:
                    folder=batch/'reports'
                    if folder.is_dir() and folder not in folders: folders.append(folder)
    reports=[]
    invalid=0
    for folder in folders:
        if not folder.is_dir(): continue
        for path in sorted(folder.glob('*.json'),key=lambda p:p.stat().st_mtime,reverse=True)[:20]:
            try:
                if path.stat().st_size>1_000_000: raise ValueError
                report=json.loads(path.read_text(encoding='utf-8'))
                if report.get('scope')!='CHRONOLOGICAL_EXPLORATORY_AUDIT' or report.get('approved') is not False: raise ValueError
                rows=[]
                for scenario in report['scenarios']:
                    for i,r in enumerate(scenario['windows'],1):
                        row=dict(scenario=scenario['name'],window=i,start_ms=r['start_ms'],end_ms=r['end_ms'])
                        for key in ('net_return','buy_hold_return','max_drawdown','closed_trades','win_rate','profit_factor','sharpe_zero_rf','gross_pnl','closed_trade_fees','closed_trade_slippage'):
                            value=r.get(key)
                            if value is not None and (type(value) not in (int,float) or not math.isfinite(value)): raise ValueError
                            row[key]=value
                        rows.append(row)
                if not rows: raise ValueError
                reports.append(dict(symbol=report['symbol'],timeframe=report['timeframe'],rows=rows,
                                    journal=trade_journal(path,report['journal_sha256']) if report.get('journal_sha256') else None,
                                    strategy=report.get('strategy','EMA20/50 + EMA200 + ATR'),saved=path.stat().st_mtime,source='Pasta de dados' if folder==folders[0] else 'Pesquisa local de desenvolvimento'))
            except (OSError,ValueError,KeyError,TypeError): invalid+=1
    reports.sort(key=lambda r:r['saved'],reverse=True)
    return dict(available=bool(reports),reports=reports[:30],invalid=invalid,approved=False)
