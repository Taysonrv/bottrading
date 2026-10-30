import csv
import io
from decimal import Decimal as D
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
from paper_export import export,safe_cell
from paper12_feasibility import assess
from upgrade_readiness import build
from tests.test_portfolio import rules
from spot_engine.main import save


class UpgradePackageTests(TestCase):
    def test_export_complete_not_last_hundred_and_exact_costs(self):
        fills=[]
        for i in range(101):
            fills.extend([dict(side='BUY',symbol='LINK/USDT',quantity='1',price='10',fee='.01',time_ms=i*2),
                dict(side='SELL',symbol='LINK/USDT',quantity='1',price='10.02',fee='.01002',time_ms=i*2+1,reason='SIGNAL_EXIT')])
        with patch('paper_export.ledger',return_value=dict(fills=fills,realized='-.00202')):
            cycles=list(csv.DictReader(io.StringIO(export('.', 'cycles').decode('utf-8-sig'))))
            rows=list(csv.DictReader(io.StringIO(export('.', 'fills').decode('utf-8-sig'))))
        self.assertEqual(len(cycles),101);self.assertEqual(len(rows),202)
        self.assertEqual(sum(D(r['net_pnl']) for r in cycles),D('-.00202'))

    def test_csv_formula_injection_and_negative_numbers(self):
        for value in ('=SUM(A1)','  @bad','\t+CMD','-not-a-number'):
            self.assertTrue(safe_cell(value).startswith("'"))
        self.assertEqual(safe_cell('-.127'), '-.127')
        with self.assertRaises(ValueError):export('.', '../secret')

    def test_cost_screen_never_is_market_signal(self):
        a=assess(rules('LINK/USDT'),D('99.99'),D(100),1000)
        self.assertTrue(a['mechanically_feasible']);self.assertLess(D(a['flat_bid_roundtrip_pnl']),0)
        self.assertFalse(a['is_market_signal']);self.assertFalse(a['execution_authorized'])
        self.assertFalse(assess(rules('LINK/USDT',minimum='10'),D('99.99'),D(100),1000)['mechanically_feasible'])
        with self.assertRaises(ValueError):assess(rules(),D(101),D(100),1000)

    def test_checklist_blocks_parallel_or_open_inventory(self):
        with TemporaryDirectory() as tmp:
            current=Path(tmp)/'current';next_root=Path(tmp)/'next';(current/'reports/local/portfolio').mkdir(parents=True);next_root.mkdir()
            save(current/'reports/local/portfolio/plan.json',dict(start_ms=100,end_ms=200000))
            save(next_root/'portfolio12.json',{'variant':'PAPER12_V1'})
            with patch('upgrade_readiness.ledger',return_value=dict(position={'symbol':'SOL/USDT'},pending=None,halt=None)):
                a=build(current,next_root,100000)
            checks={r['check']:r['passed'] for r in a['checks']}
            self.assertFalse(checks['CURRENT_SESSION_ENDED']);self.assertFalse(checks['NO_REMAINING_EXPOSURE'])
            self.assertFalse(a['ready_for_operator_review']);self.assertFalse(a['execution_authorized'])
