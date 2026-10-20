from dataclasses import replace
from decimal import Decimal as D
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from spot_engine.config import load_settings
from spot_engine.main import PaperSession, single_runner, normalized_rules, parse_book
from spot_engine.data import DataError, TransientDataError
from spot_engine.execution import ExecutionError

H=3600000


def info():
    return {'symbol':'BTCUSDT','status':'TRADING','isSpotTradingAllowed':True,'filters':[
        {'filterType':'PRICE_FILTER','minPrice':'.01','maxPrice':'10000000','tickSize':'.01'},
        {'filterType':'LOT_SIZE','minQty':'.000001','maxQty':'100','stepSize':'.000001'},
        {'filterType':'NOTIONAL','minNotional':'1','maxNotional':'1000000'}]}


class Feed:
    def __init__(self):self.now=1000*H+1000;self.price='100';self.future_price=None
    def fetch_time(self):return self.now
    def fetch_symbol_info(self,symbol):return info()
    def fetch_book(self,symbol):return dict(symbol='BTCUSDT',bidPrice=self.price,askPrice=self.price,bidQty='1',askQty='1')
    def fetch_ohlcv(self,symbol,timeframe,since,limit):
        end=self.now//H*H
        return [[t,100.,101.,99.,100.,10.] if not self.future_price or t<1000*H else [t,self.future_price,self.future_price+1,self.future_price-1,self.future_price,10.] for t in range(since,min(since+limit*H,end),H)]


class SessionTests(unittest.TestCase):
    def session(self,tmp,feed=None):
        f=feed or Feed();return PaperSession(tmp,load_settings({}),f,clock=lambda:f.now/1000)

    def test_startup_does_not_trade_warmup_or_reset_wallet(self):
        with tempfile.TemporaryDirectory() as tmp:
            s=self.session(tmp);r=s.cycle()
            self.assertEqual(r['buy_fills'],0);self.assertEqual(D(r['cash']),20)
            end=s.plan['end_ms'];s=self.session(tmp)
            self.assertEqual(s.plan['end_ms'],end);self.assertEqual(s.broker.snapshot()['orders'],{})

    def test_new_cross_submits_then_next_quote_fills(self):
        with tempfile.TemporaryDirectory() as tmp:
            f=Feed();s=self.session(tmp,f);s.cycle()
            f.now=1001*H+1000;f.future_price=120.;f.price='120'
            r=s.cycle();self.assertIn('ENTER_LONG',r['last_signal'])
            self.assertEqual(r['buy_fills'],0);self.assertGreater(D(r['reserved']),0)
            f.now+=15000;r=s.cycle()
            self.assertEqual(r['buy_fills'],1);self.assertGreater(D(r['units']),0)
            self.assertIsNotNone(r['protection'])

    def test_feed_failure_preserves_pending_signal_for_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            f=Feed();s=self.session(tmp,f);s.cycle()
            f.now=1001*H+1000;f.future_price=120.;f.price='120'
            with patch.object(f,'fetch_book',side_effect=DataError('unavailable')):
                with self.assertRaises(DataError):s.cycle()
            self.assertIsNotNone(s.pending_signal)
            f.now+=15000;r=s.cycle();self.assertGreater(D(r['reserved']),0)

    def test_restart_skips_old_entry_and_deadline_is_not_extended(self):
        with tempfile.TemporaryDirectory() as tmp:
            f=Feed();s=self.session(tmp,f);end=s.plan['end_ms']
            f.now=1001*H+1000;f.future_price=120.;f.price='120'
            s=self.session(tmp,f);s.cycle()
            self.assertEqual(s.broker.snapshot()['orders'],{})
            f.now=end+1;self.assertEqual(s.cycle()['reason'],'DEADLINE')
            with self.assertRaises(ExecutionError):self.session(tmp,f)

    def test_stop_control_prevents_start_and_cancels_pending(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp)/'STOP').touch()
            with self.assertRaises(ExecutionError):self.session(tmp)
        with tempfile.TemporaryDirectory() as tmp:
            f=Feed();s=self.session(tmp,f);s.cycle();f.now=1001*H+1000;f.future_price=120.;f.price='120';s.cycle()
            (Path(tmp)/'STOP').touch();r=s.cycle()
            self.assertEqual(r['phase'],'STOPPED');self.assertEqual(D(r['reserved']),0)

    def test_global_stop_is_respected(self):
        with tempfile.TemporaryDirectory() as tmp,tempfile.TemporaryDirectory() as control:
            with patch('spot_engine.main.ROOT',Path(control)):
                s=self.session(tmp);(Path(control)/'STOP').touch()
                self.assertEqual(s.cycle()['reason'],'STOP')

    def test_wrong_configuration_does_not_reset_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            s=self.session(tmp)
            with self.assertRaises(ExecutionError):PaperSession(tmp,replace(load_settings({}),max_order_notional=D('6')),Feed())
            self.assertEqual(D(s.broker.snapshot()['cash']),20)

    def test_lock_rejects_second_runner(self):
        with tempfile.TemporaryDirectory() as tmp:
            with single_runner(Path(tmp)/'runner.lock'):
                with self.assertRaises(ExecutionError):
                    with single_runner(Path(tmp)/'runner.lock'):pass

    def test_public_metadata_and_book_fail_closed(self):
        self.assertEqual(normalized_rules(info(),'BTC/USDT',1000).min_notional,D('1'))
        bad=info();bad['status']='BREAK'
        with self.assertRaises(DataError):normalized_rules(bad,'BTC/USDT',1000)
        for raw in ({'symbol':'ETHUSDT'},dict(symbol='BTCUSDT',bidPrice=True,askPrice='100',bidQty='1',askQty='1')):
            with self.assertRaises(DataError):parse_book(raw,'BTC/USDT')

    def test_stale_cross_is_not_used_to_force_an_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            f=Feed();s=self.session(tmp,f);s.cycle()
            f.now=1001*H+1000;f.future_price=120.;f.price='120'
            with patch.object(f,'fetch_book',side_effect=DataError('unavailable')):
                with self.assertRaises(DataError):s.cycle()
            f.now+=180000;r=s.cycle()
            self.assertEqual(r['reason'],'STALE_SIGNAL')
            self.assertEqual(s.broker.snapshot()['orders'],{})

    def test_book_without_available_size_has_no_synthetic_liquidity(self):
        result=parse_book(dict(symbol='BTCUSDT',bidPrice='100',askPrice='101',bidQty='0',askQty='0'),'BTC/USDT')
        self.assertEqual(result[2:],(D(0),D(0)))

    def test_unfilled_entry_expires_instead_of_buying_much_later(self):
        with tempfile.TemporaryDirectory() as tmp:
            f=Feed();s=self.session(tmp,f);s.cycle()
            f.now=1001*H+1000;f.future_price=120.;f.price='120';s.cycle()
            f.now+=61000;f.price='122';r=s.cycle()
            self.assertEqual(r['reason'],'ENTRY_CANCELED_STALE_OR_EXIT_SIGNAL')
            self.assertEqual(D(r['reserved']),0)
            self.assertEqual(D(r['units']),0)
