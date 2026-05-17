"""
MA Cross — Test inicial en 6 pares: tendencia vs rango
Parametros por defecto del v1.10. IS/OOS para comparar.
Uso: python -m backtest.run_ma_cross_test
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pandas as pd
from strategies.ma_cross_m15 import add_indicators, run_backtest, compute_metrics, PAIR_CONFIG, DEFAULT_PARAMS

DATA  = os.path.join(os.path.dirname(__file__), "..", "data")
CAP   = 50_000.0
IS_END    = "2021-12-31"
OOS_START = "2022-01-01"

PAIRS = {
    'GBPJPY': 'GBPJPY_M15_dukas.csv',
    'GBPUSD': 'GBPUSD_M15_histdata.csv',
    'EURUSD': 'EURUSD_M15_histdata.csv',
    'AUDNZD': 'AUDNZD_M15_histdata.csv',
    'AUDCAD': 'AUDCAD_M15_histdata.csv',
    'EURGBP': 'EURGBP_M15_histdata.csv',
}
TIPO = {
    'GBPJPY': 'TENDENCIA',
    'GBPUSD': 'TENDENCIA',
    'EURUSD': 'TENDENCIA',
    'AUDNZD': 'RANGO',
    'AUDCAD': 'RANGO',
    'EURGBP': 'RANGO',
}

def main():
    print("=" * 72)
    print("  MA Cross EMA/SMA — Test 6 pares | Parametros por defecto v1.10")
    print("  IS: 2014-2021 | OOS: 2022-2025 | Capital: $50,000")
    print("=" * 72)

    results = []
    for pair, fname in PAIRS.items():
        path = os.path.join(DATA, fname)
        if not os.path.exists(path):
            print(f"  {pair}: archivo no encontrado, saltando")
            continue

        cfg = PAIR_CONFIG[pair]
        df_raw = pd.read_csv(path, index_col=0, parse_dates=True)
        df_all = add_indicators(df_raw, DEFAULT_PARAMS)

        df_is  = df_all[df_all.index <= IS_END]
        df_oos = df_all[df_all.index >= OOS_START]

        t_is  = run_backtest(df_is,  DEFAULT_PARAMS, CAP, cfg['pip'], cfg['pip_val'])
        t_oos = run_backtest(df_oos, DEFAULT_PARAMS, CAP, cfg['pip'], cfg['pip_val'])
        m_is  = compute_metrics(t_is,  CAP)
        m_oos = compute_metrics(t_oos, CAP)

        wf = round(m_oos['pf'] / m_is['pf'], 3) if m_is['pf'] > 0 else 0
        pnl_mes = round(m_oos['pnl'] / 48, 0)  # 4 años = 48 meses
        results.append({
            'par': pair, 'tipo': TIPO[pair],
            'is_n': m_is['n'], 'is_pf': m_is['pf'], 'is_ann': m_is['ann_pct'], 'is_dd': m_is['dd_pct'],
            'oos_n': m_oos['n'], 'oos_pf': m_oos['pf'], 'oos_ann': m_oos['ann_pct'], 'oos_dd': m_oos['dd_pct'],
            'wf': wf, 'pnl_mes': pnl_mes,
        })
        print(f"  {pair} OK")

    if not results: return
    df = pd.DataFrame(results)

    print(f"\n{'Par':>7} {'Tipo':>10} {'IS_N':>6} {'IS_PF':>6} {'IS_Ann%':>8} {'IS_DD%':>7} | {'OOS_N':>6} {'OOS_PF':>7} {'OOS_Ann%':>9} {'OOS_DD%':>8} {'WF':>6} {'$/mes':>8}")
    print("-" * 100)
    for _, r in df.sort_values('oos_pf', ascending=False).iterrows():
        mark = " <-- MEJOR" if r['oos_pf'] == df['oos_pf'].max() else ""
        print(f"  {r['par']:>6} {r['tipo']:>10} {int(r['is_n']):>6} {r['is_pf']:>6.2f} {r['is_ann']:>8.1f} {r['is_dd']:>7.1f} | "
              f"{int(r['oos_n']):>6} {r['oos_pf']:>7.2f} {r['oos_ann']:>9.1f} {r['oos_dd']:>8.1f} {r['wf']:>6.3f} {r['pnl_mes']:>8.0f}{mark}")

    print(f"\n  TENDENCIA:")
    tend = df[df['tipo']=='TENDENCIA']
    print(f"    OOS PF medio: {tend['oos_pf'].mean():.2f} | Mejor: {tend.loc[tend['oos_pf'].idxmax(),'par']}")
    print(f"  RANGO:")
    rang = df[df['tipo']=='RANGO']
    print(f"    OOS PF medio: {rang['oos_pf'].mean():.2f} | Mejor: {rang.loc[rang['oos_pf'].idxmax(),'par']}")

    winner = "TENDENCIA" if tend['oos_pf'].mean() > rang['oos_pf'].mean() else "RANGO"
    print(f"\n  VEREDICTO: MA Cross funciona mejor en {winner}")

if __name__ == "__main__":
    main()
