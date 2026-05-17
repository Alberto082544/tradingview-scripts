"""
Ranger A — Optimizacion: Tendencia H4 + Pullback M30
IS: 2015-2021 | OOS: 2022-2026
Uso: python -m backtest.run_ranger_a_opt
"""
import os, sys, itertools, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pandas as pd
import multiprocessing as mp
from strategies.ranger_a_trend_m30 import add_indicators, run_backtest, compute_metrics

CACHE_M30 = os.path.join(os.path.dirname(__file__), "..", "data", "GBPJPY_M30_dukas.csv")
CAP = 50_000.0
IS_END = "2021-12-31"
OOS_START = "2022-01-01"

GRID = {
    'ADX_H4_Min':    [15, 20, 25],
    'RSI_Long_Max':  [40, 45, 50],
    'EMA_Fast':      [20, 50, 100],
    'TP_Mult':       [2.0, 2.5, 3.0],
    'BE_Mult':       [0.6, 0.8, 1.0],
    'MinSLPips':     [20, 30, 50],
    'ExitBars':      [8, 16, 24],
}

FIXED = {
    'EMA_Slow':200,'RSI_Period':14,'RSI_Short_Min':50,'ADX_H4_Period':14,
    'EMA_H4':200,'ATR_Period':14,'SL_ATR_Mult':1.5,'MaxSLPips':999,
    'TrailActivate':1.5,'TrailDistPips':40,'SessionStart':7,'SessionEnd':19,
    'BadHour':8,'MaxTradesDay':3,'LotRiskPct':0.7,'MaxLots':4.0,
}

def _worker(args):
    combo, df_is, df_oos = args
    p = {**FIXED, **combo}
    p['RSI_Short_Min'] = 100 - p['RSI_Long_Max']
    try:
        t_is  = run_backtest(add_indicators(df_is,  p), p, CAP)
        t_oos = run_backtest(add_indicators(df_oos, p), p, CAP)
        m_is  = compute_metrics(t_is,  CAP)
        m_oos = compute_metrics(t_oos, CAP)
    except Exception:
        return None
    if m_is['n'] < 30 or m_is['pf'] <= 0:
        return None
    return {**combo,
            'is_n':m_is['n'],'is_pf':m_is['pf'],'is_wr':m_is['wr'],
            'is_dd':m_is['dd_pct'],'is_ann':m_is['ann_pct'],'is_pnl':m_is['pnl'],
            'oos_n':m_oos['n'],'oos_pf':m_oos['pf'],'oos_wr':m_oos['wr'],
            'oos_dd':m_oos['dd_pct'],'oos_ann':m_oos['ann_pct'],'oos_pnl':m_oos['pnl'],
            'wf_ratio':round(m_oos['pf']/m_is['pf'],3) if m_is['pf']>0 else 0}

def main():
    print("="*55)
    print("  Ranger A — Tendencia H4 + Pullback M30")
    print("  IS: 2015-2021 | OOS: 2022-2026")
    print("="*55)
    df_raw = pd.read_csv(CACHE_M30, index_col=0, parse_dates=True)
    df_is  = df_raw[df_raw.index <= IS_END].copy()
    df_oos = df_raw[df_raw.index >= OOS_START].copy()
    keys   = list(GRID.keys())
    combos = [dict(zip(keys,v)) for v in itertools.product(*GRID.values())]
    print(f"  Grid: {len(combos)} combos")
    t0   = time.time()
    args = [(c, df_is, df_oos) for c in combos]
    ctx  = mp.get_context('spawn')
    with ctx.Pool(processes=min(11, mp.cpu_count())) as pool:
        results = pool.map(_worker, args, chunksize=4)
    results = [r for r in results if r is not None]
    print(f"  Completado: {len(results)}/{len(combos)} validos en {time.time()-t0:.0f}s")
    if not results: return
    df_res = pd.DataFrame(results)
    df_res['score'] = df_res['is_pf']*0.4 + df_res['oos_pf']*0.6 - df_res['is_dd']*0.02
    df_res = df_res.sort_values('score', ascending=False)
    out = os.path.join(os.path.dirname(__file__), "..", "reports", "Ranger_A_Opt_Results.csv")
    df_res.to_csv(out, index=False)
    df_ok = df_res[df_res['is_pf'] > 1.0].head(10)
    cols  = ['ADX_H4_Min','RSI_Long_Max','EMA_Fast','TP_Mult','BE_Mult','MinSLPips',
             'ExitBars','is_n','is_pf','oos_pf','is_ann','is_dd','wf_ratio','score']
    print(f"\n  TOP 10 (IS_PF>1.0):")
    print(df_ok[cols].to_string(index=False))
    if len(df_ok):
        b = df_ok.iloc[0]
        print(f"\n  MEJOR: ADX_H4>{b['ADX_H4_Min']} RSI<{b['RSI_Long_Max']} EMA={b['EMA_Fast']} TP={b['TP_Mult']}x BE={b['BE_Mult']}x MinSL={b['MinSLPips']} Exit={b['ExitBars']}")
        print(f"  IS  PF:{b['is_pf']} WR:{b['is_wr']}% DD:{b['is_dd']}% Ann:{b['is_ann']}% N:{b['is_n']}")
        print(f"  OOS PF:{b['oos_pf']} WR:{b['oos_wr']}% DD:{b['oos_dd']}% Ann:{b['oos_ann']}% N:{b['oos_n']}")
    print(f"  -> {out}")

if __name__ == "__main__":
    mp.freeze_support()
    main()
