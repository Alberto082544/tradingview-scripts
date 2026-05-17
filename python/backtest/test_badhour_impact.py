"""Impacto del filtro BadHour en AUDNZD (hora 8) y EURUSD (hora 15)."""
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
OOS_START = '2022-01-01'

AUDNZD_PARAMS = {**AUDNZD_DEF, **{
    'ADX_H4_Max': 20, 'StochMode': 1, 'Stoch_K': 5, 'Stoch_D': 3,
    'Stoch_Long_Max': 15, 'Stoch_Short_Min': 75,
    'MinSLPips': 20, 'TrailDistPips': 4, 'ExitBars': 32,
    'RSI_Confirm': 1, 'BB_Mid_TP': 0,
    'BadHour': -1,  # baseline
}}
EURUSD_PARAMS = {
    'ATR_Period': 14, 'BE_Offset': 0.0002, 'Trail_Start': 1.5,
    'MaxSpreadPips': 3.0, 'LotRiskPct': 0.5, 'MaxLots': 4.0,
    'EMA_Fast': 8, 'SMA_Slow': 34, 'Dir_EMA_Fast': 8, 'Dir_SMA_Slow': 34,
    'SL_ATR_Mult': 2.0, 'RR': 2.5, 'Trail_Dist': 0.5, 'BE_Trigger': 0.5,
}


def filtrar_hora(trades, hora_mala):
    """Elimina del backtest los trades cuya hora de entrada == hora_mala."""
    t = trades.copy()
    t['entry_dt'] = pd.to_datetime(t['entry_dt'])
    return t[t['entry_dt'].dt.hour != hora_mala].reset_index(drop=True)


def recalcular_metricas(trades, capital=INITIAL):
    """Recalcula equity, DD, etc. tras filtrar trades."""
    if len(trades) == 0:
        return {'n':0, 'pf':0, 'wr':0, 'dd_pct':0, 'ann_pct':0, 'pnl':0}
    t = trades.copy().sort_values('entry_dt').reset_index(drop=True)
    eq = capital + t['pnl'].cumsum()
    pk = eq.cummax()
    dd = abs(((eq - pk) / pk).min()) * 100
    pnl = t['pnl'].sum()
    wr = (t['pnl'] > 0).mean() * 100
    wins = t.loc[t['pnl'] > 0, 'pnl']
    loss = t.loc[t['pnl'] < 0, 'pnl']
    pf = wins.sum() / abs(loss.sum()) if len(loss) > 0 and loss.sum() != 0 else 0
    yrs = (pd.to_datetime(t['exit_dt'].iloc[-1]) -
           pd.to_datetime(t['entry_dt'].iloc[0])).days / 365.25
    ann = ((capital + pnl) / capital) ** (1 / max(yrs, 0.01)) - 1
    return {'n':len(t), 'pf':round(pf,2), 'wr':round(wr,1),
            'dd_pct':round(dd,2), 'ann_pct':round(ann*100,2), 'pnl':round(pnl,0)}


def main():
    # AUDNZD
    df_a = pd.read_csv(os.path.join(DATA, 'AUDNZD_M15_histdata.csv'),
                       parse_dates=['time'], index_col='time')
    df_a = audnzd_ind(df_a, AUDNZD_PARAMS)
    t_aud = audnzd_bt(df_a.loc[OOS_START:], AUDNZD_PARAMS, initial_capital=INITIAL)
    m_a_base = recalcular_metricas(t_aud)
    t_aud_filt = filtrar_hora(t_aud, 8)
    m_a_filt = recalcular_metricas(t_aud_filt)

    # EURUSD
    df_e = pd.read_csv(os.path.join(DATA, 'EURUSD_M15_histdata.csv'),
                       index_col=0, parse_dates=True)
    df_e = ma_ind(df_e, EURUSD_PARAMS)
    cfg = PAIR_CONFIG['EURUSD']
    t_eur = ma_bt(df_e.loc[OOS_START:], EURUSD_PARAMS, INITIAL, cfg['pip'], cfg['pip_val'])
    m_e_base = recalcular_metricas(t_eur)
    t_eur_filt = filtrar_hora(t_eur, 15)
    m_e_filt = recalcular_metricas(t_eur_filt)

    print("="*72)
    print("  IMPACTO FILTRO HORARIO  (OOS 2022-2025)")
    print("="*72)
    print(f"\n  AUDNZD v3 (sin hora 8):")
    print(f"    Base:     N={m_a_base['n']}  PF={m_a_base['pf']}  DD={m_a_base['dd_pct']}%  Ann={m_a_base['ann_pct']}%  PnL=${m_a_base['pnl']:,.0f}")
    print(f"    Filtrado: N={m_a_filt['n']}  PF={m_a_filt['pf']}  DD={m_a_filt['dd_pct']}%  Ann={m_a_filt['ann_pct']}%  PnL=${m_a_filt['pnl']:,.0f}")
    print(f"    Delta:    PF {m_a_filt['pf']-m_a_base['pf']:+.2f}   DD {m_a_filt['dd_pct']-m_a_base['dd_pct']:+.2f}%   PnL {m_a_filt['pnl']-m_a_base['pnl']:+,.0f}")

    print(f"\n  EURUSD v2 (sin hora 15):")
    print(f"    Base:     N={m_e_base['n']}  PF={m_e_base['pf']}  DD={m_e_base['dd_pct']}%  Ann={m_e_base['ann_pct']}%  PnL=${m_e_base['pnl']:,.0f}")
    print(f"    Filtrado: N={m_e_filt['n']}  PF={m_e_filt['pf']}  DD={m_e_filt['dd_pct']}%  Ann={m_e_filt['ann_pct']}%  PnL=${m_e_filt['pnl']:,.0f}")
    print(f"    Delta:    PF {m_e_filt['pf']-m_e_base['pf']:+.2f}   DD {m_e_filt['dd_pct']-m_e_base['dd_pct']:+.2f}%   PnL {m_e_filt['pnl']-m_e_base['pnl']:+,.0f}")


if __name__ == '__main__':
    main()
