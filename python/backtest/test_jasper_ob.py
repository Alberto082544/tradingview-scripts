"""Test Jasper OB Strategy en varios activos (forex + indices)."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.stdout.reconfigure(encoding='utf-8')

import pandas as pd
from strategies.jasper_ob_m15 import (
    add_indicators, run_backtest, compute_metrics, DEFAULT_PARAMS)

DATA = os.path.join(os.path.dirname(__file__), '..', 'data')
INITIAL = 50_000
IS_END = '2021-12-31'
OOS_START = '2022-01-01'

ACTIVOS = [
    ('EURUSD_M15_histdata.csv',         'EURUSD',         0.0001, 10.0, None,   None),
    ('GBPUSD_M15_histdata.csv',         'GBPUSD',         0.0001, 10.0, None,   None),
    ('AUDNZD_M15_histdata.csv',         'AUDNZD',         0.0001,  6.0, 'time', None),
    ('AUDCAD_M15_histdata.csv',         'AUDCAD',         0.0001,  7.3, 'time', None),
    ('GBPJPY_M15_dukas.csv',            'GBPJPY',         0.01,    6.5, None,   None),
    ('SP500_proxy_M15_twelvedata.csv',  'SPY (SP500)',    1.0,   100.0, 'time', '2020'),
    ('NAS100_proxy_M15_twelvedata.csv', 'QQQ (NAS100)',   1.0,   100.0, 'time', '2020'),
]


def run_one(fname, pretty, pip, pip_val, time_col, is_end_override):
    path = os.path.join(DATA, fname)
    if not os.path.exists(path):
        print(f"  {pretty:14s} archivo no existe")
        return
    try:
        if time_col is None:
            df = pd.read_csv(path, index_col=0, parse_dates=True)
        else:
            df = pd.read_csv(path, parse_dates=[time_col], index_col=time_col)
    except Exception as e:
        print(f"  {pretty:14s} error cargar: {e}")
        return

    is_end_use = IS_END if is_end_override is None else f"{is_end_override}-12-31"
    oos_use = OOS_START if is_end_override is None else f"{int(is_end_override)+2}-01-01"
    # Para datasets cortos como SPY/QQQ (2020-2025): IS=2020-2022, OOS=2023-2025
    if is_end_override:
        is_end_use = '2022-12-31'
        oos_use = '2023-01-01'

    df_ind = add_indicators(df, DEFAULT_PARAMS)
    df_is  = df_ind.loc[:is_end_use]
    df_oos = df_ind.loc[oos_use:]

    if len(df_is) < 1000 or len(df_oos) < 500:
        print(f"  {pretty:14s} datos insuficientes")
        return

    t_is  = run_backtest(df_is,  DEFAULT_PARAMS, INITIAL, pip=pip, pip_val=pip_val)
    t_oos = run_backtest(df_oos, DEFAULT_PARAMS, INITIAL, pip=pip, pip_val=pip_val)
    m_is  = compute_metrics(t_is,  INITIAL)
    m_oos = compute_metrics(t_oos, INITIAL)
    wf    = (m_oos['pf']/m_is['pf']) if m_is['pf']>0 else 0

    veredicto = "VIABLE" if (m_oos['pf']>1.3 and m_oos['dd_pct']<10 and wf>0.85 and m_oos['n']>=50) else "x"
    print(f"  {pretty:14s}  IS PF={m_is['pf']:.2f} N={m_is['n']:4d}  |  OOS PF={m_oos['pf']:.2f} DD={m_oos['dd_pct']:.1f}% Ann={m_oos['ann_pct']:+.1f}% N={m_oos['n']:3d}  WF={round(wf,2)}  {veredicto}")


def main():
    print("="*100)
    print("  JASPER OB STRATEGY  —  Test en varios activos")
    print("  Criterio viable: PF OOS > 1.3, DD < 10%, WF > 0.85, N >= 50")
    print("="*100)
    for fname, pretty, pip, pip_val, tc, is_end in ACTIVOS:
        run_one(fname, pretty, pip, pip_val, tc, is_end)


if __name__ == '__main__':
    main()
