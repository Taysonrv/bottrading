"""Full-session review. No labels invented, no self-modifying strategy/schema."""
from collections import Counter
from datetime import datetime,timezone
import json
from pathlib import Path
import uuid
from portfolio_alerts import ledger
from spot_engine.main import save


def summarize(journal,root,now_ms):
    rows=journal.db.execute('SELECT phase,result FROM requests ORDER BY rowid').fetchall()
    failures=Counter();review_reasons=Counter();completed=0
    for row in rows:
        if row['phase']!='completed':continue
        completed+=1;r=json.loads(row['result'])
        failures.update(r.get('policy',{}).get('gates_failed',[]))
        review_reasons.update(r.get('policy',{}).get('review_reasons',[]))
    try:
        s=ledger(root)
        fills=s['fills'];sales=sum(f['side']=='SELL' for f in fills)
        account=dict(status='RECONCILED',fills=len(fills),closed_cycles=sales,
            realized=s['realized'],fees=s['fees'],position_open=bool(s['position']),pending=bool(s['pending']))
    except Exception:account=dict(status='UNAVAILABLE',fills=None,closed_cycles=None,realized=None,fees=None)
    return dict(scope='FULL_SESSION_RESEARCH_REVIEW',updated_ms=now_ms,requests=len(rows),completed=completed,
        unknown_or_incomplete=sum(r['phase']!='completed' for r in rows),failed_gates=dict(failures),
        review_reasons=dict(review_reasons),account=account,
        genuine_model_predictions=0,mature_labels=0,brier=None,calibration_status='UNMEASURED_NO_REAL_PROVIDER',
        proposals=[dict(id='validation-first',action='Keep rejected hypotheses out of execution; require independent validation.',auto_apply=False),
                   dict(id='provider-evidence',action='Verify provider key, paid-call approval, token count and calibration before enabling inference.',auto_apply=False)],
        approved=False,execution_authorized=False,auto_apply=False,model_or_schema_changed=False,
        note='No genuine inference is configured. Market direction observations are not profitability labels.')


def daily(journal,root,now_ms):
    day=datetime.fromtimestamp(now_ms/1000,timezone.utc).strftime('%Y-%m-%d')
    if journal.get('review_day')==day:return None
    report=summarize(journal,root,now_ms)
    folder=Path(root)/'reports/local/quant-control/reviews';folder.mkdir(parents=True,exist_ok=True)
    with (folder/(day+'-'+uuid.uuid4().hex+'.json')).open('x',encoding='utf-8') as out:
        json.dump(report,out,allow_nan=False,indent=2)
    save(folder.parent/'review-latest.json',report);journal.put('review_day',day)
    return report
