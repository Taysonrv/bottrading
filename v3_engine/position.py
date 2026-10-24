"""Pure candle-model exit research. No ledger, broker, orders or live approval.

Conservative ambiguity: an existing stop is evaluated before any target.
Breakeven/trailing computed after this candle apply only to the next candle.
"""
from copy import deepcopy
from decimal import Decimal as D
from spot_engine.data import milliseconds
from spot_engine.risk import amount, decimal_policy
from spot_engine.execution import floor, ceil


@decimal_policy
def open_position(plan, opened_ms, fee=D('.001'), slip=D('.001')):
    milliseconds(opened_ms);amount(fee);amount(slip)
    if not plan.get('valid_research_plan') or plan.get('execution_authorized') is not False:
        raise ValueError('VALID_OFFLINE_PLAN_REQUIRED')
    if fee>D('.01') or slip>D('.01'):raise ValueError('INVALID_COSTS')
    q=D(plan['quantity']);cost=D(plan['estimated_cost']);entry=D(plan['entry']);stop=D(plan['stop'])
    amount(q,positive=True);amount(cost,positive=True)
    return dict(symbol=plan['symbol'],entry=str(entry),stop=str(stop),initial_risk=str(entry-stop),
        original_quantity=str(q),remaining=str(q),remaining_cost=str(cost),realized='0',
        max_high=str(entry),opened_ms=opened_ms,last_close_ms=opened_ms,bars=0,
        legs=deepcopy(plan['exits']),next_leg=0,fee=str(fee),slip=str(slip),
        execution_authorized=False,approved=False,closed=False)


@decimal_policy
def advance(position, candle, *, as_of_ms, atr, tick, stopped=False, risk_halted=False, opposite=False):
    p=deepcopy(position);amount(atr,positive=True);amount(tick,positive=True);milliseconds(as_of_ms)
    if p['closed']:raise ValueError('POSITION_ALREADY_CLOSED')
    close_ms=candle.open_ms+900000
    if candle.open_ms!=p['last_close_ms'] or close_ms>as_of_ms:raise ValueError('CAUSAL_CONTIGUOUS_CANDLE_REQUIRED')
    events=[];qty=D(p['remaining']);fee=D(p['fee']);slip=D(p['slip'])
    def exit_part(q,price,reason):
        nonlocal qty
        if q<=0 or q>qty:raise ValueError('INVALID_EXIT_QUANTITY')
        cost=D(p['remaining_cost'])*q/qty;proceeds=q*price*(1-fee)
        p['remaining_cost']=str(D(p['remaining_cost'])-cost)
        p['realized']=str(D(p['realized'])+proceeds-cost);qty-=q;p['remaining']=str(qty)
        events.append(dict(reason=reason,quantity=str(q),assumed_fill=str(price),pnl=str(proceeds-cost),execution_authorized=False))
    o,h,l=(D(str(v)) for v in (candle.open,candle.high,candle.low))
    stop=D(p['stop'])
    if stopped or risk_halted:exit_part(qty,floor(o*(1-slip),tick),'KILL_OR_RISK')
    elif l<=stop:exit_part(qty,floor(min(o,stop)*(1-slip),tick),'STOP_GAP' if o<stop else 'STOP')
    else:
        while p['next_leg']<len(p['legs']):
            leg=p['legs'][p['next_leg']];target=D(leg['target'])
            if h<target:break
            exit_part(D(leg['quantity']),floor(target*(1-slip),tick),'TP'+str(p['next_leg']+1))
            p['next_leg']+=1
        if qty and opposite:exit_part(qty,floor(D(str(candle.close))*(1-slip),tick),'OPPOSITE')
        if qty and p['bars']+1>=32:exit_part(qty,floor(D(str(candle.close))*(1-slip),tick),'TIME_STOP')
    if qty:
        entry=D(p['entry']);r=D(p['initial_risk']);peak=max(D(p['max_high']),h);new_stop=stop
        if D(p['realized'])>=D('.8')*r*D(p['original_quantity']):
            new_stop=max(new_stop,ceil(entry*(1+fee)/((1-fee)*(1-slip)),tick))
        if peak-entry>=D('1.5')*r:new_stop=max(new_stop,floor(peak-D('1.8')*atr,tick))
        p['stop']=str(new_stop);p['max_high']=str(peak)
    p.update(closed=qty==0,bars=p['bars']+1,last_close_ms=close_ms)
    return p,events
