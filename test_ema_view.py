from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from ema_view import load


class EmaViewTests(unittest.TestCase):
    def fixture(self,root):
        folder=Path(root)/'reports/local/spot-runs/ema20';folder.mkdir(parents=True)
        status=dict(mode='PAPER',phase='RUNNING',reason='NO_FILL',updated_ms=100000,end_ms=1000000,symbol='BTC/USDT',capital='20',max_order_budget='6',equity='20',pnl='0',cash='20',reserved='0',units='0',realized='0',fees='0',price_received_ms=100000,last_signal='WARMUP_REPLAYED',approved=False,real_orders=0)
        (folder/'status.json').write_text(json.dumps(status),encoding='utf-8')
        path=folder/'reports/local/spot-execution/paper.sqlite';path.parent.mkdir(parents=True)
        ledger=dict(cash='20',units='0',cost='0',reserved='0',realized='0',fees='0',orders={},fills=[],protection=None)
        with closing(sqlite3.connect(path)) as db:
            db.execute('CREATE TABLE ledger(id INTEGER PRIMARY KEY,payload TEXT)');db.execute('INSERT INTO ledger VALUES(1,?)',(json.dumps(ledger),));db.commit()
        return folder,path,status,ledger

    def test_real_zero_is_not_missing_and_ledger_not_modified(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder,path,_,_=self.fixture(tmp);before=path.read_bytes()
            r=load(tmp,101)
            self.assertTrue(r['available']);self.assertTrue(r['fresh']);self.assertEqual(r['equity'],20)
            self.assertEqual(r['buy_fills'],0);self.assertEqual(path.read_bytes(),before)

    def test_stale_stopped_and_global_stop(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder,path,s,l=self.fixture(tmp)
            self.assertFalse(load(tmp,161)['fresh']);(Path(tmp)/'STOP').touch()
            self.assertTrue(load(tmp,101)['stop']);s['phase']='STOPPED'
            (folder/'status.json').write_text(json.dumps(s));self.assertFalse(load(tmp,101)['fresh'])

    def test_missing_invalid_live_and_nonfinite_are_unavailable(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(load(tmp)['status'],'missing')
            folder,path,s,l=self.fixture(tmp)
            for change in ({'mode':'LIVE'},{'equity':'NaN'},{'approved':True}):
                with self.subTest(change=change):
                    (folder/'status.json').write_text(json.dumps(dict(s,**change)))
                    self.assertEqual(load(tmp)['status'],'invalid')

    def test_order_fields_only_and_no_raw_secrets(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder,path,s,l=self.fixture(tmp)
            l['orders']['entry_1']=dict(side='BUY',status='REJECTED',created_ms=100000,quantity='0',filled='0',limit='0',reason='MINIMUM_OR_LOT',secret='must-not-leak')
            with closing(sqlite3.connect(path)) as db:db.execute('UPDATE ledger SET payload=?',(json.dumps(l),));db.commit()
            r=load(tmp,101)
            self.assertEqual(r['orders'][0]['status'],'REJECTED');self.assertNotIn('must-not-leak',json.dumps(r))

    def test_inconsistent_ledger_is_not_displayed_as_cash(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder,path,s,l=self.fixture(tmp);l['cash']='999'
            with closing(sqlite3.connect(path)) as db:db.execute('UPDATE ledger SET payload=?',(json.dumps(l),));db.commit()
            self.assertEqual(load(tmp)['status'],'invalid')

    def test_snapshot_transition_hides_old_equity(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder,path,s,l=self.fixture(tmp)
            l.update(reserved='5')
            with closing(sqlite3.connect(path)) as db:db.execute('UPDATE ledger SET payload=?',(json.dumps(l),));db.commit()
            r=load(tmp,101)
            self.assertTrue(r['in_transition']);self.assertIsNone(r['equity']);self.assertEqual(r['reserved'],5)

    def risk_fixture(self,folder,**changes):
        path=folder/'reports/local/spot-risk/risk.sqlite';path.parent.mkdir(parents=True)
        state=dict(last_ms=100000,day=0,peak='20',day_equity='20',equity='20',daily_halted=False,drawdown_halted=False,stop_active=False)
        state.update(changes)
        with closing(sqlite3.connect(path)) as db:
            db.execute('CREATE TABLE checkpoint(id INTEGER PRIMARY KEY,payload TEXT)');db.execute('INSERT INTO checkpoint VALUES(1,?)',(json.dumps(state),));db.commit()

    def test_risk_checkpoint_is_read_only_and_independent(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder,path,s,l=self.fixture(tmp);self.risk_fixture(folder,equity='18',daily_halted=True,drawdown_halted=True)
            r=load(tmp,101)
            self.assertTrue(r['risk']['available']);self.assertTrue(r['risk']['drawdown_halted'])
            self.assertAlmostEqual(r['risk']['drawdown'],.1)
            self.assertEqual(r['equity'],20) # Different checkpoint timestamps/sources aren't merged.
            self.assertEqual(r['age_seconds'],1)

    def test_missing_or_invalid_risk_is_not_reported_as_safe(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder,path,s,l=self.fixture(tmp)
            self.assertFalse(load(tmp,101)['risk']['available'])
            self.risk_fixture(folder,daily_halted=0)
            self.assertFalse(load(tmp,101)['risk']['available'])

    def test_future_report_age_is_unknown_not_recent(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.fixture(tmp);r=load(tmp,99)
            self.assertIsNone(r['age_seconds']);self.assertFalse(r['fresh'])
