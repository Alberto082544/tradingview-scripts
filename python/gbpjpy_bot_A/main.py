"""
GBPJPY Bot — Estrategia Balanceada
===================================
Pullback en tendencia GBPJPY M15 + filtro EMA200 H4
TP=3xSL | BE=0.8xSL | Session 07-19 UTC | SL max 30 pips

Uso:
  1. Edita DATA_PATH en config.py
  2. Ejecuta: python main.py

Version: 1.0 | 2026-05-08
"""
import os, sys, pandas as pd
from datetime import datetime

try:
    from config import DATA_PATH, START_YEAR, START_MONTH, END_YEAR, END_MONTH
    from strategy import add_indicators, generate_signals
    from backtest import run_backtest, print_results
except ImportError as e:
    print(f"Error: {e}"); sys.exit(1)

BANNER = """
╔══════════════════════════════════════════════════════════════╗
║         GBPJPY Bot — Estrategia Balanceada                  ║
║         Pullback + EMA200 H4 | M15 | TP=3xSL               ║
╚══════════════════════════════════════════════════════════════╝
"""

def load_data():
    if not os.path.exists(DATA_PATH):
        print(f"\n ERROR: No se encuentra el archivo:\n  {DATA_PATH}")
        print(" Edita DATA_PATH en config.py"); sys.exit(1)
    print(f"  Cargando: {os.path.basename(DATA_PATH)}")
    df_m1 = pd.read_csv(DATA_PATH, header=None,
        names=["date","time","open","high","low","close","volume","v2","sp"],
        dtype={"date":str,"time":str})
    df_m1["datetime"] = pd.to_datetime(df_m1["date"]+" "+df_m1["time"], format="%Y.%m.%d %H:%M")
    df_m1.set_index("datetime", inplace=True)
    df_m1 = df_m1[["open","high","low","close","volume"]]
    df_m1 = df_m1[(df_m1.index >= datetime(START_YEAR,START_MONTH,1)) &
                  (df_m1.index <= datetime(END_YEAR,END_MONTH,31))]
    df_m15 = df_m1.resample("15min").agg({"open":"first","high":"max","low":"min","close":"last","volume":"sum"}).dropna()
    df_h4  = df_m1.resample("4h").agg({"open":"first","high":"max","low":"min","close":"last","volume":"sum"}).dropna()
    print(f"  M15: {len(df_m15):,} barras | H4: {len(df_h4):,} barras")
    print(f"  Periodo: {df_m15.index[0].date()} -> {df_m15.index[-1].date()}")
    return df_m15, df_h4

def main():
    print(BANNER)
    print("[ 1/4 ] Cargando datos...")
    df_m15, df_h4 = load_data()
    print("\n[ 2/4 ] Calculando indicadores...")
    df = add_indicators(df_m15.copy(), df_h4.copy())
    print("\n[ 3/4 ] Generando señales...")
    df = generate_signals(df)
    print(f"  Long: {int(df['long_signal'].sum()):,}  |  Short: {int(df['short_signal'].sum()):,}")
    print("\n[ 4/4 ] Ejecutando backtest...")
    trades = run_backtest(df)
    print_results(trades)
    if len(trades) > 0:
        os.makedirs("reports", exist_ok=True)
        path = "reports/trades_gbpjpy_balanceada.csv"
        trades.to_csv(path, index=False)
        print(f"\n  Trades guardados: {path}")
    input("\nPresiona ENTER para salir...")

if __name__ == "__main__":
    main()
