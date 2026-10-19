import http.client
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
import dashboard


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.root = Path(self.folder.name)
        self.server = dashboard.DashboardServer(('127.0.0.1', 0), self.root, 'test-code-123456', set())
        self.host = '127.0.0.1:' + str(self.server.server_port)
        self.server.allowed_hosts.add(self.host)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.folder.cleanup()

    def request(self, method, path, data=None, headers=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        headers = {'Content-Type': 'application/json', **(headers or {})}
        body = json.dumps(data) if data is not None else None
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        raw = response.read()
        result = (response.status, dict(response.getheaders()), raw)
        connection.close()
        return result

    def login(self):
        code, headers, body = self.request('POST', '/api/login', {'password': 'test-code-123456'})
        self.assertEqual(code, 200)
        return {'Cookie': headers['Set-Cookie'].split(';')[0], 'X-CSRF-Token': json.loads(body)['csrf']}

    def test_status_requires_authentication(self):
        self.assertEqual(self.request('GET', '/api/status')[0], 401)

    def test_stop_requires_session_and_csrf(self):
        self.assertEqual(self.request('POST', '/api/stop', {})[0], 403)
        headers = self.login()
        self.assertEqual(self.request('POST', '/api/stop', {}, {'Cookie': headers['Cookie']})[0], 403)
        self.assertFalse((self.root / 'STOP').exists())

    def test_authenticated_stop_does_not_modify_wallet(self):
        (self.root / 'state.json').write_text('{"cash": 1000}', encoding='utf-8')
        self.assertEqual(self.request('POST', '/api/stop', {}, self.login())[0], 200)
        self.assertTrue((self.root / 'STOP').exists())
        self.assertEqual(json.loads((self.root / 'state.json').read_text())['cash'], 1000)

    def test_files_and_secrets_are_not_served(self):
        (self.root / 'wallet-preview.json').write_text('{"secret":"private"}')
        headers = self.login()
        self.assertEqual(self.request('GET', '/wallet-preview.json', headers=headers)[0], 404)
        self.assertEqual(self.request('GET', '/../config.json', headers=headers)[0], 404)
        _, _, body = self.request('GET', '/api/status', headers=headers)
        self.assertNotIn(b'private', body)

    def test_cross_origin_and_host_are_rejected(self):
        self.assertEqual(self.request('POST', '/api/stop', {}, {**self.login(), 'Origin': 'http://evil.test'})[0], 403)
        self.assertEqual(self.request('GET', '/', headers={'Host': 'evil.test'})[0], 403)

    def test_logout_revokes_session(self):
        headers = self.login()
        self.assertEqual(self.request('POST', '/api/logout', {}, headers)[0], 200)
        self.assertEqual(self.request('GET', '/api/status', headers=headers)[0], 401)

    def test_repeated_failed_login_is_limited(self):
        for _ in range(5):
            self.assertEqual(self.request('POST', '/api/login', {'password': 'wrong'})[0], 401)
        self.assertEqual(self.request('POST', '/api/login', {'password': 'wrong'})[0], 429)

    def test_stale_heartbeat_does_not_show_recent_activity(self):
        (self.root / 'heartbeat.json').write_text(json.dumps({'time': time.time() - 400, 'phase': 'waiting'}))
        self.assertFalse(dashboard.snapshot(self.root)['activity']['recent'])

    def test_daily_report_is_visible_but_cannot_approve_orders(self):
        (self.root / 'reports').mkdir()
        report = {'created': '2026-10-18T21:00:00Z', 'adopted': True,
                  'comparisons': {'sma200_vol': {'continuous': {'return': .16, 'drawdown': .074},
                    'final_reused': {'return': -.005}, 'qualified_historical': True}}}
        (self.root / 'reports/2026-10-18-daily-results.json').write_text(json.dumps(report))
        data = dashboard.snapshot(self.root)
        self.assertEqual(data['daily_research']['comparisons'][0]['return'], .16)
        self.assertFalse(data['daily_research']['adopted'])
        self.assertFalse(data['diagnostics']['paper_ready'])

    def test_missing_daily_report_is_empty(self):
        self.assertEqual(dashboard.snapshot(self.root)['daily_research']['comparisons'], [])

    def test_budget_does_not_fabricate_performance(self):
        (self.root / 'config.json').write_text('{"paper_usdt":1000}')
        data = dashboard.snapshot(self.root)
        self.assertEqual(data['test_budget']['configured_cash'], 1000)
        self.assertFalse(data['test_budget']['measured'])
        self.assertIsNone(data['performance'])

    def test_public_replay_cannot_replace_wallet_or_validation(self):
        (self.root / 'reports').mkdir()
        (self.root / 'reports/2026-10-18-grid-replay.json').write_text(json.dumps({
            'created': '2026-10-18T23:00:00Z', 'events':1000, 'summary': {'equity':'1000', 'fills':0}}))
        data = dashboard.snapshot(self.root)
        self.assertEqual(data['grid_replay']['equity'], 1000)
        self.assertIsNone(data['performance'])
        self.assertFalse(data['diagnostics']['paper_ready'])

    def test_local_report_takes_precedence_without_changing_snapshot(self):
        (self.root/'reports/local').mkdir(parents=True)
        name = '2026-10-18-grid-replay.json'
        (self.root/'reports'/name).write_text('{"events":1000}')
        (self.root/'reports/local'/name).write_text('{"events":63458}')
        self.assertEqual(dashboard.snapshot(self.root)['grid_replay']['events'], 63458)
        self.assertEqual(json.loads((self.root/'reports'/name).read_text())['events'],1000)

    def test_invalid_local_report_does_not_show_old_snapshot_as_current(self):
        (self.root/'reports/local').mkdir(parents=True)
        name = '2026-10-18-grid-replay.json'
        (self.root/'reports'/name).write_text('{"events":1000}')
        (self.root/'reports/local'/name).write_text('{broken')
        self.assertIsNone(dashboard.snapshot(self.root)['grid_replay']['events'])

    def test_limit_fixture_decimals_and_grid_are_visible_but_never_approve(self):
        (self.root / 'reports').mkdir()
        (self.root / 'reports/2026-10-18-limit-acceptance.json').write_text(json.dumps({
            'capital_usdt': 1000, 'scenarios': {'example': {'summary': {'equity': '1002.45',
                'fees': '.05', 'reserved_cash': 'NaN', 'fills': 6}}}}))
        (self.root / 'reports/2026-10-18-grid-results.json').write_text(json.dumps({
            'comparisons': {'grid_range_v1': {'scenarios': {'continuous': {'return': -.11}}}}}))
        data = dashboard.snapshot(self.root)
        self.assertEqual(data['limit_acceptance']['scenarios'][0]['equity'], 1002.45)
        self.assertIsNone(data['limit_acceptance']['scenarios'][0]['reserved_cash'])
        self.assertEqual(data['grid_research']['comparisons'][0]['return'], -.11)
        self.assertFalse(data['diagnostics']['paper_ready'])

    def test_invalid_partial_event_is_skipped(self):
        (self.root / 'events.jsonl').write_text('{broken\n{"kind":"cycle","time":"2026-10-17T00:00:00Z","equity":1000}\n')
        data = dashboard.snapshot(self.root)
        self.assertEqual(len(data['curve']), 1)
        self.assertEqual(data['malformed_events'], 1)

    def test_defensive_research_is_reported_without_adopting_policy(self):
        report = {'comparisons': {'trend_v1': {'defensive_research': {'adopted': False,
            'reduce': {'return': -.1, 'drawdown': .16, 'defensive_orders': 3, 'remaining_exposure_usdt': 1}}}}}
        (self.root / 'validation.json').write_text(json.dumps(report))
        data = dashboard.snapshot(self.root)
        result = data['validation']['comparisons'][0]['defensive'][0]
        self.assertEqual(result['sales'], 3)
        self.assertFalse(data['diagnostics']['paper_ready'])
        self.assertFalse((self.root / 'state.json').exists())


if __name__ == '__main__':
    unittest.main()
