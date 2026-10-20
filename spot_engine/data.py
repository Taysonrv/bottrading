"""Public Spot candles only. No account keys, signals, balances or orders.

Historical timestamps describe market bars, not simulated execution availability.
"""
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import re
import time
import uuid

STEPS = {'15m': 900_000, '1h': 3_600_000, '4h': 14_400_000}


class DataError(ValueError):
    """Safe error: never include raw provider exceptions or payloads."""


class DataGapError(DataError):
    pass


class TransientDataError(DataError):
    pass


def interval(symbol, timeframe):
    if not isinstance(symbol, str) or not re.fullmatch(r'[A-Z0-9]{2,15}/USDT', symbol):
        raise DataError('Par inválido; esperado BASE/USDT Spot.')
    if timeframe not in STEPS:
        raise DataError('Timeframe não suportado.')
    return STEPS[timeframe]


def milliseconds(value):
    if type(value) is not int or not 0 <= value <= 253402300799000:
        raise DataError('Timestamp UTC em milissegundos inválido.')
    return value


@dataclass(frozen=True)
class Candle:
    open_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float

    def __post_init__(self):
        milliseconds(self.open_ms)
        values = (self.open, self.high, self.low, self.close, self.volume)
        if any(type(x) not in (int, float) or not math.isfinite(x) for x in values):
            raise DataError('OHLCV contém valor inválido.')
        if min(self.open, self.high, self.low, self.close) <= 0 or self.volume < 0:
            raise DataError('Preço não positivo ou volume negativo.')
        if not self.low <= min(self.open, self.close) <= max(self.open, self.close) <= self.high:
            raise DataError('OHLC inconsistente.')


def parse_row(row, step):
    if not isinstance(row, (list, tuple)) or len(row) != 6:
        raise DataError('Formato OHLCV inválido.')
    candle = Candle(*row)
    if candle.open_ms % step:
        raise DataError('Candle desalinhado com UTC/timeframe.')
    return candle


@dataclass(frozen=True)
class History:
    symbol: str
    timeframe: str
    start_ms: int
    end_ms: int
    observed_ms: int
    candles: tuple[Candle, ...]
    pages: int
    duplicates: int


class PublicBinance:
    """Small read-only facade; intentionally exposes no order/account methods."""
    def __init__(self):
        try:
            import ccxt
        except ImportError:
            raise DataError('Instale requirements-spot-data.txt no ambiente Python escolhido.') from None
        self._ccxt = ccxt
        self._exchange = ccxt.binance({
            'enableRateLimit': True, 'timeout': 15000, 'apiKey': '', 'secret': '',
            'options': {'defaultType': 'spot', 'fetchMarkets': {'types': ['spot']}, 'fetchCurrencies': False}})

    def _call(self, function, *args, **kwargs):
        try:
            return function(*args, **kwargs)
        except (self._ccxt.RateLimitExceeded, self._ccxt.DDoSProtection):
            # Fail closed on 429/ban rather than retrying aggressively.
            raise DataError('Limite da API atingido; interrompido sem novas tentativas.') from None
        except (self._ccxt.NetworkError, self._ccxt.ExchangeNotAvailable):
            raise TransientDataError('Consulta pública temporariamente indisponível.') from None
        except self._ccxt.BaseError:
            raise DataError('Consulta pública recusada; confira par, conexão e disponibilidade.') from None

    def fetch_time(self):
        return self._call(self._exchange.fetch_time)

    def fetch_ohlcv(self, symbol, timeframe, since, limit):
        interval(symbol, timeframe)
        return self._call(self._exchange.fetch_ohlcv, symbol, timeframe=timeframe, since=since, limit=limit)


def retry(function, sleep=time.sleep):
    for attempt in range(3):
        try:
            return function()
        except TransientDataError:
            if attempt == 2:
                raise
            sleep(2 ** attempt)


def download(client, symbol, timeframe, start_ms, end_ms=None, *, sleep=time.sleep):
    """Fetch [start,end), aligned to closed bars; reject incomplete coverage.

    Short pages are not treated as end-of-history. Same-content overlaps are
    deduplicated; conflicting bars and stalled pagination abort the download.
    """
    step = interval(symbol, timeframe)
    start = milliseconds(start_ms)
    observed = milliseconds(retry(client.fetch_time, sleep))
    end = observed // step * step if end_ms is None else milliseconds(end_ms)
    if start % step or end % step or not start < end <= observed:
        raise DataError('Janela deve ser alinhada, crescente e sem candles futuros/em formação.')
    expected = (end - start) // step
    if expected > 2_000_000:
        raise DataError('Janela excede o limite de segurança do coletor.')
    found = {}; cursor = start; pages = duplicates = 0
    while cursor < end:
        rows = retry(lambda: client.fetch_ohlcv(symbol, timeframe, since=cursor, limit=1000), sleep)
        pages += 1
        if not isinstance(rows, list) or len(rows) > 1000:
            raise DataError('Página OHLCV inválida.')
        if not rows:
            break
        parsed = [parse_row(row, step) for row in rows]
        if any(b.open_ms < a.open_ms for a, b in zip(parsed, parsed[1:])):
            raise DataError('Página OHLCV fora de ordem temporal.')
        latest = max(c.open_ms for c in parsed)
        for candle in parsed:
            if not start <= candle.open_ms < end:
                continue
            old = found.get(candle.open_ms)
            if old is not None:
                if old != candle:
                    raise DataError('Duplicata conflitante de candle fechado.')
                duplicates += 1
            found[candle.open_ms] = candle
        if latest < cursor:
            raise DataError('Paginação sem progresso; coleta interrompida.')
        cursor = latest + step
        if pages > expected + 1:
            raise DataError('Limite de paginação excedido.')
    missing = expected - len(found)
    if missing:
        raise DataGapError(f'Histórico incompleto: {missing} candles ausentes. Sem preenchimento artificial.')
    return History(symbol, timeframe, start, end, observed, tuple(found[t] for t in sorted(found)), pages, duplicates)


def parse_closed_event(message, symbol, timeframe, received_ms):
    """Validate native Binance UTC kline messages; ignore unfinished bars."""
    step = interval(symbol, timeframe); milliseconds(received_ms)
    if not isinstance(message, dict) or message.get('e') != 'kline':
        raise DataError('Evento WebSocket inválido.')
    k = message.get('k')
    if not isinstance(k, dict) or message.get('s') != symbol.replace('/', '') or k.get('s') != symbol.replace('/', '') or k.get('i') != timeframe:
        raise DataError('Evento de outro par/timeframe.')
    if type(k.get('x')) is not bool:
        raise DataError('Marcador de fechamento inválido.')
    if not k['x']:
        return None
    event_ms = milliseconds(message.get('E')); opened = milliseconds(k.get('t'))
    if k.get('T') != opened + step - 1 or not opened + step <= event_ms <= received_ms or received_ms - event_ms > 120_000:
        raise DataError('Evento fechado futuro, antigo ou com horários inconsistentes.')
    try:
        values = []
        for key in ('o', 'h', 'l', 'c', 'v'):
            raw = k[key]
            if not isinstance(raw, str) or len(raw) > 64:
                raise ValueError
            values.append(float(raw))
    except (KeyError, ValueError, OverflowError):
        raise DataError('Valores do evento WebSocket inválidos.') from None
    return parse_row([opened, *values], step)


class ClosedSequence:
    """Only consecutive closed candles; recover gaps through REST before resuming."""
    def __init__(self, symbol, timeframe, previous=None):
        self.step = interval(symbol, timeframe)
        self.symbol = symbol; self.timeframe = timeframe; self.previous = previous
        if previous is not None:
            parse_row([previous.open_ms, previous.open, previous.high, previous.low, previous.close, previous.volume], self.step)

    def accept(self, message, received_ms):
        candle = parse_closed_event(message, self.symbol, self.timeframe, received_ms)
        if candle is None:
            return None
        if self.previous is not None:
            if candle == self.previous:
                return None
            if candle.open_ms != self.previous.open_ms + self.step:
                raise DataGapError('Sequência WebSocket divergente; recupere via REST antes de continuar.')
        self.previous = candle
        return candle


def stream_closed(symbol, timeframe, seconds=30, *, previous=None):
    """Bounded public WebSocket observation, three reconnects maximum.

    No callbacks to trading. Gap/conflict errors are terminal; network reconnect
    never silently skips a candle. UTC host clock must be synchronized.
    """
    interval(symbol, timeframe)
    if type(seconds) is not int or not 1 <= seconds <= 3600:
        raise DataError('Duração WebSocket deve ser de 1 a 3600 segundos.')
    try:
        from websockets.sync.client import connect
        from websockets.exceptions import ConnectionClosed, WebSocketException
    except ImportError:
        raise DataError('Instale requirements-spot-data.txt no ambiente Python escolhido.') from None
    sequence = ClosedSequence(symbol, timeframe, previous)
    deadline = time.monotonic() + seconds; failures = 0
    url = 'wss://stream.binance.com:9443/ws/' + symbol.replace('/', '').lower() + '@kline_' + timeframe
    while time.monotonic() < deadline:
        try:
            with connect(url, open_timeout=10, close_timeout=2, max_size=65536) as ws:
                while time.monotonic() < deadline:
                    try:
                        raw = ws.recv(timeout=min(5, max(.01, deadline-time.monotonic())))
                    except TimeoutError:
                        continue
                    try:
                        message = json.loads(raw)
                    except (ValueError, TypeError):
                        raise DataError('JSON WebSocket inválido.') from None
                    candle = sequence.accept(message, int(time.time()*1000))
                    if candle is not None:
                        yield candle
        except (OSError, ConnectionClosed):
            failures += 1
            if failures > 3:
                raise DataError('Reconexões WebSocket esgotadas.') from None
            time.sleep(min(2 ** (failures-1), max(0, deadline-time.monotonic())))
        except WebSocketException:
            raise DataError('Conexão WebSocket recusada ou protocolo inválido.') from None


def save_history(history, folder):
    """Unique CSV + integrity manifest; never overwrites existing evidence."""
    folder = Path(folder); folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    path = folder / (history.symbol.replace('/', '-') + '-' + history.timeframe + '-' + stamp + '-' + uuid.uuid4().hex + '.csv')
    buffer = io.StringIO(newline='')
    writer = csv.writer(buffer, lineterminator='\n')
    writer.writerow(['open_ms','open_utc','close_exclusive_utc','open','high','low','close','volume'])
    step = STEPS[history.timeframe]
    for c in history.candles:
        writer.writerow([c.open_ms, datetime.fromtimestamp(c.open_ms/1000, timezone.utc).isoformat(),
                         datetime.fromtimestamp((c.open_ms+step)/1000, timezone.utc).isoformat(), c.open,c.high,c.low,c.close,c.volume])
    raw = buffer.getvalue().encode('utf-8')
    with path.open('xb') as output:
        output.write(raw)
    manifest = {k:v for k,v in asdict(history).items() if k != 'candles'}
    manifest.update(count=len(history.candles), csv_sha256=hashlib.sha256(raw).hexdigest(),
                    source='Binance public Spot / CCXT', collected_utc=stamp, approved=False,
                    note='Candles históricos não reproduzem fila, spread, latência ou disponibilidade histórica da informação.')
    with path.with_suffix('.json').open('x',encoding='utf-8') as output:
        json.dump(manifest,output,ensure_ascii=False,indent=2,allow_nan=False)
    return path


def main():
    import argparse
    from .config import load_settings, ConfigError
    parser = argparse.ArgumentParser(description='Somente dados públicos Spot; nenhuma ordem.')
    parser.add_argument('--years',type=int,help='Janela de coleta: mínimo 2, máximo 20 anos')
    parser.add_argument('--stream-seconds',type=int,help='Observação WebSocket, 1 a 3600 segundos; não baixa histórico')
    args=parser.parse_args()
    try:
        settings=load_settings()
        if args.years is not None and (not 2 <= args.years <= 20 or args.stream_seconds is not None):
            raise DataError('Use --years entre 2 e 20, separado da observação WebSocket.')
        if args.stream_seconds is not None:
            count=0
            for candle in stream_closed(settings.symbol,settings.timeframe,args.stream_seconds):
                count+=1;print(json.dumps(asdict(candle)),flush=True)
            print(f'Observação encerrada: {count} candles fechados recebidos. Zero é possível em amostras curtas.')
            return
        client=PublicBinance();end=milliseconds(retry(client.fetch_time))//STEPS[settings.timeframe]*STEPS[settings.timeframe]
        date=datetime.fromtimestamp(end/1000,timezone.utc);years=args.years or settings.history_years
        try:start=date.replace(year=date.year-years)
        except ValueError:start=date.replace(year=date.year-years,day=28)
        history=download(client,settings.symbol,settings.timeframe,int(start.timestamp()*1000),end)
        path=save_history(history,Path(__file__).resolve().parent.parent/'reports/local/spot-data')
        print(f'{len(history.candles)} candles fechados; {history.pages} páginas; CSV: {path}')
        print('Integridade conferida; nenhuma validação de estratégia ou ordem executada.')
    except (DataError,ConfigError) as error:
        raise SystemExit(str(error)) from None
    except KeyboardInterrupt:
        raise SystemExit('Coleta interrompida; nenhum conjunto parcial aprovado.') from None


if __name__ == '__main__':
    main()
