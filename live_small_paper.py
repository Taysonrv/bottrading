"""Continuous 20-USDT experiment. Public market GETs only. No real broker."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import time
from paper_lab import lock,save
from market_view import public_get
from small_cap_scan import universe
from small_cap_research import quantity
import research

ROOT=Path(__file__).resolve().parent
PATH=ROOT/'reports/local/live-small-paper.json'


def stopped():
    return (ROOT/'STOP').exists()


def advance(state,metadata,histories,quotes,now,stop=stopped):
    pos=state.get('position');orders=state['orders'];fee=slip=.001
    for q in quotes.values():
        if not all(math.isfinite(q[k]) and q[k]>0 for k in ('bid','ask')) or q['bid']>q['ask']:
            raise ValueError('Cotação inválida')
    net=state['cash']+(pos['units']*quotes[pos['symbol']]['bid']*(1-slip)*(1-fee) if pos else 0)
    state['peak']=max(state['peak'],net)
    state['drawdown']=1-net/state['peak']
    state['halted']=state.get('halted',False) or state['drawdown']>=.15
    reason='Aguardando sinal de tendência; nenhuma compra forçada'
    if stop() or state['halted']:
        reason='Ordens bloqueadas por STOP ou drawdown de 15%; posições não liquidadas'
    elif pos:
        s=pos['symbol'];prices=[r['close'] for r in histories[s]]
        gain=pos['units']*quotes[s]['bid']*(1-slip)*(1-fee)/pos['cost']-1
        exit_reason='proteção de perda líquida de 2%' if gain<=-.02 else 'alvo líquido de 1%' if gain>=.01 else 'perda de tendência' if prices[-1]<statistics.mean(prices[-20:]) else None
        reason=f'Posição {s}; resultado líquido estimado {gain:.3%}; aguardando saída'
        if exit_reason:
            q=quantity(metadata[s],quotes[s]['bid'],units=pos['units'])
            reason='Venda bloqueada pelo mínimo/lote' if not q else exit_reason
            if q and not stop():
                price=quotes[s]['bid']*(1-slip);charge=q*price*fee;removed=pos['cost']*q/pos['units']
                pnl=q*price-charge-removed
                state['cash']+=q*price-charge;state['realized']+=pnl
                pos['units']-=q;pos['cost']-=removed
                orders.append(dict(time=now,symbol=s,side='SELL',quantity=q,price=price,fee=charge,pnl=pnl,reason=exit_reason))
                if pos['units']<1e-12:
                    state['position']=None;pos=None
    else:
        candidates=[];blocked=0
        candle=next(iter(histories.values()))[-1]['open_time']
        for s,rows in histories.items():
            prices=[r['close'] for r in rows];fast=statistics.mean(prices[-20:]);slow=statistics.mean(prices[-50:]);momentum=prices[-1]/prices[-7]-1
            if slow<fast and slow<prices[-1]<=fast*1.005 and momentum>0:
                candidates.append((-momentum,s))
        if state.get('last_entry_candle')!=candle:
            for _,s in sorted(candidates):
                quote=quotes[s]
                if quote['ask']/quote['bid']-1>.001:
                    blocked+=1;continue
                q=quantity(metadata[s],quote['ask'],budget=min(5,net*.25,state['cash']))
                if not q:
                    blocked+=1;continue
                if stop():
                    reason='STOP acionado antes da ordem';break
                price=quote['ask']*(1+slip);charge=q*price*fee;cost=q*price+charge
                state['cash']-=cost;state['position']=dict(symbol=s,units=q,cost=cost)
                state['last_entry_candle']=candle
                orders.append(dict(time=now,symbol=s,side='BUY',quantity=q,price=price,fee=charge,pnl=None,reason='Recuo em tendência horária'))
                reason=f'Compra fictícia de {s}';break
            else:
                reason=f'Sem entrada executável: {len(candidates)} sinais; {blocked} bloqueios de mínimo/lote/spread'
        else:
            reason='Entrada já realizada neste candle horário; aguardando o próximo'
    pos=state.get('position')
    net=state['cash']+(pos['units']*quotes[pos['symbol']]['bid']*(1-slip)*(1-fee) if pos else 0)
    state['peak']=max(state['peak'],net);state['drawdown']=1-net/state['peak'];state['halted']=state['halted'] or state['drawdown']>=.15
    state.update(equity=net,pnl=net-20,unrealized=net-20-state['realized'],decision=reason,updated=now,phase='waiting')
    state['curve'].append(dict(time=now,equity=net));state['curve']=state['curve'][-1500:]
    state['orders']=orders[-500:]
    return state


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--hours',type=float,default=24);args=parser.parse_args()
    if not math.isfinite(args.hours) or not 0<args.hours<=24:
        parser.error('Duração de até 24 horas')
    with lock(ROOT/'reports/local/live-small-paper.lock'):
        identity=hashlib.sha256(b''.join((ROOT/n).read_bytes() for n in ('live_small_paper.py','small_cap_research.py','small_cap_scan.py'))).hexdigest()
        if PATH.exists():
            state=json.loads(PATH.read_text(encoding='utf-8'))
            if state['identity']!=identity or state['end']<=time.time():
                raise SystemExit('Sessão encerrada ou código mudou. Preserve os dados antes de criar outra; saldo não reiniciado.')
        else:
            state=dict(initial=20,cash=20.,equity=20.,pnl=0.,realized=0.,unrealized=0.,peak=20.,drawdown=0.,halted=False,
                       position=None,orders=[],curve=[],started=time.time(),end=time.time()+args.hours*3600,identity=identity)
        state.update(pid=os.getpid(),phase='starting',decision='Consultando dados públicos',updated=time.time());save(PATH,state)
        metadata={};histories={};cached_hour=None
        try:
            while time.time()<state['end']:
                if stopped():
                    state.update(phase='stopped',decision='STOP acionado; posição fictícia preservada');break
                try:
                    hour=int(time.time())//3600
                    if hour!=cached_hour:
                        metadata={m['symbol']:m for m in universe(public_get('exchangeInfo'),public_get('ticker/24hr'))}
                        if state['position']:
                            s=state['position']['symbol']
                            if s not in metadata:
                                info=public_get('exchangeInfo?symbol='+s)['symbols'][0]
                                if info['status']!='TRADING':
                                    raise ValueError('Par da posição suspenso')
                                metadata[s]=info
                        end=hour*3600000
                        def fetch(s):
                            raw=public_get(f'klines?symbol={s}&interval=1h&limit=60&startTime={end-60*3600000}&endTime={end-1}')
                            rows=[dict(open_time=int(r[0]),open=float(r[1]),high=float(r[2]),low=float(r[3]),close=float(r[4])) for r in raw]
                            research.check_rows(rows,60)
                            if rows[-1]['open_time']!=end-3600000:raise ValueError('Histórico atrasado')
                            return s,rows
                        with ThreadPoolExecutor(max_workers=4) as pool:
                            histories=dict(pool.map(fetch,metadata))
                        cached_hour=hour
                    before=time.time()
                    raw=public_get('ticker/bookTicker');quotes={q['symbol']:dict(bid=float(q['bidPrice']),ask=float(q['askPrice'])) for q in raw if q['symbol'] in metadata}
                    if time.time()-before>15 or int(time.time())//3600!=cached_hour:
                        raise ValueError('Lote atrasado ou horário mudou')
                    advance(state,metadata,histories,quotes,time.time())
                    state['error']=None;save(PATH,state)
                    print(json.dumps(dict(time=state['updated'],equity=state['equity'],orders=len(state['orders']),decision=state['decision'])),flush=True)
                except Exception as error:
                    state.update(phase='error',error=type(error).__name__,decision='Ciclo bloqueado: dados indisponíveis ou inválidos',heartbeat=time.time());save(PATH,state)
                    print('Ciclo bloqueado: '+type(error).__name__,flush=True)
                for _ in range(60):
                    if stopped() or time.time()>=state['end']:break
                    time.sleep(1)
        except KeyboardInterrupt:
            state['decision']='Processo interrompido; carteira fictícia preservada'
        finally:
            state.update(phase='stopped',heartbeat=time.time());save(PATH,state)


if __name__=='__main__':
    main()
