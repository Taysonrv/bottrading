import unittest
from small_cap_scan import assess,universe


def meta(minimum='5'):
    return dict(symbol='BTCUSDT',baseAsset='BTC',quoteAsset='USDT',status='TRADING',isSpotTradingAllowed=True,
                filters=[dict(filterType='LOT_SIZE',stepSize='.00001',minQty='.00001',maxQty='1000'),
                         dict(filterType='NOTIONAL',minNotional=minimum,maxNotional='1000000')])


class SmallCapTests(unittest.TestCase):
    def assess(self,minimum='5',ask='106',bid='105.99'):
        rows=[[i*3600000,str(100+i*.1),str(100+i*.1),str(100+i*.1),str(100+i*.1),'0',(i+1)*3600000-1] for i in range(60)]
        return assess(meta(minimum),dict(bidPrice=bid,askPrice=ask),rows,60*3600000)

    def test_signal_never_overrides_minimum_or_budget(self):
        r=self.assess()
        self.assertTrue(r['signal'])
        self.assertFalse(r['eligible'])
        self.assertLessEqual(r['estimated_cost'],1)

    def test_small_minimum_can_be_researched_without_rounding_up(self):
        self.assertTrue(self.assess('.1')['eligible'])

    def test_spread_blocks(self):
        self.assertFalse(self.assess('.1',bid='100')['eligible'])

    def test_invalid_quotes_fail_closed(self):
        with self.assertRaises(ValueError):
            self.assess(bid='107')

    def test_universe_requires_spot_and_liquidity(self):
        stable=meta();stable.update(symbol='USDCUSDT',baseAsset='USDC')
        info=dict(symbols=[meta(),stable])
        tickers=[dict(symbol='BTCUSDT',quoteVolume='10000001'),dict(symbol='USDCUSDT',quoteVolume='999999999')]
        self.assertEqual([s['symbol'] for s in universe(info,tickers)],['BTCUSDT'])
