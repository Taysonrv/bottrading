"""Validated settings only. Loading configuration never connects to an exchange."""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import os
import re
from typing import Mapping


class ConfigError(ValueError):
    """Safe error messages deliberately exclude supplied values and secrets."""


def number(env, name, default):
    raw = env.get('TRADING_' + name, default)
    try:
        if not isinstance(raw, str) or len(raw) > 64:
            raise ValueError
        value = Decimal(raw)
        if not value.is_finite():
            raise ValueError
        return value
    except (InvalidOperation, ValueError):
        raise ConfigError('Parâmetro numérico inválido: ' + name) from None


def integer(env, name, default):
    raw = env.get('TRADING_' + name, default)
    if not isinstance(raw, str) or not re.fullmatch(r'[0-9]{1,6}', raw):
        raise ConfigError('Parâmetro inteiro inválido: ' + name)
    return int(raw)


@dataclass(frozen=True)
class Settings:
    mode: str
    symbol: str
    timeframe: str
    capital: Decimal
    risk_per_trade: Decimal
    daily_loss_limit: Decimal
    max_drawdown: Decimal
    max_positions: int
    max_order_notional: Decimal
    stop_loss_fraction: Decimal
    take_profit_fraction: Decimal
    fee_rate: Decimal
    slippage_rate: Decimal
    latency_ms: int
    ema_fast: int
    ema_slow: int
    ema_trend: int
    atr_period: int
    atr_min_fraction: Decimal
    atr_max_fraction: Decimal
    history_years: int
    testnet_days: int
    timezone: str = 'UTC'
    strategy: str = 'ema_cross_atr'

    def __post_init__(self):
        # Direct construction must obey the same limits as environment loading.
        if self.mode not in ('backtest', 'paper'):
            raise ConfigError('Modo indisponível: execução live ainda não implementada/aprovada.')
        if not isinstance(self.symbol, str) or not re.fullmatch(r'[A-Z0-9]{2,15}/USDT', self.symbol):
            raise ConfigError('Par Spot inválido; use BASE/USDT.')
        if self.timeframe not in ('15m', '1h', '4h'):
            raise ConfigError('Timeframe permitido: 15m, 1h ou 4h.')
        for name in ('capital', 'risk_per_trade', 'daily_loss_limit', 'max_drawdown',
                     'max_order_notional', 'stop_loss_fraction', 'take_profit_fraction',
                     'fee_rate', 'slippage_rate', 'atr_min_fraction', 'atr_max_fraction'):
            value = getattr(self, name)
            if not isinstance(value, Decimal) or not value.is_finite():
                raise ConfigError('Decimal finito obrigatório: ' + name)
        if not Decimal('0') < self.capital <= Decimal('1000000000'):
            raise ConfigError('Capital fora do intervalo permitido.')
        for name, cap in (('risk_per_trade', '.01'), ('daily_loss_limit', '.03'), ('max_drawdown', '.10')):
            if not Decimal('0') < getattr(self, name) <= Decimal(cap):
                raise ConfigError('Limite de risco fora do intervalo: ' + name)
        if not Decimal('0') < self.max_order_notional <= self.capital:
            raise ConfigError('Teto por ordem deve ser positivo e não exceder o capital.')
        if not Decimal('0') < self.stop_loss_fraction < Decimal('1'):
            raise ConfigError('Stop loss positivo e inferior a 100% é obrigatório.')
        if not Decimal('0') < self.take_profit_fraction < Decimal('1'):
            raise ConfigError('Take profit fora do intervalo permitido.')
        if not Decimal('0') <= self.fee_rate <= Decimal('.05') or not Decimal('0') <= self.slippage_rate <= Decimal('.05'):
            raise ConfigError('Custos fora do intervalo permitido.')
        if not Decimal('0') <= self.atr_min_fraction < self.atr_max_fraction < Decimal('1'):
            raise ConfigError('Faixa de ATR inválida.')
        for name, lower, upper in (('max_positions', 1, 10), ('latency_ms', 0, 60000),
                                   ('ema_fast', 2, 1000), ('ema_slow', 3, 2000),
                                   ('ema_trend', 4, 5000), ('atr_period', 2, 1000),
                                   ('history_years', 2, 20), ('testnet_days', 14, 28)):
            value = getattr(self, name)
            if type(value) is not int or not lower <= value <= upper:
                raise ConfigError('Inteiro fora do intervalo: ' + name)
        if not self.ema_fast < self.ema_slow < self.ema_trend:
            raise ConfigError('Períodos exigem EMA rápida < lenta < tendência.')
        if self.timezone != 'UTC' or self.strategy != 'ema_cross_atr':
            raise ConfigError('Esta versão exige UTC e estratégia ema_cross_atr.')


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    """Read environment only; .env is not auto-loaded or written. No API keys needed."""
    env = os.environ if env is None else env
    values = {name: number(env, name.upper(), default) for name, default in {
        'capital': '20', 'risk_per_trade': '.01', 'daily_loss_limit': '.03',
        'max_drawdown': '.10', 'max_order_notional': '5', 'stop_loss_fraction': '.02',
        'take_profit_fraction': '.04', 'fee_rate': '.001', 'slippage_rate': '.001',
        'atr_min_fraction': '.001', 'atr_max_fraction': '.05'}.items()}
    values.update({name: integer(env, name.upper(), default) for name, default in {
        'max_positions': '1', 'latency_ms': '500', 'ema_fast': '20', 'ema_slow': '50',
        'ema_trend': '200', 'atr_period': '14', 'history_years': '2', 'testnet_days': '28'}.items()})
    return Settings(mode=env.get('TRADING_MODE', 'paper'), symbol=env.get('TRADING_SYMBOL', 'BTC/USDT'),
                    timeframe=env.get('TRADING_TIMEFRAME', '1h'), **values)


if __name__ == '__main__':
    try:
        settings = load_settings()
    except ConfigError as error:
        raise SystemExit(str(error)) from None
    print(f'Configuração válida: {settings.mode}, {settings.symbol}, {settings.timeframe}, capital fictício {settings.capital} USDT. Nenhum processo ou ordem iniciado.')
