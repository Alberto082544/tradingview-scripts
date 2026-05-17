"""Test EMA9+VWAP+RSI con params ganadores QQQ en otros activos.
Solo activos donde tengamos datos M15 ya disponibles."""
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

# Params ganadores QQQ
PARAMS = {**DEFAULT_PARAMS, **{
    'EMA_Fast': 9, 'EMA_Mid': 21,
    'RSI_Buy_Min': 35, 'RSI_Buy_Max': 75,
    'SL_ATR_Mult': 1.0, 'TP1_Mult': 2.0,
    'WickRatio': 1.5,
}}

# Activos a probar (csv + cfg)
ACTIVOS = [
    ('SP500_proxy_M15_twelvedata.csv', 'SPY (SP500)',  1.0, 100.0, 'time'),
    ('EURUSD_M15_histdata.csv',         'EURUSD',     0.0001, 10.0, None),
    ('GBPUSD_M15_histdata.csv',         'GBPUSD',     0.0001, 10.0, None),
    ('AUDNZD_M15_histdata.csv',         'AUDNZD',     0.0001,  6.0, 'time'),
    ('AUDCAD_M15_histdata.csv',         'AUDCAD',     0.0001,  7.3, 'time'),
    ('GBPJPY_M15_dukas.csv',            'GBPJPY',     0.01,    6.5, None),
]


def run_one(fname, pretty, pip, pip_val, time_col):
    path = os.path.join(DATA, fname)
    if not os.path.exists(path):
        print(f"  {pretty}: archivo no existe")
        return
    try:
        if time_col is None:
            df = pd.read_csv(path, index_col=0, parse_dates=True)
        else:
            df = pd.read_csv(path, parse_dates=[time_col], index_col=time_col)
    except Exception as e:
        print(f"  {pretty}: error cargar {e}")
        return

    df_ind = add_indicators(df, PARAMS)
    df_is  = df_ind.loc[:IS_END]
    df_oos = df_ind.loc[OOS_START:]
    if len(df_is) < 1000 or len(df_oos) < 500:
        print(f"  {pretty}: datos insuficientes ({len(df_is)}/{len(df_oos)})")
        return

    t_is  = run_backtest(df_is,  PARAMS, INITIAL, pip=pip, pip_val=pip_val)
    t_oos = run_backtest(df_oos, PARAMS, INITIAL, pip=pip, pip_val=pip_val)
    m_is  = compute_metrics(t_is, INITIAL)
    m_oos = compute_metrics(t_oos, INITIAL)
    wf    = (m_oos['pf']/m_is['pf']) if m_is['pf']>0 else 0

    veredicto = "✓ VIABLE" if (m_oos['pf']>1.3 and m_oos['dd_pct']<10 and wf>0.85 and m_oos['n']>=50) else "x"

    print(f"  {pretty:14s}  IS:PF={m_is['pf']:.2f} N={m_is['n']:4d}  |  OOS:PF={m_oos['pf']:.2f} DD={m_oos['dd_pct']:.1f}% Ann={m_oos['ann_pct']:+.1f}% N={m_oos['n']:3d}  WF={round(wf,2)}  {veredicto}")


def main():
    print("="*92)
    print("  EMA9+VWAP+RSI (params QQQ ganador) en OTROS ACTIVOS")
    print("  Criterio viable: PF OOS > 1.3, DD < 10%, WF > 0.85, N >= 50")
    print("="*92)

    for fname, pretty, pip, pip_val, tc in ACTIVOS:
        run_one(fname, pretty, pip, pip_val, tc)


if __name__ == '__main__':
    main()
