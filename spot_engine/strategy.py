"""Causal, incremental EMA/ATR signals. No account access or order submission."""
from dataclasses import asdict, dataclass
import math
from .config import Settings
from .data import Candle, History, interval, milliseconds, DataError


class StrategyError(ValueError):
    pass


@dataclass(frozen=True)
class Signal:
    symbol: str
    timeframe: str
    candle_open_ms: int
    decision_ms: int
    action: str
    reason: str
    ready: bool
    bars: int
    ema_fast: float
    ema_slow: float
    ema_trend: float
    atr: float | None
    atr_fraction: float | None


@dataclass(frozen=True)
class _State:
    bars: int = 0
    last: Candle | None = None
    cutoff: int | None = None
    fast: float | None = None
    slow: float | None = None
    trend: float | None = None
    atr_seed: tuple[float, ...] = ()
    atr: float | None = None


class EmaAtrStrategy:
    """One closed candle per update. Invalid inputs never mutate indicators.

    EMA starts at the first close, alpha=2/(period+1), adjust=False.
    ATR seeds with the mean of n true ranges, then uses Wilder smoothing.
    Minimum warm-up: 3*trend period and ATR seed. No parameter optimization.
    """
    def __init__(self, settings: Settings):
        if not isinstance(settings, Settings):
            raise StrategyError('Configuração validada obrigatória.')
        self.settings = settings
        self.step = interval(settings.symbol, settings.timeframe)
        self.warmup_bars = max(3*settings.ema_trend, settings.atr_period+1)
        self._state = _State()

    def update(self, candle: Candle, *, as_of_ms: int) -> Signal:
        s = self._state; cfg = self.settings
        try:
            milliseconds(as_of_ms)
        except DataError:
            raise StrategyError('Instante de decisão inválido.') from None
        if not isinstance(candle, Candle):
            raise StrategyError('Candle validado obrigatório.')
        if candle.open_ms % self.step or candle.open_ms+self.step > as_of_ms:
            raise StrategyError('Candle desalinhado, futuro ou ainda em formação.')
        if s.last is not None and candle.open_ms != s.last.open_ms+self.step:
            raise StrategyError('Candle duplicado, fora de ordem ou com lacuna; estado preservado.')
        if s.cutoff is not None and as_of_ms < s.cutoff:
            raise StrategyError('Relógio de decisão retrocedeu; estado preservado.')
        def ema(previous, period):
            alpha = 2/(period+1)
            return candle.close if previous is None else (1-alpha)*previous+alpha*candle.close
        fast = ema(s.fast,cfg.ema_fast); slow = ema(s.slow,cfg.ema_slow); trend = ema(s.trend,cfg.ema_trend)
        tr = candle.high-candle.low if s.last is None else max(candle.high-candle.low,abs(candle.high-s.last.close),abs(candle.low-s.last.close))
        seed = s.atr_seed; atr = s.atr
        if atr is None:
            seed = seed+(tr,)
            if len(seed) == cfg.atr_period:
                atr = math.fsum(x/cfg.atr_period for x in seed); seed = ()
        else:
            atr = (1-1/cfg.atr_period)*atr+tr/cfg.atr_period
        fraction = atr/candle.close if atr is not None else None
        if any(not math.isfinite(x) for x in (fast,slow,trend,tr)) or (atr is not None and (not math.isfinite(atr) or not math.isfinite(fraction))):
            raise StrategyError('Indicadores excedem limite numérico; estado preservado.')
        bars = s.bars+1
        ready = bars >= self.warmup_bars and atr is not None
        action,reason = 'HOLD','WARMUP' if not ready else 'NO_CROSS'
        if ready:
            crossed_up = s.fast <= s.slow and fast > slow
            crossed_down = s.fast >= s.slow and fast < slow
            if crossed_down:
                # Exit intent is not blocked by an entry volatility filter.
                action,reason = 'EXIT_LONG','EMA_CROSS_DOWN'
            elif crossed_up:
                if candle.close <= trend:
                    reason = 'TREND_FILTER'
                elif not float(cfg.atr_min_fraction) <= fraction <= float(cfg.atr_max_fraction):
                    reason = 'ATR_FILTER'
                else:
                    action,reason = 'ENTER_LONG','EMA_CROSS_UP'
        result = Signal(cfg.symbol,cfg.timeframe,candle.open_ms,as_of_ms,action,reason,ready,bars,
                        fast,slow,trend,atr,fraction)
        self._state = _State(bars,candle,as_of_ms,fast,slow,trend,seed,atr)
        return result


def analyze(history: History, settings: Settings) -> tuple[Signal, ...]:
    """Historical signal scan, NOT a backtest or historical latency reconstruction."""
    if history.symbol != settings.symbol or history.timeframe != settings.timeframe:
        raise StrategyError('Histórico não corresponde à configuração.')
    strategy = EmaAtrStrategy(settings)
    return tuple(strategy.update(c,as_of_ms=c.open_ms+strategy.step) for c in history.candles)


def main():
    import argparse
    import hashlib
    import json
    from pathlib import Path
    import uuid
    from .config import ConfigError, load_settings
    from .data import load_history
    parser=argparse.ArgumentParser(description='Inspeção histórica de sinais; nenhuma ordem ou PNL calculado.')
    parser.add_argument('--csv',type=Path,required=True,help='CSV do coletor com manifesto JSON ao lado')
    args=parser.parse_args()
    try:
        cfg=load_settings();history=load_history(args.csv);signals=analyze(history,cfg)
        summary={'symbol':cfg.symbol,'timeframe':cfg.timeframe,'candles':len(signals),
                 'warmup_bars':EmaAtrStrategy(cfg).warmup_bars,
                 'entry_intents':sum(s.action=='ENTER_LONG' for s in signals),
                 'exit_intents':sum(s.action=='EXIT_LONG' for s in signals),
                 'source_csv_sha256':hashlib.sha256(args.csv.read_bytes()).hexdigest(),
                 'strategy_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                 'settings':{k:str(v) for k,v in asdict(cfg).items()},
                 'approved':False,'orders':0,'pnl':None,
                 'scope':'Inspeção exploratória de sinais históricos. Não é backtest, treino/teste reservado ou validação de rentabilidade.'}
        folder=Path(__file__).resolve().parent.parent/'reports/local/spot-signals';folder.mkdir(parents=True,exist_ok=True)
        path=folder/(uuid.uuid4().hex+'.json')
        with path.open('x',encoding='utf-8') as output:json.dump(summary,output,ensure_ascii=False,indent=2,allow_nan=False)
        print(json.dumps(summary,ensure_ascii=False,indent=2));print('Resumo preservado: '+str(path))
    except (StrategyError,DataError,ConfigError,OSError):
        raise SystemExit('Inspeção recusada: confira configuração, CSV/manifesto e integridade dos candles. Nenhuma ordem enviada.') from None


if __name__=='__main__':
    main()
