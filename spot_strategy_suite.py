"""Separate historical proxies for Spot strategies. Never changes the live experiment."""
import datetime as dt
import json
from pathlib import Path
import statistics
import time
from market_view import public_get
from small_cap_research import quantity
from local_reports import destination
import research

STRATEGIES=('grid_spot_proxy','dca_spot','rebalance','souto_quartiles')
SYMBOLS=('BTCUSDT','ETHUSDT','DOGEUSDT','PEPEUSDT')


def quartile_signal(prices):
    if len(prices)<26:
        return 0
    p=prices[-26:];m10=statistics.mean(p[-10:]);m16=statistics.mean(p[-16:]);m26=statistics.mean(p)
    q1,_,q3=statistics.quantiles(p,n=4,method='inclusive')
    return 1 if p[-1]<=q1 and m16<m10<m26 else -1 if p[-1]>=q3 and m16>m10>m26 else 0


def simulate(histories,metadata,strategy,stress=1,stop=lambda:False):
    if strategy not in STRATEGIES or stress not in (1,2) or not histories:
        raise ValueError('Cenário inválido')
    symbols=sorted(histories);times=[r['open_time'] for r in histories[symbols[0]]]
    if len(times)<62:raise ValueError('Amostra insuficiente')
    for s in symbols:
        research.check_rows(histories[s])
        if [r['open_time'] for r in histories[s]]!=times:raise ValueError('Históricos desalinhados')
    cash=peak=20.;dd=realized=fees=0.;halted=False;orders=[];blocked=0
    positions={s:dict(units=0.,cost=0.) for s in symbols}
    anchors={s:histories[s][59]['close'] for s in symbols};grid_off=set()
    fee=slip=.001*stress
    def mark(prices):
        return cash+sum(positions[s]['units']*prices[s]*(1-slip)*(1-fee) for s in symbols)
    def risk(prices):
        nonlocal peak,dd,halted
        equity=mark(prices);peak=max(peak,equity);dd=max(dd,1-equity/peak);halted=halted or dd>=.15
        return equity
    for i in range(60,len(times)):
        opens={s:histories[s][i]['open'] for s in symbols}
        equity=risk(opens)
        if halted or stop():break
        for s in symbols:
            if stop() or halted:break
            prev=[r['close'] for r in histories[s][i-60:i]];last=prev[-1];p=positions[s]
            value=p['units']*opens[s];desired=0.;reason=''
            if strategy=='dca_spot' and (i-60)%24==0:
                desired=5.;reason='DCA periódico de 24 horas'
            elif strategy=='rebalance' and (i-60)%24==0:
                delta=equity*.15-value
                if abs(delta)>=equity*.05:desired=delta;reason='Rebalancear 15% por ativo; 40% em caixa'
            elif strategy=='souto_quartiles':
                signal=quartile_signal(prev)
                desired=5. if signal==1 else -value if signal==-1 else 0.
                reason='Quartis e médias 10/16/26'
            elif strategy=='grid_spot_proxy':
                if abs(last/anchors[s]-1)>.03:grid_off.add(s)
                if s not in grid_off:
                    level=min(4,max(0,int((1-last/anchors[s])/.005)))
                    if level:desired=equity*.0625*level-value;reason='Proxy de inventário em quatro degraus'
                    if p['units'] and p['units']*last*(1-slip)*(1-fee)>p['cost']*1.01:
                        desired=-value;reason='Saída da grade por ganho líquido de 1%'
            if not desired:continue
            if desired>0:
                exposure=sum(positions[k]['units']*opens[k] for k in symbols)
                # Conservative cost budget respects 25% per asset and 60% total, including fee headroom.
                budget=max(0,min(5,desired,cash,equity*.25-value,equity*.60-exposure))
                q=quantity(metadata[s],opens[s],budget=budget,stress=stress) if budget else 0
                side='BUY';price=opens[s]*(1+slip)
            else:
                q=quantity(metadata[s],opens[s],units=min(p['units'],5/opens[s],abs(desired)/opens[s]),stress=stress)
                side='SELL';price=opens[s]*(1-slip)
            if not q:blocked+=1;continue
            if stop():break
            charge=q*price*fee;fees+=charge
            if side=='BUY':
                cost=q*price+charge;cash-=cost;p['units']+=q;p['cost']+=cost;pnl=None
            else:
                removed=p['cost']*q/p['units'];pnl=q*price-charge-removed
                cash+=q*price-charge;realized+=pnl;p['cost']-=removed;p['units']-=q
            orders.append(dict(time=times[i],symbol=s,side=side,quantity=q,price=price,fee=charge,pnl=pnl,reason=reason))
            equity=risk(opens)
        risk({s:histories[s][i]['low'] for s in symbols});risk({s:histories[s][i]['close'] for s in symbols})
    equity=mark({s:histories[s][i]['close'] for s in symbols})
    return dict(strategy=strategy,stress=stress,equity=equity,pnl=equity-20,realized=realized,unrealized=equity-20-realized,
                fees=fees,drawdown=dd,halted=halted,buys=sum(o['side']=='BUY' for o in orders),
                sells=sum(o['side']=='SELL' for o in orders),blocked=blocked,orders=orders,positions=positions,approved=False)


def main():
    end=int(time.time()*1000)//3600000*3600000
    info=public_get('exchangeInfo');metadata={s['symbol']:s for s in info['symbols'] if s['symbol'] in SYMBOLS and s['status']=='TRADING'}
    if len(metadata)!=len(SYMBOLS):raise SystemExit('Universo fixo indisponível')
    histories={}
    for s in SYMBOLS:
        raw=public_get(f'klines?symbol={s}&interval=1h&limit=1000&startTime={end-780*3600000}&endTime={end-1}')
        histories[s]=[dict(open_time=int(r[0]),open=float(r[1]),high=float(r[2]),low=float(r[3]),close=float(r[4])) for r in raw]
        research.check_rows(histories[s],780)
        if histories[s][-1]['open_time']!=end-3600000:raise ValueError('Dados atrasados')
    report=dict(created=dt.datetime.now(dt.timezone.utc).isoformat(),capital=20,start=end-720*3600000,end=end,
                approved=False,comparisons=[simulate(histories,metadata,s,stress) for s in STRATEGIES for stress in (1,2)])
    destination(Path(__file__).resolve().parent,'spot-suite.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    for r in report['comparisons']:
        print(r['strategy'],r['stress'],'x',round(r['pnl'],6),'USDT',r['buys'],'compras',r['sells'],'vendas')
    print('Proxies históricos em candles horários; não são bots nativos Binance. Sem aprovação e sem mudança na sessão ativa.')


if __name__=='__main__':main()
