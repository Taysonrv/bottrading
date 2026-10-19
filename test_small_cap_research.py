import unittest
from small_cap_research import quantity,simulate
from test_small_cap_scan import meta


class SmallCapitalResearchTests(unittest.TestCase):
    def test_five_including_costs_cannot_buy_five_minimum(self):
        self.assertEqual(quantity(meta(),100,budget=5),0)

    def test_budget_includes_fee_and_slippage(self):
        q=quantity(meta('1'),100,budget=5)
        self.assertGreater(q,0)
        self.assertLessEqual(q*100*1.001*1.001,5)

    def test_exit_below_minimum_retains_inventory(self):
        self.assertEqual(quantity(meta('5'),90,units=.05),0)

    def test_stop_no_orders_and_single_position_budget(self):
        prices=[100+i*.01 for i in range(80)]
        rows=[dict(open_time=i*3600000,open=p,high=p,low=p,close=p) for i,p in enumerate(prices)]
        histories={'BTCUSDT':rows,'ETHUSDT':rows};metadata={s:meta('1') for s in histories}
        self.assertEqual(simulate(histories,metadata,.25,stop=lambda:True)['orders'],[])
        r=simulate(histories,metadata,.25)
        self.assertEqual(r['buys'],1)
        self.assertGreaterEqual(r['cash'],15)
        self.assertAlmostEqual(r['pnl'],r['realized']+r['unrealized'])
