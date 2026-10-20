from dataclasses import replace
from contextlib import closing
from decimal import Decimal as D, localcontext
from pathlib import Path
import json
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from spot_engine.config import load_settings
from spot_engine.risk import Account, Rules, RiskManager, RiskError

DAY=86400000


def account(equity='20',positions=0,pending=0):
    return Account(D(equity),D(equity) if not positions else D(equity)/2,positions,pending)


def rules(now=1000,minimum='1'):
    return Rules('BTC/USDT',now,D('.000001'),D('.000001'),D('100'),D('.01'),D('.01'),D('10000000'),D(minimum),D('1000000'))


class RiskTests(unittest.TestCase):
    def manager(self,root):
        m=RiskManager(root,load_settings({}));m.initialize(account(),1000);return m

    def test_size_includes_both_fees_slippage_and_stop(self):
        with tempfile.TemporaryDirectory() as tmp:
            m=self.manager(tmp);p=m.plan_entry(account(),D('100'),rules(),1000,1000)
            self.assertEqual(p.reason,'CANDIDATE_ONLY')
            self.assertGreater(p.quantity,0);self.assertLess(p.stop,p.entry)
            self.assertLessEqual(p.estimated_cost,D('5'))
            self.assertLessEqual(p.estimated_stop_loss,D('.20'))
            self.assertEqual(p.quantity % rules().qty_step,0)
            self.assertFalse(p.execution_authorized)
            expected=p.quantity*(p.entry*(1+m.cfg.fee_rate)-p.stop*(1-m.cfg.slippage_rate)*(1-m.cfg.fee_rate))
            self.assertEqual(p.estimated_stop_loss,expected)

    def test_minimum_never_increases_order_or_risk(self):
        with tempfile.TemporaryDirectory() as tmp:
            m=self.manager(tmp)
            self.assertEqual(m.plan_entry(account(),D('100'),rules(minimum='5'),1000,1000).reason,'MINIMUM_OR_LOT')

    def test_daily_loss_latches_after_recovery_and_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            m=self.manager(tmp);self.assertEqual(m.assess(account('19.4'),2000).reason,'DAILY_LOSS')
            m=RiskManager(tmp,load_settings({}))
            self.assertEqual(m.assess(account('20'),3000).reason,'DAILY_LOSS')
            self.assertEqual([x[2] for x in m.events()],['DAILY_LOSS'])
            self.assertTrue(m.assess(account('20'),DAY+1).can_enter)

    def test_drawdown_persists_across_new_day_and_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            m=self.manager(tmp);self.assertEqual(m.assess(account('18'),2000).reason,'DRAWDOWN')
            m=RiskManager(tmp,load_settings({}))
            self.assertEqual(m.assess(account('20'),DAY+1).reason,'DRAWDOWN')
            self.assertIn('DRAWDOWN',[x[2] for x in m.events()])

    def test_drawdown_uses_peak_not_initial_balance(self):
        with tempfile.TemporaryDirectory() as tmp:
            m=self.manager(tmp);m.assess(account('22'),2000)
            self.assertEqual(m.assess(account('19.8'),3000).reason,'DRAWDOWN')

    def test_remaining_daily_budget_caps_the_proposal(self):
        with tempfile.TemporaryDirectory() as tmp:
            m=self.manager(tmp);a=account('19.41');p=m.plan_entry(a,D('100'),rules(minimum='.1'),2000,2000)
            self.assertEqual(p.reason,'CANDIDATE_ONLY')
            self.assertLessEqual(p.estimated_stop_loss,D('.01'))

    def test_stop_blocks_entry_and_reduction_records_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            m=self.manager(tmp);(Path(tmp)/'STOP').touch()
            self.assertEqual(m.plan_entry(account(),D('100'),rules(),2000,2000).reason,'STOP')
            self.assertEqual(m.assess_reduction(account('20',1),2000,D('1'),D('1')),'STOP')
            self.assertEqual([e[2] for e in m.events()],['STOP'])

    def test_loss_halts_allow_only_inventory_reductions(self):
        with tempfile.TemporaryDirectory() as tmp:
            m=self.manager(tmp);a=account('18',1)
            self.assertEqual(m.assess_reduction(a,2000,D('1'),D('1')),'REDUCTION_CANDIDATE_ONLY')
            self.assertEqual(m.assess_reduction(a,2000,D('2'),D('1')),'INVALID_INVENTORY')
            self.assertEqual(m.assess_reduction(account('18'),2000,D('1'),D('1')),'INVALID_INVENTORY')

    def test_existing_or_pending_position_blocks_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            m=self.manager(tmp)
            for a in (account('20',1),account('20',pending=1)):
                self.assertEqual(m.plan_entry(a,D('100'),rules(),2000,2000).reason,'POSITION_LIMIT')

    def test_missing_corrupt_and_config_changed_fail_closed(self):
        for fault in ('missing','empty','flag','config'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as tmp:
                m=self.manager(tmp)
                if fault=='missing':m.path.unlink()
                elif fault=='config':m=RiskManager(tmp,replace(load_settings({}),risk_per_trade=D('.005')))
                else:
                    with closing(sqlite3.connect(m.path)) as db:
                        state={} if fault=='empty' else json.loads(db.execute('SELECT payload FROM checkpoint').fetchone()[0])
                        if fault=='flag':state['daily_halted']=0
                        db.execute('UPDATE checkpoint SET payload=?',(json.dumps(state),));db.commit()
                with self.assertRaises(RiskError):m.assess(account(),2000)
                with self.assertRaises(RiskError):m.initialize(account(),2000)

    def test_clock_rollback_does_not_reset_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            m=self.manager(tmp);m.assess(account('19.4'),2000)
            with self.assertRaises(RiskError):m.assess(account(),1000)
            self.assertEqual(m.assess(account(),3000).reason,'DAILY_LOSS')

    def test_initialization_requires_clean_account_and_never_resets(self):
        with tempfile.TemporaryDirectory() as tmp:
            m=RiskManager(tmp,load_settings({}))
            with self.assertRaises(RiskError):m.initialize(account('19'),1000)
            m.initialize(account(),1000)
            with self.assertRaises(RiskError):m.initialize(account(),2000)

    def test_stale_future_quote_and_filters_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            m=self.manager(tmp)
            for now,quote,metadata,reason in ((7000,1000,rules(),'STALE_QUOTE'),(1000,2000,rules(),'STALE_QUOTE'),(3601001,3601001,rules(),'STALE_RULES')):
                with self.subTest(reason=reason):self.assertEqual(m.plan_entry(account(),D('100'),metadata,now,quote).reason,reason)

    def test_invalid_values_and_multiple_positions_not_supported(self):
        for bad in (D('NaN'),D('Infinity'),D('-1'),True):
            with self.subTest(bad=bad),self.assertRaises(RiskError):Account(bad,D('0'))
        with self.assertRaises(RiskError):Account(D('20'),D('10'))
        with self.assertRaises(RiskError):RiskManager('.',replace(load_settings({}),max_positions=2))

    def test_no_network_or_execution_client(self):
        with tempfile.TemporaryDirectory() as tmp,patch('socket.socket',side_effect=AssertionError('Network forbidden')):
            m=self.manager(tmp);p=m.plan_entry(account(),D('100'),rules(),1000,1000)
            self.assertFalse(p.execution_authorized)
            self.assertFalse(hasattr(m,'place_order'))

    def test_exact_daily_threshold_and_invalid_filter_prices(self):
        with tempfile.TemporaryDirectory() as tmp:
            m=self.manager(tmp)
            self.assertTrue(m.assess(account('19.400001'),2000).can_enter)
            self.assertFalse(m.assess(account('19.4'),3000).can_enter)
        with tempfile.TemporaryDirectory() as tmp:
            m=self.manager(tmp)
            coarse=replace(rules(),price_tick=D('100'))
            self.assertEqual(m.plan_entry(account(),D('1'),coarse,1000,1000).reason,'PRICE_FILTER')

    def test_subprecision_and_invalid_snapshot_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            m=self.manager(tmp)
            with self.assertRaises(RiskError):m.plan_entry(account(),D('1e-1000'),rules(),1000,1000)
            with self.assertRaises(RiskError):m.assess({'equity':20},1000)

    def test_decimal_results_do_not_depend_on_callers_precision(self):
        with tempfile.TemporaryDirectory() as tmp:
            m=self.manager(tmp);expected=m.plan_entry(account(),D('100'),rules(),1000,1000)
            with localcontext() as context:
                context.prec=6
                actual=m.plan_entry(account(),D('100'),rules(),1000,1000)
            self.assertEqual(actual,expected)

    def test_stop_check_failure_is_not_permission_to_trade(self):
        with tempfile.TemporaryDirectory() as tmp:
            m=self.manager(tmp)
            with patch.object(m,'_stopped',side_effect=RiskError('STOP unavailable')):
                with self.assertRaises(RiskError):m.plan_entry(account(),D('100'),rules(),1000,1000)
            self.assertTrue(m.assess(account(),1000).can_enter)
