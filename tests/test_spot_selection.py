from dataclasses import replace
from decimal import Decimal as D
import unittest
from spot_engine.risk import Rules
from spot_engine.selection import preview, choose


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.row=dict(symbol='BTC/USDT',status='OK',action='ENTER_LONG',candle_close_ms=900000)
        self.rules=Rules('BTC/USDT',900000,D('.00001'),D('.00001'),D('100'),D('.01'),D('.01'),D('1e7'),D('5'),D('1e8'))

    def check(self,**kwargs):
        return preview(self.row,self.rules,D('9999'),D('10000'),now_ms=900000,quote_ms=900000,**kwargs)

    def test_budget_includes_fee_and_lot_rounding(self):
        result=self.check()
        self.assertTrue(result['eligible'])
        self.assertLessEqual(D(result['estimated_cost']),D('6'))
        self.assertEqual(D(result['quantity'])%self.rules.qty_step,0)
        self.assertFalse(result['execution_authorized'])

    def test_does_not_enlarge_order_to_pass_minimum(self):
        self.assertEqual(self.check(budget=D('5'))['reason'],'MINIMUM_OR_NOTIONAL_FILTER')

    def test_position_pending_and_stop_block(self):
        self.assertFalse(self.check(positions=1)['eligible'])
        self.assertFalse(self.check(pending=1)['eligible'])
        self.assertEqual(self.check(stopped=True)['reason'],'STOP')

    def test_old_future_or_absent_signal_rejected(self):
        for close in (0,900001):
            self.row['candle_close_ms']=close
            self.assertEqual(self.check()['reason'],'STALE_SIGNAL')
        self.row['action']='HOLD'
        self.assertEqual(self.check()['reason'],'NO_ENTRY_SIGNAL')

    def test_filters_and_costs_cannot_be_bypassed(self):
        self.rules=replace(self.rules,symbol='ETH/USDT')
        self.assertEqual(self.check()['reason'],'INVALID_RULES')
        self.rules=replace(self.rules,symbol='BTC/USDT',observed_ms=900001)
        self.assertEqual(self.check()['reason'],'STALE_MARKET_DATA')

    def test_one_selection_deterministic_not_probability(self):
        rows=[dict(symbol='SOL/USDT',eligible=True,spread_fraction='.002'),dict(symbol='BTC/USDT',eligible=True,spread_fraction='.001')]
        self.assertEqual(choose(rows),'BTC/USDT')
        self.assertIsNone(choose([]))

    def test_wide_spread_rejected(self):
        result=preview(self.row,self.rules,D('9900'),D('10000'),now_ms=900000,quote_ms=900000)
        self.assertEqual(result['reason'],'WIDE_SPREAD')
