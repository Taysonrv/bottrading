from dataclasses import replace
from decimal import Decimal as D
import unittest
from spot_engine.risk import Rules,RiskError
from spot_engine.v3_position_plan import Budget,plan

NOW=1700000000000


class PositionPlanTests(unittest.TestCase):
    def rules(self):return Rules('SOL/USDT',NOW,D('.001'),D('.001'),D('100000'),D('.01'),D('.01'),D('1000000'),D('5'),D('1000000'))
    def budget(self,capital='1000'):
        e=D(capital);return Budget(e,e,D(0),D(0),e*D('.03'),e*D('.1'))
    def call(self,budget=None,**changes):
        args=dict(ask=D('100'),atr=D('2'),score=100,now_ms=NOW,quote_ms=NOW);args.update(changes)
        return plan(self.rules(),budget or self.budget(),**args)
    def test_small_balance_refused_without_increasing_budget(self):
        b=self.budget('20');r=self.call(b)
        self.assertEqual(r['reason'],'STOP_FILTER');self.assertFalse(r['execution_authorized'])
        self.assertEqual(b.free_cash,D('20'))
        self.assertEqual(self.call(self.budget('50'))['reason'],'PARTIAL_EXIT_FILTER')
    def test_valid_plan_conserves_qty_and_all_risk_caps(self):
        b=self.budget();r=self.call(b)
        self.assertTrue(r['valid_research_plan']);self.assertFalse(r['approved'])
        self.assertFalse(r['execution_authorized'])
        self.assertEqual(sum(D(e['quantity']) for e in r['exits']),D(r['quantity']))
        self.assertLessEqual(D(r['estimated_cost']),b.equity*D('.4'))
        self.assertLessEqual(D(r['estimated_stop_loss']),b.equity*D('.01'))
        self.assertGreaterEqual(D(r['net_weighted_rr']),D('1.5'))
    def test_stop_stale_filters_duplicate_and_limit_block(self):
        self.assertEqual(self.call(replace(self.budget(),stopped=True))['reason'],'STOP')
        self.assertEqual(self.call(replace(self.budget(),same_symbol_open=True))['reason'],'SYMBOL_ALREADY_OPEN_OR_RESERVED')
        self.assertEqual(self.call(replace(self.budget(),positions=1,pending_entries=1))['reason'],'POSITION_LIMIT')
        self.assertEqual(self.call(quote_ms=NOW+1)['reason'],'STALE_OR_FUTURE_QUOTE')
        self.assertEqual(self.call(now_ms=NOW+3600001,quote_ms=NOW+3600001)['reason'],'STALE_OR_FUTURE_FILTERS')
    def test_remaining_loss_and_exposure_are_binding(self):
        b=replace(self.budget(),remaining_daily=D('1'))
        r=self.call(b)
        if r['valid_research_plan']:self.assertLessEqual(D(r['estimated_stop_loss']),D('1'))
        self.assertFalse(self.call(replace(self.budget(),free_cash=D('600'),exposure=D('400')))['valid_research_plan'])
    def test_invalid_and_low_score_inputs(self):
        with self.assertRaises(RiskError):self.call(ask=100.)
        with self.assertRaises(RiskError):self.call(score=True)
        self.assertEqual(self.call(score=60)['reason'],'SCORE_TOO_LOW')
    def test_cost_adjusted_rr_and_score_scaled_risk(self):
        self.assertEqual(self.call(atr=D('.51'))['reason'],'NET_WEIGHTED_RR_TOO_LOW')
        r=self.call(score=70)
        self.assertTrue(r['valid_research_plan'])
        self.assertLessEqual(D(r['estimated_stop_loss']),D('7'))
