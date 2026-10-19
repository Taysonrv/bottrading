"""Offline comparison of exits from the lab's initial paper buys; no live changes."""
import datetime as dt
import json
import math
from pathlib import Path
import urllib.request
import execution
import research
from local_reports import destination

POLICIES=('hold','take_profit_1pct','trailing_halfpct_after_1pct')
CONFIG=dict(max_symbol_fraction=.2,max_total_fraction=.6,max_order_fraction=.05)


def compare(histories, entries, policy, stop=lambda:False):
    if policy not in POLICIES:
        raise ValueError('Saída desconhecida')
    symbols=list(entries)
    timestamps=[r['open_time'] for r in histories[symbols[0]]]
    if len(timestamps)<2:
        raise ValueError('Dados insuficientes')
    for symbol in symbols:
        research.check_rows(histories[symbol],step=60000)
        if [r['open_time'] for r in histories[symbol]]!=timestamps:
            raise ValueError('Candles desalinhados')
    if any(e['quantity']<=0 or e['cost']<=0 for e in entries.values()):
        raise ValueError('Entrada inválida')
    cash=1000-sum(e['cost'] for e in entries.values())
    if cash<0:
        raise ValueError('Entradas excedem capital')
    units={s:e['quantity'] for s,e in entries.items()}
    basis={s:e['cost']/e['quantity'] for s,e in entries.items()}
    selling={s:False for s in symbols}
    peaks={s:0. for s in symbols}
    peak,worst,halted=1000.,0.,False
    orders,realized,costs=[],0.,0.
    def risk(prices):
        nonlocal peak,worst,halted
        value=cash+sum(units[s]*prices[s] for s in symbols)
        peak=max(peak,value)
        worst=max(worst,1-value/peak)
        halted=halted or worst>=.15
        return value
    risk({s:histories[s][0]['low'] for s in symbols})
    risk({s:histories[s][0]['close'] for s in symbols})
    for i in range(1,len(timestamps)):
        opens={s:histories[s][i]['open'] for s in symbols}
        risk(opens)
        for s in symbols:
            previous=histories[s][i-1]['close']
            peaks[s]=max(peaks[s],previous)
            gain=previous*(1-.001)*(1-.001)/basis[s]-1
            armed=peaks[s]*(1-.001)*(1-.001)/basis[s]-1>=.01
            selling[s]=selling[s] or (policy=='take_profit_1pct' and gain>=.01) or (
                policy=='trailing_halfpct_after_1pct' and armed and previous<=peaks[s]*.995)
            equity=risk(opens)
            if not selling[s] or halted or stop():
                continue
            exposure=sum(units[k]*opens[k] for k in symbols)
            delta=execution.plan(equity,cash,units[s],opens[s],opens[s],exposure,0,CONFIG,.001,.001)
            if stop():
                continue
            old=units[s]
            cash,units[s],order=research.fill(cash,old,opens[s],delta,.001,.001)
            if order:
                realized+=order['quantity']*(order['price']-basis[s])-order['fee']
                costs+=order['fee']+order['slippage_cost']
                orders.append(dict(symbol=s,time=timestamps[i],**order))
        risk({s:histories[s][i]['low'] for s in symbols})
        risk({s:histories[s][i]['close'] for s in symbols})
    terminal=cash+sum(units[s]*histories[s][-1]['close']*(1-.001)*(1-.001) for s in symbols)
    risk({s:histories[s][-1]['close'] for s in symbols})
    return dict(policy=policy,return_usdt=terminal-1000,net_equity=terminal,
                realized_pnl=realized,estimated_unrealized_pnl=terminal-1000-realized,
                drawdown=worst,halted=halted,orders=orders,exit_costs=costs,
                remaining_positions=units,adopted=False)


def main():
    root=Path(__file__).resolve().parent
    journal=root/'reports/local/live-paper-events.jsonl'
    first=next((json.loads(line) for line in journal.read_text(encoding='utf-8').splitlines()
                if json.loads(line).get('orders')),None)
    if not first or any(o['side']!='BUY' for o in first['orders']):
        raise ValueError('Não há lote inicial de compras')
    entries={o['symbol']:dict(quantity=o['quantity'],cost=o['quantity']*o['price']+o['fee']) for o in first['orders']}
    # Skip the candle containing the entry: its earlier high/low occurred before we bought.
    start=(int(first['time']*1000)//60000+1)*60000
    histories={}
    end=int(dt.datetime.now(dt.timezone.utc).timestamp()*1000)//60000*60000
    if not 120000<=end-start<=999*60000:
        raise ValueError('Este experimento cobre de 2 a 999 minutos após a entrada, sem paginação')
    for symbol in entries:
        url=f'https://data-api.binance.vision/api/v3/klines?symbol={symbol}&interval=1m&startTime={start}&endTime={end-1}&limit=1000'
        with urllib.request.urlopen(url,timeout=30) as response:
            rows=json.load(response)
        histories[symbol]=[dict(open_time=int(r[0]),time=int(r[6]),open=float(r[1]),high=float(r[2]),
                                low=float(r[3]),close=float(r[4])) for r in rows]
        research.check_rows(histories[symbol],(end-start)//60000,step=60000)
    report=dict(created=dt.datetime.now(dt.timezone.utc).isoformat(),experimental=True,adopted=False,
                start=start,end_exclusive=end,entry_time=first['time'],entries=entries,
                comparisons=[compare(histories,entries,p) for p in POLICIES])
    output=destination(root,'exit-comparison.json')
    output.write_text(json.dumps(report,indent=2),encoding='utf-8')
    lines=['# Comparação experimental de saídas','',
           'Entradas iniciais do laboratório; candles de 1 minuto fechados após a compra. Nenhuma alteração no laboratório.',
           'Sinal no fechamento, preenchimento na abertura seguinte com taxa/slippage estimados. Abertura não é bid real.',
           'Hold apenas mantém o lote inicial; não reproduz decisões diárias posteriores. Sem reentrada.', '',
           '| Cenário | Resultado líquido USDT | Realizado USDT | Vendas | Drawdown |',
           '|---|---:|---:|---:|---:|']
    for r in report['comparisons']:
        lines.append(f"| {r['policy']} | {r['return_usdt']:.4f} | {r['realized_pnl']:.4f} | {len(r['orders'])} | {r['drawdown']:.2%} |")
    lines+=['','Parâmetros fixados antes deste teste: lucro líquido de 1%, ou ativação em 1% líquido e recuo de 0,5% do maior fechamento.',
            'Uma travessia intraminuto não dispara saída: evita inventar a sequência dos preços. Gaps podem consumir o lucro.',
            'Vendas limitadas a 5% do patrimônio por ordem; resíduos abaixo de 10 USDT podem permanecer. STOP/drawdown bloqueiam ordens.',
            'Taxa e slippage de saída de 0,1% cada. Os custos de compra já estão no custo do lote inicial.',
            'Amostra curta e já consultada. Não aprova saída ou estratégia. Não há take-profit/trailing ativo na sessão noturna.',
            '',report['created']]
    output.with_suffix('.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('\n'.join(lines))


if __name__=='__main__':
    main()
