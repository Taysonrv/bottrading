"""Read-only public-filter audit of hypothetical V3 entries, never orders.

Separate actual strategy score from a deliberately hypothetical score=100
budget stress test. No account API, wallet or active session modifications.
"""
import argparse
from dataclasses import asdict
from decimal import Decimal as D
import hashlib
import json
from pathlib import Path
import time
import uuid
from spot_engine.data import PublicBinance, retry
from spot_engine.main import normalized_rules, parse_book, save
from spot_engine.v3_position_plan import Budget
from spot_engine.risk import amount, decimal_policy
from v3_engine import SYMBOLS
from v3_engine.risk_v3 import plan_entry


def budget(capital=D('20')):
    return Budget(capital,capital,D(0),D(0),capital*D('.03'),capital*D('.10'))


@decimal_policy
def audit_pair(rules, bid, ask, atr, score, now_ms, *, capital=D('20')):
    if rules.symbol not in SYMBOLS:raise ValueError('V3_UNIVERSE_ONLY')
    amount(bid,positive=True);amount(ask,positive=True)
    if bid>ask:raise ValueError('CROSSED_BOOK')
    b=budget(capital)
    arguments=dict(ask=ask,atr=atr,score=score,now_ms=now_ms,quote_ms=now_ms)
    actual=plan_entry(rules,b,**arguments)
    maximum=plan_entry(rules,b,**dict(arguments,score=100))
    return dict(symbol=rules.symbol,quote_ms=now_ms,bid=str(bid),ask=str(ask),atr14=str(atr),
        actual_score=score,hypothetical_capital=str(capital),max_entry_cost='5',
        strategy_score_plan=actual,
        hypothetical_perfect_score_plan=maximum,
        perfect_score_is_market_signal=False,
        minimum_aggregate_stop_notional=str(3*rules.min_notional),
        cap_precludes_three_stop_legs=3*rules.min_notional>min(D('5'),capital*D('.25'),capital),
        minimum_bound_is_necessary_not_sufficient=True,
        normalized_rules={k:str(v) if isinstance(v,D) else v for k,v in asdict(rules).items()},
        execution_authorized=False,approved=False)


def capture(root,client=None):
    root=Path(root);now=int(time.time()*1000)
    try:status=json.loads((root/'reports/local/v3-status/latest.json').read_text(encoding='utf-8'))
    except (OSError,ValueError):status={}
    stamp=status.get('updated_ms')
    fresh=(status.get('source')=='PUBLIC_REST_FORWARD' and status.get('healthy') is True
        and type(stamp) is int and 0<=now-stamp<=90000)
    states={r.get('symbol'):r for r in status.get('pairs',[]) if isinstance(r,dict)}
    client=PublicBinance() if client is None else client
    rows=[]
    for symbol in SYMBOLS:
        try:
            row=states[symbol];state=row['state']
            if not fresh or row['status']!='OK' or state['ready'] is not True:raise ValueError('NO_RECENT_CONTEXT')
            # Fetch only public metadata and book. The V3 observer remains owner
            # of its indicators; this module never updates that state.
            info=retry(lambda:client.fetch_symbol_info(symbol))
            started=time.monotonic()
            bid,ask,_,_=parse_book(retry(lambda:client.fetch_book(symbol)),symbol)
            actual=int(retry(client.fetch_time))
            if time.monotonic()-started>2:raise ValueError('SLOW_QUOTE')
            if not 0<=actual-state['decision_ms']<=900000:raise ValueError('STALE_CANDLE')
            rules=normalized_rules(info,symbol,actual)
            result=audit_pair(rules,bid,ask,D(str(state['atr14'])),row['score_estimate'],actual)
            result.update(status='OK',regime=row['regime_v3'],candle_close_ms=state['decision_ms'])
            rows.append(result)
        except Exception:
            rows.append(dict(symbol=symbol,status='DATA_UNAVAILABLE',reason='RECENT_CONTEXT_OR_PUBLIC_FILTERS_UNAVAILABLE',
                             execution_authorized=False,approved=False))
    return dict(scope='PUBLIC_FILTER_FEASIBILITY_NOT_BACKTEST',updated_ms=int(time.time()*1000),
        source='BINANCE_PUBLIC_FILTERS_AND_BOOK',observer_identity=status.get('identity'),pairs=rows,
        hypothetical_capital='20',approved=False,execution_authorized=False,
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        limitations=['A score=100 stress test is deliberately hypothetical, not a buy signal.',
            'Current filters are not historical filters and must not be represented as such.',
            'Normalized LIMIT constraints omit other exchange filters and liquidity/queue effects.',
            'No capital increase or order splitting is authorized by this report.'])


def main():
    p=argparse.ArgumentParser(description='Viabilidade V3 com dados públicos atuais, sem ordens.')
    p.add_argument('--data-dir',type=Path,required=True);args=p.parse_args()
    report=capture(args.data_dir)
    report['run_id']=uuid.uuid4().hex
    folder=args.data_dir/'reports/local/v3-feasibility';folder.mkdir(parents=True,exist_ok=True)
    with (folder/(report['run_id']+'.json')).open('x',encoding='utf-8') as output:
        json.dump(report,output,indent=2,allow_nan=False)
    save(folder/'latest.json',report)
    print(json.dumps(dict(approved=False,pairs=[dict(symbol=r['symbol'],status=r['status'],
        signal_reason=r.get('strategy_score_plan',{}).get('reason'),
        budget_reason=r.get('hypothetical_perfect_score_plan',{}).get('reason')) for r in report['pairs']]),indent=2))


if __name__=='__main__':main()
