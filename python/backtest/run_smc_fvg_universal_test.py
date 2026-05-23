"""
Backtest del SMC FVG UNIVERSAL — versión ATR-relative.

Foco: probar si la nueva versión genera trades en oro e índices
(donde la versión original con thresholds en pips fijos NO operaba).

Ejecutar:
    python -X utf8 -m backtest.run_smc_fvg_universal_test
"""
import os
import sys
import time
import warnings
from pathlib import Path
import pandas as pd

warnings.simplefilter("ignore")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from strategies.smc_fvg_universal import run_backtest, compute_metrics, DEFAULT_PARAMS

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
INIT_CASH = 15000

# (nombre, archivo, columna_fecha, point_value USD/punto/lote, fvg_tf_recomendado)
ASSETS = [
    # Forex
    ('EURUSD', 'EURUSD_M15_histdata.csv', 'time',     10.0, 'H1'),
    ('GBPUSD', 'GBPUSD_M15_histdata.csv', 'time',     10.0, 'H1'),
    ('EURGBP', 'EURGBP_M15_histdata.csv', 'time',     12.5, 'H1'),
    ('AUDCAD', 'AUDCAD_M15_histdata.csv', 'time',      7.0, 'H1'),
    ('AUDNZD', 'AUDNZD_M15_histdata.csv', 'time',      6.0, 'H1'),
    ('GBPJPY', 'GBPJPY_M15_dukas.csv',    'datetime',  6.7, 'M30'),
    # Oro: precio ~2000-3000, point_value típico 1 USD por 1 punto × 0.01 lote = 1 USD por punto-mini-lote
    ('XAUUSD', 'XAUUSD_M15_mt5.csv',      'time',      1.0, 'M30'),
    # Índices proxy: ETF (precio ~500), point_value 1 USD/punto/lote
    ('NAS100', 'NAS100_proxy_M15_twelvedata.csv', 'time', 1.0, 'M30'),
    ('SP500',  'SP500_proxy_M15_twelvedata.csv',  'time', 1.0, 'M30'),
    # CFD índices (precio real): point_value ~1 USD/punto/lote
    ('US500',  'US500_M15_mt5.csv',  'time', 1.0, 'M30'),
    ('UK100',  'UK100_M15_mt5.csv',  'time', 1.0, 'M30'),
]


def load(filename, col, start='2018-01-01'):
    path = DATA_DIR / filename
    if not path.exists(): return None
    df = pd.read_csv(path, parse_dates=[col]).set_index(col)
    return df[df.index >= start]


def main():
    print("=" * 90)
    print("  SMC FVG UNIVERSAL — Test multi-activo con thresholds ATR-relative")
    print(f"  Capital {INIT_CASH} | TrendBars=2 | ImpulseMinATR=0.3 | MaxSLATR=5.0")
    print("=" * 90)

    results = []
    for name, fname, col, pv, fvg_tf in ASSETS:
        print(f"\n[{name}] cargando...")
        df = load(fname, col)
        if df is None or len(df) < 3000:
            print(f"  Insuficientes datos")
            continue
        period = f"{df.index[0].date()} → {df.index[-1].date()}"
        print(f"  {len(df):,} filas | {period}")

        params = dict(DEFAULT_PARAMS)
        params['FVG_TF'] = fvg_tf

        t0 = time.time()
        try:
            trades = run_backtest(df, params=params, initial_capital=INIT_CASH, point_value=pv)
        except Exception as e:
            print(f"  ERROR: {e}")
            continue
        elapsed = time.time() - t0
        m = compute_metrics(trades, initial_capital=INIT_CASH)
        print(f"  {elapsed:.0f}s  trades={m['n']}  PF={m['pf']}  DD={m['dd_pct']}%  "
              f"PnL={m['pnl']} USD  Ann={m['ann_pct']}%  WR={m['wr']}%")

        results.append({
            'Activo': name, 'FVG_TF': fvg_tf, 'point_val': pv,
            'N_trades': m['n'], 'PF': m['pf'], 'DD%': m['dd_pct'],
            'NetPnL': m['pnl'], 'Annual%': m['ann_pct'], 'WR%': m['wr'],
            'Periodo': period, 'Tiempo_s': round(elapsed, 1),
        })

    print("\n" + "=" * 90)
    print("  RESUMEN (orden por PF desc)")
    print("=" * 90)
    if results:
        df_r = pd.DataFrame(results).sort_values('PF', ascending=False)
        print(df_r.to_string(index=False))
        out = Path(__file__).resolve().parents[1] / "vectorbt_bridge" / "output" / "smc_fvg_universal_test.csv"
        df_r.to_csv(out, index=False)
        print(f"\nGuardado: {out}")

        cand = df_r[(df_r['PF'] > 1.1) & (df_r['N_trades'] >= 30)]
        print(f"\n  CANDIDATOS (PF>1.1, N>=30): {len(cand)}")
        if len(cand) > 0:
            print(cand.to_string(index=False))


if __name__ == '__main__':
    main()
