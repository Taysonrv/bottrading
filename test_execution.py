import random
import unittest
import bot
import execution
import research
from unittest.mock import patch
from test_research import bars


class ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.config = bot.read(bot.ROOT / 'config.json')

    def test_order_budget_includes_fee_spread_and_slippage(self):
        delta = execution.plan(1000, 1000, 0, 100, 110, 0, 1, self.config, .02, .03)
        cash, units, order = research.fill(1000, 0, 110, delta, .02, .03)
        self.assertIsNotNone(order)
        self.assertLessEqual(1000 - cash, 50 + 1e-9)

    def test_generated_buys_respect_post_cost_exposure(self):
        rng = random.Random(124)
        for _ in range(500):
            total = rng.uniform(.2, .8)
            per_symbol = rng.uniform(.1, total)
            config = dict(self.config, max_total_fraction=total, max_symbol_fraction=per_symbol)
            equity = 1000.
            bid = rng.uniform(1, 10000)
            own = equity * rng.uniform(0, per_symbol * .9)
            other = rng.uniform(0, max(0, equity * total - own))
            cash = equity - own - other
            units = own / bid
            ask = bid * rng.uniform(1, 1.1)
            fee, slip = rng.uniform(0, .05), rng.uniform(0, .05)
            delta = execution.plan(equity, cash, units, bid, ask, own + other, 1, config, fee, slip)
            new_cash, new_units, order = research.fill(cash, units, ask, delta, fee, slip)
            if order:
                new_equity = new_cash + new_units * bid + other
                self.assertGreaterEqual(new_cash, 0)
                self.assertLessEqual(new_units * bid, per_symbol * new_equity + 1e-8)
                self.assertLessEqual(new_units * bid + other, total * new_equity + 1e-8)
                self.assertLessEqual(cash - new_cash, equity * config['max_order_fraction'] + 1e-8)

    def test_existing_overexposure_cannot_trigger_more_buying(self):
        delta = execution.plan(1000, 200, 8, 100, 101, 800, 1, self.config, .001, .001)
        self.assertLess(delta, 0)
        self.assertLess(abs(delta), 51)

    def test_existing_positions_carry_gap_risk(self):
        rows = bars()
        rows[200]['low'] = 50
        existing = research.backtest({'BTCUSDT': rows}, 200, 201, self.config, 'regime_v1',
                                     lambda _: ('queda_forte', 0), initial_exposure=.8)
        empty = research.backtest({'BTCUSDT': rows}, 200, 201, self.config, 'regime_v1',
                                  lambda _: ('queda_forte', 0))
        self.assertTrue(existing['halted'])
        self.assertFalse(empty['halted'])

    def test_sell_budget_includes_fees(self):
        delta = execution.plan(1000, 200, 8, 100, 100, 800, 0, self.config, .02, .03)
        _, _, order = research.fill(200, 8, 100, delta, .02, .03)
        self.assertLessEqual(order['quantity'] * order['price'] + order['fee'], 50 + 1e-9)

    def test_nonfinite_inputs_rejected(self):
        with self.assertRaises(ValueError):
            execution.plan(float('nan'), 0, 0, 100, 100, 0, 1, self.config, .001, .001)

    def test_download_uses_shared_cutoff_despite_hour_rollover(self):
        cutoff = 48 * research.HOUR
        source = [[i * research.HOUR, '100', '101', '99', '100', '1', (i + 1) * research.HOUR - 1]
                  for i in range(24, 48)]
        with patch.object(research.time, 'time', return_value=100 * research.HOUR / 1000):
            rows = research.download('BTCUSDT', 1, lambda _: source, end=cutoff)
        self.assertEqual(rows[-1]['time'], cutoff - 1)


if __name__ == '__main__':
    unittest.main()
