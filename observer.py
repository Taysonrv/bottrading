"""Forward signal journal only: never calls the order or wallet engines."""
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import research


def identity(config, base_identity):
    return hashlib.sha256((base_identity + Path(__file__).read_text(encoding='utf-8') +
                           json.dumps(config, sort_keys=True)).encode()).hexdigest()


def advance(state, histories, quotes, version, observed_at):
    """Record one synchronized snapshot. Never backfill decisions after downtime."""
    if state and state['version'] != version:
        raise ValueError('Código/configuração mudou durante observação; preserve e arquive a sessão anterior antes de iniciar outra')
    stamps = {rows[-1]['time'] for rows in histories.values()}
    if len(stamps) != 1:
        raise ValueError('Candles dos pares não estão sincronizados')
    stamp = stamps.pop()
    if state and stamp < state['last_candle']:
        raise ValueError('Dados anteriores à última observação')
    if state and stamp == state['last_candle']:
        return state, False
    if not state:
        state = {'version': version, 'started': observed_at, 'last_candle': -1,
                 'snapshots': [], 'outcomes': [], 'gaps': 0}
    for quote in quotes.values():
        if any(not math.isfinite(quote[k]) or quote[k] <= 0 for k in ('bid', 'ask')) or quote['bid'] > quote['ask']:
            raise ValueError('Cotação inválida para observação')
    previous = state['snapshots'][-1] if state['snapshots'] else None
    if previous:
        elapsed = observed_at - previous['observed_at']
        contiguous = stamp - previous['candle'] == research.HOUR and 45 * 60 <= elapsed <= 75 * 60
        if contiguous:
            for symbol, row in previous['symbols'].items():
                midpoint = (quotes[symbol]['bid'] + quotes[symbol]['ask']) / 2
                state['outcomes'].append({'symbol': symbol, 'from': previous['observed_at'],
                    'to': observed_at, 'market_return': midpoint / row['midpoint'] - 1,
                    'signals': row['signals']})
        else:
            state['gaps'] += 1
    snapshot = {'observed_at': observed_at, 'candle': stamp, 'symbols': {}}
    # The caller attaches signals computed from closed candles only.
    for symbol, quote in quotes.items():
        snapshot['symbols'][symbol] = {'bid': quote['bid'], 'ask': quote['ask'],
            'midpoint': (quote['bid'] + quote['ask']) / 2, 'signals': quote['signals']}
    state['snapshots'].append(snapshot)
    state['last_candle'] = stamp
    return state, True


def markdown(state):
    if not state:
        return '# Observação futura\n\nAinda não iniciada.\n'
    started = dt.datetime.fromtimestamp(state['started'], dt.timezone.utc).isoformat()
    lines = ['# Observação futura de sinais', '', f'Início: {started}.',
             f"Amostras: {len(state['snapshots'])}; intervalos ignorados por atraso/lacuna: {state['gaps']}.", '',
             'Nenhuma ordem foi criada. Valores abaixo são retornos brutos do mercado entre observações, não lucro de estratégia.', '',
             '| Estratégia | Ativo | Intervalos com sinal de entrada | Média do mercado após entrada |',
             '|---|---|---:|---:|']
    symbols = list(state['snapshots'][-1]['symbols'])
    for strategy in research.STRATEGIES:
        for symbol in symbols:
            observed = [o['market_return'] for o in state['outcomes']
                        if o['symbol'] == symbol and o['signals'][strategy]['target'] > 0]
            average = f'{sum(observed) / len(observed):.3%}' if observed else 'Sem dados'
            lines.append(f'| {strategy} | {symbol} | {len(observed)} | {average} |')
    lines += ['', 'Os sinais são registrados antes de seus resultados. Não há preenchimento retroativo após desligamento.',
              'A observação não concede aprovação, não altera parâmetros e não substitui backtest com custos nem simulação de carteira.']
    return '\n'.join(lines) + '\n'
