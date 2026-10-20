"""Audit saved paper evidence. No API calls and no strategy modifications."""
import hashlib
import json
import math
from pathlib import Path
import time


def finite(v):return isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v)


def build(state,now=None):
    now=time.time() if now is None else now
    if not isinstance(state,dict) or not finite(state.get('initial')) or state['initial']<=0:
        return dict(available=False,approved=False,reason='Sem sessão válida para auditar.')
    orders=state.get('orders',[]);curve=state.get('curve',[])
    if not isinstance(orders,list) or not isinstance(curve,list):raise ValueError('Formato inválido')
    cash=state['initial'];inventory={};realized=fees=0.;issues=[]
    if len(orders)>=500:issues.append('Histórico atingiu o limite de 500 ordens; pode estar truncado.')
    sells=[];previous=-math.inf
    for o in orders:
        if not isinstance(o,dict) or o.get('side') not in ('BUY','SELL') or not isinstance(o.get('symbol'),str):
            issues.append('Ordem inválida.');continue
        if not all(finite(o.get(k)) for k in ('quantity','price','fee','time')) or o['quantity']<=0 or o['price']<=0 or o['fee']<0:
            issues.append('Valores de ordem inválidos.');continue
        if o['time']<previous:issues.append('Ordens fora da sequência temporal.')
        previous=o['time'];q=o['quantity'];gross=q*o['price'];fees+=o['fee']
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
    for symbol,p in inventory.items():
        if p['units']<=1e-9:continue
        if not saved or saved.get('symbol')!=symbol or not all(finite(saved.get(k)) and math.isclose(saved[k],p[k],abs_tol=1e-7) for k in ('units','cost')):
            issues.append('Inventário aberto não confere.')
    if saved and (saved.get('symbol') not in inventory or not math.isclose(saved.get('units',0),inventory[saved['symbol']]['units'],abs_tol=1e-7)):
        issues.append('Posição aberta sem quantidade correspondente no histórico.')
    equity=state.get('equity');pnl=state.get('pnl');unrealized=state.get('unrealized')
    if not all(finite(x) for x in (equity,pnl,unrealized)) or not math.isclose(equity-state['initial'],pnl,abs_tol=1e-7) or not math.isclose(realized+unrealized,pnl,abs_tol=1e-7):
        issues.append('Patrimônio e decomposição do resultado não conferem.')
    points=[p for p in curve if isinstance(p,dict) and finite(p.get('time')) and finite(p.get('equity')) and p['equity']>0]
    if len(points)!=len(curve):issues.append('Medições inválidas na curva.')
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
