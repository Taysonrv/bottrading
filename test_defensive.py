import unittest
import bot
import research
from unittest.mock import patch
from test_research import bars


class DefensiveTests(unittest.TestCase):
    def setUp(self):
        self.config = bot.read(bot.ROOT / 'config.json')

    def run_policy(self, policy, stop=None):
        rows = bars(360)
        # Assets are marked at 100 initially; a later gap triggers protection.
        for row in rows[201:]:
            row.update(open=75., high=76., low=74., close=75.)
        return research.backtest({'BTCUSDT': rows}, 200, 250, self.config, 'regime_v1',
                                 lambda _: ('tranquilo', 1), initial_exposure=.8,
                                 risk_policy=policy, stop_requested=stop)

    def test_reduction_never_buys_after_halt(self):
        result = self.run_policy('reduce')
        self.assertTrue(result['halted'])
        self.assertGreater(result['defensive_orders'], 0)
        self.assertEqual(result['defensive_buys'], 0)
        self.assertFalse(result['passed'])

    def test_reduction_leaves_less_exposure_than_freeze(self):
        frozen, reduced = self.run_policy('freeze'), self.run_policy('reduce')
        self.assertLess(reduced['remaining_exposure_usdt'], frozen['remaining_exposure_usdt'])
        self.assertLess(reduced['remaining_exposure_usdt'], 10)

    def test_stop_blocks_defensive_sales(self):
        result = self.run_policy('reduce', lambda: True)
        self.assertTrue(result['manually_stopped'])
        self.assertEqual(result['trades'], 0)
        self.assertEqual(result['defensive_orders'], 0)

    def test_gap_can_exceed_fifteen_percent_before_exit(self):
        result = self.run_policy('reduce')
        self.assertGreater(result['drawdown'], .15)

    def test_unknown_policy_rejected(self):
        with self.assertRaises(ValueError):
            self.run_policy('unknown')

    def test_opening_trigger_waits_for_following_opening(self):
        rows = bars(360)
        rows[201].update(open=75., high=76., low=74., close=75.)
        for row in rows[202:]:
            row.update(open=70., high=71., low=69., close=70.)
        with patch.object(research, 'fill', wraps=research.fill) as fills:
            research.backtest({'BTCUSDT': rows}, 200, 220, self.config, 'regime_v1',
                              lambda _: ('tranquilo', 1), initial_exposure=.8, risk_policy='reduce')
        prices = [call.args[2] for call in fills.call_args_list]
        self.assertNotIn(75., prices)
        self.assertIn(70., prices)


if __name__ == '__main__':
    unittest.main()
