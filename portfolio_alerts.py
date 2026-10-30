"""Independent durable alert outbox for the shared PAPER wallet.

Reads the full reconciled ledger, not the last 100 dashboard fills. Telegram
failure never changes orders, risk, STOP or the execution database.
"""
from contextlib import closing,contextmanager
from decimal import Decimal as D
import json
import os
from pathlib import Path
import sqlite3
import threading
import time
from portfolio_backend import factory
from spot_engine.portfolio import Portfolio
from spot_engine.execution import digest
from spot_engine.main import save,single_runner
from spot_engine.risk import decimal_policy
from system_status import read


@decimal_policy
def ledger(root):
    broker=factory(root)
    with closing(sqlite3.connect(broker.path.resolve().as_uri()+'?mode=ro',uri=True,timeout=1)) as db:
        row=db.execute('SELECT payload FROM ledger WHERE id=1').fetchone()
        if not row or len(row[0])>16000000:raise ValueError('LEDGER_LIMIT')
        s=json.loads(row[0]);broker._reconcile(s)
        return s


@decimal_policy
def fill_messages(fills):
    """Compute each realized sale from its purchase cost, including both fees."""
    cost=D(0);messages=[]
    for f in fills:
        q,p,fee=(D(f[k]) for k in ('quantity','price','fee'))
        result=None
        if f['side']=='BUY':cost=q*p+fee
        else:result=q*p-fee-cost;cost=D(0)
        text=('[PAPER MULTIPAR — SEM DINHEIRO REAL]\n'+('Compra' if f['side']=='BUY' else 'Venda')+' '+f['symbol']+
              '\nQuantidade: '+str(q)+'\nPreço: '+str(p)+' USDT\nTaxa: '+str(fee)+' USDT')
        if result is not None:text+='\nResultado líquido desta venda: '+str(result)+' USDT'
        messages.append(text)
    return messages


class Relay:
    def __init__(self,root,send=None,clock=time.time):
        self.root=Path(root);self.folder=self.root/'reports/local/portfolio';self.path=self.folder/'alerts-state.json'
        self.send=send;self.clock=clock

    def collect(self):
        s=ledger(self.root);fills=s['fills'];now=self.clock()
        if self.path.exists():
            state=read(self.path)
            if (state.get('identity')!=s['identity'] or type(state.get('cursor')) is not int or
                not 0<=state['cursor']<=len(fills) or not isinstance(state.get('queue'),list) or
                state.get('prefix')!=digest(fills[:state['cursor']])):
                raise ValueError('ALERT_STATE_MISMATCH')
        else:
            # First activation starts at the current ledger, without replaying
            # old trades to a newly configured Telegram chat.
            state=dict(identity=s['identity'],cursor=len(fills),prefix=digest(fills),queue=[],health=None,last_delivery_ms=None)
        messages=fill_messages(fills)
        for index in range(state['cursor'],len(fills)):
            state['queue'].append(dict(key='fill_'+str(index),text=messages[index]))
        state['cursor']=len(fills);state['prefix']=digest(fills)
        report=read(self.folder/'status.json');stamp=report.get('updated_ms')
        fresh=type(stamp) is int and 0<=now*1000-stamp<60000
        phase=report.get('phase','UNKNOWN');reason=report.get('reason','NO_REPORT')
        health=('STALE','NO_RECENT_REPORT') if not fresh else (phase,reason if phase!='RUNNING' else s.get('halt') or 'ACTIVE')
        key=list(health)
        if state['health']!=key:
            state['queue'].append(dict(key='health_'+str(int(now*1000)),text='[PAPER MULTIPAR]\nEstado: '+health[0]+'\nMotivo: '+health[1]+'\nSTOP não liquida posições.'))
            state['health']=key
        if len(state['queue'])>1000:raise ValueError('OUTBOX_LIMIT')
        save(self.path,state)
        return state

    def poll(self):
        state=self.collect();delivery='DISABLED' if self.send is None else 'IDLE'
        if self.send is not None and state['queue']:
            try:sent=self.send(state['queue'][0]['text']) is True
            except Exception:sent=False
            if sent:
                state['queue'].pop(0);state['last_delivery_ms']=int(self.clock()*1000);save(self.path,state);delivery='SENT'
            else:delivery='RETRY_PENDING'
        save(self.folder/'alerts-status.json',dict(updated_ms=int(self.clock()*1000),telegram_enabled=self.send is not None,
             delivery=delivery,pending=len(state['queue']),last_delivery_ms=state['last_delivery_ms']))
        return delivery


@contextmanager
def service(root):
    """Local collection always; external messages only with configured credentials."""
    folder=Path(root)/'reports/local/portfolio'
    stopping=threading.Event()
    with single_runner(folder/'alerts.lock'):
        send=None
        if os.getenv('TELEGRAM_BOT_TOKEN') and os.getenv('TELEGRAM_CHAT_ID'):
            from bot import notify
            send=notify
        relay=Relay(root,send)
        def work():
            while not stopping.is_set():
                try:relay.poll()
                except Exception:
                    # No provider exceptions or credential-bearing URLs in logs.
                    try:save(folder/'alerts-status.json',dict(updated_ms=int(time.time()*1000),telegram_enabled=send is not None,delivery='LOCAL_REPORT_ERROR'))
                    except OSError:pass
                stopping.wait(10)
        worker=threading.Thread(target=work,daemon=True,name='portfolio-alerts');worker.start()
        try:yield
        finally:stopping.set();worker.join(timeout=2)


def main():
    import argparse
    parser=argparse.ArgumentParser(description='Alertas independentes da carteira PAPER; não inicia ou altera trading.')
    parser.add_argument('--data-dir',type=Path,default=Path(__file__).resolve().parent)
    parser.add_argument('--start',action='store_true')
    args=parser.parse_args()
    enabled=bool(os.getenv('TELEGRAM_BOT_TOKEN') and os.getenv('TELEGRAM_CHAT_ID'))
    print('Telegram: '+('configurado' if enabled else 'não configurado; somente fila local'),flush=True)
    if not args.start:return
    with service(args.data_dir):
        try:
            while True:time.sleep(1)
        except KeyboardInterrupt:pass


if __name__=='__main__':main()
