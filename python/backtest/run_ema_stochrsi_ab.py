"""A/B test: EMA200+StochRSI (H4+M15) vs MA Cross EURUSD v2.

Variantes para tantear el espacio de parametros:
  A — Baseline (zona on, StochRSI 15/85, RR=2.0)
  B — Sin zona (solo direccion + StochRSI)
  C — Stoch mas estricto (10/90)
  D — RR=3.0
  E — Sin zona + Stoch 10/90 + RR=3.0
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.stdout.reconfigure(encoding='utf-8')

import pandas as pd
from strategies.ema_stochrsi_m15 import (
    add_indicators as es_ind, run_backtest as es_bt,
    compute_metrics as es_m, DEFAULT_PARAMS as ES_DEF)

DATA = os.path.join(os.path.dirname(__file__), '..', 'data', 'EURUSD_M15_histdata.csv')
INITIAL = 50_000
IS_END   = '2021-12-31'
OOS_START = '2022-01-01'

VARIANTES = [
    ('A: Baseline (zona on, Stoch 15/85, RR=2)', {}),
    ('B: Sin zona EMA13-EMA32',                  {'UsePullbackZone': 0}),
    ('C: Stoch extremo 10/90',                   {'Stoch_Buy_Max':10, 'Stoch_Sell_Min':90}),
    ('D: RR=3.0',                                {'RR':3.0}),
    ('E: Sin zona + Stoch 10/90 + RR=3',         {'UsePullbackZone':0, 'Stoch_Buy_Max':10, 'Stoch_Sell_Min':90, 'RR':3.0}),
]


def run_one(nombre, overrides, df_raw):
    p = {**ES_DEF, **overrides}
    df = es_ind(df_raw, p)
    df_is  = df.loc[:IS_END]
    df_oos = df.loc[OOS_START:]
    t_is  = es_bt(df_is,  p, INITIAL, pip=0.0001, pip_val=10.0)
    t_oos = es_bt(df_oos, p, INITIAL, pip=0.0001, pip_val=10.0)
    m_is  = es_m(t_is,  INITIAL)
    m_oos = es_m(t_oos, INITIAL)
    wf    = (m_oos['pf']/m_is['pf']) if m_is['pf'] > 0 else 0
    return {'nombre':nombre,
            'is_pf':m_is['pf'],  'is_dd':m_is['dd_pct'],  'is_n':m_is['n'],
            'oos_pf':m_oos['pf'],'oos_dd':m_oos['dd_pct'],'oos_n':m_oos['n'],
            'oos_wr':m_oos['wr'],'oos_ann':m_oos['ann_pct'],
            'oos_pnl':m_oos['pnl'], 'wf':round(wf, 3)}


def main():
    print(f"Cargando {DATA}...", flush=True)
    df = pd.read_csv(DATA, index_col=0, parse_dates=True)
    print(f"Datos: {df.index[0]} -> {df.index[-1]}\n", flush=True)

    results = []
    for nombre, ov in VARIANTES:
        print(f"  {nombre}...", flush=True)
        r = run_one(nombre, ov, df)
        results.append(r)
        print(f"    IS  PF={r['is_pf']}  DD={r['is_dd']}%  N={r['is_n']}", flush=True)
        print(f"    OOS PF={r['oos_pf']}  DD={r['oos_dd']}%  WR={r['oos_wr']}%  N={r['oos_n']}  Ann={r['oos_ann']}%  WF={r['wf']}\n", flush=True)

    print("="*96)
    print("RESUMEN  vs  EURUSD v2 baseline (PF OOS 1.41 / DD 4.8% / WF 1.128 / Ann 24.2%)")
    print("="*96)
    rdf = pd.DataFrame(results)
    print(rdf.to_string(index=False))

    print("\n" + "="*96)
    print("VEREDICTO MIGRACION  (criterio: PF OOS > 1.41 Y DD < 5% Y WF > 1.0 Y N >= 100)")
    print("="*96)
    for r in results:
        c1 = r['oos_pf']  > 1.41
        c2 = r['oos_dd']  < 5.0
        c3 = r['wf']      > 1.0
        c4 = r['oos_n']   >= 100
        ok = c1 and c2 and c3 and c4
        flags = f"PF{'OK' if c1 else 'NO'} DD{'OK' if c2 else 'NO'} WF{'OK' if c3 else 'NO'} N{'OK' if c4 else 'NO'}"
        veredicto = "MIGRAR ✓" if ok else "no migrar"
        print(f"  {r['nombre']:42s}  {flags}   {veredicto}")


if __name__ == '__main__':
    main()
