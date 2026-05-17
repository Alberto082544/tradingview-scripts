"""Búsqueda AUDCAD con Stochastic buscando DD<5% para fondeo.
Mismo grid que el AUDNZD ganador."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.stdout.reconfigure(encoding='utf-8')

import pandas as pd
import itertools
from strategies.ranger_c_audcad_m15 import add_indicators, run_backtest, compute_metrics, DEFAULT_PARAMS

DATA_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'AUDCAD_M15_histdata.csv')
IS_END    = '2021-12-31'
OOS_START = '2022-01-01'
INITIAL   = 50_000

GRID = {
    'ADX_H4_Max':       [15, 18, 20],
    'Stoch_Long_Max':   [15, 20, 25],
    'Stoch_Short_Min':  [75, 80, 85],
    'StochMode':        [1],  # Stoch solo (como AUDNZD ganador)
    'MinSLPips':        [12, 20, 30],
    'TrailDistPips':    [4, 8, 15],
    'ExitBars':         [16, 32],
    'RSI_Confirm':      [1],
}

FIXED = {'BB_Mid_TP': 0, 'Stoch_K': 5, 'Stoch_D': 3}


def main():
    print(f"Cargando {DATA_PATH}...", flush=True)
    df = pd.read_csv(DATA_PATH, parse_dates=['time'], index_col='time')
    print(f"Datos: {df.index[0]} -> {df.index[-1]} ({len(df)} barras)", flush=True)

    combos = [dict(zip(GRID.keys(), c)) for c in itertools.product(*GRID.values())]
    print(f"Grid: {len(combos)} combos\n", flush=True)

    results = []
    for i, combo in enumerate(combos, 1):
        p = {**DEFAULT_PARAMS, **FIXED, **combo}
        df_idx = add_indicators(df, p)
        df_is  = df_idx.loc[:IS_END]
        df_oos = df_idx.loc[OOS_START:]
        t_is  = run_backtest(df_is,  p, initial_capital=INITIAL)
        t_oos = run_backtest(df_oos, p, initial_capital=INITIAL)
        m_is  = compute_metrics(t_is,  INITIAL)
        m_oos = compute_metrics(t_oos, INITIAL)
        wf    = (m_oos['pf'] / m_is['pf']) if m_is['pf'] > 0 else 0
        results.append({**combo,
             'is_pf': m_is['pf'], 'is_dd': m_is['dd_pct'], 'is_n': m_is['n'],
             'oos_pf': m_oos['pf'], 'oos_dd': m_oos['dd_pct'], 'oos_n': m_oos['n'],
             'oos_wr': m_oos['wr'], 'oos_ann': m_oos['ann_pct'],
             'oos_pnl': m_oos['pnl'], 'wf': round(wf, 3)})
        if i % 20 == 0:
            print(f"  {i}/{len(combos)} combos...", flush=True)

    rdf = pd.DataFrame(results)
    out_csv = os.path.join(os.path.dirname(__file__), '..', 'reports', 'AUDCAD_DD5_Search.csv')
    rdf.to_csv(out_csv, index=False)
    print(f"\nGuardado: {out_csv}", flush=True)

    apt = rdf[(rdf['oos_dd'] < 5.0) & (rdf['oos_pf'] > 1.0) & (rdf['oos_n'] >= 200)].copy()
    apt = apt.sort_values('oos_ann', ascending=False)

    print("\n" + "="*90, flush=True)
    print(f"CANDIDATOS APTOS DD<5% (PF>1, N>=200): {len(apt)}", flush=True)
    print("="*90, flush=True)
    if len(apt) > 0:
        print(apt.head(10).to_string(index=False), flush=True)
    else:
        print("⚠️  Sin combos DD<5% — AUDCAD NO viable para fondeo, descartar", flush=True)
        print("\nTop 5 por DD bajo (sin restriccion):", flush=True)
        print(rdf[(rdf['oos_pf']>1.0) & (rdf['oos_n']>=200)].sort_values('oos_dd').head(5).to_string(index=False), flush=True)


if __name__ == '__main__':
    main()
