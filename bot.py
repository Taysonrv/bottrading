"""Binance Spot paper trader. No private Binance endpoints or real orders."""
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

ROOT = Path(__file__).resolve().parent


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
        except Exception:
            # Never log URLs containing credentials.
            print('Falha no Telegram; evento preservado no diário local.')


def event(kind, **fields):
    item = {'time': now(), 'kind': kind, **fields}
    with (ROOT / 'events.jsonl').open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(item, ensure_ascii=False) + '\n')
    print(json.dumps(item, ensure_ascii=False))
    if kind != 'cycle':
        notify(json.dumps(item, ensure_ascii=False))


def candles(symbol, count=1000):
    query = urllib.parse.urlencode({'symbol': symbol, 'interval': '1h', 'limit': count})
    rows = request('https://data-api.binance.vision/api/v3/klines?' + query)
    current = time.time() * 1000
    closed = [{'time': int(r[6]), 'close': float(r[4])} for r in rows if r[6] < current]
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


def replay(prices, start, end, cost, allocation):
    cash, units, peak, worst, trades = 1.0, 0.0, 1.0, 0.0, 0
    halted = False
    # Signal uses only previous closes; execution at the following close.
    for i in range(start, end):
        price = prices[i]
        equity = cash + units * price
        peak = max(peak, equity)
        worst = max(worst, 1 - equity / peak)
        if worst >= 0.15:
            halted = True
        target = signal(prices[:i])[1] * allocation if not halted else None
        if target is not None:
            delta = equity * target - units * price
            if abs(delta) > 0.005 * equity:
                if delta > 0:
                    spend = min(delta, cash / (1 + cost))
                    cash -= spend * (1 + cost)
                    units += spend / price
                else:
                    amount = min(-delta / price, units)
                    cash += amount * price * (1 - cost)
                    units -= amount
                trades += 1
    equity = cash + units * prices[end - 1]
    worst = max(worst, 1 - equity / peak)
    benchmark = prices[end - 1] / prices[start] - 1
    return {'return': equity - 1, 'benchmark': benchmark, 'drawdown': worst,
            'trades': trades, 'passed': equity - 1 > max(0, benchmark) and worst < 0.15 and trades >= 3}


def fingerprint(config):
    return hashlib.sha256((Path(__file__).read_text(encoding='utf-8') +
                           json.dumps(config, sort_keys=True)).encode()).hexdigest()


def validate(config):
    results = {}
    cost = config['fee_rate'] + config['slippage_rate']
    for symbol in config['symbols']:
        rows = candles(symbol)
        prices = [r['close'] for r in rows]
        width = (len(prices) - 200) // 3
        folds = [replay(prices, 200 + n * width, 200 + (n + 1) * width,
                        cost, config['max_symbol_fraction']) for n in range(3)]
        results[symbol] = {'folds': folds, 'passed': all(f['passed'] for f in folds),
                           'first_candle': rows[0]['time'], 'last_candle': rows[-1]['time']}
    report = {'created': time.time(), 'fingerprint': fingerprint(config), 'results': results,
              'warning': 'Triagem curta em candles horários; não comprova rentabilidade futura.'}
    save(ROOT / 'validation.json', report)
    event('validation', results=results)


def config_check(config):
    if config.get('mode') != 'paper':
        raise ValueError('Somente modo paper implementado')
    if not config['symbols'] or any(not s.endswith('USDT') or not s.isalnum() for s in config['symbols']):
        raise ValueError('Use pares Spot cotados em USDT')
    if len(set(config['symbols'])) != len(config['symbols']):
        raise ValueError('Pares duplicados')
    for key in ['max_symbol_fraction', 'max_order_fraction', 'max_total_fraction']:
        if not 0 < config[key] <= 1:
            raise ValueError('Limite inválido: ' + key)
    if any(not math.isfinite(config[k]) or config[k] < 0 for k in ['fee_rate', 'slippage_rate', 'paper_usdt']):
        raise ValueError('Custos ou saldo inválidos')
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


def cycle(config):
    state_path = ROOT / 'state.json'
    state = read(state_path) if state_path.exists() else {
        'cash': config['paper_usdt'], 'positions': config['paper_positions'].copy(),
        'peak': 0, 'halted': False, 'last': {}}
    history = {s: candles(s, 300) for s in config['symbols']}
    prices = {s: rows[-1]['close'] for s, rows in history.items()}
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
        regime, target = signal([r['close'] for r in rows])
        passed = valid and report.get('results', {}).get(symbol, {}).get('passed', False)
        if not passed:
            event('blocked', symbol=symbol, reason='Validação ausente, reprovada ou vencida')
            continue
        price = prices[symbol]
        units = state['positions'].get(symbol, 0)
        equity = state['cash'] + sum(q * prices[s] for s, q in state['positions'].items())
        delta = equity * config['max_symbol_fraction'] * target - units * price
        delta = max(-equity * config['max_order_fraction'], min(delta, equity * config['max_order_fraction']))
        exposure = sum(q * prices[s] for s, q in state['positions'].items())
        if delta > 0:
            delta = min(delta, max(0, equity * config['max_total_fraction'] - exposure))
        cost = config['fee_rate'] + config['slippage_rate']
        if abs(delta) >= 10:
            guard(state, equity)  # Checked immediately before EACH simulated order.
            if delta > 0:
                value = min(delta, state['cash'] / (1 + cost))
                change = value / price
                state['cash'] -= value * (1 + cost)
            else:
                change = -min(units, -delta / price)
                value = -change * price
                state['cash'] += value * (1 - cost)
            state['positions'][symbol] = units + change
            state['last'][symbol] = stamp
            save(state_path, state)
            event('paper_order', symbol=symbol, side='BUY' if change > 0 else 'SELL',
                  quantity=abs(change), price=price, regime=regime, costs=value * cost)
        state['last'][symbol] = stamp
    save(state_path, state)
    event('cycle', equity=state['cash'] + sum(q * prices[s] for s, q in state['positions'].items()),
          cash=state['cash'], positions=state['positions'], peak=state['peak'])


def review():
    entries = []
    path = ROOT / 'events.jsonl'
    if path.exists():
        entries = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)
    entries = [e for e in entries if dt.datetime.fromisoformat(e['time']) >= cutoff]
    counts = {kind: sum(e['kind'] == kind for e in entries) for kind in {e['kind'] for e in entries}}
    save(ROOT / 'night-review.json', {'created': now(), 'counts': counts,
         'proposals': ['Revisar bloqueios e comparar estratégias em histórico mais longo.'],
         'status': 'Somente relatório. Nenhum parâmetro ou código foi alterado.'})
    event('review', counts=counts)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['validate', 'once', 'run', 'stop', 'resume', 'review'])
    args = parser.parse_args()
    if args.command == 'stop':
        (ROOT / 'STOP').touch()
        print('Desligado. Nenhuma posição foi liquidada.')
        return
    if args.command == 'resume':
        (ROOT / 'STOP').unlink(missing_ok=True)
        print('STOP removido. Trava de drawdown permanece, se acionada.')
        return
    config = read(ROOT / 'config.json')
    config_check(config)
    if args.command == 'validate':
        validate(config)
    elif args.command == 'review':
        review()
    elif args.command == 'once':
        cycle(config)
    else:
        # Exclusive OS lock is released automatically on process exit.
        import msvcrt
        with (ROOT / 'runtime.lock').open('a+b') as lock:
            lock.seek(0)
            lock.write(b'0')
            lock.flush()
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            last_review = None
            event('started', mode='paper')
            while not (ROOT / 'STOP').exists():
                try:
                    cycle(config)
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
    main()
