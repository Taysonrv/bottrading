"""Local saved reports only; no network, wallet permissions or execution."""
import json
from pathlib import Path


def load(root):
    def read(name):
        try:
            value=json.loads((Path(root)/'reports/local'/name).read_text(encoding='utf-8'))
            return value if isinstance(value,dict) else {}
        except (ValueError,OSError):
            return {}
    quotes=read('wallet-quote-research.json');costs=read('solana-cost-research.json');balances=read('metamask-balances.json')
    return dict(balances=balances,quotes=dict(created=quotes.get('created'),results=[
        {k:r.get(k) for k in ('asset','input_tokens','bridge_token','sale_output','repurchase_tokens','quote_loss_percent','status','gas_sensitivity')}
        for r in quotes.get('results',[]) if isinstance(r,dict)]),
        costs=dict(created=costs.get('created'),legs=[
            {**{k:r.get(k) for k in ('leg','fee_lamports','priority_lamports','units_consumed','simulation_error','builder_error','error_type')},
             'diagnosis':'Saldo insuficiente para valor, taxas ou aluguel (6024). Simulações independentes não creditam USDC.' if '6024' in json.dumps(r.get('simulation_error',{})) else None}
            for r in costs.get('legs',[]) if isinstance(r,dict)]),executed=False,approved=False)
