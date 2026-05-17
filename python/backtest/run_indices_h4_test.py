"""
MA Cross H4+D1 — Test en 4 indices (NAS100, SP500, DAX40, UK100)
IS: 2014-2021 | OOS: 2022-2025 | Capital $50,000
Uso: python -m backtest.run_indices_h4_test
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pandas as pd
import numpy as np
from strategies.ma_cross_indices_h4 import (
    add_indicators, run_backtest, compute_metrics, INDEX_CONFIG, DEFAULT_PARAMS
)

DATA      = os.path.join(os.path.dirname(__file__), "..", "data")
CAP       = 50_000.0
IS_END    = "2021-12-31"
OOS_START = "2022-01-01"

INDICES = {
    'NAS100': 'NAS100_H4_mt5.csv',
    'SP500':  'SP500_H4_mt5.csv',
    'DAX40':  'DAX40_H4_mt5.csv',
    'UK100':  'UK100_H4_mt5.csv',
}

GRID = []
for ema in [5, 8, 13, 21]:
    for sma in [21, 34, 55, 89]:
        for sl in [1.0, 1.5, 2.0]:
            for rr in [1.5, 2.0, 3.0]:
                if ema < sma:
                    GRID.append({
                        'EMA_Fast': ema, 'SMA_Slow': sma,
                        'Dir_EMA_Fast': ema, 'Dir_SMA_Slow': sma,
                        'SL_ATR_Mult': sl, 'RR': rr,
                    })


def monte_carlo(trades, n_sim=500, seed=42):
    rng  = np.random.default_rng(seed)
    pnls = trades['pnl'].values
    finals, dds = [], []
    for _ in range(n_sim):
        eq = CAP + np.cumsum(rng.choice(pnls, size=len(pnls), replace=True))
        pk = np.maximum.accumulate(np.concatenate([[CAP], eq]))
        dds.append(abs(((np.concatenate([[CAP], eq]) - pk) / pk).min()) * 100)
        finals.append(eq[-1])
    return round((np.array(finals) > CAP).mean() * 100, 1), round(np.percentile(dds, 95), 1)


def main():
    print("=" * 82)
    print("  MA Cross H4+D1 — Indices | IS 2014-2021 | OOS 2022-2025 | $50,000")
    print(f"  Grid: {len(GRID)} combinaciones por indice")
    print("=" * 82)

    resultados = []

    for idx_name, fname in INDICES.items():
        path = os.path.join(DATA, fname)
        if not os.path.exists(path):
            print(f"\n  {idx_name}: archivo no encontrado ({fname})")
            continue

        cfg = INDEX_CONFIG[idx_name]
        df_raw = pd.read_csv(path, index_col=0, parse_dates=True).dropna()

        print(f"\n  [{idx_name}] {len(df_raw):,} barras H4 — optimizando {len(GRID)} params IS...")

        best_is_pf = -1
        best_params = None

        for params in GRID:
            try:
                df_all = add_indicators(df_raw, params)
                df_is  = df_all[df_all.index <= IS_END]
                t_is   = run_backtest(df_is, params, CAP, cfg['pip'], cfg['pip_val'])
                m_is   = compute_metrics(t_is, CAP)
                if m_is['n'] < 30:
                    continue
                if m_is['pf'] > best_is_pf:
                    best_is_pf = m_is['pf']
                    best_params = params
            except Exception:
                continue

        if best_params is None:
            print(f"  {idx_name}: sin combinacion valida (trades insuficientes)")
            continue

        df_all = add_indicators(df_raw, best_params)
        df_is  = df_all[df_all.index <= IS_END]
        df_oos = df_all[df_all.index >= OOS_START]

        t_is  = run_backtest(df_is,  best_params, CAP, cfg['pip'], cfg['pip_val'])
        t_oos = run_backtest(df_oos, best_params, CAP, cfg['pip'], cfg['pip_val'])
        m_is  = compute_metrics(t_is,  CAP)
        m_oos = compute_metrics(t_oos, CAP)

        wf = round(m_oos['pf'] / m_is['pf'], 3) if m_is['pf'] > 0 else 0
        mc_pct, mc_dd = (monte_carlo(t_oos) if len(t_oos) >= 20 else (0.0, 0.0))

        anos_pos = 0
        if len(t_oos) > 0:
            t_oos_cp = t_oos.copy()
            t_oos_cp['year'] = pd.to_datetime(t_oos_cp['exit_dt']).dt.year
            anos_pos = int((t_oos_cp.groupby('year')['pnl'].sum() > 0).sum())

        pnl_mes = round(m_oos['pnl'] / 48, 0)
        p_str   = f"EMA{best_params['EMA_Fast']}/SMA{best_params['SMA_Slow']} SL{best_params['SL_ATR_Mult']} RR{best_params['RR']}"

        valido = "BUENO" if (m_oos['pf'] >= 1.2 and wf >= 0.85 and mc_pct >= 70) else \
                 ("MARGINAL" if m_oos['pf'] >= 1.1 else "MALO")

        print(f"  -> Mejores params IS: {p_str}")
        print(f"     IS:  N={m_is['n']:>4}  PF={m_is['pf']:.2f}  Ann={m_is['ann_pct']:+.1f}%  DD={m_is['dd_pct']:.1f}%")
        print(f"     OOS: N={m_oos['n']:>4}  PF={m_oos['pf']:.2f}  Ann={m_oos['ann_pct']:+.1f}%  DD={m_oos['dd_pct']:.1f}%  "
              f"WF={wf:.3f}  MC={mc_pct:.0f}%  Anos+={anos_pos}/4  {pnl_mes:+.0f}$/mes  [{valido}]")

        resultados.append({
            'indice': idx_name, 'params': p_str,
            'is_n': m_is['n'], 'is_pf': m_is['pf'],
            'oos_n': m_oos['n'], 'oos_pf': m_oos['pf'],
            'oos_ann': m_oos['ann_pct'], 'oos_dd': m_oos['dd_pct'],
            'wf': wf, 'mc_pct': mc_pct, 'mc_dd': mc_dd,
            'anos_pos': anos_pos, 'pnl_mes': pnl_mes, 'valido': valido,
        })

    print("\n" + "=" * 82)
    print("  VEREDICTO FINAL")
    print("=" * 82)
    buenos    = [r for r in resultados if r['valido'] == 'BUENO']
    marginales = [r for r in resultados if r['valido'] == 'MARGINAL']
    malos     = [r for r in resultados if r['valido'] == 'MALO']

    if buenos:
        print(f"\n  CANDIDATOS A DESARROLLAR: {', '.join(r['indice'] for r in buenos)}")
        for r in buenos:
            print(f"    {r['indice']}: PF OOS={r['oos_pf']:.2f}  WF={r['wf']:.3f}  MC={r['mc_pct']:.0f}%  {r['pnl_mes']:+.0f}$/mes")
    if marginales:
        print(f"\n  MARGINALES (necesitan mas trabajo): {', '.join(r['indice'] for r in marginales)}")
    if malos:
        print(f"\n  DESCARTAR: {', '.join(r['indice'] for r in malos)}")

    print()

if __name__ == "__main__":
    main()
