"""
MA Cross + filtro Stochastic — Optimizacion IS/OOS

Compara baseline (sin Stoch) con grid de filtros Stochastic.
Hipotesis: el filtro Stoch evita entrar largos en sobrecompra y cortos en sobreventa,
reduciendo trades de baja calidad y mejorando PF/DD.

Uso:
  python -m backtest.run_ma_cross_stoch_filter_opt EURUSD
  python -m backtest.run_ma_cross_stoch_filter_opt GBPUSD
"""
import os
import sys
import itertools
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import pandas as pd
import multiprocessing as mp
from strategies.ma_cross_filtered_m15 import (
    add_indicators, run_backtest, compute_metrics, PAIR_CONFIG,
)

PAIR = sys.argv[1].upper() if len(sys.argv) > 1 else "EURUSD"
DATA = os.path.join(os.path.dirname(__file__), "..", "data")
CAP = 50_000.0
IS_END = "2021-12-31"
OOS_START = "2022-01-01"

FILES = {
    "EURUSD": "EURUSD_M15_histdata.csv",
    "GBPUSD": "GBPUSD_M15_histdata.csv",
    "AUDNZD": "AUDNZD_M15_histdata.csv",
    "AUDCAD": "AUDCAD_M15_histdata.csv",
}

# Params base validados por par (registro)
BASE_PARAMS = {
    "EURUSD": {
        "EMA_Fast": 8, "SMA_Slow": 34, "Dir_EMA_Fast": 8, "Dir_SMA_Slow": 34,
        "ATR_Period": 14, "SL_ATR_Mult": 2.0, "RR": 2.5,
        "BE_Trigger": 0.5, "BE_Offset": 0.0002,
        "Trail_Start": 1.5, "Trail_Dist": 0.5,
        "MaxSpreadPips": 3.0, "LotRiskPct": 0.5, "MaxLots": 4.0,
        "ADX_H4_Period": 14, "ADX_H4_Min": 0,
    },
    "GBPUSD": {
        "EMA_Fast": 5, "SMA_Slow": 34, "Dir_EMA_Fast": 5, "Dir_SMA_Slow": 34,
        "ATR_Period": 14, "SL_ATR_Mult": 1.0, "RR": 3.0,
        "BE_Trigger": 0.5, "BE_Offset": 0.0002,
        "Trail_Start": 1.5, "Trail_Dist": 0.5,
        "MaxSpreadPips": 3.0, "LotRiskPct": 0.5, "MaxLots": 4.0,
        "ADX_H4_Period": 14, "ADX_H4_Min": 0,
    },
}

# Grid de Stoch (estos parametros + StochFilter)
GRID = {
    "StochFilter": [0, 1],
    "Stoch_K": [5],
    "Stoch_D": [3],
    "Stoch_MaxBuy": [70, 75, 80, 85],
    "Stoch_MinSell": [15, 20, 25, 30],
}

_df_is = None
_df_oos = None
_pip = None
_pip_val = None
_base = None


def _pool_init(df_is, df_oos, pip, pip_val, base):
    global _df_is, _df_oos, _pip, _pip_val, _base
    _df_is, _df_oos, _pip, _pip_val, _base = df_is, df_oos, pip, pip_val, base


def _worker(combo):
    p = {**_base, **combo}
    try:
        t_is = run_backtest(_df_is, p, CAP, _pip, _pip_val)
        t_oos = run_backtest(_df_oos, p, CAP, _pip, _pip_val)
        m_is = compute_metrics(t_is, CAP)
        m_oos = compute_metrics(t_oos, CAP)
    except Exception as e:
        return None
    if m_is["n"] < 30 or m_is["pf"] <= 0:
        return None
    return {
        **combo,
        "is_n": m_is["n"], "is_pf": m_is["pf"], "is_dd": m_is["dd_pct"],
        "is_ann": m_is["ann_pct"],
        "oos_n": m_oos["n"], "oos_pf": m_oos["pf"], "oos_dd": m_oos["dd_pct"],
        "oos_wr": m_oos["wr"], "oos_ann": m_oos["ann_pct"], "oos_pnl": m_oos["pnl"],
        "wf_ratio": round(m_oos["pf"] / m_is["pf"], 3) if m_is["pf"] > 0 else 0,
    }


def main():
    cfg = PAIR_CONFIG.get(PAIR)
    if not cfg:
        print(f"Par {PAIR} no reconocido")
        return
    base = BASE_PARAMS.get(PAIR)
    if not base:
        print(f"Sin parametros base para {PAIR}")
        return

    path = os.path.join(DATA, FILES[PAIR])
    if not os.path.exists(path):
        print(f"Archivo no encontrado: {path}")
        return

    print("=" * 70)
    print(f"  MA Cross + Stoch filter  -  Optimizacion {PAIR}")
    print(f"  IS 2014-2021 | OOS 2022-2025 | Capital $50,000")
    print("=" * 70)

    df_raw = pd.read_csv(path, index_col=0, parse_dates=True)
    df_is_raw = df_raw[df_raw.index <= IS_END].copy()
    df_oos_raw = df_raw[df_raw.index >= OOS_START].copy()
    print(f"  IS: {len(df_is_raw):,} barras | OOS: {len(df_oos_raw):,} barras")

    df_is = add_indicators(df_is_raw, base)
    df_oos = add_indicators(df_oos_raw, base)

    # Benchmark
    t0_bm = time.time()
    run_backtest(df_is, base, CAP, cfg["pip"], cfg["pip_val"])
    bm = time.time() - t0_bm

    keys = list(GRID.keys())
    combos = [dict(zip(keys, v)) for v in itertools.product(*GRID.values())]
    n_proc = min(8, mp.cpu_count())
    est = bm * len(combos) / n_proc
    print(f"  Grid: {len(combos)} combos | 1 BT={bm:.2f}s | Est: {est:.0f}s ({est/60:.1f} min)")

    t0 = time.time()
    ctx = mp.get_context("spawn")
    with ctx.Pool(processes=n_proc,
                  initializer=_pool_init,
                  initargs=(df_is, df_oos, cfg["pip"], cfg["pip_val"], base)) as pool:
        results = pool.map(_worker, combos, chunksize=4)
    results = [r for r in results if r is not None]
    print(f"  Completado: {len(results)}/{len(combos)} validos en {time.time()-t0:.0f}s")
    if not results:
        return

    df_res = pd.DataFrame(results)
    df_res["score"] = df_res["is_pf"] * 0.4 + df_res["oos_pf"] * 0.6 - df_res["is_dd"] * 0.02
    df_res = df_res.sort_values("score", ascending=False)

    out = os.path.join(os.path.dirname(__file__), "..", "reports",
                       f"MA_Cross_{PAIR}_Stoch_Opt_Results.csv")
    df_res.to_csv(out, index=False)

    # Baseline (StochFilter=0)
    baseline = df_res[df_res["StochFilter"] == 0].iloc[0]

    df_ok = df_res[(df_res["is_pf"] > 1.0) & (df_res["oos_pf"] > 1.0)].head(10)
    cols = ["StochFilter", "Stoch_MaxBuy", "Stoch_MinSell",
            "is_n", "is_pf", "oos_pf", "oos_dd", "oos_wr", "oos_ann", "wf_ratio", "score"]
    print(f"\n  TOP 10 combos (IS_PF>1 Y OOS_PF>1):")
    if len(df_ok):
        print(df_ok[cols].to_string(index=False))
        b = df_ok.iloc[0]
        print(f"\n  BASELINE (sin Stoch):")
        print(f"    OOS PF={baseline['oos_pf']:.2f}  DD={baseline['oos_dd']:.2f}%  Ann={baseline['oos_ann']:.2f}%  N={int(baseline['oos_n'])}")
        print(f"\n  MEJOR CON STOCH: MaxBuy={int(b['Stoch_MaxBuy'])} MinSell={int(b['Stoch_MinSell'])}")
        print(f"    OOS PF={b['oos_pf']:.2f}  DD={b['oos_dd']:.2f}%  Ann={b['oos_ann']:.2f}%  N={int(b['oos_n'])}")
        delta_pf = b['oos_pf'] - baseline['oos_pf']
        delta_dd = b['oos_dd'] - baseline['oos_dd']
        delta_ann = b['oos_ann'] - baseline['oos_ann']
        print(f"\n  MEJORA vs baseline: PF {delta_pf:+.2f}  DD {delta_dd:+.2f}pp  Ann {delta_ann:+.2f}pp")
        verdict = "MERECE LA PENA" if delta_pf > 0.05 and delta_dd <= 0.5 else "NO MEJORA SIGNIFICATIVAMENTE"
        print(f"  Veredicto: {verdict}")
    else:
        print("  Sin combos con IS_PF>1 y OOS_PF>1")
    print(f"\n  -> {out}")


if __name__ == "__main__":
    mp.freeze_support()
    main()
