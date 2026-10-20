import json
from pathlib import Path
import tempfile
import unittest
from shadow_view import load
from ai_shadow_run import run


class ShadowViewTests(unittest.TestCase):
    def test_missing_does_not_start_demo(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(load(Path(tmp)),{'status':'missing'})
            self.assertEqual(list(Path(tmp).iterdir()),[])
    def test_whitelisted_summary_does_not_expose_raw_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);folder=root/'reports/local/ai-shadow-offline';run(folder)
            path=folder/'demo-report.json';report=json.loads(path.read_text());report['secret']='never-expose';path.write_text(json.dumps(report))
            summary=load(root)
            self.assertEqual(summary['status'],'available');self.assertEqual(summary['orders'],0)
            self.assertNotIn('never-expose',json.dumps(summary));self.assertNotIn('response',summary)
    def test_report_claiming_trading_is_not_presented_as_offline(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);folder=root/'reports/local/ai-shadow-offline';run(folder)
            path=folder/'demo-report.json';report=json.loads(path.read_text());report['trading_enabled']=True;path.write_text(json.dumps(report))
            self.assertEqual(load(root),{'status':'invalid'})
    def test_non_json_report_is_unavailable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);path=root/'reports/local/ai-shadow-offline/demo-report.json';path.parent.mkdir(parents=True);path.write_text('not json')
            self.assertEqual(load(root),{'status':'invalid'})
