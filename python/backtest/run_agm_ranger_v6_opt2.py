"""
AGM_Ranger v6 — Segunda optimizacion
Foco: conseguir salidas reales (trailing + BB_Mid), no solo TIME.
Problema anterior: MinSLPips=500 impide activar trailing (necesita 250 pips de ganancia).
Solucion: SLs mas ajustados + BB_Mid_TP activo.

IS: 2015-2021 | OOS: 2022-2026
Uso: python -m backtest.run_agm_ranger_v6_opt2
"""
import os, sys, itertools, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import pandas as pd
import multiprocessing as mp

from strategies.agm_ranger_v6 import add_indicators, run_backtest, compute_metrics

CACHE_M30       = os.path.join(os.path.dirname(__file__), "..", "data", "GBPJPY_M30_dukas.csv")
INITIAL_CAPITAL = 50_000.0
IS_END          = "2021-12-31"
OOS_START       = "2022-01-01"

# Grid centrado en salidas reales
GRID = {
    'RSI_Oversold':      [28, 32, 35],
    'ADX_H4_Threshold':  [25, 30, 35],
    'ADX_Threshold':     [30, 999],
    'BB_Mid_TP':         [0, 1],
    'MinSLPips':         [80, 120, 150, 200],    # SLs ajustados para que trailing active
    'TrailDistPips':     [40, 60, 80, 120],
    'TrailActivate':     [0.3, 0.5],             # activar trailing antes
    'ExitBars':          [6, 8, 12],
}

FIXED = {
    'BB_Period':        20,
    'BB_StdDev':       2.0,
    'RSI_Period':       14,
    'RSI_Overbought':   68,
    'ADX_Period':       14,
    'ADX_H4_Period':    14,
    'SL_ATR_Mult':     1.5,
    'ATR_Period':       14,
    'MaxSLPips':       999,
    'TP_Pips':           0,
    'SessionStart':      7,
    'SessionEnd':       19,
    'BadHour':           8,
    'MaxTradesDay':      3,
    'LotRiskPct':      0.7,
    'MaxLots':         4.0,
}


def _worker(args):
    combo, df_is, df_oos = args
    params = {**FIXED, **combo}
    params['RSI_Overbought'] = 100 - params['RSI_Oversold']

    try:
        t_is  = run_backtest(add_indicators(df_is,  params), params, INITIAL_CAPITAL)
        t_oos = run_backtest(add_indicators(df_oos, params), params, INITIAL_CAPITAL)
        m_is  = compute_metrics(t_is,  INITIAL_CAPITAL)
        m_oos = compute_metrics(t_oos, INITIAL_CAPITAL)
    except Exception:
        return None

    if m_is['n'] < 20 or m_is['pf'] <= 0:
        return None

    # Penalizar si mas del 80% de salidas son TIME (no hay salidas reales)
    exits_is = t_is['exit_type'].value_counts(normalize=True).to_dict() if len(t_is) > 0 else {}
    time_pct = exits_is.get('TIME', 1.0)

    return {
        **combo,
        'is_n':      m_is['n'],
        'is_pf':     m_is['pf'],
        'is_wr':     m_is['wr'],
        'is_dd':     m_is['dd_pct'],
        'is_pnl':    m_is['pnl'],
        'is_ann':    m_is.get('ann_pct', 0),
        'oos_n':     m_oos['n'],
        'oos_pf':    m_oos['pf'],
        'oos_wr':    m_oos['wr'],
        'oos_dd':    m_oos['dd_pct'],
        'oos_pnl':   m_oos['pnl'],
        'time_pct':  round(time_pct * 100, 1),
        'wf_ratio':  round(m_oos['pf'] / m_is['pf'], 3) if m_is['pf'] > 0 else 0,
    }


def _score(row):
    # Bonificar salidas reales (penalizar si todo es TIME)
    time_penalty = max(0, (row['time_pct'] - 50) / 100)
    return (row['is_pf'] * 0.4 + row['oos_pf'] * 0.6
            - row['is_dd'] * 0.03
            - time_penalty * 0.5)


def main():
    print("=" * 62)
    print("  AGM_Ranger v6 — Re-optimizacion (salidas reales)")
    print("  IS: 2015-2021 | OOS: 2022-2026")
    print("=" * 62)

    df_raw = pd.read_csv(CACHE_M30, index_col=0, parse_dates=True)
    df_is  = df_raw[df_raw.index <= IS_END].copy()
    df_oos = df_raw[df_raw.index >= OOS_START].copy()
    print(f"  IS: {len(df_is):,} barras | OOS: {len(df_oos):,} barras")

    keys   = list(GRID.keys())
    values = list(GRID.values())
    combos = [dict(zip(keys, v)) for v in itertools.product(*values)]
    total  = len(combos)
    print(f"\n  Grid: {total} combinaciones")

    t0   = time.time()
    args = [(c, df_is, df_oos) for c in combos]
    ctx  = mp.get_context('spawn')
    with ctx.Pool(processes=min(11, mp.cpu_count())) as pool:
        results = pool.map(_worker, args, chunksize=4)

    results = [r for r in results if r is not None]
    elapsed = time.time() - t0
    print(f"  Completado: {len(results)}/{total} validos en {elapsed:.0f}s")

    if not results:
        print("  Sin resultados."); return

    df_res = pd.DataFrame(results)
    df_res['score'] = df_res.apply(_score, axis=1)
    df_res = df_res.sort_values('score', ascending=False).reset_index(drop=True)

    out = os.path.join(os.path.dirname(__file__), "..", "reports",
                       "AGM_Ranger_v6_Opt2_Results.csv")
    df_res.to_csv(out, index=False)

    # Mostrar top con IS_PF > 1.0 y TIME < 80%
    df_ok = df_res[(df_res['is_pf'] > 1.0) & (df_res['time_pct'] < 80)].head(15)
    print(f"\n  TOP combos (IS_PF>1.0, TIME<80%):")
    print("=" * 62)
    cols = ['ADX_H4_Threshold','ADX_Threshold','RSI_Oversold','MinSLPips',
            'TrailDistPips','TrailActivate','ExitBars','BB_Mid_TP',
            'is_n','is_pf','oos_pf','is_ann','is_dd','time_pct','wf_ratio','score']
    print(df_ok[cols].to_string(index=True))

    if len(df_ok) > 0:
        best = df_ok.iloc[0]
        print(f"\n  MEJOR COMBO:")
        for k in ['ADX_H4_Threshold','ADX_Threshold','RSI_Oversold','MinSLPips',
                  'TrailDistPips','TrailActivate','ExitBars','BB_Mid_TP']:
            print(f"    {k} = {best[k]}")
        print(f"  IS  -> PF:{best['is_pf']}  WR:{best['is_wr']}%  DD:{best['is_dd']}%  "
              f"N:{best['is_n']}  Ann:{best['is_ann']}%")
        print(f"  OOS -> PF:{best['oos_pf']}  WR:{best['oos_wr']}%  DD:{best['oos_dd']}%  N:{best['oos_n']}")
        print(f"  TIME exits: {best['time_pct']}%  |  WF: {best['wf_ratio']}  |  Score: {best['score']:.3f}")
    print(f"\n  Resultados -> {out}")


if __name__ == "__main__":
    mp.freeze_support()
    main()
