from dataclasses import replace
import unittest
from spot_engine.data import Candle,History
from spot_engine.layered_research import inspect

STEP=900000

def history(prices,volumes=None):
    volumes=volumes or [10.]*len(prices)
    candles=tuple(Candle(i*STEP,p,p+1,p-1,p,volumes[i]) for i,p in enumerate(prices))
    return History('BTC/USDT','15m',0,len(prices)*STEP,len(prices)*STEP,candles,1,0)


class LayeredResearchTests(unittest.TestCase):
    def test_warmup_and_flat_market_never_authorize_execution(self):
        result=inspect(history([100.]*100))
        self.assertFalse(result['ready']);self.assertIsNone(result['score_points'])
        result=inspect(history([100.]*620))
        self.assertEqual(result['rsi14'],50)
        self.assertEqual(result['candidate'],'HOLD')
        self.assertFalse(result['execution_authorized'])
        self.assertIsNone(result['calibrated_probability'])

    def test_volume_uses_prior_bars_excluding_current(self):
        result=inspect(history([100.]*620,[10.]*619+[30.]))
        self.assertEqual(result['relative_volume20'],3)
        self.assertTrue(result['checks']['volume'])

    def test_missing_volume_is_not_a_pass(self):
        result=inspect(history([100.]*620,[0.]*620))
        self.assertIsNone(result['relative_volume20'])
        self.assertFalse(result['checks']['volume'])

    def test_future_and_gapped_data_rejected(self):
        h=history([100.]*620)
        with self.assertRaises(ValueError):inspect(replace(h,observed_ms=h.end_ms-1))
        with self.assertRaises(ValueError):inspect(replace(h,candles=h.candles[:10]+h.candles[11:]))

    def test_future_extension_does_not_change_prefix_result(self):
        h=history([100.+(i%7)/10 for i in range(630)])
        prefix=replace(h,candles=h.candles[:620],end_ms=620*STEP)
        result=inspect(prefix)
        other=replace(h,candles=h.candles[:620]+(Candle(620*STEP,10000,10001,9999,10000,10.),))
        self.assertEqual(result,inspect(replace(other,candles=other.candles[:620],end_ms=620*STEP)))
