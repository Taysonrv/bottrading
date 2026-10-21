import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from portfolio_alerts import Relay, fill_messages
from spot_engine.main import save


def fill(side='BUY',price='100',fee='.1'):
    return dict(side=side,symbol='BTC/USDT',quantity='1',price=price,fee=fee)


class AlertTests(unittest.TestCase):
    def setup_relay(self,tmp,send=None):
        folder=Path(tmp)/'reports/local/portfolio';folder.mkdir(parents=True)
        save(folder/'status.json',dict(updated_ms=1000000,phase='RUNNING',reason='WAITING_SIGNAL'))
        return Relay(tmp,send,clock=lambda:1000)

    def test_first_activation_skips_old_fills_and_restart_no_duplicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            sent=[];relay=self.setup_relay(tmp,lambda text:sent.append(text) or True)
            with patch('portfolio_alerts.ledger',return_value=dict(identity='v1',fills=[fill()],halt=None)):
                relay.poll();Relay(tmp,relay.send,clock=lambda:1000).poll()
            self.assertEqual(len(sent),1);self.assertIn('Estado: RUNNING',sent[0])

    def test_new_buy_then_sell_reports_net_both_fees(self):
        with tempfile.TemporaryDirectory() as tmp:
            sent=[];relay=self.setup_relay(tmp,lambda text:sent.append(text) or True)
            s=dict(identity='v1',fills=[],halt=None)
            with patch('portfolio_alerts.ledger',return_value=s):
                relay.poll();s['fills'].append(fill());relay.poll()
                s['fills'].append(fill('SELL','102','.102'));relay.poll();relay.poll()
            self.assertEqual(len(sent),3)
            self.assertIn('Compra BTC/USDT',sent[1]);self.assertIn('1.798 USDT',sent[2])

    def test_failed_sender_preserves_outbox_for_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            relay=self.setup_relay(tmp,lambda text:False)
            with patch('portfolio_alerts.ledger',return_value=dict(identity='v1',fills=[],halt=None)):
                self.assertEqual(relay.poll(),'RETRY_PENDING')
                relay.send=lambda text:True
                self.assertEqual(relay.poll(),'SENT')
            state=json.loads(relay.path.read_text());self.assertEqual(state['queue'],[])

    def test_disabled_does_not_send_but_collects(self):
        with tempfile.TemporaryDirectory() as tmp:
            relay=self.setup_relay(tmp)
            with patch('portfolio_alerts.ledger',return_value=dict(identity='v1',fills=[],halt=None)):
                self.assertEqual(relay.poll(),'DISABLED')
            self.assertEqual(len(json.loads(relay.path.read_text())['queue']),1)

    def test_full_ledger_not_dashboard_last100(self):
        with tempfile.TemporaryDirectory() as tmp:
            relay=self.setup_relay(tmp);s=dict(identity='v1',fills=[],halt=None)
            with patch('portfolio_alerts.ledger',return_value=s):
                relay.poll();s['fills']=[fill('BUY' if i%2==0 else 'SELL') for i in range(102)]
                relay.poll()
            state=json.loads(relay.path.read_text());self.assertEqual(state['cursor'],102);self.assertEqual(len(state['queue']),103)

    def test_rewritten_history_fails_instead_of_sending(self):
        with tempfile.TemporaryDirectory() as tmp:
            relay=self.setup_relay(tmp);s=dict(identity='v1',fills=[fill()],halt=None)
            with patch('portfolio_alerts.ledger',return_value=s):
                relay.poll();s['fills'][0]['price']='200'
                with self.assertRaises(ValueError):relay.poll()

    def test_stale_warning_suppressed_until_health_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            sent=[];relay=self.setup_relay(tmp,lambda text:sent.append(text) or True)
            with patch('portfolio_alerts.ledger',return_value=dict(identity='v1',fills=[],halt=None)):
                relay.poll();relay.clock=lambda:1200;relay.poll();relay.poll()
            self.assertEqual(len(sent),2);self.assertIn('STALE',sent[-1])
