"""Attachment variant: three entry hypotheses and one observation filter.

ENTER is only a historical research signal, never an order or approval.
No invented EXIT: exits require a position state machine, absent here.
"""
from dataclasses import dataclass, asdict
from .regime import detect
from .scorer import score


@dataclass(frozen=True)
class Signal:
    action: str
    reason: str
    regime: str
    score: int
    components: dict
    execution_authorized: bool = False
    approved: bool = False

    def report(self): return asdict(self)


class Hypothesis:
    regime = ''
    range_mode = False
    def trigger(self, state): return False
    def evaluate(self, state):
        regime = detect(state).regime
        trigger = regime == self.regime and self.trigger(state)
        result = score(state, trigger=trigger, range_mode=self.range_mode)
        # Score cannot bypass timing, trend context, ATR or regime prerequisites.
        eligible = (trigger and result['score'] >= 70 and state.get('higher_context')
                    and result['components']['trigger_body'] == 20
                    and result['components']['atr_bands'] == 20)
        return Signal('ENTER' if eligible else 'HOLD',
            'RESEARCH_CANDIDATE' if eligible else 'GATES_NOT_MET', regime,
            result['score'], result['components'])


class TrendFollowing(Hypothesis):
    regime = 'TREND'
    def trigger(self, state): return bool(state['cross9'] and state['adx14'] > 25)


class RangeReversion(Hypothesis):
    regime = 'RANGE'
    range_mode = True
    def trigger(self, state):
        lower = state['bollinger20']['lower']
        return lower is not None and state['low'] <= lower <= state['close'] and state['rsi14'] < 35


class BreakoutMomentum(Hypothesis):
    regime = 'BREAKOUT'
    def trigger(self, state): return bool(state['breakout'])


class TransitionFilter(Hypothesis):
    regime = 'TRANSITION'
    def evaluate(self, state):
        result = score(state)
        return Signal('OBSERVE', 'OBSERVATION_ONLY', detect(state).regime,
                      result['score'], result['components'])


def evaluate(state):
    kind = {'TREND':TrendFollowing, 'RANGE':RangeReversion,
            'BREAKOUT':BreakoutMomentum, 'TRANSITION':TransitionFilter}.get(detect(state).regime)
    return kind().evaluate(state) if kind else Signal('HOLD','REGIME_BLOCKED',
        detect(state).regime,0,dict.fromkeys(('context_ribbon','momentum','trigger_body','atr_bands','volume_obv_vwap'),0))
