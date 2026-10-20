"""Small, credential-free status view of the live paper report."""
import json
import math
from pathlib import Path
import time


def status(root, now=None):
    now = time.time() if now is None else now
    path = Path(root)/'reports/local/live-small-paper.json'
    try:
        state = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return ('missing',), 'Simulação: aguardando relatório legível.'
    updated = state.get('updated')
    valid_time = isinstance(updated, (int, float)) and math.isfinite(updated)
    fresh = valid_time and 0 <= now-updated < 180
    phase = state.get('phase')
    health = 'erro' if phase == 'error' else 'encerrada' if phase == 'stopped' else 'atualizada' if fresh else 'sem medição recente'
    orders = state.get('orders') or []
    last = orders[-1] if orders else {}
    # No raw exceptions, URLs, addresses, keys or report dumps enter the terminal.
    def numeric(value):
        return f'{value:.6f}' if isinstance(value, (float, int)) and math.isfinite(value) else 'indisponível'
    equity = numeric(state.get('equity'))
    realized = numeric(state.get('realized'))
    side = {'BUY': 'compra', 'SELL': 'venda'}.get(last.get('side'), 'nenhuma')
    symbol = last.get('symbol', '')
    symbol = symbol if isinstance(symbol, str) and symbol.isascii() and symbol.isalnum() and len(symbol)<=24 else ''
    key = (health, last.get('time'), last.get('side'), symbol)
    message = f'Simulação {health} | patrimônio {equity} USDT | realizado {realized} USDT | última ordem: {side} {symbol}'
    if health == 'erro':
        message += ' | Confira reports/local/launcher-paper.log; ordens podem estar bloqueadas.'
    if health == 'sem medição recente':
        message += ' | Confira conexão e processo; patrimônio é a última medição salva.'
    return key, message
