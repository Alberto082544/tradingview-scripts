"""Robustez completa del bot ganador EMA9+VWAP+RSI en QQQ:
  - Year-by-year
  - Monte Carlo (1000 sims)
  - Checklist 7 puntos anti-overfitting
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.stdout.reconfigure(encoding='utf-8')

import pandas as pd
import numpy as np

from strategies.ema9_vwap_rsi import (
    add_indicators, run_backtest, compute_metrics, DEFAULT_PARAMS)

DATA = os.path.join(os.path.dirname(__file__), '..', 'data',
                    'NAS100_proxy_M15_twelvedata.csv')
INITIAL = 50_000
IS_END = '2023-12-31'
OOS_START = '2024-01-01'
N_SIM = 1000

# Mejor combo de la optimizacion (OOS PF=1.76, DD=3.0%, WF=1.344, Ann=17.1%)
BEST_PARAMS = {**DEFAULT_PARAMS, **{
    'EMA_Fast': 9, 'EMA_Mid': 21,
    'RSI_Buy_Min': 35, 'RSI_Buy_Max': 75,
    'RSI_Sell_Min': 30, 'RSI_Sell_Max': 65,
    'SL_ATR_Mult': 1.0, 'TP1_Mult': 2.0,
    'WickRatio': 1.5,
}}


def metricas_year(trades, year, capital=INITIAL):
    t = trades.copy()
    t['entry_dt'] = pd.to_datetime(t['entry_dt'])
    t_y = t[t['entry_dt'].dt.year == year].copy()
    if len(t_y) == 0:
        return None
    pnl = t_y['pnl'].sum()
    wins = t_y.loc[t_y['pnl'] > 0, 'pnl']
    loss = t_y.loc[t_y['pnl'] < 0, 'pnl']
    pf = wins.sum() / abs(loss.sum()) if len(loss) and loss.sum() != 0 else 0
    eq = capital + t_y.sort_values('entry_dt')['pnl'].cumsum().values
    eq = np.concatenate([[capital], eq])
    pk = np.maximum.accumulate(eq)
    dd = abs(((eq - pk) / pk).min()) * 100
    wr = (t_y['pnl'] > 0).mean() * 100
    ann = pnl / capital * 100
    return {'year':year, 'n':len(t_y), 'pf':round(pf,2), 'wr':round(wr,1),
            'dd':round(dd,2), 'pnl':round(pnl,0), 'ann':round(ann,2)}


def monte_carlo_dd(pnls, n=N_SIM):
    rng = np.random.default_rng(42)
    dds = np.empty(n)
    for i in range(n):
        order = rng.permutation(len(pnls))
        eq = INITIAL + np.cumsum(pnls[order])
        peak = np.maximum.accumulate(eq)
        dds[i] = ((eq - peak) / peak).min() * -100
    return {
        'dd_p50': np.percentile(dds, 50),
        'dd_p95': np.percentile(dds, 95),
        'dd_p99': np.percentile(dds, 99),
        'dd_max': dds.max(),
    }


def main():
    print("="*78)
    print("  ROBUSTEZ COMPLETA  EMA9+VWAP+RSI  QQQ (NAS100 proxy)")
    print("="*78)

    df = pd.read_csv(DATA, parse_dates=['time'], index_col='time')
    df_ind = add_indicators(df, BEST_PARAMS)
    df_is  = df_ind.loc[:IS_END]
    df_oos = df_ind.loc[OOS_START:]

    t_is  = run_backtest(df_is,  BEST_PARAMS, INITIAL, pip=1.0, pip_val=100.0)
    t_oos = run_backtest(df_oos, BEST_PARAMS, INITIAL, pip=1.0, pip_val=100.0)
    t_full = pd.concat([t_is, t_oos], ignore_index=True)

    m_is  = compute_metrics(t_is,  INITIAL)
    m_oos = compute_metrics(t_oos, INITIAL)

    # 1. Year-by-year
    t_full['entry_dt'] = pd.to_datetime(t_full['entry_dt'])
    years = sorted(t_full['entry_dt'].dt.year.unique())
    yearly = [metricas_year(t_full, y) for y in years]
    yearly = [y for y in yearly if y is not None]

    print(f"\n  YEAR-BY-YEAR (capital $50k):")
    print(f"  {'Año':<6} {'N':>4} {'PF':>6} {'WR%':>6} {'DD%':>6} {'Ann%':>8} {'PnL':>10}")
    for y in yearly:
        flag = 'OK' if y['ann'] > 0 else 'X'
        print(f"  {y['year']:<6} {y['n']:>4} {y['pf']:>6} {y['wr']:>6} {y['dd']:>6} {y['ann']:>+8.2f}  ${y['pnl']:>+8,.0f}  {flag}")

    # 2. Monte Carlo OOS
    print(f"\n  MONTE CARLO ({N_SIM} simulaciones reorden de trades OOS):")
    mc = monte_carlo_dd(t_oos['pnl'].values)
    print(f"    DD OOS real: {m_oos['dd_pct']}%")
    print(f"    DD P50: {mc['dd_p50']:.2f}%  P95: {mc['dd_p95']:.2f}%  P99: {mc['dd_p99']:.2f}%  Max: {mc['dd_max']:.2f}%")

    # 3. Checklist 7 puntos
    print(f"\n  CHECKLIST 7 PUNTOS:")
    wf = m_oos['pf']/m_is['pf'] if m_is['pf']>0 else 0
    pos = sum(1 for y in yearly if y['ann']>0)
    peor = min(y['ann'] for y in yearly)
    ann_ratio = m_oos['ann_pct']/m_is['ann_pct'] if m_is['ann_pct']!=0 else 0
    dd_ratio = m_oos['dd_pct']/m_is['dd_pct'] if m_is['dd_pct']!=0 else 99

    c1 = wf >= 0.85
    c2 = pos >= len(yearly) * 10 / 12  # adaptado a 6 años
    c3 = ann_ratio >= 0.5
    c4 = dd_ratio <= 2.0
    c5 = m_is['n'] >= 200 and m_oos['n'] >= 100
    c6 = peor >= -20
    c7 = mc['dd_p95'] < 10.0  # Monte Carlo P95 razonable

    def mk(flag): return 'OK' if flag else 'X'

    print(f"  1. WF ratio >= 0.85:              {wf:.3f}     {mk(c1)}")
    print(f"  2. {pos}/{len(yearly)} años positivos:           {mk(c2)}")
    print(f"  3. OOS Ann / IS Ann >= 0.5:       {ann_ratio:.2f}     {mk(c3)}")
    print(f"  4. OOS DD / IS DD <= 2.0:         {dd_ratio:.2f}     {mk(c4)}")
    print(f"  5. N IS={m_is['n']} OOS={m_oos['n']} >= 200/100:   {mk(c5)}")
    print(f"  6. Peor año {peor:.1f}% >= -20%:    {mk(c6)}")
    print(f"  7. MC P95 DD {mc['dd_p95']:.1f}% < 10%:        {mk(c7)}")

    passed = sum([c1,c2,c3,c4,c5,c6,c7])
    print(f"\n  VEREDICTO: {passed}/7 puntos pasados")

    if passed >= 6:
        print(f"\n  ✓ EMA9+VWAP+RSI QQQ APTO COMO 3er BOT")
        print(f"  En cuenta $15k a LotRiskPct 0.5%:")
        usd_mes = m_oos['pnl'] / ((pd.to_datetime(t_oos['exit_dt'].iloc[-1]) -
                                   pd.to_datetime(t_oos['entry_dt'].iloc[0])).days / 30.44)
        print(f"    PnL OOS: ${m_oos['pnl']:,.0f} ({m_oos['ann_pct']}%/año)")
        print(f"    USD/mes en $50k: ${usd_mes:,.0f}")
        print(f"    USD/mes en $15k: ${usd_mes*15/50:,.0f}")


if __name__ == '__main__':
    main()
