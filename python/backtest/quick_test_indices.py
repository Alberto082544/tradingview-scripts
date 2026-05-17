"""Test rapido: MA Cross v2 y Ranger C v3 aplicados a SPY (SP500) y QQQ (NAS100).

Solo OOS 2024-2025 para ver si la idea tiene base sin gastar tiempo en grids.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.stdout.reconfigure(encoding='utf-8')

import pandas as pd
import numpy as np

from strategies.ma_cross_m15 import (
    add_indicators as ma_ind, run_backtest as ma_bt,
    compute_metrics as ma_m)
from strategies.ranger_c_audnzd_stoch import (
    add_indicators as rc_ind, run_backtest as rc_bt,
    compute_metrics as rc_m, DEFAULT_PARAMS as RC_DEF)

DATA = os.path.join(os.path.dirname(__file__), '..', 'data')
INITIAL = 50_000
IS_END = '2023-12-31'
OOS_START = '2024-01-01'

# Configs para indices (ETFs):
# SPY ~$680, QQQ ~$614
# Pip=1 punto USD, pip_val=$1 por punto por lote estándar
# OJO: lote estándar para ETF = 100 acciones. Si tradeamos 1 lote forex equiv.,
# en ETF sería 1 acción. Para igualar la escala: pip_val=1
INDICES_CFG = {
    'SP500_proxy':  {'pip': 1.0, 'pip_val': 100.0, 'pretty': 'SPY (SP500)'},
    'NAS100_proxy': {'pip': 1.0, 'pip_val': 100.0, 'pretty': 'QQQ (NAS100)'},
}

# Params winning forex
MA_PARAMS = {
    'ATR_Period': 14, 'BE_Offset': 0.5, 'Trail_Start': 1.5,
    'MaxSpreadPips': 30, 'LotRiskPct': 0.5, 'MaxLots': 4.0,
    'EMA_Fast': 8, 'SMA_Slow': 34, 'Dir_EMA_Fast': 8, 'Dir_SMA_Slow': 34,
    'SL_ATR_Mult': 2.0, 'RR': 2.5, 'Trail_Dist': 0.5, 'BE_Trigger': 0.5,
}

RC_PARAMS = {**RC_DEF, **{
    'ADX_H4_Max': 20, 'StochMode': 1, 'Stoch_K': 5, 'Stoch_D': 3,
    'Stoch_Long_Max': 15, 'Stoch_Short_Min': 75,
    'MinSLPips': 0.5, 'TrailDistPips': 0.2, 'ExitBars': 32,
    'RSI_Confirm': 1, 'BB_Mid_TP': 0, 'BadHour': -1,
}}


def cargar(name):
    f = os.path.join(DATA, f'{name}_M15_twelvedata.csv')
    df = pd.read_csv(f, parse_dates=['time'], index_col='time')
    return df


def test_ma_cross(name, df, cfg):
    df_full = ma_ind(df, MA_PARAMS)
    df_is  = df_full.loc[:IS_END]
    df_oos = df_full.loc[OOS_START:]
    t_is  = ma_bt(df_is,  MA_PARAMS, INITIAL, cfg['pip'], cfg['pip_val'])
    t_oos = ma_bt(df_oos, MA_PARAMS, INITIAL, cfg['pip'], cfg['pip_val'])
    m_is  = ma_m(t_is,  INITIAL)
    m_oos = ma_m(t_oos, INITIAL)
    wf    = (m_oos['pf']/m_is['pf']) if m_is['pf'] > 0 else 0
    print(f"  MA Cross v2 en {cfg['pretty']}:")
    print(f"    IS  ({df_is.index[0].year}-{df_is.index[-1].year}): PF={m_is['pf']} DD={m_is['dd_pct']}% N={m_is['n']} Ann={m_is['ann_pct']}%")
    print(f"    OOS ({df_oos.index[0].year}-{df_oos.index[-1].year}): PF={m_oos['pf']} DD={m_oos['dd_pct']}% N={m_oos['n']} Ann={m_oos['ann_pct']}%")
    print(f"    WF={round(wf,3)}")


def test_ranger_c(name, df, cfg):
    df_full = rc_ind(df, RC_PARAMS)
    df_is  = df_full.loc[:IS_END]
    df_oos = df_full.loc[OOS_START:]
    t_is  = rc_bt(df_is,  RC_PARAMS, initial_capital=INITIAL, nzdusd=cfg['pip_val'])
    t_oos = rc_bt(df_oos, RC_PARAMS, initial_capital=INITIAL, nzdusd=cfg['pip_val'])
    m_is  = rc_m(t_is,  INITIAL)
    m_oos = rc_m(t_oos, INITIAL)
    wf    = (m_oos['pf']/m_is['pf']) if m_is['pf'] > 0 else 0
    print(f"  Ranger C v3 en {cfg['pretty']}:")
    print(f"    IS  ({df_is.index[0].year}-{df_is.index[-1].year}): PF={m_is['pf']} DD={m_is['dd_pct']}% N={m_is['n']} Ann={m_is['ann_pct']}%")
    print(f"    OOS ({df_oos.index[0].year}-{df_oos.index[-1].year}): PF={m_oos['pf']} DD={m_oos['dd_pct']}% N={m_oos['n']} Ann={m_oos['ann_pct']}%")
    print(f"    WF={round(wf,3)}")


def main():
    print("="*72)
    print("  QUICK TEST  MA Cross + Ranger C  en SPY (SP500) y QQQ (NAS100)")
    print("  Period: 2020-2025  | IS hasta 2023-12 | OOS desde 2024-01")
    print("  Params idénticos a los winning de forex (NO re-optimizado)")
    print("="*72)

    for name, cfg in INDICES_CFG.items():
        df = cargar(name)
        print(f"\n--- {cfg['pretty']} ({len(df):,} barras) ---")
        try:
            test_ma_cross(name, df, cfg)
        except Exception as e:
            print(f"  MA Cross error: {e}")
        try:
            test_ranger_c(name, df, cfg)
        except Exception as e:
            print(f"  Ranger C error: {e}")


if __name__ == '__main__':
    main()
