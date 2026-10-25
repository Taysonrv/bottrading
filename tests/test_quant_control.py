import copy
import json
from pathlib import Path
import tempfile
import unittest
from dataclasses import replace
from unittest.mock import patch
from ai_shadow.journal import Journal
from spot_engine.data import Candle,History
from quant_control.state import build
from quant_control.contracts import validate
from quant_control.policy import assess
from quant_control.jev import request,parse,DisabledProvider
from quant_control.review import daily,summarize
from quant_control.service import Control
from quant_control.calibration import mature,report,quarter_kelly_research

STEP=900000;NOW=61*STEP


def history():
    cs=tuple(Candle(i*STEP,100,101,99,100,10) for i in range(61))
    return History('BTC/USDT','15m',0,NOW,NOW,cs,0,0)


def snapshot():
    return build(dict(symbol='BTC/USDT',bid=100,ask=100.01,bid_qty=3,ask_qty=1,received_ms=NOW),
        history(),dict(inventory_fraction=0,drawdown=0,daily_loss=0),NOW)


def decision(**changes):
    d=dict(regime='trending',direction='long',probabilities=dict(long=.94,short=.03,neutral=.03),
        confidence=.91,toxic_flow=False,setup_quality=2,risk_state='safe',model='test-only',schema='q1')
    d.update(changes);return d


class QuantTests(unittest.TestCase):
    def test_numeric_state_math_and_bounds(self):
        s=snapshot();n=s['numeric']
        self.assertAlmostEqual(n['mid'],100.005);self.assertEqual(n['imb'],.5)
        self.assertEqual(n['rv'],0);self.assertEqual(n['r60'],0);self.assertEqual(n['atr'],.02)
        self.assertLess(s['bytes'],1000);self.assertFalse(s['token_count_verified']);self.assertIsNone(s['token_count'])
        self.assertFalse(s['flow_verified']);self.assertFalse(s['origin_timestamp_available'])

    def test_causal_book_candles_and_unknown_risk(self):
        h=history();b=dict(symbol='BTC/USDT',bid=100,ask=101,bid_qty=1,ask_qty=1,received_ms=NOW)
        self.assertIsNone(build(b,h,{},NOW)['numeric']['dl'])
        for bad in (dict(b,received_ms=NOW+1),dict(b,received_ms=NOW-2001),dict(b,ask=99),dict(b,bid_qty=0)):
            with self.assertRaises(ValueError):build(bad,h,{},NOW)
        with self.assertRaises(ValueError):build(b,h,{},NOW-1)

    def test_contract_rejects_probabilities_override_and_float_quality(self):
        self.assertEqual(validate(decision())['setup_quality'],2)
        for d in (decision(confidence=.94),decision(setup_quality=2.5),decision(toxic_flow='false'),
            decision(probabilities=dict(long=.9,short=.2,neutral=.1)),dict(decision(),order_size=100)):
            with self.assertRaises(ValueError):validate(d)

    def test_gates_hold_even_high_confidence_and_no_exec_path(self):
        c=dict(stopped=False,fresh=True,session_active=True,edge_validated=True,calibration_verified=True,
               positions=0,pending=0,risk_ledger_clear=True,decision_state_fresh=True)
        s=snapshot();original=copy.deepcopy(s)
        p=assess(s,decision(),c)
        self.assertIn('FLOW_VERIFIED',p['gates_failed']);self.assertIn('TOKEN_BUDGET_VERIFIED',p['gates_failed'])
        self.assertEqual(s,original);self.assertFalse(p['execution_authorized']);self.assertFalse(p['kelly_enabled'])
        s.update(flow_verified=True,token_count_verified=True,token_count=200)
        p=assess(s,decision(),c);self.assertEqual(p['action'],'RESEARCH_CANDIDATE')
        self.assertFalse(p['execution_authorized'])
        for flags,expected in ((dict(c,stopped=True),'STOP_CLEAR'),(dict(c,edge_validated=False),'HISTORICAL_EDGE_VALIDATED')):
            self.assertIn(expected,assess(s,decision(),flags)['gates_failed'])

    def test_crisis_low_confidence_and_daily_drawdown(self):
        s=snapshot();s['numeric'].update(dd=.10,dl=.03)
        p=assess(s,decision(regime='crisis'),{})
        self.assertIn('CRISIS_REGIME',p['review_reasons'])
        self.assertIn('DRAWDOWN_UNDER_10_PERCENT',p['gates_failed'])
        self.assertIn('DAILY_LOSS_UNDER_3_PERCENT',p['gates_failed'])
        d=decision(probabilities=dict(long=.6,short=.3,neutral=.1),confidence=.4)
        self.assertIn('LOW_CONFIDENCE',assess(snapshot(),d,{})['review_reasons'])

    def test_provider_request_contract_and_no_paid_transport(self):
        s=snapshot();r=request(s)
        self.assertEqual(len(r['questions']),5);self.assertEqual(r['state'],s['encoded'])
        self.assertTrue(all(q['type']=='choice' for q in r['questions'].values()))
        response=dict(model='test-provider',answers={})
        choices=dict(regime='trending',direction='long',setup_quality='2',toxic_flow='false',risk_state='safe')
        for name,q in r['questions'].items():
            keys=list(q['criteria']);chosen=choices[name]
            ps={k:float(k==chosen) for k in keys}
            response['answers'][name]=dict(type='choice',choice=chosen,probabilities=ps,confidence=1.)
        parsed=parse(response);self.assertEqual(parsed['confidence'],1)
        self.assertEqual(parsed['setup_quality'],2)
        self.assertFalse(DisabledProvider().evaluate(s)['provider_enabled'])
        self.assertIsNone(DisabledProvider().evaluate(s)['decision'])

    def test_daily_review_reads_full_journal_without_fake_brier(self):
        with tempfile.TemporaryDirectory() as root:
            j=Journal(Path(root)/'lab.sqlite','p','c')
            try:
                for i in range(3):
                    j.reserve(str(i),{'number':i},0)
                    j.finish(str(i),dict(policy=dict(gates_failed=['NO_EDGE'],review_reasons=['LOW_CONFIDENCE'])))
                with patch('quant_control.review.ledger',return_value=dict(fills=[],realized='0',fees='0',position=None,pending=None)):
                    r=daily(j,Path(root),NOW)
                    self.assertEqual(r['completed'],3);self.assertEqual(r['failed_gates']['NO_EDGE'],3)
                    self.assertIsNone(r['brier']);self.assertFalse(r['auto_apply'])
                    self.assertIsNone(daily(j,Path(root),NOW+1000))
                    self.assertIsNotNone(daily(j,Path(root),NOW+86400000))
                self.assertFalse((Path(root)/'reports/local/portfolio').exists())
            finally:j.close()

    def test_stop_does_not_fetch_or_create_wallet(self):
        with tempfile.TemporaryDirectory() as root:
            Path(root,'STOP').touch();client=object();c=Control(Path(root),client)
            try:
                r=c.cycle();self.assertEqual(r['reason'],'STOP');self.assertEqual(r['calls_paid'],0)
                self.assertFalse((Path(root)/'reports/local/portfolio').exists())
            finally:c.close()

    def test_real_label_matures_only_after_entry_and_horizon(self):
        r=dict(symbol='BTC/USDT',decision=decision(),source='REAL_PROVIDER_RESPONSE',predicted_ms=1000)
        entry=dict(time_ms=2000,received_ms=2001,bid=100,ask=100.01)
        exit=dict(time_ms=3602000,received_ms=3602001,bid=102,ask=102.01)
        self.assertIsNone(mature(r,entry,exit,3602000))
        label=mature(r,entry,exit,3602001);self.assertEqual(label['outcome'],'long')
        scored=report([label],3602001,'test-only','q1')
        self.assertAlmostEqual(scored['multiclass_brier'],.0054)
        self.assertFalse(scored['approved'])
        self.assertIsNone(mature(dict(r,source='FIXTURE'),entry,exit,3602001))
        with self.assertRaises(ValueError):report([label,label],3602001,'test-only','q1')
        with self.assertRaises(ValueError):report([label],3602001,'another-model','q1')

    def test_kelly_never_uses_confidence_as_automatic_allocation(self):
        r=quarter_kelly_research(.6,2,1)
        self.assertAlmostEqual(r['fraction'],.1);self.assertFalse(r['kelly_enabled'])
        self.assertEqual(quarter_kelly_research(.2,1,1)['fraction'],0)

    def test_cached_inference_never_caches_current_risk_or_clock(self):
        class Client:
            def fetch_book(self,symbol):return dict(symbol=symbol.replace('/',''),bidPrice='100',askPrice='100.01',bidQty='3',askQty='1')
        account=dict(inventory_fraction=0,drawdown=0,daily_loss=0,session_active=False,positions=0,
                     pending=0,ledger_halt=None,phase='STOPPED',account_received_ms=NOW)
        with tempfile.TemporaryDirectory() as root,patch('quant_control.service.time.time',return_value=NOW/1000),\
             patch('quant_control.service.download',side_effect=lambda c,s,*a:replace(history(),symbol=s)),\
             patch('quant_control.service.load_account',side_effect=lambda *a:dict(account)),\
             patch('quant_control.service.daily'):
            c=Control(Path(root),Client())
            try:
                first=c.cycle();self.assertTrue(first['healthy'])
                self.assertTrue(all('SESSION_ACTIVE' in p['policy']['gates_failed'] for p in first['pairs']))
                account['session_active']=True
                with patch('quant_control.service.time.time',return_value=(NOW+30000)/1000):second=c.cycle()
                self.assertTrue(all('SESSION_ACTIVE' not in p['policy']['gates_failed'] for p in second['pairs']))
                self.assertTrue(all('MODEL_STATE_FRESH' in p['policy']['gates_failed'] for p in second['pairs']))
                self.assertEqual(c.journal.db.execute('SELECT count(*) FROM requests').fetchone()[0],4)
                with self.assertRaisesRegex(ValueError,'CLOCK_REVERSED'):c.cycle()
            finally:c.close()

    def test_unavailable_data_is_durable_and_never_logs_provider_details(self):
        with tempfile.TemporaryDirectory() as root,patch('quant_control.service.time.time',return_value=NOW/1000),\
             patch('quant_control.service.download',side_effect=ValueError('SECRET_PROVIDER_BODY')),\
             patch('quant_control.service.daily'):
            c=Control(Path(root),object())
            try:
                r=c.cycle();self.assertFalse(r['healthy']);self.assertEqual(r['calls_paid'],0)
                c.cycle()
                stored=c.journal.db.execute('SELECT snapshot,result FROM requests').fetchall()
                self.assertEqual(len(stored),4)
                self.assertNotIn('SECRET_PROVIDER_BODY',str([tuple(row) for row in stored]))
                self.assertTrue(all(p['policy']['action']=='HOLD' for p in r['pairs']))
            finally:c.close()


if __name__=='__main__':unittest.main()
