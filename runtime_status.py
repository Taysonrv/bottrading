"""Small, credential-free status view of the live paper report."""
import json
import math
from pathlib import Path
import time


def finite_number(value):
    return type(value) in (int, float) and math.isfinite(value)


def safe_symbol(value):
    return value if isinstance(value, str) and value.isascii() and value.isalnum() and len(value)<=24 else ''


def status(root, now=None):
    now = time.time() if now is None else now
    path = Path(root)/'reports/local/live-small-paper.json'
    try:
        state = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return ('missing',), 'Simulação: aguardando relatório legível.'
    if not isinstance(state, dict):
        return ('invalid',), 'Simulação: relatório inválido; confira o log local.'
    updated = state.get('updated')
    valid_time = finite_number(updated)
    fresh = valid_time and 0 <= now-updated < 180
    phase = state.get('phase')
    health = 'bloqueada por STOP' if (Path(root)/'STOP').exists() else 'bloqueada por drawdown' if state.get('halted') else 'erro' if phase == 'error' else 'encerrada' if phase == 'stopped' else 'atualizada' if phase == 'waiting' and fresh else 'sem medição recente'
    end = state.get('end')
    if health in ('atualizada', 'sem medição recente') and finite_number(end) and end <= now:
        health = 'prazo encerrado'
    orders = state.get('orders')
    last = orders[-1] if isinstance(orders, list) and orders and isinstance(orders[-1], dict) else {}
    # No raw exceptions, URLs, addresses, keys or report dumps enter the terminal.
    def numeric(value):
        return f'{value:.6f}' if finite_number(value) else 'indisponível'
    equity = numeric(state.get('equity'))
    realized = numeric(state.get('realized'))
    side = 'compra' if last.get('side') == 'BUY' else 'venda' if last.get('side') == 'SELL' else 'nenhuma'
    symbol = safe_symbol(last.get('symbol'))
    position = state.get('position')
    if position is None:
        position_text = 'nenhuma'
    elif isinstance(position, dict) and safe_symbol(position.get('symbol')) and finite_number(position.get('units')) and position['units'] > 0:
        position_text = safe_symbol(position['symbol'])
    else:
        position_text = 'dados inválidos'
    retained = orders if isinstance(orders, list) else []
    buys = sum(isinstance(o, dict) and o.get('side') == 'BUY' for o in retained)
    sells = sum(isinstance(o, dict) and o.get('side') == 'SELL' for o in retained)
    age = f'{int(now-updated)}s' if valid_time and now >= updated else 'indisponível'
    key = (health, last.get('time'), last.get('side'), symbol, position_text, buys, sells)
    message = f'Simulação {health} | patrimônio {equity} USDT | realizado {realized} USDT | última ordem: {side} {symbol}'
    message += f' | posição: {position_text} | histórico retido: {buys} compras / {sells} vendas | idade da medição: {age}'
    if health == 'prazo encerrado':
        message += ' | Prazo atingido; confira encerramento do processo e resumo. Saldo não reiniciado.'
    if health == 'erro':
        message += ' | Execute python diagnosticar.py e confira reports/local/launcher-paper.log; ordens podem estar bloqueadas.'
    if health == 'sem medição recente':
        message += ' | Confira conexão e processo; patrimônio é a última medição salva.'
    return key, message


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Consulta local da simulação; não inicia processos nem envia ordens.')
    parser.add_argument('--data-dir', type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    print(status(args.data_dir)[1])
