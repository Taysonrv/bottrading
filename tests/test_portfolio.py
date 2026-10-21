from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from decimal import Decimal as D
from pathlib import Path
import sqlite3
import tempfile
import unittest
from spot_engine.portfolio import Portfolio, PortfolioError
from spot_engine.risk import Rules


def rules(symbol='BTC/USDT',now=1000,minimum='5'):
    return Rules(symbol,now,D('.000001'),D('.000001'),D('1000000'),D('.01'),D('.01'),D('1000000'),D(minimum),D('1000000'))


class PortfolioTests(unittest.TestCase):
    def make(self,tmp):
        p=Portfolio(tmp);p.initialize(1000);return p

    def reserve(self,p,symbol='BTC/USDT',key='buy',now=1000):
        return p.reserve(key,dict(symbol=symbol,status='OK',action='ENTER_LONG',candle_close_ms=now),rules(symbol,now),D('99.99'),D('100'),now,now)

    def tick(self,p,key='tick',symbol='BTC/USDT',now=2000,bid='99.99',ask='100',liquidity='1',exit=False):
        return p.quote(key,rules(symbol,now),D(bid),D(ask),D(liquidity),now,now,exit)

    def test_shared_reservation_prevents_second_symbol(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=self.make(tmp);o=self.reserve(p)
            self.assertEqual(o['status'],'NEW')
            with self.assertRaises(PortfolioError):self.reserve(p,'ETH/USDT','other')
            s=p.snapshot();self.assertEqual(D(s['cash']),20);self.assertLessEqual(D(s['pending']['reserved']),6)

    def test_later_fill_fee_protection_and_restart_idempotency(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=self.make(tmp);self.reserve(p)
            self.assertEqual(self.tick(p,now=1200),'NO_FILL')
            self.assertEqual(self.tick(p,'fill'),'BUY_FILLED')
            p=Portfolio(tmp);self.assertEqual(self.tick(p,'fill'),'BUY_FILLED')
            s=p.snapshot();self.assertEqual(len(s['fills']),1);self.assertIsNotNone(s['position'])
            self.assertGreater(D(s['fees']),0);self.assertLess(D(s['cash']),20)
            with self.assertRaises(PortfolioError):self.reserve(p,'SOL/USDT','second',now=3000)

    def test_profit_round_trip_then_other_symbol_same_cash(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=self.make(tmp);self.reserve(p);self.tick(p)
            self.assertEqual(self.tick(p,'sell',now=3000,bid='105',ask='105.01'),'EXIT_PENDING')
            self.assertEqual(self.tick(p,'sellfill',now=4000,bid='105',ask='105.01'),'SELL_FILLED')
            cash=D(p.snapshot()['cash']);self.assertGreater(cash,20)
            self.reserve(p,'ETH/USDT','eth',now=5000)
            self.assertEqual(D(p.snapshot()['cash']),cash)
            self.tick(p,'ethfill','ETH/USDT',now=6000)
            self.assertEqual(p.snapshot()['position']['symbol'],'ETH/USDT')
            self.assertEqual(len(p.snapshot()['fills']),3)

    def test_stop_cancels_reserve_and_blocks_exit_without_selling(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=self.make(tmp);self.reserve(p);(Path(tmp)/'STOP').touch()
            self.assertEqual(self.tick(p),'STOP');self.assertIsNone(p.snapshot()['pending'])
        with tempfile.TemporaryDirectory() as tmp:
            p=self.make(tmp);self.reserve(p);self.tick(p);(Path(tmp)/'STOP').touch()
            self.assertEqual(self.tick(p,'stop',now=3000,bid='90',ask='90.01'),'STOP_EXPOSED')
            self.assertIsNotNone(p.snapshot()['position']);self.assertEqual(len(p.snapshot()['fills']),1)

    def test_gap_sells_at_adverse_bid_not_stop_and_latches_daily_loss(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=self.make(tmp);self.reserve(p);self.tick(p)
            self.tick(p,'gap',now=3000,bid='89',ask='89.01')
            self.assertEqual(self.tick(p,'earlyexit',now=3100,bid='89',ask='89.01'),'EXIT_PENDING')
            self.tick(p,'exitfill',now=4000,bid='89',ask='89.01')
            s=p.snapshot();self.assertEqual(s['halt'],'DAILY_LOSS')
            self.assertEqual(s['fills'][-1]['price'],'88.91')
            self.assertEqual(self.reserve(p,'ETH/USDT','blocked',now=5000)['status'],'REJECTED')
            self.assertEqual(self.reserve(p,'ETH/USDT','tomorrow',now=86401000)['status'],'REJECTED')

    def test_insufficient_liquidity_and_expiry_release_reservation(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=self.make(tmp);self.reserve(p)
            self.assertEqual(self.tick(p,liquidity='0.000001'),'NO_FILL')
            self.tick(p,'expire',now=61000)
            self.assertIsNone(p.snapshot()['pending']);self.assertEqual(p.snapshot()['cash'],'20')

    def test_stale_quote_and_wrong_symbol_cannot_fill(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=self.make(tmp);self.reserve(p)
            self.assertEqual(self.tick(p,symbol='ETH/USDT'),'NO_FILL')
            with self.assertRaises(PortfolioError):
                p.quote('stale',rules(),D('99'),D('100'),D('1'),1000,8000)
            self.assertEqual(len(p.snapshot()['fills']),0)

    def test_race_two_symbols_only_one_reservation(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=self.make(tmp)
            def attempt(symbol):
                try:return self.reserve(Portfolio(tmp),symbol,symbol.replace('/',''))['status']
                except PortfolioError:return 'BLOCKED'
            with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(attempt,('BTC/USDT','ETH/USDT')))
            self.assertCountEqual(results,['NEW','BLOCKED'])
            self.assertEqual(len(p.snapshot()['orders']),1)

    def test_corrupt_cash_refuses_reinitialization(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=self.make(tmp)
            with closing(sqlite3.connect(p.path)) as db:
                db.execute("UPDATE ledger SET payload=json_set(payload,'$.cash','200')");db.commit()
            with self.assertRaises(PortfolioError):p.snapshot()
            with self.assertRaises(FileExistsError):p.initialize(2000)

    def test_below_minimum_rejected_without_reserve(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=self.make(tmp)
            result=p.reserve('buy',dict(symbol='BTC/USDT',status='OK',action='ENTER_LONG',candle_close_ms=1000),rules(minimum='10'),D('99.99'),D('100'),1000,1000)
            self.assertEqual(result['status'],'REJECTED');self.assertIsNone(p.snapshot()['pending'])
