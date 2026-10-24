"""Pure persistent-state contract for V3 simulation circuit breakers."""
from copy import deepcopy
from decimal import Decimal as D
from spot_engine.risk import amount, decimal_policy
from spot_engine.data import milliseconds


@decimal_policy
def assess(previous, *, equity, now_ms, stopped=False, closed_trade_pnl=None):
    amount(equity,positive=True);milliseconds(now_ms)
    if type(stopped) is not bool:raise ValueError('INVALID_STOP')
    s=deepcopy(previous) if previous else dict(peak=str(equity),day_base=str(equity),day=now_ms//86400000,
        last_ms=now_ms,daily_halted=False,drawdown_halted=False,losses=0,losses_halted=False)
    if now_ms<s['last_ms']:raise ValueError('CLOCK_REVERSED')
    if s['day']!=now_ms//86400000:s.update(day=now_ms//86400000,day_base=str(equity),daily_halted=False)
    s['peak']=str(max(equity,D(s['peak'])))
    s['drawdown_halted']|=equity<=D(s['peak'])*D('.90')
    s['daily_halted']|=equity<=D(s['day_base'])*D('.97')
    if closed_trade_pnl is not None:
        if not isinstance(closed_trade_pnl,D) or not closed_trade_pnl.is_finite():raise ValueError('INVALID_PNL')
        if closed_trade_pnl<0:s['losses']+=1
        elif closed_trade_pnl>0:s['losses']=0
        s['losses_halted']|=s['losses']>=4
    s['last_ms']=now_ms
    reason=('STOP' if stopped else 'DRAWDOWN' if s['drawdown_halted'] else 'DAILY_LOSS' if s['daily_halted']
            else 'FOUR_LOSSES' if s['losses_halted'] else 'OK')
    return dict(state=s,can_enter=reason=='OK',reason=reason,execution_authorized=False,approved=False)
