"""Fixture adapter ONLY. There is no HTTP transport in this build."""
from .contracts import decision,numeric


class FixtureClient:
    def __init__(self,response=None,latency=0):self.response=response;self.latency=latency
    def evaluate(self,snapshot):
        if self.response is None:raise ValueError('Provedor real não implementado; use fixture explícita')
        numeric(self.latency,0)
        if self.latency>2:raise TimeoutError('Fixture simula resposta tardia')
        return decision(self.response)


class CircuitBreaker:
    def __init__(self,journal):self.journal=journal
    def state(self,now):
        numeric(now,0)
        s=self.journal.get('circuit') or dict(failures=0,open_until=0,last_at=now)
        if now<s['last_at']:raise ValueError('Relógio retrocedeu')
        s['last_at']=now
        return s
    def allowed(self,now):
        s=self.state(now);self.journal.put('circuit',s)
        return now>=s['open_until']
    def failure(self,now):
        s=self.state(now);s['failures']+=1
        if s['failures']>=3:s['open_until']=now+60
        self.journal.put('circuit',s)
    def success(self,now):
        s=self.state(now)
        if now<s['open_until']:raise ValueError('Circuito aberto')
        s.update(failures=0,open_until=0);self.journal.put('circuit',s)
