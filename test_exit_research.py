import unittest
from exit_research import compare


def rows(prices):
    return [dict(open_time=i*60000,time=(i+1)*60000-1,open=p,high=p+1,low=p-1,close=p)
            for i,p in enumerate(prices)]


class ExitResearchTests(unittest.TestCase):
    def run_case(self,prices,policy,stop=lambda:False):
        return compare({'BTCUSDT':rows(prices)}, {'BTCUSDT':dict(quantity=.4,cost=40)},policy,stop)
    def test_target_fills_only_after_closed_signal(self):
        r=self.run_case([100,102,102,102],'take_profit_1pct')
        self.assertEqual(r['orders'][0]['time'],120000)
        self.assertGreater(r['realized_pnl'],0)
    def test_intraminute_high_alone_does_not_trigger(self):
        history=rows([100,100,100])
        for row in history:
            row['high']=120
        r=compare({'BTCUSDT':history},{'BTCUSDT':dict(quantity=.4,cost=40)},'take_profit_1pct')
        self.assertEqual(r['orders'],[])
    def test_gap_can_turn_target_into_realized_loss(self):
        r=self.run_case([100,102,80,80],'take_profit_1pct')
        self.assertLess(r['realized_pnl'],0)
    def test_trailing_arms_then_waits_for_pullback(self):
        r=self.run_case([100,102,103,102.4,102.2],'trailing_halfpct_after_1pct')
        self.assertEqual(r['orders'][0]['time'],240000)
    def test_hold_and_stop_do_not_sell(self):
        self.assertEqual(self.run_case([100,102,104],'hold')['orders'],[])
        self.assertEqual(self.run_case([100,102,104],'take_profit_1pct',lambda:True)['orders'],[])
