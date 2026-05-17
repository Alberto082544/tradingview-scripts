"""
ORB Multi-Asset Optimizer
=========================
Grid search sobre sesión, dirección, TP1, TP2, rango min/max.
Soporta múltiples activos si se dispone de sus CSVs M1.
"""
import sys, os, itertools, types, warnings
import pandas as pd
import numpy as np
warnings.filterwarnings('ignore')
# Encoding manejado por PYTHONIOENCODING=utf-8

from strategy import add_indicators, generate_signals
from backtest import run_backtest

# ─── Activos a testear ────────────────────────────────────────────────────────
# pip     : tamaño de 1 pip en precio
# pip_usd : USD por pip por lote estándar
# fmt     : "dukascopy_nohdr" (GBPJPY) | "dukascopy_hdr" (XAUUSD con cabecera)
ASSETS = {
    "GBPJPY": {
        "csv": r"C:\Users\alber\OneDrive\Desktop\Nueva carpeta\GBPJPY_M1_dukas.csv",
        "pip": 0.01,
        "pip_usd": 6.9,
        "fmt": "dukascopy_nohdr",
        "min_rng": [5, 10, 15],
        "max_rng": [30, 50],
    },
    "XAUUSD": {
        "csv": r"C:\Users\alber\OneDrive\Desktop\Nueva carpeta\2026.5.8XAUUSD_M1_dukas-M1-No Session.csv",
        "pip": 0.1,       # 1 pip XAU = $0.10
        "pip_usd": 10.0,  # $10 por pip por lote estándar (100 oz × $0.10)
        "fmt": "dukascopy_hdr",
        "min_rng": [20, 30, 50],    # pips = $2, $3, $5
        "max_rng": [150, 250],      # pips = $15, $25
    },
    # "EURUSD": {
    #     "csv": r"C:\ruta\a\EURUSD_M1_dukas.csv",
    #     "pip": 0.0001,
    #     "pip_usd": 10.0,
    #     "fmt": "dukascopy_nohdr",
    #     "min_rng": [5, 10],
    #     "max_rng": [30, 60],
    # },
}

START_YEAR, START_MONTH = 2020, 1
END_YEAR,   END_MONTH   = 2025, 12
INITIAL_CAPITAL         = 50_000.0

# ─── Grid de parámetros ───────────────────────────────────────────────────────
GRID = {
    "SESSION":        ["NY", "LONDON", "BOTH"],
    "DIRECTION":      ["BOTH", "LONG_ONLY", "SHORT_ONLY"],
    "TP1_MULT":       [0.5, 1.0, 1.5],
    "TP2_MULT":       [2.0, 3.0, 4.0, 5.0],
    "MIN_RANGE_PIPS": [5, 10, 15],
    "MAX_RANGE_PIPS": [30, 50],
}

FIXED = {
    "NY_START_H": 13, "NY_START_M": 30, "NY_END_H": 20,
    "LDN_START_H": 8, "LDN_START_M": 0, "LDN_END_H": 16,
    "BE_OFFSET_PIPS": 0,
    "USE_DOUBLE_ENTRY": True,
    "CLOSE_EOS": True,
    "MAX_TRADES_DAY": 2,
    "MAX_LOTS": 4.0,
    "RISK_PCT": 0.01,
}


def load_m15(csv_path, start_year, start_month, end_year, end_month, fmt="dukascopy_nohdr"):
    from datetime import datetime
    if fmt == "dukascopy_hdr":
        # Formato con cabecera: Date,Time,Open,High,Low,Close,Volume
        # Date: YYYYMMDD  Time: HH:MM:SS
        df = pd.read_csv(csv_path, dtype={"Date": str, "Time": str})
        df.columns = [c.strip() for c in df.columns]
        df["datetime"] = pd.to_datetime(df["Date"] + " " + df["Time"],
                                        format="%Y%m%d %H:%M:%S")
        df = df.rename(columns={"Open":"open","High":"high","Low":"low",
                                 "Close":"close","Volume":"volume"})
    else:
        # Formato sin cabecera Dukascopy estándar
        df = pd.read_csv(csv_path, header=None,
            names=["date","time","open","high","low","close","volume","v2","sp"],
            dtype={"date":str,"time":str})
        df["datetime"] = pd.to_datetime(df["date"]+" "+df["time"], format="%Y.%m.%d %H:%M")

    df.set_index("datetime", inplace=True)
    df = df[["open","high","low","close","volume"]]
    df = df[(df.index >= datetime(start_year,start_month,1)) &
            (df.index <= datetime(end_year,end_month,31))]
    df_m15 = df.resample("15min").agg(
        {"open":"first","high":"max","low":"min","close":"last","volume":"sum"}
    ).dropna()
    return df_m15


def run_combo(df_m15, params, asset_info):
    cfg = types.SimpleNamespace(**{**FIXED, **params})
    cfg.DATA_PATH       = asset_info["csv"]
    cfg.INITIAL_CAPITAL = INITIAL_CAPITAL
    cfg._pip_usd        = asset_info["pip_usd"]   # usado por backtest
    cfg._pip            = asset_info["pip"]

    df = add_indicators(df_m15.copy())
    df = generate_signals(df, cfg)

    if df['long_signal'].sum() + df['short_signal'].sum() < 20:
        return None

    trades = run_backtest(df, cfg)
    if len(trades) < 20:
        return None

    wins   = (trades['pnl'] > 0).sum()
    losses = (trades['pnl'] <= 0).sum()
    wr     = wins / len(trades)
    gross_p = trades[trades['pnl'] > 0]['pnl'].sum()
    gross_l = abs(trades[trades['pnl'] <= 0]['pnl'].sum())
    pf     = gross_p / gross_l if gross_l > 0 else 0
    total  = trades['pnl'].sum()
    eq     = INITIAL_CAPITAL + trades['pnl'].cumsum()
    peak   = eq.cummax()
    dd     = ((peak - eq) / peak * 100).max()
    score  = (pf - 1.0) * 0.4 + (total / INITIAL_CAPITAL * 100) * 0.3 - dd * 0.3

    return {**params, "trades": len(trades), "wr": round(wr*100,1),
            "pf": round(pf,2), "pnl": round(total,0), "dd": round(dd,1),
            "score": round(score,3)}


def main():
    print("=" * 70)
    print("  ORB Multi-Asset Optimizer")
    print("=" * 70)

    all_results = []
    keys = list(GRID.keys())
    combos = list(itertools.product(*[GRID[k] for k in keys]))
    total  = len(combos) * len(ASSETS)
    done   = 0

    for asset_name, asset_info in ASSETS.items():
        if not os.path.exists(asset_info["csv"]):
            print(f"\n  [{asset_name}] CSV no encontrado: {asset_info['csv']}")
            continue

        print(f"\n  [{asset_name}] Cargando datos M1...")
        df_m15 = load_m15(asset_info["csv"], START_YEAR, START_MONTH, END_YEAR, END_MONTH,
                          fmt=asset_info.get("fmt","dukascopy_nohdr"))
        print(f"  [{asset_name}] {len(df_m15):,} barras M15")

        # Grid específico por activo
        asset_grid = {**GRID,
                      "MIN_RANGE_PIPS": asset_info.get("min_rng", GRID["MIN_RANGE_PIPS"]),
                      "MAX_RANGE_PIPS": asset_info.get("max_rng", GRID["MAX_RANGE_PIPS"])}
        asset_keys   = list(asset_grid.keys())
        asset_combos = list(itertools.product(*[asset_grid[k] for k in asset_keys]))
        print(f"  [{asset_name}] {len(asset_combos)} combinaciones")

        asset_results = []
        for combo_vals in asset_combos:
            params = dict(zip(asset_keys, combo_vals))
            if params["TP1_MULT"] >= params["TP2_MULT"]: continue
            if params["MIN_RANGE_PIPS"] >= params["MAX_RANGE_PIPS"]: continue

            result = run_combo(df_m15, params, asset_info)
            done += 1
            if result:
                result["asset"] = asset_name
                asset_results.append(result)
                all_results.append(result)

            if done % 100 == 0:
                profitable = sum(1 for r in asset_results if r and r.get("pnl", 0) > 0)
                print(f"  [{asset_name}] {done} hechas | Rentables: {profitable}")

        if asset_results:
            df_r = pd.DataFrame(asset_results)
            df_r = df_r.sort_values("score", ascending=False)
            print(f"\n  [{asset_name}] TOP 10 combinaciones:")
            print(df_r.head(10).to_string(index=False))
            os.makedirs("reports", exist_ok=True)
            df_r.to_csv(f"reports/orb_grid_{asset_name}.csv", index=False)
            print(f"  Guardado: reports/orb_grid_{asset_name}.csv")

    if all_results:
        df_all = pd.DataFrame(all_results).sort_values("score", ascending=False)
        df_all.to_csv("reports/orb_grid_ALL.csv", index=False)

        print("\n" + "=" * 70)
        print("  TOP 15 GLOBALES (todos los activos)")
        print("=" * 70)
        print(df_all.head(15).to_string(index=False))

        # Mejor por activo
        print("\n  MEJOR por activo:")
        for asset, grp in df_all.groupby("asset"):
            best = grp.iloc[0]
            print(f"  {asset:8s}: PF={best['pf']:.2f}  WR={best['wr']:.0f}%  "
                  f"P&L=${best['pnl']:+,.0f}  DD={best['dd']:.0f}%  "
                  f"Sess={best['SESSION']}  Dir={best['DIRECTION']}  "
                  f"TP1={best['TP1_MULT']}x  TP2={best['TP2_MULT']}x  "
                  f"Rng={best['MIN_RANGE_PIPS']}-{best['MAX_RANGE_PIPS']}p")

        print("\n  Resultados guardados en reports/orb_grid_ALL.csv")
    else:
        print("\n  Sin resultados. Verifica que los CSVs existen.")

    print("\n=== OPTIMIZACION COMPLETADA ===")


if __name__ == "__main__":
    main()
