"""Descarga datos XAUUSD M15 frescos desde MT5 (FundedNext / The 5%ers / otros).

Si no consigue por MT5, sugiere alternativas.
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
    print("MetaTrader5 no instalado")
    sys.exit(1)

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
os.makedirs(OUT_DIR, exist_ok=True)


def intentar_terminal(path, label):
    print(f"\n  >>> Intentando {label}: {path}")
    if not os.path.exists(path):
        print(f"      [skip] no existe")
        return None
    if not mt5.initialize(path=path):
        print(f"      [X] no se pudo conectar: {mt5.last_error()}")
        return None
    info = mt5.account_info()
    if info is None:
        print(f"      [!] sin cuenta autenticada")
        mt5.shutdown()
        return None
    print(f"      Conectado: cuenta {info.login} ({info.server})")

    # Buscar simbolo XAU
    all_syms = mt5.symbols_get()
    xau_syms = [s.name for s in all_syms if "XAU" in s.name.upper() or "GOLD" in s.name.upper()]
    if not xau_syms:
        print(f"      [X] No hay simbolo XAU")
        mt5.shutdown()
        return None
    sym = xau_syms[0]
    if not mt5.symbol_select(sym, True):
        mt5.shutdown()
        return None
    info_s = mt5.symbol_info(sym)
    print(f"      Simbolo: {sym} | Point: {info_s.point}")

    # Probar metodos
    rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M15, 0, 200000)
    if rates is None or len(rates) == 0:
        print(f"      [X] copy_rates_from_pos vacio")
        utc_to = datetime.now()
        utc_from = utc_to - timedelta(days=180)
        rates = mt5.copy_rates_range(sym, mt5.TIMEFRAME_M15, utc_from, utc_to)
    mt5.shutdown()

    if rates is None or len(rates) == 0:
        print(f"      [X] sin barras (terminal sin cache del historico)")
        return None
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df = df.set_index("time")
    print(f"      OK: {len(df):,} barras desde {df.index[0]} hasta {df.index[-1]}")
    return df


def main():
    print("=" * 70)
    print("  XAUUSD - Descarga datos frescos M15")
    print("=" * 70)

    terminals = [
        (r"C:\Program Files\FundedNext MT5 Terminal\terminal64.exe", "FundedNext"),
        (r"C:\Program Files\Capital Point Trading MT5 Terminal\terminal64.exe", "The 5%ers (Capital Point)"),
        (r"C:\Program Files\Five Percent Online MT5 Terminal\terminal64.exe", "The 5%ers (Five Percent Online)"),
    ]

    df = None
    for path, label in terminals:
        result = intentar_terminal(path, label)
        if result is not None and len(result) > 0:
            df = result
            print(f"\n  GANADOR: {label} con {len(df):,} barras")
            break

    if df is None or len(df) == 0:
        print("\n  [X] Ningun terminal entrego datos M15 de XAUUSD.")
        print("  Causa probable: los terminales no han descargado el historico en su cache local.")
        print()
        print("  SOLUCION manual (1 vez):")
        print("  1. Abre MT5 (FundedNext o The 5%ers)")
        print("  2. Abre grafico XAUUSD M15")
        print("  3. Pulsa Home varias veces para que el cliente descargue historico atras")
        print("  4. Vuelve a ejecutar este script")
        return

    # Guardar
    out_csv = os.path.join(OUT_DIR, "XAUUSD_M15_mt5.csv")
    df.to_csv(out_csv)
    print(f"\n  Guardado: {out_csv}  ({os.path.getsize(out_csv) / 1e6:.1f} MB)")

    # Combinar con dataset Dukascopy historico si existe
    dukas = r"C:\Users\alber\OneDrive\Desktop\DATOS_CSV\2026.5.8XAUUSD_M1_dukas-M1-No Session.csv"
    if os.path.exists(dukas):
        print(f"\n  Hay dataset Dukascopy historico. ¿Combinarlo? (M1 agregado a M15)")
        print(f"  Por ahora dejo separados: MT5 reciente para validacion, Dukascopy para backtest largo.")


if __name__ == "__main__":
    main()
