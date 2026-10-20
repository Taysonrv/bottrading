from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from dataclasses import replace
from decimal import Decimal as D
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from spot_engine.config import load_settings
from spot_engine.execution import PaperBroker, ExecutionError
from spot_engine.risk import Account, Rules, RiskError


def rules(now=1000,minimum='.1'):
    return Rules('BTC/USDT',now,D('.000001'),D('.000001'),D('100'),D('.01'),D('.01'),D('10000000'),D(minimum),D('1000000'))


class ExecutionTests(unittest.TestCase):
    def broker(self,root):
        b=PaperBroker(root,load_settings({}));b.initialize(1000);return b

    def submit(self,b,client='entry',now=1000):
        return b.submit_entry(client,bid=D('99.99'),ask=D('100'),quote_ms=now,now_ms=now,rules=rules())

    def tick(self,b,event='tick',now=2000,bid='99.99',ask='100',available='1'):
        return b.process_quote(event,bid=D(bid),ask=D(ask),available_quantity=D(available),quote_ms=now,now_ms=now,rules=rules())

    def test_reservation_then_later_fill_and_protection(self):
        with tempfile.TemporaryDirectory() as tmp:
            b=self.broker(tmp);o=self.submit(b);s=b.snapshot()
            self.assertEqual(D(s['cash']),20);self.assertGreater(D(s['reserved']),0)
            self.assertEqual(D(s['units']),0)
            self.assertEqual(self.tick(b,now=1000)['reason'],'NO_FILL')
            self.assertEqual(self.tick(b,'early',1100)['reason'],'NO_FILL')
            self.assertEqual(self.tick(b,'later',2000)['reason'],'FILLED')
            s=b.snapshot();self.assertEqual(D(s['reserved']),0)
            self.assertEqual(D(s['units']),D(o['quantity']))
            self.assertIsNotNone(s['protection'])

    def test_duplicate_request_event_and_restart_never_duplicate_fill(self):
        with tempfile.TemporaryDirectory() as tmp:
            b=self.broker(tmp);o=self.submit(b);self.assertEqual(self.submit(b),o)
            r=self.tick(b);s=b.snapshot()
            b=PaperBroker(tmp,load_settings({}))
            self.assertEqual(self.tick(b),r)
            self.assertEqual(b.snapshot(),s)
            self.assertEqual(len(s['fills']),1)
            with self.assertRaises(ExecutionError):b.initialize(3000)

    def test_same_id_different_content_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            b=self.broker(tmp);self.submit(b)
            with self.assertRaises(ExecutionError):self.submit(b,now=2000)
            self.tick(b)
            with self.assertRaises(ExecutionError):self.tick(b,bid='99.98')
            with self.assertRaises(ExecutionError):self.submit(b,client='protect_1')

    def test_partial_fill_has_protection_and_reservation(self):
        with tempfile.TemporaryDirectory() as tmp:
            b=self.broker(tmp);self.submit(b);self.assertEqual(self.tick(b,available='.01')['reason'],'PARTIAL')
            s=b.snapshot();self.assertEqual(D(s['units']),D('.01'))
            self.assertGreater(D(s['reserved']),0);self.assertIsNotNone(s['protection'])
            self.tick(b,'remaining',3000)
            self.assertEqual(len(b.snapshot()['fills']),2)
            self.assertEqual(D(b.snapshot()['reserved']),0)

    def test_cancel_partial_releases_only_unfilled_reservation(self):
        with tempfile.TemporaryDirectory() as tmp:
            b=self.broker(tmp);self.submit(b);self.tick(b,available='.01')
            cash=b.snapshot()['cash'];b.cancel('entry',2500);s=b.snapshot()
            self.assertEqual(s['cash'],cash);self.assertEqual(D(s['units']),D('.01'))
            self.assertEqual(D(s['reserved']),0);self.assertIsNotNone(s['protection'])

    def test_stop_blocks_fills_cancels_pending_and_does_not_liquidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            b=self.broker(tmp);self.submit(b);self.tick(b,available='.01');before=b.snapshot()
            (Path(tmp)/'STOP').touch();self.assertEqual(self.tick(b,'stopped',3000)['reason'],'STOP_EXPOSED')
            s=b.snapshot();self.assertEqual(s['fills'],before['fills']);self.assertEqual(s['units'],before['units'])
            self.assertEqual(D(s['reserved']),0);self.assertIsNotNone(s['protection'])
            with self.assertRaises(ExecutionError):b.submit_exit('exit',bid=D('99'),ask=D('100'),quote_ms=3000,now_ms=3000,rules=rules())

    def test_protective_stop_waits_then_fills_at_worse_gap_price(self):
        with tempfile.TemporaryDirectory() as tmp:
            b=self.broker(tmp);self.submit(b);self.tick(b)
            old_cash=D(b.snapshot()['cash'])
            r=self.tick(b,'trigger',3000,bid='97',ask='97.01')
            self.assertEqual(r['reason'],'PROTECTIVE_STOP');self.assertEqual(len(b.snapshot()['fills']),1)
            self.tick(b,'gap',4000,bid='96',ask='96.01');s=b.snapshot()
            self.assertEqual(D(s['units']),0);self.assertIsNone(s['protection'])
            self.assertGreater(D(s['cash']),old_cash);self.assertLess(D(s['realized']),0)
            self.assertLess(D(s['fills'][-1]['price']),D('97'))

    def test_take_profit_and_partial_sale_preserve_remaining_protection(self):
        with tempfile.TemporaryDirectory() as tmp:
            b=self.broker(tmp);self.submit(b);self.tick(b)
            self.assertEqual(self.tick(b,'target',3000,bid='110',ask='110.01')['reason'],'TAKE_PROFIT')
            self.assertEqual(self.tick(b,'partial-sale',4000,bid='110',ask='110.01',available='.01')['reason'],'PARTIAL')
            self.assertIsNotNone(b.snapshot()['protection'])
            self.tick(b,'closed',5000,bid='110',ask='110.01');s=b.snapshot()
            self.assertEqual(D(s['units']),0);self.assertGreater(D(s['realized']),0)

    def test_exit_signal_cancels_unfilled_buy_and_cannot_sell_twice(self):
        with tempfile.TemporaryDirectory() as tmp:
            b=self.broker(tmp);self.submit(b);self.tick(b,available='.01')
            o=b.submit_exit('exit',bid=D('100'),ask=D('100.01'),quote_ms=2500,now_ms=2500,rules=rules())
            self.assertEqual(o['side'],'SELL');self.assertEqual(D(b.snapshot()['reserved']),0)
            self.tick(b,'exit-fill',3000,bid='100',ask='100.01')
            with self.assertRaises(ExecutionError):b.submit_exit('again',bid=D('100'),ask=D('100.01'),quote_ms=3500,now_ms=3500,rules=rules())

    def test_insufficient_liquidity_and_nonmarketable_limit_no_fill(self):
        with tempfile.TemporaryDirectory() as tmp:
            b=self.broker(tmp);self.submit(b)
            self.assertEqual(self.tick(b,available='0')['reason'],'NO_FILL')
            self.assertEqual(self.tick(b,'high',3000,bid='102',ask='102.01')['reason'],'NO_FILL')
            self.assertEqual(b.snapshot()['fills'],[])

    def test_second_entry_is_rejected_and_reservation_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            b=self.broker(tmp);self.submit(b);reserve=b.snapshot()['reserved']
            self.assertEqual(self.submit(b,'second')['status'],'REJECTED')
            self.assertEqual(b.snapshot()['active'],'entry');self.assertEqual(b.snapshot()['reserved'],reserve)

    def test_concurrent_requests_cannot_reserve_same_cash(self):
        with tempfile.TemporaryDirectory() as tmp:
            b=self.broker(tmp)
            with ThreadPoolExecutor(max_workers=2) as pool:
                results=list(pool.map(lambda name:self.submit(PaperBroker(tmp,load_settings({})),name),['one','two']))
            self.assertEqual(sorted(o['status'] for o in results),['NEW','REJECTED'])

    def test_stale_future_and_out_of_order_events_do_not_change_ledger(self):
        with tempfile.TemporaryDirectory() as tmp:
            b=self.broker(tmp);self.submit(b);self.tick(b);saved=b.snapshot()
            with self.assertRaises(ExecutionError):self.tick(b,'old',1500)
            self.assertEqual(b.snapshot(),saved)
            with self.assertRaises(ExecutionError):b.process_quote('stale',bid=D('100'),ask=D('101'),available_quantity=D('1'),quote_ms=1000,now_ms=10000,rules=rules())
            self.assertEqual(b.snapshot(),saved)

    def test_missing_checkpoint_cannot_reset_balance(self):
        with tempfile.TemporaryDirectory() as tmp:
            b=self.broker(tmp);b.path.unlink()
            with self.assertRaises(ExecutionError):b.snapshot()
            with self.assertRaises(ExecutionError):b.initialize(2000)

    def test_corrupt_cash_fails_reconciliation(self):
        with tempfile.TemporaryDirectory() as tmp:
            b=self.broker(tmp)
            import json
            with closing(sqlite3.connect(b.path)) as db:
                s=json.loads(db.execute('SELECT payload FROM ledger').fetchone()[0]);s['cash']='999'
                db.execute('UPDATE ledger SET payload=?',(json.dumps(s),));db.commit()
            with self.assertRaises(ExecutionError):b.snapshot()

    def test_minimum_rejection_does_not_reserve_or_fill(self):
        with tempfile.TemporaryDirectory() as tmp:
            b=self.broker(tmp)
            o=b.submit_entry('entry',bid=D('99.99'),ask=D('100'),quote_ms=1000,now_ms=1000,rules=rules(minimum='5'))
            self.assertEqual(o['status'],'REJECTED');self.assertEqual(D(b.snapshot()['reserved']),0)

    def test_reserved_cash_account_is_valid_but_unexplained_cash_is_not(self):
        Account(D('20'),D('15'),0,1,D('5'))
        with self.assertRaises(RiskError):Account(D('20'),D('15'),0,0,D('5'))

    def test_no_network_or_real_orders(self):
        with tempfile.TemporaryDirectory() as tmp,patch('socket.socket',side_effect=AssertionError('Network forbidden')):
            b=self.broker(tmp);self.submit(b);self.tick(b)
            self.assertFalse(hasattr(b,'exchange'));self.assertFalse(hasattr(b,'live'))

    def test_lost_response_can_be_reconciled_after_quote_expires(self):
        with tempfile.TemporaryDirectory() as tmp:
            b=self.broker(tmp);o=self.submit(b);r=self.tick(b);saved=b.snapshot()
            self.assertEqual(b.submit_entry('entry',bid=D('99.99'),ask=D('100'),quote_ms=1000,now_ms=30000,rules=rules())['filled'],b.snapshot()['orders']['entry']['filled'])
            self.assertEqual(b.process_quote('tick',bid=D('99.99'),ask=D('100'),available_quantity=D('1'),quote_ms=2000,now_ms=30000,rules=rules()),r)
            self.assertEqual(b.snapshot(),saved)

    def test_failed_fill_transaction_rolls_back_and_retry_fills_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            b=self.broker(tmp);self.submit(b);saved=b.snapshot();original=b.risk.assess;calls=[]
            def fault(*args):
                calls.append(1)
                if len(calls)==2:raise RiskError('simulated checkpoint failure')
                return original(*args)
            with patch.object(b.risk,'assess',side_effect=fault):
                with self.assertRaises(RiskError):self.tick(b)
            self.assertEqual(b.snapshot(),saved)
            self.tick(b);self.assertEqual(len(b.snapshot()['fills']),1)

    def test_daily_halt_cancels_remaining_entry_but_preserves_exposure(self):
        with tempfile.TemporaryDirectory() as tmp:
            b=self.broker(tmp);self.submit(b);self.tick(b,available='.01')
            self.tick(b,'crash',3000,bid='1',ask='1.01')
            s=b.snapshot()
            self.assertEqual(s['orders']['entry']['status'],'CANCELED')
            self.assertEqual(D(s['reserved']),0)
            self.assertEqual(len(s['fills']),1)
            self.assertIsNotNone(s['protection'])
            self.assertIn('DAILY_LOSS',[e[2] for e in b.risk.events()])

    def test_unexecutable_exit_still_cancels_remaining_buy(self):
        with tempfile.TemporaryDirectory() as tmp:
            b=self.broker(tmp);self.submit(b);self.tick(b,available='.001')
            o=b.submit_exit('exit',bid=D('99'),ask=D('99.01'),quote_ms=2500,now_ms=2500,rules=rules(minimum='1'))
            self.assertEqual(o['status'],'REJECTED')
            s=b.snapshot()
            self.assertEqual(s['orders']['entry']['status'],'CANCELED')
            self.assertEqual(D(s['reserved']),0)
            self.assertIsNotNone(s['protection'])
            self.assertEqual(D(s['units']),D('.001'))
