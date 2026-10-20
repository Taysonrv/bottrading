import unittest
from technical_strategies import atr,rsi,vwap,decision,NAMES


class TechnicalTests(unittest.TestCase):
    def rows(self):
        return [dict(open_time=i*3600000,open=100,high=101,low=99,close=100,volume=10) for i in range(60)]
    def test_rsi_wilder_extremes_and_flat(self):
        self.assertEqual(rsi(list(range(1,61))),100)
        self.assertEqual(rsi(list(range(60,0,-1))),0)
        self.assertEqual(rsi([100]*60),50)
    def test_atr_true_range_includes_gap(self):
        rows=self.rows();rows[-1].update(high=111,low=109,close=110)
        self.assertAlmostEqual(atr(rows),(13*2+11)/14)
    def test_vwap_volume_weights_and_zero_rejected(self):
        rows=[dict(high=10,low=10,close=10,volume=1),dict(high=20,low=20,close=20,volume=3)]
        self.assertEqual(vwap(rows),17.5)
        with self.assertRaises(ValueError):vwap([dict(volume=0)])
    def test_flat_has_no_forced_buys(self):
        for name in NAMES:
            self.assertFalse(decision(name,self.rows(),dict(units=0,cost=0))['buy'])
    def test_atr_stop_requires_position_and_no_averaging(self):
        r=decision('pullback_atr',self.rows(),dict(units=.05,cost=5,atr_stop=101,atr_target=110))
        self.assertTrue(r['sell']);self.assertFalse(r['buy'])
