"""Isolated historical comparison; no account or order endpoints."""
from decimal import Decimal, ROUND_DOWN
import datetime as dt
import json
from pathlib import Path
import statistics
import time
from small_cap_scan import universe
from market_view import public_get
from local_reports import destination
import research


def quantity(meta,reference,budget=None,units=None,stress=1):
    filters={f['filterType']:f for f in meta['filters']}
    lot=filters['LOT_SIZE'];step=Decimal(lot['stepSize'])
    price=Decimal(str(reference))*(1+Decimal('.001')*stress if budget is not None else 1-Decimal('.001')*stress)
    raw=Decimal(str(budget))/(price*(1+Decimal('.001')*stress)) if budget is not None else Decimal(str(units))
    q=(raw/step).to_integral_value(rounding=ROUND_DOWN)*step
    minimum=max([Decimal(f['minNotional']) for f in meta['filters'] if f['filterType'] in ('MIN_NOTIONAL','NOTIONAL')]+[Decimal(0)])
    # Require minimum at both reference and adverse fill; never increase order to meet it.
    if q<Decimal(lot['minQty']) or q>Decimal(lot['maxQty']) or q*min(price,Decimal(str(reference)))<minimum:
        return 0.
    if 'NOTIONAL' in filters and q*max(price,Decimal(str(reference)))>Decimal(filters['NOTIONAL']['maxNotional']):
        return 0.
    return float(q)


def simulate(histories,metadata,fraction,stress=1,stop=lambda:False,entry_interval=1):
    if fraction not in (.05,.25) or stress not in (1,2) or not histories or entry_interval not in (1,24):
        raise ValueError('Cenário inválido')
    symbols=sorted(histories); times=[r['open_time'] for r in histories[symbols[0]]]
    if len(times)<62:
        raise ValueError('Histórico insuficiente')
    for s in symbols:
        research.check_rows(histories[s],step=3600000)
        if [r['open_time'] for r in histories[s]]!=times or s not in metadata:
            raise ValueError('Históricos/filtros incompatíveis')
    cash,peak,drawdown=20.,20.,0.
    position=None; orders=[];blocked=0;halted=False;realized=0.
    fee=slip=.001*stress
    def mark(index,key):
        return cash+(position['units']*histories[position['symbol']][index][key] if position else 0)
    def risk(value):
        nonlocal peak,drawdown,halted
        peak=max(peak,value);drawdown=max(drawdown,1-value/peak);halted=halted or drawdown>=.15
    for i in range(60,len(times)):
        risk(mark(i,'open'))
        if stop() or halted:
            break
        if position:
            s=position['symbol']; prev=[r['close'] for r in histories[s][i-60:i]]
            net=position['units']*prev[-1]*(1-slip)*(1-fee)
            gain=net/position['cost']-1
            reason='proteção de perda' if gain<=-.02 else 'perda de tendência' if prev[-1]<statistics.mean(prev[-20:]) else 'alvo líquido de 1%' if gain>=.01 else None
            if reason:
                q=quantity(metadata[s],histories[s][i]['open'],units=position['units'],stress=stress)
                if q and not stop():
                    price=histories[s][i]['open']*(1-slip);charge=q*price*fee
                    removed=position['cost']*q/position['units']
                    pnl=q*price-charge-removed;realized+=pnl;cash+=q*price-charge
                    position['units']-=q;position['cost']-=removed
                    orders.append(dict(time=times[i],symbol=s,side='SELL',quantity=q,price=price,fee=charge,realized_pnl=pnl,reason=reason))
                    if position['units']<1e-12:
                        position=None
                else:
                    blocked+=1
            # Never rotate/rebuy in the candle of a sale; residual inventory prevents a second position.
        elif (i-60)%entry_interval==0:
            candidates=[]
            for s in symbols:
                prev=[r['close'] for r in histories[s][i-60:i]]
                fast,slow=statistics.mean(prev[-20:]),statistics.mean(prev[-50:])
                momentum=prev[-1]/prev[-7]-1
                if slow<fast and slow<prev[-1]<=fast*1.005 and momentum>0:
                    candidates.append((-momentum,s))
            for _,s in sorted(candidates):
                budget=min(20*fraction,mark(i,'open')*fraction,cash)
                q=quantity(metadata[s],histories[s][i]['open'],budget=budget,stress=stress)
                if not q:
                    blocked+=1;continue
                if stop():
                    break
                price=histories[s][i]['open']*(1+slip);charge=q*price*fee;cost=q*price+charge
                cash-=cost;position=dict(symbol=s,units=q,cost=cost)
                orders.append(dict(time=times[i],symbol=s,side='BUY',quantity=q,price=price,fee=charge,reason='recuo em tendência'))
                break
        risk(mark(i,'low'));risk(mark(i,'close'))
    # If stopped early, mark at the current simulation candle, never at a later unseen price.
    net=cash+(position['units']*histories[position['symbol']][i]['close']*(1-slip)*(1-fee) if position else 0)
    risk(net)
    return dict(fraction=fraction,stress=stress,equity=net,pnl=net-20,realized=realized,
                unrealized=net-20-realized,drawdown=drawdown,halted=halted,
                blocked=blocked,orders=orders,buys=sum(o['side']=='BUY' for o in orders),
                sells=sum(o['side']=='SELL' for o in orders),position=position,cash=cash,approved=False)


def main():
    end=int(time.time()*1000)//3600000*3600000
    metadata={s['symbol']:s for s in universe(public_get('exchangeInfo'),public_get('ticker/24hr'))}
    histories={};excluded=[]
    for s in metadata:
        rows=public_get(f'klines?symbol={s}&interval=1h&limit=1000&startTime={end-780*3600000}&endTime={end-1}')
        histories[s]=[dict(open_time=int(r[0]),open=float(r[1]),high=float(r[2]),low=float(r[3]),close=float(r[4])) for r in rows]
        if len(histories[s])!=780:
            excluded.append(dict(symbol=s,reason='Histórico incompleto para a janela fixa de 30 dias'))
            del histories[s]
            print(f'{s}: excluído por histórico incompleto.',flush=True)
            continue
        research.check_rows(histories[s],780)
        if histories[s][-1]['open_time']!=end-3600000:
            raise ValueError('Histórico desatualizado')
    report=dict(created=dt.datetime.now(dt.timezone.utc).isoformat(),start=end-720*3600000,end=end,
                capital=20,symbols=list(histories),excluded=excluded,approved=False,
                comparisons=[simulate(histories,metadata,f,stress) for f in (.05,.25) for stress in (1,2)])
    destination(Path(__file__).resolve().parent,'small-cap-comparison.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    for r in report['comparisons']:
        print(f"Limite {r['fraction']:.0%}; custos {r['stress']}x; resultado {r['pnl']:.6f} USDT; compras {r['buys']}; vendas {r['sells']}; bloqueios {r['blocked']}; DD {r['drawdown']:.2%}")
    print('Pesquisa histórica de 30 dias, universo/filtros atuais, execução aproximada. Nenhuma aprovação ou ativação.')


if __name__=='__main__':
    main()
