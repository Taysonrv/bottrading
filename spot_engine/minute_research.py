"""Isolated 1m breakout experiment. No paper/live broker or running-state writes."""
from collections import deque
from dataclasses import dataclass
from decimal import Decimal as D, ROUND_FLOOR
import hashlib
import json
import math
from pathlib import Path
import statistics
import uuid
from .data import Candle, PublicBinance, retry, interval
from .main import normalized_rules, save
from .scanner import SYMBOLS

M=60000
WARMUP=2250  # 150 complete 15m candles, three times the slow EMA period.


def collect(client,symbol,start,end):
    """Raw public klines, contiguous UTC closed minutes only, max 50k bars."""
    interval(symbol,'15m')
    if start%M or end%M or not 0<end-start<=50000*M:
        raise ValueError('Invalid minute range')
    result=[]
    while start+len(result)*M<end:
        cursor=start+len(result)*M
        page=retry(lambda:client._call(client._exchange.public_get_klines,
                   {'symbol':symbol.replace('/',''),'interval':'1m','startTime':cursor,'endTime':end-1,'limit':1000}))
        if not page: raise ValueError('Incomplete minute history')
        added=0
        for row in page:
            if type(row[0]) is not int: raise ValueError('Invalid candle time')
            if row[0]>=end: continue
            if row[0]!=start+len(result)*M: raise ValueError('Gap or duplicate')
            c=Candle(row[0],*[float(v) for v in row[1:6]])
            result.append(c);added+=1
        if not added: raise ValueError('No progress')
    return tuple(result)


@dataclass(frozen=True)
class Intent:
    enter: bool
    reason: str
    stop_fraction: float=0


class Breakout:
    """Prior 20 highs, volume >=1.5x prior20; completed15m EMA20>50 filter.

    Stop=max(1.5*ATR14,0.3%); target=2*stop. Reject stop>2%.
    All thresholds fixed before observing experiment results.
    """
    def __init__(self):
        self.recent=deque(maxlen=20);self.last=None;self.atr=None
        self.trs=[];self.fast=None;self.slow=None;self.bars15=0;self.group=[]

    def update(self,c):
        if c.open_ms%M or (self.last and c.open_ms!=self.last.open_ms+M):
            raise ValueError('Non-contiguous minutes')
        tr=c.high-c.low if self.last is None else max(c.high-c.low,abs(c.high-self.last.close),abs(c.low-self.last.close))
        if self.atr is None:
            self.trs.append(tr)
            if len(self.trs)==14:self.atr=statistics.mean(self.trs)
        else:self.atr=(self.atr*13+tr)/14
        # A partial initial UTC15m block cannot seed a trend indicator.
        if c.open_ms%(15*M)==0:self.group=[]
        self.group.append(c)
        if (c.open_ms+M)%(15*M)==0 and len(self.group)==15:
            close=c.close
            self.fast=close if self.fast is None else self.fast+2/21*(close-self.fast)
            self.slow=close if self.slow is None else self.slow+2/51*(close-self.slow)
            self.bars15+=1
            self.group=[]
        answer=Intent(False,'WARMUP')
        if self.bars15>=150 and len(self.recent)==20 and self.atr is not None:
            stop=max(.003,1.5*self.atr/c.close)
            if self.fast<=self.slow or c.close<=self.slow:answer=Intent(False,'TREND_FILTER')
            elif c.close<=max(p.high for p in self.recent):answer=Intent(False,'NO_BREAKOUT')
            elif c.volume<1.5*statistics.mean(p.volume for p in self.recent):answer=Intent(False,'VOLUME_FILTER')
            elif stop>.02:answer=Intent(False,'VOLATILITY_FILTER')
            else:answer=Intent(True,'BREAKOUT_VOLUME',stop)
        self.recent.append(c);self.last=c
        return answer


def simulate(bars,intents,start,end,rules,*,fee=.001,slip=.001,step_ms=M,exit_mode='fixed',atrs=None,journal=False):
    """Independent20USDT trial; next-open fills, stop first, present-day filters.

    Exit below current min notional cannot be filled: keep inventory marked.
    Stop/target synthetic, fees in quote assumed; no queue/latency reproduction.
    """
    if exit_mode not in ('fixed','trailing') or (exit_mode=='trailing' and (atrs is None or len(atrs)!=len(bars))):raise ValueError('Invalid exit policy')
    ledger=[];stop_changes=[];entry_record=None
    cash=20.;qty=cost=stop=target=0.;peak=20.;dd=0.;dailybase=20.;day=None
    halted=dailyhalt=False;fees=0.;pnls=[];returns=[];previous=20.;blocked=0
    def sell(raw_price,reason,index):
        nonlocal cash,qty,cost,fees,blocked,entry_record
        price=raw_price*(1-slip)
        if qty*price<float(rules.min_notional):blocked+=1;return
        value=qty*price;charge=value*fee
        net=value-charge-cost
        pnls.append(net);cash+=value-charge;fees+=charge
        if journal:
            gross=qty*(raw_price-entry_record['raw_entry'])
            slippage=qty*((entry_record['entry']-entry_record['raw_entry'])+(raw_price-price))
            total_fees=entry_record['entry_fee']+charge
            if not math.isclose(net,gross-slippage-total_fees,abs_tol=1e-10):raise ValueError('PnL reconciliation failed')
            ledger.append(dict(**entry_record,exit_candle_open_ms=bars[index].open_ms,exit_reference=raw_price,
                               exit_price=price,exit_reason=reason,quantity=qty,gross_pnl=gross,
                               slippage_cost=slippage,fees=total_fees,net_pnl=net))
        qty=cost=0.;entry_record=None
    for i in range(start,end):
        b=bars[i];intent=intents[i-1]
        opening=cash+qty*b.open*(1-slip)*(1-fee)
        if day!=b.open_ms//86400000:day=b.open_ms//86400000;dailybase=opening;dailyhalt=False
        peak=max(peak,opening)
        dailyhalt|=opening<=dailybase*.97
        halted|=opening<=peak*.90
        if not qty and intent.enter and not halted and not dailyhalt:
            entry=b.open*(1+slip)
            stop=entry*(1-intent.stop_fraction);target=entry*(1+2*intent.stop_fraction)
            riskunit=entry*(1+fee)-stop*(1-slip)*(1-fee)
            budget=min(cash,6.,max(0,opening-dailybase*.97)/riskunit*entry*(1+fee),
                       max(0,opening-peak*.90)/riskunit*entry*(1+fee),opening*.01/riskunit*entry*(1+fee))
            unit=(D(str(budget/(entry*(1+fee))))/rules.qty_step).to_integral_value(rounding=ROUND_FLOOR)*rules.qty_step
            q=float(unit)
            if (not float(rules.min_qty)<=q<=float(rules.max_qty) or q*stop*(1-slip)<float(rules.min_notional)
                    or q*entry>float(rules.max_notional) or 2*intent.stop_fraction<=2*(fee+slip)):
                blocked+=1
            else:
                qty=q;cost=q*entry*(1+fee);cash-=cost;fees+=q*entry*fee
                entry_record=dict(signal_close_ms=bars[i-1].open_ms+step_ms,entry_candle_open_ms=b.open_ms,
                                  entry_reason=intent.reason,raw_entry=b.open,entry=entry,entry_fee=q*entry*fee,
                                  initial_stop=stop,target=target if exit_mode=='fixed' else None)
        if qty:
            if b.low<=stop:sell(min(b.open,stop),'STOP_GAP' if b.open<stop else 'STOP',i)
            elif exit_mode=='fixed' and b.high>=target:sell(target,'TARGET',i)
            # The close-derived stop is effective from the NEXT candle only.
            if qty and exit_mode=='trailing':
                if atrs[i] is not None and atrs[i]>0:
                    new_stop=max(stop,b.close-3*atrs[i])
                    if new_stop>stop:
                        if journal:stop_changes.append(dict(decision_close_ms=b.open_ms+step_ms,effective_from_ms=b.open_ms+step_ms,old=stop,new=new_stop))
                        stop=new_stop
        equity=cash+qty*b.close*(1-slip)*(1-fee)
        peak=max(peak,equity);dd=max(dd,1-equity/peak)
        halted|=dd>=.10;dailyhalt|=equity<=dailybase*.97
        returns.append(equity/previous-1);previous=equity
    if qty:sell(bars[end-1].close,'END_LIQUIDATION',end-1)
    equity=cash+qty*bars[end-1].close*(1-slip)*(1-fee)
    wins=sum(p for p in pnls if p>0);loss=-sum(p for p in pnls if p<0)
    sigma=statistics.stdev(returns) if len(returns)>1 else 0
    return dict(start_ms=bars[start].open_ms,end_ms=bars[end-1].open_ms+step_ms,net_return=equity/20-1,
                buy_hold_return=bars[end-1].close*(1-slip)*(1-fee)/(bars[start].open*(1+slip)*(1+fee))-1,
                max_drawdown=dd,closed_trades=len(pnls),win_rate=sum(p>0 for p in pnls)/len(pnls) if pnls else None,
                profit_factor=wins/loss if loss else None,sharpe_zero_rf=statistics.mean(returns)/sigma*math.sqrt(365.25*86400000/step_ms) if sigma else None,
                blocked=blocked,fees=fees,remaining_units=qty,
                **({'trade_journal':ledger,'stop_changes':stop_changes,'exit_mode':exit_mode} if journal else {}))


def main():
    client=PublicBinance();end=int(retry(client.fetch_time))//(15*M)*(15*M)
    start=end-(28*1440+WARMUP)*M
    folder=Path(__file__).resolve().parent.parent/'reports/local/spot-minute'/uuid.uuid4().hex
    folder.mkdir(parents=True)
    index=dict(scope='BREAKOUT_1M_EXPLORATORY',approved=False,start_ms=start,end_ms=end,rows=[])
    save(folder/'index.json',index)
    print('Experimento: '+str(folder),flush=True)
    for symbol in SYMBOLS:
        print('Coletando '+symbol,flush=True)
        try:
            bars=collect(client,symbol,start,end)
            raw=json.dumps([[c.open_ms,c.open,c.high,c.low,c.close,c.volume] for c in bars],separators=(',',':')).encode()
            (folder/(symbol.replace('/','-')+'-candles.json')).write_bytes(raw)
            rules=normalized_rules(retry(lambda:client.fetch_symbol_info(symbol)),symbol,int(retry(client.fetch_time)))
            strategy=Breakout();intents=tuple(strategy.update(c) for c in bars)
            scenarios=[]
            for label,mult in [('base',1),('double_costs',2)]:
                windows=[simulate(bars,intents,WARMUP+j*10080,WARMUP+(j+1)*10080,rules,fee=.001*mult,slip=.001*mult) for j in range(4)]
                scenarios.append(dict(name=label,windows=windows))
            report=dict(scope='CHRONOLOGICAL_EXPLORATORY_AUDIT',approved=False,symbol=symbol,timeframe='1m',
                        strategy='BREAKOUT20_VOLUME15_TREND15M',scenarios=scenarios,csv_sha256=hashlib.sha256(raw).hexdigest(),
                        model_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                        rules={k:str(v) for k,v in vars(rules).items()},
                        caveats=['28 days only; not two-year statistical validation.',
                                 'Current lot/notional constraints, not historical constraints; no tick rounding, spread, queue, partial fills or measured latency.',
                                 'Stop first on ambiguous bars; unrealizable exits remain marked, not reported as fills.',
                                 'Independent20USDT trials with reset risk; synthetic stop gaps may exceed limits.',
                                 'Six pairs and two cost scenarios; multiple comparisons, not a shared multi-pair wallet.'])
            out=folder/'reports';out.mkdir(exist_ok=True)
            save(out/(symbol.replace('/','-')+'.json'),report)
            row=dict(symbol=symbol,status='COMPLETE',bars=len(bars),base_returns=[r['net_return'] for r in scenarios[0]['windows']],
                     stress_returns=[r['net_return'] for r in scenarios[1]['windows']])
        except Exception:row=dict(symbol=symbol,status='ERROR',reason='PUBLIC_DATA_OR_EXPERIMENT_FAILED')
        index['rows'].append(row);save(folder/'index.json',index)
        print(json.dumps(row),flush=True)
    print('Pesquisa encerrada; nenhuma ordem real ou alteração da carteira ativa.',flush=True)


if __name__=='__main__':main()
