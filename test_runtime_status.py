import json
from pathlib import Path
import tempfile
import unittest
from runtime_status import status


class RuntimeStatusTests(unittest.TestCase):
    def write(self, root, **changes):
        state = dict(phase='waiting', updated=1000, equity=19.9, realized=-.1, orders=[])
        state.update(changes)
        path = root/'reports/local/live-small-paper.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state), encoding='utf-8')

    def test_live_process_can_have_old_quote(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); self.write(root)
            self.assertIn('atualizada', status(root, 1001)[1])
            self.assertIn('sem medição recente', status(root, 1180)[1])

    def test_error_is_not_fresh_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); self.write(root, phase='error')
            self.assertIn('Simulação erro', status(root, 1001)[1])

    def test_new_order_changes_marker_without_echoing_raw_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); self.write(root)
            before=status(root, 1001)[0]
            self.write(root, orders=[dict(time=1000, side='BUY', symbol='DOGEUSDT', secret='do-not-print')])
            marker, text=status(root,1001)
            self.assertNotEqual(before,marker)
            self.assertIn('compra DOGEUSDT',text)
            self.assertNotIn('do-not-print',text)

    def test_missing_report_does_not_crash_launcher(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(status(Path(tmp))[0], ('missing',))
