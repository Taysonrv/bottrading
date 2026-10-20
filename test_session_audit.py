import json
from pathlib import Path
import tempfile
import unittest
from session_audit import build,register
from paper_lab import save


class AuditTests(unittest.TestCase):
    def state(self):
        orders=[dict(time=1,symbol='DOGEUSDT',side='BUY',quantity=10,price=1,fee=.1,pnl=None),
                dict(time=2,symbol='DOGEUSDT',side='SELL',quantity=5,price=1.2,fee=.1,pnl=.85)]
        return dict(initial=20,cash=15.8,equity=20.8,pnl=.8,realized=.85,unrealized=-.05,
                    position=dict(symbol='DOGEUSDT',units=5,cost=5.05),orders=orders,updated=203,
                    curve=[dict(time=1,equity=20),dict(time=202,equity=19),dict(time=203,equity=20.8)])
    def test_partial_sale_reconciles_cost_and_fees(self):
        r=build(self.state(),300)
        self.assertTrue(r['reconciled'],r['issues'])
        self.assertAlmostEqual(r['fees'],.2)
        self.assertAlmostEqual(r['average_win'],.85)
        self.assertIsNone(r['profit_factor'])
        self.assertEqual(r['gaps_over_180s'],1)
        self.assertAlmostEqual(r['saved_curve_drawdown'],.05)
    def test_disagreement_does_not_certify(self):
        s=self.state();s['cash']=999
        self.assertFalse(build(s)['reconciled'])
    def test_missing_buy_is_not_a_valid_history(self):
        s=self.state();s['orders']=s['orders'][1:]
        self.assertFalse(build(s)['reconciled'])
    def test_closed_ledger_cannot_hide_open_position(self):
        s=self.state();s['position']['units']=10
        self.assertFalse(build(s)['reconciled'])
    def test_no_benchmark_or_annualized_sharpe_invented(self):
        r=build(self.state());self.assertIsNone(r['benchmarks']['buy_hold'])
        self.assertFalse(r['approved']);self.assertNotIn('sharpe',r)
    def test_registry_keeps_snapshots_but_counts_configuration_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);folder=root/'reports/local';folder.mkdir(parents=True)
            path=folder/'spot-suite.json'
            data=dict(capital=20,comparisons=[dict(strategy='ma',stress=1,pnl=-1)])
            save(path,data);r=register(root);save(folder/'research-registry.json',r)
            self.assertEqual(len(register(root)['studies']),1)
            data['comparisons'][0]['pnl']=2;save(path,data)
            r=register(root)
            self.assertEqual(len(r['studies']),2);self.assertEqual(len(r['variants']),1)
            self.assertFalse(r['approved'])

    def test_closed_wallet_equity_must_equal_cash(self):
        s=dict(initial=20,cash=20,equity=25,pnl=5,realized=0,unrealized=5,position=None,orders=[],curve=[],updated=100)
        self.assertFalse(build(s,200)['reconciled'])

    def test_open_position_cannot_have_negative_marked_value(self):
        s=self.state();s.update(equity=10,pnl=-10,unrealized=-10.85)
        self.assertFalse(build(s,300)['reconciled'])

    def test_malformed_position_is_reported_without_crashing(self):
        for position in ([], 'invalid', {'symbol': 'DOGEUSDT', 'units': True, 'cost': 5.05}):
            with self.subTest(position=position):
                s=self.state();s['position']=position
                self.assertFalse(build(s,300)['reconciled'])

    def test_future_order_cannot_reconcile(self):
        s=self.state();s['orders'][-1]['time']=400
        self.assertFalse(build(s,300)['reconciled'])

    def test_future_measurement_and_curve_cannot_reconcile(self):
        s=self.state();s['updated']=400
        self.assertFalse(build(s,300)['reconciled'])
        s=self.state();s['curve'][-1]['time']=204
        self.assertFalse(build(s,300)['reconciled'])

    def test_nonfinite_arithmetic_is_not_a_reconciled_ledger(self):
        s=self.state();s['orders'][0].update(quantity=1e308,price=1e308)
        self.assertFalse(build(s,300)['reconciled'])
