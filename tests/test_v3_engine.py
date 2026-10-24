"""Contracts for the isolated observation variant; no network or live state."""
import copy
from decimal import Decimal as D
from pathlib import Path
import tempfile
import unittest
from spot_engine.data import Candle, History
from spot_engine.risk import Rules
from spot_engine.v3_position_plan import Budget
from v3_engine.context import MultiTimeframeContext
from v3_engine.regime import detect
from v3_engine.scorer import score
from v3_engine.strategies import evaluate
from v3_engine.risk_v3 import plan_entry
from v3_engine.engine_v3 import observe, identity

STEP = 900000


def state(**changes):
    result = dict(ready=True,adx14=30.,rsi14=55.,atr_fraction=.01,close=103.,vwap=100.,
        volume_relative20=1.4,ema={9:102.,21:101.,50:100.},higher_context=True,
        breakout=False,cross9=True,macd12_26=2.,macd_signal9=1.,histogram_rising=True,
        body_fraction=.7,upper_third=True,bollinger20={'lower':98.,'upper':104.},
        low=99.,obv_rising3=True)
    result.update(changes); return result


class V3EngineTests(unittest.TestCase):
    def test_priority_and_all_six_regimes(self):
        for expected,s in [('UNKNOWN',state(ready=False,atr_fraction=.1)),
            ('CRISIS',state(atr_fraction=.031,breakout=True)),
            ('BREAKOUT',state(breakout=True)),('TREND',state()),
            ('RANGE',state(adx14=15.,rsi14=30.,close=99.)),
            ('TRANSITION',state(adx14=22.))]:
            self.assertEqual(detect(s).regime,expected)
            self.assertFalse(detect(s).execution_authorized)

    def test_unready_nan_and_missing_are_unknown(self):
        for s in (state(adx14=float('nan')),state(rsi14=101),state(ema={}),state(vwap=None)):
            self.assertEqual(detect(s).regime,'UNKNOWN')
            self.assertNotEqual(evaluate(s).action,'ENTER')

    def test_score_not_probability_and_no_execution(self):
        s=state();before=copy.deepcopy(s); r=score(s,trigger=True)
        self.assertEqual(r['score'],100);self.assertEqual(s,before)
        signal=evaluate(s);self.assertEqual(signal.action,'ENTER')
        self.assertFalse(signal.execution_authorized);self.assertFalse(signal.approved)
        for change in ({'cross9':False},{'atr_fraction':.025},{'higher_context':False}):
            self.assertEqual(evaluate(state(**change)).action,'HOLD')

    def test_range_not_required_to_be_above_vwap(self):
        s=state(adx14=15.,rsi14=30.,close=99.,low=97.,
                bollinger20={'lower':98.,'upper':104.})
        self.assertEqual(evaluate(s).regime,'RANGE')
        self.assertEqual(evaluate(s).action,'ENTER')
        self.assertEqual(evaluate(state(adx14=22.)).action,'OBSERVE')

    def test_context_closed_causal_and_snapshot_isolated(self):
        ctx=MultiTimeframeContext('BTC/USDT')
        c=Candle(0,100,101,99,100,10)
        with self.assertRaises(ValueError):ctx.update_15m(c,STEP-1)
        self.assertFalse(ctx.is_ready())
        a=ctx.update_15m(c,STEP); a['ema'][9]=999
        self.assertEqual(ctx.state()['ema'][9],100)
        with self.assertRaises(ValueError):ctx.update_15m(Candle(2*STEP,100,101,99,100,10),3*STEP)
        self.assertEqual(ctx.state()['decision_ms'],STEP)

    def test_vwap_reset_and_no_fake_higher_warmup(self):
        ctx=MultiTimeframeContext('BTC/USDT')
        for i in range(96):ctx.update_15m(Candle(i*STEP,100,101,99,100,10),(i+1)*STEP)
        row=ctx.update_15m(Candle(96*STEP,110,111,109,110,10),97*STEP)
        self.assertEqual(row['vwap'],110);self.assertFalse(row['ready'])
        self.assertEqual(row['daily_bars'],1)

    def test_stop_and_replay_cannot_count_as_forward_test(self):
        candles=tuple(Candle(i*STEP,100,101,99,100,10) for i in range(25))
        history=History('BTC/USDT','15m',0,25*STEP,25*STEP,candles,1,0)
        result=observe(history)
        self.assertEqual(result['bars'],25);self.assertEqual(result['buy_fills'],0)
        self.assertEqual(result['forward_observation_hours'],0)
        self.assertFalse(result['validation']['observation_48h'])
        self.assertEqual(len(identity()),64)
        with tempfile.TemporaryDirectory() as root:
            stop=Path(root)/'STOP';stop.write_text('test')
            r=observe(history,stop);self.assertEqual(r['reason'],'STOP');self.assertEqual(r['bars'],0)

    def test_small_cap_cap_and_partial_filters(self):
        now=1700000000000
        rules=Rules('SOL/USDT',now,D('.001'),D('.001'),D('100000'),D('.01'),D('.01'),D('1000000'),D('5'),D('1000000'))
        b=Budget(D(1000),D(1000),D(0),D(0),D(30),D(100))
        r=plan_entry(rules,b,ask=D(100),atr=D(2),score=100,now_ms=now,quote_ms=now)
        self.assertFalse(r['valid_research_plan']);self.assertFalse(r['execution_authorized'])
        self.assertIn(r['reason'],('MAX_NOTIONAL_FILTER','CAPPED_PARTIAL_EXIT_FILTER'))


if __name__ == '__main__': unittest.main()
