"""
Backtest del SMC FVG (port Python) en 11 activos: forex + oro + índices.
Usa lógica del .mq5 v9.4 simplificada.

Ejecutar desde /python:
    python -X utf8 -m backtest.run_smc_fvg_multi_activo
"""
import os
import sys
import time
import warnings
from pathlib import Path
import pandas as pd

warnings.simplefilter("ignore")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from strategies.smc_fvg import run_backtest, compute_metrics, DEFAULT_PARAMS

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
INIT_CASH = 15000

# Cada activo: (file, time_col, pip_size, fvg_tf_recomendado, sl_atr_recomendado)
ASSETS = [
    # Forex majors / crosses
    ('EURUSD', 'EURUSD_M15_histdata.csv', 'time', 0.0001, 'H1', 1.5),
    ('GBPUSD', 'GBPUSD_M15_histdata.csv', 'time', 0.0001, 'H1', 1.5),
    ('EURGBP', 'EURGBP_M15_histdata.csv', 'time', 0.0001, 'H1', 1.5),
    ('AUDCAD', 'AUDCAD_M15_histdata.csv', 'time', 0.0001, 'H1', 1.5),
    ('AUDNZD', 'AUDNZD_M15_histdata.csv', 'time', 0.0001, 'H1', 1.5),
    ('GBPJPY', 'GBPJPY_M15_dukas.csv',    'datetime', 0.01, 'M30', 2.0),
    # Oro
    ('XAUUSD', 'XAUUSD_M15_mt5.csv',      'time', 0.1, 'M30', 2.0),
    # Índices
    ('NAS100', 'NAS100_proxy_M15_twelvedata.csv', 'time', 1.0, 'M30', 1.5),
    ('SP500',  'SP500_proxy_M15_twelvedata.csv',  'time', 1.0, 'M30', 1.5),
    ('US500',  'US500_M15_mt5.csv',               'time', 0.1, 'M30', 1.5),
    ('UK100',  'UK100_M15_mt5.csv',               'time', 1.0, 'M30', 1.5),
]


def load(filename, col, start='2018-01-01'):
    path = DATA_DIR / filename
    if not path.exists():
        return None
    df = pd.read_csv(path, parse_dates=[col]).set_index(col)
    df = df[df.index >= start]
    return df


def main():
    print("=" * 80)
    print("  SMC FVG — Backtest multi-activo (Python port)")
    print(f"  Capital: {INIT_CASH} USD | Riesgo 1%/trade | Sesion 7-21 GMT")
    print("=" * 80)

    results = []
    for name, fname, col, pip, fvg_tf, sl_mult in ASSETS:
        print(f"\n[{name}] cargando...")
        df = load(fname, col)
        if df is None or len(df) < 5000:
            print(f"  ❌ Datos insuficientes ({0 if df is None else len(df)} filas)")
            continue
        period = f"{df.index[0].date()} → {df.index[-1].date()}"
        print(f"  ✓ {len(df):,} filas | {period}")

        params = dict(DEFAULT_PARAMS)
        params['FVG_TF'] = fvg_tf
        params['SL_ATR_Mult'] = sl_mult
        # Relajar filtros para tener muestra estadística
        params['TrendBars'] = 1              # antes 3 (demasiado estricto)
        params['MaxFVG_Age_Hours'] = 168     # 1 semana (antes 72h)
        params['MaxM15Confirm'] = 48         # 12h (antes 3h)
        params['UseRSIFilter'] = False       # quitar filtro RSI
        params['UseEMAFilter'] = False       # quitar filtro EMA
        params['UseSessionFilter'] = False   # quitar filtro horario
        params['ImpulseMinPips'] = 4.0       # FVG más pequeños permitidos (antes 8)

        t0 = time.time()
        try:
            trades = run_backtest(df, params=params, initial_capital=INIT_CASH, pip=pip)
        except Exception as e:
            print(f"  ❌ Error: {e}")
            continue
        elapsed = time.time() - t0
        m = compute_metrics(trades, initial_capital=INIT_CASH)
        print(f"  Tiempo: {elapsed:.1f}s  |  trades={m['n']}  PF={m['pf']}  DD={m['dd_pct']}%  "
              f"PnL={m['pnl']} USD  Ann={m['ann_pct']}%  WR={m['wr']}%")
        results.append({
            'Activo': name, 'FVG_TF': fvg_tf, 'SL_ATR': sl_mult,
            'N_trades': m['n'], 'PF': m['pf'], 'DD%': m['dd_pct'],
            'NetPnL': m['pnl'], 'Annual%': m['ann_pct'], 'WR%': m['wr'],
            'Periodo': period, 'Tiempo_s': round(elapsed, 1),
        })

    print("\n" + "=" * 80)
    print("  RESUMEN COMPARATIVO")
    print("=" * 80)
    if results:
        df_res = pd.DataFrame(results).sort_values('PF', ascending=False)
        print(df_res.to_string(index=False))
        out = Path(__file__).resolve().parents[1] / "vectorbt_bridge" / "output" / "smc_fvg_multi_activo.csv"
        out.parent.mkdir(exist_ok=True)
        df_res.to_csv(out, index=False)
        print(f"\nGuardado: {out}")

        # Top candidatos: PF > 1, trades > 50
        cand = df_res[(df_res['PF'] > 1.0) & (df_res['N_trades'] > 50) & (df_res['DD%'] < 25)]
        print("\n" + "=" * 80)
        print(f"  CANDIDATOS VÁLIDOS (PF>1, N>50, DD<25%): {len(cand)}")
        print("=" * 80)
        if len(cand) > 0:
            print(cand.to_string(index=False))
        else:
            print("  Ninguno. Necesita ajuste de params o estrategia no funciona.")
    else:
        print("Sin resultados.")


if __name__ == '__main__':
    main()
