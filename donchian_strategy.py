"""One unvalidated research hypothesis. Closed-bar signal only, no order adapter."""
from dataclasses import replace
from spot_engine.strategy import analyze


def signals(history,cfg):
    if history.symbol!='BTC/USDT' or history.timeframe!='1h' or cfg.ema_trend!=200 or cfg.atr_period!=14:
        raise ValueError('FIXED_DONCHIAN_PROTOCOL_REQUIRED')
    indicators=analyze(history,cfg);result=[]
    for i,current in enumerate(indicators):
        high=max(c.high for c in history.candles[i-20:i]) if i>=20 else None
        enter=(current.ready and high is not None and history.candles[i].close>high
            and history.candles[i].close>current.ema_trend and current.atr_fraction is not None
            and .001<=current.atr_fraction<=.02)
        result.append(replace(current,action='ENTER_LONG' if enter else 'HOLD',
            reason='DONCHIAN20_CLOSED_BREAKOUT' if enter else 'WAIT_DONCHIAN20'))
    return tuple(result)
