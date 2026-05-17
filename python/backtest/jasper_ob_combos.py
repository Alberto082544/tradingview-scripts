"""Test Jasper OB con combos de filtros de nuestros bots ganadores."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.stdout.reconfigure(encoding='utf-8')

import pandas as pd
from strategies.jasper_ob_filtered_m15 import (
    add_indicators, run_backtest, compute_metrics, DEFAULT_PARAMS)

DATA = os.path.join(os.path.dirname(__file__), '..', 'data')
INITIAL = 50_000
IS_END = '2021-12-31'
OOS_START = '2022-01-01'

# Activos y configs
ACTIVOS = [
    ('EURUSD_M15_histdata.csv',         'EURUSD',     0.0001, 10.0, None),
    ('GBPUSD_M15_histdata.csv',         'GBPUSD',     0.0001, 10.0, None),
    ('AUDNZD_M15_histdata.csv',         'AUDNZD',     0.0001,  6.0, 'time'),
    ('NAS100_proxy_M15_twelvedata.csv', 'QQQ',        1.0,   100.0, 'time'),
]

COMBOS = [
    ('A: BASE (sin filtros)',                    {}),
    ('B: + EMA200 H4',                            {'UseEMA200H4':1}),
    ('C: + EMA200 H4 + Wick',                    {'UseEMA200H4':1, 'UseWick':1}),
    ('D: + EMA200 H4 + VWAP + Wick',             {'UseEMA200H4':1, 'UseVWAP':1, 'UseWick':1}),
    ('E: + EMA200 H4 + ADX>20 + Wick',           {'UseEMA200H4':1, 'UseADXH4':1, 'UseWick':1}),
    ('F: TODO (EMA+VWAP+ADX+Wick+NY)',           {'UseEMA200H4':1, 'UseVWAP':1, 'UseADXH4':1, 'UseWick':1, 'UseNYSession':1}),
]


def run_one(nombre_activo, fname, pip, pip_val, time_col, combo_nombre, overrides):
    path = os.path.join(DATA, fname)
    if not os.path.exists(path): return None
    if time_col is None:
        df = pd.read_csv(path, index_col=0, parse_dates=True)
    else:
        df = pd.read_csv(path, parse_dates=[time_col], index_col=time_col)

    is_end_use = IS_END
    oos_start_use = OOS_START
    # QQQ: solo tenemos 2020-2025
    if 'NAS100' in fname or 'SP500' in fname:
        is_end_use = '2022-12-31'
        oos_start_use = '2023-01-01'

    p = {**DEFAULT_PARAMS, **overrides}
    df_ind = add_indicators(df, p)
    df_is  = df_ind.loc[:is_end_use]
    df_oos = df_ind.loc[oos_start_use:]
    if len(df_is) < 1000 or len(df_oos) < 500: return None

    t_is  = run_backtest(df_is,  p, INITIAL, pip=pip, pip_val=pip_val)
    t_oos = run_backtest(df_oos, p, INITIAL, pip=pip, pip_val=pip_val)
    m_is  = compute_metrics(t_is,  INITIAL)
    m_oos = compute_metrics(t_oos, INITIAL)
    wf    = (m_oos['pf']/m_is['pf']) if m_is['pf']>0 else 0
    return {'activo':nombre_activo, 'combo':combo_nombre,
            'is_pf':m_is['pf'], 'oos_pf':m_oos['pf'], 'oos_dd':m_oos['dd_pct'],
            'oos_ann':m_oos['ann_pct'], 'oos_n':m_oos['n'], 'wf':round(wf,2)}


def main():
    print("="*100)
    print("  JASPER OB + COMBOS DE FILTROS  —  test multi-activo")
    print("="*100)
    print(f"\n{'Activo':<10} {'Combo':<42} {'OOS_PF':>7} {'DD%':>6} {'Ann%':>7} {'N':>4} {'WF':>5} {'Veredicto':>12}")
    print('-'*100)

    for fname, nombre_activo, pip, pip_val, tc in ACTIVOS:
        print(f"\nProcesando {nombre_activo}...", flush=True)
        for combo_nombre, ov in COMBOS:
            r = run_one(nombre_activo, fname, pip, pip_val, tc, combo_nombre, ov)
            if r is None:
                print(f"  {combo_nombre}: SKIPPED", flush=True)
                continue
            ok = r['oos_pf']>1.3 and r['oos_dd']<10 and r['wf']>0.85 and r['oos_n']>=50
            v = "✓ MIGRAR" if ok else "x"
            print(f"  {nombre_activo:<10} {combo_nombre:<42} OOS PF={r['oos_pf']:>5.2f} DD={r['oos_dd']:>5.1f}% Ann={r['oos_ann']:>+6.1f}% N={r['oos_n']:>4} WF={r['wf']:>4.2f}  {v}", flush=True)


if __name__ == '__main__':
    main()
