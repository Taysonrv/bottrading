from dataclasses import replace
from decimal import Decimal
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from spot_engine.backtest import run
from spot_engine.config import load_settings
from spot_engine.data import Candle, History

H = 3600000


class BacktestTests(unittest.TestCase):
    def simulate(self, last, fee='.001', slip='.001'):
        cfg = replace(load_settings({}), ema_fast=2, ema_slow=3, ema_trend=4,
                      atr_period=2, max_order_notional=Decimal('6'),
                      fee_rate=Decimal(fee), slippage_rate=Decimal(slip))
        bars = tuple(Candle(i*H, 100, 100, 100, 100, 10) for i in range(12)) + (Candle(12*H, *last, 10),)
        history = History(cfg.symbol, cfg.timeframe, 0, len(bars)*H, len(bars)*H, bars, 1, 0)
        signals = [SimpleNamespace(action='HOLD') for _ in bars]
        signals[11] = SimpleNamespace(action='ENTER_LONG')
        with patch('spot_engine.backtest.analyze', return_value=signals):
            return run(history, cfg)

    def test_both_levels_stop_first(self):
        result = self.simulate((100, 110, 90, 100))
        self.assertEqual(result['trades'][0]['reason'], 'STOP')
        self.assertLess(result['final_equity'], 20)
        self.assertFalse(result['approved'])

    def test_costs_reduce_flat_liquidation(self):
        free = self.simulate((100, 100, 100, 100), '0', '0')
        paid = self.simulate((100, 100, 100, 100))
        self.assertAlmostEqual(free['final_equity'], 20)
        self.assertLess(paid['final_equity'], free['final_equity'])
        self.assertGreater(paid['fees'], 0)

    def test_entry_uses_next_open_not_signal_close(self):
        result = self.simulate((200, 200, 200, 200), '0', '0')
        self.assertAlmostEqual(result['final_equity'], 20)

    def test_target_net_gain_after_costs(self):
        result = self.simulate((100, 110, 100, 105))
        self.assertEqual(result['trades'][0]['reason'], 'TARGET')
        self.assertGreater(result['final_equity'], 20)


if __name__ == '__main__':
    unittest.main()
