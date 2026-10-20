import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
from coingecko_feed import update,normalize,clean_key


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
        get=Mock(return_value=[self.row]);update(self.root,'CG-fixture0000000000',get,self.now)
        update(self.root,'CG-fixture0000000000',get,self.now+60)
        self.assertEqual(get.call_count,1)
        self.assertNotIn('CG-fixture0000000000',(self.root/'reports/local/coingecko-context.json').read_text())
    def test_failure_preserves_previous_rows_and_throttles(self):
        update(self.root,'CG-fixture0000000000',lambda _: [self.row],self.now)
        get=Mock(side_effect=OSError('SECRET URL'))
        report=update(self.root,'CG-fixture0000000000',get,self.now+901)
        self.assertEqual(report['rows'][0]['price_usd'],100)
        self.assertEqual(report['status'],'error')
        self.assertNotIn('CG-fixture0000000000',json.dumps(report))
        update(self.root,'CG-fixture0000000000',get,self.now+902);self.assertEqual(get.call_count,1)
    def test_negative_price_and_duplicate_identity_rejected(self):
        with self.assertRaises(ValueError):normalize([{**self.row,'current_price':-1}])
        with self.assertRaises(ValueError):normalize([self.row,self.row])
    def test_missing_optional_market_cap_is_not_zero(self):
        result=normalize([{**self.row,'market_cap':None}])
        self.assertIsNone(result[0]['market_cap_usd'])

    def test_copied_url_or_quotes_are_normalized_locally(self):
        key='CG-fixture0000000000'
        self.assertEqual(clean_key(' "'+key+'" '),key)
        self.assertEqual(clean_key('https://api.coingecko.com/api/v3/simple/price?x_cg_demo_api_key='+key),key)
        with self.assertRaises(ValueError):clean_key('https://evil.example/?x_cg_demo_api_key='+key)
    def test_http_status_is_safe_and_specific(self):
        from urllib.error import HTTPError
        def get(_):raise HTTPError('https://private-secret',401,'private-secret',None,None)
        report=update(self.root,'CG-fixture0000000000',get,self.now)
        self.assertEqual(report['error_code'],'HTTP_401')
        self.assertNotIn('private-secret',json.dumps(report))
    def test_explicit_check_can_retry_failed_cache_once(self):
        get=Mock(side_effect=[OSError('fail'),[self.row]])
        update(self.root,'CG-fixture0000000000',get,self.now)
        report=update(self.root,'CG-fixture0000000000',get,self.now+1,force=True)
        self.assertEqual(report['status'],'ok');self.assertIsNone(report['error_code'])
        self.assertEqual(get.call_count,2)
