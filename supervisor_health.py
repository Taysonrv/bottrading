"""Bounded recovery of non-trading children and a local operational journal."""
import json
import math
import time
from pathlib import Path
from system_status import read


def persist_status(path,payload,writer=None,sleep=time.sleep):
    """Bounded retries for Windows sharing errors on an auxiliary heartbeat.

    This is never used for ledger, orders, STOP or engine risk persistence.
    Persistent failure returns false so readers naturally see stale status.
    """
    if writer is None:
        from spot_engine.main import save
        writer=save
    for attempt in range(3):
        try:writer(path,payload);return True
        except PermissionError:
            if attempt<2:sleep(.05*2**attempt)
        except OSError:return False
    return False


class Recovery:
    """Three delayed attempts per component for this supervisor lifetime."""
    def __init__(self):
        self.attempts = {}
        self.due = {}

    def ready(self, name, now):
        # An engine exit can represent a risk stop or corrupt ledger. Never
        # turn an operational retry into permission to resume trading.
        if name not in ('dashboard', 'market') or not math.isfinite(now):
            return False
        count = self.attempts.get(name, 0)
        if count >= 3:
            return False
        if name not in self.due:
            self.due[name] = now + 15 * 2 ** count
        return now >= self.due[name]

    def attempted(self, name, now):
        self.attempts[name] = self.attempts.get(name, 0) + 1
        self.due[name] = now + 15 * 2 ** self.attempts[name]


def event(root, kind, **fields):
    """Record only selected operational fields; never environment or credentials."""
    path = Path(root) / 'reports/local/supervisor-events.jsonl'
    path.parent.mkdir(parents=True, exist_ok=True)
    allowed = ('component', 'pid', 'exit_code', 'reason', 'attempt', 'age_seconds')
    row = dict(time_ms=int(time.time() * 1000), kind=kind)
    row.update({k: fields[k] for k in allowed if k in fields})
    # Small bounded journal, with one previous segment retained.
    if path.exists() and path.stat().st_size > 1_000_000:
        path.replace(path.with_suffix('.previous.jsonl'))
    with path.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(row, ensure_ascii=True, allow_nan=False) + '\n')


def previous_run(root, now=None):
    """A stale heartbeat is evidence of a gap, not its cause."""
    now = time.time() if now is None else now
    old = read(Path(root) / 'reports/local/system-run.json')
    stamp = old.get('updated_ms')
    if (old.get('phase') in ('RUNNING', 'DEGRADED', 'IDLE') and
            type(stamp) is int and 0 <= stamp <= now * 1000):
        event(root, 'PREVIOUS_RUN_WITHOUT_SHUTDOWN_RECORD',
              reason='CAUSE_UNKNOWN', age_seconds=(now * 1000 - stamp) / 1000)
