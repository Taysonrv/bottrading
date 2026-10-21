import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import kronos_view
from spot_engine.kronos_lab import summarize


class KronosViewTests(unittest.TestCase):
    def test_valid_report_and_inconsistent_bands(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);folder=root/'reports/local/kronos-lab';folder.mkdir(parents=True)
            paths=[[100,110],[102,112]]
            report=dict(scope='KRONOS_OBSERVE_ONLY',orders=0,approved=False,symbol='BTC/USDT',timeframe='1h',
                        cutoff_ms=3600000,issued_ms=3601000,samples=2,horizon=2,anchor_close=100,
                        paths=paths,bands=summarize(paths,2))
            path=folder/'latest.json';path.write_text(json.dumps(report),encoding='utf-8')
            with patch.object(kronos_view,'__file__',str(root/'kronos_view.py')):
                self.assertTrue(kronos_view.load(root)['available'])
                report['bands'][0]['p50']=999
                path.write_text(json.dumps(report),encoding='utf-8')
                self.assertEqual(kronos_view.load(root)['status'],'invalid')

    def test_missing_not_a_forecast(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            with patch.object(kronos_view,'__file__',str(root/'kronos_view.py')):
                result=kronos_view.load(root)
            self.assertFalse(result['available'])
            self.assertNotIn('paths',result)
