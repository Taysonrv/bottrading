"""Transactional PAPER broker. No exchange adapter, keys, network or live mode."""
from contextlib import closing, contextmanager
from dataclasses import asdict
from decimal import Decimal as D, ROUND_FLOOR, ROUND_CEILING
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from .data import milliseconds, DataError
from .risk import Account, Rules, RiskManager, RiskError, amount, decimal_policy


class ExecutionError(ValueError):pass


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,default=str).encode()).hexdigest()


def floor(value,step):return (value/step).to_integral_value(rounding=ROUND_FLOOR)*step

def ceil(value,step):return (value/step).to_integral_value(rounding=ROUND_CEILING)*step


class PaperBroker:
    """Serialized paper reservations/fills. Quotes and liquidity are supplied externally.

    Replaying an identical ID returns its stored result, never another fill.
    Protective stops are synthetic, require a running process and do not cap loss.
    """
    def __init__(self,root,settings,control_root=None):
        self.root=Path(root);self.cfg=settings;self.risk=RiskManager(root,settings,control_root=control_root)
        self.folder=self.root/'reports/local/spot-execution'
        self.path=self.folder/'paper.sqlite';self.marker=self.folder/'initialized'
        self.identity=digest({'risk':self.risk.identity,'execution':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})

    @decimal_policy
    def initialize(self,now_ms):
        self._time(now_ms);self.folder.mkdir(parents=True,exist_ok=True)
        if self.path.exists() or self.marker.exists():raise ExecutionError('Execução já inicializada ou incompleta; não reiniciada.')
        try:
            with self.marker.open('x',encoding='ascii') as f:f.write(self.identity)
            self.risk.initialize(Account(self.cfg.capital,self.cfg.capital),now_ms)
            with closing(sqlite3.connect(self.path,timeout=5)) as db:
                db.execute('PRAGMA synchronous=FULL')
                db.execute('CREATE TABLE ledger (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL)')
                s=dict(identity=self.identity,cash=str(self.cfg.capital),units='0',cost='0',realized='0',fees='0',reserved='0',
                       active=None,protection=None,last_ms=now_ms,last_quote_ms=-1,orders={},events={},fills=[])
                db.execute('INSERT INTO ledger VALUES(1,?)',(json.dumps(s),));db.commit()
        except (OSError,sqlite3.Error):raise ExecutionError('Inicialização incompleta; estado preservado para revisão.') from None

    def _time(self,value):
        try:return milliseconds(value)
        except DataError:raise ExecutionError('Timestamp de execução inválido.') from None

    def _id(self,value):
        if not isinstance(value,str) or value.startswith('protect_') or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',value):raise ExecutionError('ID inválido.')

    def _quote(self,bid,ask,quote_ms,now_ms,rules):
        self._time(quote_ms);self._time(now_ms);amount(bid,positive=True);amount(ask,positive=True)
        if bid>ask or not 0<=now_ms-quote_ms<=5000:raise ExecutionError('Cotação antiga, futura ou cruzada.')
        if not isinstance(rules,Rules) or rules.symbol!=self.cfg.symbol or not 0<=now_ms-rules.observed_ms<=3600000:
            raise ExecutionError('Filtros ausentes, antigos ou de outro par.')

    def _load(self,db):
        try:
            if self.marker.read_text(encoding='ascii')!=self.identity:raise ExecutionError('Identidade de execução incompatível.')
            row=db.execute('SELECT payload FROM ledger WHERE id=1').fetchone();s=json.loads(row[0])
            if s['identity']!=self.identity or not isinstance(s['orders'],dict) or not isinstance(s['events'],dict) or not isinstance(s['fills'],list):
                raise ExecutionError('Estado de execução inválido.')
            cash=self.cfg.capital;units=cost=realized=fees=D(0)
            for f in s['fills']:
                q=D(f['quantity']);p=D(f['price']);fee=D(f['fee'])
                amount(q,positive=True);amount(p,positive=True);amount(fee)
                if fee!=q*p*self.cfg.fee_rate:raise ExecutionError('Taxa do fill divergente.')
                fees+=fee
                if f['side']=='BUY':cash-=q*p+fee;units+=q;cost+=q*p+fee
                elif f['side']=='SELL' and 0<q<=units:
                    removed=cost if q==units else cost*q/units
                    cash+=q*p-fee;realized+=q*p-fee-removed;units-=q;cost-=removed
                else:raise ExecutionError('Fill inválido ou venda sem inventário.')
            if any(D(s[k])!=v for k,v in dict(cash=cash,units=units,cost=cost,realized=realized,fees=fees).items()):
                raise ExecutionError('Reconciliação do ledger divergente.')
            if min(cash,units,cost,D(s['reserved']))<0 or D(s['reserved'])>cash:raise ExecutionError('Caixa, inventário ou reserva inválidos.')
            active=s['orders'].get(s['active']) if s['active'] else None
            if s['active'] and (not active or active['status'] not in ('NEW','PARTIAL')):raise ExecutionError('Ordem ativa inconsistente.')
            reserve=(D(active['quantity'])-D(active['filled']))*D(active['limit'])*(1+self.cfg.fee_rate) if active and active['side']=='BUY' else D(0)
            if reserve!=D(s['reserved']):raise ExecutionError('Reserva divergente.')
            if bool(units)!=bool(s['protection']):raise ExecutionError('Inventário sem proteção registrada.')
            if units and not 0<D(s['protection']['stop'])<D(s['protection']['take']):raise ExecutionError('Proteção inválida.')
            self._time(s['last_ms'])
            return s
        except (KeyError,TypeError,ValueError,OSError,sqlite3.Error):
            raise ExecutionError('Ledger ausente, corrompido ou não reconciliado; não reiniciado.') from None

    @contextmanager
    def _transaction(self):
        if not self.path.exists() or not self.marker.exists():raise ExecutionError('Execução não inicializada ou checkpoint perdido.')
        try:
            with closing(sqlite3.connect(self.path.resolve().as_uri()+'?mode=rw',uri=True,timeout=5)) as db:
                db.execute('PRAGMA synchronous=FULL');db.execute('BEGIN IMMEDIATE')
                try:
                    s=self._load(db);yield s
                    if len(s['events'])>100000 or len(s['orders'])>10000:raise ExecutionError('Limite do protótipo atingido; preserve e revise o histórico.')
                    db.execute('UPDATE ledger SET payload=? WHERE id=1',(json.dumps(s,default=str),));db.commit()
                except Exception:db.rollback();raise
        except sqlite3.Error:raise ExecutionError('Ledger indisponível; nenhuma operação executada.') from None

    def _account(self,s,bid,rules):
        liquidation=floor(bid*(1-self.cfg.slippage_rate),rules.price_tick)*(1-self.cfg.fee_rate)
        cash=D(s['cash']);reserved=D(s['reserved']);units=D(s['units'])
        active=s['orders'].get(s['active'])
        return Account(cash+units*liquidation,cash-reserved,int(units>0),int(bool(active and active['side']=='BUY')),reserved)

    def _clock(self,s,now_ms):
        if now_ms<s['last_ms']:raise ExecutionError('Relógio retrocedeu; estado preservado.')
        s['last_ms']=now_ms

    def _cancel(self,s):
        if s['active']:
            s['orders'][s['active']]['status']='CANCELED';s['active']=None;s['reserved']='0'

    def _sell(self,s,client_id,rules,bid,quote_ms,now_ms,reason):
        if self.risk._stopped():raise ExecutionError('STOP antes da saída simulada.')
        self._cancel(s)
        price=floor(bid*(1-self.cfg.slippage_rate),rules.price_tick)
        q=floor(min(D(s['units']),rules.max_qty,rules.max_notional/price),rules.qty_step) if price>0 else D(0)
        if q<rules.min_qty or q==0 or price<rules.min_price or price>rules.max_price or q*price<rules.min_notional:
            return {'reason':'EXIT_MINIMUM_OR_FILTER','order':None}
        s['orders'][client_id]=dict(side='SELL',quantity=str(q),filled='0',limit=str(price),status='NEW',
                                   created_ms=now_ms,quote_ms=quote_ms,reason=reason)
        s['active']=client_id
        return {'reason':reason,'order':client_id}

    @decimal_policy
    def submit_entry(self,client_id,*,bid,ask,quote_ms,now_ms,rules):
        self._id(client_id);self._time(now_ms)
        if not isinstance(rules,Rules):raise ExecutionError('Filtros validados obrigatórios.')
        request=digest(['ENTRY',bid,ask,quote_ms,asdict(rules)])
        with self._transaction() as s:
            old=s['orders'].get(client_id)
            if old:
                if old.get('request')!=request:raise ExecutionError('ID já usado para outra solicitação.')
                return dict(old)
            self._quote(bid,ask,quote_ms,now_ms,rules)
            self._clock(s,now_ms)
            plan=self.risk.plan_entry(self._account(s,bid,rules),ask,rules,now_ms,quote_ms)
            o=dict(request=request,side='BUY',quantity=str(plan.quantity),filled='0',limit=str(plan.entry or 0),
                   stop=str(plan.stop or 0),take=str(plan.take_profit or 0),created_ms=now_ms,quote_ms=quote_ms,
                   status='NEW' if plan.reason=='CANDIDATE_ONLY' else 'REJECTED',reason=plan.reason)
            s['orders'][client_id]=o
            if o['status']=='NEW':
                if self.risk._stopped():raise ExecutionError('STOP antes da reserva; entrada cancelada.')
                s['active']=client_id;s['reserved']=str(plan.estimated_cost)
            return dict(o)

    @decimal_policy
    def submit_exit(self,client_id,*,bid,ask,quote_ms,now_ms,rules):
        self._id(client_id);self._time(now_ms)
        if not isinstance(rules,Rules):raise ExecutionError('Filtros validados obrigatórios.')
        request=digest(['EXIT',bid,ask,quote_ms,asdict(rules)])
        with self._transaction() as s:
            old=s['orders'].get(client_id)
            if old:
                if old.get('request')!=request:raise ExecutionError('ID já usado para outra solicitação.')
                return dict(old)
            self._quote(bid,ask,quote_ms,now_ms,rules)
            self._clock(s,now_ms)
            if self.risk._stopped():raise ExecutionError('STOP impede saída; posição permanece exposta.')
            active=s['orders'].get(s['active'])
            if active and active['side']=='SELL':raise ExecutionError('Já existe saída pendente.')
            a=self._account(s,bid,rules)
            if not D(s['units']):raise ExecutionError('Não há inventário para vender.')
            if self.risk.assess_reduction(a,now_ms,D(s['units']),D(s['units']))!='REDUCTION_CANDIDATE_ONLY':
                raise ExecutionError('Redução recusada pelo risco.')
            result=self._sell(s,client_id,rules,bid,quote_ms,now_ms,'SIGNAL_EXIT')
            if result['order'] is None:
                s['orders'][client_id]=dict(request=request,side='SELL',quantity='0',filled='0',limit='0',status='REJECTED',reason=result['reason'],created_ms=now_ms,quote_ms=quote_ms)
                return dict(s['orders'][client_id])
            s['orders'][client_id]['request']=request
            return dict(s['orders'][client_id])

    @decimal_policy
    def cancel(self,client_id,now_ms):
        self._time(now_ms);self._id(client_id)
        with self._transaction() as s:
            self._clock(s,now_ms)
            if client_id not in s['orders']:raise ExecutionError('Ordem desconhecida.')
            if s['active']==client_id:self._cancel(s)
            return dict(s['orders'][client_id])

    @decimal_policy
    def process_quote(self,event_id,*,bid,ask,available_quantity,quote_ms,now_ms,rules):
        self._id(event_id);self._time(now_ms);amount(available_quantity)
        if not isinstance(rules,Rules):raise ExecutionError('Filtros validados obrigatórios.')
        request=digest([bid,ask,available_quantity,quote_ms,asdict(rules)])
        with self._transaction() as s:
            if event_id in s['events']:
                event=s['events'][event_id]
                if event['request']!=request:raise ExecutionError('Evento repetido com conteúdo diferente.')
                return dict(event['result'])
            self._quote(bid,ask,quote_ms,now_ms,rules)
            self._clock(s,now_ms)
            if quote_ms<=s['last_quote_ms']:raise ExecutionError('Evento fora de ordem; nenhum preenchimento.')
            s['last_quote_ms']=quote_ms
            assessment=self.risk.assess(self._account(s,bid,rules),now_ms)
            result={'reason':'NO_FILL','filled':'0'}
            active=s['orders'].get(s['active'])
            if self.risk._stopped():
                self._cancel(s);result['reason']='STOP_EXPOSED' if D(s['units']) else 'STOP'
            else:
                if assessment.reason in ('DAILY_LOSS','DRAWDOWN') and active and active['side']=='BUY':self._cancel(s)
                protection=s['protection']
                active=s['orders'].get(s['active'])
                if protection and not (active and active['side']=='SELL') and (bid<=D(protection['stop']) or bid>=D(protection['take'])):
                    code='PROTECTIVE_STOP' if bid<=D(protection['stop']) else 'TAKE_PROFIT'
                    result=self._sell(s,'protect_'+str(len(s['orders'])),rules,bid,quote_ms,now_ms,code)
                active=s['orders'].get(s['active'])
                if active and active['side']=='BUY' and bid<=D(active['stop']):
                    self._cancel(s);active=None;result={'reason':'ENTRY_BELOW_STOP','filled':'0'}
                if active and quote_ms>active['quote_ms'] and quote_ms>=active['created_ms']+self.cfg.latency_ms:
                    q=floor(min(available_quantity,D(active['quantity'])-D(active['filled'])),rules.qty_step)
                    price=ceil(ask*(1+self.cfg.slippage_rate),rules.price_tick) if active['side']=='BUY' else floor(bid*(1-self.cfg.slippage_rate),rules.price_tick)
                    if q>0 and price>0 and rules.min_price<=price<=rules.max_price and (active['side']=='SELL' or price<=D(active['limit'])):
                        if self.risk._stopped():raise ExecutionError('STOP imediatamente antes do fill; estado preservado.')
                        fee=q*price*self.cfg.fee_rate
                        amount(price,positive=True);amount(fee)
                        if active['side']=='BUY':
                            cost=q*price+fee
                            if cost>D(s['reserved']):raise ExecutionError('Fill excede reserva.')
                            s['cash']=str(D(s['cash'])-cost);s['units']=str(D(s['units'])+q);s['cost']=str(D(s['cost'])+cost)
                            s['protection']={'stop':active['stop'],'take':active['take']}
                        else:
                            units=D(s['units']);cost=D(s['cost']);removed=cost if q==units else cost*q/units
                            if q>units:raise ExecutionError('Fill sem inventário.')
                            s['cash']=str(D(s['cash'])+q*price-fee);s['units']=str(units-q);s['cost']=str(cost-removed)
                            s['realized']=str(D(s['realized'])+q*price-fee-removed)
                            if q==units:s['protection']=None
                        s['fees']=str(D(s['fees'])+fee)
                        s['fills'].append(dict(event=event_id,order=s['active'],side=active['side'],quantity=str(q),price=str(price),fee=str(fee),time_ms=now_ms))
                        active['filled']=str(D(active['filled'])+q)
                        active['status']='FILLED' if D(active['filled'])==D(active['quantity']) else 'PARTIAL'
                        s['reserved']=str((D(active['quantity'])-D(active['filled']))*D(active['limit'])*(1+self.cfg.fee_rate)) if active['side']=='BUY' else '0'
                        if active['status']=='FILLED':s['active']=None
                        result={'reason':'FILLED' if active['status']=='FILLED' else 'PARTIAL','filled':str(q)}
                # Preserve loss latches after fees/fills even if no further tick arrives.
                post=self.risk.assess(self._account(s,bid,rules),now_ms)
                active=s['orders'].get(s['active'])
                if post.reason in ('DAILY_LOSS','DRAWDOWN','STOP') and active and active['side']=='BUY':self._cancel(s)
            s['events'][event_id]={'request':request,'result':result}
            return dict(result)

    @decimal_policy
    def snapshot(self):
        with self._transaction() as s:return json.loads(json.dumps(s))
