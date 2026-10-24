"""Reuse audited incremental indicators without editing the running engine.

Higher timeframes are aggregated from complete UTC 15m buckets. Warmup is
3*period, including 150 complete daily bars, as in ESPECIFICACAO-V3.md.
"""
from copy import deepcopy
from spot_engine.v3_research import V3Research, STEP
from . import SYMBOLS


class MultiTimeframeContext:
    def __init__(self, symbol):
        if symbol not in SYMBOLS:
            raise ValueError('V3_OBSERVATION_UNIVERSE_ONLY')
        self._engine = V3Research(symbol)
        self._state = None

    def update_15m(self, candle, as_of_ms):
        previous = self._state
        # Validation occurs in V3Research before any state mutation.
        row = self._engine.update(candle, as_of_ms=as_of_ms)
        e = self._engine
        high = candle.high - candle.low
        obvs = [r['obv'] for r in e.history]
        row.update(close=candle.close, low=candle.low, high=candle.high,
                   body_fraction=abs(candle.close-candle.open)/high if high else 0.,
                   upper_third=bool(high and candle.close >= candle.low+high*2/3),
                   cross9=bool(previous and previous['ema'][9] <= previous['ema'][21]
                               and row['ema'][9] > row['ema'][21]),
                   histogram=row['macd12_26']-row['macd_signal9'],
                   histogram_rising=bool(previous and row['macd12_26']-row['macd_signal9'] > previous['histogram']),
                   obv_rising3=len(obvs) >= 4 and all(a < b for a,b in zip(obvs[-4:],obvs[-3:])),
                   previous_high20=max((r['c'].high for r in list(e.history)[-21:-1]), default=None),
                   breakout=False,
                   higher_context=bool(row['ready'] and e.h4.close > e.h4.value
                                       and e.daily.close > e.daily.value),
                   execution_authorized=False, approved=False)
        if len(e.history) >= 21:
            row['breakout'] = candle.close > row['previous_high20']
        self._state = row
        return self.state()

    def is_ready(self):
        return bool(self._state and self._state['ready'])

    def state(self):
        return deepcopy(self._state) if self._state else {
            'ready': False, 'regime': 'UNKNOWN', 'execution_authorized': False,
            'approved': False}


def replay(history):
    if history.timeframe != '15m':
        raise ValueError('V3_REQUIRES_15M')
    if not history.candles or history.candles[-1].open_ms+STEP > history.observed_ms:
        raise ValueError('HISTORY_NOT_CLOSED')
    context = MultiTimeframeContext(history.symbol)
    for candle in history.candles:
        yield context.update_15m(candle, candle.open_ms+STEP)
