"""
AGM_Ranger v6 — Analisis de robustez completo
Mejor combo: ADX_H4<30 + ADX_M30<30 + RSI=32 + MinSL=500 + Trail=120 + ExitBars=12

Uso: python -m backtest.run_agm_ranger_v6_robustness
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import pandas as pd
import random

from strategies.agm_ranger_v6 import add_indicators, run_backtest, compute_metrics

CACHE_M30       = os.path.join(os.path.dirname(__file__), "..", "data", "GBPJPY_M30_dukas.csv")
INITIAL_CAPITAL = 50_000.0
IS_END          = "2021-12-31"
OOS_START       = "2022-01-01"

V6_PARAMS = {
    'BB_Period':        20,
    'BB_StdDev':       2.0,
    'RSI_Period':       14,
    'RSI_Oversold':     32,
    'RSI_Overbought':   68,
    'ADX_Period':       14,
    'ADX_Threshold':    30,    # M30 micro-filtro
    'ADX_H4_Period':    14,
    'ADX_H4_Threshold': 30,    # H4 macro-filtro (NUEVO v6)
    'SL_ATR_Mult':     1.5,
    'ATR_Period':       14,
    'MaxSLPips':       999,
    'MinSLPips':       500,
    'TrailActivate':   0.5,
    'TrailDistPips':   120,
    'TP_Pips':           0,
    'BB_Mid_TP':         0,
    'ExitBars':         12,
    'SessionStart':      7,
    'SessionEnd':       19,
    'BadHour':           8,
    'MaxTradesDay':      3,
    'LotRiskPct':      0.7,
    'MaxLots':         4.0,
}

SENSITIVITY_GRID = {
    'ADX_H4_Threshold': [15, 20, 25, 30, 35, 40, 999],
    'ADX_Threshold':    [20, 25, 30, 35, 999],
    'RSI_Oversold':     [25, 28, 32, 35, 38],
    'MinSLPips':        [200, 350, 500, 650],
    'TrailDistPips':    [60, 80, 100, 120, 160],
    'ExitBars':         [6, 8, 10, 12, 16],
}


def load_m30():
    df = pd.read_csv(CACHE_M30, index_col=0, parse_dates=True)
    print(f"  {len(df):,} barras ({df.index[0].date()} -> {df.index[-1].date()})")
    return df


def yearly_breakdown(trades, cap=INITIAL_CAPITAL):
    if len(trades) == 0:
        return
    t = trades.copy()
    t['year'] = pd.to_datetime(t['entry_dt']).dt.year
    print(f"\n  {'Ano':>4} {'N':>5} {'PnL':>10} {'WR':>6} {'DD':>6}  Estado")
    print("  " + "-" * 44)
    for yr, g in t.groupby('year'):
        pnl = g['pnl'].sum()
        wr  = (g['pnl'] > 0).mean() * 100
        eq  = g['equity'].values
        pk  = np.maximum.accumulate(eq)
        dd  = abs((eq - pk) / pk).max() * 100 if len(eq) > 0 else 0
        sig = "VERDE" if pnl > 0 else "ROJO"
        print(f"  {yr:>4} {len(g):>5} {pnl:>+10,.0f} {wr:>5.1f}% {dd:>5.1f}%  {sig}")


def monte_carlo(trades, n_sim=1000, cap=INITIAL_CAPITAL):
    pnls = trades['pnl'].values
    max_dds = []
    final_equities = []
    for _ in range(n_sim):
        shuffled = random.sample(list(pnls), len(pnls))
        eq = cap
        peak = cap
        max_dd = 0
        for p in shuffled:
            eq += p
            if eq > peak:
                peak = eq
            dd = (peak - eq) / peak * 100
            if dd > max_dd:
                max_dd = dd
        max_dds.append(max_dd)
        final_equities.append(eq)
    dds = np.array(max_dds)
    fes = np.array(final_equities)
    return {
        'p50_dd':  round(np.percentile(dds, 50), 1),
        'p90_dd':  round(np.percentile(dds, 90), 1),
        'p95_dd':  round(np.percentile(dds, 95), 1),
        'p99_dd':  round(np.percentile(dds, 99), 1),
        'pct_pos': round((fes > cap).mean() * 100, 1),
        'ruin':    round((fes < cap * 0.5).mean() * 100, 1),
    }


def sensitivity(df_full, param_name, values, base_params):
    print(f"\n  {param_name:<22}", end="")
    print(f"{'Valor':>7} {'IS_PF':>6} {'OOS_PF':>7} {'DD%':>6} {'N_IS':>6}")
    print("  " + "-" * 50)
    df_is  = df_full[df_full.index <= IS_END]
    df_oos = df_full[df_full.index >= OOS_START]
    for v in values:
        p = {**base_params, param_name: v}
        if param_name == 'RSI_Oversold':
            p['RSI_Overbought'] = 100 - v
        try:
            t_is  = run_backtest(add_indicators(df_is,  p), p, INITIAL_CAPITAL)
            t_oos = run_backtest(add_indicators(df_oos, p), p, INITIAL_CAPITAL)
            m_is  = compute_metrics(t_is,  INITIAL_CAPITAL)
            m_oos = compute_metrics(t_oos, INITIAL_CAPITAL)
            marker = " <--" if v == base_params.get(param_name) else ""
            print(f"  {'':<22} {v:>7} {m_is['pf']:>6.2f} {m_oos['pf']:>7.2f} "
                  f"{m_is['dd_pct']:>6.1f} {m_is['n']:>6}{marker}")
        except Exception:
            print(f"  {'':<22} {v:>7}  ERROR")


def main():
    sep = "=" * 58
    print(sep)
    print("  AGM_Ranger v6 — Robustez completa")
    print("  ADX_H4<30 + ADX_M30<30 | M30 | GBPJPY")
    print(sep)

    print("\n[1/5] Cargando datos...")
    df_raw = load_m30()
    df_ind = add_indicators(df_raw, V6_PARAMS)
    df_is  = df_ind[df_ind.index <= IS_END]
    df_oos = df_ind[df_ind.index >= OOS_START]

    print("\n[2/5] Backtest completo 2015-2026...")
    trades_all = run_backtest(df_ind, V6_PARAMS, INITIAL_CAPITAL)
    m_all      = compute_metrics(trades_all, INITIAL_CAPITAL)
    t_is       = run_backtest(df_is,  V6_PARAMS, INITIAL_CAPITAL)
    t_oos      = run_backtest(df_oos, V6_PARAMS, INITIAL_CAPITAL)
    m_is       = compute_metrics(t_is,  INITIAL_CAPITAL)
    m_oos      = compute_metrics(t_oos, INITIAL_CAPITAL)

    print(f"\n{sep}")
    print(f"  RESULTADO 2015-2026")
    print(sep)
    print(f"  Trades:       {m_all['n']}  |  PnL: ${m_all['pnl']:+,.0f}")
    print(f"  Rent. anual:  {m_all['ann_pct']:+.2f}%  |  WR: {m_all['wr']}%")
    print(f"  PF:           {m_all['pf']}  |  DD: {m_all['dd_pct']}%")
    print(f"  Calmar:       {m_all['calmar']}x")
    print(f"  Salidas:      {m_all['exits']}")

    yearly_breakdown(trades_all)

    print(f"\n{sep}")
    print(f"  WALK-FORWARD (IS 2015-2021 / OOS 2022-2026)")
    print(sep)
    print(f"  IS  -> N:{m_is['n']:4d}  PF:{m_is['pf']}  WR:{m_is['wr']}%  DD:{m_is['dd_pct']}%  PnL:${m_is['pnl']:+,.0f}")
    print(f"  OOS -> N:{m_oos['n']:4d}  PF:{m_oos['pf']}  WR:{m_oos['wr']}%  DD:{m_oos['dd_pct']}%  PnL:${m_oos['pnl']:+,.0f}")
    wf = round(m_oos['pf'] / m_is['pf'], 2) if m_is['pf'] > 0 else 0
    print(f"  WF ratio (OOS/IS): {wf}")
    print(sep)

    print("\n[3/5] Monte Carlo (1000 simulaciones)...")
    mc = monte_carlo(trades_all)
    print(f"\n{sep}")
    print(f"  MONTE CARLO — Drawdown esperado (1000 sims)")
    print(sep)
    print(f"  P50 DD:  {mc['p50_dd']}%")
    print(f"  P90 DD:  {mc['p90_dd']}%")
    print(f"  P95 DD:  {mc['p95_dd']}%")
    print(f"  P99 DD:  {mc['p99_dd']}%")
    print(f"  Sims positivas: {mc['pct_pos']}%  |  Ruina (<50%): {mc['ruin']}%")
    print(sep)

    print("\n[4/5] Sensibilidad de parametros...")
    print(f"\n{sep}")
    print(f"  SENSIBILIDAD (cambiar un parametro a la vez)")
    print(sep)
    for param, values in SENSITIVITY_GRID.items():
        sensitivity(df_ind, param, values, V6_PARAMS)

    # Veredicto
    positivos = sum(1 for _, g in trades_all.groupby(
        pd.to_datetime(trades_all['entry_dt']).dt.year) if g['pnl'].sum() > 0)
    total_anos = trades_all.groupby(
        pd.to_datetime(trades_all['entry_dt']).dt.year).ngroups

    score_pct = 0
    if m_all['pf'] >= 1.2:    score_pct += 20
    elif m_all['pf'] >= 1.1:  score_pct += 10
    if wf >= 1.0:              score_pct += 25
    if mc['pct_pos'] >= 80:   score_pct += 20
    elif mc['pct_pos'] >= 60: score_pct += 10
    if m_all['dd_pct'] <= 5:  score_pct += 20
    elif m_all['dd_pct'] <= 10: score_pct += 10
    if positivos >= total_anos * 0.8: score_pct += 15

    veredicto = "SOLIDA" if score_pct >= 70 else ("ACEPTABLE" if score_pct >= 50 else "FRAGIL")

    print(f"\n{sep}")
    print(f"  VEREDICTO FINAL — v6 vs v5")
    print(sep)
    print(f"  PF total:      {m_all['pf']}  (v5: 1.24)")
    print(f"  DD max:        {m_all['dd_pct']}%  (v5: 1.1%)")
    print(f"  WF ratio:      {wf}  (v5: 1.27)")
    print(f"  MC positivo:   {mc['pct_pos']}%  (v5: 95%)")
    print(f"  MC DD P95:     {mc['p95_dd']}%  (v5: 3.2%)")
    print(f"  Anos positivos:{positivos}/{total_anos}  (v5: 10/11)")
    print(f"  Rent. anual:   {m_all['ann_pct']}%  (v5: 0.45%)")
    print(f"  Score:         {score_pct}%  -> {veredicto}")
    print(sep)

    # Guardar reporte
    os.makedirs(os.path.join(os.path.dirname(__file__), "..", "reports"), exist_ok=True)
    out = os.path.join(os.path.dirname(__file__), "..", "reports", "AGM_Ranger_v6_Robustness.md")
    with open(out, 'w', encoding='utf-8') as f:
        f.write(f"# AGM_Ranger v6 — Robustez\n\n")
        f.write(f"ADX_H4<30 + ADX_M30<30 | M30 | GBPJPY 2015-2026\n\n")
        f.write(f"| Metrica | v6 | v5 |\n|---|---|---|\n")
        f.write(f"| PF total | {m_all['pf']} | 1.24 |\n")
        f.write(f"| DD max | {m_all['dd_pct']}% | 1.1% |\n")
        f.write(f"| WF ratio | {wf} | 1.27 |\n")
        f.write(f"| MC positivo | {mc['pct_pos']}% | 95% |\n")
        f.write(f"| MC DD P95 | {mc['p95_dd']}% | 3.2% |\n")
        f.write(f"| Anos positivos | {positivos}/{total_anos} | 10/11 |\n")
        f.write(f"| Rent. anual | {m_all['ann_pct']}% | 0.45% |\n")
        f.write(f"| Score | {score_pct}% — {veredicto} |\n")
    print(f"\n  Reporte -> {out}")
    trades_all.to_csv(out.replace('.md', '_trades.csv'), index=False)


if __name__ == "__main__":
    main()
