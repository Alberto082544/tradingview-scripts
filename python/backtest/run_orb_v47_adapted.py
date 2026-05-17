"""Backtest ORB v4.7 con parametros ADAPTADOS al precio de ETF.
SPY/QQQ se mueven $1-5 en la sesion, no 100-300 puntos como el SPX/NDX reales.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.stdout.reconfigure(encoding='utf-8')

import pandas as pd
from strategies.orb_v47_indices import (
    add_indicators, run_backtest, compute_metrics, DEFAULT_PARAMS)

DATA = os.path.join(os.path.dirname(__file__), '..', 'data')
INITIAL = 50_000
IS_END = '2023-12-31'
OOS_START = '2024-01-01'

# Parametros ADAPTADOS al precio de los ETF (~$680 SPY, $610 QQQ)
SPY_PARAMS = {**DEFAULT_PARAMS, **{
    'BufPts':   0.3,
    'MinRng':   0.5,
    'MaxRng':  10.0,
    'TpMult':   2.0,
    'EmaLen':  200,
    'MaxTpd':    2,
    'LotRiskPct': 0.5,
}}

QQQ_PARAMS = {**DEFAULT_PARAMS, **{
    'BufPts':   0.5,
    'MinRng':   1.0,
    'MaxRng':  20.0,
    'TpMult':   2.0,
    'EmaLen':  200,
    'MaxTpd':    2,
    'LotRiskPct': 0.5,
}}


def run_one(name, pretty, df, params):
    df_ind = add_indicators(df, params)
    df_is  = df_ind.loc[:IS_END]
    df_oos = df_ind.loc[OOS_START:]
    t_is   = run_backtest(df_is,  params, INITIAL, pip=1.0, pip_val=100.0)
    t_oos  = run_backtest(df_oos, params, INITIAL, pip=1.0, pip_val=100.0)
    m_is   = compute_metrics(t_is,  INITIAL)
    m_oos  = compute_metrics(t_oos, INITIAL)
    wf     = (m_oos['pf'] / m_is['pf']) if m_is['pf'] > 0 else 0

    print(f"\n  ORB v4.7 ADAPTADO en {pretty}  (BufPts={params['BufPts']}, MinRng={params['MinRng']}, MaxRng={params['MaxRng']}, TpMult={params['TpMult']})")
    print(f"  {'-'*78}")
    print(f"  IS  (2020-2023):  PF={m_is['pf']}  WR={m_is['wr']}%  DD={m_is['dd_pct']}%  N={m_is['n']}  Ann={m_is['ann_pct']}%  PnL=${m_is['pnl']:,.0f}")
    print(f"  OOS (2024-2025):  PF={m_oos['pf']}  WR={m_oos['wr']}%  DD={m_oos['dd_pct']}%  N={m_oos['n']}  Ann={m_oos['ann_pct']}%  PnL=${m_oos['pnl']:,.0f}")
    print(f"  WF ratio: {round(wf, 3)}")
    if len(t_oos):
        exits = t_oos['exit_type'].value_counts()
        print(f"  Exits OOS: {dict(exits)}")


def main():
    print("="*78)
    print("  ORB v4.7 ADAPTADO  —  SPY (SP500) y QQQ (NAS100) M15")
    print("  Parametros ajustados al precio del ETF (~$680/$610)")
    print("="*78)

    df_spy = pd.read_csv(os.path.join(DATA, 'SP500_proxy_M15_twelvedata.csv'),
                          parse_dates=['time'], index_col='time')
    df_qqq = pd.read_csv(os.path.join(DATA, 'NAS100_proxy_M15_twelvedata.csv'),
                          parse_dates=['time'], index_col='time')

    run_one('SP500_proxy',  'SPY (SP500)',  df_spy, SPY_PARAMS)
    run_one('NAS100_proxy', 'QQQ (NAS100)', df_qqq, QQQ_PARAMS)


if __name__ == '__main__':
    main()
