"""
Analisis de rangos XAUUSD ORB usando el CSV Dukascopy M1 original (2009-2026).
Agrega a M15 y calcula rangos de la barra ORB NY (13:30 GMT) por anio.

Objetivo: recalibrar el filtro [MinRangePips, MaxRangePips] del EA con datos reales.
"""
import os
import sys
import warnings

warnings.filterwarnings("ignore")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import pandas as pd
import numpy as np

CSV = r"C:\Users\alber\OneDrive\Desktop\DATOS_CSV\2026.5.8XAUUSD_M1_dukas-M1-No Session.csv"
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "reports")
PIP = 0.1  # XAU: 1 pip = $0.10

os.makedirs(OUT_DIR, exist_ok=True)


def main():
    print("=" * 70)
    print("  XAUUSD - Analisis de rangos ORB NY (datos Dukascopy 2009-2026)")
    print("=" * 70)

    if not os.path.exists(CSV):
        print(f"  [X] CSV no encontrado: {CSV}")
        return

    print(f"  Cargando CSV ({os.path.getsize(CSV) / 1e6:.0f} MB)...")
    df = pd.read_csv(CSV, dtype={
        "Date": str, "Time": str,
        "Open": np.float32, "High": np.float32, "Low": np.float32, "Close": np.float32,
        "Volume": np.int32,
    })
    df["datetime"] = pd.to_datetime(df["Date"] + " " + df["Time"], format="%Y%m%d %H:%M:%S")
    df = df.set_index("datetime").drop(columns=["Date", "Time"])
    print(f"  {len(df):,} barras M1 de {df.index[0]} a {df.index[-1]}")
    print(f"  Precio: min=${df['Low'].min():.0f}  max=${df['High'].max():.0f}")

    # Agregar a M15
    print("  Agregando a M15...")
    df15 = df.resample("15min").agg({
        "Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum",
    }).dropna()
    print(f"  {len(df15):,} barras M15")

    # Filtrar SOLO la barra ORB de NY: la que empieza a las 13:30 UTC
    df15 = df15.copy()
    df15["hour"] = df15.index.hour
    df15["minute"] = df15.index.minute
    df15["year"] = df15.index.year
    df15["dow"] = df15.index.dayofweek

    orb = df15[(df15["hour"] == 13) & (df15["minute"] == 30) & (df15["dow"] < 5)].copy()
    print(f"  {len(orb):,} velas ORB NY (13:30 GMT, L-V)")

    orb["range_usd"] = orb["High"] - orb["Low"]
    orb["range_pips"] = orb["range_usd"] / PIP
    orb["range_pct"] = 100 * orb["range_usd"] / orb["Close"]

    # Resumen por anio
    print("\n  RANGO BARRA ORB NY (13:30 GMT, 15 min) por anio")
    print(f"  {'Anio':<6} {'N':>4} {'Avg$':>7} {'Med$':>7} {'P10$':>7} {'P25$':>7} {'P75$':>7} {'P90$':>7}"
          f" {'AvgPips':>8} {'AvgPct':>7}")
    summary_rows = []
    for year, g in orb.groupby("year"):
        r = g["range_usd"]
        rp = g["range_pips"]
        rpct = g["range_pct"]
        avg_close = float(g["Close"].mean())
        row = {
            "year": int(year),
            "n_bars": int(len(g)),
            "avg_close": avg_close,
            "avg_usd": float(r.mean()),
            "med_usd": float(r.median()),
            "p10_usd": float(r.quantile(0.10)),
            "p25_usd": float(r.quantile(0.25)),
            "p75_usd": float(r.quantile(0.75)),
            "p90_usd": float(r.quantile(0.90)),
            "avg_pips": float(rp.mean()),
            "med_pips": float(rp.median()),
            "p10_pips": float(rp.quantile(0.10)),
            "p90_pips": float(rp.quantile(0.90)),
            "avg_pct_price": float(rpct.mean()),
            "med_pct_price": float(rpct.median()),
        }
        summary_rows.append(row)
        print(f"  {year:<6} {row['n_bars']:>4} {row['avg_usd']:>6.2f} {row['med_usd']:>6.2f}"
              f" {row['p10_usd']:>6.2f} {row['p25_usd']:>6.2f} {row['p75_usd']:>6.2f} {row['p90_usd']:>6.2f}"
              f" {row['avg_pips']:>7.1f} {row['avg_pct_price']:>6.3f}%")

    df_summary = pd.DataFrame(summary_rows)
    df_summary.to_csv(os.path.join(OUT_DIR, "XAUUSD_orb_ranges_by_year.csv"), index=False)

    # Recomendacion de filtro
    print("\n" + "=" * 70)
    print("  RECOMENDACION DE FILTRO ORB")
    print("=" * 70)

    actual_min, actual_max = 40, 150
    actual_cobertura = ((orb["range_pips"] >= actual_min) & (orb["range_pips"] <= actual_max)).mean() * 100
    print(f"  Filtro actual EA [{actual_min}, {actual_max}] pips: cobertura {actual_cobertura:.1f}% de las barras")

    # Periodo del backtest original (2020-2025 segun config_xauusd.py)
    bt_period = orb[(orb["year"] >= 2020) & (orb["year"] <= 2025)]
    bt_cob_actual = ((bt_period["range_pips"] >= actual_min) & (bt_period["range_pips"] <= actual_max)).mean() * 100
    print(f"  Cobertura del filtro actual en periodo backtest 2020-2025: {bt_cob_actual:.1f}%")

    # Periodo reciente
    recent = orb[orb["year"] >= 2024]
    p10r = recent["range_pips"].quantile(0.10)
    p90r = recent["range_pips"].quantile(0.90)
    p25r = recent["range_pips"].quantile(0.25)
    p75r = recent["range_pips"].quantile(0.75)
    print(f"\n  PERIODO RECIENTE 2024-2026 (mas pertinente para operar HOY):")
    print(f"  Percentiles rango pips: P10={p10r:.0f}  P25={p25r:.0f}  P75={p75r:.0f}  P90={p90r:.0f}")
    print(f"  Recomendado filtro absoluto: [{int(p10r)}, {int(p90r)}] pips  (= [${p10r*PIP:.1f}, ${p90r*PIP:.1f}])")

    # Filtro relativo
    median_pct = recent["range_pct"].median()
    p10_pct = recent["range_pct"].quantile(0.10)
    p90_pct = recent["range_pct"].quantile(0.90)
    print(f"\n  ALTERNATIVA: filtro RELATIVO al precio (mas robusto a evolucion XAU)")
    print(f"  Mediana rango = {median_pct:.3f}% del precio. P10={p10_pct:.3f}%  P90={p90_pct:.3f}%")
    print(f"  Filtro recomendado: rango entre {p10_pct:.3f}% y {p90_pct:.3f}% del precio actual")

    # Evolucion del rango promedio
    print(f"\n  EVOLUCION del rango medio en pips por anio:")
    yearly_avg_pips = orb.groupby("year")["range_pips"].mean()
    for year, avg in yearly_avg_pips.items():
        if year >= 2018:
            print(f"    {int(year)}: {avg:.0f} pips")

    print(f"\n  [OK] Output: {os.path.join(OUT_DIR, 'XAUUSD_orb_ranges_by_year.csv')}")


if __name__ == "__main__":
    main()
