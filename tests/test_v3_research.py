import copy
import unittest
from spot_engine.data import Candle
from spot_engine.v3_research import V3Research,HigherClose,Wilder,rule_decisions,STEP


def candle(i,p=100.,volume=10.):return Candle(i*STEP,p,p+.2,p-.2,p,volume)


class V3ResearchTests(unittest.TestCase):
    def test_higher_candle_never_publishes_before_close(self):
        h=HigherClose(16*STEP,200)
        for i in range(15):h.update(candle(i));self.assertIsNone(h.close_ms)
        h.update(candle(15,110));self.assertEqual(h.close_ms,16*STEP);self.assertEqual(h.value,110)
        for i in range(16,31):h.update(candle(i,999))
        self.assertEqual(h.value,110);self.assertEqual(h.close_ms,16*STEP)

    def test_initial_partial_bucket_is_ignored(self):
        h=HigherClose(16*STEP,200)
        for i in range(1,16):h.update(candle(i))
        self.assertEqual(h.bars,0)
        for i in range(16,32):h.update(candle(i))
        self.assertEqual(h.bars,1)

    def test_flat_indicators_and_full_higher_warmup(self):
        engine=V3Research('BTC/USDT')
        for i in range(14400):row=engine.update(candle(i),as_of_ms=(i+1)*STEP)
        self.assertTrue(row['ready']);self.assertEqual(row['h4_bars'],900);self.assertEqual(row['daily_bars'],150)
        self.assertEqual(row['rsi14'],50);self.assertEqual(row['adx14'],0)
        self.assertEqual(row['vwap'],100);self.assertEqual(row['volume_relative20'],1)
        self.assertFalse(row['execution_authorized']);self.assertEqual(row['action'],'HOLD')
        self.assertTrue(all(not r['candidate'] for r in row['rules'].values()))

    def test_invalid_input_does_not_mutate_state(self):
        engine=V3Research('BTC/USDT');engine.update(candle(0),as_of_ms=STEP)
        before=copy.deepcopy(engine.__dict__)
        tiny=Candle(STEP,1e-13,2e-13,1e-14,1e-13,1.)
        for c,now in ((candle(0),STEP),(candle(2),3*STEP),(candle(1),STEP),(tiny,2*STEP)):
            with self.assertRaises(ValueError):engine.update(c,as_of_ms=now)
            self.assertEqual(engine.index,before['index']);self.assertEqual(engine.ema,before['ema'])
            self.assertEqual(engine.last,before['last']);self.assertEqual(list(engine.history),list(before['history']))

    def test_pivot_appears_only_after_two_right_candles(self):
        e=V3Research('BTC/USDT')
        prices=[100.]*30+[102.,101.,99.,101.,102.]
        for i,p in enumerate(prices):
            row=e.update(candle(i,p),as_of_ms=(i+1)*STEP)
            if i in (32,33):self.assertEqual(row['pivot_confirmations'],[])
        self.assertEqual(row['pivot_confirmations'][0]['index'],32)
        self.assertEqual(row['pivot_confirmations'][0]['confirmed_ms'],35*STEP)

    def test_wilder_seed_and_update(self):
        w=Wilder(3);self.assertIsNone(w.update(1));self.assertIsNone(w.update(2))
        self.assertEqual(w.update(3),2);self.assertEqual(w.update(5),3)

    def test_rule_gates_never_become_execution_permission(self):
        f=dict(regime='TREND',context=True,rsi=55,cross9=True,cross_macd=True,rsi35=False,
               close=101,vwap=100,divergence=False,band_recovery=False,band_cross=False,
               macd=1,macd_signal=0,breakout=False,body=.5,atr_fraction=.01,
               relative_volume=1.5,obv_rising=True,ready=True,hour_allowed=True)
        result=rule_decisions(f);self.assertTrue(result['ema_ribbon']['candidate'])
        self.assertEqual(result['ema_ribbon']['score_points'],100)
        self.assertFalse(rule_decisions(dict(f,hour_allowed=False))['ema_ribbon']['candidate'])
        self.assertFalse(rule_decisions(dict(f,relative_volume=None))['ema_ribbon']['candidate'])
        breakout=dict(f,regime='BREAKOUT',breakout=True)
        self.assertTrue(rule_decisions(breakout)['breakout_volume']['candidate'])
        divergence=dict(f,regime='RANGE',rsi=40,rsi35=True,close=99,divergence=True,band_recovery=True)
        self.assertTrue(rule_decisions(divergence)['rsi_divergence']['candidate'])
        reversion=dict(divergence,divergence=False,band_cross=True)
        self.assertTrue(rule_decisions(reversion)['vwap_reversion']['candidate'])
        self.assertTrue(all(not r['candidate'] for r in rule_decisions(dict(f,ready=False)).values()))

    def test_batch_prefix_does_not_use_future_extension(self):
        from dataclasses import replace
        from tests.test_layered_research import history
        from spot_engine.v3_research import scan
        h=history([100.+i%11 for i in range(1100)])
        prefix=replace(h,candles=h.candles[:1000],end_ms=1000*STEP)
        self.assertEqual(list(scan(prefix)),list(scan(h))[:1000])
