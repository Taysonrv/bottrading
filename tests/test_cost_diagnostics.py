import unittest
from spot_engine.cost_diagnostics import evaluate
from tests.test_layered_research import history


class CostDiagnosticsTests(unittest.TestCase):
    def test_all_scenarios_and_zero_trade_windows_remain_visible(self):
        result=evaluate(history([100.]*2000),2)
        self.assertEqual(len(result['rows']),16)
        self.assertEqual(result['evaluated_configurations'],8)
        self.assertFalse(result['approved']);self.assertFalse(result['execution_authorized'])
        self.assertEqual(set(r['scenario'] for r in result['rows']),{'no_costs','fees_only','slippage_only','base'})
        self.assertTrue(all(r['exit_reasons']=={} and r['mean_closed_trade_pnl'] is None for r in result['rows']))
        for row in result['rows']:
            if row['scenario']=='no_costs':
                self.assertEqual(row['fee_rate'],'0');self.assertEqual(row['slippage_rate'],'0')
                self.assertEqual(row['fees'],0)
            if row['scenario']=='fees_only':self.assertEqual(row['slippage_rate'],'0')
            if row['scenario']=='slippage_only':self.assertEqual(row['fee_rate'],'0')

    def test_short_history_refused(self):
        with self.assertRaises(ValueError):evaluate(history([100.]*100),2)
