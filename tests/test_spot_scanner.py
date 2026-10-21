import unittest
from types import SimpleNamespace
from unittest.mock import patch
from spot_engine.scanner import scan, SYMBOLS


class ScannerTests(unittest.TestCase):
    def test_pairs_are_observation_only_and_causal(self):
        history = SimpleNamespace(candles=[SimpleNamespace(close=100)])
        signal = SimpleNamespace(action='HOLD', reason='NO_CROSS', ema_fast=100,
                                 ema_slow=100, ema_trend=100, atr_fraction=.01)
        with patch('spot_engine.scanner.download', return_value=history) as download, patch('spot_engine.scanner.analyze', return_value=[signal]):
            report = scan(object(), 1000*3600000+123)
        self.assertEqual([p['symbol'] for p in report['pairs']], list(SYMBOLS))
        self.assertEqual(report['simulated_orders'], 0)
        self.assertFalse(report['approved'])
        self.assertEqual(report['timeframe'], '15m')
        for call in download.call_args_list:
            self.assertEqual(call.args[-1], 1000*3600000)
            self.assertEqual(call.args[-2], 1000*3600000-620*900000)

    def test_optional_hourly_and_invalid_timeframe(self):
        with patch('spot_engine.scanner.download', side_effect=ValueError):
            self.assertEqual(scan(object(), 1000*3600000, '1h')['timeframe'], '1h')
        with self.assertRaises(ValueError):
            scan(object(), 1000*3600000, '1m')

    def test_failure_cannot_reuse_signal(self):
        with patch('spot_engine.scanner.download', side_effect=ValueError('private')):
            result = scan(object(), 1000*3600000)
        self.assertTrue(all(p['action'] is None for p in result['pairs']))
        self.assertNotIn('private', str(result))
