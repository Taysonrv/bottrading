from dataclasses import replace
from decimal import Decimal
import unittest
from unittest.mock import patch
from spot_engine.config import ConfigError, load_settings


class SpotConfigTests(unittest.TestCase):
    def test_conservative_defaults(self):
        s = load_settings({})
        self.assertEqual((s.symbol, s.capital, s.max_positions), ('BTC/USDT', Decimal('20'), 1))
        self.assertEqual((s.risk_per_trade, s.daily_loss_limit, s.max_drawdown), (Decimal('.01'), Decimal('.03'), Decimal('.10')))
        self.assertEqual((s.ema_fast, s.ema_slow, s.ema_trend), (20, 50, 200))

    def test_symbol_and_timeframe_configurable(self):
        s = load_settings({'TRADING_SYMBOL':'ETH/USDT','TRADING_TIMEFRAME':'15m','TRADING_CAPITAL':'100'})
        self.assertEqual(s.symbol, 'ETH/USDT')
        self.assertEqual(s.capital, Decimal('100'))

    def test_risk_caps_and_stop_cannot_be_disabled(self):
        for key, value in [('RISK_PER_TRADE','.0101'),('DAILY_LOSS_LIMIT','.031'),('MAX_DRAWDOWN','.101'),('STOP_LOSS_FRACTION','0'),('STOP_LOSS_FRACTION','1'),('MAX_POSITIONS','0'),('MAX_ORDER_NOTIONAL','21')]:
            with self.subTest(key=key), self.assertRaises(ConfigError):
                load_settings({'TRADING_'+key:value})

    def test_invalid_numeric_inputs_and_secrets_not_echoed(self):
        for value in ('NaN','Infinity','-Infinity','secret-value',True, '9'*65):
            with self.subTest(value=value):
                with self.assertRaises(ConfigError) as error:
                    load_settings({'TRADING_CAPITAL':value})
                self.assertNotIn(str(value),str(error.exception))

    def test_live_and_derivatives_rejected(self):
        for env in ({'TRADING_MODE':'live'},{'TRADING_SYMBOL':'BTC/USDT:USDT'},{'TRADING_SYMBOL':'BTC/USDC'}):
            with self.subTest(env=env), self.assertRaises(ConfigError):
                load_settings(env)

    def test_validation_horizon_and_period_order(self):
        for env in ({'TRADING_HISTORY_YEARS':'1'},{'TRADING_TESTNET_DAYS':'7'},{'TRADING_EMA_FAST':'50'},{'TRADING_ATR_MIN_FRACTION':'.06'}):
            with self.subTest(env=env), self.assertRaises(ConfigError):
                load_settings(env)

    def test_direct_construction_and_mutation_cannot_bypass_limits(self):
        s=load_settings({})
        for changes in ({'risk_per_trade':Decimal('.02')},{'max_positions':True},{'timezone':'local'}):
            with self.subTest(changes=changes), self.assertRaises(ConfigError):
                replace(s,**changes)
        with self.assertRaises(AttributeError):
            s.mode='live'

    def test_configuration_never_connects_or_spends(self):
        with patch('socket.socket',side_effect=AssertionError('Network forbidden')):
            load_settings({'BINANCE_API_KEY':'ignored-secret','BINANCE_API_SECRET':'ignored-secret'})

    def test_costs_are_independent_parameters(self):
        s=load_settings({'TRADING_FEE_RATE':'.002','TRADING_SLIPPAGE_RATE':'.003'})
        self.assertEqual(s.fee_rate,Decimal('.002'))
        self.assertEqual(s.slippage_rate,Decimal('.003'))
