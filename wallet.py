"""Read-only Binance Spot inventory. No order endpoints and no trading credentials saved."""
import datetime as dt
from decimal import Decimal, InvalidOperation
import hashlib
import hmac
import json
import urllib.error
import urllib.parse
import urllib.request


class WalletError(ValueError):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise WalletError('Redirecionamento recusado na consulta Binance')


class ReadOnlyClient:
    HOST = 'https://api.binance.com'
    PATHS = {'/api/v3/time', '/api/v3/account', '/api/v3/exchangeInfo', '/api/v3/ticker/bookTicker'}

    def __init__(self, key, secret):
        if not key or not secret:
            raise WalletError('Configure BINANCE_API_KEY e BINANCE_API_SECRET localmente')
        self.key, self.secret = key, secret
        self.opener = urllib.request.build_opener(NoRedirect())

    def get(self, path, params=None):
        if path not in self.PATHS:
            raise WalletError('Endpoint não permitido pelo cliente somente leitura')
        params = dict(params or {})
        headers = {}
        if path == '/api/v3/account':
            params['timestamp'] = int(self.get('/api/v3/time')['serverTime'])
            params['recvWindow'] = 5000
            encoded = urllib.parse.urlencode(params)
            params['signature'] = hmac.new(self.secret.encode(), encoded.encode(), hashlib.sha256).hexdigest()
            headers['X-MBX-APIKEY'] = self.key
        query = urllib.parse.urlencode(params)
        req = urllib.request.Request(self.HOST + path + ('?' + query if query else ''), headers=headers, method='GET')
        try:
            with self.opener.open(req, timeout=20) as response:
                payload = json.load(response)
            if isinstance(payload, dict) and isinstance(payload.get('code'), int) and payload['code'] < 0:
                raise WalletError(f"Consulta Binance recusada (código {payload['code']})")
            return payload
        except urllib.error.HTTPError as error:
            raise WalletError(f'Consulta Binance recusada (HTTP {error.code}); confira permissões de leitura, IP e disponibilidade regional') from None
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            # Never include request URL, signed query or API headers in diagnostic text.
            raise WalletError('Falha de conexão ou resposta inválida na leitura Binance') from None


def number(value):
    try:
        result = Decimal(str(value))
    except InvalidOperation:
        raise WalletError('Quantidade ou preço inválido na resposta') from None
    if not result.is_finite() or result < 0:
        raise WalletError('Quantidade ou preço inválido na resposta')
    return result


def preview(account, exchange, tickers):
    if account.get('accountType') != 'SPOT' or not isinstance(account.get('balances'), list):
        raise WalletError('Resposta não corresponde a uma carteira Spot')
    if not isinstance(exchange.get('symbols'), list) or not isinstance(tickers, list):
        raise WalletError('Resposta de mercado inválida')
    pairs = {r['baseAsset']: r for r in exchange['symbols'] if r.get('quoteAsset') == 'USDT'}
    prices = {r['symbol']: r for r in tickers}
    assets, positions = [], {}
    free_usdt, managed, locked_value = Decimal(0), Decimal(0), Decimal(0)
    seen = set()
    for balance in account['balances']:
        asset = balance['asset']
        if not isinstance(asset, str) or not asset.isalnum() or asset in seen:
            raise WalletError('Ativo inválido ou duplicado na carteira')
        seen.add(asset)
        free, locked = number(balance['free']), number(balance['locked'])
        if free + locked == 0:
            continue
        item = {'asset': asset, 'free': str(free), 'locked': str(locked), 'supported': False,
                'bid_usdt': None, 'free_value_usdt': None, 'locked_value_usdt': None}
        if asset == 'USDT':
            bid, supported, reason = Decimal(1), True, 'USDT livre'
            category = 'spot_usdt'
            free_usdt = free
        else:
            pair = pairs.get(asset)
            ticker = prices.get(pair['symbol']) if pair else None
            bid = number(ticker['bidPrice']) if ticker else Decimal(0)
            supported = bool(pair and pair.get('status') == 'TRADING' and pair.get('isSpotTradingAllowed') is True and bid > 0)
            if supported:
                category, reason = 'spot_pair', 'Par direto Spot/USDT disponível'
            elif not pair and asset.startswith('LD'):
                category, reason = 'ld_marker', 'Marcador LD sem par Spot; verificar posição no Earn'
            elif not pair:
                category, reason = 'no_direct_pair', 'Não há par direto em USDT'
            elif pair.get('status') != 'TRADING':
                category, reason = 'inactive_pair', 'Par USDT fora de negociação (' + str(pair.get('status')) + ')'
            elif pair.get('isSpotTradingAllowed') is not True:
                category, reason = 'spot_disabled', 'Par sem permissão Spot'
            else:
                category, reason = 'no_quote', 'Cotação bid indisponível'
            if supported and free > 0:
                positions[pair['symbol']] = str(free)
                minimum = Decimal(10)
                for rule in pair.get('filters', []):
                    if rule.get('filterType') in ('NOTIONAL', 'MIN_NOTIONAL'):
                        minimum = max(minimum, number(rule.get('minNotional', 0)))
                item['below_minimum_estimate'] = free * bid < minimum
                item['symbol'] = pair['symbol']
        if supported:
            item.update(supported=True, bid_usdt=str(bid), free_value_usdt=str(free * bid), locked_value_usdt=str(locked * bid))
            managed += free * bid
            locked_value += locked * bid
        item['reason'] = reason
        item['category'] = category
        assets.append(item)
    return {'created': dt.datetime.now(dt.timezone.utc).isoformat(), 'mode': 'read_only',
            'assets': assets, 'paper_usdt_proposal': str(free_usdt), 'paper_positions_proposal': positions,
            'supported_free_value_usdt': str(managed), 'supported_locked_value_usdt': str(locked_value),
            'capital_ready': managed > 0,
            'category_counts': {category: sum(r['category'] == category for r in assets)
                                for category in sorted({r['category'] for r in assets})},
            'unpriced_assets': [r['asset'] for r in assets if not r['supported']],
            'note': 'Estimativa parcial pelo bid. Saldos bloqueados e ativos sem par direto ficam fora da proposta. Não garante execução.'}


def markdown(report):
    lines = ['# Carteira Binance Spot — consulta somente leitura', '', f"Consulta: {report['created']}", '',
             '| Ativo | Livre | Bloqueado | Valor livre estimado (USDT) | Situação |',
             '|---|---:|---:|---:|---|']
    for row in report['assets']:
        lines.append(f"| {row['asset']} | {row['free']} | {row['locked']} | {row['free_value_usdt'] or 'Sem preço'} | {row['reason']} |")
    lines += ['', f"Valor livre com cotação: {report['supported_free_value_usdt']} USDT (pode ser parcial).",
              f"Valor bloqueado com cotação: {report['supported_locked_value_usdt']} USDT (fora da proposta).", '',
              'Nenhuma ordem enviada; nenhuma configuração ou posição simulada foi alterada.',
              'A proposta em wallet-preview.json serve para revisão. Valores abaixo do mínimo podem permanecer como saldo residual.',
              'Não inclui Earn, futuros ou margem. Estimativas não incluem taxas, slippage nem filtros completos de execução.']
    if not report.get('capital_ready'):
        lines += ['', '**Nenhum capital Spot utilizável foi encontrado nesta consulta. Não importar como carteira apta para operar.**',
                  'Confira saldos aplicados no Earn/Simple Earn e os ativos sem par ativo. Marcadores LD não são convertidos automaticamente em suas moedas correspondentes.',
                  'Caso decida disponibilizar capital, faça o resgate na Binance e gere uma nova consulta após confirmar o saldo livre na Spot. O bot não resgata, transfere ou vende esses ativos.']
    return '\n'.join(lines) + '\n'
