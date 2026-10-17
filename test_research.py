import unittest
from unittest.mock import patch
import bot
import research


def bars(count=320):
    return [{'open_time': i * research.HOUR, 'time': (i + 1) * research.HOUR - 1,
             'open': 100., 'high': 101., 'low': 99., 'close': 100.} for i in range(count)]


class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.config = bot.read(bot.ROOT / 'config.json')

    def test_fees_and_slippage_reduce_round_trip(self):
        cash, units, buy = research.fill(1000, 0, 100, 1000, .001, .001)
        self.assertAlmostEqual(cash, 0)
        cash, units, sell = research.fill(cash, units, 100, -units * 100, .001, .001)
        self.assertEqual(units, 0)
        self.assertLess(cash, 1000)
        self.assertAlmostEqual(buy['price'], 100.1)
        self.assertAlmostEqual(sell['price'], 99.9)

    def test_dust_does_not_create_trade(self):
        cash, units, order = research.fill(2, 0, 100, 50, .001, .001)
        self.assertIsNone(order)
        self.assertEqual((cash, units), (2, 0))

    def test_signal_never_sees_execution_candle(self):
        rows = bars()
        rows[200]['open'] = 110
        rows[200]['close'] = 10000
        seen = []
        def capture(prices):
            seen.append(list(prices))
            return 'tranquilo', 1
        result = research.backtest({'BTCUSDT': rows}, 200, 201, self.config, 'regime_v1', capture)
        self.assertEqual(seen, [[100.] * 200])
        self.assertEqual(result['trades'], 1)

    def test_low_triggers_latched_halt(self):
        rows = bars()
        rows[205]['low'] = 1
        result = research.backtest({'BTCUSDT': rows}, 200, 220, self.config, 'regime_v1', lambda _: ('tranquilo', 1))
        self.assertTrue(result['halted'])
        self.assertFalse(result['passed'])
        self.assertGreaterEqual(result['drawdown'], .15)

    def test_combined_wallet_enforces_total_exposure(self):
        config = dict(self.config, max_total_fraction=.05)
        result = research.backtest({'BTCUSDT': bars(), 'ETHUSDT': bars()}, 200, 201,
                                   config, 'regime_v1', lambda _: ('tranquilo', 1))
        self.assertEqual(result['trades'], 1)

    def test_gaps_rejected(self):
        rows = bars()
        del rows[20]
        with self.assertRaises(ValueError):
            research.check_rows(rows)

    def test_nonfinite_prices_rejected(self):
        rows = bars()
        rows[20]['close'] = float('nan')
        with self.assertRaises(ValueError):
            research.check_rows(rows)

    def test_pagination_and_exclusion_of_open_candle(self):
        end = 48 * research.HOUR
        source = [[i * research.HOUR, '100', '101', '99', '100', '1', (i + 1) * research.HOUR - 1] for i in range(24, 48)]
        with patch.object(research.time, 'time', return_value=end / 1000):
            rows = research.download('BTCUSDT', 1, lambda url: source)
        self.assertEqual(len(rows), 24)
        self.assertLess(rows[-1]['time'], end)

    def test_holdout_change_does_not_change_earlier_folds(self):
        original, changed = bars(), bars()
        changed[-1]['close'] = 1000
        first = research.evaluate({'BTCUSDT': original}, self.config, bot.signal)
        second = research.evaluate({'BTCUSDT': changed}, self.config, bot.signal)
        for name in research.STRATEGIES:
            self.assertEqual(first[name]['portfolio_folds'], second[name]['portfolio_folds'])


if __name__ == '__main__':
    unittest.main()
