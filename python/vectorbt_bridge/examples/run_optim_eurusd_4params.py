"""
Optimización EURUSD MA Cross con 4 parámetros + Walk-Forward + spread realista.

Params optimizados:
- EMA_Fast: 3, 5, 8
- SMA_Slow: 21, 34, 55
- SL_ATR_Mult: 0.5, 1.0, 1.5
- RR: 1.5, 2.0, 3.0

Total: 3×3×3×3 = 81 combos (× 2 IS+OOS = 162 backtests)
Tiempo estimado: ~2-3 min

Ejecutar:
    python -X utf8 -m vectorbt_bridge.examples.run_optim_gbpusd_4params
"""
import sys
import time
import warnings
from pathlib import Path
import pandas as pd

warnings.simplefilter("ignore", FutureWarning)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from strategies.ma_cross_m15 import add_indicators, run_backtest, DEFAULT_PARAMS

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
INIT_CASH = 15000
PIP_VAL = 10.0
LOT_TYPICAL = 0.5
SPREAD_PIPS = 1.5
COST_PER_TRADE_USD = SPREAD_PIPS * PIP_VAL * LOT_TYPICAL

# Grids
EMA_GRID = [3, 5, 8]
SMA_GRID = [21, 34, 55]
SL_GRID = [0.5, 1.0, 1.5]
RR_GRID = [1.5, 2.0, 3.0]


def load(filename: str, start: str, end: str) -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / filename, parse_dates=["time"]).set_index("time")
    return df[(df.index >= start) & (df.index <= end)]


def backtest(df: pd.DataFrame, ema: int, sma: int, sl_mult: float, rr: float) -> dict:
    p = dict(DEFAULT_PARAMS)
    p["EMA_Fast"] = ema
    p["SMA_Slow"] = sma
    p["Dir_EMA_Fast"] = ema
    p["Dir_SMA_Slow"] = sma
    p["SL_ATR_Mult"] = sl_mult
    p["RR"] = rr

    df_ind = add_indicators(df.copy(), p)
    trades = run_backtest(df_ind, p, initial_capital=INIT_CASH, pip_val=PIP_VAL)
    if trades is None or len(trades) == 0:
        return {"PF": 0, "DD%": 0, "NetReturn%": 0, "NTrades": 0}

    pnl_adj = trades["pnl"] - COST_PER_TRADE_USD
    wins = pnl_adj[pnl_adj > 0].sum()
    losses = abs(pnl_adj[pnl_adj < 0].sum())
    pf = wins / losses if losses > 0 else 0
    equity = INIT_CASH + pnl_adj.cumsum()
    peak = equity.cummax()
    dd = abs(((equity - peak) / peak).min()) * 100
    return {
        "PF": round(pf, 3),
        "DD%": round(dd, 1),
        "NetReturn%": round(pnl_adj.sum() / INIT_CASH * 100, 1),
        "NTrades": len(trades),
    }


def main():
    print("=" * 80)
    print("  EURUSD MA Cross — Optimización 4 params (EMA × SMA × SL × RR)")
    print(f"  IS 2018-2022 + OOS 2023-2024 | Spread {SPREAD_PIPS} pips realista")
    print("=" * 80)

    df_is = load("EURUSD_M15_histdata.csv", "2018-01-01", "2022-12-31")
    df_oos = load("EURUSD_M15_histdata.csv", "2023-01-01", "2024-12-31")
    print(f"  IS: {len(df_is):,} filas | OOS: {len(df_oos):,} filas")

    combos = [(e, s, sl, rr) for e in EMA_GRID for s in SMA_GRID if e < s for sl in SL_GRID for rr in RR_GRID]
    print(f"  Total combos: {len(combos)}")

    results = []
    t0 = time.time()
    for i, (ema, sma, sl, rr) in enumerate(combos, 1):
        m_is = backtest(df_is, ema, sma, sl, rr)
        m_oos = backtest(df_oos, ema, sma, sl, rr)
        wf = m_oos["PF"] / m_is["PF"] if m_is["PF"] > 0 else 0
        results.append({
            "EMA_Fast": ema, "SMA_Slow": sma, "SL_ATR_Mult": sl, "RR": rr,
            "PF_IS": m_is["PF"], "PF_OOS": m_oos["PF"], "WF_ratio": round(wf, 3),
            "DD_IS%": m_is["DD%"], "DD_OOS%": m_oos["DD%"],
            "NetReturn_IS%": m_is["NetReturn%"], "NetReturn_OOS%": m_oos["NetReturn%"],
            "Trades_IS": m_is["NTrades"], "Trades_OOS": m_oos["NTrades"],
        })
        if i % 10 == 0:
            print(f"    [{i}/{len(combos)}]  {time.time()-t0:.0f}s")

    elapsed = time.time() - t0
    df = pd.DataFrame(results)
    print(f"\n  Completado: {len(combos)} combos en {elapsed:.0f}s ({elapsed/len(combos):.2f}s/combo)")

    # Checklist 7 puntos simplificado
    df["pasa_WF"] = df["WF_ratio"] >= 0.85
    df["pasa_DD"] = df["DD_OOS%"] <= 2 * df["DD_IS%"]
    df["pasa_trades"] = (df["Trades_IS"] >= 200) & (df["Trades_OOS"] >= 100)
    df["pasa_OOS_pos"] = df["NetReturn_OOS%"] > 0
    df["pasa_DD_real"] = df["DD_OOS%"] <= 15  # límite cuentas fondeo
    df["VALIDADO"] = df["pasa_WF"] & df["pasa_DD"] & df["pasa_trades"] & df["pasa_OOS_pos"] & df["pasa_DD_real"]

    n_val = df["VALIDADO"].sum()
    print(f"\n  Combos VALIDADOS (5 filtros incl DD<15%): {n_val}/{len(df)}")

    if n_val > 0:
        df_val = df[df["VALIDADO"]].sort_values("PF_OOS", ascending=False)
        print("\n  TOP 10 VALIDADOS por PF_OOS:")
        print(df_val.head(10)[["EMA_Fast", "SMA_Slow", "SL_ATR_Mult", "RR", "PF_IS", "PF_OOS", "WF_ratio", "DD_OOS%", "NetReturn_OOS%", "Trades_OOS"]].to_string(index=False))
    else:
        print("\n  Ningún combo pasa los 5 filtros. Top 5 por PF_OOS sin filtrar:")
        print(df.sort_values("PF_OOS", ascending=False).head(5)[["EMA_Fast", "SMA_Slow", "SL_ATR_Mult", "RR", "PF_IS", "PF_OOS", "WF_ratio", "DD_OOS%", "NetReturn_OOS%"]].to_string(index=False))

    out_dir = Path(__file__).resolve().parents[2] / "vectorbt_bridge" / "output"
    df.to_csv(out_dir / "optim_eurusd_4params_WF.csv", index=False)
    print(f"\n  Guardado: {out_dir/'optim_eurusd_4params_WF.csv'}")


if __name__ == "__main__":
    main()
