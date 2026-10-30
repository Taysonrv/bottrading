from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock,patch
from decimal import Decimal as D
from decision_trace import record,lookup
from portfolio12_run import Session
from tests.test_portfolio import rules


class DecisionTraceTests(TestCase):
    def test_immutable_idempotent_and_whitelisted(self):
        with TemporaryDirectory() as tmp:
            row=dict(symbol='LINK/USDT',action='ENTER_LONG',candle_close_ms=1000,ema_fast=99,api_key='secret')
            a=record(tmp,'identity','ENTRY_INTENT','order',1100,row,quote={'bid':'100','secret':'no'})
            b=record(tmp,'identity','ENTRY_INTENT','order',1200,row,quote={'bid':'100','secret':'no'})
            self.assertEqual(a,b)
            self.assertNotIn('secret',str(a));self.assertNotIn('api_key',str(a))
            with self.assertRaisesRegex(ValueError,'TRACE_EVIDENCE_CONFLICT'):
                record(tmp,'identity','ENTRY_INTENT','order',1200,row,quote={'bid':'101'})

    def test_future_or_nonfinite_signal_leaves_no_record(self):
        with TemporaryDirectory() as tmp:
            for row in (dict(candle_close_ms=2000),dict(candle_close_ms=1000,ema_fast=float('nan'))):
                with self.assertRaises(ValueError):record(tmp,'identity','SIGNAL','key',1000,row)
            self.assertFalse((Path(tmp)/'reports').exists())

    def test_entry_audit_failure_blocks_new_reservation(self):
        with TemporaryDirectory() as tmp:
            client=Mock();client.fetch_time.return_value=900010
            s=Session(tmp,client);s.broker.initialize(1000)
            row=dict(symbol='LINK/USDT',status='OK',action='ENTER_LONG',candle_close_ms=900000)
            with patch('portfolio12_run.base_scan',return_value={'pairs':[row]}),patch.object(s,'book',return_value=(rules('LINK/USDT',900010),(D('99.99'),D(100),D(1),D(1)),900010)),patch('portfolio12_run.record',side_effect=OSError('disk')):
                report=s.cycle(dict(start_bar=0,end_ms=10000000))
            self.assertEqual(report['reason'],'AUDIT_ENTRY_BLOCKED')
            self.assertIsNone(s.broker.snapshot()['pending'])
            self.assertEqual(s.broker.snapshot()['cash'],'20')

    def test_reservation_has_prior_evidence_with_exact_quote(self):
        with TemporaryDirectory() as tmp:
            client=Mock();client.fetch_time.return_value=900010
            s=Session(tmp,client);s.broker.initialize(1000)
            row=dict(symbol='LINK/USDT',status='OK',action='ENTER_LONG',candle_close_ms=900000,ema_fast=100)
            with patch('portfolio12_run.base_scan',return_value={'pairs':[row]}),patch.object(s,'book',return_value=(rules('LINK/USDT',900010),(D('99.99'),D(100),D(1),D(1)),900010)):
                r=s.cycle(dict(start_bar=0,end_ms=10000000))
            key=r['pending']['id'];proof=lookup(tmp,s.broker.identity,'ENTRY_INTENT',key)
            self.assertEqual(proof['quote']['ask'],'100')
            self.assertEqual(proof['signal']['ema_fast'],100)
            self.assertEqual(lookup(tmp,s.broker.identity,'RESERVATION',key)['outcome']['status'],'NEW')

    def test_audit_failure_does_not_block_existing_position_exit(self):
        with TemporaryDirectory() as tmp:
            client=Mock();client.fetch_time.return_value=900010
            s=Session(tmp,client);s.broker.initialize(1000)
            buy=dict(symbol='LINK/USDT',status='OK',action='ENTER_LONG',candle_close_ms=1000)
            s.broker.reserve('buy',buy,rules('LINK/USDT',1000),D('99.99'),D(100),1000,1000)
            s.broker.quote('fill',rules('LINK/USDT',2000),D('99.99'),D(100),D(1),2000,2000)
            row=dict(symbol='LINK/USDT',status='OK',action='EXIT_LONG',candle_close_ms=900000)
            with patch('portfolio12_run.base_scan',return_value={'pairs':[row]}),patch.object(s,'book',return_value=(rules('LINK/USDT',900010),(D('99.99'),D(100),D(1),D(1)),900010)),patch('portfolio12_run.record',side_effect=OSError('disk')):
                r=s.cycle(dict(start_bar=0,end_ms=10000000))
            self.assertEqual(r['reason'],'EXIT_PENDING')
            self.assertEqual(r['decision_audit'],'DEGRADED')
            self.assertEqual(len(r['fills']),1)
