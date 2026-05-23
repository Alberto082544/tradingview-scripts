"""
Optimización 2 params (EMA_Fast × SMA_Slow) para GBPUSD y EURUSD MA Cross.

Spread realista aplicado: 1.5 pips por trade.
Periodo IS: 2018-2022 (5 años). OOS: 2023-2024 (2 años).
Para cada combo: PF IS, PF OOS, WF ratio, DD%, NetReturn.

Ejecutar desde /python:
    python -X utf8 -m vectorbt_bridge.examples.run_optim_ma_cross
"""
import sys
import time
import warnings
from pathlib import Path
import pandas as pd

warnings.simplefilter("ignore", FutureWarning)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from strategies.ma_cross_m15 import add_indicators, run_backtest, compute_metrics, DEFAULT_PARAMS

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
INIT_CASH = 15000
PIP_VAL = 10.0
LOT_TYPICAL = 0.5
SPREAD_PIPS = 1.5
COST_PER_TRADE_USD = SPREAD_PIPS * PIP_VAL * LOT_TYPICAL  # 7.5 USD/trade

# Grid: EMA_Fast × SMA_Slow
EMA_FAST_GRID = [3, 5, 8, 13, 21]
SMA_SLOW_GRID = [21, 34, 55, 89, 144]


def load(filename: str, start: str, end: str) -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / filename, parse_dates=["time"]).set_index("time")
    return df[(df.index >= start) & (df.index <= end)]


def backtest_combo(df: pd.DataFrame, ema_fast: int, sma_slow: int) -> dict:
    p = dict(DEFAULT_PARAMS)
    p["EMA_Fast"] = ema_fast
    p["SMA_Slow"] = sma_slow
    p["Dir_EMA_Fast"] = ema_fast  # mantener consistencia H4
    p["Dir_SMA_Slow"] = sma_slow

    df_ind = add_indicators(df.copy(), p)
    trades = run_backtest(df_ind, p, initial_capital=INIT_CASH, pip_val=PIP_VAL)
    if trades is None or len(trades) == 0:
        return {"PF": 0, "DD%": 0, "NetPnL": 0, "NetReturn%": 0, "NTrades": 0, "WR%": 0}

    pnl_adj = trades["pnl"] - COST_PER_TRADE_USD
    wins = pnl_adj[pnl_adj > 0].sum()
    losses = abs(pnl_adj[pnl_adj < 0].sum())
    pf = wins / losses if losses > 0 else 0
    equity = INIT_CASH + pnl_adj.cumsum()
    peak = equity.cummax()
    dd_pct = abs(((equity - peak) / peak).min()) * 100
    return {
        "PF": round(pf, 3),
        "DD%": round(dd_pct, 1),
        "NetPnL": round(pnl_adj.sum(), 0),
        "NetReturn%": round(pnl_adj.sum() / INIT_CASH * 100, 1),
        "NTrades": len(trades),
        "WR%": round((trades["pnl"] > 0).mean() * 100, 1),
    }


def grid_search(name: str, data_file: str):
    print(f"\n{'='*75}")
    print(f"  {name} — Optimización {len(EMA_FAST_GRID)}×{len(SMA_SLOW_GRID)} = {len(EMA_FAST_GRID)*len(SMA_SLOW_GRID)} combos")
    print(f"  Spread aplicado: {SPREAD_PIPS} pips (coste {COST_PER_TRADE_USD} USD/trade)")
    print(f"{'='*75}")

    df_is = load(data_file, "2018-01-01", "2022-12-31")
    df_oos = load(data_file, "2023-01-01", "2024-12-31")
    print(f"  IS:  {len(df_is):,} filas  ({df_is.index[0].date()} → {df_is.index[-1].date()})")
    print(f"  OOS: {len(df_oos):,} filas  ({df_oos.index[0].date()} → {df_oos.index[-1].date()})")

    results = []
    t0 = time.time()
    for ema in EMA_FAST_GRID:
        for sma in SMA_SLOW_GRID:
            if ema >= sma:
                continue  # EMA_Fast debe ser < SMA_Slow
            m_is = backtest_combo(df_is, ema, sma)
            m_oos = backtest_combo(df_oos, ema, sma)
            wf = m_oos["PF"] / m_is["PF"] if m_is["PF"] > 0 else 0
            results.append({
                "EMA_Fast": ema,
                "SMA_Slow": sma,
                "PF_IS": m_is["PF"],
                "PF_OOS": m_oos["PF"],
                "WF_ratio": round(wf, 3),
                "DD_IS%": m_is["DD%"],
                "DD_OOS%": m_oos["DD%"],
                "NetReturn_IS%": m_is["NetReturn%"],
                "NetReturn_OOS%": m_oos["NetReturn%"],
                "Trades_IS": m_is["NTrades"],
                "Trades_OOS": m_oos["NTrades"],
            })
    elapsed = time.time() - t0

    df_r = pd.DataFrame(results)
    n = len(df_r)
    print(f"\n  Completado: {n} combos en {elapsed:.1f}s ({elapsed/n:.2f}s/combo)")

    # Filtros del checklist 7 puntos
    df_r["pasa_WF"] = df_r["WF_ratio"] >= 0.85
    df_r["pasa_DD"] = df_r["DD_OOS%"] <= 2 * df_r["DD_IS%"]
    df_r["pasa_trades"] = (df_r["Trades_IS"] >= 200) & (df_r["Trades_OOS"] >= 100)
    df_r["pasa_OOS_pos"] = df_r["NetReturn_OOS%"] > 0
    df_r["VALIDADO"] = df_r["pasa_WF"] & df_r["pasa_DD"] & df_r["pasa_trades"] & df_r["pasa_OOS_pos"]

    print("\n  TOP 5 por PF_OOS (filtrados validados primero):")
    df_top = df_r.sort_values(["VALIDADO", "PF_OOS"], ascending=[False, False]).head(5)
    print(df_top[["EMA_Fast", "SMA_Slow", "PF_IS", "PF_OOS", "WF_ratio", "DD_IS%", "DD_OOS%", "NetReturn_IS%", "NetReturn_OOS%", "VALIDADO"]].to_string(index=False))

    n_val = df_r["VALIDADO"].sum()
    print(f"\n  Combos VALIDADOS (pasan 4 filtros): {n_val}/{n}")

    return df_r


def main():
    print("=" * 75)
    print("  OPTIMIZACIÓN MA CROSS — GBPUSD y EURUSD con WF y spread realista")
    print("=" * 75)

    out_dir = Path(__file__).resolve().parents[2] / "vectorbt_bridge" / "output"
    out_dir.mkdir(exist_ok=True)

    for name, data_file in [
        ("GBPUSD", "GBPUSD_M15_histdata.csv"),
        ("EURUSD", "EURUSD_M15_histdata.csv"),
    ]:
        df_res = grid_search(name, data_file)
        df_res.to_csv(out_dir / f"optim_ma_cross_{name}_WF.csv", index=False)
        print(f"  Guardado: optim_ma_cross_{name}_WF.csv")


if __name__ == "__main__":
    main()
