import unittest
from micro_research import simulate


def history(prices):
    return {'BTCUSDT':[dict(open_time=i*60000,open=p,high=p,low=p,close=p)
                       for i,p in enumerate(prices)]}


class MicroResearchTests(unittest.TestCase):
    def sample(self, ending):
        return history([99]*40+[101]*19+[100.5]+ending)

    def test_budget_and_profit_after_closed_signal(self):
        r=simulate(self.sample([100.5,102,102]),.0025)
        buy,sell=r['orders'][:2]
        self.assertLessEqual(buy['quantity']*buy['price']+buy['fee'],25.00000001)
        self.assertEqual(sell['time'],62*60000)
        self.assertGreater(sell['realized_pnl'],0)
        self.assertAlmostEqual(r['pnl'],r['realized']+r['unrealized'])

    def test_gap_can_lose_after_profit_signal(self):
        r=simulate(self.sample([103,80,80]),.0025)
        self.assertLess(r['realized'],0)

    def test_stop_prevents_every_order(self):
        self.assertEqual(simulate(self.sample([102,102]),.0025,stop=lambda:True)['orders'],[])

    def test_flat_and_downtrend_do_not_force_entries(self):
        for prices in ([100]*80,[100-i*.1 for i in range(80)]):
            self.assertEqual(simulate(history(prices),.0025)['orders'],[])

    def test_rejects_missing_and_gapped_history(self):
        for data in ({},history([100]*61)):
            with self.assertRaises(ValueError):
                simulate(data,.0025)
        data=self.sample([102,102])
        data['BTCUSDT'][-1]['open_time']+=60000
        with self.assertRaises(ValueError):
            simulate(data,.0025)
