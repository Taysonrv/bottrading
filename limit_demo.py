"""Deterministic synthetic acceptance scenarios, NOT a historical strategy backtest."""
import json
from pathlib import Path
from limit_simulator import LimitBook, fixture_filters


def scenarios():
    def fresh(**kwargs):
        return LimitBook({'BTCUSDT': 100}, fixture_filters(), **kwargs)
    outputs = {}
    b = fresh()
    buy = b.place('BTCUSDT', 'BUY', 95, '.25')
    for seq in (1, 2, 3):
        b.trade(seq, 'BTCUSDT', 94, 1, 'SELL')
    assert b.orders[buy]['status'] == 'FILLED'
    sale = b.place('BTCUSDT', 'SELL', 105, '.25')
    for seq in (4, 5, 6):
        b.trade(seq, 'BTCUSDT', 106, 1, 'BUY')
    assert b.orders[sale]['status'] == 'FILLED'
    replacement = b.place('BTCUSDT', 'BUY', 95, '.25')
    outputs['synthetic_roundtrip_and_replacement'] = {
        'summary': b.summary(), 'fills': b.fills, 'replacement_order': replacement}

    b = fresh()
    oid = b.place('BTCUSDT', 'BUY', 95, '.25')
    b.trade(1, 'BTCUSDT', 94, 1, 'SELL')
    b.cancel(oid, 'fim do episódio de teste')
    outputs['synthetic_partial_then_cancel'] = {'summary': b.summary(), 'fills': b.fills}

    stopped = False
    b = fresh(stop_requested=lambda: stopped)
    b.place('BTCUSDT', 'BUY', 95, '.25')
    stopped = True
    b.trade(1, 'BTCUSDT', 94, 100, 'SELL')
    outputs['synthetic_stop_before_fill'] = {'summary': b.summary(), 'fills': b.fills}

    b = fresh(cash=800, positions={'BTCUSDT': 2})
    b.place('BTCUSDT', 'SELL', 110, '.25')
    b.trade(1, 'BTCUSDT', 20, 100, 'SELL')
    b.trade(2, 'BTCUSDT', 10, 100, 'SELL')
    outputs['synthetic_crash_with_existing_inventory'] = {'summary': b.summary(), 'fills': b.fills}
    return outputs


def main():
    report = dict(capital_usdt=1000, synthetic=True, historical_backtest=False,
                  adopted=False, prices_are_fictional=True, scenarios=scenarios())
    root = Path(__file__).resolve().parent
    output = root/'reports/2026-10-18-limit-acceptance.json'
    output.write_text(json.dumps(report, indent=2, default=str), encoding='utf-8')
    lines = ['# Aceitação do simulador de ordens limitadas', '',
             '**Dados e preços inteiramente artificiais. Não é backtest, previsão de lucro ou aprovação de estratégia.**',
             'Cada cenário começa com patrimônio fictício de 1.000 USDT; o cenário de queda começa com 800 em caixa e 200 em ativo.', '',
             '| Cenário artificial | Patrimônio marcado | Taxas pagas | Saldo reservado | Execuções parciais/totais | Ordens abertas |',
             '|---|---:|---:|---:|---:|---:|']
    for name, item in report['scenarios'].items():
        s = item['summary']
        lines.append(f"| {name} | {s['equity']:.5f} | {s['fees']:.5f} | {s['reserved_cash']:.5f} | {s['fills']} | {s['active_orders']} |")
    lines += ['', 'Patrimônio marcado inclui posições ao último preço artificial, sem custo estimado de liquidação. Taxas cobradas em USDT neste modelo.',
              'Cenário positivo foi construído para testar compra/venda; não demonstra lucratividade. Reposição permanece pendente e não usa o evento anterior.',
              'Na queda artificial, drawdown alcança 18%: a trava cancela ordens, mas não liquida ativos nem limita a perda a 15%.',
              'Participação máxima de 10% do volume agressor informado; não estima posição real na fila. Toque de preço não preenche.',
              'Filtros de preço/lote/mínimo são fictícios. Fonte técnica de referência: https://developers.binance.com/en/docs/products/spot/filters']
    output.with_suffix('.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
