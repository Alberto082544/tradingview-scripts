"""
Ranger C AUDNZD Stoch RESTRICTIVO — Grid disenyado por DeepSeek (6 sombreros) 2026-05-21
Familia: Ranger C | Par: AUDNZD | Variante: Stoch | Modo: restrictivo

Objetivo: encontrar combo con OOS_DD <= 6% y WF >= 1.0 SIN tocar sizing.
Si exito → permite deploy con LotRiskPct=0.7 (sin reducir).
Si fallo → caer al combo del grid normal con sizing reducido (mitad).

Grid fijado: StochMode=2, TrailDist=8, RSI_L=40, RSI_S=60 (valores ganadores AUDCAD).
Solo varia: MinSL [20,25], ExitBars [16,20], ADX_H4_Max [20,25] = 8 combos.

NOTA: el motor de backtest NO calcula MC ni year-by-year. Esos checks se hacen
a posteriori con audcad_yearbyyear_mc.py adaptado a AUDNZD-Stoch sobre top 3.

Uso: python -m backtest.run_ranger_c_audnzd_stoch_restrictivo_opt
"""
import os, sys, itertools, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pandas as pd
import multiprocessing as mp
from strategies.ranger_c_audnzd_stoch import add_indicators, run_backtest, compute_metrics

CACHE     = os.path.join(os.path.dirname(__file__), "..", "data", "AUDNZD_M15_histdata.csv")
CAP       = 50_000.0
IS_END    = "2021-12-31"
OOS_START = "2022-01-01"

FIXED_IND = {
    'BB_Period':20, 'BB_StdDev':2.0, 'RSI_Period':14,
    'ADX_H4_Period':14, 'ATR_Period':14,
    'Stoch_K':5, 'Stoch_D':3,
}

# Grid RESTRICTIVO segun DeepSeek 6 sombreros 2026-05-21
GRID = {
    'MinSLPips':       [20, 25],
    'ExitBars':        [16, 20],
    'ADX_H4_Max':      [20, 25],
}
# Resto FIJO en valores ganadores AUDCAD
FIXED_PARAMS = {
    'StochMode':       2,
    'Stoch_Long_Max':  20,
    'Stoch_Short_Min': 75,
    'RSI_Long_Max':    40,
    'RSI_Short_Min':   60,
    'RSI_Confirm':     1,
    'BB_Mid_TP':       0,
    'TrailDistPips':   8,
}
FIXED_BT = {
    'SL_ATR_Mult':1.5, 'MaxSLPips':999, 'TP_ATR_Mult':0,
    'TrailActivate':0.5, 'SessionStart':0, 'SessionEnd':23,
    'BadHour':-1, 'MaxTradesDay':5, 'LotRiskPct':0.7, 'MaxLots':4.0,
}

_df_is = None
_df_oos = None

def _pool_init(df_is, df_oos):
    global _df_is, _df_oos
    _df_is = df_is
    _df_oos = df_oos

def _worker(combo):
    p = {**FIXED_IND, **FIXED_BT, **FIXED_PARAMS, **combo}
    try:
        t_is  = run_backtest(_df_is,  p, CAP)
        t_oos = run_backtest(_df_oos, p, CAP)
        m_is  = compute_metrics(t_is,  CAP)
        m_oos = compute_metrics(t_oos, CAP)
    except Exception:
        return None
    if m_is['n'] < 50 or m_is['pf'] <= 0:
        return None
    exits = t_is['exit_type'].value_counts(normalize=True).to_dict() if len(t_is) > 0 else {}
    return {**combo,
            'is_n':m_is['n'],'is_pf':m_is['pf'],'is_wr':m_is['wr'],
            'is_dd':m_is['dd_pct'],'is_ann':m_is['ann_pct'],'is_pnl':m_is['pnl'],
            'oos_n':m_oos['n'],'oos_pf':m_oos['pf'],'oos_wr':m_oos['wr'],
            'oos_dd':m_oos['dd_pct'],'oos_ann':m_oos['ann_pct'],'oos_pnl':m_oos['pnl'],
            'time_pct':round(exits.get('TIME',0)*100,1),
            'wf_ratio':round(m_oos['pf']/m_is['pf'],3) if m_is['pf']>0 else 0}

def main():
    print("="*60)
    print("  Ranger C AUDNZD Stoch RESTRICTIVO")
    print("  Grid DeepSeek 6 sombreros 2026-05-21")
    print("  StochMode=2 / TrailDist=8 / RSI_L=40 / RSI_S=60 (FIJOS)")
    print("  Varia: MinSL [20,25] x ExitBars [16,20] x ADX [20,25] = 8 combos")
    print("="*60)
    df_raw = pd.read_csv(CACHE, index_col=0, parse_dates=True)
    df_is  = df_raw[df_raw.index <= IS_END].copy()
    df_oos = df_raw[df_raw.index >= OOS_START].copy()

    print("  Calculando indicadores (1 vez)...")
    df_is  = add_indicators(df_is,  FIXED_IND)
    df_oos = add_indicators(df_oos, FIXED_IND)
    print(f"  IS: {len(df_is):,} barras | OOS: {len(df_oos):,} barras")

    keys   = list(GRID.keys())
    combos = [dict(zip(keys,v)) for v in itertools.product(*GRID.values())]
    n_proc = min(8, mp.cpu_count())
    print(f"  Grid: {len(combos)} combos | procesos: {n_proc}")

    t0  = time.time()
    ctx = mp.get_context('spawn')
    with ctx.Pool(processes=n_proc,
                  initializer=_pool_init, initargs=(df_is, df_oos)) as pool:
        results = pool.map(_worker, combos, chunksize=1)
    results = [r for r in results if r is not None]
    print(f"  Completado: {len(results)}/{len(combos)} validos en {time.time()-t0:.0f}s")
    if not results: return

    df_res = pd.DataFrame(results)
    # Score multi-objetivo adaptado (sin MC, ese se valida a posteriori)
    # Pondera PF OOS, penaliza DD OOS, premia WF
    df_res['score'] = (
        df_res['oos_pf'] * 0.5
        + (1 - df_res['oos_dd'].clip(upper=20) / 20) * 0.3
        + df_res['wf_ratio'].clip(upper=2) * 0.2
    )
    df_res = df_res.sort_values('score', ascending=False)

    out = os.path.join(os.path.dirname(__file__), "..", "reports",
                       "Ranger_C_AUDNZD_Stoch_Restrictivo_Opt_Results.csv")
    df_res.to_csv(out, index=False)

    # Filtros post-opt segun DeepSeek
    df_ok = df_res[
        (df_res['oos_dd'] <= 6.0)
        & (df_res['oos_pf'] >= 1.10)
        & (df_res['wf_ratio'] >= 1.0)
    ]

    print(f"\n  CSV completo: {out}")
    print(f"\n  TOP 8 (todos, ordenados por score):")
    cols = ['MinSLPips','ExitBars','ADX_H4_Max',
            'is_n','is_pf','is_dd','oos_n','oos_pf','oos_dd','oos_ann','wf_ratio','score']
    print(df_res[cols].to_string(index=False))

    print(f"\n  PASAN FILTROS (OOS_DD<=6%, OOS_PF>=1.10, WF>=1.0): {len(df_ok)}")
    if len(df_ok):
        b = df_ok.iloc[0]
        print(f"\n  MEJOR CANDIDATO: MinSL={b['MinSLPips']} Exit={b['ExitBars']} ADX<{b['ADX_H4_Max']}")
        print(f"  IS  PF:{b['is_pf']} WR:{b['is_wr']}% DD:{b['is_dd']}% Ann:{b['is_ann']}% N:{b['is_n']}")
        print(f"  OOS PF:{b['oos_pf']} WR:{b['oos_wr']}% DD:{b['oos_dd']}% Ann:{b['oos_ann']}% N:{b['oos_n']} WF:{b['wf_ratio']}")
        print(f"\n  SIGUIENTE PASO: validar MC + year-by-year sobre este combo.")
    else:
        print("\n  Sin combos que pasen los filtros. Caer a grid normal + sizing reducido.")

if __name__ == "__main__":
    mp.freeze_support()
    main()
