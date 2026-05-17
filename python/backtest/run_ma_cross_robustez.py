"""
MA Cross — Robustez Year-by-Year para un par dado
Uso: python -m backtest.run_ma_cross_robustez EURUSD
     python -m backtest.run_ma_cross_robustez GBPUSD
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pandas as pd
import numpy as np
from strategies.ma_cross_m15 import add_indicators, run_backtest, compute_metrics, PAIR_CONFIG

PAIR = sys.argv[1].upper() if len(sys.argv) > 1 else "EURUSD"
CAP  = 50_000.0

FILES = {
    'GBPUSD': 'GBPUSD_M15_histdata.csv',
    'EURUSD': 'EURUSD_M15_histdata.csv',
    'GBPJPY': 'GBPJPY_M15_dukas.csv',
}

BEST = {
    'EURUSD': {
        'EMA_Fast':5,'SMA_Slow':21,'Dir_EMA_Fast':5,'Dir_SMA_Slow':21,
        'ATR_Period':14,'SL_ATR_Mult':2.0,'RR':3.0,'BE_Trigger':0.5,
        'BE_Offset':0.0002,'Trail_Start':1.5,'Trail_Dist':0.5,
        'MaxSpreadPips':3.0,'LotRiskPct':0.5,'MaxLots':4.0,
    },
    'GBPUSD': {
        'EMA_Fast':5,'SMA_Slow':34,'Dir_EMA_Fast':5,'Dir_SMA_Slow':34,
        'ATR_Period':14,'SL_ATR_Mult':1.0,'RR':3.0,'BE_Trigger':0.5,
        'BE_Offset':0.0002,'Trail_Start':1.5,'Trail_Dist':0.5,
        'MaxSpreadPips':3.0,'LotRiskPct':0.5,'MaxLots':4.0,
    },
}

def main():
    params = BEST.get(PAIR)
    if not params:
        print(f"Sin params para {PAIR}"); return

    cfg  = PAIR_CONFIG[PAIR]
    pip  = cfg['pip']
    pv   = cfg['pip_val']
    fname = FILES.get(PAIR)
    path  = os.path.join(os.path.dirname(__file__), "..", "data", fname)

    print("=" * 64)
    print(f"  MA Cross {PAIR} — Robustez Year-by-Year")
    par_str = f"EMA{params['EMA_Fast']}/SMA{params['SMA_Slow']} SL={params['SL_ATR_Mult']}xATR RR={params['RR']} Trail={params['Trail_Dist']}xATR"
    print(f"  {par_str}")
    print("=" * 64)

    df_raw = pd.read_csv(path, index_col=0, parse_dates=True)
    print(f"  Calculando indicadores sobre {len(df_raw):,} barras...")
    df_all = add_indicators(df_raw, params)

    years = sorted(df_all.index.year.unique())
    rows  = []
    for yr in years:
        df_yr = df_all[df_all.index.year == yr]
        if len(df_yr) < 2000:
            continue
        t = run_backtest(df_yr, params, CAP, pip, pv)
        m = compute_metrics(t, CAP)
        if m['n'] == 0:
            rows.append({'year':yr,'n':0,'pf':0,'wr':0,'dd':0,'ann':0,'calmar':0,'pnl':0,'exits':'-'})
            continue
        exits = t['exit_type'].value_counts(normalize=True).mul(100).round(1).to_dict()
        exit_str = ' '.join(f"{k}:{v:.0f}%" for k, v in sorted(exits.items()))
        rows.append({'year':yr,'n':m['n'],'pf':m['pf'],'wr':m['wr'],
                     'dd':m['dd_pct'],'ann':m['ann_pct'],'calmar':m['calmar'],
                     'pnl':m['pnl'],'exits':exit_str})

    df_r = pd.DataFrame(rows)

    # Full period
    t_full = run_backtest(df_all, params, CAP, pip, pv)
    m_full = compute_metrics(t_full, CAP)
    exits_full = t_full['exit_type'].value_counts(normalize=True).mul(100).round(1).to_dict()
    exit_full_str = ' '.join(f"{k}:{v:.0f}%" for k, v in sorted(exits_full.items()))

    print(f"\n{'Year':>5} {'N':>5} {'PF':>5} {'WR%':>6} {'DD%':>6} {'Ann%':>7} {'Calmar':>7} {'PnL USD':>9}  Exits")
    print("-" * 80)
    for _, r in df_r.iterrows():
        marker = " <-- ROJO" if (r['pf'] < 1.0 and r['n'] > 10) else ""
        print(f"{int(r['year']):>5} {int(r['n']):>5} {r['pf']:>5.2f} {r['wr']:>6.1f} "
              f"{r['dd']:>6.1f} {r['ann']:>7.2f} {r['calmar']:>7.2f} {r['pnl']:>9.0f}  {r['exits']}{marker}")
    print("-" * 80)
    print(f"{'FULL':>5} {m_full['n']:>5} {m_full['pf']:>5.2f} {m_full['wr']:>6.1f} "
          f"{m_full['dd_pct']:>6.1f} {m_full['ann_pct']:>7.2f} {m_full['calmar']:>7.2f} "
          f"{m_full['pnl']:>9.0f}  {exit_full_str}")

    # Long vs Short
    print("\n  Long vs Short:")
    for lbl, filt in [('Long','long'),('Short','short')]:
        tt = t_full[t_full['direction']==filt]
        if len(tt) == 0: continue
        mm = compute_metrics(tt, CAP)
        print(f"    {lbl:5s}: N={mm['n']:4d} WR={mm['wr']:5.1f}% PF={mm['pf']:.2f} Ann={mm['ann_pct']:.2f}%")

    neg = df_r[(df_r['pf'] < 1.0) & (df_r['n'] > 10)]
    if len(neg) == 0:
        print(f"\n  Ningun año con PF<1 (N>10) — ROBUSTO")
    else:
        print(f"\n  Años negativos: {list(neg['year'].astype(int))}")
    worst = df_r[df_r['n'] > 10].sort_values('pf').iloc[0]
    print(f"  Peor año: {int(worst['year'])} PF={worst['pf']:.2f} DD={worst['dd']:.1f}% Ann={worst['ann']:.2f}%")

    pnl_yr = m_full['pnl'] / 12
    pnl_mes = pnl_yr / 12
    print(f"\n  PnL total: ${m_full['pnl']:,.0f} | ${pnl_yr:,.0f}/anio | ${pnl_mes:,.0f}/mes  (sobre $50k)")

if __name__ == "__main__":
    main()
