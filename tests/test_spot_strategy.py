from dataclasses import replace
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from spot_engine.config import load_settings
from spot_engine.data import Candle, History, DataError, load_history, save_history
from spot_engine.strategy import EmaAtrStrategy, StrategyError, analyze

H=3_600_000


def candles(prices):
    return tuple(Candle(i*H,p,p+1,p-1,p,10.) for i,p in enumerate(prices))


def config(**changes):
    return replace(load_settings({}),ema_fast=2,ema_slow=3,ema_trend=5,atr_period=2,
                   atr_min_fraction=Decimal('0'),atr_max_fraction=Decimal('.9'),**changes)


def scan(prices,cfg=None):
    strategy=EmaAtrStrategy(cfg or config())
    return [strategy.update(c,as_of_ms=c.open_ms+H) for c in candles(prices)]


class StrategyTests(unittest.TestCase):
    def test_ema_and_wilder_atr_known_values(self):
        signals=scan([100.,110.,105.])
        self.assertAlmostEqual(signals[1].ema_fast,106.6666666667)
        self.assertAlmostEqual(signals[2].ema_fast,105.5555555556)
        self.assertAlmostEqual(signals[1].atr,6.5)
        self.assertAlmostEqual(signals[2].atr,6.25)

    def test_default_warmup_prevents_early_entries(self):
        s=EmaAtrStrategy(load_settings({}))
        self.assertEqual(s.warmup_bars,600)
        results=[s.update(c,as_of_ms=c.open_ms+H) for c in candles([100.]*600)]
        self.assertTrue(all(r.action=='HOLD' and not r.ready for r in results[:599]))
        self.assertTrue(results[599].ready)
        self.assertEqual(results[599].reason,'NO_CROSS')

    def test_cross_up_is_one_intent_not_repeated_buy(self):
        results=scan([100.]*30+[120.]*10)
        self.assertEqual(sum(r.action=='ENTER_LONG' for r in results),1)
        self.assertEqual(results[30].reason,'EMA_CROSS_UP')
        self.assertTrue(all(r.action=='HOLD' for r in results[31:]))

    def test_trend_filter_blocks_cross_below_trend(self):
        cfg=replace(config(),ema_trend=20)
        results=scan([300.]*100+[100.]*8+[110.],cfg)
        self.assertEqual(results[-1].reason,'TREND_FILTER')
        self.assertEqual(results[-1].action,'HOLD')

    def test_atr_filter_blocks_entry_but_not_exit(self):
        cfg=replace(config(),atr_max_fraction=Decimal('.00001'))
        results=scan([100.]*30+[120.]*10+[80.],cfg)
        self.assertEqual(results[30].reason,'ATR_FILTER')
        self.assertEqual(results[-1].action,'EXIT_LONG')

    def test_future_extension_cannot_change_past_signals(self):
        prefix=[100.]*30+[120.]*10+[80.]*10
        before=scan(prefix)
        after=scan(prefix+[200.,60.,100.,500.])
        self.assertEqual(before,after[:len(before)])

    def test_duplicate_gap_and_future_reject_without_mutating_state(self):
        s=EmaAtrStrategy(config());c=candles([100.,101.,102.])
        first=s.update(c[0],as_of_ms=H)
        for candle,cutoff in ((c[0],H),(c[2],3*H),(c[1],2*H-1),(c[1],True)):
            with self.subTest(candle=candle,cutoff=cutoff),self.assertRaises(StrategyError):
                s.update(candle,as_of_ms=cutoff)
        self.assertEqual(s.update(c[1],as_of_ms=2*H).bars,first.bars+1)

    def test_clock_rollback_rejects_closed_candle(self):
        s=EmaAtrStrategy(config());c=candles([100.,101.])
        s.update(c[0],as_of_ms=10*H)
        with self.assertRaises(StrategyError):s.update(c[1],as_of_ms=2*H)
        self.assertEqual(s.update(c[1],as_of_ms=10*H).bars,2)

    def test_overflow_rejects_without_poisoning_indicators(self):
        s=EmaAtrStrategy(config());s.update(candles([100.])[0],as_of_ms=H)
        bad=Candle(H,1e-308,1e308,1e-308,1e-308,0)
        # ATR/price overflows while each OHLC component is finite.
        with self.assertRaises(StrategyError):s.update(bad,as_of_ms=2*H)
        good=Candle(H,100.,101.,99.,100.,1.)
        self.assertEqual(s.update(good,as_of_ms=2*H).bars,2)

    def test_no_network_or_order_client_required(self):
        with patch('socket.socket',side_effect=AssertionError('Network forbidden')):
            results=scan([100.]*30+[120.])
        self.assertFalse(hasattr(results[-1],'quantity'))
        self.assertFalse(hasattr(EmaAtrStrategy(config()),'place_order'))

    def test_verified_history_and_config_must_match(self):
        h=History('BTC/USDT','1h',0,3*H,3*H,candles([100.,101.,102.]),1,0)
        self.assertEqual(len(analyze(h,config())),3)
        with self.assertRaises(StrategyError):analyze(h,replace(config(),symbol='ETH/USDT'))

    def test_csv_reader_checks_hash_coverage_and_utc(self):
        h=History('BTC/USDT','1h',0,3*H,3*H,candles([100.,101.,102.]),1,0)
        with tempfile.TemporaryDirectory() as tmp:
            path=save_history(h,tmp)
            self.assertEqual(load_history(path),h)
            raw=path.read_bytes();path.write_bytes(raw+b'corruption')
            with self.assertRaises(DataError):load_history(path)
            path.write_bytes(raw)
            manifest=json.loads(path.with_suffix('.json').read_text(encoding='utf-8'));manifest['count']=2
            path.with_suffix('.json').write_text(json.dumps(manifest),encoding='utf-8')
            with self.assertRaises(DataError):load_history(path)
            path=save_history(h,tmp);raw=path.read_bytes().replace(b'+00:00',b'+01:00',1);path.write_bytes(raw)
            m=json.loads(path.with_suffix('.json').read_text(encoding='utf-8'));m['csv_sha256']=hashlib.sha256(raw).hexdigest()
            path.with_suffix('.json').write_text(json.dumps(m),encoding='utf-8')
            with self.assertRaises(DataError):load_history(path)
