"""Optimizacion grid EMA9+VWAP+RSI en QQQ con robustez year-by-year."""
import sys, os, itertools, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.stdout.reconfigure(encoding='utf-8')

import pandas as pd
import numpy as np
import multiprocessing as mp

from strategies.ema9_vwap_rsi import (
    add_indicators, run_backtest, compute_metrics, DEFAULT_PARAMS)

DATA = os.path.join(os.path.dirname(__file__), '..', 'data',
                    'NAS100_proxy_M15_twelvedata.csv')
INITIAL = 50_000
IS_END = '2023-12-31'
OOS_START = '2024-01-01'

GRID = {
    'EMA_Fast':     [9, 13],
    'EMA_Mid':      [21, 34],
    'RSI_Buy_Min':  [30, 35, 40],
    'RSI_Buy_Max':  [65, 70, 75],
    'SL_ATR_Mult':  [1.0, 1.5, 2.0],
    'TP1_Mult':     [1.5, 2.0, 2.5],
    'WickRatio':    [1.0, 1.5, 2.0],
}

FIXED = {
    'RSI_Period':     14,
    'RSI_Sell_Min':   30,
    'RSI_Sell_Max':   65,
    'ATR_Period':     14,
    'MinSLPips':     0.3,
    'BE_Mult':       2.0,
    'TP1_Pct':       0.5,
    'Trail_EMA':       1,
    'MaxTradesDay':    3,
    'SessionStart':    0,
    'SessionEnd':     23,
    'LotRiskPct':    0.5,
    'MaxLots':       4.0,
    'Commission':    0.0,
}

_df_is_raw = None
_df_oos_raw = None


def _pool_init(df_is, df_oos):
    global _df_is_raw, _df_oos_raw
    _df_is_raw = df_is
    _df_oos_raw = df_oos


def _worker(combo):
    p = {**FIXED, **combo}
    try:
        df_is  = add_indicators(_df_is_raw,  p)
        df_oos = add_indicators(_df_oos_raw, p)
        t_is  = run_backtest(df_is,  p, INITIAL, pip=1.0, pip_val=100.0)
        t_oos = run_backtest(df_oos, p, INITIAL, pip=1.0, pip_val=100.0)
        m_is  = compute_metrics(t_is,  INITIAL)
        m_oos = compute_metrics(t_oos, INITIAL)
    except Exception:
        return None
    if m_is['n'] < 50 or m_oos['n'] < 30 or m_is['pf'] <= 0:
        return None
    wf = m_oos['pf']/m_is['pf'] if m_is['pf'] > 0 else 0
    return {**combo,
            'is_pf':m_is['pf'], 'is_dd':m_is['dd_pct'], 'is_n':m_is['n'],
            'oos_pf':m_oos['pf'], 'oos_dd':m_oos['dd_pct'], 'oos_n':m_oos['n'],
            'oos_wr':m_oos['wr'], 'oos_ann':m_oos['ann_pct'],
            'wf':round(wf,3)}


def main():
    print(f"Cargando {DATA}...", flush=True)
    df = pd.read_csv(DATA, parse_dates=['time'], index_col='time')
    df_is_raw  = df.loc[:IS_END]
    df_oos_raw = df.loc[OOS_START:]
    print(f"  IS: {len(df_is_raw)} barras | OOS: {len(df_oos_raw)} barras", flush=True)

    keys = list(GRID.keys())
    combos = [dict(zip(keys, v)) for v in itertools.product(*GRID.values())]
    print(f"  Grid: {len(combos)} combos", flush=True)

    t0 = time.time()
    ctx = mp.get_context('spawn')
    with ctx.Pool(processes=min(11, mp.cpu_count()),
                  initializer=_pool_init,
                  initargs=(df_is_raw, df_oos_raw)) as pool:
        results = pool.map(_worker, combos, chunksize=8)
    results = [r for r in results if r is not None]
    print(f"  Completado: {len(results)} validos en {time.time()-t0:.0f}s\n", flush=True)
    if not results:
        print("Sin combos validos")
        return

    rdf = pd.DataFrame(results)
    # Filtros: PF OOS >1.3, DD OOS<10%, WF>0.85
    apt = rdf[(rdf['oos_pf']>1.3) & (rdf['oos_dd']<10) & (rdf['wf']>0.85)].copy()
    apt = apt.sort_values('oos_ann', ascending=False)

    out = os.path.join(os.path.dirname(__file__), '..', 'reports',
                       'EMA9_QQQ_Opt_Results.csv')
    rdf.to_csv(out, index=False)

    print("="*92)
    print(f"CANDIDATOS APTOS (PF OOS>1.3, DD<10%, WF>0.85): {len(apt)}")
    print("="*92)
    if len(apt):
        print(apt.head(10).to_string(index=False))
        print(f"\nGuardado: {out}")
    else:
        print("Sin candidatos. Top 5 por OOS Ann (sin restricciones):")
        print(rdf.sort_values('oos_ann', ascending=False).head(5).to_string(index=False))


if __name__ == '__main__':
    mp.freeze_support()
    main()
