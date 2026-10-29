from unittest import TestCase
from unittest.mock import Mock,patch
from expanded_radar import cycle,SYMBOLS
from spot_engine.scanner import scan


class ExpandedRadarTests(TestCase):
    def test_universe_validated_before_network(self):
        client=Mock()
        for universe in (('BTC/USDT','BTC/USDT'),(),('BTC/USDT','BTC/USDT:USDT')):
            with self.assertRaises(ValueError):scan(client,900000,symbols=universe)
        self.assertEqual(client.mock_calls,[])

    def test_signals_count_once_per_closed_bar_not_per_poll(self):
        client=Mock();client.fetch_time.return_value=900001
        report=dict(pairs=[dict(symbol=s,status='OK',action='ENTER_LONG',candle_close_ms=900000) for s in SYMBOLS])
        with patch('expanded_radar.scan',side_effect=lambda *a,**k:dict(report)):
            first=cycle(client);second=cycle(client,first)
        self.assertEqual(first['signal_counts'],second['signal_counts'])
        self.assertEqual(len(second['signal_counts']),12)
        self.assertEqual(second['simulated_orders'],0)
        self.assertFalse(second['execution_authorized'])

    def test_reversed_clock_refused(self):
        client=Mock();client.fetch_time.return_value=10
        with patch('expanded_radar.scan',return_value=dict(pairs=[])):
            with self.assertRaisesRegex(ValueError,'CLOCK_REVERSED'):cycle(client,dict(last_updated_ms=11))
