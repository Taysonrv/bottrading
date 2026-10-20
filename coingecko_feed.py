"""Optional aggregated USD context. Never used for execution or order signals."""
import datetime as dt
import json
import math
import os
from pathlib import Path
import threading
import time
import urllib.request
from paper_lab import save

COINS={'bitcoin':'BTC','ethereum':'ETH','solana':'SOL','dogecoin':'DOGE'}
INTERVAL=900


def fetch(key):
    url='https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&ids='+','.join(COINS)+'&sparkline=false'
    request=urllib.request.Request(url,headers={'x-cg-demo-api-key':key,'Accept':'application/json'})
    with urllib.request.urlopen(request,timeout=15) as response:return json.load(response)


def normalize(raw):
    if not isinstance(raw,list):raise ValueError('Resposta inválida')
    result=[];seen=set()
    for row in raw:
        identity=row.get('id')
        if identity not in COINS or identity in seen:raise ValueError('Ativo inválido ou duplicado')
        seen.add(identity)
        def number(name,positive=False):
            value=row.get(name)
            if value is None and not positive:return None
            if isinstance(value,bool) or not isinstance(value,(float,int)) or not math.isfinite(value) or positive and value<=0:
                raise ValueError('Valor inválido')
            return value
        price=number('current_price',True)
        volume=number('total_volume');cap=number('market_cap')
        if any(v is not None and v<0 for v in (volume,cap)):raise ValueError('Valor negativo')
        stamp=dt.datetime.fromisoformat(row['last_updated'].replace('Z','+00:00'))
        if stamp.tzinfo is None:raise ValueError('Horário sem fuso')
        result.append(dict(id=identity,symbol=COINS[identity],price_usd=price,volume_usd=volume,market_cap_usd=cap,
                           change_24h=number('price_change_percentage_24h'),provider_updated=stamp.timestamp()))
    if not result:raise ValueError('Sem dados')
    return result


def update(root,key,get=fetch,now=None):
    now=time.time() if now is None else now
    path=Path(root)/'reports/local/coingecko-context.json'
    try:state=json.loads(path.read_text(encoding='utf-8'))
    except (OSError,ValueError):state={}
    if not isinstance(state,dict):state={}
    if not key:
        state.update(status='disabled',message='Configure COINGECKO_DEMO_API_KEY no terminal para habilitar.',source='CoinGecko',currency='USD')
        save(path,state);return state
    last=state.get('attempted',0)
    if isinstance(last,(int,float)) and 0<=now-last<INTERVAL:return state
    state.update(attempted=now,source='CoinGecko',currency='USD',interval_seconds=INTERVAL)
    # Persist attempt before network access, so restarting does not bypass throttling.
    save(path,state)
    try:
        rows=normalize(get(key))
        if any(r['provider_updated']>now+120 for r in rows):raise ValueError('Horário futuro')
        state.update(rows=rows,updated=time.time() if now is None else now,status='ok',message='Contexto agregado; não é preço executável.')
    except Exception:
        state.update(status='error',message='Consulta falhou ou retornou dados inválidos. Dados anteriores, se houver, foram preservados.')
    save(path,state);return state


def start(root):
    key=os.getenv('COINGECKO_DEMO_API_KEY')
    if not key:
        update(root,None)
        print('CoinGecko opcional desativada: configure COINGECKO_DEMO_API_KEY.',flush=True)
        return None
    stop=threading.Event()
    def work():
        while not stop.is_set():
            try:update(root,key)
            except Exception:print('Contexto CoinGecko indisponível; trading não alterado.',flush=True)
            if stop.wait(INTERVAL):break
    threading.Thread(target=work,daemon=True,name='coingecko-context').start()
    return stop


if __name__=='__main__':
    state=update(Path(__file__).resolve().parent,os.getenv('COINGECKO_DEMO_API_KEY'))
    print(state.get('message','Contexto consultado.'))
