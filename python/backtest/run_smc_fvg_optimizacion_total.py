"""
OPTIMIZACIÓN TOTAL SMC FVG Universal — secuencial por activo.

Proceso por cada activo:
1. **TF FVG**: probar M15, M30, H1 → quedarse con el mejor
2. **UseSession**: con/sin filtro sesión 7-21 GMT
3. **UseH1Trend**: con/sin confirmación H1 (además de H4)
4. **UsePatternC**: con/sin patrón fallback laxo
5. **SL_ATR_Mult**: 0.5, 1.0, 1.5, 2.0
6. **TP_RR**: 2.0, 3.0, 4.0

Al final, mejor config por activo + candidatos validados.

Ejecutar:
    python -X utf8 -m backtest.run_smc_fvg_optimizacion_total
"""
import os
import sys
import time
import warnings
from pathlib import Path
from copy import deepcopy
import pandas as pd

warnings.simplefilter("ignore")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from strategies.smc_fvg_universal import run_backtest, compute_metrics, DEFAULT_PARAMS

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
INIT_CASH = 15000

# Activos con datos suficientes (>30000 barras M15)
ASSETS = [
    ('EURUSD', 'EURUSD_M15_histdata.csv', 'time',     10.0),
    ('GBPUSD', 'GBPUSD_M15_histdata.csv', 'time',     10.0),
    ('EURGBP', 'EURGBP_M15_histdata.csv', 'time',     12.5),
    ('AUDCAD', 'AUDCAD_M15_histdata.csv', 'time',      7.0),
    ('AUDNZD', 'AUDNZD_M15_histdata.csv', 'time',      6.0),
    ('GBPJPY', 'GBPJPY_M15_dukas.csv',    'datetime',  6.7),
    ('NAS100', 'NAS100_proxy_M15_twelvedata.csv', 'time', 1.0),
    ('SP500',  'SP500_proxy_M15_twelvedata.csv',  'time', 1.0),
    ('US500',  'US500_M15_mt5.csv',  'time', 1.0),
    ('UK100',  'UK100_M15_mt5.csv',  'time', 1.0),
]


def load(filename, col):
    path = DATA_DIR / filename
    if not path.exists(): return None
    df = pd.read_csv(path, parse_dates=[col]).set_index(col)
    return df[df.index >= '2018-01-01']


def test_combo(df, params, pv):
    try:
        trades = run_backtest(df, params=params, initial_capital=INIT_CASH, point_value=pv)
        return compute_metrics(trades, initial_capital=INIT_CASH)
    except Exception as e:
        return {'n': 0, 'pnl': 0, 'wr': 0, 'pf': 0, 'dd_pct': 0, 'ann_pct': 0, 'error': str(e)}


def optimize_asset(name, df, pv):
    print(f"\n{'='*75}")
    print(f"  OPTIMIZANDO {name}  ({len(df):,} filas)")
    print(f"{'='*75}")

    # Base config
    base = dict(DEFAULT_PARAMS)
    base['FVG_TF'] = 'H1'
    base['SL_ATR_Mult'] = 1.5
    base['TP_RR'] = 2.0
    base['UseSessionFilter'] = False
    base['UseH1Trend'] = False
    base['UsePatternC'] = True

    history = []

    def run(label, p):
        t0 = time.time()
        m = test_combo(df, p, pv)
        m['label'] = label
        m['params'] = {k: p.get(k) for k in ['FVG_TF', 'SL_ATR_Mult', 'TP_RR',
                                              'UseSessionFilter', 'UseH1Trend', 'UsePatternC']}
        m['time'] = round(time.time() - t0, 1)
        history.append(m)
        print(f"  [{label:20s}] N={m['n']:4d}  PF={m['pf']:.2f}  DD={m['dd_pct']:5.1f}%  "
              f"PnL={m['pnl']:6.0f}  WR={m['wr']:.0f}%  ({m['time']}s)")
        return m

    # === PASO 1: FVG_TF ===
    print(f"\n[PASO 1] FVG_TF (manteniendo defaults)")
    best_tf, best_m = None, None
    for tf in ['M15', 'M30', 'H1']:
        p = dict(base); p['FVG_TF'] = tf
        m = run(f"TF={tf}", p)
        if best_m is None or m['pf'] > best_m['pf']:
            best_tf = tf; best_m = m
    base['FVG_TF'] = best_tf
    print(f"  → Mejor TF: {best_tf} (PF {best_m['pf']})")

    # === PASO 2: UseSession ===
    print(f"\n[PASO 2] UseSession (con TF={best_tf})")
    base_off = dict(base); base_off['UseSessionFilter'] = False
    base_on = dict(base); base_on['UseSessionFilter'] = True
    m_off = run("Session=OFF", base_off)
    m_on = run("Session=ON", base_on)
    best_session = m_on['pf'] >= m_off['pf']
    base['UseSessionFilter'] = best_session
    print(f"  → Mejor Session: {'ON' if best_session else 'OFF'}")

    # === PASO 3: UseH1Trend ===
    print(f"\n[PASO 3] UseH1Trend")
    base_h1off = dict(base); base_h1off['UseH1Trend'] = False
    base_h1on = dict(base); base_h1on['UseH1Trend'] = True
    m_h1off = run("H1Trend=OFF", base_h1off)
    m_h1on = run("H1Trend=ON", base_h1on)
    best_h1 = m_h1on['pf'] >= m_h1off['pf']
    base['UseH1Trend'] = best_h1
    print(f"  → Mejor H1Trend: {'ON' if best_h1 else 'OFF'}")

    # === PASO 4: UsePatternC ===
    print(f"\n[PASO 4] UsePatternC")
    base_pc_on = dict(base); base_pc_on['UsePatternC'] = True
    base_pc_off = dict(base); base_pc_off['UsePatternC'] = False
    m_pc_on = run("PatternC=ON", base_pc_on)
    m_pc_off = run("PatternC=OFF", base_pc_off)
    best_pc = m_pc_on['pf'] >= m_pc_off['pf']
    base['UsePatternC'] = best_pc
    print(f"  → Mejor PatternC: {'ON' if best_pc else 'OFF'}")

    # === PASO 5: SL_ATR_Mult ===
    print(f"\n[PASO 5] SL_ATR_Mult")
    best_sl, best_m_sl = None, None
    for sl in [0.5, 1.0, 1.5, 2.0, 2.5]:
        p = dict(base); p['SL_ATR_Mult'] = sl
        m = run(f"SL_ATR={sl}", p)
        if best_m_sl is None or m['pf'] > best_m_sl['pf']:
            best_sl = sl; best_m_sl = m
    base['SL_ATR_Mult'] = best_sl
    print(f"  → Mejor SL_ATR: {best_sl}")

    # === PASO 6: TP_RR ===
    print(f"\n[PASO 6] TP_RR")
    best_rr, best_m_rr = None, None
    for rr in [1.5, 2.0, 2.5, 3.0, 4.0]:
        p = dict(base); p['TP_RR'] = rr
        m = run(f"TP_RR={rr}", p)
        if best_m_rr is None or m['pf'] > best_m_rr['pf']:
            best_rr = rr; best_m_rr = m
    base['TP_RR'] = best_rr
    print(f"  → Mejor TP_RR: {best_rr}")

    # Mejor combo final
    final = best_m_rr
    final['final_params'] = {
        'FVG_TF': base['FVG_TF'],
        'UseSessionFilter': base['UseSessionFilter'],
        'UseH1Trend': base['UseH1Trend'],
        'UsePatternC': base['UsePatternC'],
        'SL_ATR_Mult': base['SL_ATR_Mult'],
        'TP_RR': base['TP_RR'],
    }
    print(f"\n  🏆 MEJOR FINAL: PF={final['pf']} N={final['n']} DD={final['dd_pct']}% PnL={final['pnl']}")
    print(f"      Params: {final['final_params']}")
    return final, history


def main():
    print("=" * 80)
    print("  OPTIMIZACIÓN TOTAL SMC FVG Universal — secuencial por activo")
    print("=" * 80)

    all_results = []
    for name, fname, col, pv in ASSETS:
        df = load(fname, col)
        if df is None or len(df) < 10000:
            print(f"\n[{name}] datos insuficientes")
            continue
        final, history = optimize_asset(name, df, pv)
        all_results.append({
            'Activo': name, **final['final_params'],
            'N': final['n'], 'PF': final['pf'], 'DD%': final['dd_pct'],
            'PnL': final['pnl'], 'WR%': final['wr'], 'Ann%': final['ann_pct'],
        })

    print("\n" + "=" * 80)
    print("  RESUMEN GLOBAL — mejor config por activo")
    print("=" * 80)
    df_res = pd.DataFrame(all_results).sort_values('PF', ascending=False)
    print(df_res.to_string(index=False))

    out = Path(__file__).resolve().parents[1] / "vectorbt_bridge" / "output" / "smc_fvg_opt_total.csv"
    df_res.to_csv(out, index=False)
    print(f"\nGuardado: {out}")

    # Candidatos
    cand = df_res[(df_res['PF'] >= 1.2) & (df_res['N'] >= 50) & (df_res['DD%'] <= 15)]
    print(f"\n🎯 CANDIDATOS (PF≥1.2, N≥50, DD≤15%): {len(cand)}")
    if len(cand) > 0:
        print(cand.to_string(index=False))
    else:
        print("  Ninguno cumple los 3 criterios estrictos. Top 3 por PF para análisis:")
        print(df_res.head(3).to_string(index=False))


if __name__ == '__main__':
    main()
