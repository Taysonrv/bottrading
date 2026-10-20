import unittest
from spot_strategy_suite import simulate,quartile_signal,STRATEGIES
from test_small_cap_scan import meta


class SpotSuiteTests(unittest.TestCase):
    def data(self):
        prices=[100]*60+[99]*20+[102]*20
        return {'DOGEUSDT':[dict(open_time=i*3600000,open=p,high=p,low=p,close=p) for i,p in enumerate(prices)]}
    def test_stop_blocks_all_strategies(self):
        for s in STRATEGIES:
            self.assertEqual(simulate(self.data(),{'DOGEUSDT':meta('1')},s,stop=lambda:True)['orders'],[])
    def test_dca_budget_and_accounting(self):
        r=simulate(self.data(),{'DOGEUSDT':meta('1')},'dca_spot')
        self.assertGreater(r['buys'],0)
        for o in r['orders']:
            self.assertLessEqual(o['quantity']*o['price']+o['fee'],5.0000001)
        self.assertAlmostEqual(r['pnl'],r['realized']+r['unrealized'])
    def test_quartile_flat_no_signal(self):
        self.assertEqual(quartile_signal([100]*26),0)
    def test_no_future_close_in_order_signal(self):
        h=self.data();a=simulate(h,{'DOGEUSDT':meta('1')},'dca_spot')
        h['DOGEUSDT'][-1].update(close=103,high=103)
        b=simulate(h,{'DOGEUSDT':meta('1')},'dca_spot')
        self.assertEqual(a['orders'],b['orders'])
