import hashlib
import hmac
import io
import unittest
import urllib.error
import urllib.parse
from unittest.mock import Mock
import wallet


def fixtures():
    account = {'accountType': 'SPOT', 'balances': [
        {'asset': 'USDT', 'free': '100', 'locked': '20'},
        {'asset': 'BTC', 'free': '0.01', 'locked': '0.02'},
        {'asset': 'OLD', 'free': '4', 'locked': '0'}]}
    exchange = {'symbols': [{'baseAsset': 'BTC', 'quoteAsset': 'USDT', 'symbol': 'BTCUSDT',
                           'status': 'TRADING', 'isSpotTradingAllowed': True, 'filters': []}]}
    tickers = [{'symbol': 'BTCUSDT', 'bidPrice': '60000'}]
    return account, exchange, tickers


class WalletTests(unittest.TestCase):
    def test_locked_balances_never_enter_proposal(self):
        result = wallet.preview(*fixtures())
        self.assertEqual(result['paper_usdt_proposal'], '100')
        self.assertEqual(result['paper_positions_proposal'], {'BTCUSDT': '0.01'})
        self.assertEqual(result['supported_free_value_usdt'], '700.00')
        self.assertEqual(result['supported_locked_value_usdt'], '1220.00')
        self.assertEqual(result['unpriced_assets'], ['OLD'])

    def test_disabled_pair_is_not_in_proposal(self):
        account, exchange, tickers = fixtures()
        exchange['symbols'][0]['status'] = 'BREAK'
        result = wallet.preview(account, exchange, tickers)
        self.assertEqual(result['paper_positions_proposal'], {})
        self.assertIn('BTC', result['unpriced_assets'])

    def test_missing_price_is_not_zero_valuation(self):
        account, exchange, _ = fixtures()
        result = wallet.preview(account, exchange, [])
        btc = next(r for r in result['assets'] if r['asset'] == 'BTC')
        self.assertIsNone(btc['free_value_usdt'])
        self.assertFalse(btc['supported'])

    def test_nonfinite_balance_rejected(self):
        account, exchange, tickers = fixtures()
        account['balances'][0]['free'] = 'NaN'
        with self.assertRaises(wallet.WalletError):
            wallet.preview(account, exchange, tickers)

    def test_nonspot_account_rejected(self):
        account, exchange, tickers = fixtures()
        account['accountType'] = 'MARGIN'
        with self.assertRaises(wallet.WalletError):
            wallet.preview(account, exchange, tickers)

    def test_trading_endpoints_rejected_before_network(self):
        client = wallet.ReadOnlyClient('fake-key', 'fake-secret')
        client.opener = Mock()
        for endpoint in ('/api/v3/order', '/api/v3/order/test', '/sapi/v1/capital/withdraw/apply'):
            with self.assertRaises(wallet.WalletError):
                client.get(endpoint)
        client.opener.open.assert_not_called()

    def test_signed_request_uses_get_and_correct_hmac(self):
        client = wallet.ReadOnlyClient('fake-key', 'fake-secret')
        responses = [io.StringIO('{"serverTime":123456}'), io.StringIO('{"accountType":"SPOT","balances":[]}')]
        client.opener = Mock()
        client.opener.open.side_effect = responses
        client.get('/api/v3/account')
        req = client.opener.open.call_args_list[1].args[0]
        params = urllib.parse.parse_qs(urllib.parse.urlparse(req.full_url).query)
        expected = hmac.new(b'fake-secret', b'timestamp=123456&recvWindow=5000', hashlib.sha256).hexdigest()
        self.assertEqual(params['signature'], [expected])
        self.assertEqual(req.get_method(), 'GET')
        self.assertEqual(req.get_header('X-mbx-apikey'), 'fake-key')
        self.assertNotIn('fake-secret', req.full_url)

    def test_errors_do_not_expose_signed_urls(self):
        client = wallet.ReadOnlyClient('fake-key', 'fake-secret')
        client.opener = Mock()
        client.opener.open.side_effect = urllib.error.HTTPError('https://example.test/?signature=secret', 403, 'fake-secret', {}, None)
        with self.assertRaises(wallet.WalletError) as captured:
            client.get('/api/v3/exchangeInfo')
        self.assertNotIn('secret', str(captured.exception))

    def test_redirect_refused(self):
        with self.assertRaises(wallet.WalletError):
            wallet.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://other.test')

    def test_missing_credentials_rejected(self):
        with self.assertRaises(wallet.WalletError):
            wallet.ReadOnlyClient(None, None)


if __name__ == '__main__':
    unittest.main()
