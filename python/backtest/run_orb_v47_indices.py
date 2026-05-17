"""Backtest ORB v4.7 en SPY (SP500) y QQQ (NAS100) con datos TwelveData M15."""
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

SIMBOLOS = [
    ('SP500_proxy',  'SPY (SP500)'),
    ('NAS100_proxy', 'QQQ (NAS100)'),
]


def run_one(name, pretty, df):
    df_ind = add_indicators(df, DEFAULT_PARAMS)
    df_is  = df_ind.loc[:IS_END]
    df_oos = df_ind.loc[OOS_START:]
    t_is   = run_backtest(df_is,  DEFAULT_PARAMS, INITIAL, pip=1.0, pip_val=100.0)
    t_oos  = run_backtest(df_oos, DEFAULT_PARAMS, INITIAL, pip=1.0, pip_val=100.0)
    m_is   = compute_metrics(t_is,  INITIAL)
    m_oos  = compute_metrics(t_oos, INITIAL)
    wf     = (m_oos['pf'] / m_is['pf']) if m_is['pf'] > 0 else 0

    print(f"\n  ORB v4.7 en {pretty}")
    print(f"  {'-'*60}")
    print(f"  IS  ({df_is.index[0].year}-{df_is.index[-1].year}):  PF={m_is['pf']}  WR={m_is['wr']}%  DD={m_is['dd_pct']}%  N={m_is['n']}  Ann={m_is['ann_pct']}%")
    print(f"  OOS ({df_oos.index[0].year}-{df_oos.index[-1].year}):  PF={m_oos['pf']}  WR={m_oos['wr']}%  DD={m_oos['dd_pct']}%  N={m_oos['n']}  Ann={m_oos['ann_pct']}%")
    print(f"  WF ratio: {round(wf, 3)}")

    if len(t_oos):
        meses = (pd.to_datetime(t_oos['exit_dt'].iloc[-1]) -
                 pd.to_datetime(t_oos['entry_dt'].iloc[0])).days / 30.44
        usd_mes = m_oos['pnl'] / meses if meses > 0 else 0
        print(f"  USD/mes OOS (en $50k): ${usd_mes:,.0f}")
        # Distribucion de exits
        exits = t_oos['exit_type'].value_counts()
        print(f"  Exits OOS: {dict(exits)}")


def main():
    print("="*72)
    print("  ORB v4.7  —  Indices M15 (SP500 vía SPY, NAS100 vía QQQ)")
    print("  Period: 2020-2025  | IS hasta 2023-12 | OOS 2024-2025")
    print("="*72)

    for name, pretty in SIMBOLOS:
        f = os.path.join(DATA, f'{name}_M15_twelvedata.csv')
        df = pd.read_csv(f, parse_dates=['time'], index_col='time')
        run_one(name, pretty, df)


if __name__ == '__main__':
    main()
