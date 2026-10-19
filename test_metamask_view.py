import json
from pathlib import Path
import tempfile
import unittest
from metamask_view import load


class MetamaskViewTests(unittest.TestCase):
    def test_missing_reports_are_explicit_and_not_executed(self):
        with tempfile.TemporaryDirectory() as folder:
            r=load(folder)
            self.assertEqual(r['quotes']['results'],[])
            self.assertFalse(r['executed'])

    def test_excludes_raw_transactions_and_simulation_logs(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'reports/local';p.mkdir(parents=True)
            (p/'solana-cost-research.json').write_text(json.dumps({'legs':[{'leg':'venda','fee_lamports':15000,'logs':['private'],'swapTransaction':'payload'}]}))
            r=load(folder)
            self.assertEqual(r['costs']['legs'][0]['fee_lamports'],15000)
            self.assertNotIn('logs',r['costs']['legs'][0])
            self.assertNotIn('swapTransaction',r['costs']['legs'][0])
