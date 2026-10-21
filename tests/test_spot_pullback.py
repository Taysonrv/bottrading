from types import SimpleNamespace
import unittest
from spot_engine.data import Candle
from spot_engine.pullback_research import Pullback,hourly,H


class PullbackTests(unittest.TestCase):
    def test_only_complete_hourly_groups(self):
        bars=tuple(Candle(i*900000,100+i,102+i,99+i,101+i,2) for i in range(7))
        result=hourly(SimpleNamespace(timeframe='15m',candles=bars))
        self.assertEqual(len(result),1)
        self.assertEqual(result[0].open_ms,0)
        self.assertEqual(result[0].close,104)
        self.assertEqual(result[0].volume,8)

    def test_trend_changes_only_on_closed_four_hours(self):
        s=Pullback()
        for i in range(4):s.update(Candle(i*H,100,101,99,100,1))
        self.assertEqual(s.count4,1)
        self.assertEqual(s.ema200,100)
        s.update(Candle(4*H,200,201,199,200,1))
        self.assertEqual(s.ema200,100)

    def ready(self):
        s=Pullback();s.count4=600;s.ema200=90;s.ema20=100;s.atr=1
        s.previous=Candle(0,100,101,99,100,1);s.previous_touch=True
        return s

    def test_confirmation_and_filters(self):
        bar=Candle(H,102,104,101,103,1)
        result=self.ready().update(bar)
        self.assertTrue(result.enter)
        self.assertGreater(result.stop_fraction,0)
        s=self.ready();s.previous_touch=False
        self.assertEqual(s.update(bar).reason,'NO_PREVIOUS_PULLBACK')
        s=self.ready();s.ema200=110
        self.assertEqual(s.update(bar).reason,'TREND_4H_FILTER')
        self.assertEqual(self.ready().update(Candle(H,100,101,99,100,1)).reason,'NO_CONFIRMATION')

    def test_future_cannot_change_previous_intents(self):
        bars=tuple(Candle(i*H,100+i*.01,101+i*.01,99+i*.01,100+i*.01,1) for i in range(2420))
        a=Pullback();b=Pullback()
        whole=[a.update(c) for c in bars]
        prefix=[b.update(c) for c in bars[:2410]]
        self.assertEqual(prefix,whole[:2410])
        self.assertFalse(any(i.enter for i in whole[:2399]))

    def test_gap_does_not_mutate_state(self):
        s=Pullback();s.update(Candle(0,100,101,99,100,1))
        with self.assertRaises(ValueError):s.update(Candle(2*H,100,101,99,100,1))
        self.assertEqual(s.previous.open_ms,0)
