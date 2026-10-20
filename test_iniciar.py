import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch, MagicMock
import iniciar


class LauncherTests(unittest.TestCase):
    def test_stop_refuses_start(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); (root/'STOP').touch()
            with self.assertRaisesRegex(ValueError, 'STOP'):
                iniciar.preflight(root, 8768)

    def test_expired_session_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); report = root/'reports/local/live-small-paper.json'
            report.parent.mkdir(parents=True); original = json.dumps({'end': time.time()-1, 'cash': 17})
            report.write_text(original)
            with self.assertRaisesRegex(ValueError, 'encerrada'):
                iniciar.preflight(root, 8768)
            self.assertEqual(report.read_text(), original)

    def test_child_failure_stops_owned_children(self):
        with tempfile.TemporaryDirectory() as tmp:
            children = [MagicMock(), MagicMock(), MagicMock()]
            for i, child in enumerate(children):
                child.pid = 700+i
                child.poll.return_value = None
            children[0].poll.return_value = 1
            with patch.object(iniciar, 'ROOT', Path(tmp)), patch.object(iniciar, 'preflight', return_value='node'), patch.object(iniciar.sys, 'argv', ['iniciar.py']), patch.object(iniciar.subprocess, 'Popen', side_effect=children):
                with self.assertRaisesRegex(SystemExit, 'paper encerrou'):
                    iniciar.main()
            children[1].terminate.assert_called_once()
            children[2].terminate.assert_called_once()
            for child in children:
                child.wait.assert_called_once()

    def test_partial_start_failure_stops_previous_child(self):
        with tempfile.TemporaryDirectory() as tmp:
            child = MagicMock(); child.pid = 700; child.poll.return_value = None
            with patch.object(iniciar, 'ROOT', Path(tmp)), patch.object(iniciar, 'preflight', return_value='node'), patch.object(iniciar.sys, 'argv', ['iniciar.py']), patch.object(iniciar.subprocess, 'Popen', side_effect=[child, OSError('spawn failed')]):
                with self.assertRaisesRegex(SystemExit, 'spawn failed'):
                    iniciar.main()
            child.terminate.assert_called_once()
            child.wait.assert_called_once()
