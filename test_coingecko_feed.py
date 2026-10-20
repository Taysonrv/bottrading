import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
from coingecko_feed import update,normalize


class CoinGeckoTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.row=dict(id='bitcoin',current_price=100,market_cap=200,total_volume=30,price_change_percentage_24h=2,last_updated='2026-10-20T00:00:00Z')
        self.now=1792454400
    def tearDown(self):self.tmp.cleanup()
    def test_missing_key_never_calls_network(self):
        get=Mock();report=update(self.root,None,get,self.now)
        get.assert_not_called();self.assertEqual(report['status'],'disabled')
    def test_cached_attempt_survives_restart_without_key_persistence(self):
        get=Mock(return_value=[self.row]);update(self.root,'SECRET',get,self.now)
        update(self.root,'SECRET',get,self.now+60)
        self.assertEqual(get.call_count,1)
        self.assertNotIn('SECRET',(self.root/'reports/local/coingecko-context.json').read_text())
    def test_failure_preserves_previous_rows_and_throttles(self):
        update(self.root,'KEY',lambda _: [self.row],self.now)
        get=Mock(side_effect=OSError('SECRET URL'))
        report=update(self.root,'KEY',get,self.now+901)
        self.assertEqual(report['rows'][0]['price_usd'],100)
        self.assertEqual(report['status'],'error')
        self.assertNotIn('SECRET',json.dumps(report))
        update(self.root,'KEY',get,self.now+902);self.assertEqual(get.call_count,1)
    def test_negative_price_and_duplicate_identity_rejected(self):
        with self.assertRaises(ValueError):normalize([{**self.row,'current_price':-1}])
        with self.assertRaises(ValueError):normalize([self.row,self.row])
    def test_missing_optional_market_cap_is_not_zero(self):
        result=normalize([{**self.row,'market_cap':None}])
        self.assertIsNone(result[0]['market_cap_usd'])
