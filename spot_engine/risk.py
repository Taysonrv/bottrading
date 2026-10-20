"""Persistent paper risk assessments and sizing proposals; never sends orders."""
from contextlib import closing
from dataclasses import asdict, dataclass
from decimal import Decimal, ROUND_FLOOR, ROUND_CEILING, DecimalException, localcontext
from functools import wraps
import hashlib
import json
from pathlib import Path
import sqlite3
from .config import Settings
from .data import milliseconds, DataError

D=Decimal


class RiskError(ValueError):pass


def decimal_policy(function):
    @wraps(function)
    def wrapped(*args,**kwargs):
        try:
            with localcontext() as context:
                context.prec=80
                return function(*args,**kwargs)
        except DecimalException:
            raise RiskError('Cálculo financeiro inválido; proposta recusada.') from None
    return wrapped


def amount(value, *, positive=False):
    if not isinstance(value,D) or not value.is_finite() or value<0 or (positive and value==0) or abs(value)>D('1e20') or (value!=0 and value<D('1e-18')):
        raise RiskError('Valor Decimal de risco inválido.')
    return value


@dataclass(frozen=True)
class Account:
    equity: D
    free_cash: D
    open_positions: int = 0
    pending_entries: int = 0
    reserved_cash: D = D(0)

    def __post_init__(self):
        amount(self.equity);amount(self.free_cash)
        amount(self.reserved_cash)
        if self.free_cash+self.reserved_cash>self.equity:raise RiskError('Caixa excede patrimônio marcado.')
        for value in (self.open_positions,self.pending_entries):
            if type(value) is not int or not 0<=value<=1000:raise RiskError('Contagem de posições inválida.')
        if self.reserved_cash and not self.pending_entries:raise RiskError('Reserva sem entrada pendente.')
        if self.open_positions==0 and self.free_cash+self.reserved_cash!=self.equity:
            raise RiskError('Sem posição, patrimônio deve corresponder ao caixa livre.')


@dataclass(frozen=True)
class Rules:
    """Normalized LIMIT lot/price/notional constraints; not full exchange validation."""
    symbol: str
    observed_ms: int
    qty_step: D
    min_qty: D
    max_qty: D
    price_tick: D
    min_price: D
    max_price: D
    min_notional: D
    max_notional: D

    def __post_init__(self):
        try:milliseconds(self.observed_ms)
        except DataError:raise RiskError('Horário dos filtros inválido.') from None
        for name in ('qty_step','min_qty','max_qty','price_tick','max_price','max_notional'):
            amount(getattr(self,name),positive=True)
        amount(self.min_price);amount(self.min_notional)
        if self.min_qty>self.max_qty or self.min_price>self.max_price or self.min_notional>self.max_notional:
            raise RiskError('Intervalo de filtros inválido.')


@dataclass(frozen=True)
class Assessment:
    reason: str
    can_enter: bool
    drawdown: D
    daily_loss: D
    remaining_daily: D
    remaining_drawdown: D
    execution_authorized: bool = False


@dataclass(frozen=True)
class EntryPlan:
    reason: str
    quantity: D = D('0')
    entry: D | None = None
    stop: D | None = None
    take_profit: D | None = None
    estimated_cost: D = D('0')
    estimated_stop_loss: D = D('0')
    execution_authorized: bool = False


class RiskManager:
    """One-position engine. Recheck account, STOP and filters before future execution.

    SQLite transactions serialize checkpoint updates, not exchange requests.
    A proposal does NOT reserve cash or risk; execution must add reservations.
    """
    def __init__(self, root, settings, session_id='ema-spot-v1'):
        if not isinstance(settings,Settings) or settings.max_positions!=1:
            raise RiskError('Esta versão de risco suporta uma posição por vez.')
        if not isinstance(session_id,str) or not session_id or len(session_id)>100:
            raise RiskError('Identificador de sessão inválido.')
        self.root=Path(root);self.cfg=settings;self.folder=self.root/'reports/local/spot-risk'
        self.path=self.folder/'risk.sqlite';self.marker=self.folder/'initialized'
        self.identity=hashlib.sha256(json.dumps({'session':session_id,'risk_code':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'config':{k:str(v) for k,v in asdict(settings).items()}},sort_keys=True).encode()).hexdigest()

    def initialize(self, account, now_ms):
        self._validate(account,now_ms)
        if account.equity!=self.cfg.capital or account.free_cash!=account.equity or account.open_positions or account.pending_entries:
            raise RiskError('Inicialização exige capital configurado, caixa e nenhuma exposição.')
        self.folder.mkdir(parents=True,exist_ok=True)
        if self.path.exists() or self.marker.exists():raise RiskError('Sessão já inicializada ou incompleta; não reiniciada.')
        # A crash after the marker fails closed; no automatic reset of risk.
        try:
            with self.marker.open('x',encoding='ascii') as f:f.write(self.identity)
            with closing(sqlite3.connect(self.path,timeout=5)) as db:
                db.execute('PRAGMA synchronous=FULL')
                db.execute('CREATE TABLE checkpoint (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL)')
                db.execute('CREATE TABLE events (id INTEGER PRIMARY KEY, time_ms INTEGER NOT NULL, code TEXT NOT NULL)')
                state=dict(identity=self.identity,last_ms=now_ms,day=now_ms//86400000,
                           day_equity=str(account.equity),peak=str(account.equity),equity=str(account.equity),
                           daily_halted=False,drawdown_halted=False,stop_active=False)
                db.execute('INSERT INTO checkpoint VALUES(1,?)',(json.dumps(state),));db.commit()
        except (OSError,sqlite3.Error):raise RiskError('Falha ao inicializar risco; revise estado parcial, sem apagar automaticamente.') from None

    def _stopped(self):
        try:
            (self.root/'STOP').stat()
            return True
        except FileNotFoundError:
            return False
        except OSError:
            raise RiskError('Não foi possível verificar STOP; operação recusada.') from None

    def _validate(self,account,now_ms):
        if not isinstance(account,Account):raise RiskError('Snapshot de conta validado obrigatório.')
        try:milliseconds(now_ms)
        except DataError:raise RiskError('Horário de risco inválido.') from None

    def _read(self,db):
        try:
            if not self.marker.exists() or self.marker.read_text(encoding='ascii')!=self.identity:
                raise RiskError('Marcador de risco ausente ou configuração diferente.')
            row=db.execute('SELECT payload FROM checkpoint WHERE id=1').fetchone()
            state=json.loads(row[0]) if row else None
            fields={'identity','last_ms','day','day_equity','peak','equity','daily_halted','drawdown_halted','stop_active'}
            if not isinstance(state,dict) or set(state)!=fields or state['identity']!=self.identity:
                raise RiskError('Checkpoint de risco inválido ou de outra configuração.')
            milliseconds(state['last_ms'])
            if type(state['day']) is not int or state['day']!=state['last_ms']//86400000:
                raise RiskError('Dia UTC persistido inválido.')
            for key in ('daily_halted','drawdown_halted','stop_active'):
                if type(state[key]) is not bool:raise RiskError('Trava persistida inválida.')
            for key in ('day_equity','peak','equity'):
                if not isinstance(state[key],str) or len(state[key])>64:raise RiskError('Valor persistido inválido.')
                amount(D(state[key]),positive=key!='equity')
            if D(state['peak'])<max(D(state['day_equity']),D(state['equity'])):raise RiskError('Pico persistido inválido.')
            if (D(state['equity'])<=D(state['peak'])*(1-self.cfg.max_drawdown) and not state['drawdown_halted']) or (D(state['equity'])<=D(state['day_equity'])*(1-self.cfg.daily_loss_limit) and not state['daily_halted']):
                raise RiskError('Trava persistida inconsistente.')
            return state
        except (sqlite3.Error,OSError,ValueError,TypeError,DecimalException,DataError):
            raise RiskError('Checkpoint ausente, corrompido ou inconsistente; não reiniciado.') from None

    @decimal_policy
    def assess(self,account,now_ms):
        self._validate(account,now_ms)
        if not self.path.exists() or not self.marker.exists():raise RiskError('Risco não inicializado ou checkpoint perdido.')
        try:
            with closing(sqlite3.connect(self.path.resolve().as_uri()+'?mode=rw',uri=True,timeout=5)) as db:
                db.execute('PRAGMA synchronous=FULL');db.execute('BEGIN IMMEDIATE')
                try:
                    state=self._read(db)
                    if now_ms<state['last_ms']:raise RiskError('Relógio retrocedeu; checkpoint preservado.')
                    day=now_ms//86400000
                    old_daily=state['daily_halted'];old_dd=state['drawdown_halted'];old_stop=state['stop_active']
                    if day!=state['day']:
                        if account.equity==0:raise RiskError('Patrimônio zero; revisão obrigatória.')
                        state.update(day=day,day_equity=str(account.equity),daily_halted=False);old_daily=False
                    peak=max(D(state['peak']),account.equity);base=D(state['day_equity'])
                    dd=max(D(0),1-account.equity/peak);daily=max(D(0),1-account.equity/base)
                    state.update(peak=str(peak),equity=str(account.equity),last_ms=now_ms,
                                 daily_halted=state['daily_halted'] or daily>=self.cfg.daily_loss_limit,
                                 drawdown_halted=state['drawdown_halted'] or dd>=self.cfg.max_drawdown,
                                 stop_active=self._stopped())
                    for active,previous,code in ((state['daily_halted'],old_daily,'DAILY_LOSS'),(state['drawdown_halted'],old_dd,'DRAWDOWN'),(state['stop_active'],old_stop,'STOP')):
                        if active and not previous:db.execute('INSERT INTO events(time_ms,code) VALUES(?,?)',(now_ms,code))
                    db.execute('UPDATE checkpoint SET payload=? WHERE id=1',(json.dumps(state),));db.commit()
                except Exception:
                    db.rollback();raise
        except sqlite3.Error:raise RiskError('Estado de risco indisponível; entradas recusadas.') from None
        reason='STOP' if state['stop_active'] else 'DRAWDOWN' if state['drawdown_halted'] else 'DAILY_LOSS' if state['daily_halted'] else 'POSITION_LIMIT' if account.open_positions+account.pending_entries>=1 else 'NO_CASH' if account.free_cash==0 else 'OK'
        return Assessment(reason,reason=='OK',dd,daily,max(D(0),account.equity-base*(1-self.cfg.daily_loss_limit)),max(D(0),account.equity-peak*(1-self.cfg.max_drawdown)))

    @decimal_policy
    def plan_entry(self,account,price,rules,now_ms,quote_ms):
        amount(price,positive=True)
        try:milliseconds(quote_ms)
        except DataError:raise RiskError('Horário da cotação inválido.') from None
        self._validate(account,now_ms)
        if not isinstance(rules,Rules) or rules.symbol!=self.cfg.symbol:raise RiskError('Filtros não correspondem ao par.')
        if not 0<=now_ms-quote_ms<=5000:return EntryPlan('STALE_QUOTE')
        if not 0<=now_ms-rules.observed_ms<=3600000:return EntryPlan('STALE_RULES')
        assessment=self.assess(account,now_ms)
        if not assessment.can_enter:return EntryPlan(assessment.reason)
        cfg=self.cfg
        floor=lambda v,s:(v/s).to_integral_value(rounding=ROUND_FLOOR)*s
        ceil=lambda v,s:(v/s).to_integral_value(rounding=ROUND_CEILING)*s
        entry=ceil(price*(1+cfg.slippage_rate),rules.price_tick)
        stop=floor(entry*(1-cfg.stop_loss_fraction),rules.price_tick)
        take=ceil(entry*(1+cfg.take_profit_fraction),rules.price_tick)
        if not rules.min_price<=stop<entry<take<=rules.max_price or stop<=0:return EntryPlan('PRICE_FILTER')
        unit_cost=entry*(1+cfg.fee_rate)
        unit_loss=unit_cost-stop*(1-cfg.slippage_rate)*(1-cfg.fee_rate)
        budget=min(account.equity*cfg.risk_per_trade,assessment.remaining_daily,assessment.remaining_drawdown)
        quantity=floor(min(budget/unit_loss,min(account.free_cash,cfg.max_order_notional)/unit_cost,rules.max_notional/entry,rules.max_qty),rules.qty_step)
        if quantity<rules.min_qty or quantity==0 or quantity*entry<rules.min_notional:return EntryPlan('MINIMUM_OR_LOT')
        cost=quantity*unit_cost;loss=quantity*unit_loss
        if cost>min(account.free_cash,cfg.max_order_notional) or loss>budget:raise RiskError('Arredondamento excede orçamento; proposta recusada.')
        if self._stopped():return EntryPlan('STOP')
        return EntryPlan('CANDIDATE_ONLY',quantity,entry,stop,take,cost,loss)

    def assess_reduction(self,account,now_ms,quantity,held_quantity):
        amount(quantity,positive=True);amount(held_quantity,positive=True)
        assessment=self.assess(account,now_ms)
        if self._stopped():return 'STOP'
        if account.open_positions==0 or quantity>held_quantity:return 'INVALID_INVENTORY'
        # Daily/DD limits stop NEW risk, not protective reductions; filters still required.
        return 'REDUCTION_CANDIDATE_ONLY'

    @decimal_policy
    def events(self):
        if not self.path.exists() or not self.marker.exists():raise RiskError('Checkpoint ausente.')
        try:
            with closing(sqlite3.connect(self.path.resolve().as_uri()+'?mode=rw',uri=True,timeout=5)) as db:
                self._read(db)
                return tuple(db.execute('SELECT id,time_ms,code FROM events ORDER BY id'))
        except sqlite3.Error:raise RiskError('Eventos de risco indisponíveis.') from None
