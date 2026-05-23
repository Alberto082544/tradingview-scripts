"""
Test de sensibilidad al spread + Walk-Forward para GBPUSD y EURUSD.

Objetivo: explicar la divergencia Python (+PF) vs MT5 (-PF).
Hipótesis: los DEFAULT_PARAMS son rentables con spread bajo pero se desmoronan
con spreads realistas del broker (1-3 pips).

Para cada bot, prueba varios niveles de spread y muestra cómo evoluciona el PF.
También hace split IS (2018-2022) / OOS (2023-2024) para detectar overfit.

Ejecutar:
    python -X utf8 -m vectorbt_bridge.examples.run_spread_sensitivity
"""
import sys
import time
import warnings
from pathlib import Path
import numpy as np
import pandas as pd

warnings.simplefilter("ignore", FutureWarning)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
INIT_CASH = 15000

# Spreads a probar (en pips totales por trade = entrada + salida)
# Ej. spread real de 1.0 pip = 0.0001 fees + 0.0001 slippage
SPREAD_LEVELS_PIPS = [0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 5.0]


def load_data(filename: str, start: str, end: str) -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / filename, parse_dates=["time"]).set_index("time")
    return df[(df.index >= start) & (df.index <= end)]


def run_ma_cross_with_cost(df: pd.DataFrame, cost_per_trade_usd: float,
                            pip_val: float = 10.0, init_cash: float = INIT_CASH) -> dict:
    """Ejecuta MA Cross con coste extra por trade aplicado al PnL."""
    from strategies.ma_cross_m15 import add_indicators, run_backtest, compute_metrics, DEFAULT_PARAMS
    params = dict(DEFAULT_PARAMS)
    df_ind = add_indicators(df.copy(), params)
    trades = run_backtest(df_ind, params, initial_capital=init_cash, pip_val=pip_val)
    if trades is None or len(trades) == 0:
        return {"PF": 0, "DD%": 0, "NetPnL": 0, "NTrades": 0, "WR%": 0}

    # Aplicar coste fijo por trade
    pnl_adj = trades["pnl"] - cost_per_trade_usd
    wins = pnl_adj[pnl_adj > 0].sum()
    losses = abs(pnl_adj[pnl_adj < 0].sum())
    pf = wins / losses if losses > 0 else 0

    # DD recalculado con costes aplicados
    equity = init_cash + pnl_adj.cumsum()
    peak = equity.cummax()
    dd_pct = abs(((equity - peak) / peak).min()) * 100

    return {
        "PF": round(pf, 2),
        "DD%": round(dd_pct, 1),
        "NetPnL": round(pnl_adj.sum(), 0),
        "NetReturn%": round(pnl_adj.sum() / init_cash * 100, 1),
        "NTrades": len(trades),
        "WR%": round((trades["pnl"] > 0).mean() * 100, 1),
    }


def test_spread_sensitivity(bot_name: str, data_file: str, pip_val: float):
    print(f"\n{'='*65}")
    print(f"  {bot_name} — Sensibilidad al spread (2018-2024 completo)")
    print(f"{'='*65}")

    df = load_data(data_file, "2018-01-01", "2024-12-31")
    print(f"  Datos: {len(df):,} filas")

    # Para cada nivel de spread, lote típico ~0.5 con SL ~25 pips → coste de spread en USD
    # spread (pips) × pip_val (USD/pip por lote 1.0) × lote 0.5 = USD por trade
    LOT_TYPICAL = 0.5
    results = []
    for spread_pips in SPREAD_LEVELS_PIPS:
        cost_usd = spread_pips * pip_val * LOT_TYPICAL
        m = run_ma_cross_with_cost(df, cost_per_trade_usd=cost_usd, pip_val=pip_val)
        m["Spread_pips"] = spread_pips
        m["Cost_USD/trade"] = round(cost_usd, 2)
        results.append(m)

    df_res = pd.DataFrame(results)[["Spread_pips", "Cost_USD/trade", "PF", "DD%", "NetPnL", "NetReturn%", "NTrades", "WR%"]]
    print(df_res.to_string(index=False))

    # Encontrar el spread crítico donde PF cruza 1.0
    df_sorted = df_res.sort_values("Spread_pips")
    crit = None
    for _, row in df_sorted.iterrows():
        if row["PF"] < 1.0:
            crit = row["Spread_pips"]
            break

    if crit is not None:
        print(f"\n  → Spread crítico (PF < 1.0): {crit} pips")
        if crit > 2.0:
            print(f"  → El bot AGUANTA spreads realistas de broker (1-2 pips). EDGE REAL.")
        else:
            print(f"  → El bot SE DESMORONA con spreads de broker. EDGE FALSA.")
    else:
        print(f"\n  → El bot mantiene PF > 1.0 hasta {SPREAD_LEVELS_PIPS[-1]} pips. EDGE MUY FUERTE.")

    return df_res


def test_walk_forward(bot_name: str, data_file: str, pip_val: float):
    print(f"\n{'='*65}")
    print(f"  {bot_name} — Walk-Forward IS (2018-2022) vs OOS (2023-2024)")
    print(f"{'='*65}")

    df_is = load_data(data_file, "2018-01-01", "2022-12-31")
    df_oos = load_data(data_file, "2023-01-01", "2024-12-31")

    # Aplicar spread realista (1.5 pips típico FN para GBPUSD/EURUSD)
    cost_realistic = 1.5 * pip_val * 0.5

    m_is = run_ma_cross_with_cost(df_is, cost_per_trade_usd=cost_realistic, pip_val=pip_val)
    m_oos = run_ma_cross_with_cost(df_oos, cost_per_trade_usd=cost_realistic, pip_val=pip_val)

    print(f"  IS  2018-2022 (5 años): PF={m_is['PF']}  DD={m_is['DD%']}%  Return={m_is['NetReturn%']}%  Trades={m_is['NTrades']}")
    print(f"  OOS 2023-2024 (2 años): PF={m_oos['PF']}  DD={m_oos['DD%']}%  Return={m_oos['NetReturn%']}%  Trades={m_oos['NTrades']}")

    wf_ratio = m_oos["PF"] / m_is["PF"] if m_is["PF"] > 0 else 0
    print(f"  → WF ratio (OOS/IS): {wf_ratio:.3f}")
    if wf_ratio >= 0.85:
        print(f"  → SUPERA checklist WF (≥0.85). NO hay overfit detectable.")
    elif wf_ratio >= 0.50:
        print(f"  → WF degradado (0.50-0.85). POSIBLE overfit.")
    else:
        print(f"  → WF muy degradado (<0.50). OVERFIT confirmado.")

    return m_is, m_oos


def main():
    print("=" * 65)
    print("  ANÁLISIS DIVERGENCIA Python vs MT5 — GBPUSD y EURUSD")
    print("  Capital: 15.000 USD | Lote típico: 0.5")
    print("=" * 65)

    bots = [
        ("GBPUSD MA Cross", "GBPUSD_M15_histdata.csv", 10.0),
        ("EURUSD MA Cross", "EURUSD_M15_histdata.csv", 10.0),
    ]

    spread_results = {}
    wf_results = {}

    for name, data, pip_val in bots:
        spread_results[name] = test_spread_sensitivity(name, data, pip_val)
        wf_results[name] = test_walk_forward(name, data, pip_val)

    # Guardar
    out_dir = Path(__file__).resolve().parents[2] / "vectorbt_bridge" / "output"
    out_dir.mkdir(exist_ok=True)
    for name, df in spread_results.items():
        safe_name = name.replace(" ", "_").replace("/", "-")
        df.to_csv(out_dir / f"spread_sensitivity_{safe_name}.csv", index=False)
    print(f"\n  CSVs guardados en: {out_dir}")

    # Conclusión
    print("\n" + "=" * 65)
    print("  CONCLUSIÓN")
    print("=" * 65)
    for name in spread_results:
        df = spread_results[name]
        pf_0 = df[df["Spread_pips"] == 0.0]["PF"].iloc[0]
        pf_15 = df[df["Spread_pips"] == 1.5]["PF"].iloc[0]
        pf_30 = df[df["Spread_pips"] == 3.0]["PF"].iloc[0]
        print(f"\n  {name}:")
        print(f"    Sin spread: PF {pf_0}")
        print(f"    Spread 1.5 pips (típico FN): PF {pf_15}")
        print(f"    Spread 3.0 pips (cierres/noticias): PF {pf_30}")


if __name__ == "__main__":
    main()
