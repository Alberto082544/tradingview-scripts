"""Monte Carlo + correlacion AUDNZD v3 vs EURUSD v2.

Objetivo: saber si es seguro operar los 2 bots juntos en una cuenta con DD<5%.

Calcula:
  1. Trades OOS reales de cada bot
  2. Monte Carlo individual (1000 simulaciones por bot)
       -> DD P50/P95/P99
  3. Correlacion diaria entre PnL de los 2 bots
  4. DD agregado REAL OOS (suma dia a dia)
  5. Monte Carlo conjunto (1000 simulaciones de la cuenta combinada)
       -> DD agregado P50/P95/P99
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.stdout.reconfigure(encoding='utf-8')

import pandas as pd
import numpy as np

from strategies.ranger_c_audnzd_stoch import (
    add_indicators as audnzd_ind,
    run_backtest    as audnzd_bt,
    compute_metrics as audnzd_m,
    DEFAULT_PARAMS  as AUDNZD_DEF,
)
from strategies.ma_cross_m15 import (
    add_indicators as ma_ind,
    run_backtest    as ma_bt,
    compute_metrics as ma_m,
    PAIR_CONFIG,
)

DATA = os.path.join(os.path.dirname(__file__), '..', 'data')
INITIAL = 50_000
OOS_START = '2022-01-01'
N_SIM = 1000


# === Parametros ganadores ===
AUDNZD_PARAMS = {**AUDNZD_DEF, **{
    'ADX_H4_Max': 20, 'StochMode': 1,
    'Stoch_K': 5, 'Stoch_D': 3,
    'Stoch_Long_Max': 15, 'Stoch_Short_Min': 75,
    'MinSLPips': 20, 'TrailDistPips': 4, 'ExitBars': 32,
    'RSI_Confirm': 1, 'BB_Mid_TP': 0,
}}

EURUSD_PARAMS = {
    'ATR_Period': 14, 'BE_Offset': 0.0002,
    'Trail_Start': 1.5, 'MaxSpreadPips': 3.0,
    'LotRiskPct': 0.5, 'MaxLots': 4.0,
    'EMA_Fast': 8, 'SMA_Slow': 34,
    'Dir_EMA_Fast': 8, 'Dir_SMA_Slow': 34,
    'SL_ATR_Mult': 2.0, 'RR': 2.5,
    'Trail_Dist': 0.5, 'BE_Trigger': 0.5,
}


def cargar_audnzd_trades():
    df = pd.read_csv(os.path.join(DATA, 'AUDNZD_M15_histdata.csv'),
                     parse_dates=['time'], index_col='time')
    df = audnzd_ind(df, AUDNZD_PARAMS)
    df_oos = df.loc[OOS_START:]
    return audnzd_bt(df_oos, AUDNZD_PARAMS, initial_capital=INITIAL)


def cargar_eurusd_trades():
    df = pd.read_csv(os.path.join(DATA, 'EURUSD_M15_histdata.csv'),
                     index_col=0, parse_dates=True)
    df = ma_ind(df, EURUSD_PARAMS)
    df_oos = df.loc[OOS_START:]
    cfg = PAIR_CONFIG['EURUSD']
    return ma_bt(df_oos, EURUSD_PARAMS, INITIAL, cfg['pip'], cfg['pip_val'])


def monte_carlo_dd(pnls: np.ndarray, n: int = N_SIM) -> dict:
    """Reordena aleatoriamente los pnl y calcula DD% de cada simulacion."""
    rng = np.random.default_rng(42)
    dds = np.empty(n)
    for i in range(n):
        order = rng.permutation(len(pnls))
        eq = INITIAL + np.cumsum(pnls[order])
        peak = np.maximum.accumulate(eq)
        dds[i] = ((eq - peak) / peak).min() * -100  # DD% positivo
    return {
        'dd_p50':  np.percentile(dds, 50),
        'dd_p95':  np.percentile(dds, 95),
        'dd_p99':  np.percentile(dds, 99),
        'dd_max':  dds.max(),
    }


def dd_real(daily_pnl: pd.Series) -> float:
    eq = INITIAL + daily_pnl.cumsum()
    peak = eq.cummax()
    return ((eq - peak) / peak).min() * -100


def main():
    print("="*70, flush=True)
    print("  MONTE CARLO + CORRELACION  AUDNZD v3 vs EURUSD v2", flush=True)
    print("  OOS 2022-2025  |  Capital $50,000  |  Simulaciones: 1000", flush=True)
    print("="*70, flush=True)

    print("\n[1/4] Generando trades OOS AUDNZD v3...", flush=True)
    t_aud = cargar_audnzd_trades()
    print(f"      Trades AUDNZD: {len(t_aud)}", flush=True)
    print("\n[2/4] Generando trades OOS EURUSD v2...", flush=True)
    t_eur = cargar_eurusd_trades()
    print(f"      Trades EURUSD: {len(t_eur)}", flush=True)

    # --- Metricas reales individuales ---
    m_aud = audnzd_m(t_aud, INITIAL)
    m_eur = ma_m(t_eur, INITIAL)
    print("\n--- METRICAS REALES OOS ---", flush=True)
    print(f"  AUDNZD: PF={m_aud['pf']} DD={m_aud['dd_pct']}% N={m_aud['n']} Ann={m_aud['ann_pct']}%", flush=True)
    print(f"  EURUSD: PF={m_eur['pf']} DD={m_eur['dd_pct']}% N={m_eur['n']} Ann={m_eur['ann_pct']}%", flush=True)

    # --- Monte Carlo individual ---
    print("\n[3/4] Monte Carlo individual (1000 simulaciones por bot)...", flush=True)
    mc_aud = monte_carlo_dd(t_aud['pnl'].values)
    mc_eur = monte_carlo_dd(t_eur['pnl'].values)
    print("\n--- MONTE CARLO DD ---", flush=True)
    print(f"  AUDNZD:  P50={mc_aud['dd_p50']:.2f}%  P95={mc_aud['dd_p95']:.2f}%  P99={mc_aud['dd_p99']:.2f}%  Max={mc_aud['dd_max']:.2f}%", flush=True)
    print(f"  EURUSD:  P50={mc_eur['dd_p50']:.2f}%  P95={mc_eur['dd_p95']:.2f}%  P99={mc_eur['dd_p99']:.2f}%  Max={mc_eur['dd_max']:.2f}%", flush=True)

    # --- Correlacion diaria ---
    print("\n[4/4] Correlacion y DD agregado real...", flush=True)
    daily_aud = (t_aud.set_index(pd.to_datetime(t_aud['exit_dt'])).groupby(pd.Grouper(freq='D'))['pnl'].sum())
    daily_eur = (t_eur.set_index(pd.to_datetime(t_eur['exit_dt'])).groupby(pd.Grouper(freq='D'))['pnl'].sum())
    daily = pd.concat([daily_aud, daily_eur], axis=1).fillna(0)
    daily.columns = ['AUDNZD', 'EURUSD']

    corr = daily.corr().iloc[0, 1]
    print(f"\n--- CORRELACION DIARIA ---", flush=True)
    print(f"  Pearson r(AUDNZD, EURUSD) = {corr:.4f}", flush=True)
    if abs(corr) < 0.2:
        cor_txt = "BAJA (no correlados, ideal para diversificar)"
    elif abs(corr) < 0.5:
        cor_txt = "MODERADA"
    else:
        cor_txt = "ALTA (DD podria amplificarse)"
    print(f"  Interpretacion: {cor_txt}", flush=True)

    # --- DD agregado real ---
    daily['SUMA'] = daily['AUDNZD'] + daily['EURUSD']
    dd_aud_real  = dd_real(daily['AUDNZD'])
    dd_eur_real  = dd_real(daily['EURUSD'])
    dd_agg_real  = dd_real(daily['SUMA'])
    print(f"\n--- DD REAL OOS (suma dia a dia) ---", flush=True)
    print(f"  AUDNZD solo:        {dd_aud_real:.2f}%", flush=True)
    print(f"  EURUSD solo:        {dd_eur_real:.2f}%", flush=True)
    print(f"  AMBOS combinados:   {dd_agg_real:.2f}%  ({dd_agg_real/(dd_aud_real+dd_eur_real)*100:.0f}% de la suma)", flush=True)

    # --- Monte Carlo conjunto ---
    print("\nMonte Carlo cuenta combinada (1000 simulaciones)...", flush=True)
    pnls_all = np.concatenate([t_aud['pnl'].values, t_eur['pnl'].values])
    mc_agg = monte_carlo_dd(pnls_all)
    print(f"\n--- MONTE CARLO DD AGREGADO ---", flush=True)
    print(f"  P50={mc_agg['dd_p50']:.2f}%  P95={mc_agg['dd_p95']:.2f}%  P99={mc_agg['dd_p99']:.2f}%  Max={mc_agg['dd_max']:.2f}%", flush=True)

    # --- Veredicto ---
    print("\n" + "="*70, flush=True)
    print("  VEREDICTO FONDEO (DD limite 5%)", flush=True)
    print("="*70, flush=True)
    seguro_5pct = (mc_agg['dd_p95'] < 5.0)
    seguro_99   = (mc_agg['dd_p99'] < 5.0)
    if seguro_99:
        print("  ✓ Operar AMBOS bots: SEGURO incluso al P99", flush=True)
    elif seguro_5pct:
        print("  ⚠ Operar AMBOS bots: SEGURO al P95 (riesgo 5% de tocar limite)", flush=True)
    else:
        print("  ✗ Operar AMBOS bots a sizing actual: ROMPE 5% en P95", flush=True)
        factor = 5.0 / mc_agg['dd_p95']
        print(f"    Reducir LotRiskPct un {(1-factor)*100:.0f}% (x{factor:.2f}) para estar seguro P95", flush=True)

    # Guardar
    out = os.path.join(os.path.dirname(__file__), '..', 'reports', 'MonteCarlo_AUDNZD_EURUSD.md')
    with open(out, 'w', encoding='utf-8') as f:
        f.write(f"""# Monte Carlo + Correlacion — AUDNZD v3 / EURUSD v2

**Fecha:** 2026-05-17 | **OOS:** 2022-2025 | **Capital:** $50,000

## Metricas reales individuales
| Bot | PF | DD | N | Ann |
|-----|-----|-----|---|-----|
| AUDNZD v3 | {m_aud['pf']} | {m_aud['dd_pct']}% | {m_aud['n']} | {m_aud['ann_pct']}% |
| EURUSD v2 | {m_eur['pf']} | {m_eur['dd_pct']}% | {m_eur['n']} | {m_eur['ann_pct']}% |

## Monte Carlo DD individual (1000 simulaciones)
| Bot | P50 | P95 | P99 | Max |
|-----|-----|-----|-----|-----|
| AUDNZD | {mc_aud['dd_p50']:.2f}% | {mc_aud['dd_p95']:.2f}% | {mc_aud['dd_p99']:.2f}% | {mc_aud['dd_max']:.2f}% |
| EURUSD | {mc_eur['dd_p50']:.2f}% | {mc_eur['dd_p95']:.2f}% | {mc_eur['dd_p99']:.2f}% | {mc_eur['dd_max']:.2f}% |

## Correlacion diaria
**Pearson r(AUDNZD, EURUSD) = {corr:.4f}** → {cor_txt}

## DD agregado real OOS
| Setup | DD |
|-------|-----|
| AUDNZD solo | {dd_aud_real:.2f}% |
| EURUSD solo | {dd_eur_real:.2f}% |
| Ambos combinados | **{dd_agg_real:.2f}%** ({dd_agg_real/(dd_aud_real+dd_eur_real)*100:.0f}% de la suma) |

## Monte Carlo DD agregado
| P50 | P95 | P99 | Max |
|-----|-----|-----|-----|
| {mc_agg['dd_p50']:.2f}% | {mc_agg['dd_p95']:.2f}% | {mc_agg['dd_p99']:.2f}% | {mc_agg['dd_max']:.2f}% |

## Veredicto fondeo (DD max 5%)
""")
        if seguro_99:
            f.write("**SEGURO incluso al P99** — operar ambos bots sin riesgo significativo de tocar 5%.\n")
        elif seguro_5pct:
            f.write("**SEGURO al P95** — operar ambos bots con riesgo ~5% de tocar el limite.\n")
        else:
            factor = 5.0 / mc_agg['dd_p95']
            f.write(f"**ROMPE 5% en P95** — reducir LotRiskPct un {(1-factor)*100:.0f}% (x{factor:.2f}).\n")
    print(f"\n  Informe guardado: {out}", flush=True)


if __name__ == '__main__':
    main()
