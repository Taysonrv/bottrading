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

    def test_stop_overrides_fresh_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); self.write(root); (root/'STOP').touch()
            self.assertIn('bloqueada por STOP',status(root,1001)[1])

    def test_halted_cannot_look_healthy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); self.write(root, halted=True)
            self.assertIn('bloqueada por drawdown',status(root,1001)[1])

    def test_valid_json_with_wrong_shape_does_not_stop_launcher(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); self.write(root)
            path=root/'reports/local/live-small-paper.json'
            path.write_text('[]')
            self.assertEqual(status(root)[0],('invalid',))
            self.write(root, orders={'unexpected':'shape'})
            self.assertIn('última ordem: nenhuma',status(root,1001)[1])

    def test_starting_and_future_timestamp_are_not_healthy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); self.write(root,phase='starting')
            self.assertIn('sem medição recente',status(root,1001)[1])
            self.write(root,updated=2000)
            self.assertIn('sem medição recente',status(root,1001)[1])

    def test_age_counts_and_open_position_are_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            self.write(root,position=dict(symbol='DOGEUSDT',units=5),orders=[dict(side='BUY'),dict(side='SELL')])
            message=status(root,1181)[1]
            self.assertIn('idade da medição: 181s',message)
            self.assertIn('posição: DOGEUSDT',message)
            self.assertIn('1 compras / 1 vendas',message)

    def test_no_false_position_or_numeric_boolean(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            self.write(root,position='secret-not-for-output',equity=True,updated=True)
            message=status(root,2)[1]
            self.assertIn('dados inválidos',message)
            self.assertIn('patrimônio indisponível',message)
            self.assertIn('idade da medição: indisponível',message)
            self.assertNotIn('secret-not-for-output',message)
            self.assertIn('sem medição recente',message)

    def test_deadline_is_visible_without_claiming_process_stopped(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.write(root,end=1001)
            self.assertIn('prazo encerrado',status(root,1001)[1])
            self.assertIn('confira encerramento',status(root,1001)[1])
            (root/'STOP').touch()
            self.assertIn('bloqueada por STOP',status(root,1001)[1])

    def test_age_does_not_generate_status_change_every_second(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.write(root)
            self.assertEqual(status(root,1001)[0],status(root,1002)[0])
