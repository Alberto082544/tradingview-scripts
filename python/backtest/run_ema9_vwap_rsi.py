"""Backtest EMA9+EMA21+VWAP+RSI en SPY (SP500) y QQQ (NAS100)."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.stdout.reconfigure(encoding='utf-8')

import pandas as pd
from strategies.ema9_vwap_rsi import (
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

    print(f"\n  EMA9+EMA21+VWAP+RSI en {pretty}")
    print(f"  {'-'*60}")
    print(f"  IS  (2020-2023):  PF={m_is['pf']}  WR={m_is['wr']}%  DD={m_is['dd_pct']}%  N={m_is['n']}  Ann={m_is['ann_pct']}%  PnL=${m_is['pnl']:,.0f}")
    print(f"  OOS (2024-2025):  PF={m_oos['pf']}  WR={m_oos['wr']}%  DD={m_oos['dd_pct']}%  N={m_oos['n']}  Ann={m_oos['ann_pct']}%  PnL=${m_oos['pnl']:,.0f}")
    print(f"  WF ratio: {round(wf, 3)}")
    if len(t_oos):
        exits = t_oos['exit_type'].value_counts()
        print(f"  Exits OOS: {dict(exits)}")


def main():
    print("="*72)
    print("  EMA9+EMA21+VWAP+RSI  —  Indices M15 (intraday)")
    print("  Estrategia del usuario, primera prueba en SPY/QQQ")
    print("="*72)

    df_spy = pd.read_csv(os.path.join(DATA, 'SP500_proxy_M15_twelvedata.csv'),
                          parse_dates=['time'], index_col='time')
    df_qqq = pd.read_csv(os.path.join(DATA, 'NAS100_proxy_M15_twelvedata.csv'),
                          parse_dates=['time'], index_col='time')

    run_one('SP500_proxy', 'SPY (SP500)', df_spy)
    run_one('NAS100_proxy', 'QQQ (NAS100)', df_qqq)


if __name__ == '__main__':
    main()
