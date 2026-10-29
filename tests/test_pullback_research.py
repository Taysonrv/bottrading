from dataclasses import replace
import unittest
from unittest.mock import patch
from pullback_research import pullback_signals
from spot_engine.config import load_settings
from spot_engine.strategy import analyze
from tests.test_single_exit_research import hours, rules
from single_exit_research import run


class PullbackTests(unittest.TestCase):
    def test_causal_prefix_real_indicators(self):
        h=hours(660);cfg=replace(load_settings({}),symbol='BTC/USDT',timeframe='1h')
        prefix=replace(h,candles=h.candles[:620],end_ms=620*3600000)
        self.assertEqual(pullback_signals(prefix,cfg),pullback_signals(h,cfg)[:620])

    def test_exact_entry_and_no_downtrend_or_excess_volatility(self):
        h=hours(2);bars=list(h.candles)
        bars[0]=replace(bars[0],close=99,low=98)
        bars[1]=replace(bars[1],open=100,close=102,high=103)
        h=replace(h,candles=tuple(bars));cfg=load_settings({})
        proto=analyze(hours(),replace(cfg,timeframe='1h'))[-1]
        a=replace(proto,ready=True,ema_fast=100,ema_slow=95,ema_trend=90,atr_fraction=.01)
        with patch('pullback_research.analyze',return_value=(a,a)):
            self.assertEqual(pullback_signals(h,cfg)[1].action,'ENTER_LONG')
        for bad in (replace(a,ema_fast=94),replace(a,atr_fraction=.03),replace(a,ready=False)):
            with patch('pullback_research.analyze',return_value=(a,bad)):
                self.assertEqual(pullback_signals(h,cfg)[1].action,'HOLD')

    def test_strategy_hook_cannot_silently_drop_bars(self):
        with self.assertRaisesRegex(ValueError,'SIGNAL_COUNT_MISMATCH'):
            run(hours(),rules(),signal_generator=lambda h,c:())

