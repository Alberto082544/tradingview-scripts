"""
Migración de AUDNZD Ranger-C Stoch a VectorBT — prueba de concepto.

Compara:
- Engine custom Python actual (strategies.ranger_c_audnzd_stoch.run_backtest)
- VectorBT con las mismas señales

Mide:
- Speedup (segundos engine vs segundos VectorBT)
- Coincidencia de métricas (PF, DD, N trades, PnL)
- Resultado de optimización 42 combos (Stoch_Long_Max × SL_ATR_Mult)

Ejecutar desde /python:
    python -m vectorbt_bridge.examples.run_audnzd_vbt
"""
import sys
import time
from pathlib import Path
import numpy as np
import pandas as pd

# Permitir imports del proyecto
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import vectorbt as vbt
from strategies.ranger_c_audnzd_stoch import (
    add_indicators,
    run_backtest,
    compute_metrics,
    DEFAULT_PARAMS,
    PIP,
    NZDUSD,
)


DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "AUDNZD_M15_histdata.csv"


def load_data(start: str = "2018-01-01", end: str = "2024-12-31") -> pd.DataFrame:
    print(f"\n[1] Cargando datos AUDNZD M15 del CSV…")
    df = pd.read_csv(DATA_FILE, parse_dates=["time"]).set_index("time")
    df = df[(df.index >= start) & (df.index <= end)]
    print(f"    Filas: {len(df):,}  ·  Periodo: {df.index[0]} → {df.index[-1]}")
    return df


def build_signals(df_ind: pd.DataFrame, params: dict) -> tuple:
    """Genera 4 arrays booleanos a partir del DataFrame con indicadores.

    Returns:
        long_entries, long_exits, short_entries, short_exits
    """
    p = params
    rsi_confirm = p.get("RSI_Confirm", 1)
    stoch_mode = p.get("StochMode", 0)

    rsi = df_ind["rsi"]
    rsi_prev = rsi.shift(1)
    sk = df_ind["stoch_k"]
    sd = df_ind["stoch_d"]
    bb_lo = df_ind["bb_lower"]
    bb_up = df_ind["bb_upper"]
    adx = df_ind["adx_h4"]
    close_prev = df_ind["close"].shift(1)

    # Filtros
    rsi_ok_long = (rsi < p["RSI_Long_Max"]) & ((not rsi_confirm) | (rsi > rsi_prev))
    rsi_ok_short = (rsi > p["RSI_Short_Min"]) & ((not rsi_confirm) | (rsi < rsi_prev))
    stoch_ok_long = sk.notna() & (sk < p.get("Stoch_Long_Max", 25)) & (sk > sd)
    stoch_ok_short = sk.notna() & (sk > p.get("Stoch_Short_Min", 75)) & (sk < sd)

    if stoch_mode == 0:
        ok_long, ok_short = rsi_ok_long, rsi_ok_short
    elif stoch_mode == 1:
        ok_long, ok_short = stoch_ok_long, stoch_ok_short
    else:
        ok_long = rsi_ok_long & stoch_ok_long
        ok_short = rsi_ok_short & stoch_ok_short

    # Filtros adicionales del engine
    adx_ok = adx.notna() & (adx < p["ADX_H4_Max"])
    hour_ok = df_ind.index.hour.to_series(index=df_ind.index).between(
        p["SessionStart"], p["SessionEnd"] - 1
    )
    bad_hour_ok = df_ind.index.hour.to_series(index=df_ind.index) != p["BadHour"]
    weekday_ok = df_ind.index.weekday.to_series(index=df_ind.index) < 5

    long_entries = (
        (close_prev <= bb_lo.shift(1) * 1.001)
        & ok_long.shift(1).fillna(False)
        & adx_ok.shift(1).fillna(False)
        & hour_ok
        & bad_hour_ok
        & weekday_ok
    )
    short_entries = (
        (close_prev >= bb_up.shift(1) * 0.999)
        & ok_short.shift(1).fillna(False)
        & adx_ok.shift(1).fillna(False)
        & hour_ok
        & bad_hour_ok
        & weekday_ok
        & ~long_entries  # no abrir corto si ya hay largo
    )

    # Exits = ExitBars de timing (los SL/TP los maneja VectorBT con sl_stop/tp_stop)
    long_exits = pd.Series(False, index=df_ind.index)
    short_exits = pd.Series(False, index=df_ind.index)

    return long_entries.astype(bool), long_exits, short_entries.astype(bool), short_exits


def run_vectorbt(df_ind: pd.DataFrame, params: dict, init_cash: float = 15000) -> vbt.Portfolio:
    long_e, long_x, short_e, short_x = build_signals(df_ind, params)

    # SL dinámico en % del precio
    atr = df_ind["atr"]
    sl_pips = (atr * params["SL_ATR_Mult"]).clip(lower=params["MinSLPips"] * PIP)
    sl_stop = sl_pips / df_ind["close"]
    sl_stop = sl_stop.fillna(0.01).clip(0.001, 0.05)  # entre 0,1% y 5%

    # Exit por tiempo: forzar exit ExitBars después de cada entrada
    exit_bars = params["ExitBars"]
    long_x = long_e.shift(exit_bars).fillna(False).astype(bool)
    short_x = short_e.shift(exit_bars).fillna(False).astype(bool)

    pf = vbt.Portfolio.from_signals(
        close=df_ind["close"],
        entries=long_e,
        exits=long_x,
        short_entries=short_e,
        short_exits=short_x,
        sl_stop=sl_stop,
        init_cash=init_cash,
        fees=0.00003,
        slippage=0.00005,
        freq="15T",
    )
    return pf


def compare_engines(df: pd.DataFrame, params: dict):
    print("\n[2] Calculando indicadores (shared engine)…")
    t0 = time.time()
    df_ind = add_indicators(df.copy(), params)
    t_ind = time.time() - t0
    print(f"    Indicadores: {t_ind:.2f}s")

    print("\n[3] Ejecutando engine Python custom…")
    t0 = time.time()
    trades_custom = run_backtest(df_ind, params, initial_capital=15000)
    t_custom = time.time() - t0
    metrics_custom = compute_metrics(trades_custom, initial_capital=15000)
    print(f"    Engine custom: {t_custom:.2f}s")
    print(f"    Métricas: {metrics_custom}")

    print("\n[4] Ejecutando VectorBT…")
    t0 = time.time()
    pf = run_vectorbt(df_ind, params, init_cash=15000)
    t_vbt = time.time() - t0
    print(f"    VectorBT: {t_vbt:.2f}s")

    stats = pf.stats()
    print(f"    PF: {stats.get('Profit Factor', 'n/a')}")
    print(f"    DD%: {stats.get('Max Drawdown [%]', 'n/a')}")
    print(f"    N trades: {stats.get('Total Trades', 'n/a')}")
    print(f"    Net Profit: {stats.get('Total Return [%]', 'n/a')}")

    print(f"\n→ Speedup VectorBT vs Python custom: {t_custom / max(t_vbt, 1e-6):.1f}×")
    return t_custom, t_vbt, metrics_custom, stats


def optimize_grid(df_ind: pd.DataFrame, init_cash: float = 15000):
    """Grid 6×7 = 42 combos (Stoch_Long_Max × SL_ATR_Mult) — mismo que probamos en MT5."""
    print("\n[5] Optimización 42 combos (Stoch × SL_ATR) con VectorBT…")
    stoch_grid = [5, 10, 15, 20, 25, 30]
    sl_grid = [1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5]

    results = []
    t0 = time.time()
    for stoch in stoch_grid:
        for sl in sl_grid:
            params = dict(DEFAULT_PARAMS)
            params["Stoch_Long_Max"] = stoch
            params["SL_ATR_Mult"] = sl
            params["StochMode"] = 2  # usar Stoch + RSI (como en MT5)
            pf = run_vectorbt(df_ind, params, init_cash=init_cash)
            stats = pf.stats()
            results.append({
                "Stoch_Long_Max": stoch,
                "SL_ATR_Mult": sl,
                "PF": stats.get("Profit Factor", 0),
                "DD%": stats.get("Max Drawdown [%]", 0),
                "Trades": stats.get("Total Trades", 0),
                "NetProfit": stats.get("Total Return [%]", 0),
            })
    t_total = time.time() - t0
    df_res = pd.DataFrame(results).sort_values("PF", ascending=False)
    print(f"\n    {len(results)} combos en {t_total:.2f}s ({t_total/len(results):.3f}s/combo)")
    print("\n    TOP 5 por PF:")
    print(df_res.head(5).to_string(index=False))
    print("\n    BOTTOM 3 por PF:")
    print(df_res.tail(3).to_string(index=False))
    return df_res


if __name__ == "__main__":
    print("=" * 60)
    print(" Migración AUDNZD Ranger-C Stoch → VectorBT")
    print(" Prueba de concepto + comparativa de velocidad")
    print("=" * 60)

    df = load_data(start="2018-01-01", end="2024-12-31")

    # Step 1: comparar engine custom vs VectorBT con params default
    params = dict(DEFAULT_PARAMS)
    params["StochMode"] = 2  # como en MT5
    t_custom, t_vbt, metrics_custom, stats_vbt = compare_engines(df, params)

    # Step 2: grid 42 combos (igual que MT5)
    df_ind = add_indicators(df.copy(), params)
    df_results = optimize_grid(df_ind)

    # Guardar resultados
    out_dir = Path(__file__).resolve().parents[2] / "vectorbt_bridge" / "output"
    out_dir.mkdir(exist_ok=True)
    out_file = out_dir / "audnzd_grid_2018_2024.csv"
    df_results.to_csv(out_file, index=False)
    print(f"\n[6] Resultados guardados en: {out_file}")

    print("\n" + "=" * 60)
    print(" RESUMEN")
    print("=" * 60)
    print(f" Engine custom (1 backtest): {t_custom:.2f}s")
    print(f" VectorBT      (1 backtest): {t_vbt:.2f}s")
    print(f" Speedup:                    {t_custom/max(t_vbt,1e-6):.1f}×")
    print(f" Grid 42 combos VectorBT:    ver CSV")
    print("=" * 60)
