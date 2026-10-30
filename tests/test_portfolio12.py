from pathlib import Path
from tempfile import TemporaryDirectory
from decimal import Decimal as D
from unittest import TestCase
from unittest.mock import Mock,patch
from portfolio12 import Portfolio,PortfolioError,SYMBOLS
from portfolio_backend import factory
from prepare_portfolio12 import prepare
from tests.test_portfolio import rules
import portfolio_view
import operar
from portfolio12_run import Session


class Portfolio12Tests(TestCase):
    def reserve(self,p,symbol,key,now=1000):
        return p.reserve(key,dict(symbol=symbol,status='OK',action='ENTER_LONG',candle_close_ms=now),
            rules(symbol,now),D('99.99'),D('100'),now,now)

    def test_new_pair_round_trip_reconciles_same_twenty_usdt(self):
        with TemporaryDirectory() as tmp:
            root=prepare(Path(tmp)/'new');p=factory(root);p.initialize(1000)
            order=self.reserve(p,'LINK/USDT','link')
            self.assertLessEqual(D(order['reserved']),6)
            self.assertEqual(p.quote('fill',rules('LINK/USDT',2000),D('99.99'),D('100'),D(1),2000,2000),'BUY_FILLED')
            with self.assertRaises(PortfolioError):self.reserve(p,'AVAX/USDT','second',3000)
            self.assertEqual(p.quote('exit',rules('LINK/USDT',3000),D(105),D('105.01'),D(1),3000,3000),'EXIT_PENDING')
            self.assertEqual(p.quote('sell',rules('LINK/USDT',4000),D(105),D('105.01'),D(1),4000,4000),'SELL_FILLED')
            resumed=factory(root);self.assertEqual(len(resumed.snapshot()['fills']),2)
            self.assertGreater(D(resumed.snapshot()['cash']),20)
            self.assertTrue(portfolio_view.load(root)['available'])

    def test_legacy_profile_and_source_identity_remain_separate(self):
        from spot_engine.portfolio import Portfolio as Legacy
        with TemporaryDirectory() as tmp:
            self.assertIsInstance(factory(tmp),Legacy)
            new=prepare(Path(tmp)/'new')
            self.assertIsInstance(factory(new),Portfolio)
            self.assertNotEqual(factory(new).identity,Legacy(new).identity)
            self.assertEqual(len(SYMBOLS),12)
            self.assertIn('portfolio12_run',operar.commands(new,8769,'portfolio')[0][1])
            with self.assertRaises(FileExistsError):prepare(new)

    def test_stop_and_unknown_symbol_refuse_new_orders(self):
        with TemporaryDirectory() as tmp:
            root=prepare(Path(tmp)/'new');p=factory(root);p.initialize(1000)
            with self.assertRaises(PortfolioError):self.reserve(p,'UNKNOWN/USDT','bad')
            (root/'STOP').touch()
            self.assertEqual(self.reserve(p,'ADA/USDT','stopped')['status'],'REJECTED')
            self.assertEqual(p.snapshot()['cash'],'20')

    def test_invalid_profile_does_not_fall_back_to_old_wallet(self):
        with TemporaryDirectory() as tmp:
            (Path(tmp)/'portfolio12.json').write_text('{}')
            with self.assertRaises(ValueError):factory(tmp)
            self.assertFalse(portfolio_view.load(tmp)['available'])

    def test_runner_reserves_new_symbol_and_does_not_replay_initial_bar(self):
        with TemporaryDirectory() as tmp:
            root=prepare(Path(tmp)/'new');client=Mock();client.fetch_time.return_value=900010
            session=Session(root,client);session.broker.initialize(1000)
            row=dict(symbol='LINK/USDT',status='OK',action='ENTER_LONG',candle_close_ms=900000)
            with patch('portfolio12_run.base_scan',return_value=dict(pairs=[row])),patch.object(session,'book',return_value=(rules('LINK/USDT',900010),(D('99.99'),D(100),D(1),D(1)),900010)):
                r=session.cycle(dict(start_bar=0,end_ms=10000000))
            self.assertEqual(r['pending']['symbol'],'LINK/USDT')
            self.assertEqual(len(r['symbols']),12)
            self.assertEqual(r['fills'],[])

    def test_marker_cannot_migrate_legacy_cash(self):
        from spot_engine.portfolio import Portfolio as Legacy
        with TemporaryDirectory() as tmp:
            Legacy(tmp).initialize(1000)
            (Path(tmp)/'portfolio12.json').write_text('{"variant":"PAPER12_V1"}')
            with self.assertRaises(PortfolioError):factory(tmp).snapshot()
