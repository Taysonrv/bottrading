import tempfile
import urllib.error
import unittest
from unittest.mock import Mock
from external_context import fear,ticker,pools,cycle


class ContextTests(unittest.TestCase):
    def test_index_bounds_and_future_rejected(self):
        raw=dict(data=[dict(value='50',timestamp='1000')])
        self.assertEqual(fear(raw,1000000)['value'],50)
        raw['data'][0]['value']='101'
        with self.assertRaises(ValueError):fear(raw,1000000)
        raw['data'][0].update(value='50',timestamp='2000')
        with self.assertRaises(ValueError):fear(raw,1000000)

    def test_ticker_identity_and_timestamp_validated(self):
        raw=dict(id='btc-bitcoin',symbol='BTC',last_updated='2026-10-21T00:00:00Z',quotes=dict(USD=dict(price=100,volume_24h=1000)))
        self.assertEqual(ticker(raw,'btc-bitcoin',1792620000000)['usd_price'],100)
        raw['symbol']='FAKE'
        with self.assertRaises(ValueError):ticker(raw,'btc-bitcoin',1792620000000)

    def test_pool_sample_not_wallet_and_null_is_not_zero(self):
        raw=dict(data=[dict(type='pool',attributes=dict(name='A / B',reserve_in_usd='100',volume_usd=dict(h24='2')))])
        self.assertEqual(pools(raw,'bsc')[0]['liquidity_usd'],100)
        raw['data'][0]['attributes']['reserve_in_usd']=None
        with self.assertRaises((ValueError,TypeError)):pools(raw,'bsc')

    def test_provider_failures_independent_and_cached(self):
        with tempfile.TemporaryDirectory() as tmp:
            def get(url):
                if 'alternative' in url:return dict(data=[dict(value='50',timestamp='1000')])
                raise OSError('offline')
            mock=Mock(side_effect=get)
            first=cycle(tmp,mock,now=1000)
            self.assertEqual(first['sources']['alternative']['status'],'OK')
            self.assertEqual(first['sources']['coinpaprika']['status'],'UNAVAILABLE')
            self.assertFalse(first['execution_authorized'])
            count=mock.call_count;cycle(tmp,mock,now=1100)
            self.assertEqual(mock.call_count,count)
            second=cycle(tmp,Mock(side_effect=OSError('down')),now=30000)
            self.assertEqual(second['sources']['alternative']['status'],'UNAVAILABLE')
            self.assertEqual(second['sources']['alternative']['data']['value'],50)

    def test_gecko_partial_results_survive_rate_limit(self):
        from external_context import collect
        def get(url):
            if 'bsc' in url:return dict(data=[dict(type='pool',attributes=dict(name='A/B',reserve_in_usd='10',volume_usd=dict(h24='1')))])
            raise urllib.error.HTTPError(url,429,'limit',None,None)
        data=collect('geckoterminal',get,1000000)
        self.assertTrue(data['partial']);self.assertTrue(data['rate_limited'])
        self.assertEqual(len(data['pools']),1)
        self.assertEqual(data['networks']['solana'],'DEFERRED_RATE_LIMIT')
