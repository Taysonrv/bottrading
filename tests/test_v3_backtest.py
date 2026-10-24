from decimal import Decimal as D
from unittest.mock import patch
import unittest
from spot_engine.data import Candle,History
from spot_engine.risk import Rules
from v3_engine.strategies import Signal
from v3_feasibility import audit_pair
from v3_backtest import run,rules_from_snapshot

STEP=900000


def rules(minimum='0.01'):
    return Rules('BTC/USDT',1700000000000,D('.001'),D('.001'),D(100000),D('.01'),D('.01'),D(1000000),D(minimum),D(1000000))


def history(prices):
    candles=tuple(Candle(i*STEP,p,p+2,p-2,p,10) for i,p in enumerate(prices))
    return History('BTC/USDT','15m',0,len(candles)*STEP,len(candles)*STEP,candles,0,0)


class Context:
    def __init__(self,symbol):pass
    def update_15m(self,candle,as_of_ms):
        return dict(ready=True,decision_ms=as_of_ms,atr14=1.8,
                    ema={9:101,21:100},regime='TREND')


class V3BacktestTests(unittest.TestCase):
    def test_small_cap_three_leg_mathematical_bound(self):
        r=audit_pair(rules('5'),D(100),D('100.01'),D('1.8'),20,1700000000000)
        self.assertTrue(r['cap_precludes_three_stop_legs'])
        self.assertEqual(r['minimum_aggregate_stop_notional'],'15')
        self.assertFalse(r['perfect_score_is_market_signal'])
        self.assertFalse(r['execution_authorized'])
        self.assertEqual(r['strategy_score_plan']['reason'],'SCORE_TOO_LOW')

    def test_no_warmup_is_not_validated_zero_return(self):
        with self.assertRaisesRegex(ValueError,'INSUFFICIENT'):
            run(history([100]*10),rules())

    def test_mock_context_only_tests_finance_not_real_signal_edge(self):
        # Artificial warmed context/ENTER to exercise small-account arithmetic;
        # this fixture is not evidence about actual V3 signal generation.
        with patch('v3_backtest.MultiTimeframeContext',Context),patch('v3_backtest.evaluate',
            return_value=Signal('ENTER','TEST','TREND',100,{})):
            r=run(history([100,100,100]),rules('5'))
        self.assertEqual(r['candidate_count'],2);self.assertEqual(r['closed_trades'],0)
        self.assertEqual(r['final_equity'],'20');self.assertIsNone(r['win_rate'])
        self.assertEqual(r['verdict'],'NO_TRADES_NOT_VALIDATED')

    def test_next_open_not_signal_close_and_end_cash_reconciles(self):
        with patch('v3_backtest.MultiTimeframeContext',Context),patch('v3_backtest.evaluate',
            return_value=Signal('ENTER','TEST','TREND',100,{})):
            r=run(history([100,110,110]),rules())
        self.assertEqual(r['closed_trades'],1)
        self.assertEqual(r['trades'][0]['entry_ms'],STEP)
        self.assertEqual(D(r['final_equity']),D(20)+sum(D(t['pnl']) for t in r['trades']))
        self.assertGreater(D(r['fees']),0);self.assertFalse(r['approved'])
        self.assertEqual(r['exit_events'][-1]['reason'],'END_LIQUIDATION')

    def test_rejects_wrong_provenance_and_crossed_book(self):
        with self.assertRaises(ValueError):rules_from_snapshot({},'BTC/USDT')
        with self.assertRaises(ValueError):audit_pair(rules(),D(101),D(100),D(1),100,1700000000000)


if __name__=='__main__':unittest.main()
