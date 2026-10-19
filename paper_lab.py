"""Explicitly experimental forward paper account. Public GET data only; no live broker."""
import argparse
from contextlib import contextmanager
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import time
import urllib.request
import accounting
import execution
import research

ROOT = Path(__file__).resolve().parent
CONFIG = dict(symbols=['BTCUSDT','ETHUSDT'], fee_rate=.001, slippage_rate=.001,
              max_order_fraction=.05, max_symbol_fraction=.2, max_total_fraction=.6)


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(path)


def request(path):
    # No keys, payload, signatures or arbitrary host accepted.
    with urllib.request.urlopen('https://data-api.binance.vision/api/v3/'+path, timeout=20) as response:
        return json.load(response)


def daily_signal(rows, timestamp):
    closed = [r for r in rows if int(r[6]) < timestamp*1000]
    if len(closed) < 201:
        raise ValueError('Menos de 201 dias fechados')
    closed = closed[-201:]
    if any(int(b[0])-int(a[0]) != 86400000 for a,b in zip(closed,closed[1:])):
        raise ValueError('Lacuna no histórico diário')
    if not 0 <= timestamp*1000-int(closed[-1][6]) <= 26*3600000:
        raise ValueError('Candle diário atrasado')
    prices = [float(r[4]) for r in closed]
    if any(not math.isfinite(p) or p <= 0 for p in prices):
        raise ValueError('Preço diário inválido')
    returns = [prices[i]/prices[i-1]-1 for i in range(len(prices)-30,len(prices))]
    vol = statistics.stdev(returns)*365**.5
    target = min(1.,.20/vol) if vol else 1.
    positive = prices[-1] > statistics.mean(prices[-200:])
    return dict(candle=str(closed[-1][6]), target=target if positive else 0.,
                reason='Acima da média diária de 200 dias' if positive else 'Em caixa: abaixo da média diária de 200 dias')


def quote(symbol):
    q = request('ticker/bookTicker?symbol='+symbol)
    bid, ask = float(q['bidPrice']), float(q['askPrice'])
    if not all(math.isfinite(v) and v>0 for v in (bid,ask)) or bid>ask:
        raise ValueError('Cotação inválida')
    return dict(bid=bid,ask=ask)


def stopped(control):
    return (ROOT/'STOP').exists() or (control is not None and (control/'STOP').exists())


def cycle(state, signals, quotes, stop=lambda:False):
    """One entry/exit adjustment per closed daily candle; no catch-up trades."""
    prices = {s:q['bid'] for s,q in quotes.items()}
    accounting.initialize(state, prices)
    def risk():
        equity = state['cash']+sum(q*prices[s] for s,q in state['positions'].items())
        state['peak'] = max(state['peak'],equity)
        state['halted'] = state['halted'] or equity <= state['peak']*.85
        return equity
    risk()
    fills = []
    for s in CONFIG['symbols']:
        equity = risk()
        if stop() or state['halted']:
            break
        signal = signals[s]
        if state['last'].get(s)==signal['candle']:
            continue
        units = state['positions'].get(s,0.)
        exposure = sum(q*prices[k] for k,q in state['positions'].items())
        buying = equity*CONFIG['max_symbol_fraction']*signal['target'] > units*prices[s]
        reference = quotes[s]['ask'] if buying else quotes[s]['bid']
        delta = execution.plan(equity,state['cash'],units,prices[s],reference,exposure,
                               signal['target'],CONFIG,CONFIG['fee_rate'],CONFIG['slippage_rate'])
        if abs(delta)>=10:
            if stop() or state['halted']:
                break
            state['cash'],state['positions'][s],order = research.fill(
                state['cash'],units,reference,delta,CONFIG['fee_rate'],CONFIG['slippage_rate'])
            if order:
                order['realized_pnl'] = accounting.record(state,s,units,order)
                fills.append(dict(symbol=s,**order))
        state['last'][s]=signal['candle']
    risk()
    accounting.mark(state,prices,CONFIG['fee_rate'],CONFIG['slippage_rate'])
    return fills


@contextmanager
def lock(path):
    import msvcrt
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('a+b') as stream:
        stream.seek(0,2)
        if stream.tell()==0:
            stream.write(b'0'); stream.flush()
        stream.seek(0)
        try:
            msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
        except PermissionError:
            raise SystemExit('Laboratório já está ativo; não inicie outro processo.') from None
        try:
            yield
        finally:
            stream.seek(0)
            msvcrt.locking(stream.fileno(),msvcrt.LK_UNLCK,1)


def main():
    parser = argparse.ArgumentParser(description='Experimento com saldo fictício; estratégia NÃO aprovada')
    parser.add_argument('--hours',type=float,default=10)
    parser.add_argument('--control-dir',type=Path,help='Também respeitar STOP desta pasta')
    args = parser.parse_args()
    if not math.isfinite(args.hours) or not 0<args.hours<=24:
        parser.error('Duração deve ser maior que zero e até 24 horas')
    folder = ROOT/'reports/local'
    path = folder/'live-paper.json'
    with lock(folder/'live-paper.lock'):
        identity = hashlib.sha256(b''.join((ROOT/name).read_bytes() for name in
                     ('paper_lab.py','research.py','execution.py','accounting.py'))).hexdigest()
        if path.exists():
            state = json.loads(path.read_text(encoding='utf-8'))
            if state.get('identity')!=identity:
                raise SystemExit('Código mudou: preserve a sessão anterior antes de iniciar outra.')
            if state['end']<=time.time():
                raise SystemExit('A sessão terminou. Preserve o relatório; não reinicie saldos automaticamente.')
        else:
            state = dict(cash=1000.,positions={},peak=1000.,halted=False,last={},
                         started=time.time(),end=time.time()+args.hours*3600,identity=identity,curve=[])
        state.update(experimental=True,strategy='sma200_vol_daily',pid=os.getpid(),phase='starting')
        save(path,state)
        signal_cache, cache_day = {}, None
        try:
            while time.time()<state['end'] and not stopped(args.control_dir):
                try:
                    timestamp = time.time()
                    day = int(timestamp)//86400
                    if day!=cache_day:
                        signal_cache = {s:daily_signal(request('klines?symbol='+s+'&interval=1d&limit=250'),timestamp)
                                        for s in CONFIG['symbols']}
                        cache_day = day
                    quotes = {s:quote(s) for s in CONFIG['symbols']}
                    # Reject a delayed batch instead of treating stale quotes as current.
                    if time.time()-timestamp>30:
                        raise ValueError('Consulta de preços demorou demais')
                    orders = cycle(state,signal_cache,quotes,lambda:stopped(args.control_dir))
                    state.update(updated=time.time(),phase='waiting',signals=signal_cache,error=None)
                    state['curve'].append(dict(time=state['updated'],equity=state['performance']['equity']))
                    state['curve']=state['curve'][-1500:]
                    save(path,state)
                    with (folder/'live-paper-events.jsonl').open('a',encoding='utf-8') as stream:
                        stream.write(json.dumps(dict(time=state['updated'],orders=orders,
                                     equity=state['performance']['equity']))+'\n')
                    print(json.dumps(dict(equity=state['performance']['equity'],orders=len(orders),
                                          halted=state['halted'],signals=signal_cache)),flush=True)
                except Exception as error:
                    state.update(updated=time.time(),phase='error',error=type(error).__name__)
                    save(path,state)
                    print('Ciclo experimental bloqueado: '+type(error).__name__,flush=True)
                for _ in range(60):
                    if stopped(args.control_dir) or time.time()>=state['end']:
                        break
                    time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            state.update(updated=time.time(),phase='stopped')
            save(path,state)


if __name__=='__main__':
    main()
