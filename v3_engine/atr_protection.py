"""Pure migration proposal: levels only, not an active engine modification."""
from decimal import Decimal as D
from spot_engine.risk import amount, decimal_policy
from spot_engine.execution import floor,ceil


@decimal_policy
def levels(entry, atr, price_tick, stop_multiplier=D('1.8'),take_multiplier=D('2')):
    for x in (entry,atr,price_tick,stop_multiplier,take_multiplier):amount(x,positive=True)
    if stop_multiplier>D(10) or take_multiplier>D(20):raise ValueError('MULTIPLIER_LIMIT')
    stop=floor(entry-atr*stop_multiplier,price_tick)
    take=ceil(entry+atr*take_multiplier,price_tick)
    if not 0<stop<entry<take:raise ValueError('INVALID_ATR_LEVELS')
    return dict(stop=str(stop),take=str(take),atr_at_entry=str(atr),execution_authorized=False,
        approved=False,gross_rr=str((take-entry)/(entry-stop)),
        note='First target at 2 ATR with 1.8 ATR stop yields only ~1.11 gross R, below V3 minimum 1.5 net R.')
