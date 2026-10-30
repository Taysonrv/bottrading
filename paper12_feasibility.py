"""Public mechanical/cost screen, explicitly independent of strategy signals."""
import argparse
from decimal import Decimal as D
import json
from pathlib import Path
import time
import uuid
from portfolio12 import SYMBOLS,FEE,SLIP
from spot_engine.data import PublicBinance,retry
from spot_engine.main import normalized_rules,parse_book,save
from spot_engine.selection import preview
from spot_engine.execution import floor,ceil
from spot_engine.risk import decimal_policy,amount
from spot_engine.v3_position_plan import filters


@decimal_policy
def assess(rules,bid,ask,now_ms):
    amount(bid,positive=True);amount(ask,positive=True)
    if bid>ask or rules.symbol not in SYMBOLS:raise ValueError('INVALID_SCREEN_MARKET')
    row=dict(symbol=rules.symbol,status='OK',action='ENTER_LONG',candle_close_ms=now_ms)
    plan=preview(row,rules,bid,ask,now_ms=now_ms,quote_ms=now_ms)
    result=dict(symbol=rules.symbol,updated_ms=now_ms,min_notional=str(rules.min_notional),
        spread_fraction=str((ask-bid)/((ask+bid)/2)),mechanically_feasible=False,
        reason=plan['reason'],assumed_entry_signal=True,is_market_signal=False,execution_authorized=False)
    if not plan['eligible']:return result
    q=D(plan['quantity']);entry=ceil(ask*(1+SLIP),rules.price_tick)
    stop=floor(entry*D('.98'),rules.price_tick);take=ceil(entry*D('1.04'),rules.price_tick)
    stop_fill=floor(stop*(1-SLIP),rules.price_tick);take_fill=floor(take*(1-SLIP),rules.price_tick)
    exits=all(filters(rules,q,p) for p in (stop_fill,take_fill))
    cost=q*entry*(1+FEE);risk=cost-q*stop_fill*(1-FEE);reward=q*take_fill*(1-FEE)-cost
    flat=q*floor(bid*(1-SLIP),rules.price_tick)*(1-FEE)-cost
    result.update(quantity=str(q),entry_cost=str(cost),stop_loss_estimate=str(risk),target_profit_estimate=str(reward),
        net_rr=str(reward/risk) if risk>0 else None,flat_bid_roundtrip_pnl=str(flat),
        reason='HYPOTHETICAL_MECHANICALLY_FEASIBLE' if exits and risk>0 and reward>0 else 'EXIT_FILTER_OR_NONPOSITIVE_REWARD',
        mechanically_feasible=exits and risk>0 and reward>0)
    return result


def main():
    p=argparse.ArgumentParser(description='Custos e mínimos públicos para12 pares; não fornece sinais ou ordens.')
    p.add_argument('--data-dir',type=Path,required=True);args=p.parse_args()
    client=PublicBinance();rows=[]
    for symbol in SYMBOLS:
        try:
            now=int(retry(client.fetch_time));rules=normalized_rules(retry(lambda:client.fetch_symbol_info(symbol)),symbol,now)
            start=time.monotonic();raw=retry(lambda:client.fetch_book(symbol))
            actual=int(retry(client.fetch_time))
            if time.monotonic()-start>3:raise ValueError('SLOW_BOOK')
            bid,ask,_,_=parse_book(raw,symbol);rows.append(assess(rules,bid,ask,actual))
        except Exception:rows.append(dict(symbol=symbol,reason='PUBLIC_DATA_UNAVAILABLE',mechanically_feasible=None,is_market_signal=False,execution_authorized=False))
    report=dict(scope='PAPER12_PUBLIC_MECHANICAL_SCREEN',updated_ms=int(time.time()*1000),capital='20',budget='6',
        fee_rate=str(FEE),slippage_rate=str(SLIP),pairs=rows,approved=False,execution_authorized=False,
        note='Assumed entry signal solely for mechanical screening. Not a strategy result, executable quote or guarantee of fill.')
    folder=args.data_dir/'reports/local/paper12-feasibility';folder.mkdir(parents=True,exist_ok=True)
    save(folder/(uuid.uuid4().hex+'.json'),report);save(folder/'latest.json',report)
    print(json.dumps(dict(pairs=len(rows),feasible=sum(r['mechanically_feasible'] is True for r in rows),unknown=sum(r['mechanically_feasible'] is None for r in rows),execution_authorized=False)))


if __name__=='__main__':main()
