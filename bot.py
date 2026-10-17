"""Binance Spot paper trader with read-only account previews. No real orders."""
import argparse
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import time
import urllib.parse
import urllib.request
import research
import observer
import notifications
import wallet
from contextlib import contextmanager

ROOT = Path(__file__).resolve().parent


@contextmanager
def runtime_lock(name='runtime.lock'):
    """Wallet reports have a separate lock from the trading/observer process."""
    import msvcrt
    if name not in ('runtime.lock', 'wallet-preview.lock'):
        raise ValueError('Nome de trava inválido')
    with (ROOT / name).open('a+b') as lock:
        lock.seek(0, 2)
        if lock.tell() == 0:
            lock.write(b'0')
            lock.flush()
        lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except PermissionError:
            raise LockBusy('Já existe um processo usando esta função. Aguarde ou desligue o processo correspondente; não apague a trava.') from None
        try:
            yield
        finally:
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)


class LockBusy(RuntimeError):
    pass


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def save(path, value):
    path = Path(path)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding='utf-8')
    tmp.replace(path)


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def request(url, payload=None):
    data = None if payload is None else urllib.parse.urlencode(payload).encode()
    with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=20) as response:
        return json.load(response)


def notify(message):
    token, chat = os.getenv('TELEGRAM_BOT_TOKEN'), os.getenv('TELEGRAM_CHAT_ID')
    if token and chat:
        try:
            result = request(f'https://api.telegram.org/bot{token}/sendMessage',
                             {'chat_id': chat, 'text': message})
            if not result.get('ok'):
                raise RuntimeError('Telegram recusou a mensagem')
            return True
        except Exception:
            # Never log URLs containing credentials.
            print('Falha no Telegram; evento preservado no diário local.')
    return False


def event(kind, **fields):
    item = {'time': now(), 'kind': kind, **fields}
    with (ROOT / 'events.jsonl').open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(item, ensure_ascii=False) + '\n')
    print(json.dumps(item, ensure_ascii=False))
    if kind not in ('cycle', 'observation'):
        path = ROOT / 'notifications-state.json'
        sent = read(path) if path.exists() else {}
        allowed, marker = notifications.should_send(item, sent)
        if allowed and notify(notifications.message(item)) and marker:
            key, day = marker
            sent[key] = day
            save(path, sent)


def candles(symbol, count=1000):
    query = urllib.parse.urlencode({'symbol': symbol, 'interval': '1h', 'limit': count})
    rows = request('https://data-api.binance.vision/api/v3/klines?' + query)
    current = time.time() * 1000
    closed = [{'time': int(r[6]), 'close': float(r[4]), 'open_time': int(r[0]),
               'open': float(r[1]), 'high': float(r[2]), 'low': float(r[3])} for r in rows if r[6] < current]
    if len(closed) < 240 or current - closed[-1]['time'] > 90 * 60 * 1000:
        raise ValueError('Histórico insuficiente ou atrasado')
    if any(b['time'] - a['time'] != 3600000 for a, b in zip(closed, closed[1:])):
        raise ValueError('Histórico com lacunas')
    return closed


def signal(prices):
    if len(prices) < 200:
        return 'aquecimento', 0.0
    recent = prices[-25:]
    returns = [b / a - 1 for a, b in zip(recent, recent[1:])]
    change = prices[-1] / prices[-25] - 1
    volatility = statistics.pstdev(returns)
    slow, fast = statistics.mean(prices[-200:]), statistics.mean(prices[-24:])
    if change <= -0.06:
        return 'queda_forte', 0.0
    if volatility >= 0.018:
        return 'nervoso', 0.0
    if abs(fast / slow - 1) < 0.01:
        mean = statistics.mean(prices[-48:])
        return 'lateral', 1.0 if prices[-1] < mean * 0.985 else 0.0
    return 'tranquilo', 1.0 if prices[-1] > fast > slow else 0.0


def fingerprint(config):
    return hashlib.sha256((Path(__file__).read_text(encoding='utf-8') +
                           Path(research.__file__).read_text(encoding='utf-8') +
                           json.dumps(config, sort_keys=True)).encode()).hexdigest()


def validate(config):
    histories = {}
    for symbol in config['symbols']:
        print(f'Baixando {config["history_days"]} dias de {symbol}...', flush=True)
        histories[symbol] = research.download(symbol, config['history_days'], request)
    comparisons = research.evaluate(histories, config, signal)
    active = comparisons[config['strategy']]
    report = {'created': time.time(), 'fingerprint': fingerprint(config),
              'active_strategy': config['strategy'], 'comparisons': comparisons,
              'results': active['symbols'], 'portfolio_passed': active['passed'],
              'history_days': config['history_days'],
              'warning': 'Pesquisa com regras fixas; não comprova rentabilidade futura.'}
    save(ROOT / 'validation.json', report)
    (ROOT / 'research-report.md').write_text(research.markdown(report), encoding='utf-8')
    event('validation', strategy=config['strategy'], portfolio_passed=active['passed'],
          comparisons={s: r['passed'] for s, r in comparisons.items()})


def config_check(config):
    if config.get('mode') != 'paper':
        raise ValueError('Somente modo paper implementado')
    if config.get('strategy') not in research.STRATEGIES:
        raise ValueError('Estratégia inválida')
    if type(config.get('history_days')) is not int or not 180 <= config['history_days'] <= 1095:
        raise ValueError('Histórico precisa ter entre 180 e 1095 dias')
    if not config['symbols'] or any(not s.endswith('USDT') or not s.isalnum() for s in config['symbols']):
        raise ValueError('Use pares Spot cotados em USDT')
    if len(set(config['symbols'])) != len(config['symbols']):
        raise ValueError('Pares duplicados')
    for key in ['max_symbol_fraction', 'max_order_fraction', 'max_total_fraction']:
        if not 0 < config[key] <= 1:
            raise ValueError('Limite inválido: ' + key)
    if any(not math.isfinite(config[k]) or config[k] < 0 for k in ['fee_rate', 'slippage_rate', 'paper_usdt']):
        raise ValueError('Custos ou saldo inválidos')
    if config['paper_usdt'] <= 0 and not any(config['paper_positions'].values()):
        raise ValueError('Carteira inicial vazia')
    if config['fee_rate'] >= .1 or config['slippage_rate'] >= .1:
        raise ValueError('Custos fora do intervalo permitido')
    if any(s not in config['symbols'] or not math.isfinite(q) or q < 0 for s, q in config['paper_positions'].items()):
        raise ValueError('Posições iniciais inválidas')


def guard(state, equity):
    if (ROOT / 'STOP').exists():
        raise ValueError('Botão de desligar acionado')
    state['peak'] = max(state['peak'], equity)
    if equity <= state['peak'] * 0.85:
        state['halted'] = True
    if state['halted']:
        raise ValueError('Proteção de drawdown travada; exige revisão manual')


def quote(symbol):
    row = request('https://data-api.binance.vision/api/v3/ticker/bookTicker?' +
                  urllib.parse.urlencode({'symbol': symbol}))
    bid, ask = float(row['bidPrice']), float(row['askPrice'])
    if not all(math.isfinite(p) and p > 0 for p in (bid, ask)) or bid > ask:
        raise ValueError('Cotação inválida')
    return {'bid': bid, 'ask': ask}


def cycle(config):
    state_path = ROOT / 'state.json'
    state = read(state_path) if state_path.exists() else {
        'cash': config['paper_usdt'], 'positions': config['paper_positions'].copy(),
        'peak': 0, 'halted': False, 'last': {}}
    history = {s: candles(s, 300) for s in config['symbols']}
    if any(s not in config['symbols'] for s in state['positions']):
        raise ValueError('Há posição fora dos pares configurados; revise antes de continuar')
    quotes = {s: quote(s) for s in config['symbols']}
    prices = {s: q['bid'] for s, q in quotes.items()}
    equity = state['cash'] + sum(q * prices[s] for s, q in state['positions'].items())
    try:
        guard(state, equity)
    except ValueError:
        save(state_path, state)
        raise
    report_path = ROOT / 'validation.json'
    report = read(report_path) if report_path.exists() else {}
    valid = (report.get('fingerprint') == fingerprint(config) and
             0 <= time.time() - report.get('created', 0) < 86400)
    for symbol, rows in history.items():
        stamp = str(rows[-1]['time'])
        if state['last'].get(symbol) == stamp:
            continue
        regime, target = research.target([r['close'] for r in rows][-200:], config['strategy'], signal)
        passed = valid and report.get('portfolio_passed', False) and report.get('results', {}).get(symbol, {}).get('passed', False)
        if not passed:
            event('blocked', symbol=symbol, reason='Validação ausente, reprovada ou vencida')
            continue
        quotes[symbol] = quote(symbol)
        prices[symbol] = quotes[symbol]['bid']
        price = prices[symbol]
        units = state['positions'].get(symbol, 0)
        equity = state['cash'] + sum(q * prices[s] for s, q in state['positions'].items())
        delta = equity * config['max_symbol_fraction'] * target - units * price
        delta = max(-equity * config['max_order_fraction'], min(delta, equity * config['max_order_fraction']))
        exposure = sum(q * prices[s] for s, q in state['positions'].items())
        if delta > 0:
            delta = min(delta, max(0, equity * config['max_total_fraction'] - exposure))
        if abs(delta) >= 10:
            try:
                guard(state, equity)  # Checked immediately before EACH simulated order.
            except ValueError:
                save(state_path, state)
                raise
            reference = quotes[symbol]['ask'] if delta > 0 else quotes[symbol]['bid']
            state['cash'], state['positions'][symbol], order = research.fill(
                state['cash'], units, reference, delta, config['fee_rate'], config['slippage_rate'])
            state['last'][symbol] = stamp
            save(state_path, state)
            if order:
                event('paper_order', symbol=symbol, regime=regime, **order)
        state['last'][symbol] = stamp
    save(state_path, state)
    event('cycle', equity=state['cash'] + sum(q * prices[s] for s, q in state['positions'].items()),
          cash=state['cash'], positions=state['positions'], peak=state['peak'])


def observe(config):
    if (ROOT / 'STOP').exists():
        raise ValueError('Observação desligada pelo STOP')
    path = ROOT / 'observation-state.json'
    state = read(path) if path.exists() else None
    histories = {s: candles(s, 300) for s in config['symbols']}
    quotes = {s: quote(s) for s in config['symbols']}
    for symbol, rows in histories.items():
        prices = [r['close'] for r in rows][-200:]
        quotes[symbol]['signals'] = {}
        for strategy in research.STRATEGIES:
            regime, fraction = research.target(prices, strategy, signal)
            quotes[symbol]['signals'][strategy] = {'regime': regime, 'target': fraction}
    version = observer.identity(config, fingerprint(config))
    state, changed = observer.advance(state, histories, quotes, version, time.time())
    if (ROOT / 'STOP').exists():
        raise ValueError('Observação desligada pelo STOP')
    if changed:
        save(path, state)
        (ROOT / 'observation-report.md').write_text(observer.markdown(state), encoding='utf-8')
        event('observation', samples=len(state['snapshots']), gaps=state['gaps'])
    else:
        print('Este candle já foi observado; nenhuma amostra duplicada.')


def status():
    state_path, observed_path = ROOT / 'state.json', ROOT / 'observation-state.json'
    state = read(state_path) if state_path.exists() else {}
    observed = read(observed_path) if observed_path.exists() else {}
    print(json.dumps({'mode': 'paper', 'stop': (ROOT / 'STOP').exists(),
          'drawdown_halted': state.get('halted', False), 'paper_cash': state.get('cash'),
          'observation_samples': len(observed.get('snapshots', [])),
          'last_observed_at': observed.get('snapshots', [{}])[-1].get('observed_at') if observed else None,
          'note': 'Estado salvo; não confirma que há um processo rodando.'}, ensure_ascii=False, indent=2))


def review():
    entries = []
    path = ROOT / 'events.jsonl'
    if path.exists():
        entries = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)
    entries = [e for e in entries if dt.datetime.fromisoformat(e['time']) >= cutoff]
    counts = {kind: sum(e['kind'] == kind for e in entries) for kind in {e['kind'] for e in entries}}
    validation_path = ROOT / 'validation.json'
    validation = read(validation_path) if validation_path.exists() else {}
    comparisons = validation.get('comparisons', {})
    proposals = []
    for strategy, result in comparisons.items():
        failures = [s for s, r in result['symbols'].items() if not r['passed']]
        proposals.append({'strategy': strategy, 'passed': result['passed'], 'failed_symbols': failures,
                          'action': 'Revisão humana necessária; não aplicar automaticamente'})
    save(ROOT / 'night-review.json', {'created': now(), 'counts': counts,
         'validation_created': validation.get('created'),
         'proposals': proposals or ['Executar validação histórica para obter comparações.'],
         'status': 'Somente relatório. Nenhum parâmetro ou código foi alterado.'})
    observation_path = ROOT / 'observation-state.json'
    observed = read(observation_path) if observation_path.exists() else None
    (ROOT / 'observation-report.md').write_text(observer.markdown(observed), encoding='utf-8')
    event('review', counts=counts)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['validate', 'once', 'run', 'stop', 'resume', 'review',
                                             'observe', 'watch', 'status', 'telegram-test', 'wallet-preview'])
    args = parser.parse_args()
    if args.command == 'stop':
        (ROOT / 'STOP').touch()
        print('Desligado. Nenhuma posição foi liquidada.')
        return
    if args.command == 'resume':
        (ROOT / 'STOP').unlink(missing_ok=True)
        print('STOP removido. Trava de drawdown permanece, se acionada.')
        return
    if args.command == 'telegram-test':
        if not notify('[SIMULAÇÃO] Conexão Telegram confirmada. Nenhuma ordem real está habilitada.'):
            raise SystemExit('Telegram não configurado ou envio recusado. Confira token/chat ID localmente.')
        print('Mensagem de teste enviada ao chat configurado.')
        return
    if args.command == 'status':
        status()
        return
    if args.command == 'wallet-preview':
        try:
            with runtime_lock('wallet-preview.lock'):
                client = wallet.ReadOnlyClient(os.getenv('BINANCE_API_KEY'), os.getenv('BINANCE_API_SECRET'))
                report = wallet.preview(client.get('/api/v3/account'), client.get('/api/v3/exchangeInfo'),
                                        client.get('/api/v3/ticker/bookTicker'))
                save(ROOT / 'wallet-preview.json', report)
                (ROOT / 'wallet-preview.md').write_text(wallet.markdown(report), encoding='utf-8')
            print('Consulta concluída. Revise wallet-preview.md localmente. Nenhuma ordem enviada.')
        except wallet.WalletError as error:
            raise SystemExit(str(error)) from None
        return
    config = read(ROOT / 'config.json')
    config_check(config)
    if args.command == 'validate':
        validate(config)
    elif args.command == 'review':
        review()
    elif args.command in ('once', 'observe'):
        with runtime_lock():
            (cycle if args.command == 'once' else observe)(config)
    else:
        with runtime_lock():
            last_review = None
            event('started', mode='paper', command=args.command)
            while not (ROOT / 'STOP').exists():
                try:
                    (observe if args.command == 'watch' else cycle)(config)
                    day = dt.datetime.now(dt.timezone(dt.timedelta(hours=-3))).date().isoformat()
                    if day != last_review:
                        review()
                        last_review = day
                except Exception as error:
                    event('error', error_type=type(error).__name__, message='Ciclo bloqueado; confira conexão, estado e validação.')
                for _ in range(60):
                    if (ROOT / 'STOP').exists():
                        break
                    time.sleep(1)
            event('stopped', mode='paper')


if __name__ == '__main__':
    try:
        main()
    except LockBusy as error:
        raise SystemExit(str(error)) from None
