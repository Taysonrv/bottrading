import unittest
import market_view


class MarketViewTests(unittest.TestCase):
    def setUp(self):
        self.now=22000*86400+100
        day=22000*86400
        self.intraday=[[int(day-(59-i)*900)*1000,100,110,90,100,0,
                       int(day-(58-i)*900)*1000-1] for i in range(60)]
        self.daily=[[int(day-(249-i)*86400)*1000,100,110,90,100,0,
                    int(day-(248-i)*86400)*1000-1] for i in range(250)]
    def get(self,path):
        return self.intraday if 'interval=15m' in path else self.daily
    def test_incomplete_daily_close_does_not_change_exit_reference(self):
        self.daily[-1][4]=999999
        r=market_view.load('BTCUSDT',self.get,self.now)
        self.assertEqual(r['sma200'],100)
        self.assertEqual(r['next_close_reference'],100)
        self.assertFalse(r['candles'][-1]['closed'])
    def test_gap_is_rejected(self):
        del self.intraday[10]
        with self.assertRaises(ValueError):
            market_view.load('BTCUSDT',self.get,self.now)
    def test_stale_candles_are_rejected(self):
        with self.assertRaises(ValueError):
            market_view.load('BTCUSDT',self.get,self.now+3600)
    def test_unknown_pair_never_fetches(self):
        def no_fetch(path):
            raise AssertionError('Unexpected network call')
        with self.assertRaises(ValueError):
            market_view.load('OTHER',no_fetch,self.now)
