"""Bounded offline replay of explicit fixtures; no WebSocket or HTTP transport."""
from copy import deepcopy
from .contracts import fields,numeric


class ReplayCollector:
    def __init__(self):self.books=[]
    def accept(self,book):
        fields(book,('symbol','bid','ask','bid_qty','ask_qty','received_at','event_at','sequence','continuous'))
        numeric(book['received_at'],0)
        if isinstance(book['sequence'],bool) or not isinstance(book['sequence'],int) or book['sequence']<0:raise ValueError('Sequência inválida')
        if self.books:
            last=self.books[-1]
            if book['symbol']!=last['symbol'] or book['sequence']<=last['sequence'] or book['received_at']<last['received_at']:
                raise ValueError('Replay fora da sequência')
        self.books.append(deepcopy(book));self.books=self.books[-1024:]
    def latest(self,cutoff):
        numeric(cutoff,0)
        valid=[b for b in self.books if b['received_at']<=cutoff]
        if not valid:raise ValueError('Sem evento recebido até cutoff')
        return deepcopy(valid[-1])
