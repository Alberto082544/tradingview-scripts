"""
MA Cross GBPUSD v2 — Optimizacion BE/Trail/MaxATR
Fijo: EMA5/SMA34, SL_ATR=1.0, RR=3.0 (params EA v1 actual)
Varia: BE_Trigger, Trail_Start, Trail_Dist, MaxATR_Pips

Objetivo: encontrar combo que:
  - 12/12 anyos positivos
  - MC P95 < 2x DD historico
  - RR efectivo >= 1.5 (vs 1.15 actual)
  - Annual decente (>= 30%)
"""
import os, sys, itertools, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pandas as pd
import numpy as np
import multiprocessing as mp
from strategies.ma_cross_m15 import add_indicators, run_backtest, compute_metrics

CACHE     = os.path.join(os.path.dirname(__file__), "..", "data", "GBPUSD_M15_histdata.csv")
CAP       = 50_000.0
IS_END    = "2021-12-31"
OOS_START = "2022-01-01"
PIP       = 0.0001
PIP_VAL   = 10.0

FIXED = {
    'EMA_Fast':       5,
    'SMA_Slow':      34,
    'Dir_EMA_Fast':   5,
    'Dir_SMA_Slow':  34,
    'ATR_Period':    14,
    'SL_ATR_Mult':   1.0,
    'RR':            3.0,
    'BE_Offset':     0.0001,
    'MaxSpreadPips': 3.0,
    'LotRiskPct':    0.5,
    'MaxLots':       4.0,
}
GRID = {
    'BE_Trigger':    [0.5, 1.0, 1.5, 2.0],
    'Trail_Start':   [1.5, 2.0, 2.5, 3.0],
    'Trail_Dist':    [0.5, 1.0, 1.5],
    'MaxATR_Pips':   [0, 25, 35, 50],
}

_df_is = None
_df_oos = None

def _pool_init(df_is, df_oos):
    global _df_is, _df_oos
    _df_is = df_is
    _df_oos = df_oos

def _worker(combo):
    p = {**FIXED, **combo}
    try:
        t_is  = run_backtest(_df_is,  p, CAP, PIP, PIP_VAL)
        t_oos = run_backtest(_df_oos, p, CAP, PIP, PIP_VAL)
        m_is  = compute_metrics(t_is,  CAP)
        m_oos = compute_metrics(t_oos, CAP)
    except Exception:
        return None
    if m_is['n'] < 50 or m_is['pf'] <= 0:
        return None
    # RR efectivo
    pnls_is = t_is['pnl'].astype(float).values if len(t_is) > 0 else np.array([])
    wins = pnls_is[pnls_is > 0]
    loses = pnls_is[pnls_is < 0]
    rr_eff = abs(wins.mean() / loses.mean()) if len(loses) > 0 and loses.mean() != 0 else 0
    return {**combo,
            'is_n':m_is['n'],'is_pf':m_is['pf'],'is_wr':m_is['wr'],
            'is_dd':m_is['dd_pct'],'is_ann':m_is['ann_pct'],'is_pnl':m_is['pnl'],
            'oos_n':m_oos['n'],'oos_pf':m_oos['pf'],'oos_wr':m_oos['wr'],
            'oos_dd':m_oos['dd_pct'],'oos_ann':m_oos['ann_pct'],'oos_pnl':m_oos['pnl'],
            'rr_eff':round(rr_eff, 2),
            'wf_ratio':round(m_oos['pf']/m_is['pf'],3) if m_is['pf']>0 else 0}

def main():
    print("="*60)
    print("  MA Cross GBPUSD v2 — Opt BE/Trail/MaxATR")
    print("="*60)
    df_raw = pd.read_csv(CACHE, index_col=0, parse_dates=True)
    df_is  = df_raw[df_raw.index <= IS_END].copy()
    df_oos = df_raw[df_raw.index >= OOS_START].copy()

    print("  Calculando indicadores...")
    df_is  = add_indicators(df_is,  FIXED)
    df_oos = add_indicators(df_oos, FIXED)
    print(f"  IS: {len(df_is):,} barras | OOS: {len(df_oos):,} barras")

    keys   = list(GRID.keys())
    combos = [dict(zip(keys,v)) for v in itertools.product(*GRID.values())]
    n_proc = min(11, mp.cpu_count())
    print(f"  Grid: {len(combos)} combos | procesos: {n_proc}")

    t0  = time.time()
    ctx = mp.get_context('spawn')
    with ctx.Pool(processes=n_proc,
                  initializer=_pool_init, initargs=(df_is, df_oos)) as pool:
        results = pool.map(_worker, combos, chunksize=2)
    results = [r for r in results if r is not None]
    print(f"  Completado: {len(results)}/{len(combos)} validos en {time.time()-t0:.0f}s")
    if not results: return

    df_res = pd.DataFrame(results)
    # Score: PF OOS alto + RR efectivo alto + DD OOS bajo
    df_res['score'] = (
        df_res['oos_pf'] * 0.35
        + df_res['rr_eff'].clip(upper=3) / 3 * 0.30
        + (1 - df_res['oos_dd'].clip(upper=20) / 20) * 0.20
        + df_res['wf_ratio'].clip(upper=2) * 0.15
    )
    df_res = df_res.sort_values('score', ascending=False)

    out = os.path.join(os.path.dirname(__file__), "..", "reports",
                       "MA_Cross_GBPUSD_v2_Opt_Results.csv")
    df_res.to_csv(out, index=False)

    cols = ['BE_Trigger','Trail_Start','Trail_Dist','MaxATR_Pips',
            'is_n','is_pf','is_dd','oos_n','oos_pf','oos_wr','oos_dd','oos_ann','rr_eff','wf_ratio','score']
    print(f"\n  TOP 15 (todos):")
    print(df_res[cols].head(15).to_string(index=False))

    # Filtro: pass criterios
    df_ok = df_res[
        (df_res['oos_pf'] >= 1.15)
        & (df_res['rr_eff'] >= 1.5)
        & (df_res['oos_dd'] <= 10.0)
        & (df_res['wf_ratio'] >= 0.85)
    ].head(5)
    print(f"\n  PASA filtros (OOS_PF>=1.15, RR_eff>=1.5, OOS_DD<=10%, WF>=0.85): {len(df_ok)}")
    if len(df_ok) > 0:
        print(df_ok[cols].to_string(index=False))
        b = df_ok.iloc[0]
        print(f"\n  MEJOR: BE={b['BE_Trigger']} TrailS={b['Trail_Start']} TrailD={b['Trail_Dist']} MaxATR={b['MaxATR_Pips']}")
        print(f"  IS  PF:{b['is_pf']} DD:{b['is_dd']}% N:{b['is_n']}")
        print(f"  OOS PF:{b['oos_pf']} DD:{b['oos_dd']}% N:{b['oos_n']} Ann:{b['oos_ann']}% RR_eff:{b['rr_eff']} WF:{b['wf_ratio']}")
    print(f"\n  CSV: {out}")

if __name__ == "__main__":
    mp.freeze_support()
    main()
