"""A/B test AUDNZD: baseline (sin Stoch, ADX_H4_Max=30) vs variantes con Stochastic.

Recomendacion CrewAI 2026-05-17: Stochastic(5,3,3) + ADX_H4 < 20 sobre Ranger C.
Criterio migracion (con tema fondeos):
  PF OOS  > 1.16 (actual)
  WF      > 1.045
  DD OOS  < 12.6%  (CRITICO para fondeo: idealmente <10%)
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.stdout.reconfigure(encoding='utf-8')

import pandas as pd
from strategies.ranger_c_audnzd_stoch import add_indicators, run_backtest, compute_metrics

DATA_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'AUDNZD_M15_histdata.csv')
IS_END    = '2021-12-31'
OOS_START = '2022-01-01'
INITIAL   = 50_000

# Variantes a comparar
VARIANTES = [
    {
        'nombre': 'A: BASELINE (RSI solo, ADX<30)',
        'params': {
            'ADX_H4_Max':      30,
            'RSI_Long_Max':    50,
            'RSI_Short_Min':   50,
            'RSI_Confirm':      1,
            'StochMode':        0,
            'BB_Mid_TP':        0,
            'MinSLPips':       20,
            'TrailDistPips':    8,
            'ExitBars':        32,
        }
    },
    {
        'nombre': 'B: STOCH+ADX<20 (modo ambos)',
        'params': {
            'ADX_H4_Max':      20,
            'RSI_Long_Max':    50,
            'RSI_Short_Min':   50,
            'RSI_Confirm':      1,
            'StochMode':        2,
            'Stoch_K':          5,
            'Stoch_D':          3,
            'Stoch_Long_Max':  25,
            'Stoch_Short_Min': 75,
            'BB_Mid_TP':        0,
            'MinSLPips':       20,
            'TrailDistPips':    8,
            'ExitBars':        32,
        }
    },
    {
        'nombre': 'C: STOCH SOLO+ADX<20',
        'params': {
            'ADX_H4_Max':      20,
            'StochMode':        1,
            'Stoch_K':          5,
            'Stoch_D':          3,
            'Stoch_Long_Max':  25,
            'Stoch_Short_Min': 75,
            'BB_Mid_TP':        0,
            'MinSLPips':       20,
            'TrailDistPips':    8,
            'ExitBars':        32,
        }
    },
    {
        'nombre': 'D: STOCH+ADX<25 (intermedio)',
        'params': {
            'ADX_H4_Max':      25,
            'RSI_Long_Max':    50,
            'RSI_Short_Min':   50,
            'RSI_Confirm':      1,
            'StochMode':        2,
            'Stoch_K':          5,
            'Stoch_D':          3,
            'Stoch_Long_Max':  25,
            'Stoch_Short_Min': 75,
            'BB_Mid_TP':        0,
            'MinSLPips':       20,
            'TrailDistPips':    8,
            'ExitBars':        32,
        }
    },
]


def merge_defaults(p):
    from strategies.ranger_c_audnzd_stoch import DEFAULT_PARAMS
    return {**DEFAULT_PARAMS, **p}


def run_one(name, raw_params, df_full):
    p = merge_defaults(raw_params)
    df = add_indicators(df_full, p)
    df_is  = df.loc[:IS_END]
    df_oos = df.loc[OOS_START:]

    t_is  = run_backtest(df_is,  p, initial_capital=INITIAL)
    t_oos = run_backtest(df_oos, p, initial_capital=INITIAL)
    m_is  = compute_metrics(t_is,  INITIAL)
    m_oos = compute_metrics(t_oos, INITIAL)

    wf = (m_oos['pf'] / m_is['pf']) if m_is['pf'] > 0 else 0
    meses_oos = (pd.to_datetime(t_oos['exit_dt'].iloc[-1]) -
                 pd.to_datetime(t_oos['entry_dt'].iloc[0])).days / 30.44 if len(t_oos) > 0 else 1
    usd_mes = m_oos['pnl'] / meses_oos if meses_oos > 0 else 0

    return {
        'nombre':   name,
        'is_pf':    m_is['pf'],
        'is_dd':    m_is['dd_pct'],
        'is_n':     m_is['n'],
        'oos_pf':   m_oos['pf'],
        'oos_wr':   m_oos['wr'],
        'oos_dd':   m_oos['dd_pct'],
        'oos_ann':  m_oos['ann_pct'],
        'oos_pnl':  m_oos['pnl'],
        'oos_n':    m_oos['n'],
        'wf':       round(wf, 3),
        'usd_mes':  round(usd_mes, 0),
    }


def main():
    print(f"Cargando {DATA_PATH}...", flush=True)
    df = pd.read_csv(DATA_PATH, parse_dates=['time'], index_col='time')
    print(f"Datos: {df.index[0]} -> {df.index[-1]} ({len(df)} barras)\n", flush=True)

    results = []
    for v in VARIANTES:
        print(f"Ejecutando: {v['nombre']}...", flush=True)
        r = run_one(v['nombre'], v['params'], df)
        results.append(r)
        print(f"  IS  PF={r['is_pf']} DD={r['is_dd']}% N={r['is_n']}", flush=True)
        print(f"  OOS PF={r['oos_pf']} DD={r['oos_dd']}% WR={r['oos_wr']}% N={r['oos_n']}", flush=True)
        print(f"  WF={r['wf']} Ann_OOS={r['oos_ann']}% USD/mes(OOS,$50k)={r['usd_mes']}\n", flush=True)

    print("="*90, flush=True)
    print("RESUMEN COMPARATIVO", flush=True)
    print("="*90, flush=True)
    rdf = pd.DataFrame(results)
    print(rdf.to_string(index=False), flush=True)

    # Veredicto
    print("\n" + "="*90, flush=True)
    print("VEREDICTO (CRITERIOS: PF OOS>1.16, WF>1.045, DD OOS<12.6%)", flush=True)
    print("="*90, flush=True)
    baseline = results[0]
    for r in results[1:]:
        mejor_pf  = r['oos_pf']  > baseline['oos_pf']
        mejor_wf  = r['wf']      > baseline['wf']
        mejor_dd  = r['oos_dd']  < baseline['oos_dd']
        sub_10dd  = r['oos_dd']  < 10.0
        sub_5dd   = r['oos_dd']  < 5.0
        veredicto = "MIGRAR" if (mejor_pf and mejor_wf and mejor_dd) else "no migrar"
        flag_fn   = "✅ FundedNext" if sub_10dd else "❌ FundedNext"
        flag_5p   = "✅ The 5%ers"  if sub_5dd  else "❌ The 5%ers"
        print(f"  {r['nombre']}: {veredicto} | {flag_fn} | {flag_5p}", flush=True)


if __name__ == '__main__':
    main()
