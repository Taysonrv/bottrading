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

    def test_planned_exit_requires_clean_code_and_finished_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);path=root/'reports/local/live-small-paper.json';path.parent.mkdir(parents=True)
            path.write_text(json.dumps({'phase':'stopped','end':100}))
            self.assertEqual(iniciar.exit_reason(root,'paper',0,101),'deadline')
            self.assertIsNone(iniciar.exit_reason(root,'paper',1,101))
            self.assertIsNone(iniciar.exit_reason(root,'panel',0,101))
            path.write_text(json.dumps({'phase':'waiting','end':100}))
            self.assertIsNone(iniciar.exit_reason(root,'paper',0,101))
    def test_stop_is_distinct_from_unexpected_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'STOP').touch()
            self.assertEqual(iniciar.exit_reason(root,'stream',0,100),'stop')
            self.assertIsNone(iniciar.exit_reason(root,'stream',1,100))
    def test_shutdown_reports_do_not_reset_or_overwrite_account(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);path=root/'reports/local/live-small-paper.json';path.parent.mkdir(parents=True)
            original=json.dumps({'initial':20,'cash':20,'equity':20,'pnl':0,'realized':0,'unrealized':0,'orders':[],'curve':[],'position':None})
            path.write_text(original)
            from auditar import finalize
            first=finalize(root,'interrupted');second=finalize(root,'deadline')
            self.assertNotEqual(first,second)
            self.assertEqual(path.read_text(),original)
            self.assertTrue((first.with_suffix('.md')).exists())
            self.assertEqual(json.loads(second.read_text())['end_reason'],'deadline')

    def test_deadline_stops_remaining_components_and_saves_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = root/'reports/local/live-small-paper.json'
            report.parent.mkdir(parents=True)
            report.write_text(json.dumps({'phase':'stopped','end':100}))
            children = [MagicMock(), MagicMock(), MagicMock()]
            for i, child in enumerate(children):
                child.pid = 800+i
                child.poll.return_value = None
            children[0].poll.return_value = 0
            with patch.object(iniciar, 'ROOT', root), patch.object(iniciar, 'preflight', return_value='node'), patch.object(iniciar.sys, 'argv', ['iniciar.py']), patch.object(iniciar.subprocess, 'Popen', side_effect=children), patch.object(iniciar.auditar, 'finalize', return_value=root/'summary.json') as finalize:
                iniciar.main()
            finalize.assert_called_once_with(root, 'deadline')
            children[1].terminate.assert_called_once()
            children[2].terminate.assert_called_once()
            self.assertEqual(json.loads(report.read_text()), {'phase':'stopped','end':100})
