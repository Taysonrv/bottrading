"""Reconciled PAPER session report. Sampling gaps stay unknown, never uptime."""
import argparse
from decimal import Decimal as D
import json
import math
import sqlite3
from pathlib import Path
import time
import uuid
from portfolio_alerts import ledger
from spot_engine.main import save
from spot_engine.risk import decimal_policy
from system_status import read


def coverage(plan,health,now_ms):
    start=plan.get('start_ms');end=plan.get('end_ms')
    if type(start) is not int or type(end) is not int or not 0<=start<end or now_ms<start:
        return dict(available=False,reason='INVALID_OR_FUTURE_PLAN')
    until=min(now_ms,end);elapsed=(until-start)/1000
    result=dict(available=True,elapsed_seconds=elapsed,recent_seconds=0,stopped_seconds=0,
        unknown_seconds=elapsed,sampled_recent_fraction=0 if elapsed else None,reason='NO_VALID_COVERAGE')
    a=health.get('started');b=health.get('updated')
    keys=('recent_seconds','stopped_seconds','unknown_seconds');values=[health.get(k) for k in keys]
    if any(type(v) not in (int,float) or not math.isfinite(v) or v<0 for v in [a,b,*values]):return result
    if not 0<=a<=b<=now_ms/1000 or abs(sum(values)-(b-a))>1:return result
    if b<start/1000 or a>until/1000:return result
    # The monitor may start just before the wallet. Without interval history,
    # conservatively remove all outside-window time from each known category.
    outside=max(0,start/1000-a)+max(0,b-until/1000)
    recent=max(0,values[0]-outside);stopped=max(0,values[1]-outside)
    result.update(recent_seconds=recent,stopped_seconds=stopped,
        unknown_seconds=max(0,elapsed-recent-stopped),
        sampled_recent_fraction=recent/elapsed if elapsed else None,reason='SAMPLED_CONSERVATIVE_NOT_CONTINUOUS_UPTIME')
    return result


@decimal_policy
def load(root,now_ms=None):
    root=Path(root);folder=root/'reports/local';now=int(time.time()*1000) if now_ms is None else now_ms
    plan=read(folder/'portfolio/plan.json');status=read(folder/'portfolio/status.json')
    result=dict(available=False,scope='FORWARD_PAPER_SESSION_ONLY',updated_ms=now,approved=False,
        execution_authorized=False,coverage=coverage(plan,read(folder/'operation-health.json'),now))
    try:s=ledger(root)
    except (OSError,ValueError,KeyError,TypeError,ArithmeticError,sqlite3.Error):return result
    pnl=[];position=None
    for f in s['fills']:
        if f['side']=='BUY':position=f
        elif position:
            cost=D(position['quantity'])*D(position['price'])+D(position['fee'])
            pnl.append(D(f['quantity'])*D(f['price'])-D(f['fee'])-cost);position=None
    if sum(pnl,D(0))!=D(s['realized']):return result
    stamp=status.get('updated_ms');fresh=type(stamp) is int and 0<=now-stamp<60000
    matches=all(status.get(k)==s[k] for k in ('cash','fees','realized','position','pending'))
    equity=D(s['cash']) if not s['position'] else None
    if equity is None and fresh and matches and status.get('equity') is not None:
        try:
            candidate=D(str(status['equity']))
            if candidate.is_finite() and candidate>=0:equity=candidate
        except ArithmeticError:pass
    wins=[p for p in pnl if p>0];losses=[p for p in pnl if p<0]
    gain=sum(wins,D(0));loss=-sum(losses,D(0));end=plan.get('end_ms')
    result.update(available=True,phase='DEADLINE_REACHED' if type(end) is int and now>=end else status.get('phase','UNKNOWN'),
        start_ms=plan.get('start_ms'),end_ms=end,mark_fresh=fresh and matches,initial_capital='20',cash=s['cash'],
        equity=str(equity) if equity is not None else None,realized=s['realized'],fees=s['fees'],
        net_return=float(equity/D(20)-1) if equity is not None else None,
        unrealized_net=str(equity-D(20)-D(s['realized'])) if equity is not None else None,
        open_position=bool(s['position']),pending=bool(s['pending']),halt=s['halt'],
        closed_cycles=len(pnl),wins=len(wins),losses=len(losses),win_rate=len(wins)/len(pnl) if pnl else None,
        profit_factor=float(gain/loss) if loss else None,sharpe=None,max_drawdown=None,
        sample_verdict='INSUFFICIENT_FOR_EDGE_VALIDATION',
        limitations=['Win rate and profit factor describe only this session, not future edge.',
            'No continuous equity curve: Sharpe and maximum drawdown are not reconstructed.',
            'Open inventory needs a fresh matching mark; expiry does not guarantee liquidation.',
            'Fees are ledger cashflows; hypothetical slippage is embedded in fill prices, not measured impact.',
            'Recent sampled seconds are evidence at adjacent observations, not proof of uninterrupted uptime.'])
    return result


def main():
    p=argparse.ArgumentParser(description='Relatório da carteira PAPER sem alterar a sessão.')
    p.add_argument('--data-dir',type=Path,required=True);args=p.parse_args()
    report=load(args.data_dir)
    if not report['available']:raise SystemExit('Ledger indisponível ou não reconciliado; relatório recusado.')
    folder=args.data_dir/'reports/local/session-performance';folder.mkdir(parents=True,exist_ok=True)
    identity=uuid.uuid4().hex;save(folder/(identity+'.json'),report);save(folder/'latest.json',report)
    print(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False))


if __name__=='__main__':main()
