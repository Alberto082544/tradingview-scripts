"""
EMA9+VWAP+Stochastic en NAS100 — Optimizacion (sustituye RSI por Stochastic)

Compara variante con Stoch vs baseline RSI (EMA9_QQQ_Opt_Results.csv):
  Baseline RSI: OOS PF 1.76, DD 3.0%, Ann 17.12% (top combo)

Hipotesis: el Stoch puede mejorar timing de entrada en retroceso a EMA9
respecto al RSI 35-75 que es muy amplio.

Uso: python -m backtest.run_ema9_vwap_stoch_opt
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
from strategies.ema9_vwap_stoch import (
    add_indicators, run_backtest, compute_metrics, DEFAULT_PARAMS,
)

DATA = os.path.join(os.path.dirname(__file__), "..", "data", "NAS100_proxy_M15_twelvedata.csv")
CAP = 50_000.0
IS_END = "2023-12-31"
OOS_START = "2024-01-01"

FIXED = {
    "EMA_Fast": 9, "EMA_Mid": 21,
    "Stoch_K": 5, "Stoch_D": 3, "Stoch_Slow": 3,
    "ATR_Period": 14,
    "SL_ATR_Mult": 1.5, "MinSLPips": 0.3,
    "BE_Mult": 2.0, "TP1_Mult": 1.5, "TP1_Pct": 0.5,
    "Trail_EMA": 1, "WickRatio": 1.5,
    "MaxTradesDay": 3, "SessionStart": 0, "SessionEnd": 23,
    "LotRiskPct": 0.5, "MaxLots": 4.0, "Commission": 0.0,
}

GRID = {
    "StochMode":      [1, 2],
    "Stoch_Buy_Min":  [20, 30, 40],
    "Stoch_Buy_Max":  [60, 70, 80],
    "Stoch_Sell_Min": [20, 30, 40],
    "Stoch_Sell_Max": [60, 70, 80],
}

_df = None


def _pool_init(df):
    global _df
    _df = df


def _worker(combo):
    # Filtrar combos invalidos (rango buy invertido o rango sell invertido)
    if combo["Stoch_Buy_Min"] >= combo["Stoch_Buy_Max"]:
        return None
    if combo["Stoch_Sell_Min"] >= combo["Stoch_Sell_Max"]:
        return None
    p = {**FIXED, **combo}
    try:
        t = run_backtest(_df, p, CAP, pip=1.0, pip_val=100.0)
    except Exception:
        return None
    if not isinstance(t, pd.DataFrame):
        return None
    t = t.copy()
    t["exit_dt"] = pd.to_datetime(t["exit_dt"])
    t_is = t[t["exit_dt"] <= pd.Timestamp(IS_END)]
    t_oos = t[t["exit_dt"] >= pd.Timestamp(OOS_START)]
    m_is = compute_metrics(t_is, CAP)
    m_oos = compute_metrics(t_oos, CAP)
    if m_is["n"] < 20 or m_is["pf"] <= 0:
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
    print("=" * 70)
    print("  EMA9+VWAP+Stoch - Optimizacion NAS100 (sustituye RSI por Stoch)")
    print(f"  IS hasta {IS_END} | OOS desde {OOS_START} | Capital ${CAP:,.0f}")
    print("  BASELINE RSI top combo: OOS PF=1.76 DD=3.0% Ann=17.1%")
    print("=" * 70)

    if not os.path.exists(DATA):
        print(f"  [X] Datos no encontrados: {DATA}")
        return

    df_raw = pd.read_csv(DATA, parse_dates=["time"], index_col="time")
    print(f"  Datos: {df_raw.index[0]} -> {df_raw.index[-1]} ({len(df_raw):,} barras)")

    df = add_indicators(df_raw, FIXED)

    t0_bm = time.time()
    run_backtest(df, {**FIXED, **{"StochMode":1, "Stoch_Buy_Min":20, "Stoch_Buy_Max":70,
                                   "Stoch_Sell_Min":30, "Stoch_Sell_Max":80}}, CAP, pip=1.0, pip_val=100.0)
    bm = time.time() - t0_bm

    keys = list(GRID.keys())
    combos = [dict(zip(keys, v)) for v in itertools.product(*GRID.values())]
    n_proc = min(8, mp.cpu_count())
    est = bm * len(combos) / n_proc
    print(f"  Grid: {len(combos)} combos | 1 BT={bm:.2f}s | Est: {est:.0f}s ({est/60:.1f} min)")

    t0 = time.time()
    ctx = mp.get_context("spawn")
    with ctx.Pool(processes=n_proc, initializer=_pool_init, initargs=(df,)) as pool:
        results = pool.map(_worker, combos, chunksize=4)
    results = [r for r in results if r is not None]
    print(f"  Completado: {len(results)}/{len(combos)} validos en {time.time()-t0:.0f}s")
    if not results:
        return

    df_res = pd.DataFrame(results)
    df_res["score"] = df_res["is_pf"] * 0.4 + df_res["oos_pf"] * 0.6 - df_res["is_dd"] * 0.02
    df_res = df_res.sort_values("score", ascending=False)

    out = os.path.join(os.path.dirname(__file__), "..", "reports",
                       "EMA9_VWAP_Stoch_NAS100_Opt_Results.csv")
    df_res.to_csv(out, index=False)

    df_ok = df_res[(df_res["is_pf"] > 1.0) & (df_res["oos_pf"] > 1.0)].head(10)
    cols = ["StochMode", "Stoch_Buy_Min", "Stoch_Buy_Max", "Stoch_Sell_Min", "Stoch_Sell_Max",
            "is_n", "is_pf", "oos_pf", "oos_dd", "oos_wr", "oos_ann", "wf_ratio", "score"]
    print(f"\n  TOP 10 combos (IS_PF>1 Y OOS_PF>1):")
    if len(df_ok):
        print(df_ok[cols].to_string(index=False))
        b = df_ok.iloc[0]
        print(f"\n  MEJOR con Stoch:")
        print(f"    StochMode={int(b['StochMode'])} Buy[{int(b['Stoch_Buy_Min'])}-{int(b['Stoch_Buy_Max'])}] Sell[{int(b['Stoch_Sell_Min'])}-{int(b['Stoch_Sell_Max'])}]")
        print(f"    OOS PF={b['oos_pf']:.2f}  DD={b['oos_dd']:.2f}%  Ann={b['oos_ann']:.2f}%  N={int(b['oos_n'])}  WF={b['wf_ratio']:.3f}")
        print(f"\n  BASELINE RSI (top combo del registro): OOS PF=1.76 DD=3.0% Ann=17.1%")
        delta_pf = b['oos_pf'] - 1.76
        delta_dd = b['oos_dd'] - 3.0
        delta_ann = b['oos_ann'] - 17.1
        print(f"  MEJORA vs baseline RSI: PF {delta_pf:+.2f}  DD {delta_dd:+.2f}pp  Ann {delta_ann:+.2f}pp")
        verdict = "MERECE LA PENA SUSTITUIR" if (delta_pf > 0.05 and delta_dd <= 1.0) else "NO MEJORA, MANTENER RSI"
        print(f"  Veredicto: {verdict}")
    else:
        print("  Sin combos validos. Probable: Stoch no encaja con el setup tendencia + retroceso a EMA9.")
    print(f"\n  -> {out}")


if __name__ == "__main__":
    mp.freeze_support()
    main()
