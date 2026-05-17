"""A/B test EURUSD v2: baseline vs variantes con ADX H4 + Stoch filter."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.stdout.reconfigure(encoding='utf-8')

import pandas as pd
from strategies.ma_cross_filtered_m15 import (
    add_indicators, run_backtest, compute_metrics, PAIR_CONFIG, DEFAULT_PARAMS)

DATA_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'EURUSD_M15_histdata.csv')
IS_END    = '2021-12-31'
OOS_START = '2022-01-01'
INITIAL   = 50_000

BASE = {**DEFAULT_PARAMS,
    'EMA_Fast': 8, 'SMA_Slow': 34,
    'Dir_EMA_Fast': 8, 'Dir_SMA_Slow': 34,
    'SL_ATR_Mult': 2.0, 'RR': 2.5,
    'Trail_Dist': 0.5, 'BE_Trigger': 0.5,
}

VARIANTES = [
    {'nombre': 'A: BASELINE (v2 actual)',         'overrides': {}},
    {'nombre': 'B: + ADX H4 > 20',                'overrides': {'ADX_H4_Min': 20}},
    {'nombre': 'C: + ADX H4 > 25',                'overrides': {'ADX_H4_Min': 25}},
    {'nombre': 'D: + Stoch filter',               'overrides': {'StochFilter': 1}},
    {'nombre': 'E: + ADX>20 + Stoch filter',      'overrides': {'ADX_H4_Min': 20, 'StochFilter': 1}},
    {'nombre': 'F: + ADX>25 + Stoch filter',      'overrides': {'ADX_H4_Min': 25, 'StochFilter': 1}},
]


def run_one(nombre, overrides, df_raw, cfg):
    p = {**BASE, **overrides}
    df = add_indicators(df_raw, p)
    df_is  = df.loc[:IS_END]
    df_oos = df.loc[OOS_START:]
    t_is  = run_backtest(df_is,  p, INITIAL, cfg['pip'], cfg['pip_val'])
    t_oos = run_backtest(df_oos, p, INITIAL, cfg['pip'], cfg['pip_val'])
    m_is  = compute_metrics(t_is,  INITIAL)
    m_oos = compute_metrics(t_oos, INITIAL)
    wf    = (m_oos['pf']/m_is['pf']) if m_is['pf'] > 0 else 0
    return {'nombre': nombre,
            'is_pf': m_is['pf'], 'is_dd': m_is['dd_pct'], 'is_n': m_is['n'],
            'oos_pf': m_oos['pf'], 'oos_wr': m_oos['wr'], 'oos_dd': m_oos['dd_pct'],
            'oos_ann': m_oos['ann_pct'], 'oos_n': m_oos['n'], 'wf': round(wf, 3)}


def main():
    print(f"Cargando {DATA_PATH}...", flush=True)
    df = pd.read_csv(DATA_PATH, index_col=0, parse_dates=True)
    print(f"Datos: {df.index[0]} -> {df.index[-1]} ({len(df)} barras)\n", flush=True)

    cfg = PAIR_CONFIG['EURUSD']
    results = []
    for v in VARIANTES:
        print(f"  {v['nombre']}...", flush=True)
        r = run_one(v['nombre'], v['overrides'], df, cfg)
        results.append(r)
        print(f"    IS PF={r['is_pf']} DD={r['is_dd']}% N={r['is_n']}", flush=True)
        print(f"    OOS PF={r['oos_pf']} DD={r['oos_dd']}% WR={r['oos_wr']}% N={r['oos_n']} Ann={r['oos_ann']}% WF={r['wf']}\n", flush=True)

    print("="*92)
    print("RESUMEN COMPARATIVO")
    print("="*92)
    rdf = pd.DataFrame(results)
    print(rdf.to_string(index=False))

    base = results[0]
    print("\n" + "="*92)
    print(f"VEREDICTO (vs BASELINE: PF={base['oos_pf']} DD={base['oos_dd']}% WF={base['wf']})")
    print("="*92)
    for r in results[1:]:
        mejor_pf = r['oos_pf'] > base['oos_pf']
        mejor_wf = r['wf']     > base['wf']
        mejor_dd = r['oos_dd'] < base['oos_dd']
        veredicto = "MIGRAR" if (mejor_pf and mejor_wf and mejor_dd) else "no migrar"
        print(f"  {r['nombre']:35s} → {veredicto}  (PF Δ={r['oos_pf']-base['oos_pf']:+.2f}, DD Δ={r['oos_dd']-base['oos_dd']:+.1f}%, WF Δ={r['wf']-base['wf']:+.3f})")


if __name__ == '__main__':
    main()
