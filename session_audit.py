"""Audit saved paper evidence. No API calls and no strategy modifications."""
import hashlib
import json
import math
from pathlib import Path
import time


def shared_review(root,now=None):
    """Read-only review of the complete shared ledger and sampled services.

    Snapshot sources are read separately, not a cross-process transaction.
    Never sums legacy wallets, treats unknown intervals as uptime, or approves.
    """
    from collections import Counter
    from decimal import Decimal,DecimalException,localcontext
    import sqlite3
    from portfolio_alerts import ledger
    from portfolio_view import load
    from system_status import build as operational,read
    root=Path(root);now=time.time() if now is None else now
    if not finite(now) or now<0:raise ValueError('INVALID_REVIEW_TIME')
    issues=[];s=None
    try:s=ledger(root)
    except (OSError,ValueError,TypeError,KeyError,sqlite3.Error,DecimalException):
        issues.append('Carteira completa indisponível ou com integridade/identidade inválida.')
    scope=operational(root,now)
    if scope['controller']['engine']!='portfolio':issues.append('Motor compartilhado não está selecionado no supervisor.')
    for name in ('controller','execution','market'):
        if not scope[name]['fresh']:issues.append('Sem atualização confirmada: '+name+'.')
    plan=read(root/'reports/local/portfolio/plan.json')
    end=plan.get('end_ms');valid_end=type(end) is int and 0<end<=253402300799000
    expired=now*1000>=end if valid_end else None
    if not valid_end:issues.append('Prazo da sessão indisponível.')
    elif expired:issues.append('Prazo da sessão encerrado; relatório não renova a sessão.')
    stopped=(root/'STOP').exists() or (root/'reports/local/portfolio/STOP').exists()
    if stopped:issues.append('STOP presente; este relatório não remove a trava.')
    wallet=None
    if s is not None:
        view=load(root,now);same=view.get('available') and all(view.get(k)==s[k] for k in ('cash','fees','realized','position','pending'))
        # Cash is known without a quote if no inventory is held. With inventory,
        # accept only the same reconciled snapshot's recent mark.
        equity=s['cash'] if s['position'] is None else view.get('equity') if same and view.get('fresh') else None
        with localcontext() as context:
            context.prec=80
            pnl=str(Decimal(equity)-Decimal('20')) if equity is not None else None
        wallet=dict(cash=s['cash'],fees=s['fees'],realized=s['realized'],equity=equity,
            total_pnl=pnl,
            position_open=s['position'] is not None,entry_pending=s['pending'] is not None,
            halt=s['halt'],buy_fills=sum(f['side']=='BUY' for f in s['fills']),
            sell_fills=sum(f['side']=='SELL' for f in s['fills']),orders=len(s['orders']),
            order_states=dict(Counter(o['status'] for o in s['orders'].values())),
            canceled_reasons=dict(Counter(o.get('reason','UNRECORDED') for o in s['orders'].values() if o['status']=='CANCELED')),
            ledger_reconciled=True,ledger_last_ms=s['last_ms'])
        if equity is None:issues.append('Inventário sem marcação recente compatível; patrimônio desconhecido.')
        if s['halt']:issues.append('Trava de risco registrada: '+str(s['halt'])+'.')
        if not s['fills']:issues.append('Sem preenchimentos: não há desempenho operacional de trades para avaliar.')
    h=read(root/'reports/local/operation-health.json');monitor=None
    keys=('recent_seconds','stopped_seconds','unknown_seconds')
    if (all(finite(h.get(k)) and h[k]>=0 for k in keys) and finite(h.get('updated')) and
            finite(h.get('started')) and 0<=h['started']<=h['updated']<=now):
        monitor=dict(**{k:h[k] for k in keys},age_seconds=now-h['updated'],
                     scope='Janela do monitor pode incluir outras sessões; não é uptime comprovado.')
        if monitor['age_seconds']>=45:issues.append('Monitor de disponibilidade sem amostra recente.')
        if h['unknown_seconds']>0:issues.append('Há tempo desconhecido no monitor; continuidade não demonstrada.')
    else:issues.append('Medição de disponibilidade ausente ou inválida.')
    alerts=read(root/'reports/local/portfolio/alerts-status.json');stamp=alerts.get('updated_ms')
    alerts_recent=type(stamp) is int and 0<=now*1000-stamp<90000
    telegram=alerts.get('telegram_enabled') if alerts_recent and type(alerts.get('telegram_enabled')) is bool else None
    if telegram is not True:issues.append('Entrega Telegram não confirmada neste relatório.')
    return dict(mode='PAPER',created_ms=int(now*1000),approved=False,live_enabled=False,
        verdict='NOT_READY_FOR_LIVE',wallet=wallet,operational=scope,session_expired=expired,
        stop_present=stopped,availability=monitor,telegram_enabled=telegram,issues=issues,
        notes=['Full shared-wallet ledger only; legacy balances excluded.',
               'Sources sampled separately; not an atomic cross-service snapshot.',
               'Zero trading PnL without fills is not evidence of an edge.',
               'No strategy profitability or independent validation is granted by this operational report.'])


def finite(v):return isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v)


def build(state,now=None):
    now=time.time() if now is None else now
    if not isinstance(state,dict) or not finite(state.get('initial')) or state['initial']<=0:
        return dict(available=False,approved=False,reason='Sem sessão válida para auditar.')
    orders=state.get('orders',[]);curve=state.get('curve',[])
    if not isinstance(orders,list) or not isinstance(curve,list):raise ValueError('Formato inválido')
    cash=state['initial'];inventory={};realized=fees=0.;issues=[]
    measurement=state.get('updated')
    valid_measurement=finite(measurement) and measurement>=0 and measurement<=now
    if not valid_measurement:issues.append('Horário da medição ausente, inválido ou futuro.')
    if len(orders)>=500:issues.append('Histórico atingiu o limite de 500 ordens; pode estar truncado.')
    sells=[];previous=-math.inf
    for o in orders:
        if not isinstance(o,dict) or o.get('side') not in ('BUY','SELL') or not isinstance(o.get('symbol'),str):
            issues.append('Ordem inválida.');continue
        if not all(finite(o.get(k)) for k in ('quantity','price','fee','time')) or o['quantity']<=0 or o['price']<=0 or o['fee']<0:
            issues.append('Valores de ordem inválidos.');continue
        if o['time']<0 or o['time']>now or (valid_measurement and o['time']>measurement):
            issues.append('Ordem posterior à medição ou com horário inválido/futuro.')
        if o['time']<previous:issues.append('Ordens fora da sequência temporal.')
        previous=o['time'];q=o['quantity'];gross=q*o['price'];fees+=o['fee']
        if not finite(gross) or not finite(gross+o['fee']):
            issues.append('Valor financeiro da ordem excede limite numérico.');continue
        p=inventory.setdefault(o['symbol'],dict(units=0.,cost=0.))
        if o['side']=='BUY':
            cash-=gross+o['fee'];p['units']+=q;p['cost']+=gross+o['fee']
        elif q>p['units']+1e-9:
            issues.append('Venda sem inventário suficiente; histórico incompleto ou inconsistente.')
        else:
            removed=p['cost']*q/p['units'];pnl=gross-o['fee']-removed
            cash+=gross-o['fee'];realized+=pnl;sells.append(pnl)
            p['units']-=q;p['cost']-=removed
            if not finite(o.get('pnl')) or not math.isclose(o['pnl'],pnl,abs_tol=1e-7):issues.append('PNL da venda não confere com custo médio.')
    for k,value in [('cash',cash),('realized',realized)]:
        if not finite(state.get(k)) or not math.isclose(state[k],value,abs_tol=1e-7):issues.append('Reconciliação divergente: '+k)
    saved=state.get('position')
    if saved is not None and (not isinstance(saved,dict) or not isinstance(saved.get('symbol'),str) or not all(finite(saved.get(k)) and saved[k]>0 for k in ('units','cost'))):
        issues.append('Formato ou valores da posição aberta inválidos.')
        saved=None
    for symbol,p in inventory.items():
        if p['units']<=1e-9:continue
        if not saved or saved.get('symbol')!=symbol or not all(finite(saved.get(k)) and math.isclose(saved[k],p[k],abs_tol=1e-7) for k in ('units','cost')):
            issues.append('Inventário aberto não confere.')
    if saved and (saved.get('symbol') not in inventory or not math.isclose(saved.get('units',0),inventory[saved['symbol']]['units'],abs_tol=1e-7)):
        issues.append('Posição aberta sem quantidade correspondente no histórico.')
    equity=state.get('equity');pnl=state.get('pnl');unrealized=state.get('unrealized')
    if not all(finite(x) for x in (equity,pnl,unrealized)) or not math.isclose(equity-state['initial'],pnl,abs_tol=1e-7) or not math.isclose(realized+unrealized,pnl,abs_tol=1e-7):
        issues.append('Patrimônio e decomposição do resultado não conferem.')
    if not finite(cash) or cash < -1e-7:
        issues.append('Caixa reconstruído negativo ou inválido para Spot sem alavancagem.')
    if finite(equity) and finite(state.get('cash')):
        if saved is None and not math.isclose(equity,state['cash'],abs_tol=1e-7):
            issues.append('Sem posição aberta, patrimônio deve corresponder ao caixa.')
        elif saved is not None and equity < state['cash']-1e-7:
            issues.append('Valor marcado da posição não pode ser negativo.')
    points=[p for p in curve if isinstance(p,dict) and finite(p.get('time')) and finite(p.get('equity')) and p['equity']>0]
    if len(points)!=len(curve):issues.append('Medições inválidas na curva.')
    if any(p['time']<0 or p['time']>now or (valid_measurement and p['time']>measurement) for p in points):
        issues.append('Curva contém horário inválido, futuro ou posterior à medição.')
    if any(b['time']<=a['time'] for a,b in zip(points,points[1:])):issues.append('Curva fora de ordem temporal.')
    gaps=[b['time']-a['time'] for a,b in zip(points,points[1:]) if b['time']-a['time']>180]
    peak=points[0]['equity'] if points else None;dd=0.
    for point in points:
        peak=max(peak,point['equity']);dd=max(dd,1-point['equity']/peak)
    gains=[v for v in sells if v>0];losses=[v for v in sells if v<0]
    return dict(available=True,created=now,measurement=state.get('updated'),approved=False,
      session_identity=state.get('identity'),source_sha256=hashlib.sha256(json.dumps(state,sort_keys=True).encode()).hexdigest(),
      audit_code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
      initial=state['initial'],cash=state.get('cash'),equity=equity,pnl=pnl,realized=realized,unrealized=unrealized,
      fees=fees,buys=sum(o.get('side')=='BUY' for o in orders if isinstance(o,dict)),sells=len(sells),
      wins=len(gains),losses=len(losses),win_rate=len(gains)/len(sells) if sells else None,
      average_win=sum(gains)/len(gains) if gains else None,average_loss=sum(losses)/len(losses) if losses else None,
      profit_factor=sum(gains)/-sum(losses) if losses else None,
      saved_curve_drawdown=dd if points else None,curve_points=len(points),curve_start=points[0]['time'] if points else None,
      curve_end=points[-1]['time'] if points else None,gaps_over_180s=len(gaps),largest_gap_seconds=max(gaps) if gaps else 0,
      reconciled=not issues,issues=list(dict.fromkeys(issues)),position=saved,
      benchmarks={'cash_pnl':0,'buy_hold':None,'reason':'Sem série de benchmark independente, alinhada ao início e aos custos desta sessão.'},
      limits=['Drawdown e lacunas cobrem apenas as medições retidas; a curva pode estar truncada a 1.500 pontos.',
              'Taxas registradas não incluem slippage separadamente: ele já está embutido nos preços fictícios.',
              'Fator de lucro indefinido sem vendas negativas; não é infinito nem prova de vantagem.',
              'Sem cotações independentes para confirmar o preço marcado da posição aberta; somente consistência contábil.',
              'Sem Sharpe/CAGR anualizados para esta sessão curta e irregular. Reconciliação não valida rentabilidade.'])


SOURCES=('spot-suite.json','momentum-universe.json','small-cap-comparison.json','prospective-results.json')

def register(root):
    folder=Path(root)/'reports/local';path=folder/'research-registry.json'
    registry=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'studies':[],'variants':[]}
    known={s['digest'] for s in registry['studies']};variants={v['id'] for v in registry['variants']}
    for name in SOURCES:
        report=folder/name
        if not report.exists():continue
        raw=report.read_bytes();digest=hashlib.sha256(raw).hexdigest()
        if digest in known:continue
        data=json.loads(raw)
        if not isinstance(data,dict) or not isinstance(data.get('comparisons'),list):continue
        registry['studies'].append(dict(source=name,digest=digest,registered=time.time(),created=data.get('created'),
                                       result_rows=len(data['comparisons']),approved=False))
        for row in data['comparisons']:
            config={k:row.get(k) for k in ('strategy','stress','window','fraction','entry_interval') if k in row}
            config.update(source=name,symbols=data.get('symbols'),capital=data.get('capital'))
            variant=hashlib.sha256(json.dumps(config,sort_keys=True).encode()).hexdigest()
            if variant not in variants:
                registry['variants'].append(dict(id=variant,configuration=config,first_report=digest));variants.add(variant)
        known.add(digest)
    registry['scope']='Inventário retrospectivo dos relatórios locais disponíveis, não uma pré-inscrição histórica. Configurações não registradas não são contadas. Não corrige múltiplos testes.'
    registry['approved']=False
    return registry


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description='Revisão somente leitura da carteira compartilhada PAPER.')
    parser.add_argument('--data-dir',type=Path,default=Path(__file__).resolve().parent)
    args=parser.parse_args()
    print(json.dumps(shared_review(args.data_dir.resolve()),ensure_ascii=True,allow_nan=False,indent=2))
