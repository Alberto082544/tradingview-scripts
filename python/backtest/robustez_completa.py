"""Robustez year-by-year + checklist 7 puntos para AUDNZD v3 y EURUSD v2.

7 puntos anti-overfit:
  1. WF ratio (OOS/IS) >= 0.85
  2. >= 10/12 años positivos
  3. OOS Ann >= 50% de IS Ann
  4. OOS DD <= 2x IS DD
  5. N >= 200 (IS) / 100 (OOS)
  6. Peor año Ann >= -20%
  7. Cluster de parametros estable (sensibilidad)  ← chequeo aparte
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.stdout.reconfigure(encoding='utf-8')

import pandas as pd
import numpy as np

from strategies.ranger_c_audnzd_stoch import (
    add_indicators as audnzd_ind, run_backtest as audnzd_bt,
    compute_metrics as audnzd_m, DEFAULT_PARAMS as AUDNZD_DEF)
from strategies.ma_cross_m15 import (
    add_indicators as ma_ind, run_backtest as ma_bt,
    compute_metrics as ma_m, PAIR_CONFIG)

DATA = os.path.join(os.path.dirname(__file__), '..', 'data')
INITIAL = 50_000
IS_END = '2021-12-31'
OOS_START = '2022-01-01'

AUDNZD_PARAMS = {**AUDNZD_DEF, **{
    'ADX_H4_Max': 20, 'StochMode': 1, 'Stoch_K': 5, 'Stoch_D': 3,
    'Stoch_Long_Max': 15, 'Stoch_Short_Min': 75,
    'MinSLPips': 20, 'TrailDistPips': 4, 'ExitBars': 32,
    'RSI_Confirm': 1, 'BB_Mid_TP': 0, 'BadHour': 8,
}}
EURUSD_PARAMS = {
    'ATR_Period': 14, 'BE_Offset': 0.0002, 'Trail_Start': 1.5,
    'MaxSpreadPips': 3.0, 'LotRiskPct': 0.5, 'MaxLots': 4.0,
    'EMA_Fast': 8, 'SMA_Slow': 34, 'Dir_EMA_Fast': 8, 'Dir_SMA_Slow': 34,
    'SL_ATR_Mult': 2.0, 'RR': 2.5, 'Trail_Dist': 0.5, 'BE_Trigger': 0.5,
}


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


def checklist_7(bot_name, t_is, t_oos, capital=INITIAL):
    m_is  = audnzd_m(t_is,  capital)
    m_oos = audnzd_m(t_oos, capital)
    # Filtrar hora 8 si AUDNZD, hora 15 si EURUSD
    t_full = pd.concat([t_is, t_oos], ignore_index=True)
    t_full['entry_dt'] = pd.to_datetime(t_full['entry_dt'])

    years = sorted(t_full['entry_dt'].dt.year.unique())
    yearly = [metricas_year(t_full, y, capital) for y in years]
    yearly = [y for y in yearly if y is not None]

    positivos = sum(1 for y in yearly if y['ann'] > 0)
    peor_ann = min(y['ann'] for y in yearly)
    wf = m_oos['pf'] / m_is['pf'] if m_is['pf'] > 0 else 0
    ann_ratio = (m_oos['ann_pct'] / m_is['ann_pct']) if m_is['ann_pct'] != 0 else 0
    dd_ratio = (m_oos['dd_pct'] / m_is['dd_pct']) if m_is['dd_pct'] != 0 else 99

    print(f"\n{'='*72}")
    print(f"  {bot_name}  —  ROBUSTEZ YEAR-BY-YEAR + CHECKLIST 7 PUNTOS")
    print(f"{'='*72}")

    print(f"\n  Year-by-year (capital base $50k, % anual sobre capital):")
    print(f"  {'Año':<6} {'N':>4} {'PF':>6} {'WR%':>6} {'DD%':>6} {'Ann%':>8} {'PnL':>10}")
    for y in yearly:
        flag = '✓' if y['ann'] > 0 else '✗'
        print(f"  {y['year']:<6} {y['n']:>4} {y['pf']:>6} {y['wr']:>6} {y['dd']:>6} {y['ann']:>+8.2f}  ${y['pnl']:>+8,.0f}  {flag}")

    print(f"\n  CHECKLIST 7 PUNTOS:")
    c1 = wf >= 0.85
    c2 = positivos >= 10 * len(yearly) / 12   # 10/12 si tenemos 12 años
    c3 = ann_ratio >= 0.5
    c4 = dd_ratio <= 2.0
    c5 = m_is['n'] >= 200 and m_oos['n'] >= 100
    c6 = peor_ann >= -20
    print(f"  1. WF ratio >= 0.85:                          {wf:.3f}     {'✓' if c1 else '✗'}")
    print(f"  2. {positivos}/{len(yearly)} años positivos (mín {int(10*len(yearly)/12)}/{len(yearly)}):           {'✓' if c2 else '✗'}")
    print(f"  3. OOS Ann/IS Ann >= 0.5:                     {ann_ratio:.2f}      {'✓' if c3 else '✗'}")
    print(f"  4. OOS DD/IS DD <= 2.0:                       {dd_ratio:.2f}      {'✓' if c4 else '✗'}")
    print(f"  5. N (IS={m_is['n']}, OOS={m_oos['n']}) suficiente:        {'✓' if c5 else '✗'}")
    print(f"  6. Peor año Ann >= -20% (peor: {peor_ann:.1f}%):       {'✓' if c6 else '✗'}")
    print(f"  7. Sensibilidad de parámetros estable          (chequeo aparte)")

    passed = sum([c1, c2, c3, c4, c5, c6])
    print(f"\n  VEREDICTO: {passed}/6 puntos pasados (excluyendo sensibilidad)")
    return yearly


def main():
    # AUDNZD
    df_a = pd.read_csv(os.path.join(DATA, 'AUDNZD_M15_histdata.csv'),
                       parse_dates=['time'], index_col='time')
    df_a = audnzd_ind(df_a, AUDNZD_PARAMS)
    t_is_a  = audnzd_bt(df_a.loc[:IS_END],   AUDNZD_PARAMS, initial_capital=INITIAL)
    t_oos_a = audnzd_bt(df_a.loc[OOS_START:], AUDNZD_PARAMS, initial_capital=INITIAL)
    checklist_7("AUDNZD v3 (Mean Reversion)", t_is_a, t_oos_a)

    # EURUSD
    df_e = pd.read_csv(os.path.join(DATA, 'EURUSD_M15_histdata.csv'),
                       index_col=0, parse_dates=True)
    df_e = ma_ind(df_e, EURUSD_PARAMS)
    cfg = PAIR_CONFIG['EURUSD']
    t_is_e  = ma_bt(df_e.loc[:IS_END],   EURUSD_PARAMS, INITIAL, cfg['pip'], cfg['pip_val'])
    t_oos_e = ma_bt(df_e.loc[OOS_START:], EURUSD_PARAMS, INITIAL, cfg['pip'], cfg['pip_val'])
    checklist_7("EURUSD v2 (Trend Following)", t_is_e, t_oos_e)


if __name__ == '__main__':
    main()
