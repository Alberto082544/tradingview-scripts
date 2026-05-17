"""
GBPJPY Bot — Estrategia Maximo Rendimiento
==========================================
Pullback en tendencia GBPJPY M15 + filtro EMA200 H4
TP=5xSL | BE=1.5xSL | Session 07-18 UTC | SL max 30 pips

Uso:
  1. Edita DATA_PATH en config.py con la ruta a tu CSV Dukascopy
  2. Ejecuta: python main.py

Datos Dukascopy (gratis):
  https://www.dukascopy.com/trading-tools/widgets/tools/historical_data_feed/
  Selecciona GBPJPY, Bid candles, M1, formato CSV

Version: 2.0 | 2026-05-08
"""

import os
import sys
import pandas as pd
from datetime import datetime

# Importar módulos del bot
try:
    from config import DATA_PATH, START_YEAR, START_MONTH, END_YEAR, END_MONTH
    from strategy import add_indicators, generate_signals
    from backtest import run_backtest, print_results
except ImportError as e:
    print(f"Error al importar modulos: {e}")
    print("Asegurate de ejecutar desde la carpeta del bot.")
    sys.exit(1)


BANNER = """
╔══════════════════════════════════════════════════════════════╗
║         GBPJPY Bot — Estrategia Maximo Rendimiento          ║
║         Pullback + EMA200 H4 | M15 | TP=5xSL               ║
╚══════════════════════════════════════════════════════════════╝
"""


def load_data():
    """Carga el CSV Dukascopy y resamplea a M15 + H4."""
    if not os.path.exists(DATA_PATH):
        print(f"\n ERROR: No se encuentra el archivo de datos:")
        print(f"  {DATA_PATH}")
        print(f"\n Edita DATA_PATH en config.py con la ruta correcta.")
        print(f" Descarga los datos en: dukascopy.com/trading-tools/")
        sys.exit(1)

    print(f"  Cargando datos desde: {os.path.basename(DATA_PATH)}")
    df_m1 = pd.read_csv(
        DATA_PATH, header=None,
        names=["date","time","open","high","low","close","volume","v2","sp"],
        dtype={"date": str, "time": str},
    )
    df_m1["datetime"] = pd.to_datetime(df_m1["date"] + " " + df_m1["time"],
                                        format="%Y.%m.%d %H:%M")
    df_m1.set_index("datetime", inplace=True)
    df_m1 = df_m1[["open","high","low","close","volume"]]

    start = datetime(START_YEAR, START_MONTH, 1)
    end   = datetime(END_YEAR,   END_MONTH,   31)
    df_m1 = df_m1[(df_m1.index >= start) & (df_m1.index <= end)]

    df_m15 = df_m1.resample("15min").agg({"open":"first","high":"max",
                                           "low":"min","close":"last","volume":"sum"}).dropna()
    df_h4  = df_m1.resample("4h").agg({"open":"first","high":"max",
                                        "low":"min","close":"last","volume":"sum"}).dropna()

    print(f"  M15: {len(df_m15):,} barras  |  H4: {len(df_h4):,} barras")
    print(f"  Periodo: {df_m15.index[0].date()} → {df_m15.index[-1].date()}")
    return df_m15, df_h4


def save_results(trades: pd.DataFrame):
    """Guarda los trades en CSV."""
    os.makedirs("reports", exist_ok=True)
    path = "reports/trades_gbpjpy_maxrendimiento.csv"
    trades.to_csv(path, index=False)
    print(f"\n  Trades guardados en: {path}")


def main():
    print(BANNER)

    # 1. Cargar datos
    print("[ 1/4 ] Cargando datos...")
    df_m15, df_h4 = load_data()

    # 2. Calcular indicadores
    print("\n[ 2/4 ] Calculando indicadores...")
    df = add_indicators(df_m15.copy(), df_h4.copy())

    # 3. Generar señales
    print("\n[ 3/4 ] Generando señales...")
    df = generate_signals(df)
    longs  = int(df["long_signal"].sum())
    shorts = int(df["short_signal"].sum())
    print(f"  Señales generadas — Long: {longs:,}  |  Short: {shorts:,}")

    # 4. Ejecutar backtest
    print("\n[ 4/4 ] Ejecutando backtest...")
    trades = run_backtest(df)

    # Mostrar resultados
    print_results(trades)

    # Guardar CSV
    if len(trades) > 0:
        save_results(trades)

    input("\nPresiona ENTER para salir...")


if __name__ == "__main__":
    main()
