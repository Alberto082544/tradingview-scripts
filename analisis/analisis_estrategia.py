import warnings
warnings.filterwarnings("ignore")

import yfinance as yf
import pandas as pd
import numpy as np
import quantstats as qs
import os

# --- CONFIGURACION ---
SIMBOLO    = "^GSPC"   # SP500
INICIO     = "2019-01-01"
FIN        = "2026-05-01"
CAPITAL    = 10000
RIESGO_PCT = 0.10      # 10% equity por operacion
ATR_MULT   = 2.0       # multiplicador SL
RR         = 2.0       # ratio riesgo/recompensa

print("Descargando datos SP500...")
df = yf.download(SIMBOLO, start=INICIO, end=FIN, interval="1d", auto_adjust=True, progress=False)
if isinstance(df.columns, pd.MultiIndex):
    df.columns = df.columns.droplevel(1)
df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
print(f"Datos: {len(df)} velas desde {df.index[0].date()} hasta {df.index[-1].date()}")

# --- INDICADORES ---
def ema(series, n):
    return series.ewm(span=n, adjust=False).mean()

def atr(df, n=14):
    hl  = df["High"] - df["Low"]
    hc  = (df["High"] - df["Close"].shift()).abs()
    lc  = (df["Low"]  - df["Close"].shift()).abs()
    tr  = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    return tr.ewm(span=n, adjust=False).mean()

def macd(close, fast=12, slow=26, signal=9):
    macd_line   = ema(close, fast) - ema(close, slow)
    signal_line = ema(macd_line, signal)
    return macd_line, signal_line

def adx(df, n=14):
    up   = df["High"].diff()
    down = -df["Low"].diff()
    dm_p = np.where((up > down) & (up > 0), up, 0)
    dm_m = np.where((down > up) & (down > 0), down, 0)
    tr_s = atr(df, n) * n
    di_p = 100 * pd.Series(dm_p, index=df.index).ewm(span=n, adjust=False).mean() / (tr_s / n)
    di_m = 100 * pd.Series(dm_m, index=df.index).ewm(span=n, adjust=False).mean() / (tr_s / n)
    dx   = (100 * (di_p - di_m).abs() / (di_p + di_m).replace(0, np.nan))
    return dx.ewm(span=n, adjust=False).mean()

df["ema9"]   = ema(df["Close"], 9)
df["ema21"]  = ema(df["Close"], 21)
df["ema200"] = ema(df["Close"], 200)
df["atr"]    = atr(df).shift(1)   # barra anterior (sin lookahead)
df["macd"], df["signal_macd"] = macd(df["Close"])
df["adx"]    = adx(df)

df.index = pd.to_datetime(df.index, utc=True)

# --- SEÑALES (diario — sin filtro de sesion, aplica toda la jornada) ---
cross_up  = (df["ema9"] > df["ema21"]) & (df["ema9"].shift() <= df["ema21"].shift())
trend_up  = df["Close"] > df["ema200"]
macd_up   = df["macd"] > df["signal_macd"]
adx_ok    = df["adx"] > 20

df["compra"] = cross_up & trend_up & macd_up & adx_ok
df = df.dropna()

# --- BACKTEST ---
equity    = CAPITAL
trades    = []
en_trade  = False
entry_px  = sl = tp = 0.0

for i in range(len(df)):
    row = df.iloc[i]

    if en_trade:
        px = row["Close"]
        if px <= sl:
            pnl = sl - entry_px
            trades.append({"fecha": df.index[i], "pnl": pnl, "tipo": "SL"})
            equity += equity * RIESGO_PCT * (pnl / (entry_px - sl))
            en_trade = False
        elif px >= tp:
            pnl = tp - entry_px
            trades.append({"fecha": df.index[i], "pnl": pnl, "tipo": "TP"})
            equity += equity * RIESGO_PCT * (pnl / (entry_px - sl))
            en_trade = False

    if not en_trade and row["compra"]:
        entry_px  = row["Close"]
        sl        = entry_px - row["atr"] * ATR_MULT
        tp        = entry_px + row["atr"] * ATR_MULT * RR
        en_trade  = True

# --- RESULTADOS ---
df_trades = pd.DataFrame(trades)
total     = len(df_trades)
ganadoras = (df_trades["pnl"] > 0).sum() if total > 0 else 0
win_rate  = ganadoras / total * 100 if total > 0 else 0
avg_win   = df_trades[df_trades["pnl"] > 0]["pnl"].mean() if ganadoras > 0 else 0
avg_loss  = df_trades[df_trades["pnl"] < 0]["pnl"].mean() if (total - ganadoras) > 0 else 0
factor    = abs(avg_win * ganadoras) / abs(avg_loss * (total - ganadoras)) if avg_loss != 0 else 0
meses     = (df.index[-1] - df.index[0]).days / 30.44
ops_mes   = total / meses

print(f"\n{'='*45}")
print(f"  ANALISIS ESTRATEGIA v3 — SP500 Diario")
print(f"{'='*45}")
print(f"  Periodo        : {df.index[0].date()} - {df.index[-1].date()}")
print(f"  Capital inicial: ${CAPITAL:,.0f}")
print(f"  Capital final  : ${equity:,.0f}")
print(f"  Rentabilidad   : {(equity/CAPITAL - 1)*100:.1f}%")
print(f"  Total trades   : {total}")
print(f"  Trades/mes     : {ops_mes:.1f}")
print(f"  Win rate       : {win_rate:.1f}%")
print(f"  Factor ganancia: {factor:.3f}")
print(f"  Avg win        : {avg_win:.2f} pts")
print(f"  Avg loss       : {avg_loss:.2f} pts")
print(f"{'='*45}")

# --- CURVA DE EQUITY PARA QUANTSTATS ---
df_trades["fecha"] = pd.to_datetime(df_trades["fecha"], utc=True)
df_trades = df_trades.set_index("fecha").sort_index()

# Retornos diarios de la estrategia
equity_serie = CAPITAL
retornos = []
fechas   = []
cap_actual = CAPITAL

for _, row in df_trades.iterrows():
    ret = RIESGO_PCT * (row["pnl"] / abs(avg_loss)) if avg_loss != 0 else 0
    cap_actual *= (1 + ret)
    retornos.append(ret)
    fechas.append(row.name)

returns_series = pd.Series(retornos, index=pd.DatetimeIndex(fechas))
returns_series.index = returns_series.index.normalize().tz_localize(None)
returns_series = returns_series.groupby(level=0).sum()

# --- REPORTE QUANTSTATS ---
output_path = r"C:\Users\alber\tradingview-scripts\analisis\reporte_sp500.html"
os.makedirs(os.path.dirname(output_path), exist_ok=True)

benchmark = yf.download("^GSPC", start=INICIO, end=FIN, progress=False)["Close"]
if isinstance(benchmark, pd.DataFrame):
    benchmark = benchmark.iloc[:, 0]
benchmark = benchmark.squeeze()
bench_returns = benchmark.pct_change().dropna()
bench_returns.index = pd.to_datetime(bench_returns.index).tz_localize(None).normalize()

qs.reports.html(
    returns_series,
    benchmark=bench_returns,
    title="EMA+MACD v3 - SP500",
    output=output_path
)
print(f"\nReporte HTML generado en:\n{output_path}")
print("Abrelo en tu navegador para ver el analisis completo.")
