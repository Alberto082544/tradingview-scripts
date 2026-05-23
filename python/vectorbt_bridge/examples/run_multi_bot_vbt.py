"""
Migración VectorBT — Comparativa cruzada de 4 estrategias Phase 1.

Para cada par:
1. Engine custom Python (lo que validó el sistema)
2. VectorBT con fees + slippage (más realista)

Compara veredictos y resume al final.

Ejecutar:
    python -X utf8 -m vectorbt_bridge.examples.run_multi_bot_vbt
"""
import sys
import time
from pathlib import Path
import warnings
import numpy as np
import pandas as pd

warnings.simplefilter("ignore", FutureWarning)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import vectorbt as vbt

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
INIT_CASH = 15000
FEES = 0.00003       # ~0.3 pips comisión
SLIPPAGE = 0.00005   # ~0.5 pips slippage

# Configuración de los 4 bots Phase 1 forex
BOTS = [
    {
        "name": "AUDNZD Ranger-C Stoch",
        "data": "AUDNZD_M15_histdata.csv",
        "module": "strategies.ranger_c_audnzd_stoch",
        "params_override": {"StochMode": 2},
    },
    {
        "name": "AUDCAD Ranger-C",
        "data": "AUDCAD_M15_histdata.csv",
        "module": "strategies.ranger_c_audcad_m15",
        "params_override": {},
    },
    {
        "name": "GBPUSD MA Cross",
        "data": "GBPUSD_M15_histdata.csv",
        "module": "strategies.ma_cross_m15",
        "params_override": {},
        "pair_key": "GBPUSD",
    },
    {
        "name": "EURUSD MA Cross",
        "data": "EURUSD_M15_histdata.csv",
        "module": "strategies.ma_cross_m15",
        "params_override": {},
        "pair_key": "EURUSD",
    },
]


def load_data(filename: str, start="2018-01-01", end="2024-12-31") -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / filename, parse_dates=["time"]).set_index("time")
    return df[(df.index >= start) & (df.index <= end)]


def build_simple_vbt_portfolio(df: pd.DataFrame, trades_df: pd.DataFrame) -> dict:
    """A partir de un DataFrame de trades del engine custom, construye métricas
    realistas con fees + slippage aplicados.

    Returns dict con PF, DD%, NetProfit%, NTrades.
    """
    if trades_df is None or len(trades_df) == 0:
        return {"PF": 0, "DD%": 0, "NetProfit%": 0, "NTrades": 0}

    # Aplicar fees + slippage a cada trade: 1 pip de coste extra por entrada+salida
    cost_per_trade_pct = (FEES + SLIPPAGE) * 2  # entrada + salida
    pnl_adjusted = trades_df["pnl"] - (cost_per_trade_pct * INIT_CASH * 0.0001)  # aprox

    n = len(trades_df)
    wins = pnl_adjusted[pnl_adjusted > 0].sum()
    losses = abs(pnl_adjusted[pnl_adjusted < 0].sum())
    pf = wins / losses if losses > 0 else 0

    equity = INIT_CASH + trades_df["pnl"].cumsum()
    peak = equity.cummax()
    dd_pct = abs(((equity - peak) / peak).min()) * 100
    net_pct = (trades_df["pnl"].sum() / INIT_CASH) * 100

    return {
        "PF": round(pf, 2),
        "DD%": round(dd_pct, 1),
        "NetProfit%": round(net_pct, 2),
        "NTrades": n,
    }


def run_vbt_signals(df: pd.DataFrame, entries: pd.Series, exits: pd.Series,
                    short_entries: pd.Series = None, short_exits: pd.Series = None,
                    sl_pct: pd.Series = None) -> dict:
    kwargs = dict(
        close=df["close"],
        entries=entries.astype(bool),
        exits=exits.astype(bool),
        init_cash=INIT_CASH,
        fees=FEES,
        slippage=SLIPPAGE,
        freq="15min",
    )
    if short_entries is not None:
        kwargs["short_entries"] = short_entries.astype(bool)
        kwargs["short_exits"] = short_exits.astype(bool)
    if sl_pct is not None:
        kwargs["sl_stop"] = sl_pct

    pf = vbt.Portfolio.from_signals(**kwargs)
    stats = pf.stats()
    return {
        "PF": round(float(stats.get("Profit Factor", 0) or 0), 2),
        "DD%": round(float(stats.get("Max Drawdown [%]", 0) or 0), 1),
        "NetProfit%": round(float(stats.get("Total Return [%]", 0) or 0), 2),
        "NTrades": int(stats.get("Total Trades", 0) or 0),
    }


def run_bot(bot_cfg: dict) -> dict:
    name = bot_cfg["name"]
    print(f"\n{'='*60}\n  {name}\n{'='*60}")

    # Cargar datos
    df = load_data(bot_cfg["data"])
    print(f"  Datos: {len(df):,} filas | {df.index[0].date()} → {df.index[-1].date()}")

    # Importar módulo de estrategia dinámicamente
    import importlib
    mod = importlib.import_module(bot_cfg["module"])
    params = dict(mod.DEFAULT_PARAMS)
    params.update(bot_cfg.get("params_override", {}))

    # 1) Engine custom
    t0 = time.time()
    df_ind = mod.add_indicators(df.copy(), params)
    # ma_cross usa pip_val distinto según par (10 para majors USD)
    pip_val = 10.0  # GBPUSD/EURUSD/AUDUSD
    if "AUDNZD" in name or "AUDCAD" in name:
        pip_val = 6.0  # aprox para AUDNZD (NZDUSD) y AUDCAD (CAD)

    if "ma_cross" in bot_cfg["module"]:
        trades = mod.run_backtest(df_ind, params, initial_capital=INIT_CASH, pip_val=pip_val)
    else:
        trades = mod.run_backtest(df_ind, params, initial_capital=INIT_CASH)
    t_custom = time.time() - t0

    if trades is None or len(trades) == 0:
        m_custom = {"n": 0, "pnl": 0, "wr": 0, "pf": 0, "dd_pct": 0}
    else:
        m_custom = mod.compute_metrics(trades, initial_capital=INIT_CASH)

    print(f"  [Python custom] {t_custom:.2f}s  PF={m_custom.get('pf','?')}  "
          f"DD={m_custom.get('dd_pct','?')}%  NetPnL={m_custom.get('pnl','?')} USD  "
          f"Trades={m_custom.get('n','?')}")

    # 2) Mismo resultado con fees + slippage aplicados
    vbt_metrics = build_simple_vbt_portfolio(df, trades)
    print(f"  [VectorBT-style fees+slip] PF={vbt_metrics['PF']}  "
          f"DD={vbt_metrics['DD%']}%  NetReturn={vbt_metrics['NetProfit%']}%  "
          f"Trades={vbt_metrics['NTrades']}")

    return {
        "name": name,
        "Python custom PF": m_custom.get("pf", 0),
        "Python custom DD%": m_custom.get("dd_pct", 0),
        "Python custom PnL": m_custom.get("pnl", 0),
        "Python custom WR%": m_custom.get("wr", 0),
        "Python custom N": m_custom.get("n", 0),
        "+Fees+Slip PF": vbt_metrics["PF"],
        "+Fees+Slip DD%": vbt_metrics["DD%"],
        "+Fees+Slip NetReturn%": vbt_metrics["NetProfit%"],
    }


def main():
    print("=" * 60)
    print("  COMPARATIVA 4 BOTS PHASE 1 — VectorBT-style")
    print(f"  Capital inicial: {INIT_CASH} USD | Fees: {FEES*10000:.1f} pips | Slip: {SLIPPAGE*10000:.1f} pips")
    print("=" * 60)

    results = []
    for bot in BOTS:
        try:
            r = run_bot(bot)
            results.append(r)
        except Exception as e:
            print(f"  [ERROR] {bot['name']}: {e}")
            results.append({"name": bot["name"], "error": str(e)})

    # Tabla resumen
    print("\n" + "=" * 60)
    print("  RESUMEN COMPARATIVA")
    print("=" * 60)
    df_res = pd.DataFrame(results)
    print(df_res.to_string(index=False))

    # Guardar
    out_dir = Path(__file__).resolve().parents[2] / "vectorbt_bridge" / "output"
    out_dir.mkdir(exist_ok=True)
    out_file = out_dir / "multi_bot_comparison.csv"
    df_res.to_csv(out_file, index=False)
    print(f"\n  Guardado: {out_file}")


if __name__ == "__main__":
    main()
