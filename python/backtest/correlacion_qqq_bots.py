"""Correlacion entre EMA9+VWAP+RSI y Jasper OB combo C en QQQ.
Si correlacion baja → ambos diversifican.
Si alta → mejor uno solo."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.stdout.reconfigure(encoding='utf-8')

import pandas as pd
import numpy as np

from strategies.ema9_vwap_rsi import (
    add_indicators as ema_ind, run_backtest as ema_bt, DEFAULT_PARAMS as EMA_DEF)
from strategies.jasper_ob_filtered_m15 import (
    add_indicators as jasp_ind, run_backtest as jasp_bt, DEFAULT_PARAMS as JASP_DEF)

DATA = os.path.join(os.path.dirname(__file__), '..', 'data',
                    'NAS100_proxy_M15_twelvedata.csv')
INITIAL = 50_000
OOS_START = '2023-01-01'

EMA_PARAMS = {**EMA_DEF, 'EMA_Fast':9, 'EMA_Mid':21,
              'RSI_Buy_Min':35, 'RSI_Buy_Max':75,
              'SL_ATR_Mult':1.0, 'TP1_Mult':2.0, 'WickRatio':1.5}
JASP_PARAMS = {**JASP_DEF, 'UseEMA200H4':1, 'UseWick':1}


def main():
    df = pd.read_csv(DATA, parse_dates=['time'], index_col='time')

    df_ema = ema_ind(df, EMA_PARAMS)
    df_jasp = jasp_ind(df, JASP_PARAMS)

    t_ema  = ema_bt(df_ema.loc[OOS_START:],  EMA_PARAMS,  INITIAL, pip=1.0, pip_val=100.0)
    t_jasp = jasp_bt(df_jasp.loc[OOS_START:], JASP_PARAMS, INITIAL, pip=1.0, pip_val=100.0)

    print(f"  EMA9+VWAP+RSI: {len(t_ema)} trades")
    print(f"  Jasper OB:     {len(t_jasp)} trades")

    # PnL diario
    daily_ema  = (t_ema.set_index(pd.to_datetime(t_ema['exit_dt']))
                       .groupby(pd.Grouper(freq='D'))['pnl'].sum())
    daily_jasp = (t_jasp.set_index(pd.to_datetime(t_jasp['exit_dt']))
                       .groupby(pd.Grouper(freq='D'))['pnl'].sum())

    daily = pd.concat([daily_ema, daily_jasp], axis=1).fillna(0)
    daily.columns = ['EMA9_VWAP', 'JasperOB']

    print(f"\n  Dias con actividad EMA9: {(daily['EMA9_VWAP']!=0).sum()}")
    print(f"  Dias con actividad JOB:  {(daily['JasperOB']!=0).sum()}")
    print(f"  Dias coincidentes (ambos): {((daily['EMA9_VWAP']!=0) & (daily['JasperOB']!=0)).sum()}")

    corr = daily.corr().iloc[0,1]
    print(f"\n  Correlacion diaria EMA9 vs Jasper OB: {corr:.4f}")

    if abs(corr) < 0.3:
        cor_txt = "BAJA — diversifican bien, vale la pena tener AMBOS"
    elif abs(corr) < 0.5:
        cor_txt = "MODERADA — aportan algo, pero redundancia parcial"
    else:
        cor_txt = "ALTA — son redundantes, mejor solo el mejor (EMA9)"
    print(f"  → {cor_txt}")

    # DD agregado vs individual
    def dd(s):
        eq = INITIAL + s.cumsum()
        return abs(((eq - eq.cummax())/eq.cummax()).min())*100

    dd_e = dd(daily['EMA9_VWAP'])
    dd_j = dd(daily['JasperOB'])
    dd_agg = dd(daily['EMA9_VWAP'] + daily['JasperOB'])
    print(f"\n  DD individuales: EMA9={dd_e:.2f}% | Jasper={dd_j:.2f}%")
    print(f"  DD agregado:     {dd_agg:.2f}%  ({dd_agg/(dd_e+dd_j)*100:.0f}% de la suma)")


if __name__ == '__main__':
    main()
