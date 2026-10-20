"""Optional Telegram relay for paper reports, independent from order execution."""
import hashlib
import json
import os
from pathlib import Path
import threading
from paper_lab import save
from runtime_status import status


def order_key(order):
    return hashlib.sha256(json.dumps(order, sort_keys=True).encode()).hexdigest()


def order_message(order):
    side={'BUY':'Compra','SELL':'Venda'}[order['side']]
    symbol=order['symbol']
    if not isinstance(symbol,str) or not symbol.isascii() or not symbol.isalnum() or len(symbol)>24:
        raise ValueError('Par inválido')
    text=f"[SIMULAÇÃO 20 USDT] {side} {symbol}\nQuantidade: {float(order['quantity']):.8f}\nPreço: {float(order['price']):.8f} USDT\nTaxa: {float(order['fee']):.6f} USDT"
    if order['side']=='SELL' and order.get('pnl') is not None:
        text+=f"\nRealizado nesta venda: {float(order['pnl']):.6f} USDT"
    return text+'\nNenhuma ordem real.'


class Relay:
    def __init__(self, root, send):
        self.root=Path(root);self.send=send
        self.path=self.root/'reports/local/paper-alerts.json'
        if self.path.exists():
            self.state=json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(self.state,dict) or not isinstance(self.state.get('seen'),list):
                raise ValueError('Estado de notificações inválido')
        else:
            report=self.report()
            self.state={'seen':[order_key(o) for o in report.get('orders',[])], 'health':None}
            save(self.path,self.state)

    def report(self):
        path=self.root/'reports/local/live-small-paper.json'
        if not path.exists():return {}
        report=json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(report,dict) or not isinstance(report.get('orders',[]),list):
            raise ValueError('Relatório inválido')
        return report

    def poll(self):
        report=self.report()
        for order in report.get('orders',[]):
            key=order_key(order)
            if key in self.state['seen']:continue
            if self.send(order_message(order)):
                self.state['seen'].append(key)
                save(self.path,self.state)
            return
        key,summary=status(self.root)
        health=key[0]
        if self.state['health']!=health and self.send('[SIMULAÇÃO 20 USDT] '+summary):
            self.state['health']=health;save(self.path,self.state)


def start(root):
    if not(os.getenv('TELEGRAM_BOT_TOKEN') and os.getenv('TELEGRAM_CHAT_ID')):
        print('Telegram desativado: configure token e chat ID neste terminal.',flush=True)
        return None
    from bot import notify
    try:relay=Relay(root,notify)
    except (OSError,ValueError,TypeError):
        print('Telegram não iniciado: confira o estado local de notificações. Simulação preservada.',flush=True)
        return None
    stopping=threading.Event()
    def work():
        while not stopping.wait(10):
            try:relay.poll()
            except Exception:
                print('Notificação pendente: envio ou relatório indisponível; nova tentativa em 30 segundos.',flush=True)
                if stopping.wait(20):break
    threading.Thread(target=work,daemon=True,name='paper-telegram').start()
    print('Telegram habilitado para novas ordens fictícias e mudanças de estado.',flush=True)
    return stopping
