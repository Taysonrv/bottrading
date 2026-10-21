import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import operar
import system_status


class IntegrationTests(unittest.TestCase):
    def root(self,temp):
        root=Path(temp);(root/'spot_engine').mkdir()
        for name in ('main.py','config.py'):(root/'spot_engine'/name).touch()
        return root

    def test_stale_running_is_not_live(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);folder=root/'reports/local/spot-runs/ema20';folder.mkdir(parents=True)
            (folder/'status.json').write_text(json.dumps(dict(phase='RUNNING',updated_ms=1000)),encoding='utf-8')
            result=system_status.build(root,now=1000)
            self.assertFalse(result['execution']['fresh'])
            self.assertFalse(result['controller']['fresh'])
            self.assertFalse(result['real_orders_enabled'])
            self.assertFalse(result['multipair_execution_enabled'])

    def test_missing_is_not_a_running_controller(self):
        with tempfile.TemporaryDirectory() as tmp:
            result=system_status.build(tmp,now=1000)
            self.assertEqual(result['controller']['phase'],'NOT_STARTED')
            self.assertFalse(result['market']['fresh'])

    def test_commands_use_one_execution_and_separate_data_source(self):
        rows=operar.commands(Path('C:/example'),8768)
        self.assertEqual([r[0] for r in rows],['execution','market','dashboard'])
        self.assertIn('paper',rows[0][1])
        self.assertIn('6',rows[0][1])
        self.assertNotIn('live',sum([r[1] for r in rows],[]))
        self.assertEqual(rows[0][2],Path('C:/example'))

    def test_global_and_session_stop_never_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=self.root(tmp);stop=root/'STOP';stop.write_text('stop')
            with self.assertRaises(ValueError):operar.preflight(root,8768,now=1000)
            self.assertTrue(stop.exists())

    def test_expired_deadline_not_reset(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=self.root(tmp);folder=root/'reports/local/spot-runs/ema20';folder.mkdir(parents=True)
            path=folder/'session.json';path.write_text(json.dumps(dict(end_ms=1000)))
            with self.assertRaises(ValueError):operar.preflight(root,8768,now=1000)
            self.assertEqual(json.loads(path.read_text())['end_ms'],1000)

    def test_check_does_not_initialize_wallet(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=self.root(tmp)
            with patch('operar.socket.socket'):
                operar.preflight(root,8768,now=1000)
            self.assertFalse((root/'reports').exists())

    def test_invalid_port_rejected(self):
        with self.assertRaises(ValueError):operar.preflight(Path('.'),80)

    def test_corrupt_market_rows_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);folder=root/'reports/local';folder.mkdir(parents=True)
            for rows in (None,{},[None]*6):
                (folder/'multipair.json').write_text(json.dumps(dict(updated_ms=1000000,pairs=rows)))
                self.assertFalse(system_status.build(root,now=1001)['market']['fresh'])
