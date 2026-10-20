import math
from .contracts import numeric,fields


def assess(journal,account,now,stop=False):
    fields(account,('equity','cash','positions','inventory_fraction'))
    numeric(now,0);equity=numeric(account['equity'],1e-300);numeric(account['cash'],0,equity)
    numeric(account['inventory_fraction'],0,1)
    if isinstance(account['positions'],bool) or not isinstance(account['positions'],int) or account['positions']<0:raise ValueError('Posições inválidas')
    if not math.isclose(account['cash']+equity*account['inventory_fraction'],equity,abs_tol=1e-8):raise ValueError('Caixa e inventário não reconciliam')
    if bool(account['positions'])!=bool(account['inventory_fraction']):raise ValueError('Inventário inconsistente')
    saved=journal.get('risk')
    if saved is None and journal.get('risk_initialized'):raise ValueError('Checkpoint de risco ausente; não reiniciado')
    if saved is not None:
        fields(saved,('day','day_start','peak','daily_halted','halted','last_at'))
        numeric(saved['day_start'],1e-300);numeric(saved['peak'],saved['day_start']);numeric(saved['last_at'],0)
        if type(saved['halted']) is not bool or type(saved['daily_halted']) is not bool:raise ValueError('Trava persistente inválida')
        if type(saved['day']) is not int or saved['day']<0 or saved['day']!=int(saved['last_at'])//86400:
            raise ValueError('Dia persistente inconsistente')
    state=saved or dict(day=int(now)//86400,day_start=equity,peak=equity,daily_halted=False,halted=False,last_at=now)
    if now<state['last_at']:raise ValueError('Relógio retrocedeu')
    day=int(now)//86400
    if day!=state['day']:state.update(day=day,day_start=equity,daily_halted=False)
    state['peak']=max(state['peak'],equity)
    dd=1-equity/state['peak'];daily=1-equity/state['day_start']
    state['halted']=state['halted'] or dd>=.15-1e-12
    state['daily_halted']=state['daily_halted'] or daily>=.03-1e-12
    state.update(last_at=now);journal.put_many({'risk':state,'risk_initialized':True})
    reason='STOP' if stop else 'DRAWDOWN' if state['halted'] else 'DAILY_LOSS' if state['daily_halted'] else 'REVIEW_REQUIRED' if journal.get('review_required') else 'POSITION_LIMIT' if account['positions'] else 'NO_CASH' if account['cash']<=0 else 'OK'
    return dict(eligible=reason=='OK',reason=reason,drawdown=dd,daily_loss=daily,max_notional=min(5,equity*.25,account['cash']),kelly_enabled=False,trading_enabled=False)
