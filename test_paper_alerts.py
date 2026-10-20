import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
from paper_alerts import Relay


class PaperAlertTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)
        self.path=self.root/'reports/local/live-small-paper.json'
        self.path.parent.mkdir(parents=True)
        self.order=dict(time=123,side='BUY',symbol='DOGEUSDT',quantity=62,price=.08,fee=.00496)
        self.write([])
    def tearDown(self):self.tmp.cleanup()
    def write(self,orders):self.path.write_text(json.dumps(dict(orders=orders,phase='waiting',updated=1)),encoding='utf-8')
    def test_existing_orders_not_replayed_on_first_setup(self):
        self.write([self.order]); send=Mock(return_value=True); relay=Relay(self.root,send)
        relay.poll()
        self.assertNotIn('Compra',send.call_args.args[0])
    def test_new_order_sent_once_across_restart(self):
        send=Mock(return_value=True); relay=Relay(self.root,send)
        self.write([self.order]); relay.poll()
        self.assertIn('Compra DOGEUSDT',send.call_args.args[0])
        self.assertIn('Nenhuma ordem real',send.call_args.args[0])
        send.reset_mock(); Relay(self.root,send).poll()
        self.assertNotIn('Compra',send.call_args.args[0])
    def test_failed_delivery_retried(self):
        send=Mock(side_effect=[False,True]); relay=Relay(self.root,send)
        self.write([self.order]); relay.poll();relay.poll()
        self.assertEqual(send.call_count,2)
        self.assertEqual(send.call_args_list[0],send.call_args_list[1])
    def test_unchanged_health_not_repeated(self):
        send=Mock(return_value=True); relay=Relay(self.root,send)
        relay.poll();relay.poll();self.assertEqual(send.call_count,1)
    def test_corrupt_notification_state_not_silently_reset(self):
        (self.path.parent/'paper-alerts.json').write_text('[]')
        with self.assertRaises(ValueError):Relay(self.root,Mock())
