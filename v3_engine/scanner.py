"""Additional scanner diagnostics; partial warmup cannot imply V3 readiness."""
from spot_engine.v3_research import V3Research


def quick_regime(history):
    if history.timeframe!='15m':return dict(detected='UNKNOWN',reason='V3_REQUIRES_15M',execution_authorized=False)
    # Indicators are price-series functions independent of asset names. The
    # existing research class has a restricted candidate universe; use it only
    # as a numeric accumulator and never expose its candidate/action outputs.
    engine=V3Research('BTC/USDT');row=None
    for c in history.candles:row=engine.update(c,as_of_ms=c.open_ms+900000)
    if not row:return dict(detected='UNKNOWN',reason='NO_DATA',execution_authorized=False)
    ema=row['ema'];recent=list(engine.history)
    high=max((r['c'].high for r in recent[-21:-1]),default=float('inf'))
    return dict(detected=row['regime'],reason='READY' if row['ready'] else 'HIGHER_TIMEFRAME_WARMUP',
        adx14=row['adx14'],rsi14=row['rsi14'],atr_fraction=row['atr_fraction'],
        score_estimate=None,ema9_above_21=ema[9]>ema[21],ema21_above_50=ema[21]>ema[50],
        breakout_above_20bar_high=history.candles[-1].close>high,
        vol_relative=row['volume_relative20'],closes20=[r['c'].close for r in recent[-20:]],
        execution_authorized=False,approved=False,
        note='620 bars do not warm up daily/4H context. No quick score invented.')
