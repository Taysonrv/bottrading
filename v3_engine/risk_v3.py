"""Offline entry proposals only; reuse precision-80 policy and filter checks."""
from decimal import Decimal as D
from spot_engine.risk import decimal_policy
from spot_engine.execution import floor
from spot_engine.v3_position_plan import plan, filters, reject
from . import SYMBOLS


@decimal_policy
def plan_entry(rules, budget, **kwargs):
    if rules.symbol not in SYMBOLS: return reject('UNSUPPORTED_SYMBOL')
    # Existing plan already enforces 1%/5% risk, 40% exposure, freshness,
    # per-leg quantity/notional filters and NET weighted RR >= 1.5.
    result = plan(rules, budget, **kwargs)
    if not result['valid_research_plan']: return result
    cap = min(D('5'),budget.equity*D('.25'),budget.free_cash)
    cost = D(result['estimated_cost'])
    if cost <= cap: return result
    entry = D(result['entry']); fee = kwargs.get('fee',D('.001'))
    qty = floor(cap/(entry*(1+fee)), rules.qty_step)
    if not filters(rules,qty,entry): return reject('MAX_NOTIONAL_FILTER')
    quantities = (floor(qty*D('.4'),rules.qty_step),floor(qty*D('.35'),rules.qty_step))
    quantities += (qty-sum(quantities),)
    stop_fill = D(result['assumed_stop_fill'])
    for leg, q in zip(result['exits'],quantities):
        if not all(filters(rules,q,p) for p in (D(leg['target']),D(leg['assumed_fill']),stop_fill)):
            return reject('CAPPED_PARTIAL_EXIT_FILTER')
        leg['quantity'] = str(q)
    previous_qty = D(result['quantity'])
    risk = D(result['estimated_stop_loss'])*qty/previous_qty
    capped_cost = qty*entry*(1+fee)
    gain = sum(q*D(leg['assumed_fill'])*(1-fee) for q,leg in zip(quantities,result['exits']))-capped_cost
    if gain/risk < D('1.5'): return reject('NET_WEIGHTED_RR_TOO_LOW')
    result.update(quantity=str(qty), estimated_cost=str(capped_cost),estimated_stop_loss=str(risk),
                  net_weighted_rr=str(gain/risk),max_notional=str(cap),
                  remaining_exposure_room=str(budget.equity*D('.4')-budget.exposure-capped_cost))
    return result
