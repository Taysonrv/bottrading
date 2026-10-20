import unittest
from live_small_paper import advance
from test_small_cap_scan import meta


class LiveSmallTests(unittest.TestCase):
    def state(self):
        return dict(cash=20.,peak=20.,realized=0.,position=None,orders=[],curve=[],halted=False)
    def data(self):
        return {'BTCUSDT':[dict(open_time=i*3600000,close=100+i*.01) for i in range(60)]}
    def test_buy_budget_then_profitable_sell(self):
        s=self.state();m={'BTCUSDT':meta('1')};h=self.data()
        advance(s,m,h,{'BTCUSDT':dict(bid=100.59,ask=100.60)},1,lambda:False)
        self.assertEqual(s['orders'][0]['side'],'BUY');self.assertGreaterEqual(s['cash'],15)
        advance(s,m,h,{'BTCUSDT':dict(bid=103,ask=103.01)},2,lambda:False)
        self.assertEqual(s['orders'][-1]['side'],'SELL');self.assertGreater(s['realized'],0)
    def test_stop_and_minimum_block_orders(self):
        for minimum,stop in [('5',False),('1',True)]:
            s=self.state();advance(s,{'BTCUSDT':meta(minimum)},self.data(),{'BTCUSDT':dict(bid=100.59,ask=100.60)},1,lambda:stop)
            self.assertEqual(s['orders'],[])
    def test_drawdown_latches(self):
        s=self.state();s.update(cash=15.,position=dict(symbol='BTCUSDT',units=.05,cost=5.))
        advance(s,{'BTCUSDT':meta('1')},self.data(),{'BTCUSDT':dict(bid=1,ask=1.01)},1,lambda:False)
        self.assertTrue(s['halted']);self.assertEqual(s['orders'],[])
