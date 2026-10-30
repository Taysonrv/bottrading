from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
import json
from research_desk import ROOT,evaluate_saved,run


class ResearchDeskTests(TestCase):
    def test_real_rejected_result_never_becomes_winner(self):
        r=json.loads((ROOT/'research_results/single-exit-20261025.json').read_text(encoding='utf-8-sig'))
        e=evaluate_saved('ema_single_exit','known',r)
        self.assertEqual(e['status'],'REJECTED');self.assertIsNone(e['score_25'])
        self.assertFalse(e['independent_oos']);self.assertFalse(e['execution_authorized'])

    def test_missing_or_forged_oos_cannot_authorize(self):
        e=evaluate_saved('ema_single_exit','test',{'independent_oos':True,'approved':True})
        self.assertEqual(e['status'],'REJECTED');self.assertFalse(e['approved'])
        self.assertFalse(next(c for c in e['checks'] if c['check']=='UNTOUCHED_OOS_EVIDENCE')['passed'])

    def test_one_pipeline_preserves_history_and_never_creates_wallet(self):
        with TemporaryDirectory() as tmp:
            a=run(tmp);b=run(tmp)
            self.assertNotEqual(a['run_id'],b['run_id'])
            self.assertEqual(a['approved_strategies'],[])
            self.assertEqual(a['builder_status'],'BLOCKED_NO_VALIDATED_STRATEGY')
            self.assertEqual(len(a['evaluations']),3)
            self.assertIn('WHY THIS COULD FAIL',a['brief'])
            self.assertFalse(a['scheduled'])
            self.assertTrue((Path(tmp)/'reports/local/research-desk'/a['run_id']/'manifest.json').is_file())
            self.assertFalse((Path(tmp)/'reports/local/portfolio/paper.sqlite').exists())

    def test_unknown_schema_does_not_rank_as_valid(self):
        e=evaluate_saved('unknown','x',{'net_return':10,'closed_trades':1000})
        self.assertEqual(e['status'],'REJECTED');self.assertEqual(e['metrics'],{})

    def test_wrong_csv_cannot_replace_a_report_with_fake_evidence(self):
        with TemporaryDirectory() as tmp:
            csv=Path(tmp)/'wrong.csv';csv.write_text('not the original history')
            with self.assertRaisesRegex(ValueError,'KNOWN_EXPLORATORY_CSV_REQUIRED'):run(tmp,csv)
            folder=Path(tmp)/'reports/local/research-desk'
            self.assertEqual(len(list(folder.glob('*/manifest.json'))),1)
            self.assertFalse((folder/'latest.json').exists())
