"""Human-readable Telegram messages, with persistent duplicate suppression."""
import datetime as dt
import hashlib
import json


def message(item):
    kind = item['kind']
    prefix = '[SIMULAÇÃO] '
    if kind == 'paper_order':
        return (prefix + f"{'Compra' if item['side'] == 'BUY' else 'Venda'} de {item['symbol']}\n"
                f"Quantidade: {item['quantity']:.8f}\nPreço: {item['price']:.4f} USDT\n"
                f"Taxa: {item['fee']:.4f} USDT\nRegime: {item['regime']}")
    if kind == 'blocked':
        return prefix + f"Operações bloqueadas em {item['symbol']}: {item['reason']}"
    if kind == 'observation':
        return prefix + 'Observação de sinais registrada. Nenhuma ordem enviada.'
    if kind == 'review':
        return prefix + 'Resumo diário\n' + '\n'.join(f'{key}: {value}' for key, value in item['counts'].items())
    if kind == 'error':
        return prefix + f"Ciclo interrompido ({item['error_type']}). Consulte o diário local."
    return prefix + {'started': 'Processo iniciado.', 'stopped': 'Processo desligado.',
                     'validation': 'Validação concluída. Consulte o relatório local.'}.get(kind, kind)


def should_send(item, sent):
    # Always deliver orders and lifecycle events. Suppress unchanged blocks/errors per day.
    if item['kind'] not in ('blocked', 'error'):
        return True, None
    day = dt.datetime.fromisoformat(item['time']).astimezone(dt.timezone(dt.timedelta(hours=-3))).date().isoformat()
    payload = {k: v for k, v in item.items() if k != 'time'}
    key = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    return sent.get(key) != day, (key, day)
