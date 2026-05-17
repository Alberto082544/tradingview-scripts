"""
Ranger C AUDNZD — Optimizacion: Mean Reversion H4+M15
Familia: Ranger C | Par: AUDNZD

IS: 2014-2021 | OOS: 2022-2025
Uso: python -m backtest.run_ranger_c_audnzd_opt
"""
import os, sys, itertools, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pandas as pd
import multiprocessing as mp
from strategies.ranger_c_audnzd_m15 import add_indicators, run_backtest, compute_metrics

CACHE   = os.path.join(os.path.dirname(__file__), "..", "data", "AUDNZD_M15_histdata.csv")
CAP     = 50_000.0
IS_END  = "2021-12-31"
OOS_START = "2022-01-01"

FIXED_IND = {
    'BB_Period':20, 'BB_StdDev':2.0, 'RSI_Period':14,
    'ADX_H4_Period':14, 'ATR_Period':14,
}
GRID = {
    'ADX_H4_Max':    [20, 25, 30, 35],
    'RSI_Long_Max':  [40, 45, 50],
    'RSI_Short_Min': [50, 55, 60],
    'RSI_Confirm':   [0, 1],
    'BB_Mid_TP':     [0, 1],
    'MinSLPips':     [8, 12, 20],
    'TrailDistPips': [8, 12, 20],
    'ExitBars':      [8, 16, 24, 32],
}
FIXED_BT = {
    'SL_ATR_Mult':1.5, 'MaxSLPips':999, 'TP_ATR_Mult':0,
    'TrailActivate':0.5, 'SessionStart':0, 'SessionEnd':23,
    'BadHour':-1, 'MaxTradesDay':5, 'LotRiskPct':0.7, 'MaxLots':4.0,
}

_df_is  = None
_df_oos = None

def _pool_init(df_is, df_oos):
    global _df_is, _df_oos
    _df_is  = df_is
    _df_oos = df_oos

def _worker(combo):
    p = {**FIXED_IND, **FIXED_BT, **combo}
    try:
        t_is  = run_backtest(_df_is,  p, CAP)
        t_oos = run_backtest(_df_oos, p, CAP)
        m_is  = compute_metrics(t_is,  CAP)
        m_oos = compute_metrics(t_oos, CAP)
    except Exception:
        return None
    if m_is['n'] < 50 or m_is['pf'] <= 0:
        return None
    exits = t_is['exit_type'].value_counts(normalize=True).to_dict() if len(t_is) > 0 else {}
    return {**combo,
            'is_n':m_is['n'],'is_pf':m_is['pf'],'is_wr':m_is['wr'],
            'is_dd':m_is['dd_pct'],'is_ann':m_is['ann_pct'],'is_pnl':m_is['pnl'],
            'oos_n':m_oos['n'],'oos_pf':m_oos['pf'],'oos_wr':m_oos['wr'],
            'oos_dd':m_oos['dd_pct'],'oos_ann':m_oos['ann_pct'],'oos_pnl':m_oos['pnl'],
            'time_pct':round(exits.get('TIME',0)*100,1),
            'wf_ratio':round(m_oos['pf']/m_is['pf'],3) if m_is['pf']>0 else 0}

def main():
    print("="*58)
    print("  Ranger C AUDNZD — Mean Reversion H4+M15")
    print("  Familia: Ranger C | Par: AUDNZD")
    print("  IS: 2014-2021 | OOS: 2022-2025")
    print("="*58)
    df_raw = pd.read_csv(CACHE, index_col=0, parse_dates=True)
    df_is  = df_raw[df_raw.index <= IS_END].copy()
    df_oos = df_raw[df_raw.index >= OOS_START].copy()

    print("  Calculando indicadores (1 vez)...")
    df_is  = add_indicators(df_is,  FIXED_IND)
    df_oos = add_indicators(df_oos, FIXED_IND)
    print(f"  IS: {len(df_is):,} barras | OOS: {len(df_oos):,} barras")

    keys   = list(GRID.keys())
    combos = [dict(zip(keys,v)) for v in itertools.product(*GRID.values())]
    print(f"  Grid: {len(combos)} combos")
    t0  = time.time()
    ctx = mp.get_context('spawn')
    with ctx.Pool(processes=min(11, mp.cpu_count()),
                  initializer=_pool_init, initargs=(df_is, df_oos)) as pool:
        results = pool.map(_worker, combos, chunksize=16)
    results = [r for r in results if r is not None]
    print(f"  Completado: {len(results)}/{len(combos)} validos en {time.time()-t0:.0f}s")
    if not results: return
    df_res = pd.DataFrame(results)
    df_res['score'] = df_res['is_pf']*0.4 + df_res['oos_pf']*0.6 - df_res['is_dd']*0.02
    df_res = df_res.sort_values('score', ascending=False)
    out = os.path.join(os.path.dirname(__file__), "..", "reports", "Ranger_C_AUDNZD_Opt_Results.csv")
    df_res.to_csv(out, index=False)
    df_ok = df_res[(df_res['is_pf'] > 1.0) & (df_res['oos_pf'] > 1.0)].head(15)
    cols  = ['ADX_H4_Max','RSI_Long_Max','RSI_Short_Min','RSI_Confirm','BB_Mid_TP',
             'MinSLPips','TrailDistPips','ExitBars','is_n','is_pf','oos_pf',
             'is_ann','is_dd','oos_dd','time_pct','wf_ratio','score']
    print(f"\n  TOP 15 (IS_PF>1.0 Y OOS_PF>1.0):")
    print(df_ok[cols].to_string(index=False))
    if len(df_ok):
        b = df_ok.iloc[0]
        print(f"\n  MEJOR: ADX<{b['ADX_H4_Max']} RSI_L<{b['RSI_Long_Max']} RSI_S>{b['RSI_Short_Min']} BB_Mid={b['BB_Mid_TP']} MinSL={b['MinSLPips']} Trail={b['TrailDistPips']} Exit={b['ExitBars']}")
        print(f"  IS  PF:{b['is_pf']} WR:{b['is_wr']}% DD:{b['is_dd']}% Ann:{b['is_ann']}% N:{b['is_n']}")
        print(f"  OOS PF:{b['oos_pf']} WR:{b['oos_wr']}% DD:{b['oos_dd']}% Ann:{b['oos_ann']}% N:{b['oos_n']}")
    print(f"  -> {out}")

if __name__ == "__main__":
    mp.freeze_support()
    main()
