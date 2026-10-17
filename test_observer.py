import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import bot
import notifications
import observer


def market(stamp, price=100):
    histories = {'BTCUSDT': [{'time': stamp}]}
    quotes = {'BTCUSDT': {'bid': price - 1, 'ask': price + 1,
              'signals': {name: {'regime': 'tranquilo', 'target': 1.0}
                          for name in bot.research.STRATEGIES}}}
    return histories, quotes


class ObserverTests(unittest.TestCase):
    def test_first_sample_has_no_future_result(self):
        state, changed = observer.advance(None, *market(3600000), 'v1', 10000)
        self.assertTrue(changed)
        self.assertEqual(state['outcomes'], [])

    def test_same_candle_never_duplicates(self):
        state, _ = observer.advance(None, *market(3600000), 'v1', 10000)
        state, changed = observer.advance(state, *market(3600000, 200), 'v1', 10020)
        self.assertFalse(changed)
        self.assertEqual(len(state['snapshots']), 1)

    def test_result_uses_previously_recorded_signals(self):
        state, _ = observer.advance(None, *market(3600000), 'v1', 10000)
        histories, quotes = market(7200000, 110)
        for signal in quotes['BTCUSDT']['signals'].values():
            signal['target'] = 0
        state, _ = observer.advance(state, histories, quotes, 'v1', 13600)
        self.assertAlmostEqual(state['outcomes'][0]['market_return'], .1)
        self.assertEqual(state['outcomes'][0]['signals']['trend_v1']['target'], 1)

    def test_downtime_is_not_backfilled(self):
        state, _ = observer.advance(None, *market(3600000), 'v1', 10000)
        state, _ = observer.advance(state, *market(10800000), 'v1', 17200)
        self.assertEqual(state['gaps'], 1)
        self.assertEqual(state['outcomes'], [])

    def test_rule_change_preserves_session(self):
        state, _ = observer.advance(None, *market(3600000), 'v1', 10000)
        before = copy.deepcopy(state)
        with self.assertRaises(ValueError):
            observer.advance(state, *market(7200000), 'v2', 13600)
        self.assertEqual(state, before)

    def test_observation_never_creates_wallet_or_orders(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(bot, 'ROOT', Path(folder)):
            rows = [{'time': i * 3600000, 'close': 100.} for i in range(300)]
            config = bot.read(Path(__file__).parent / 'config.json')
            with patch.object(bot, 'candles', return_value=rows), patch.object(bot, 'quote', return_value={'bid': 99, 'ask': 101}), patch.object(bot, 'event') as event, patch.object(bot.research, 'fill', side_effect=AssertionError('No orders allowed')):
                bot.observe(config)
            self.assertFalse((Path(folder) / 'state.json').exists())
            self.assertTrue((Path(folder) / 'observation-state.json').exists())
            self.assertFalse(any(c.args[0] == 'paper_order' for c in event.call_args_list))

    def test_stop_blocks_observation_before_network(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(bot, 'ROOT', Path(folder)):
            (Path(folder) / 'STOP').touch()
            with patch.object(bot, 'candles', side_effect=AssertionError('No network after stop')):
                with self.assertRaises(ValueError):
                    bot.observe({})


class NotificationTests(unittest.TestCase):
    def test_unchanged_block_is_suppressed_today(self):
        item = {'kind': 'blocked', 'symbol': 'BTCUSDT', 'reason': 'Reprovada', 'time': '2026-10-17T01:00:00+00:00'}
        allowed, marker = notifications.should_send(item, {})
        self.assertTrue(allowed)
        key, day = marker
        self.assertFalse(notifications.should_send(item, {key: day})[0])
        item['time'] = '2026-10-18T01:00:00+00:00'
        self.assertTrue(notifications.should_send(item, {key: day})[0])

    def test_failed_delivery_does_not_suppress_retry(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(bot, 'ROOT', Path(folder)):
            with patch.object(bot, 'notify', return_value=False):
                bot.event('blocked', symbol='BTCUSDT', reason='Reprovada')
            self.assertFalse((Path(folder) / 'notifications-state.json').exists())

    def test_orders_are_never_suppressed(self):
        self.assertEqual(notifications.should_send({'kind': 'paper_order'}, {}), (True, None))


if __name__ == '__main__':
    unittest.main()
