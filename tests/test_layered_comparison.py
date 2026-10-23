from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch
import unittest
from spot_engine.config import load_settings
from spot_engine.backtest import run
from spot_engine.layered_research import series
from spot_engine.layered_comparison import compare
from tests.test_layered_research import history,STEP


class LayeredComparisonTests(unittest.TestCase):
    def test_full_series_prefix_is_unchanged_by_future_bars(self):
        h=history([100.+(i%13)/10 for i in range(650)])
        prefix=replace(h,candles=h.candles[:620],end_ms=620*STEP)
        self.assertEqual(series(h)[:620],series(prefix))

    def test_masks_only_suppress_entries_and_use_previous_bar(self):
        h=history([100.]*602)
        cfg=replace(load_settings({'TRADING_TIMEFRAME':'15m'}),symbol=h.symbol)
        signals=[SimpleNamespace(action='HOLD') for _ in h.candles]
        signals[599]=SimpleNamespace(action='ENTER_LONG')
        with patch('spot_engine.backtest.analyze',return_value=signals):
            baseline=run(h,cfg)
            all_true=run(h,cfg,entry_mask=[True]*602)
            wrong_bar=[False]*602;wrong_bar[600]=True
            suppressed=run(h,cfg,entry_mask=wrong_bar)
        self.assertEqual(baseline,all_true)
        self.assertEqual(baseline['closed_trades'],1)
        self.assertEqual(suppressed['closed_trades'],0)

    def test_invalid_mask_rejected(self):
        h=history([100.]*602);cfg=load_settings({'TRADING_TIMEFRAME':'15m'})
        for mask in ([True], [1]*602):
            with self.assertRaises(ValueError):run(h,cfg,entry_mask=mask)

    def test_comparison_retains_zero_trade_windows_and_no_approval(self):
        result=compare(history([100.]*2000),2)
        self.assertEqual(len(result['rows']),8)
        self.assertEqual(result['evaluated_variants'],4)
        self.assertFalse(result['approved']);self.assertFalse(result['execution_authorized'])
        self.assertFalse(result['two_year_horizon'])
        self.assertTrue(all(r['closed_trades']==0 for r in result['rows']))
        self.assertTrue(all(r['net_return']==0 for r in result['rows']))
