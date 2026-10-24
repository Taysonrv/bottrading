"""Five binary 20-point diagnostics. A score is NOT a probability.

These new attachment rules are a separate variant, not the four original
divergence/VWAP hypotheses. Range entries use range-specific context/volume
alignment: a long below VWAP cannot also be required to be above VWAP.
"""
from .regime import detect


def score(state, trigger=False, range_mode=False):
    regime = detect(state).regime
    components = dict(context_ribbon=0, momentum=0, trigger_body=0,
                      atr_bands=0, volume_obv_vwap=0)
    if regime in ('UNKNOWN','CRISIS'):
        return dict(score=0, components=components, execution_authorized=False)
    close = state['close']; bands = state['bollinger20']; ema = state['ema']
    components['context_ribbon'] = 20*int(state['higher_context'] and (
        regime == 'RANGE' if range_mode else
        regime in ('TREND','BREAKOUT') and ema[9] > ema[21] > ema[50] and close > ema[9]))
    components['momentum'] = 20*int((state['rsi14'] < 35 if range_mode else 45 <= state['rsi14'] <= 65)
        and state['macd12_26'] > state['macd_signal9'] and state['histogram_rising'])
    components['trigger_body'] = 20*int(trigger and state['body_fraction'] >= .6 and state['upper_third'])
    band_ok = (bands['lower'] is not None and bands['upper'] is not None and
               (state['low'] <= bands['lower'] <= close if range_mode else
                close >= bands['lower']+(bands['upper']-bands['lower'])*2/3))
    components['atr_bands'] = 20*int(.005 <= state['atr_fraction'] <= .02 and band_ok)
    components['volume_obv_vwap'] = 20*int(state['volume_relative20'] > 1.2 and state['obv_rising3']
        and (close < state['vwap'] if range_mode else close > state['vwap']))
    return dict(score=sum(components.values()), components=components, execution_authorized=False)
