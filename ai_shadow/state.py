import math
import statistics
from .contracts import numeric,fields


def snapshot(book,history,account,cutoff):
    fields(book,('symbol','bid','ask','bid_qty','ask_qty','received_at','event_at','sequence','continuous'))
    numeric(cutoff,0)
    if book['symbol'] not in ('BTCUSDT','ETHUSDT'):raise ValueError('Par não autorizado neste observador')
    if book['continuous'] is not True:raise ValueError('Coleta descontínua')
    if isinstance(book['sequence'],bool) or not isinstance(book['sequence'],int) or book['sequence']<0:raise ValueError('Sequência inválida')
    received=numeric(book['received_at'],0)
    if not 0<=cutoff-received<=5:raise ValueError('Book futuro ou antigo')
    if book['event_at'] is not None:
        event=numeric(book['event_at'],0)
        if not 0<=cutoff-event<=5 or event>received:raise ValueError('Horário de evento inválido')
    for key in ('bid','ask','bid_qty','ask_qty'):numeric(book[key],minimum=1e-300)
    if book['ask']<book['bid']:raise ValueError('Book cruzado')
    if not isinstance(history,list) or len(history)!=61:raise ValueError('Exige 61 observações de minuto')
    for row in history:
        fields(row,('time','received_at','close'));numeric(row['time'],0);numeric(row['received_at'],0);numeric(row['close'],1e-300)
        if not row['time']<=row['received_at']<=cutoff:raise ValueError('Observação futura ou recebida após cutoff')
    if cutoff-history[-1]['time']>60 or any(b['time']-a['time']!=60 for a,b in zip(history,history[1:])):raise ValueError('Lacuna ou histórico antigo')
    for key in ('equity','cash','inventory_fraction'):numeric(account.get(key),0)
    if account['equity']<=0 or account['cash']>account['equity']+1e-8:raise ValueError('Conta inconsistente')
    numeric(account['inventory_fraction'],0,1)
    mid=book['bid']+(book['ask']-book['bid'])/2
    size_scale=max(book['bid_qty'],book['ask_qty'])
    bq,aq=book['bid_qty']/size_scale,book['ask_qty']/size_scale
    returns=[math.log(b['close'])-math.log(a['close']) for a,b in zip(history,history[1:])]
    return dict(version='state-v1',symbol=book['symbol'],cutoff=cutoff,received_at=received,event_at=book['event_at'],
      sequence=book['sequence'],mid=mid,spread=(book['ask']-book['bid'])/mid,
      imbalance_l1=(bq-aq)/(bq+aq),
      volatility=statistics.pstdev(returns),inventory_fraction=account['inventory_fraction'],
      token_count_verified=False,book_type='level_1',mode='offline_fixture')
