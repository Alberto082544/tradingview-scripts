"""
Conecta a MT5, descarga XAUUSD M15 de los ultimos N anios y analiza:
- Rangos absolutos por anio (% del precio + USD absoluto + pips XAU)
- Rangos de la sesion NY (13:30-14:30 GMT, primera hora)
- Distribucion de rangos para calibrar filtro ORB

Output: tabla por anio + percentiles + recomendacion de filtro
"""
import os
import sys
import warnings

warnings.filterwarnings("ignore")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

try:
    import MetaTrader5 as mt5
except ImportError:
    print("MetaTrader5 no instalado: pip install MetaTrader5")
    sys.exit(1)

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "reports")
os.makedirs(OUT_DIR, exist_ok=True)


def main():
    print("=" * 70)
    print("  XAUUSD M15 - Analisis de rangos de apertura NY por anio")
    print("=" * 70)

    # Probar conexion a terminales reales del usuario por path
    terminals = [
        r"C:\Program Files\FundedNext MT5 Terminal\terminal64.exe",
        r"C:\Program Files\Capital Point Trading MT5 Terminal\terminal64.exe",
        r"C:\Program Files\Five Percent Online MT5 Terminal\terminal64.exe",
    ]
    connected = False
    for path in terminals:
        if not os.path.exists(path):
            continue
        if mt5.initialize(path=path):
            info = mt5.account_info()
            if info is not None:
                print(f"  Conectado a cuenta {info.login} ({info.server}) via {os.path.basename(os.path.dirname(path))}")
                connected = True
                break
            mt5.shutdown()
    if not connected:
        # Fallback: cualquier terminal abierto
        if not mt5.initialize():
            print(f"  [X] No se pudo conectar a MT5: {mt5.last_error()}")
            print("  Asegurate de que un terminal MT5 (FundedNext o The 5%ers) esta abierto.")
            return
        info = mt5.account_info()
        if info is None:
            print("  [!] No hay cuenta autenticada en el terminal abierto.")
            mt5.shutdown()
            return
        print(f"  (fallback) Conectado a cuenta {info.login} ({info.server})")

    # Listar todos los simbolos con XAU o GOLD
    all_syms = mt5.symbols_get()
    xau_syms = [s.name for s in all_syms if "XAU" in s.name.upper() or "GOLD" in s.name.upper()]
    print(f"  Simbolos con XAU/GOLD encontrados: {xau_syms[:10]}")

    sym = None
    for cand in xau_syms:
        if mt5.symbol_select(cand, True):
            info_s = mt5.symbol_info(cand)
            if info_s is not None and info_s.point > 0:
                sym = cand
                break
    if sym is None:
        print("  [X] No se encontro simbolo XAU operable en este broker")
        mt5.shutdown()
        return
    info_s = mt5.symbol_info(sym)
    print(f"  Usando simbolo: {sym} | Point: {info_s.point} | Digits: {info_s.digits}")
    pip = info_s.point * 10  # XAU pip = $0.10 (point=$0.01)
    print(f"  pip XAU = {pip}  (1 pip = ${pip})")

    # Probar copy_rates_from_pos (mas robusto que rates_range)
    print(f"  Descargando ultimas 100,000 barras M15 (~3 anios)...")
    rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M15, 0, 100000)
    if rates is None or len(rates) == 0:
        # fallback con rates_range
        utc_to = datetime.now()
        utc_from = utc_to - timedelta(days=365 * 3)
        print(f"  Fallback: rates_range desde {utc_from.date()}...")
        rates = mt5.copy_rates_range(sym, mt5.TIMEFRAME_M15, utc_from, utc_to)
    mt5.shutdown()

    if rates is None or len(rates) == 0:
        print("  [X] No se obtuvieron barras")
        return

    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df = df.set_index("time")
    print(f"  {len(df):,} barras M15 desde {df.index[0]} hasta {df.index[-1]}")

    # Calcular rango de la barra ORB de NY (13:30 GMT = primera vela M15 13:30-13:45)
    df["hour"] = df.index.hour
    df["minute"] = df.index.minute
    df["year"] = df.index.year

    # Considerar la vela cuyo inicio es 13:30 (rango ORB inicial)
    orb_bars = df[(df["hour"] == 13) & (df["minute"] == 30)].copy()
    orb_bars["range_usd"] = orb_bars["high"] - orb_bars["low"]
    orb_bars["range_pips"] = orb_bars["range_usd"] / pip
    orb_bars["range_pct"] = 100 * orb_bars["range_usd"] / orb_bars["close"]

    # Resumen por anio
    print("\n  RANGO BARRA ORB NY (13:30 GMT) — Estadisticas por anio")
    print(f"  {'Anio':<6} {'N':>5} {'Avg $':>8} {'Med $':>8} {'P25 $':>8} {'P75 $':>8} {'P95 $':>8} {'Avg p':>8} {'Avg %':>6}")
    summary_rows = []
    for year, grp in orb_bars.groupby("year"):
        r = grp["range_usd"]
        rp = grp["range_pips"]
        rpct = grp["range_pct"]
        row = {
            "year": int(year),
            "n_bars": int(len(grp)),
            "avg_usd": float(r.mean()),
            "med_usd": float(r.median()),
            "p25_usd": float(r.quantile(0.25)),
            "p75_usd": float(r.quantile(0.75)),
            "p95_usd": float(r.quantile(0.95)),
            "avg_pips": float(rp.mean()),
            "avg_pct_price": float(rpct.mean()),
            "avg_close": float(grp["close"].mean()),
        }
        summary_rows.append(row)
        print(f"  {row['year']:<6} {row['n_bars']:>5} ${row['avg_usd']:>6.2f} ${row['med_usd']:>6.2f}"
              f" ${row['p25_usd']:>6.2f} ${row['p75_usd']:>6.2f} ${row['p95_usd']:>6.2f}"
              f" {row['avg_pips']:>7.1f} {row['avg_pct_price']:>5.2f}%")

    df_summary = pd.DataFrame(summary_rows)
    df_summary.to_csv(os.path.join(OUT_DIR, "XAUUSD_orb_ranges_by_year.csv"), index=False)

    # Recomendacion de filtro
    p10_all = orb_bars["range_pips"].quantile(0.10)
    p90_all = orb_bars["range_pips"].quantile(0.90)
    p10_recent = orb_bars[orb_bars["year"] >= 2024]["range_pips"].quantile(0.10)
    p90_recent = orb_bars[orb_bars["year"] >= 2024]["range_pips"].quantile(0.90)

    print("\n  PERCENTILES DE RANGO (pips XAU)")
    print(f"  Todo periodo: P10={p10_all:.0f}p  P90={p90_all:.0f}p")
    print(f"  2024-2025:    P10={p10_recent:.0f}p  P90={p90_recent:.0f}p")

    print("\n  RECOMENDACION DE FILTRO ABSOLUTO (descartar 10% extremos cada lado)")
    print(f"  Periodo completo: [{int(p10_all)}, {int(p90_all)}] pips")
    print(f"  Solo 2024-2025:   [{int(p10_recent)}, {int(p90_recent)}] pips  (mas pertinente para operar HOY)")

    # Trades reales con filtro [40, 150] vs nuevo
    n_total = len(orb_bars)
    n_actual = ((orb_bars["range_pips"] >= 40) & (orb_bars["range_pips"] <= 150)).sum()
    n_recom = ((orb_bars["range_pips"] >= p10_recent) & (orb_bars["range_pips"] <= p90_recent)).sum()
    print(f"\n  COBERTURA del filtro:")
    print(f"  [40, 150] (EA actual):       {n_actual}/{n_total} ({100*n_actual/n_total:.1f}%)")
    print(f"  [{int(p10_recent)}, {int(p90_recent)}] (recomendado): {n_recom}/{n_total} ({100*n_recom/n_total:.1f}%)")

    print(f"\n  [OK] Output: {os.path.join(OUT_DIR, 'XAUUSD_orb_ranges_by_year.csv')}")


if __name__ == "__main__":
    main()
