"""
MA Cross D1 — Test inicial en 4 índices (NAS100, SP500, DAX40, UK100)
IS: 2014-2021 | OOS: 2022-2025 | Capital: $50,000
Uso: python -m backtest.run_indices_test
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pandas as pd
import numpy as np
from strategies.ma_cross_indices_d1 import add_indicators, run_backtest, compute_metrics, INDEX_CONFIG, DEFAULT_PARAMS

DATA      = os.path.join(os.path.dirname(__file__), "..", "data")
CAP       = 50_000.0
IS_END    = "2021-12-31"
OOS_START = "2022-01-01"

INDICES = {
    'NAS100': 'NAS100_D1_yahoo.csv',
    'SP500':  'SP500_D1_yahoo.csv',
    'DAX40':  'DAX40_D1_yahoo.csv',
    'UK100':  'UK100_D1_yahoo.csv',
}

# Grid de parámetros para optimización rápida
GRID = []
for ema in [5, 8, 13]:
    for sma in [21, 34, 55]:
        for sl in [1.0, 1.5, 2.0]:
            for rr in [1.5, 2.0, 3.0]:
                if ema < sma:
                    GRID.append({'EMA_Fast': ema, 'SMA_Slow': sma,
                                 'Dir_EMA_Fast': ema, 'Dir_SMA_Slow': sma,
                                 'SL_ATR_Mult': sl, 'RR': rr})

def monte_carlo(trades, n_sim=300, seed=42):
    rng  = np.random.default_rng(seed)
    pnls = trades['pnl'].values
    finals, dds = [], []
    for _ in range(n_sim):
        eq = CAP + np.cumsum(rng.choice(pnls, size=len(pnls), replace=True))
        pk = np.maximum.accumulate(np.concatenate([[CAP], eq]))
        dds.append(abs(((np.concatenate([[CAP], eq]) - pk) / pk).min()) * 100)
        finals.append(eq[-1])
    return round((np.array(finals) > CAP).mean() * 100, 1), round(np.percentile(dds, 95), 1)

def wf_ratio(m_is, m_oos):
    if m_is['pf'] > 0:
        return round(m_oos['pf'] / m_is['pf'], 3)
    return 0

def main():
    print("=" * 80)
    print("  MA Cross D1+W1 — Test índices | IS: 2014-2021 | OOS: 2022-2025 | $50k")
    print("=" * 80)

    resultados = []

    for idx_name, fname in INDICES.items():
        path = os.path.join(DATA, fname)
        if not os.path.exists(path):
            print(f"\n  {idx_name}: archivo no encontrado, saltando")
            continue

        cfg = INDEX_CONFIG[idx_name]
        df_raw = pd.read_csv(path, index_col=0, parse_dates=True)
        df_raw = df_raw.dropna()

        print(f"\n  Optimizando {idx_name} ({len(GRID)} combinaciones)...")

        best_is_pf = -1
        best_params = None

        for params in GRID:
            try:
                df_all = add_indicators(df_raw, params)
                df_is  = df_all[df_all.index <= IS_END]
                t_is   = run_backtest(df_is, params, CAP, cfg['pip'], cfg['pip_val'])
                m_is   = compute_metrics(t_is, CAP)
                if m_is['n'] < 20: continue
                if m_is['pf'] > best_is_pf:
                    best_is_pf = m_is['pf']
                    best_params = params
            except Exception:
                continue

        if best_params is None:
            print(f"  {idx_name}: sin resultados válidos")
            continue

        # Evaluar en OOS con los mejores parámetros IS
        df_all = add_indicators(df_raw, best_params)
        df_is  = df_all[df_all.index <= IS_END]
        df_oos = df_all[df_all.index >= OOS_START]

        t_is  = run_backtest(df_is,  best_params, CAP, cfg['pip'], cfg['pip_val'])
        t_oos = run_backtest(df_oos, best_params, CAP, cfg['pip'], cfg['pip_val'])
        m_is  = compute_metrics(t_is,  CAP)
        m_oos = compute_metrics(t_oos, CAP)

        wf = wf_ratio(m_is, m_oos)
        mc_pct, mc_dd = (monte_carlo(t_oos) if len(t_oos) >= 10 else (0, 0))
        anos_pos = 0
        if len(t_oos) > 0:
            t_oos['year'] = pd.to_datetime(t_oos['exit_dt']).dt.year
            anos_pos = (t_oos.groupby('year')['pnl'].sum() > 0).sum()

        pnl_mes = round(m_oos['pnl'] / 48, 0)

        resultados.append({
            'indice': idx_name,
            'params': f"EMA{best_params['EMA_Fast']}/SMA{best_params['SMA_Slow']} SL{best_params['SL_ATR_Mult']} RR{best_params['RR']}",
            'is_n': m_is['n'], 'is_pf': m_is['pf'], 'is_ann': m_is['ann_pct'], 'is_dd': m_is['dd_pct'],
            'oos_n': m_oos['n'], 'oos_pf': m_oos['pf'], 'oos_ann': m_oos['ann_pct'], 'oos_dd': m_oos['dd_pct'],
            'wf': wf, 'mc_pct': mc_pct, 'mc_dd': mc_dd, 'anos_pos': anos_pos,
            'pnl_mes': pnl_mes, 'pnl_total': m_oos['pnl'],
        })
        print(f"  {idx_name}: OOS PF={m_oos['pf']:.2f} | Ann={m_oos['ann_pct']:.1f}% | DD={m_oos['dd_pct']:.1f}% | WF={wf} | MC={mc_pct}% | {pnl_mes:+.0f}$/mes")

    if not resultados:
        print("\n  Sin resultados.")
        return

    print("\n" + "=" * 80)
    print("  RESUMEN FINAL — OOS (datos no vistos 2022-2025)")
    print("=" * 80)
    print(f"\n{'Índice':>8} {'Params':>22} {'IS_PF':>6} {'OOS_PF':>7} {'OOS_Ann%':>9} {'OOS_DD%':>8} {'WF':>6} {'MC%':>5} {'$/mes':>8}")
    print("-" * 80)

    for r in sorted(resultados, key=lambda x: x['oos_pf'], reverse=True):
        valido = " ✅" if r['oos_pf'] >= 1.2 and r['wf'] >= 0.9 else (" ⚠️" if r['oos_pf'] >= 1.1 else " ❌")
        print(f"  {r['indice']:>7} {r['params']:>22} {r['is_pf']:>6.2f} {r['oos_pf']:>7.2f} {r['oos_ann']:>9.1f} {r['oos_dd']:>8.1f} {r['wf']:>6.3f} {r['mc_pct']:>5.0f} {r['pnl_mes']:>8.0f}{valido}")

    print()
    buenos = [r for r in resultados if r['oos_pf'] >= 1.15 and r['wf'] >= 0.85]
    if buenos:
        print(f"  CANDIDATOS A DESARROLLAR: {', '.join(r['indice'] for r in buenos)}")
    else:
        print("  Ningún índice supera el umbral mínimo (OOS PF>=1.15 + WF>=0.85)")

if __name__ == "__main__":
    main()
