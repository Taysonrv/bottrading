from decimal import Decimal as D
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch
from spot_engine.portfolio_run import Session
from tests.test_portfolio import rules
import portfolio_view
import operar


class PortfolioRunTests(unittest.TestCase):
    def test_scan_selects_one_reserves_then_later_fills_same_wallet(self):
        with tempfile.TemporaryDirectory() as tmp:
            client=Mock();client.fetch_time.return_value=900010
            session=Session(tmp,client);session.broker.initialize(1000)
            rows=[dict(symbol=s,status='OK',action='ENTER_LONG',candle_close_ms=900000) for s in ('BTC/USDT','ETH/USDT')]
            now=[900010]
            def book(symbol):
                return rules(symbol,now[0]),(D('99.99') if symbol=='ETH/USDT' else D('99.9'),D('100'),D('1'),D('1')),now[0]
            plan=dict(start_bar=0,end_ms=10000000)
            with patch('spot_engine.portfolio_run.scan',return_value=dict(pairs=rows)),patch.object(session,'book',side_effect=book):
                first=session.cycle(plan)
                self.assertEqual(first['pending']['symbol'],'ETH/USDT')
                self.assertEqual(len(first['fills']),0)
                now[0]=901010;client.fetch_time.return_value=now[0]
                second=session.cycle(plan)
                self.assertEqual(second['position']['symbol'],'ETH/USDT')
                self.assertEqual(len(second['fills']),1)
                self.assertLess(D(second['cash']),20)
                self.assertEqual(len(second['orders']),1)

    def test_startup_does_not_trade_old_cross(self):
        with tempfile.TemporaryDirectory() as tmp:
            client=Mock();client.fetch_time.return_value=900010
            session=Session(tmp,client);session.broker.initialize(1000)
            row=dict(symbol='BTC/USDT',status='OK',action='ENTER_LONG',candle_close_ms=900000)
            with patch('spot_engine.portfolio_run.scan',return_value=dict(pairs=[row])),patch.object(session,'book') as book:
                session.cycle(dict(start_bar=900000,end_ms=10000000))
                book.assert_not_called()
            self.assertEqual(session.broker.snapshot()['orders'],{})

    def test_view_never_initializes_and_stale_mark_is_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(portfolio_view.load(tmp)['available'])
            self.assertFalse((Path(tmp)/'reports').exists())
            session=Session(tmp,None);session.broker.initialize(1000)
            session.publish('STOPPED','TEST',dict(end_ms=1000000))
            data=portfolio_view.load(tmp)
            self.assertTrue(data['available']);self.assertFalse(data['fresh'])
            self.assertIsNone(data['equity']);self.assertEqual(data['cash'],'20')

    def test_supervisor_portfolio_does_not_launch_second_ema_wallet(self):
        rows=operar.commands(Path('C:/session'),8768,'portfolio')
        self.assertEqual([r[0] for r in rows],['execution','dashboard'])
        self.assertIn('spot_engine.portfolio_run',rows[0][1])
        self.assertNotIn('spot_engine.main',rows[0][1])
        self.assertNotIn('spot_engine.scanner',rows[0][1])

    def test_invalid_equity_does_not_break_wallet_projection(self):
        import json
        with tempfile.TemporaryDirectory() as tmp:
            session=Session(tmp,None);session.broker.initialize(1000)
            session.publish('RUNNING','TEST',dict(end_ms=9999999999999))
            path=session.folder/'status.json';report=json.loads(path.read_text())
            for bad in ('NaN','Infinity','-1','bad'):
                report['equity']=bad;path.write_text(json.dumps(report),encoding='utf-8')
                data=portfolio_view.load(tmp)
                self.assertTrue(data['available']);self.assertIsNone(data['equity']);self.assertIsNone(data['drawdown'])

    def test_projection_reconciles_with_execution_decimal_precision(self):
        from decimal import getcontext
        from spot_engine.portfolio import Portfolio
        original=Portfolio._reconcile
        def check(broker,state):
            self.assertEqual(getcontext().prec,80)
            return original(broker,state)
        with tempfile.TemporaryDirectory() as tmp:
            session=Session(tmp,None);session.broker.initialize(1000)
            with patch('portfolio_view.Portfolio._reconcile',new=check):
                self.assertTrue(portfolio_view.load(tmp)['available'])
