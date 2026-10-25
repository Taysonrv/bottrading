"""Public read-only state loop and durable decisions. No broker or HTTP AI calls."""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import time
from ai_shadow.journal import Journal
from spot_engine.data import PublicBinance,download,retry
from spot_engine.main import parse_book,save
from . import SYMBOLS,VERSION
from .state import build
from .account import load as load_account
from .policy import assess
from .jev import DisabledProvider,request
from .review import daily


def hashes():
    package=Path(__file__).parent
    digest=hashlib.sha256()
    files=sorted(package.glob('*.py'))+[package.parent/'quant_control_run.py',package.parent/'ai_shadow/journal.py',
        package.parent/'experiments/quant_control_plan.json']
    for p in files:digest.update(p.name.encode()+b'\0'+p.read_bytes())
    plan=hashlib.sha256(json.dumps(dict(version=VERSION,symbols=SYMBOLS,mode='OBSERVE_ONLY',paid_calls=0),sort_keys=True).encode()).hexdigest()
    return plan,digest.hexdigest()


class Control:
    def __init__(self,root,client=None):
        self.root=Path(root);self.folder=self.root/'reports/local/quant-control'
        self.folder.mkdir(parents=True,exist_ok=True)
        plan,code=hashes();self.journal=Journal(self.folder/'journal.sqlite',plan,code)
        self.identity=code;self.client=PublicBinance() if client is None else client
        self.provider=DisabledProvider();self.histories={};self.cutoff=None
        self.started_ms=int(time.time()*1000)

    def close(self):self.journal.close()
    def stopped(self):
        return (self.root/'STOP').exists() or (self.folder/'STOP').exists()

    def cycle(self):
        start=time.monotonic();now=int(time.time()*1000);cutoff=now//900000*900000;rows=[]
        last=self.journal.get('last_ms')
        if last is not None and now<last:raise ValueError('CONTROL_CLOCK_REVERSED')
        if self.stopped():return self.publish([],False,'STOP',start)
        for symbol in SYMBOLS:
            try:
                if self.stopped():raise ValueError('STOP')
                history=self.histories.get(symbol)
                if history is None or history.end_ms!=cutoff:
                    history=download(self.client,symbol,'15m',cutoff-61*900000,cutoff)
                    self.histories[symbol]=history
                then=time.monotonic();raw=retry(lambda:self.client.fetch_book(symbol))
                received=int(time.time()*1000)
                if time.monotonic()-then>2:raise ValueError('SLOW_BOOK')
                bid,ask,bq,aq=parse_book(raw,symbol)
                book=dict(symbol=symbol,bid=float(bid),ask=float(ask),bid_qty=float(bq),ask_qty=float(aq),received_ms=received)
                account=load_account(self.root,book,received)
                as_of=int(time.time()*1000)
                if account['account_received_ms']>as_of:raise ValueError('ACCOUNT_CLOCK_REVERSED')
                snapshot=build(book,history,account,as_of)
                context=dict(stopped=self.stopped(),fresh=True,session_active=account['session_active'],
                    positions=account['positions'],pending=account['pending'],risk_ledger_clear=account['ledger_halt'] is None,
                    edge_validated=False,calibration_verified=False,decision_state_fresh=True)
                ident=hashlib.sha256((self.identity+symbol+str(history.end_ms)).encode()).hexdigest()
                old=self.journal.request(ident)
                if old:
                    result=json.loads(old['result']) if old['phase']=='completed' else dict(policy=dict(action='HOLD',gates_failed=['UNKNOWN_PREVIOUS_RESULT']))
                else:
                    provider=self.provider.evaluate(snapshot)
                    policy=assess(snapshot,provider['decision'],context)
                    result=dict(symbol=symbol,decision_ms=history.end_ms,snapshot=snapshot,provider=provider,
                        policy=policy,requests_paid=0,execution_authorized=False)
                    self.journal.reserve(ident,dict(snapshot=snapshot,note='No secrets, raw wallet address or account keys.'),0)
                    self.journal.finish(ident,result)
                # Inference is deduplicated per bar. Safety is rechecked with
                # CURRENT state every cycle, never copied from an older verdict.
                context['stopped']=self.stopped()
                decision_at=result.get('snapshot',{}).get('as_of_ms')
                context['decision_state_fresh']=type(decision_at) is int and 0<=as_of-decision_at<=2000
                current_policy=assess(snapshot,result.get('provider',{}).get('decision'),context)
                rows.append(dict(symbol=symbol,status='OK',snapshot=snapshot,
                    decision_id=ident,decision_ms=history.end_ms,policy=current_policy,
                    model_input_as_of_ms=decision_at,snapshot_role='CURRENT_RISK_RECHECK',
                    provider=self.provider.name,provider_latency_ms=None,
                    account_phase=account['phase'],execution_authorized=False))
            except Exception:
                error_id=hashlib.sha256((self.identity+symbol+str(cutoff)+'unverified').encode()).hexdigest()
                if self.journal.request(error_id) is None:
                    self.journal.reserve(error_id,dict(symbol=symbol,closed_bar_ms=cutoff,valid_state=False),0)
                    self.journal.finish(error_id,dict(policy=dict(action='HOLD',gates_failed=['VALID_STATE'],
                        review_reasons=['STATE_OR_LEDGER_UNVERIFIED']),execution_authorized=False))
                rows.append(dict(symbol=symbol,status='UNAVAILABLE',reason='STATE_OR_LEDGER_UNVERIFIED',
                    policy=dict(action='HOLD',gates_failed=['VALID_STATE']),execution_authorized=False))
        report=self.publish(rows,all(r['status']=='OK' for r in rows),'OBSERVING',start)
        self.journal.put('last_ms',max(last or 0,report['updated_ms']))
        try:daily(self.journal,self.root,int(time.time()*1000))
        except Exception:report['review_status']='UNAVAILABLE';save(self.folder/'latest.json',report)
        return report

    def publish(self,rows,healthy,reason,start):
        report=dict(version=VERSION,identity=self.identity,mode='PAPER_RESEARCH_CONTROL',
            updated_ms=int(time.time()*1000),started_ms=self.started_ms,
            reason=reason if healthy or reason=='STOP' else 'PARTIAL_OR_UNVERIFIED_DATA',
            healthy=healthy,pairs=rows,provider_enabled=False,provider='NOT_CONFIGURED',
            calls_paid=0,orders=0,execution_authorized=False,approved=False,kelly_enabled=False,
            limits=dict(drawdown=.10,daily_loss=.03,risk_per_trade=.01),
            cycle_latency_ms=(time.monotonic()-start)*1000,
            token_target=400,token_count_verified=False,provider_latency_ms=None,
            note='Research/reflex separation implemented; no AI inference or execution enabled.')
        save(self.folder/'latest.json',report)
        return report
