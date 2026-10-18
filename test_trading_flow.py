"""Integration tests of paper execution. Quotes and approval reports are synthetic."""
from contextlib import ExitStack
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
import bot


class TradingFlowTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch('builtins.print'))
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.stack.enter_context(patch.object(bot, 'ROOT', self.root))
        self.config = dict(mode='paper', strategy='trend_v1', history_days=365,
            symbols=['BTCUSDT'], paper_usdt=1000, paper_positions={},
            max_symbol_fraction=.2, max_order_fraction=.05, max_total_fraction=.6,
            fee_rate=.001, slippage_rate=.001)
        self.rows = [{'time': i*3600000, 'close': 100.} for i in range(300)]
        self.stack.enter_context(patch.object(bot, 'candles', side_effect=lambda *args: self.rows))
        self.quote = self.stack.enter_context(patch.object(bot, 'quote', return_value={'bid': 100., 'ask': 100.1}))
        self.signal = self.stack.enter_context(patch.object(bot.research, 'target', return_value=('tranquilo', 1.)))
        self.send = self.stack.enter_context(patch.object(bot, 'notify', return_value=True))
        self.report = {'fingerprint': bot.fingerprint(self.config), 'created': time.time(),
                       'portfolio_passed': True, 'results': {'BTCUSDT': {'passed': True}}}
        self.write_report()

    def write_report(self):
        bot.save(self.root / 'validation.json', self.report)

    def state(self):
        return bot.read(self.root / 'state.json')

    def test_buy_restart_no_duplicate_then_sell_and_notify(self):
        bot.cycle(self.config)
        first = self.state()
        self.assertEqual(first['accounting']['orders'], 1)
        self.assertGreater(first['positions']['BTCUSDT'], 0)
        self.assertGreaterEqual(first['cash'], 950)
        bot.cycle(self.config)  # Persisted candle prevents a duplicate after restart.
        self.assertEqual(self.state()['accounting']['orders'], 1)
        self.rows = self.rows + [{'time': 300*3600000, 'close': 100.}]
        self.signal.return_value = ('lateral', 0.)
        bot.cycle(self.config)
        state = self.state()
        self.assertEqual(state['accounting']['orders'], 2)
        self.assertLess(state['positions']['BTCUSDT'], first['positions']['BTCUSDT'])
        self.assertAlmostEqual(state['performance']['total_pnl'],
            state['performance']['realized_pnl'] + state['performance']['unrealized_pnl'])
        messages = [call.args[0] for call in self.send.call_args_list]
        self.assertTrue(any('Compra de BTCUSDT' in m for m in messages))
        self.assertTrue(any('Venda de BTCUSDT' in m for m in messages))
        self.assertEqual(len(messages), 2)  # Decision telemetry must not spam Telegram.

    def test_expiry_while_fetching_quote_blocks_fill(self):
        calls = 0
        def quote(symbol):
            nonlocal calls
            calls += 1
            if calls == 2:
                self.report['created'] = time.time()-86401
                self.write_report()
            return {'bid': 100., 'ask': 100.1}
        self.quote.side_effect = quote
        bot.cycle(self.config)
        self.assertEqual(self.state()['accounting']['orders'], 0)
        self.assertEqual(self.state()['cash'], 1000)

    def test_stop_arriving_after_signal_blocks_order(self):
        def quote(symbol):
            (self.root / 'STOP').touch()
            return {'bid': 100., 'ask': 100.1}
        # First quote marks the wallet; second quote arrives immediately before planning.
        calls = 0
        def delayed_stop(symbol):
            nonlocal calls
            calls += 1
            return quote(symbol) if calls == 2 else {'bid': 100., 'ask': 100.1}
        self.quote.side_effect = delayed_stop
        with self.assertRaises(ValueError):
            bot.cycle(self.config)
        self.assertEqual(self.state()['accounting']['orders'], 0)

    def test_revoked_approval_blocks_fill(self):
        calls = 0
        def quote(symbol):
            nonlocal calls
            calls += 1
            if calls == 2:
                self.report['portfolio_passed'] = False
                self.write_report()
            return {'bid': 100., 'ask': 100.1}
        self.quote.side_effect = quote
        bot.cycle(self.config)
        self.assertEqual(self.state()['accounting']['orders'], 0)
