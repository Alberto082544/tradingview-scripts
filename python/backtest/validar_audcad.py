"""Validacion completa AUDCAD: robustez year-by-year + Monte Carlo + checklist 7."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.stdout.reconfigure(encoding='utf-8')

import pandas as pd
import numpy as np

from strategies.ranger_c_audcad_m15 import (
    add_indicators, run_backtest, compute_metrics, DEFAULT_PARAMS)

DATA = os.path.join(os.path.dirname(__file__), '..', 'data', 'AUDCAD_M15_histdata.csv')
INITIAL = 50_000
IS_END = '2021-12-31'
OOS_START = '2022-01-01'
N_SIM = 1000

# Mejor combo DD<5% (PF OOS 1.29, DD 4.6%, Ann 7%, WF 1.075)
PARAMS = {**DEFAULT_PARAMS, **{
    'ADX_H4_Max': 15, 'StochMode': 1, 'Stoch_K': 5, 'Stoch_D': 3,
    'Stoch_Long_Max': 25, 'Stoch_Short_Min': 75,
    'MinSLPips': 30, 'TrailDistPips': 15, 'ExitBars': 32,
    'RSI_Confirm': 1, 'BB_Mid_TP': 0,
}}


def metricas_year(trades, year):
    t = trades.copy()
    t['entry_dt'] = pd.to_datetime(t['entry_dt'])
    t_y = t[t['entry_dt'].dt.year == year].copy()
    if len(t_y) == 0: return None
    pnl = t_y['pnl'].sum()
    wins = t_y.loc[t_y['pnl'] > 0, 'pnl']; loss = t_y.loc[t_y['pnl'] < 0, 'pnl']
    pf = wins.sum() / abs(loss.sum()) if len(loss) and loss.sum()!=0 else 0
    eq = INITIAL + t_y.sort_values('entry_dt')['pnl'].cumsum().values
    eq = np.concatenate([[INITIAL], eq])
    pk = np.maximum.accumulate(eq)
    dd = abs(((eq-pk)/pk).min()) * 100
    return {'year':year, 'n':len(t_y), 'pf':round(pf,2),
            'dd':round(dd,2), 'ann':round(pnl/INITIAL*100,2)}


def mc_dd(pnls, n=N_SIM):
    rng = np.random.default_rng(42)
    dds = np.empty(n)
    for i in range(n):
        order = rng.permutation(len(pnls))
        eq = INITIAL + np.cumsum(pnls[order])
        peak = np.maximum.accumulate(eq)
        dds[i] = ((eq - peak)/peak).min() * -100
    return {'p50':np.percentile(dds,50), 'p95':np.percentile(dds,95),
            'p99':np.percentile(dds,99), 'max':dds.max()}


def main():
    print("="*78)
    print("  VALIDACION COMPLETA  AUDCAD  Ranger C (Stoch+ADX<15)")
    print("="*78)

    df = pd.read_csv(DATA, parse_dates=['time'], index_col='time')
    df_ind = add_indicators(df, PARAMS)
    df_is  = df_ind.loc[:IS_END]
    df_oos = df_ind.loc[OOS_START:]

    t_is  = run_backtest(df_is,  PARAMS, initial_capital=INITIAL)
    t_oos = run_backtest(df_oos, PARAMS, initial_capital=INITIAL)
    t_full = pd.concat([t_is, t_oos], ignore_index=True)

    m_is  = compute_metrics(t_is,  INITIAL)
    m_oos = compute_metrics(t_oos, INITIAL)

    t_full['entry_dt'] = pd.to_datetime(t_full['entry_dt'])
    years = sorted(t_full['entry_dt'].dt.year.unique())
    yearly = [metricas_year(t_full, y) for y in years if metricas_year(t_full, y)]

    print(f"\n  YEAR-BY-YEAR ($50k):")
    print(f"  {'Año':<6} {'N':>5} {'PF':>6} {'DD%':>6} {'Ann%':>8}")
    for y in yearly:
        f = 'OK' if y['ann']>0 else 'X'
        print(f"  {y['year']:<6} {y['n']:>5} {y['pf']:>6} {y['dd']:>6} {y['ann']:>+8.2f}  {f}")

    pos = sum(1 for y in yearly if y['ann']>0)
    peor = min(y['ann'] for y in yearly)

    mc = mc_dd(t_oos['pnl'].values)
    print(f"\n  MONTE CARLO OOS (1000 sims):")
    print(f"    DD OOS real: {m_oos['dd_pct']}%")
    print(f"    P50: {mc['p50']:.2f}%  P95: {mc['p95']:.2f}%  P99: {mc['p99']:.2f}%  Max: {mc['max']:.2f}%")

    wf = m_oos['pf']/m_is['pf'] if m_is['pf']>0 else 0
    ann_r = m_oos['ann_pct']/m_is['ann_pct'] if m_is['ann_pct']!=0 else 0
    dd_r  = m_oos['dd_pct']/m_is['dd_pct'] if m_is['dd_pct']!=0 else 99

    c1 = wf >= 0.85
    c2 = pos >= len(yearly) * 10 / 12
    c3 = ann_r >= 0.5
    c4 = dd_r <= 2.0
    c5 = m_is['n'] >= 200 and m_oos['n'] >= 100
    c6 = peor >= -20
    c7 = mc['p95'] < 10.0

    def m(x): return 'OK' if x else 'X'
    print(f"\n  CHECKLIST 7 PUNTOS:")
    print(f"  1. WF {wf:.3f} >= 0.85:           {m(c1)}")
    print(f"  2. {pos}/{len(yearly)} años positivos:        {m(c2)}")
    print(f"  3. OOS Ann/IS Ann {ann_r:.2f} >= 0.5:  {m(c3)}")
    print(f"  4. OOS DD/IS DD {dd_r:.2f} <= 2.0:    {m(c4)}")
    print(f"  5. N IS={m_is['n']} OOS={m_oos['n']}: {m(c5)}")
    print(f"  6. Peor año {peor:.1f}% >= -20%:   {m(c6)}")
    print(f"  7. MC P95 {mc['p95']:.1f}% < 10%:       {m(c7)}")
    print(f"\n  VEREDICTO: {sum([c1,c2,c3,c4,c5,c6,c7])}/7 pasados")
    print(f"\n  Metricas resumen OOS:  PF={m_oos['pf']}  DD={m_oos['dd_pct']}%  Ann={m_oos['ann_pct']}%")
    print(f"  En $15k a 0.5% lotrisk: ~${m_oos['pnl']/15:.0f} OOS total (4 años ~ ${m_oos['pnl']/(4*12):.0f}/mes)")
    print(f"  Ajustado proporcional: ~${m_oos['pnl']*15/(50*48):.0f}/mes en $15k")


if __name__ == '__main__':
    main()
