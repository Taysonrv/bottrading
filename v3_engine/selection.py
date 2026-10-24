"""Optional observation-only priority wrapper, preserving legacy selection."""
from decimal import Decimal
from spot_engine.selection import choose as legacy_choose


def choose(previews, regime_priority=False):
    if type(regime_priority) is not bool:raise ValueError('INVALID_PRIORITY_FLAG')
    if not regime_priority:return legacy_choose(previews)
    priorities={'TREND':0,'BREAKOUT':0,'RANGE':1,'TRANSITION':2}
    rows=[r for r in previews if r.get('eligible') is True and
          r.get('regime_v3',{}).get('detected') in priorities]
    return min(rows,key=lambda r:(priorities[r['regime_v3']['detected']],
               Decimal(r['spread_fraction']),r['symbol']))['symbol'] if rows else None
