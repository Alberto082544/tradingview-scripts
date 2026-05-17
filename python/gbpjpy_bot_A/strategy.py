"""
GBPJPY Bot — Lógica de señales
Pullback en tendencia con filtro EMA200 H4
"""
import pandas as pd
import numpy as np
from config import (RSI_PERIOD, EMA_FAST, EMA_SLOW, EMA_H4,
                    ATR_PERIOD, PULLBACK_RATIO)


def _ema(series: pd.Series, period: int) -> pd.Series:
    alpha = 2.0 / (period + 1)
    result = pd.Series(np.nan, index=series.index, dtype=float)
    result.iloc[period - 1] = series.iloc[:period].mean()
    for i in range(period, len(series)):
        result.iloc[i] = alpha * series.iloc[i] + (1 - alpha) * result.iloc[i - 1]
    return result


def _atr(df: pd.DataFrame, period: int) -> pd.Series:
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - df["close"].shift(1)).abs(),
        (df["low"]  - df["close"].shift(1)).abs(),
    ], axis=1).max(axis=1)
    result = pd.Series(np.nan, index=df.index, dtype=float)
    result.iloc[period - 1] = tr.iloc[:period].mean()
    for i in range(period, len(tr)):
        result.iloc[i] = (result.iloc[i - 1] * (period - 1) + tr.iloc[i]) / period
    return result


def _rsi(series: pd.Series, period: int) -> pd.Series:
    delta = series.diff()
    gain  = delta.clip(lower=0)
    loss  = (-delta).clip(lower=0)
    avg_g = pd.Series(np.nan, index=series.index, dtype=float)
    avg_l = pd.Series(np.nan, index=series.index, dtype=float)
    avg_g.iloc[period] = gain.iloc[1:period + 1].mean()
    avg_l.iloc[period] = loss.iloc[1:period + 1].mean()
    for i in range(period + 1, len(series)):
        avg_g.iloc[i] = (avg_g.iloc[i - 1] * (period - 1) + gain.iloc[i]) / period
        avg_l.iloc[i] = (avg_l.iloc[i - 1] * (period - 1) + loss.iloc[i]) / period
    rs = avg_g / avg_l.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def add_indicators(df_m15: pd.DataFrame, df_h4: pd.DataFrame) -> pd.DataFrame:
    df = df_m15.copy()

    # Indicadores M15
    df["ema_fast"]     = _ema(df["close"], EMA_FAST)
    df["ema_slow"]     = _ema(df["close"], EMA_SLOW)
    df["rsi14"]        = _rsi(df["close"], RSI_PERIOD)
    df["atr14"]        = _atr(df, ATR_PERIOD)
    df["ema_slope"]    = df["ema_fast"] - df["ema_fast"].shift(5)
    df["range_high20"] = df["high"].rolling(20).max()
    df["range_low20"]  = df["low"].rolling(20).min()
    df["range_size"]   = df["range_high20"] - df["range_low20"]
    df["swing_low10"]  = df["low"].rolling(10).min()
    df["swing_high10"] = df["high"].rolling(10).max()

    # EMA200 H4 mapeada al M15
    h4 = df_h4.copy()
    h4["ema200_h4"] = _ema(h4["close"], EMA_H4)
    df = pd.merge_asof(df, h4[["ema200_h4"]],
                       left_index=True, right_index=True, direction="backward")
    return df


def generate_signals(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()

    pullback_long  = d["range_low20"].shift(1)  + d["range_size"].shift(1) * PULLBACK_RATIO
    pullback_short = d["range_high20"].shift(1) - d["range_size"].shift(1) * PULLBACK_RATIO

    # Condición LONG
    cond_long = (
        (d["close"].shift(1) > d["ema200_h4"].shift(1)) &
        (d["ema_fast"].shift(1) > d["ema_slow"].shift(1)) &
        (d["ema_slope"].shift(1) > 0) &
        (d["rsi14"].shift(1) >= 35) & (d["rsi14"].shift(1) <= 60) &
        (d["rsi14"].shift(1) > d["rsi14"].shift(2)) &
        (d["close"].shift(1) <= pullback_long * 1.002)
    )

    # Condición SHORT
    cond_short = (
        (d["close"].shift(1) < d["ema200_h4"].shift(1)) &
        (d["ema_fast"].shift(1) < d["ema_slow"].shift(1)) &
        (d["ema_slope"].shift(1) < 0) &
        (d["rsi14"].shift(1) >= 40) & (d["rsi14"].shift(1) <= 65) &
        (d["rsi14"].shift(1) < d["rsi14"].shift(2)) &
        (d["close"].shift(1) >= pullback_short * 0.998)
    ) & ~cond_long

    d["long_signal"]  = cond_long
    d["short_signal"] = cond_short
    d["entry_price"]  = np.where(d["long_signal"] | d["short_signal"], d["open"], np.nan)

    # Stop Loss: distancia al swing reciente (min 1xATR)
    sl_long  = d["close"].shift(1) - d["swing_low10"].shift(1)
    sl_short = d["swing_high10"].shift(1) - d["close"].shift(1)
    d["sl"]  = np.where(d["long_signal"], sl_long,
               np.where(d["short_signal"], sl_short, d["atr14"] * 1.5))
    d["sl"]  = d[["sl", "atr14"]].max(axis=1)
    d["tp"]  = d["sl"] * 3.0  # referencia (se usa TP_MULT de config en backtest)

    return d
