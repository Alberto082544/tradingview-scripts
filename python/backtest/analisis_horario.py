"""Analisis horario AUDNZD v3 y EURUSD v2: detectar mejores y peores horas."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.stdout.reconfigure(encoding='utf-8')

import pandas as pd
import numpy as np

from strategies.ranger_c_audnzd_stoch import (
    add_indicators as audnzd_ind, run_backtest as audnzd_bt, DEFAULT_PARAMS as AUDNZD_DEF)
from strategies.ma_cross_m15 import (
    add_indicators as ma_ind, run_backtest as ma_bt, PAIR_CONFIG)

DATA = os.path.join(os.path.dirname(__file__), '..', 'data')
INITIAL = 50_000
OOS_START = '2022-01-01'

AUDNZD_PARAMS = {**AUDNZD_DEF, **{
    'ADX_H4_Max': 20, 'StochMode': 1, 'Stoch_K': 5, 'Stoch_D': 3,
    'Stoch_Long_Max': 15, 'Stoch_Short_Min': 75,
    'MinSLPips': 20, 'TrailDistPips': 4, 'ExitBars': 32,
    'RSI_Confirm': 1, 'BB_Mid_TP': 0,
}}
EURUSD_PARAMS = {
    'ATR_Period': 14, 'BE_Offset': 0.0002, 'Trail_Start': 1.5,
    'MaxSpreadPips': 3.0, 'LotRiskPct': 0.5, 'MaxLots': 4.0,
    'EMA_Fast': 8, 'SMA_Slow': 34, 'Dir_EMA_Fast': 8, 'Dir_SMA_Slow': 34,
    'SL_ATR_Mult': 2.0, 'RR': 2.5, 'Trail_Dist': 0.5, 'BE_Trigger': 0.5,
}


def analizar(nombre, trades):
    t = trades.copy()
    t['entry_dt'] = pd.to_datetime(t['entry_dt'])
    t['hora'] = t['entry_dt'].dt.hour
    g = t.groupby('hora').agg(
        n     =('pnl', 'count'),
        pnl   =('pnl', 'sum'),
        wins  =('pnl', lambda s: (s > 0).sum()),
        avg   =('pnl', 'mean'),
    ).round(1)
    g['wr']    = (100 * g['wins'] / g['n']).round(1)
    g_pf = t.groupby('hora').apply(
        lambda d: d.loc[d['pnl']>0,'pnl'].sum() / abs(d.loc[d['pnl']<0,'pnl'].sum())
                  if d.loc[d['pnl']<0,'pnl'].sum() != 0 else 0,
        include_groups=False
    ).round(2)
    g['pf'] = g_pf

    print(f"\n{'='*72}")
    print(f"  {nombre}  (total trades OOS: {len(t)})")
    print(f"{'='*72}")
    print(g[['n','wins','wr','pf','pnl','avg']].to_string())

    # Detectar horas malas
    print(f"\n  HORAS MALAS  (PF < 0.8 con n >= 15 trades):")
    bad = g[(g['pf'] < 0.8) & (g['n'] >= 15)]
    if len(bad):
        print(bad[['n','wr','pf','pnl']].to_string())
        sum_loss = bad['pnl'].sum()
        print(f"  Total perdido en horas malas: ${sum_loss:,.0f}")
    else:
        print("  Ninguna hora mala estructural — distribución uniforme")

    # Detectar horas top
    print(f"\n  HORAS TOP  (PF > 1.5 con n >= 15 trades):")
    top = g[(g['pf'] > 1.5) & (g['n'] >= 15)]
    if len(top):
        print(top[['n','wr','pf','pnl']].to_string())
    else:
        print("  Ninguna hora con PF claramente superior")

    return g


def main():
    print("="*72)
    print("  ANALISIS HORARIO  AUDNZD v3 + EURUSD v2  (OOS 2022-2025)")
    print("="*72)

    # AUDNZD
    df_a = pd.read_csv(os.path.join(DATA, 'AUDNZD_M15_histdata.csv'),
                       parse_dates=['time'], index_col='time')
    df_a = audnzd_ind(df_a, AUDNZD_PARAMS)
    t_aud = audnzd_bt(df_a.loc[OOS_START:], AUDNZD_PARAMS, initial_capital=INITIAL)
    analizar("AUDNZD v3", t_aud)

    # EURUSD
    df_e = pd.read_csv(os.path.join(DATA, 'EURUSD_M15_histdata.csv'),
                       index_col=0, parse_dates=True)
    df_e = ma_ind(df_e, EURUSD_PARAMS)
    cfg = PAIR_CONFIG['EURUSD']
    t_eur = ma_bt(df_e.loc[OOS_START:], EURUSD_PARAMS, INITIAL, cfg['pip'], cfg['pip_val'])
    analizar("EURUSD v2", t_eur)


if __name__ == '__main__':
    main()
