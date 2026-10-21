from dataclasses import replace
import unittest
from spot_engine.config import load_settings
from spot_engine.data import Candle,History
from spot_engine.temporal_validation import windows,evaluate

H=3600000


class TemporalTests(unittest.TestCase):
    def setUp(self):
        self.cfg=replace(load_settings({}),ema_fast=2,ema_slow=3,ema_trend=4,atr_period=2)
        bars=tuple(Candle(i*H,100,101,99,100,10) for i in range(100))
        self.history=History('BTC/USDT','1h',0,100*H,100*H,bars,1,0)

    def test_nonoverlap_fullcoverage_and_prior_warmup(self):
        parts=windows(self.history,self.cfg)
        self.assertEqual(parts[0][0],12*H)
        self.assertEqual(parts[-1][1],100*H)
        for a,b in zip(parts,parts[1:]):self.assertEqual(a[1],b[0])
        for start,end,part in parts:
            self.assertEqual(start-part.start_ms,12*H)
            self.assertEqual(part.end_ms,end)
            self.assertLess(part.candles[-1].open_ms,end)

    def test_two_cost_scenarios_no_false_approval(self):
        result=evaluate(self.history,self.cfg)
        self.assertFalse(result['approved'])
        self.assertEqual(result['evaluated_variants'],2)
        self.assertEqual(result['scenarios'][1]['fee_rate'],'0.002')
        for scenario in result['scenarios']:
            for row in scenario['windows']:
                self.assertEqual(row['closed_trades'],0)
                self.assertEqual(row['final_equity'],20)

    def test_invalid_windows_and_short_history_rejected(self):
        for count in (True,1,13):
            with self.assertRaises(ValueError):windows(self.history,self.cfg,count)
        with self.assertRaises(ValueError):windows(self.history,self.cfg,12)

    def test_future_window_changes_do_not_change_first_result(self):
        first=evaluate(self.history,self.cfg)['scenarios'][0]['windows'][0]
        changed=tuple(Candle(b.open_ms,200,201,199,200,10) if i>=78 else b
                      for i,b in enumerate(self.history.candles))
        other=evaluate(replace(self.history,candles=changed),self.cfg)
        self.assertEqual(first,other['scenarios'][0]['windows'][0])
