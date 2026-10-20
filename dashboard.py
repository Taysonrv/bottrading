"""Authenticated local dashboard. Reads reports and only exposes the STOP action."""
import argparse
from collections import deque
import hashlib
import hmac
from http.cookies import SimpleCookie, CookieError
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import json
import os
from pathlib import Path
import secrets
import threading
import time
import diagnostics
from urllib.parse import urlsplit,parse_qs
import market_view
import metamask_view

ASSETS = Path(__file__).resolve().parent / 'dashboard_assets'


def read(root, name, fallback=None):
    try:
        return json.loads((root / name).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {} if fallback is None else fallback


def research_report(root, filename):
    local = 'reports/local/'+filename
    # An unreadable local report is unavailable, not silently replaced by an old snapshot.
    return read(root, local if (root/local).exists() else 'reports/'+filename)


def lab_history(root, lab):
    import math
    def finite(value):
        return type(value) in (float,int) and math.isfinite(value)
    curve = [{'time': p['time'], 'equity': p['equity']} for p in lab.get('curve', [])
             if isinstance(p,dict) and finite(p.get('time')) and finite(p.get('equity'))]
    orders = deque(maxlen=200)
    try:
        with (root/'reports/local/live-paper-events.jsonl').open(encoding='utf-8') as stream:
            for line in stream:
                try:
                    row = json.loads(line)
                    if not finite(row.get('time')) or not isinstance(row.get('orders'),list):
                        continue
                    for order in row['orders']:
                        if not isinstance(order,dict) or order.get('side') not in ('BUY','SELL'):
                            continue
                        orders.append({'time': row['time'], 'symbol':order.get('symbol'), 'side':order['side'],
                            **{k: order.get(k) if finite(order.get(k)) else None for k in
                               ('quantity','price','fee','slippage_cost','realized_pnl')}})
                except (ValueError,TypeError,AttributeError):
                    continue
    except OSError:
        pass
    return curve[-1500:],list(reversed(orders))


def snapshot(root):
    state = read(root, 'state.json')
    config = read(root, 'config.json')
    validation = read(root, 'validation.json')
    observed = read(root, 'observation-state.json')
    heartbeat = read(root, 'heartbeat.json')
    lab = read(root, 'reports/local/live-paper.json')
    exit_trial = read(root, 'reports/local/exit-comparison.json')
    micro_trial = read(root, 'reports/local/micro-results.json')
    small_cap = read(root, 'reports/local/small-cap-scan.json')
    small_comparison = read(root, 'reports/local/small-cap-comparison.json')
    spot_suite = read(root, 'reports/local/spot-suite.json')
    lab_curve,lab_orders = lab_history(root,lab)
    daily = research_report(root, '2026-10-18-daily-results.json')
    grid = research_report(root, '2026-10-18-grid-results.json')
    acceptance = research_report(root, '2026-10-18-limit-acceptance.json')
    replay_report = research_report(root, '2026-10-18-grid-replay.json')
    grid_rows = []
    for name, result in grid.get('comparisons', {}).items():
        row = result.get('scenarios', {}).get('continuous', {})
        grid_rows.append({'name': name, 'return': row.get('return'), 'drawdown': row.get('drawdown'),
                          'costs': row.get('costs_usdt'), 'qualified': result.get('qualified_historical', False)})
    def metric(value):
        import math
        try:
            result = float(value)
            return result if math.isfinite(result) else None
        except (ValueError, TypeError, OverflowError):
            return None
    acceptance_rows = []
    for name, item in acceptance.get('scenarios', {}).items():
        row = item.get('summary', {})
        acceptance_rows.append({'name': name, **{k: metric(row.get(k)) for k in
            ('equity', 'fees', 'reserved_cash', 'active_orders', 'fills', 'drawdown')}})
    daily_rows = []
    for name, result in daily.get('comparisons', {}).items():
        continuous = result.get('continuous', {})
        final = result.get('final_reused', {})
        daily_rows.append({'name': name, 'return': continuous.get('return'),
                           'drawdown': continuous.get('drawdown'),
                           'benchmark': continuous.get('benchmark'),
                           'final_return': final.get('return'),
                           'qualified': result.get('qualified_historical', False)})
    events, curve = deque(maxlen=50), deque(maxlen=200)
    malformed = 0
    try:
        with (root / 'events.jsonl').open(encoding='utf-8') as stream:
            for line in stream:
                try:
                    row = json.loads(line)
                    events.append({k: row[k] for k in ('time', 'kind', 'symbol', 'side', 'quantity', 'price', 'regime', 'reason', 'error_type', 'realized_pnl') if k in row})
                    if row.get('kind') == 'cycle' and isinstance(row.get('equity'), (int, float)):
                        curve.append({'time': row['time'], 'equity': row['equity']})
                except (ValueError, KeyError, TypeError):
                    malformed += 1
    except OSError:
        pass
    age = time.time() - heartbeat.get('time', 0)
    comparisons = []
    config_ok, observation_current = False, False
    try:
        import bot
        bot.config_check(config)
        config_ok = True
        current = validation.get('fingerprint') == bot.fingerprint(config) and 0 <= time.time() - validation.get('created', 0) < 86400
        observation_current = observed.get('version') == bot.observer.identity(config, bot.fingerprint(config))
    except (OSError, ValueError, TypeError, KeyError):
        current = False
    for name, result in validation.get('comparisons', {}).items():
        holdout = result.get('portfolio_holdout', {})
        continuous = result.get('continuous_portfolio', {})
        experimental = result.get('defensive_research', {})
        defense = []
        for key in ('freeze', 'reduce', 'reduce_stress', 'existing_freeze', 'existing_reduce'):
            row = experimental.get(key)
            if row:
                defense.append({'scenario': key, 'return': row.get('return'), 'drawdown': row.get('drawdown'),
                                'remaining_exposure': row.get('remaining_exposure_usdt'), 'sales': row.get('defensive_orders')})
        comparisons.append({'name': name, 'passed': result.get('passed', False), 'defensive': defense,
                            'return': holdout.get('return'), 'benchmark': holdout.get('benchmark'),
                            'drawdown': continuous.get('drawdown', holdout.get('drawdown'))})
    recent = 0 <= age <= 180 and heartbeat.get('phase') != 'stopped'
    health = diagnostics.assess(config_ok=config_ok, stop=(root / 'STOP').exists(), halted=state.get('halted', False),
        validation_exists=bool(validation), validation_current=current, validation_passed=validation.get('portfolio_passed', False),
        observation_exists=bool(observed), observation_current=observation_current,
        activity_recent=recent, performance_exists=bool(state.get('performance')))
    return {'market_stream':read(root,'reports/local/market-stream.json'),'live_small':read(root,'reports/local/live-small-paper.json'),'metamask':metamask_view.load(root),'as_of': time.time(), 'mode': 'paper', 'diagnostics': health, 'stop': (root / 'STOP').exists(),
            'halted': state.get('halted', False),
            'activity': {'recent': 0 <= age <= 180 and heartbeat.get('phase') != 'stopped',
                         'time': heartbeat.get('time'), 'phase': heartbeat.get('phase'), 'command': heartbeat.get('command')},
            'performance': state.get('performance'), 'paper_cash': state.get('cash'),
            'curve': list(curve), 'events': list(reversed(events)), 'malformed_events': malformed,
            'strategy': config.get('strategy'),
            'spot_suite': {'created':spot_suite.get('created'),'comparisons':[
                {'strategy':r.get('strategy'),**{k:metric(r.get(k)) for k in ('stress','pnl','buys','sells','drawdown','blocked')}}
                for r in spot_suite.get('comparisons',[])]},
            'small_comparison': {'created':small_comparison.get('created'),'start':small_comparison.get('start'),'end':small_comparison.get('end'),'comparisons':[
                {k:metric(r.get(k)) for k in ('fraction','stress','pnl','buys','sells','blocked','drawdown')}
                for r in small_comparison.get('comparisons',[])]},
            'small_cap': {'created':small_cap.get('created'),'results':[
                {'symbol':r.get('symbol'),'minimum':metric(r.get('minimum')),'spread':metric(r.get('spread')),
                 'signal':r.get('signal') is True,'reasons':r.get('reasons',[])} for r in small_cap.get('results',[])]},
            'micro_trial': {'created':micro_trial.get('created'),'comparisons':[
                {k:metric(r.get(k)) for k in ('target','stress','pnl','buy_count','sell_count','drawdown')}
                for r in micro_trial.get('comparisons',[])]},
            'exit_trial': {'created':exit_trial.get('created'),'start':exit_trial.get('start'),
                'end':exit_trial.get('end_exclusive'),'comparisons':[
                    {'policy':r.get('policy'),'pnl':metric(r.get('return_usdt')),
                     'realized':metric(r.get('realized_pnl')),'sales':len(r.get('orders',[])),
                     'drawdown':metric(r.get('drawdown'))} for r in exit_trial.get('comparisons',[])]},
            'paper_lab': {'started': lab.get('started'), 'end': lab.get('end'), 'updated': lab.get('updated'),
                           'phase': lab.get('phase'), 'error': lab.get('error'),
                           'signals': lab.get('signals', {}), 'performance': lab.get('performance'),
                           'curve':lab_curve, 'orders':lab_orders,
                           'experimental': True},
            'test_budget': {'configured_cash': config.get('paper_usdt'), 'measured': bool(state.get('performance'))},
            'grid_research': {'created': grid.get('created'), 'comparisons': grid_rows},
            'limit_acceptance': {'synthetic': True, 'capital': metric(acceptance.get('capital_usdt')),
                                 'scenarios': acceptance_rows},
            'grid_replay': {'created': replay_report.get('created'), 'events': metric(replay_report.get('events')),
                            'first_time': metric(replay_report.get('first_time')), 'last_time': metric(replay_report.get('last_time')),
                            'fills': metric(replay_report.get('summary', {}).get('fills')),
                            'equity': metric(replay_report.get('summary', {}).get('equity')),
                            'active_at_cutoff': metric(replay_report.get('active_at_cutoff'))},
            'daily_research': {'created': daily.get('created'), 'adopted': False,
                               'independent_out_of_sample': False, 'comparisons': daily_rows},
            'limits': {k: config.get(k) for k in ('max_symbol_fraction', 'max_order_fraction', 'max_total_fraction')},
            'validation': {'created': validation.get('created'), 'passed': current and validation.get('portfolio_passed', False), 'current': current,
                           'comparisons': comparisons},
            'observation': {'samples': len(observed.get('snapshots', [])), 'gaps': observed.get('gaps', 0),
                            'latest': observed.get('snapshots', [{}])[-1] if observed.get('snapshots') else None}}


class DashboardServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, root, password, allowed_hosts):
        super().__init__(address, Handler)
        self.root, self.allowed_hosts = Path(root), allowed_hosts
        self.salt = secrets.token_bytes(16)
        self.password_hash = self.digest(password)
        self.sessions, self.attempts = {}, {}
        self.mutex = threading.Lock()
        self.market_mutex = threading.Lock()
        self.market_cache = {}

    def digest(self, password):
        return hashlib.pbkdf2_hmac('sha256', password.encode(), self.salt, 120000)


class Handler(BaseHTTPRequestHandler):
    server_version = 'SpotLab'

    def log_message(self, *args):
        pass  # Do not log paths, cookies, access codes or account data.

    def send(self, status, data, content_type='application/json; charset=utf-8', cookie=None):
        body = json.dumps(data, ensure_ascii=False, allow_nan=False).encode() if isinstance(data, (dict, list)) else data
        self.send_response(status)
        for name, value in {'Content-Type': content_type, 'Cache-Control': 'no-store',
                            'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer',
                            'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"}.items():
            self.send_header(name, value)
        if cookie:
            self.send_header('Set-Cookie', cookie)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def boundary(self):
        host = self.headers.get('Host', '')
        if host not in self.server.allowed_hosts:
            self.send(403, {'error': 'Host não permitido'})
            return False
        origin = self.headers.get('Origin')
        if origin and origin != 'http://' + host:
            self.send(403, {'error': 'Origem não permitida'})
            return False
        return True

    def session(self):
        try:
            cookie = SimpleCookie(self.headers.get('Cookie', ''))
            token = cookie['spotlab'].value
        except (KeyError, ValueError, CookieError):
            return None
        with self.server.mutex:
            session = self.server.sessions.get(token)
            return session if session and session['expires'] > time.time() else None

    def do_GET(self):
        if not self.boundary():
            return
        path = urlsplit(self.path).path
        if path in ('/', '/app.js', '/market.js', '/metamask.js', '/style.css'):
            filename, mime = {'/': ('index.html', 'text/html; charset=utf-8'),
                              '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
                              '/market.js': ('market.js', 'text/javascript; charset=utf-8'),
                              '/metamask.js': ('metamask.js', 'text/javascript; charset=utf-8'),
                              '/style.css': ('style.css', 'text/css; charset=utf-8')}[path]
            return self.send(200, (ASSETS / filename).read_bytes(), mime)
        session = self.session()
        if not session:
            return self.send(401, {'error': 'Entre com o código exibido no computador'})
        if path == '/api/status':
            try:
                return self.send(200, {'csrf': session['csrf'], 'data': snapshot(self.server.root)})
            except (ValueError, TypeError):
                return self.send(503, {'error': 'Relatórios temporariamente indisponíveis'})
        if path == '/api/lab-market':
            symbol=parse_qs(urlsplit(self.path).query).get('symbol',[''])[0]
            if symbol not in ('BTCUSDT','ETHUSDT'):
                return self.send(400,{'error':'Ativo não permitido'})
            try:
                with self.server.market_mutex:
                    cached=self.server.market_cache.get(symbol)
                    if not cached or time.time()-cached['as_of']>=30:
                        cached=market_view.load(symbol)
                        self.server.market_cache[symbol]=cached
                return self.send(200,cached)
            except (OSError,ValueError,KeyError,TypeError):
                return self.send(503,{'error':'Candles indisponíveis; nenhuma decisão de trading foi alterada.'})
        return self.send(404, {'error': 'Não encontrado'})

    def do_POST(self):
        if not self.boundary():
            return
        if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
            return self.send(415, {'error': 'Requisição inválida'})
        try:
            length = int(self.headers.get('Content-Length', 0))
            if not 0 < length <= 1024:
                raise ValueError()
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError()
        except (ValueError, UnicodeError):
            return self.send(400, {'error': 'Requisição inválida'})
        path = urlsplit(self.path).path
        if path == '/api/login':
            ip, now = self.client_address[0], time.time()
            with self.server.mutex:
                self.server.attempts = {k: v for k, v in self.server.attempts.items() if now - v[-1] < 300}
                attempts = [t for t in self.server.attempts.get(ip, []) if now - t < 300]
                if len(attempts) >= 5 or len(self.server.attempts) > 1024:
                    return self.send(429, {'error': 'Muitas tentativas. Aguarde cinco minutos.'})
                password = data.get('password', '')
                if not isinstance(password, str) or not hmac.compare_digest(self.server.password_hash, self.server.digest(password)):
                    self.server.attempts[ip] = attempts + [now]
                    return self.send(401, {'error': 'Código incorreto'})
                self.server.sessions = {k: v for k, v in self.server.sessions.items() if v['expires'] > now}
                if len(self.server.sessions) >= 32:
                    return self.send(429, {'error': 'Limite de sessões atingido'})
                token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(24)
                self.server.sessions[token] = {'csrf': csrf, 'expires': now + 8 * 3600}
            return self.send(200, {'csrf': csrf}, cookie=f'spotlab={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800')
        session = self.session()
        if not session or not hmac.compare_digest(self.headers.get('X-CSRF-Token', ''), session['csrf']):
            return self.send(403, {'error': 'Sessão inválida'})
        if path == '/api/stop':
            try:
                (self.server.root / 'STOP').touch()
            except OSError:
                return self.send(503, {'error': 'Não foi possível gravar a trava. Use o terminal.'})
            return self.send(200, {'stopped': True, 'message': 'STOP acionado. O processo reconhecerá a trava; posições não são liquidadas.'})
        if path == '/api/logout':
            token = SimpleCookie(self.headers['Cookie'])['spotlab'].value
            with self.server.mutex:
                self.server.sessions.pop(token, None)
            return self.send(200, {'ok': True}, cookie='spotlab=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0')
        return self.send(404, {'error': 'Ação não disponível'})


def main():
    parser = argparse.ArgumentParser(description='Painel local do bot, sem ordens reais')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--data-dir', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--lan-ip', help='IPv4 privado do computador; habilita acesso HTTP na rede local')
    parser.add_argument('--allow-lan-http', action='store_true')
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error('Porta deve estar entre 1024 e 65535')
    hosts = {f'localhost:{args.port}', f'127.0.0.1:{args.port}'}
    host = '127.0.0.1'
    if args.lan_ip:
        ip = ipaddress.IPv4Address(args.lan_ip)
        if not ip.is_private or ip.is_loopback or not args.allow_lan_http:
            parser.error('Para rede local use IPv4 privado e --allow-lan-http. Não use em rede pública.')
        host = str(ip)
        hosts.add(f'{ip}:{args.port}')
    if not args.data_dir.is_dir():
        parser.error('Pasta de dados inexistente')
    password = os.getenv('SPOTLAB_ACCESS_CODE') or secrets.token_urlsafe(12)
    if len(password) < 12:
        parser.error('SPOTLAB_ACCESS_CODE precisa ter pelo menos 12 caracteres')
    server = DashboardServer((host, args.port), args.data_dir.resolve(), password, hosts)
    print(f'Spot Lab: http://{host}:{args.port}', flush=True)
    print(f'Código de acesso: {password}', flush=True)
    if args.lan_ip:
        print('HTTP na rede local não é criptografado. Use apenas Wi-Fi privado confiável. Não encaminhe portas no roteador.', flush=True)
    print('Painel não inicia o bot. Ctrl+C encerra somente o painel.', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
