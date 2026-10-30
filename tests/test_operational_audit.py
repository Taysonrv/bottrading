from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
from operational_audit import load,recent_events
from spot_engine.main import save


class OperationalAuditTests(TestCase):
    def test_missing_state_never_creates_database(self):
        with TemporaryDirectory() as tmp:
            a=load(tmp,1000000)
            self.assertEqual(a['state'],'ENGINE_UNCONFIRMED')
            self.assertFalse(a['ledger_available'])
            self.assertFalse((Path(tmp)/'reports').exists())

    def test_stale_running_not_mistaken_for_active_and_stop_priority(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp);folder=root/'reports/local/portfolio';folder.mkdir(parents=True)
            save(folder/'status.json',dict(updated_ms=1,phase='RUNNING',end_ms=2000000))
            self.assertEqual(load(root,1000000)['state'],'ENGINE_UNCONFIRMED')
            (root/'STOP').write_text('test')
            self.assertEqual(load(root,1000000)['state'],'STOP')

    def test_full_ledger_costs_and_current_context_are_separate(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp);folder=root/'reports/local/portfolio';folder.mkdir(parents=True)
            save(folder/'status.json',dict(updated_ms=1000000,phase='RUNNING',end_ms=2000000))
            save(folder.parent/'system-run.json',dict(updated_ms=1000000))
            save(folder/'radar.json',dict(updated_ms=1000000,pairs=[dict(symbol='SOL/USDT',action='HOLD',reason='NO_CROSS')]))
            fills=[dict(side='BUY',quantity='1',price='10',fee='.01',time_ms=1,symbol='SOL/USDT'),dict(side='SELL',quantity='1',price='11',fee='.011',time_ms=2,symbol='SOL/USDT',reason='SIGNAL_EXIT')]
            with patch('operational_audit.ledger',return_value=dict(fills=fills,orders={},position=None,pending=None,halt=None,cash='20.979',realized='.979',fees='.021')):
                a=load(root,1000000)
            self.assertEqual(a['state'],'RECENT_REPORTS')
            self.assertEqual(a['trades'][0]['net_pnl'],'0.979')
            self.assertEqual(a['trades'][0]['entry_indicators'],'NOT_RECORDED_AT_ORDER_TIME')
            self.assertEqual(a['decisions'][0]['context_reason'],'NO_CROSS')

    def test_event_parser_preserves_unknown_cause_and_omits_secrets(self):
        with TemporaryDirectory() as tmp:
            path=Path(tmp)/'events';path.write_text('broken\n'+ '{"kind":"PREVIOUS_RUN_WITHOUT_SHUTDOWN_RECORD","reason":"CAUSE_UNKNOWN","token":"secret"}\n')
            rows=recent_events(path)
            self.assertEqual(rows[0]['reason'],'CAUSE_UNKNOWN');self.assertNotIn('token',rows[0])
