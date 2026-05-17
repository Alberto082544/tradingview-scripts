"""
MA Cross — Optimizacion IS/OOS para un par dado
Uso: python -m backtest.run_ma_cross_opt GBPUSD
     python -m backtest.run_ma_cross_opt EURUSD
"""
import os, sys, itertools, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pandas as pd
import multiprocessing as mp
from strategies.ma_cross_m15 import add_indicators, run_backtest, compute_metrics, PAIR_CONFIG

PAIR      = sys.argv[1].upper() if len(sys.argv) > 1 else "GBPUSD"
DATA      = os.path.join(os.path.dirname(__file__), "..", "data")
CAP       = 50_000.0
IS_END    = "2021-12-31"
OOS_START = "2022-01-01"

FILES = {
    'GBPUSD': 'GBPUSD_M15_histdata.csv',
    'EURUSD': 'EURUSD_M15_histdata.csv',
    'GBPJPY': 'GBPJPY_M15_dukas.csv',
    'AUDNZD': 'AUDNZD_M15_histdata.csv',
    'AUDCAD': 'AUDCAD_M15_histdata.csv',
    'EURGBP': 'EURGBP_M15_histdata.csv',
    # Indices (descargados Dukascopy via Dukascopy-DL)
    'SP500':  'SP500_M15.csv',
    'NAS100': 'NAS100_M15.csv',
    'DAX40':  'DAX40_M15.csv',
    'UK100':  'UK100_M15.csv',
}

# Indicadores fijos (calculados 1 vez)
FIXED_IND = {}

GRID = {
    'EMA_Fast':     [5, 8, 13, 21],
    'SMA_Slow':     [21, 34, 50, 89],
    'SL_ATR_Mult':  [1.0, 1.5, 2.0],
    'RR':           [1.5, 2.0, 2.5, 3.0],
    'Trail_Dist':   [0.5, 1.0, 1.5],
    'BE_Trigger':   [0.0, 0.5, 1.0],
}

FIXED_BT = {
    'ATR_Period': 14,
    'BE_Offset':  0.0002,
    'Trail_Start': 1.5,
    'MaxSpreadPips': 3.0,
    'LotRiskPct': 0.5,
    'MaxLots': 4.0,
}

_df_is_raw  = None
_df_oos_raw = None
_pip        = None
_pip_val    = None

def _pool_init(df_is, df_oos, pip, pip_val):
    global _df_is_raw, _df_oos_raw, _pip, _pip_val
    _df_is_raw  = df_is
    _df_oos_raw = df_oos
    _pip = pip; _pip_val = pip_val

def _worker(combo):
    p = {**FIXED_BT, **combo}
    p['Dir_EMA_Fast'] = combo['EMA_Fast']
    p['Dir_SMA_Slow'] = combo['SMA_Slow']
    try:
        df_is  = add_indicators(_df_is_raw,  p)
        df_oos = add_indicators(_df_oos_raw, p)
        t_is  = run_backtest(df_is,  p, CAP, _pip, _pip_val)
        t_oos = run_backtest(df_oos, p, CAP, _pip, _pip_val)
        m_is  = compute_metrics(t_is,  CAP)
        m_oos = compute_metrics(t_oos, CAP)
    except Exception:
        return None
    if m_is['n'] < 30 or m_is['pf'] <= 0:
        return None
    exits_is = t_is['exit_type'].value_counts(normalize=True).to_dict() if len(t_is) > 0 else {}
    return {**combo,
            'is_n':m_is['n'],'is_pf':m_is['pf'],'is_wr':m_is['wr'],
            'is_dd':m_is['dd_pct'],'is_ann':m_is['ann_pct'],'is_pnl':m_is['pnl'],
            'oos_n':m_oos['n'],'oos_pf':m_oos['pf'],'oos_wr':m_oos['wr'],
            'oos_dd':m_oos['dd_pct'],'oos_ann':m_oos['ann_pct'],'oos_pnl':m_oos['pnl'],
            'tp_pct': round(exits_is.get('TP',0)*100,1),
            'sl_pct': round(exits_is.get('SL',0)*100,1),
            'wf_ratio':round(m_oos['pf']/m_is['pf'],3) if m_is['pf']>0 else 0}

def main():
    cfg = PAIR_CONFIG.get(PAIR)
    if not cfg:
        print(f"Par {PAIR} no reconocido"); return
    pip     = cfg['pip']
    pip_val = cfg['pip_val']

    fname = FILES.get(PAIR)
    if not fname:
        print(f"Sin archivo para {PAIR}"); return
    path = os.path.join(DATA, fname)
    if not os.path.exists(path):
        print(f"Archivo no encontrado: {path}"); return

    print("=" * 60)
    print(f"  MA Cross — Optimizacion {PAIR} M15")
    print(f"  IS: 2014-2021 | OOS: 2022-2025 | Capital: $50,000")
    print("=" * 60)

    df_raw = pd.read_csv(path, index_col=0, parse_dates=True)

    df_is_raw  = df_raw[df_raw.index <= IS_END].copy()
    df_oos_raw = df_raw[df_raw.index >= OOS_START].copy()
    print(f"  IS: {len(df_is_raw):,} barras | OOS: {len(df_oos_raw):,} barras")

    # Benchmark (incluye add_indicators por combo)
    t0_bm = time.time()
    bm_p = {**FIXED_BT,'EMA_Fast':8,'SMA_Slow':21,'Dir_EMA_Fast':8,
            'Dir_SMA_Slow':21,'SL_ATR_Mult':1.5,'RR':2.0,'Trail_Dist':1.0,'BE_Trigger':1.0}
    df_bm = add_indicators(df_is_raw, bm_p)
    run_backtest(df_bm, bm_p, CAP, pip, pip_val)
    bm = time.time() - t0_bm

    keys   = list(GRID.keys())
    combos = [dict(zip(keys,v)) for v in itertools.product(*GRID.values())]
    # Filtrar combos donde SMA_Slow > EMA_Fast
    combos = [c for c in combos if c['SMA_Slow'] > c['EMA_Fast']]
    n_proc = min(11, mp.cpu_count())
    est    = bm * len(combos) / n_proc
    print(f"  Grid: {len(combos)} combos | 1 BT={bm:.2f}s | Est: {est:.0f}s ({est/60:.1f} min)")

    t0  = time.time()
    ctx = mp.get_context('spawn')
    with ctx.Pool(processes=n_proc,
                  initializer=_pool_init,
                  initargs=(df_is_raw, df_oos_raw, pip, pip_val)) as pool:
        results = pool.map(_worker, combos, chunksize=16)
    results = [r for r in results if r is not None]
    print(f"  Completado: {len(results)}/{len(combos)} validos en {time.time()-t0:.0f}s")
    if not results: return

    df_res = pd.DataFrame(results)
    df_res['score'] = df_res['is_pf']*0.4 + df_res['oos_pf']*0.6 - df_res['is_dd']*0.02
    df_res = df_res.sort_values('score', ascending=False)

    out = os.path.join(os.path.dirname(__file__), "..", "reports", f"MA_Cross_{PAIR}_Opt_Results.csv")
    df_res.to_csv(out, index=False)

    df_ok = df_res[(df_res['is_pf'] > 1.0) & (df_res['oos_pf'] > 1.0)].head(15)
    cols  = ['EMA_Fast','SMA_Slow','SL_ATR_Mult','RR','Trail_Dist','BE_Trigger',
             'is_n','is_pf','oos_pf','is_ann','is_dd','oos_dd','tp_pct','sl_pct','wf_ratio','score']
    print(f"\n  TOP 15 (IS_PF>1.0 Y OOS_PF>1.0):")
    if len(df_ok):
        print(df_ok[cols].to_string(index=False))
        b = df_ok.iloc[0]
        print(f"\n  MEJOR: EMA{int(b['EMA_Fast'])}/SMA{int(b['SMA_Slow'])} SL={b['SL_ATR_Mult']}xATR RR={b['RR']} Trail={b['Trail_Dist']}xATR BE={b['BE_Trigger']}xATR")
        print(f"  IS  PF:{b['is_pf']} WR:{b['is_wr']}% DD:{b['is_dd']}% Ann:{b['is_ann']}%  N:{int(b['is_n'])}")
        print(f"  OOS PF:{b['oos_pf']} WR:{b['oos_wr']}% DD:{b['oos_dd']}% Ann:{b['oos_ann']}%  N:{int(b['oos_n'])}")
        pnl_yr  = b['oos_pnl'] / 4
        print(f"  OOS PnL: ${b['oos_pnl']:,.0f} total | ${pnl_yr:,.0f}/anio | ${pnl_yr/12:,.0f}/mes  (sobre $50k)")
    else:
        print("  Sin combos con IS_PF>1 y OOS_PF>1")
    print(f"  -> {out}")

if __name__ == "__main__":
    mp.freeze_support()
    main()
