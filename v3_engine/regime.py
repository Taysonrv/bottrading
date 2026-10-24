"""Deterministic regime classification; UNKNOWN wins over every other rule."""
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class RegimeResult:
    regime: str
    execution_authorized: bool = False


def detect(state):
    required = ('adx14', 'rsi14', 'atr_fraction', 'close', 'vwap', 'volume_relative20')
    if not state.get('ready') or any(type(state.get(k)) not in (int,float)
        or not math.isfinite(state[k]) for k in required):
        return RegimeResult('UNKNOWN')
    adx, rsi, atr = (state[k] for k in required[:3])
    ema = state.get('ema', {})
    if any(type(ema.get(k)) not in (int,float) or not math.isfinite(ema[k]) for k in (9,21,50)):
        return RegimeResult('UNKNOWN')
    if not 0 <= adx <= 100 or not 0 <= rsi <= 100 or atr < 0 or min(state['close'],state['vwap']) <= 0:
        return RegimeResult('UNKNOWN')
    if atr > .03: regime = 'CRISIS'
    elif adx > 25 and state.get('breakout') and state['volume_relative20'] > 1.3: regime = 'BREAKOUT'
    elif adx > 25 and ema[9] > ema[21] > ema[50]: regime = 'TREND'
    elif adx < 20 and rsi < 45 and state['close'] < state['vwap']: regime = 'RANGE'
    else: regime = 'TRANSITION'
    return RegimeResult(regime)


class RegimeDetector:
    def __init__(self, context): self.context = context
    def detect(self, candle_15m, as_of_ms):
        return detect(self.context.update_15m(candle_15m, as_of_ms))
