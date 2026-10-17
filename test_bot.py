import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import bot


class RiskTests(unittest.TestCase):
    def test_drawdown_latches_across_recovery(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(bot, 'ROOT', Path(folder)):
            state = {'peak': 100, 'halted': False}
            with self.assertRaises(ValueError):
                bot.guard(state, 85)
            with self.assertRaises(ValueError):
                bot.guard(state, 120)

    def test_stop_prevents_order(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(bot, 'ROOT', Path(folder)):
            (Path(folder) / 'STOP').touch()
            with self.assertRaises(ValueError):
                bot.guard({'peak': 100, 'halted': False}, 100)

    def test_crash_exits(self):
        regime, fraction = bot.signal([100.0] * 200 + [90.0])
        self.assertEqual((regime, fraction), ('queda_forte', 0.0))

    def test_flat_market_cannot_pass(self):
        result = bot.replay([100.0] * 500, 200, 500, 0.002, 0.2)
        self.assertFalse(result['passed'])

    def test_real_mode_rejected(self):
        config = bot.read(bot.ROOT / 'config.json')
        config['mode'] = 'live'
        with self.assertRaises(ValueError):
            bot.config_check(config)

    def test_missing_validation_cannot_trade(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(bot, 'ROOT', Path(folder)):
            rows = [{'time': i * 3600000, 'close': 100 + i} for i in range(300)]
            config = {'symbols': ['BTCUSDT'], 'paper_usdt': 1000, 'paper_positions': {},
                      'max_symbol_fraction': .2, 'max_order_fraction': .05,
                      'max_total_fraction': .6, 'fee_rate': .001, 'slippage_rate': .001}
            with patch.object(bot, 'candles', return_value=rows), patch.object(bot, 'event') as events:
                bot.cycle(config)
            self.assertEqual(bot.read(Path(folder) / 'state.json')['cash'], 1000)
            self.assertFalse(any(c.args[0] == 'paper_order' for c in events.call_args_list))


if __name__ == '__main__':
    unittest.main()
