"""
Validacion regimen-dependencia para el top combo AUDNZD-Stoch (grid restrictivo 2026-05-21).

Combo ganador (de Ranger_C_AUDNZD_Stoch_Restrictivo_Opt_Results.csv):
  MinSL=25, Exit=16, ADX_H4_Max=20, StochMode=2, Stoch_L=20, Stoch_S=75,
  RSI_L=40, RSI_S=60, Trail=8

- Year-by-year: PF, PnL, DD para cada anyo 2014-2025
- Monte Carlo: aleatoriza orden de trades 2000 veces, DD distribution

Regla anti-overfitting (feedback_regimen_dependiente.md):
- >= 10/12 anios positivos
- MC P95 DD < 2x DD historico
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

# Top combo del grid restrictivo 2026-05-21 (DeepSeek 6 sombreros)
TOP_PARAMS = {
    "BB_Period": 20,
    "BB_StdDev": 2.0,
    "RSI_Period": 14,
    "ADX_H4_Period": 14,
    "ATR_Period": 14,
    "Stoch_K": 5,
    "Stoch_D": 3,
    # Filtros ganadores grid restrictivo
    "ADX_H4_Max": 20,
    "RSI_Long_Max": 40,
    "RSI_Short_Min": 60,
    "RSI_Confirm": 1,
    "StochMode": 2,
    "Stoch_Long_Max": 20,
    "Stoch_Short_Min": 75,
    "BB_Mid_TP": 0,
    "MinSLPips": 20,
    "TrailDistPips": 8,
    "ExitBars": 20,
    "SL_ATR_Mult": 1.5,
    "MaxSLPips": 999,
    "TP_ATR_Mult": 0,
    "TrailActivate": 0.5,
    "SessionStart": 0,
    "SessionEnd": 23,
    "BadHour": -1,
    "MaxTradesDay": 5,
    "LotRiskPct": 0.7,
    "MaxLots": 4.0,
}


def calc_dd_pct(pnl_series, initial=CAPITAL):
    equity = initial + np.cumsum(pnl_series)
    peak = np.maximum.accumulate(equity)
    dd = (equity - peak) / peak
    return abs(float(dd.min()) * 100.0)


def main():
    print("=" * 70)
    print("  AUDNZD-Stoch Combo #2 Restrictivo - Year-by-Year + MC")
    print("  Combo: MinSL=20 Exit=20 ADX<20 StochMode=2")
    print("=" * 70)

    print("  Cargando datos AUDNZD M15...")
    df_raw = pd.read_csv(DATA, index_col=0, parse_dates=True)
    print(f"  Periodo datos: {df_raw.index[0]} -> {df_raw.index[-1]} ({len(df_raw):,} barras)")

    print("  Calculando indicadores...")
    df = add_indicators(df_raw, TOP_PARAMS)
    print(f"  Ejecutando backtest sobre TODO el periodo...")

    trades = run_backtest(df, TOP_PARAMS, CAPITAL)
    if not isinstance(trades, pd.DataFrame):
        trades = pd.DataFrame(trades, columns=[
            "entry_dt", "exit_dt", "direction", "pnl",
            "exit_type", "equity", "lots", "sl_pips",
        ])

    if len(trades) == 0:
        print("  [X] Sin trades. Algo falla en los params.")
        return

    trades["exit_dt"] = pd.to_datetime(trades["exit_dt"])
    trades["year"] = trades["exit_dt"].dt.year
    print(f"  Total trades: {len(trades):,}")

    # ---- Year-by-year ----
    print()
    print("=" * 70)
    print("  YEAR-BY-YEAR")
    print("=" * 70)
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
        if is_pos:
            positive_years += 1
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

    # ---- Monte Carlo ----
    print()
    print("=" * 70)
    print(f"  MONTE CARLO ({MC_RUNS:,} iteraciones)")
    print("=" * 70)
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
    print(f"  MC P50 DD: {p50:.2f}%")
    print(f"  MC P95 DD: {p95:.2f}%")
    print(f"  MC P99 DD: {p99:.2f}%")
    print(f"  Simulaciones positivas: {pct_pos_sims:.1f}%")

    mc_ok = p95 < 2 * dd_historico
    print(f"  Regla MC P95 < 2x DD historico: {'PASA' if mc_ok else 'FALLA'}"
          f"  ({p95:.2f}% < {2*dd_historico:.2f}%? {'si' if mc_ok else 'no'})")

    # ---- Veredicto final ----
    print()
    print("=" * 70)
    print("  VEREDICTO ANTI-OVERFITTING")
    print("=" * 70)
    if consistency_ok and mc_ok:
        verdict = "PASA: top combo es ROBUSTO (no regimen-dependiente)"
    elif consistency_ok and not mc_ok:
        verdict = "DUDOSO: anios consistentes pero MC alto, sequencia depende del orden"
    elif not consistency_ok and mc_ok:
        verdict = "DUDOSO: MC ok pero anios inconsistentes -> regimen-dependiente"
    else:
        verdict = "FALLA: regimen-dependiente, NO usar este combo"
    print(f"  {verdict}")

    # ---- Guardar ----
    out_yearly = os.path.join(OUT_DIR, "AUDNZD_Stoch_combo2_yearly.csv")
    pd.DataFrame(yearly_rows).to_csv(out_yearly, index=False)
    out_mc = os.path.join(OUT_DIR, "AUDNZD_Stoch_combo2_mc_dd_distribution.csv")
    pd.DataFrame({"dd_pct": dd_dist}).to_csv(out_mc, index=False)

    import json
    summary = {
        "params": TOP_PARAMS,
        "n_trades_total": int(len(trades)),
        "dd_historico_pct": round(dd_historico, 2),
        "mc_p50_pct": round(p50, 2),
        "mc_p95_pct": round(p95, 2),
        "mc_p99_pct": round(p99, 2),
        "mc_pct_positive": round(pct_pos_sims, 1),
        "positive_years": int(positive_years),
        "total_years": int(total_years),
        "consistency_ok": bool(consistency_ok),
        "mc_ok": bool(mc_ok),
        "verdict": verdict,
        "yearly": yearly_rows,
    }
    out_json = os.path.join(OUT_DIR, "AUDNZD_Stoch_combo2_validation_summary.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, default=str)

    print(f"\n  Reports guardados:")
    print(f"    {out_yearly}")
    print(f"    {out_mc}")
    print(f"    {out_json}")


if __name__ == "__main__":
    main()
