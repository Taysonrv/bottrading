import json
from pathlib import Path
import tempfile
import unittest
from diagnosticar import inspect


class DiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.now=200000*3600+60
        self.report=self.root/'reports/local/live-small-paper.json';self.report.parent.mkdir(parents=True)
        self.report.write_text(json.dumps(dict(phase='error',position={'symbol':'DOGEUSDT'})))
    def tearDown(self):self.tmp.cleanup()
    def get(self,path):
        if path=='time':return {'serverTime':self.now*1000}
        if path.startswith('ticker/'):return {'bidPrice':'.08','askPrice':'.08001'}
        end=int(self.now)//3600*3600000
        return [[end-(60-i)*3600000,100,101,99,100] for i in range(60)]
    def test_success_keeps_wallet_unchanged(self):
        before=self.report.read_bytes();report=inspect(self.root,self.get,self.now)
        self.assertTrue(all(c['ok'] for c in report['checks']))
        self.assertFalse(report['trading_enabled']);self.assertEqual(self.report.read_bytes(),before)
    def test_missing_hour_is_not_silently_accepted(self):
        def get(path):
            result=self.get(path)
            return result[:-1] if path.startswith('klines') else result
        report=inspect(self.root,get,self.now)
        self.assertFalse(next(c['ok'] for c in report['checks'] if c['check']=='candles'))
    def test_network_errors_do_not_print_exception_urls(self):
        def get(path):raise OSError('secret-url')
        report=inspect(self.root,get,self.now)
        self.assertNotIn('secret-url',json.dumps(report))
        self.assertFalse(next(c['ok'] for c in report['checks'] if c['check']=='cotacao'))
    def test_stop_is_not_removed(self):
        (self.root/'STOP').touch();report=inspect(self.root,self.get,self.now)
        self.assertFalse(next(c['ok'] for c in report['checks'] if c['check']=='stop'))
        self.assertTrue((self.root/'STOP').exists())
