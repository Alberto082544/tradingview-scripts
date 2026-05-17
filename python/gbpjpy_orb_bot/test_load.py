import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = sys.stdout

import pandas as pd
from datetime import datetime

csv_path = r"C:\Users\alber\OneDrive\Desktop\Nueva carpeta\2026.5.8XAUUSD_M1_dukas-M1-No Session.csv"

print("Loading XAUUSD CSV...")
df = pd.read_csv(csv_path, dtype={"Date": str, "Time": str})
print("Raw rows:", len(df))
print(df.head(3).to_string())

print("\nParsing datetime...")
df["datetime"] = pd.to_datetime(df["Date"] + " " + df["Time"], format="%Y%m%d %H:%M:%S")
df = df.rename(columns={"Open":"open","High":"high","Low":"low","Close":"close","Volume":"volume"})
df.set_index("datetime", inplace=True)
df = df[["open","high","low","close","volume"]]

print("Date range:", df.index[0], "->", df.index[-1])
print("Filtering 2020-2025...")
df = df[(df.index >= datetime(2020,1,1)) & (df.index <= datetime(2025,12,31))]
print("Filtered rows:", len(df))

print("Resampling to M15...")
df_m15 = df.resample("15min").agg({"open":"first","high":"max","low":"min","close":"last","volume":"sum"}).dropna()
print("M15 bars:", len(df_m15))
print(df_m15.head(3).to_string())
print("DONE")
