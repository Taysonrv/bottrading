"""Archive one STOPPED EMA experiment, never the active shared portfolio.

Confirmation is required. Positions, active orders and inconsistent reports
refuse migration. STOP is preserved. Local risk state travels with its session.
"""
import argparse
from contextlib import closing
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import re
import sqlite3
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from spot_engine.main import single_runner


def inspect(folder):
    plan=json.loads((folder/'session.json').read_text(encoding='utf-8'))
    status=json.loads((folder/'status.json').read_text(encoding='utf-8'))
    dbpath=folder/'reports/local/spot-execution/paper.sqlite'
    with closing(sqlite3.connect(dbpath.resolve().as_uri()+'?mode=ro',uri=True)) as db:
        state=json.loads(db.execute('SELECT payload FROM ledger WHERE id=1').fetchone()[0])
    if Decimal(state['units'])!=0 or state.get('active') or status.get('phase')!='STOPPED':
        raise ValueError('SESSION_MUST_BE_STOPPED_FLAT_WITHOUT_PENDING_ORDER')
    if status.get('units')!=state['units'] or status.get('cash')!=state['cash']:
        raise ValueError('STATUS_LEDGER_MISMATCH')
    return plan,status


def archive(root, session, reason, confirm=input):
    root=Path(root).resolve()
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,40}',session) or not isinstance(reason,str) or not 1<=len(reason)<=500:
        raise ValueError('INVALID_ARGUMENTS')
    folder=(root/'reports/local/spot-runs'/session).resolve()
    if not folder.is_relative_to(root/'reports/local/spot-runs') or folder.is_symlink():raise ValueError('INVALID_PATH')
    stamp=datetime.now(timezone.utc).strftime('%Y-%m-%d_%H%M%S_%f')
    destination=root/'reports/archive'/(session+'_'+stamp)
    # Retain runner.lock in its original directory while moving session-owned
    # contents. This closes the release/rename race and works on Windows.
    with single_runner(folder/'runner.lock'):
        plan,status=inspect(folder)
        if confirm('Confirmar arquivo da sessão parada, sem posição? [sim/não]: ').strip().lower()!='sim':
            return None
        # Recheck after potentially long interactive confirmation.
        inspect(folder)
        children=[p for p in folder.iterdir() if p.name!='runner.lock']
        if any(p.is_symlink() for p in children):raise ValueError('SYMLINK_NOT_ALLOWED')
        destination.parent.mkdir(parents=True,exist_ok=True)
        destination.mkdir(exist_ok=False)
        record=dict(archived_at=datetime.now(timezone.utc).isoformat(),session=session,
            final_equity=status.get('equity'),final_pnl=status.get('pnl'),buy_fills=status.get('buy_fills'),
            identity_archived=plan['identity'],reason=reason,files_moved=[],state='MOVING',
            note='Original runner.lock retained. STOP preserved; no automatic restart or rollback.')
        path=destination.parent/('MIGRATION_RECORD_'+stamp+'.json')
        # Persist each completed move; a partial filesystem failure remains
        # diagnosable. Never silently roll back over a newly created session.
        with path.open('x',encoding='utf-8') as stream:json.dump(record,stream,indent=2)
        for child in children:
            child.rename(destination/child.name)
            record['files_moved'].append(dict(source=str(child),destination=str(destination/child.name)))
            path.write_text(json.dumps(record,indent=2),encoding='utf-8')
        record['state']='ARCHIVED';path.write_text(json.dumps(record,indent=2),encoding='utf-8')
    print(str(destination));return destination


def main():
    p=argparse.ArgumentParser(description='Arquivo EMA parado, sem posição; nunca move portfolio.')
    p.add_argument('--data-dir',type=Path,default=Path.cwd());p.add_argument('--session',required=True)
    p.add_argument('--reason',required=True);args=p.parse_args()
    try:archive(args.data_dir,args.session,args.reason)
    except (OSError,ValueError,KeyError,sqlite3.Error) as e:raise SystemExit('Migração recusada; preserve a sessão e confira locks/ledger/status.') from e


if __name__=='__main__':main()
