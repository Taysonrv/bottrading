from decimal import Decimal as D
import unittest
from unittest.mock import patch
from single_exit_audit import Audit, aggregate, compare
from single_exit_research import run
from tests.test_single_exit_research import hours, rules, signals


class CashflowAuditTests(unittest.TestCase):
    def test_observer_does_not_change_results_and_reconciles(self):
        journal=Audit(D('.001'))
        with patch('single_exit_research.analyze',signals):
            original=run(hours(),rules())
            observed=run(hours(),rules(),audit=journal)
        self.assertEqual(original,observed)
        self.assertEqual(len(journal.rows),1)
        totals=aggregate(journal.rows)
        self.assertEqual(D(totals['net_pnl']),D(original['net_realized']))
        self.assertEqual(D(totals['fees']),D(original['fees']))
        self.assertIsNone(journal.active)
        self.assertFalse(journal.rows[0]['execution_authorized'])

    def test_blocked_exit_keeps_inventory_and_records_no_fake_sale(self):
        journal=Audit(D('.001'))
        def crash(i,o,h,l,c):return (50,50.1,49.9,50) if i>=602 else (o,h,l,c)
        with patch('single_exit_research.analyze',signals):
            result=run(hours(change=crash),rules(),audit=journal)
        self.assertTrue(result['position_open'])
        self.assertEqual(journal.rows,[])
        self.assertIsNotNone(journal.active)
        self.assertEqual(journal.blocked,result['blocked_exit_attempts'])

    def test_saved_result_tampering_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'BASELINE_REPRODUCTION_FAILED'):
            compare({'cash':'19'},{'cash':'20'})

    def test_cashflow_tampering_is_rejected(self):
        journal=Audit(D('.001'))
        with patch('single_exit_research.analyze',signals):run(hours(),rules(),audit=journal)
        row=dict(journal.rows[0],net_pnl='999')
        with self.assertRaisesRegex(ValueError,'AUDIT_AGGREGATE_MISMATCH'):aggregate([row])

    def test_invalid_observer_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'AUDIT_CALLBACK_REQUIRED'):run(hours(),rules(),audit=True)

