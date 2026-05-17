"""
Ranger C AUDCAD — Analisis de Robustez Year-by-Year
Usa el mejor combo del la optimizacion IS/OOS.
Uso: python -m backtest.run_ranger_c_audcad_robustez
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pandas as pd
from strategies.ranger_c_audcad_m15 import add_indicators, run_backtest, compute_metrics

CACHE = os.path.join(os.path.dirname(__file__), "..", "data", "AUDCAD_M15_histdata.csv")
CAP   = 50_000.0

# Mejor combo de la optimizacion
BEST = {
    'BB_Period': 20, 'BB_StdDev': 2.0, 'RSI_Period': 14,
    'ADX_H4_Period': 14, 'ATR_Period': 14,
    'ADX_H4_Max':    35,
    'RSI_Long_Max':  40,
    'RSI_Short_Min': 60,
    'RSI_Confirm':    1,
    'BB_Mid_TP':      0,
    'MinSLPips':     20,
    'TrailDistPips': 12,
    'ExitBars':      24,
    'SL_ATR_Mult':  1.5, 'MaxSLPips': 999, 'TP_ATR_Mult': 0,
    'TrailActivate': 0.5, 'SessionStart': 0, 'SessionEnd': 23,
    'BadHour': -1, 'MaxTradesDay': 5, 'LotRiskPct': 0.7, 'MaxLots': 4.0,
}

def main():
    print("=" * 62)
    print("  Ranger C AUDCAD — Robustez Year-by-Year")
    print("  ADX<35 RSI_L<40 RSI_S>60 MinSL=20 Trail=12 Exit=24")
    print("=" * 62)

    df_raw = pd.read_csv(CACHE, index_col=0, parse_dates=True)
    print(f"  Calculando indicadores sobre {len(df_raw):,} barras...")
    df_all = add_indicators(df_raw, BEST)

    years = sorted(df_all.index.year.unique())
    rows  = []
    for yr in years:
        df_yr = df_all[df_all.index.year == yr]
        if len(df_yr) < 2000:
            continue
        t  = run_backtest(df_yr, BEST, CAP)
        m  = compute_metrics(t, CAP)
        if m['n'] == 0:
            rows.append({'year': yr, 'n': 0, 'pf': 0, 'wr': 0,
                         'dd': 0, 'ann': 0, 'calmar': 0,
                         'pnl': 0, 'exits': '-'})
            continue
        exits = t['exit_type'].value_counts(normalize=True).mul(100).round(1).to_dict()
        exit_str = ' '.join(f"{k}:{v:.0f}%" for k, v in sorted(exits.items()))
        rows.append({
            'year':   yr,
            'n':      m['n'],
            'pf':     m['pf'],
            'wr':     m['wr'],
            'dd':     m['dd_pct'],
            'ann':    m['ann_pct'],
            'calmar': m['calmar'],
            'pnl':    m['pnl'],
            'exits':  exit_str,
        })

    df_r = pd.DataFrame(rows)

    t_full = run_backtest(df_all, BEST, CAP)
    m_full = compute_metrics(t_full, CAP)
    exits_full = t_full['exit_type'].value_counts(normalize=True).mul(100).round(1).to_dict()
    exit_full_str = ' '.join(f"{k}:{v:.0f}%" for k, v in sorted(exits_full.items()))

    print(f"\n{'Year':>5} {'N':>5} {'PF':>5} {'WR%':>6} {'DD%':>6} {'Ann%':>7} {'Calmar':>7} {'PnL USD':>9}  Exits")
    print("-" * 85)
    for _, r in df_r.iterrows():
        marker = " <-- ROJO" if (r['pf'] < 1.0 and r['n'] > 10) else ""
        print(f"{int(r['year']):>5} {int(r['n']):>5} {r['pf']:>5.2f} {r['wr']:>6.1f} "
              f"{r['dd']:>6.1f} {r['ann']:>7.2f} {r['calmar']:>7.2f} {r['pnl']:>9.0f}  {r['exits']}{marker}")
    print("-" * 85)
    print(f"{'FULL':>5} {m_full['n']:>5} {m_full['pf']:>5.2f} {m_full['wr']:>6.1f} "
          f"{m_full['dd_pct']:>6.1f} {m_full['ann_pct']:>7.2f} {m_full['calmar']:>7.2f} "
          f"{m_full['pnl']:>9.0f}  {exit_full_str}")

    print("\n  Long vs Short breakdown:")
    t_l = t_full[t_full['direction'] == 'long']
    t_s = t_full[t_full['direction'] == 'short']
    for lbl, tt in [('Long', t_l), ('Short', t_s)]:
        if len(tt) == 0:
            continue
        mm = compute_metrics(tt, CAP)
        print(f"    {lbl:5s}: N={mm['n']:4d} WR={mm['wr']:5.1f}% PF={mm['pf']:.2f} "
              f"Ann={mm['ann_pct']:.2f}% DD={mm['dd_pct']:.1f}%")

    neg = df_r[(df_r['pf'] < 1.0) & (df_r['n'] > 10)]
    if len(neg) == 0:
        print("\n  Ningun ano con PF < 1 (N>10) — ROBUSTO")
    else:
        print(f"\n  Anos negativos: {list(neg['year'].astype(int))}")

    worst = df_r[df_r['n'] > 10].sort_values('pf').iloc[0]
    print(f"  Peor ano: {int(worst['year'])} PF={worst['pf']:.2f} DD={worst['dd']:.1f}% Ann={worst['ann']:.2f}%")

if __name__ == "__main__":
    main()
