"""
Validacion year-by-year + Monte Carlo del EA REAL AUDNZD-v3 cargado en MT5.

EA: AGM_Ranger_C_AUDNZD_M15.mq5 v3 "optimizado DD<5%"
Header: Stochastic(5,3,3) K<15 + ADX H4<20 + Trail 4 pips

Parametros reales del .mq5:
- StochMode=1 (Stoch solo, NO usa RSI)
- Stoch_K=5, Stoch_D=3
- Stoch_Long_Max=15, Stoch_Short_Min=75
- ADX_H4_Max=20
- MinSLPips=20, TrailDistPips=4, ExitBars=32
- BadHour=8 (transicion Asia-Londres bloqueada)
- LotRiskPct=0.5
- BB_Mid_TP=0
"""
import os
import sys
import warnings

warnings.filterwarnings("ignore", category=UserWarning)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import numpy as np
import pandas as pd
from strategies.ranger_c_audnzd_stoch import add_indicators, run_backtest, compute_metrics

DATA = os.path.join(os.path.dirname(__file__), "..", "data", "AUDNZD_M15_histdata.csv")
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "reports")
CAPITAL = 50_000.0
MC_RUNS = 2000

# === PARAMETROS REALES DEL EA v3 EN PRODUCCION ===
REAL_PARAMS = {
    "BB_Period": 20,
    "BB_StdDev": 2.0,
    "RSI_Period": 14,        # Ignorado con StochMode=1 pero requerido por modulo
    "ADX_H4_Period": 14,
    "ATR_Period": 14,
    "Stoch_K": 5,
    "Stoch_D": 3,
    "ADX_H4_Max": 20,
    "RSI_Long_Max": 45,      # Ignorado
    "RSI_Short_Min": 55,     # Ignorado
    "RSI_Confirm": 0,        # Ignorado
    "StochMode": 1,          # *** Stoch SOLO (sin RSI) ***
    "Stoch_Long_Max": 15,    # *** Restrictivo del EA real ***
    "Stoch_Short_Min": 75,
    "BB_Mid_TP": 0,
    "MinSLPips": 20,
    "TrailDistPips": 4,
    "ExitBars": 32,
    "SL_ATR_Mult": 1.5,
    "MaxSLPips": 999,
    "TP_ATR_Mult": 0,
    "TrailActivate": 0.5,
    "SessionStart": 0,
    "SessionEnd": 23,
    "BadHour": 8,            # *** Hora bloqueada ***
    "MaxTradesDay": 5,
    "LotRiskPct": 0.5,       # *** Sizing real ***
    "MaxLots": 4.0,
}


def calc_dd_pct(pnl_series, initial=CAPITAL):
    equity = initial + np.cumsum(pnl_series)
    peak = np.maximum.accumulate(equity)
    dd = (equity - peak) / peak
    return abs(float(dd.min()) * 100.0)


def main():
    print("=" * 72)
    print("  AUDNZD-v3 REAL (EA en produccion) — Validacion year-by-year + MC")
    print("  StochMode=1 / Stoch K<15 / ADX H4<20 / Trail 4 / Exit 32 / LotRisk 0.5")
    print("=" * 72)

    print("  Cargando datos AUDNZD M15...")
    df_raw = pd.read_csv(DATA, index_col=0, parse_dates=True)
    print(f"  Periodo: {df_raw.index[0]} -> {df_raw.index[-1]} ({len(df_raw):,} barras)")

    print("  Calculando indicadores...")
    df = add_indicators(df_raw, REAL_PARAMS)
    print("  Backtest sobre TODO el periodo...")

    trades = run_backtest(df, REAL_PARAMS, CAPITAL)
    if len(trades) == 0:
        print("  [X] Sin trades.")
        return

    trades["exit_dt"] = pd.to_datetime(trades["exit_dt"])
    trades["year"] = trades["exit_dt"].dt.year
    print(f"  Total trades: {len(trades):,}")

    # Year-by-year
    print()
    print("=" * 72)
    print("  YEAR-BY-YEAR")
    print("=" * 72)
    print(f"  {'Anio':<6} {'Trades':>7} {'WR%':>6} {'PF':>6} {'PnL $':>10} {'DD %':>6}")
    yearly_rows = []
    positive_years = 0
    total_years = 0
    for year, grp in trades.groupby("year"):
        pnls = grp["pnl"].astype(float).values
        wins = (pnls > 0).sum()
        wr = 100 * wins / len(pnls) if len(pnls) else 0
        gross_win = pnls[pnls > 0].sum()
        gross_loss = abs(pnls[pnls < 0].sum())
        pf = gross_win / gross_loss if gross_loss > 0 else float("inf")
        total_pnl = pnls.sum()
        dd_year = calc_dd_pct(pnls)
        is_pos = total_pnl > 0
        if is_pos: positive_years += 1
        total_years += 1
        mark = "[+]" if is_pos else "[-]"
        print(f"  {year:<6} {len(pnls):>7} {wr:>5.1f}% {pf:>6.2f} ${total_pnl:>9,.0f} {dd_year:>5.1f}%  {mark}")
        yearly_rows.append({
            "year": int(year), "trades": int(len(pnls)), "wr": round(wr, 1),
            "pf": round(pf, 2) if pf != float("inf") else 99.0,
            "pnl": round(total_pnl, 2), "dd_pct": round(dd_year, 2),
            "positive": bool(is_pos),
        })

    print(f"\n  Anios positivos: {positive_years}/{total_years}")
    consistency_ok = positive_years >= (total_years * 10 / 12)
    print(f"  Regla >=10/12: {'PASA' if consistency_ok else 'FALLA'}")

    # Monte Carlo
    print()
    print("=" * 72)
    print(f"  MONTE CARLO ({MC_RUNS:,} iteraciones)")
    print("=" * 72)
    pnls = trades["pnl"].astype(float).values
    dd_historico = calc_dd_pct(pnls)
    print(f"  DD historico (orden real): {dd_historico:.2f}%")

    rng = np.random.default_rng(42)
    dd_dist = np.empty(MC_RUNS, dtype=float)
    pnl_total = pnls.sum()
    pct_pos_sims = 0
    for i in range(MC_RUNS):
        perm = rng.permutation(pnls)
        dd_dist[i] = calc_dd_pct(perm)
        if pnl_total > 0:
            pct_pos_sims += 1
    pct_pos_sims = 100.0 * pct_pos_sims / MC_RUNS

    p50 = float(np.percentile(dd_dist, 50))
    p95 = float(np.percentile(dd_dist, 95))
    p99 = float(np.percentile(dd_dist, 99))
    print(f"  MC P50/P95/P99: {p50:.2f}% / {p95:.2f}% / {p99:.2f}%")
    print(f"  Simulaciones positivas: {pct_pos_sims:.1f}%")
    mc_ok = p95 < 2 * dd_historico
    print(f"  Regla MC P95<2xDD: {'PASA' if mc_ok else 'FALLA'} ({p95:.2f}% < {2*dd_historico:.2f}%?)")

    # PnL anual promedio + DD esperado con sizing real
    avg_pnl_year = trades["pnl"].sum() / total_years
    print(f"\n  PnL promedio/anio: ${avg_pnl_year:,.0f} (sobre ${CAPITAL:,.0f})")
    print(f"  Annual %: {avg_pnl_year / CAPITAL * 100:.2f}%")

    # Veredicto
    print()
    print("=" * 72)
    print("  VEREDICTO ANTI-OVERFITTING")
    print("=" * 72)
    if consistency_ok and mc_ok:
        verdict = "PASA: EA v3 es ROBUSTO"
    elif consistency_ok and not mc_ok:
        verdict = "DUDOSO: anyos consistentes pero MC alto"
    elif not consistency_ok and mc_ok:
        verdict = "DUDOSO: regimen-dependiente (MC ok)"
    else:
        verdict = "FALLA: regimen-dependiente Y MC alto. Revisar deploy URGENTE"
    print(f"  {verdict}")

    # Guardar
    out_yearly = os.path.join(OUT_DIR, "AUDNZD_v3_real_yearly.csv")
    pd.DataFrame(yearly_rows).to_csv(out_yearly, index=False)
    out_mc = os.path.join(OUT_DIR, "AUDNZD_v3_real_mc_dd_distribution.csv")
    pd.DataFrame({"dd_pct": dd_dist}).to_csv(out_mc, index=False)
    import json
    summary = {
        "params_reales_ea_v3": REAL_PARAMS,
        "n_trades_total": int(len(trades)),
        "dd_historico_pct": round(dd_historico, 2),
        "mc_p50_pct": round(p50, 2),
        "mc_p95_pct": round(p95, 2),
        "mc_p99_pct": round(p99, 2),
        "mc_pct_positive": round(pct_pos_sims, 1),
        "positive_years": int(positive_years),
        "total_years": int(total_years),
        "avg_pnl_year": round(avg_pnl_year, 2),
        "annual_pct": round(avg_pnl_year / CAPITAL * 100, 2),
        "consistency_ok": bool(consistency_ok),
        "mc_ok": bool(mc_ok),
        "verdict": verdict,
        "yearly": yearly_rows,
    }
    out_json = os.path.join(OUT_DIR, "AUDNZD_v3_real_validation_summary.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, default=str)
    print(f"\n  Reports en: {OUT_DIR}/AUDNZD_v3_real_*")


if __name__ == "__main__":
    main()
