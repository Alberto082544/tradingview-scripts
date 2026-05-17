"""
Convierte GBPJPY_M30_dukas.csv (Dukascopy) al formato txt que lee el script MQL5.
Salida: MQL5\Files\GBPJPY_DK.txt  → DATE\tTIME\tOPEN\tHIGH\tLOW\tCLOSE\tVOL
"""
import csv
from pathlib import Path
from datetime import datetime, timezone

SRC = Path(__file__).parent / "data" / "GBPJPY_M30_dukas.csv"
DST = Path(r"C:\Users\alber\AppData\Roaming\MetaQuotes\Terminal"
           r"\4AD3E132EC87A9BCE70CE370D3B528A0\MQL5\Files\GBPJPY_DK.txt")

def main():
    rows = []
    with open(SRC, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            dt = datetime.strptime(row["datetime"], "%Y-%m-%d %H:%M:%S")
            # Saltar velas de fin de semana (vol=0 o precio flat)
            if float(row["volume"]) == 0:
                continue
            rows.append(
                f"{dt.strftime('%Y.%m.%d')}\t{dt.strftime('%H:%M')}\t"
                f"{row['open']}\t{row['high']}\t{row['low']}\t{row['close']}\t"
                f"{row['volume']}"
            )

    DST.parent.mkdir(parents=True, exist_ok=True)
    with open(DST, "w") as f:
        f.write("\n".join(rows))

    print(f"Escrito: {len(rows):,} barras -> {DST}")

if __name__ == "__main__":
    main()
