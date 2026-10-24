"""Pure v3 sizing/partial-exit research. No wallet, reservation or order IO."""
from dataclasses import dataclass
from decimal import Decimal as D
from .data import milliseconds
from .execution import floor,ceil
from .risk import Rules,RiskError,amount,decimal_policy
from .v3_research import SYMBOLS


@dataclass(frozen=True)
class Budget:
    equity:D
    free_cash:D
    exposure:D
    open_risk:D
    remaining_daily:D
    remaining_drawdown:D
    positions:int=0
    pending_entries:int=0
    same_symbol_open:bool=False
    stopped:bool=False

    @decimal_policy
    def __post_init__(self):
        for key in ('equity','free_cash','exposure','open_risk','remaining_daily','remaining_drawdown'):amount(getattr(self,key))
        if self.equity<=0 or self.free_cash+self.exposure>self.equity:raise RiskError('INVALID_BUDGET')
        if any(type(v) is not int or not 0<=v<=1000 for v in (self.positions,self.pending_entries)):raise RiskError('INVALID_COUNTS')
        if type(self.same_symbol_open) is not bool or type(self.stopped) is not bool:raise RiskError('INVALID_FLAGS')


def reject(reason):
    return dict(reason=reason,valid_research_plan=False,execution_authorized=False,approved=False)


def filters(rules,qty,price):
    return (qty>0 and rules.min_qty<=qty<=rules.max_qty and qty%rules.qty_step==0 and
            rules.min_price<=price<=rules.max_price and price>0 and price%rules.price_tick==0 and
            rules.min_notional<=qty*price<=rules.max_notional)


@decimal_policy
def plan(rules,budget,*,ask,atr,score,now_ms,quote_ms,fee=D('.001'),slip=D('.001')):
    if not isinstance(rules,Rules) or not isinstance(budget,Budget):raise RiskError('VALIDATED_INPUTS_REQUIRED')
    for timestamp in (now_ms,quote_ms):milliseconds(timestamp)
    amount(ask,positive=True);amount(atr,positive=True);amount(fee);amount(slip)
    if fee>D('.01') or slip>D('.01'):raise RiskError('COST_OUT_OF_RANGE')
    if type(score) is not int or not 0<=score<=100:raise RiskError('INVALID_SCORE')
    if rules.symbol not in SYMBOLS:return reject('UNSUPPORTED_SYMBOL')
    if budget.stopped:return reject('STOP')
    if budget.same_symbol_open:return reject('SYMBOL_ALREADY_OPEN_OR_RESERVED')
    if budget.positions+budget.pending_entries>=2:return reject('POSITION_LIMIT')
    if score<70:return reject('SCORE_TOO_LOW')
    if not 0<=now_ms-quote_ms<=2000:return reject('STALE_OR_FUTURE_QUOTE')
    if not 0<=now_ms-rules.observed_ms<=3600000:return reject('STALE_OR_FUTURE_FILTERS')
    entry=ceil(ask*(1+slip),rules.price_tick)
    if not D('.005')<=atr/entry<=D('.02'):return reject('ATR_RANGE')
    stop=floor(entry-D('1.8')*atr,rules.price_tick)
    if stop<=0:return reject('INVALID_STOP')
    stop_fill=floor(stop*(1-slip),rules.price_tick)
    unit_cost=entry*(1+fee);unit_loss=unit_cost-stop_fill*(1-fee)
    risk_budget=min(budget.equity*D('.01')*D(score)/100,
                    max(D(0),budget.equity*D('.05')-budget.open_risk),
                    budget.remaining_daily,budget.remaining_drawdown)
    exposure_room=max(D(0),budget.equity*D('.4')-budget.exposure)
    qty=floor(min(risk_budget/unit_loss,budget.free_cash/unit_cost,exposure_room/unit_cost),rules.qty_step)
    if not filters(rules,qty,entry):return reject('ENTRY_FILTER_OR_BUDGET')
    if not filters(rules,qty,stop_fill):return reject('STOP_FILTER')
    q1=floor(qty*D('.4'),rules.qty_step);q2=floor(qty*D('.35'),rules.qty_step);q3=qty-q1-q2
    exits=[]
    for fraction,q in zip(('2','3.5','5'),(q1,q2,q3)):
        target=ceil(entry+D(fraction)*atr,rules.price_tick)
        fill=floor(target*(1-slip),rules.price_tick)
        # Every possible residual leg must also be executable at the assumed
        # stop. Never round up or add capital to meet a minimum.
        if not filters(rules,q,target) or not filters(rules,q,fill) or not filters(rules,q,stop_fill):return reject('PARTIAL_EXIT_FILTER')
        exits.append(dict(quantity=q,target=target,assumed_fill=fill))
    cost=qty*unit_cost;loss=qty*unit_loss
    weighted_gain=sum(e['quantity']*e['assumed_fill']*(1-fee) for e in exits)-cost
    rr=weighted_gain/loss
    if rr<D('1.5'):return reject('NET_WEIGHTED_RR_TOO_LOW')
    return dict(reason='VALID_RESEARCH_PLAN',valid_research_plan=True,execution_authorized=False,approved=False,
                symbol=rules.symbol,quantity=str(qty),entry=str(entry),stop=str(stop),assumed_stop_fill=str(stop_fill),
                estimated_cost=str(cost),estimated_stop_loss=str(loss),risk_budget=str(risk_budget),
                net_weighted_rr=str(rr),remaining_exposure_room=str(exposure_room-cost),
                exits=[{k:str(v) for k,v in e.items()} for e in exits],
                note='Hypothetical sizing only; no reservation, orders, partial fills, trailing or guaranteed stop execution.')


def main():
    import argparse,json
    parser=argparse.ArgumentParser(description='Exemplo fictício de sizing v3; sem conexão ou ordens.')
    parser.add_argument('--example',action='store_true');args=parser.parse_args()
    if not args.example:parser.print_help();return
    now=1700000000000
    rules=Rules('SOL/USDT',now,D('.001'),D('.001'),D('100000'),D('.01'),D('.01'),D('1000000'),D('5'),D('1000000'))
    for capital in (D('20'),D('50'),D('1000')):
        b=Budget(capital,capital,D(0),D(0),capital*D('.03'),capital*D('.1'))
        result=plan(rules,b,ask=D('100'),atr=D('2'),score=100,now_ms=now,quote_ms=now)
        print(json.dumps(dict(mock_filters=True,capital=str(capital),plan=result),indent=2))


if __name__=='__main__':main()
