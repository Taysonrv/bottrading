"""Explicit version selection; absence of marker keeps the original six-pair ledger."""
import json
from pathlib import Path
from spot_engine.portfolio import Portfolio as LegacyPortfolio


def factory(root):
    path=Path(root)/'portfolio12.json'
    if not path.exists():return LegacyPortfolio(root)
    if path.stat().st_size>1000:raise ValueError('INVALID_PORTFOLIO_PROFILE')
    marker=json.loads(path.read_text(encoding='utf-8'))
    if marker!={'variant':'PAPER12_V1'}:raise ValueError('INVALID_PORTFOLIO_PROFILE')
    from portfolio12 import Portfolio
    return Portfolio(root)


def symbols(root):
    path=Path(root)/'portfolio12.json'
    if path.exists():
        factory(root)  # Explicit fail-closed profile validation.
        from portfolio12 import SYMBOLS
    else:
        from spot_engine.portfolio import SYMBOLS
    return SYMBOLS
