"""Analiza la peor perdida en 1 solo dia (DD diario) para AUDNZD+EURUSD."""
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


def get_daily(trades):
    return (trades.set_index(pd.to_datetime(trades['exit_dt']))
                  .groupby(pd.Grouper(freq='D'))['pnl'].sum())


def stats_dias_perdedores(daily, nombre, capital=INITIAL):
    days_loss = daily[daily < 0]
    if len(days_loss) == 0:
        return
    days_loss_pct = (days_loss / capital * 100).abs()
    print(f"\n=== {nombre} ===")
    print(f"  Dias con perdida: {len(days_loss)} de {len(daily[daily != 0])} dias con actividad")
    print(f"  Perdida media en dia rojo:    {days_loss.mean():>8.2f} USD  ({days_loss_pct.mean():.2f}%)")
    print(f"  Perdida P95 en dia rojo:      {np.percentile(days_loss, 5):>8.2f} USD  ({np.percentile(days_loss_pct, 95):.2f}%)")
    print(f"  Perdida P99 en dia rojo:      {np.percentile(days_loss, 1):>8.2f} USD  ({np.percentile(days_loss_pct, 99):.2f}%)")
    print(f"  PEOR DIA HISTORICO:           {days_loss.min():>8.2f} USD  ({days_loss_pct.max():.2f}%)")


def main():
    print("="*70)
    print("  PEOR DIA / DD DIARIO  AUDNZD v3 + EURUSD v2  OOS 2022-2025")
    print("="*70)

    df_a = pd.read_csv(os.path.join(DATA, 'AUDNZD_M15_histdata.csv'),
                       parse_dates=['time'], index_col='time')
    df_a = audnzd_ind(df_a, AUDNZD_PARAMS)
    t_aud = audnzd_bt(df_a.loc[OOS_START:], AUDNZD_PARAMS, initial_capital=INITIAL)

    df_e = pd.read_csv(os.path.join(DATA, 'EURUSD_M15_histdata.csv'),
                       index_col=0, parse_dates=True)
    df_e = ma_ind(df_e, EURUSD_PARAMS)
    cfg = PAIR_CONFIG['EURUSD']
    t_eur = ma_bt(df_e.loc[OOS_START:], EURUSD_PARAMS, INITIAL, cfg['pip'], cfg['pip_val'])

    daily_a = get_daily(t_aud)
    daily_e = get_daily(t_eur)
    daily_combined = pd.concat([daily_a, daily_e], axis=1).fillna(0).sum(axis=1)

    stats_dias_perdedores(daily_a, "AUDNZD v3 solo")
    stats_dias_perdedores(daily_e, "EURUSD v2 solo")
    stats_dias_perdedores(daily_combined, "AMBOS COMBINADOS")

    # ¿Cuántos dias romperian 5% diario?
    print("\n" + "="*70)
    print("  ¿CUANTOS DIAS HISTORICOS ROMPERIAN DD DIARIO 5% ?")
    print("="*70)
    for nombre, daily in [("AUDNZD solo", daily_a),
                          ("EURUSD solo", daily_e),
                          ("AMBOS",       daily_combined)]:
        breaches = (daily < -INITIAL*0.05).sum()
        worst_pct = (daily.min() / INITIAL * 100) if len(daily) else 0
        print(f"  {nombre:20s}: {breaches} dias rotos  (peor dia: {worst_pct:.2f}%)")


if __name__ == '__main__':
    main()
