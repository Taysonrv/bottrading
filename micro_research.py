"""Predeclared 25-USDT buy-dip/sell-rise research. Never touches the running lab."""
import datetime as dt
import hashlib
import json
from pathlib import Path
import statistics
import time
import urllib.request
import execution
import research
from local_reports import destination

CONFIG=dict(max_order_fraction=.05,max_symbol_fraction=.2,max_total_fraction=.6)
TARGETS=(.0025,.005,.01)


def simulate(histories,target,stress=1,stop=lambda:False):
    if target not in TARGETS or stress not in (1,2):
        raise ValueError('Hipótese não declarada')
    symbols=list(histories)
    if not symbols:
        raise ValueError('Histórico vazio')
    times=[r['open_time'] for r in histories[symbols[0]]]
    if len(times)<62:
        raise ValueError('Histórico insuficiente')
    for rows in histories.values():
        research.check_rows(rows,step=60000)
        if [r['open_time'] for r in rows]!=times:
            raise ValueError('Ativos desalinhados')
    fee=slip=.001*stress
    cash,peak,worst,halted=1000.,1000.,0.,False
    lots={s:[] for s in symbols}
    trades=[]
    realized=costs=0.
    def units(s):
        return sum(lot['quantity'] for lot in lots[s])
    def mark(prices):
        return cash+sum(units(s)*prices[s] for s in symbols)
    def risk(prices):
        nonlocal peak,worst,halted
        value=mark(prices)
        peak=max(peak,value)
        worst=max(worst,1-value/peak)
        halted=halted or worst>=.15
        return value
    for i in range(60,len(times)):
        opens={s:histories[s][i]['open'] for s in symbols}
        risk(opens)
        for s in symbols:
            closes=[r['close'] for r in histories[s][i-60:i]]
            fast,slow=statistics.mean(closes[-20:]),statistics.mean(closes)
            down=fast<slow or closes[-1]/closes[0]-1<=-.02
            sold=False
            for lot in list(lots[s]):
                equity=risk(opens)
                if halted or stop():
                    break
                net_gain=lot['quantity']*closes[-1]*(1-slip)*(1-fee)/lot['cost']-1
                reason='lucro líquido alvo' if net_gain>=target else 'tendência de queda' if down else 'perda de 2%' if net_gain<=-.02 else None
                if not reason:
                    continue
                previous=units(s)
                exposure=sum(units(k)*opens[k] for k in symbols)
                delta=execution.plan(equity,cash,previous,opens[s],opens[s],exposure,0,CONFIG,fee,slip)
                delta=-min(abs(delta),lot['quantity']*opens[s])
                if stop():
                    break
                cash,new_units,order=research.fill(cash,previous,opens[s],delta,fee,slip)
                if order:
                    removed=lot['cost']*order['quantity']/lot['quantity']
                    pnl=order['quantity']*order['price']-order['fee']-removed
                    realized+=pnl
                    costs+=order['fee']+order['slippage_cost']
                    lot['cost']-=removed
                    lot['quantity']-=order['quantity']
                    if lot['quantity']<=1e-12:
                        lots[s].remove(lot)
                    trades.append(dict(time=times[i],symbol=s,reason=reason,realized_pnl=pnl,**order))
                    sold=True
            # No sell-and-rebuy in the same candle. Each further buy requires a new lower rung.
            if halted or stop() or down or sold or closes[-1]>=fast*.999:
                continue
            if lots[s] and closes[-1]>lots[s][-1]['entry_reference']*.997:
                continue
            equity=risk(opens)
            if halted:
                continue
            previous=units(s)
            exposure=sum(units(k)*opens[k] for k in symbols)
            delta=min(25/((1+slip)*(1+fee)),execution.plan(
                equity,cash,previous,opens[s],opens[s],exposure,1,CONFIG,fee,slip))
            if stop():
                break
            cash,new_units,order=research.fill(cash,previous,opens[s],delta,fee,slip)
            if order:
                lots[s].append(dict(quantity=order['quantity'],cost=order['quantity']*order['price']+order['fee'],
                                    entry_reference=closes[-1]))
                costs+=order['fee']+order['slippage_cost']
                trades.append(dict(time=times[i],symbol=s,reason='recuo com filtro de tendência',**order))
        risk({s:histories[s][i]['low'] for s in symbols})
        risk({s:histories[s][i]['close'] for s in symbols})
    net=cash+sum(units(s)*histories[s][-1]['close']*(1-slip)*(1-fee) for s in symbols)
    worst=max(worst,1-net/peak)
    halted=halted or worst>=.15
    sales=[t for t in trades if t['side']=='SELL']
    benchmark=sum(histories[s][-1]['close']*(1-slip)*(1-fee)/
                  (histories[s][60]['open']*(1+slip)*(1+fee)) for s in symbols)/len(symbols)-1
    return dict(target=target,stress=stress,net_equity=net,pnl=net-1000,realized=realized,
                unrealized=net-1000-realized,costs=costs,drawdown=worst,halted=halted,
                benchmark_pnl=benchmark*1000,buy_count=sum(t['side']=='BUY' for t in trades),
                sell_count=len(sales),profitable_sales=sum(t['realized_pnl']>0 for t in sales),
                remaining_positions={s:units(s) for s in symbols},orders=trades,
                adopted=False,approved=False)


def main():
    root=Path(__file__).resolve().parent
    end=int(time.time()*1000)//60000*60000
    start=end-780*60000
    histories={}
    for symbol in ('BTCUSDT','ETHUSDT'):
        url=f'https://data-api.binance.vision/api/v3/klines?symbol={symbol}&interval=1m&limit=1000&startTime={start}&endTime={end-1}'
        with urllib.request.urlopen(url,timeout=30) as response:
            rows=json.load(response)
        histories[symbol]=[dict(open_time=int(r[0]),time=int(r[6]),open=float(r[1]),high=float(r[2]),low=float(r[3]),close=float(r[4])) for r in rows]
        research.check_rows(histories[symbol],780,step=60000)
    report=dict(created=dt.datetime.now(dt.timezone.utc).isoformat(),start=start+60*60000,end=end,
                capital=1000,order_budget=25,adopted=False,
                data_hash=hashlib.sha256(json.dumps(histories,sort_keys=True).encode()).hexdigest(),
                comparisons=[simulate(histories,t,stress) for t in TARGETS for stress in (1,2)])
    output=destination(root,'micro-results.json')
    output.write_text(json.dumps(report,indent=2),encoding='utf-8')
    lines=['# Pequenas compras/vendas — pesquisa', '',
           'Capital fictício 1.000 USDT; até 25 USDT por compra incluindo custos. 12 horas de avaliação + 60 minutos de aquecimento.',
           'Seis tentativas predefinidas: três margens líquidas, custos normais e dobrados. Nenhuma adoção.', '',
           '| Margem líquida | Custos | Resultado USDT | Compras | Vendas | Drawdown |',
           '|---|---:|---:|---:|---:|---:|']
    for r in report['comparisons']:
        lines.append(f"| {r['target']:.2%} | {r['stress']}x | {r['pnl']:.4f} | {r['buy_count']} | {r['sell_count']} | {r['drawdown']:.2%} |")
    lines+=['','Sinal no fechamento; referência de execução na abertura seguinte, com taxa/slippage de 0,1% cada no cenário 1x. Não representa bid/ask ou livro reais.',
            'Compra no recuo de 0,1% abaixo da média de 20 minutos, somente se média 20 >= média 60; compras adicionais precisam de novo recuo de 0,3%.',
            'Venda por margem líquida atingida, média 20 abaixo da média 60, queda de 2% em 60 minutos ou perda líquida de 2% do lote. Pode vender com prejuízo.',
            'Limites de 5% por ordem, 20% por ativo e 60% no conjunto. STOP/drawdown bloqueiam ordens e não garantem liquidação.',
            'Resíduos abaixo de 10 USDT e posições remanescentes entram no patrimônio líquido estimado. Não há martingale.',
            'Janela curta e já consultada, sem teste independente; não seleciona vencedora nem altera o laboratório noturno.', '',report['created']]
    output.with_suffix('.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('\n'.join(lines))


if __name__=='__main__':
    main()
