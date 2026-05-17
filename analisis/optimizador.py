"""
OPTIMIZADOR DE ESTRATEGIA — EMA + MACD + ADX
Flujo: vectorbt (backtest rapido) + optuna (optimizacion robusta) + quantstats (reporte)
"""
import warnings
warnings.filterwarnings("ignore")
import os, sys

import numpy as np
import pandas as pd
import yfinance as yf
import vectorbt as vbt
import optuna
import quantstats as qs

optuna.logging.set_verbosity(optuna.logging.WARNING)

# ============================================================
# CONFIGURACION
# ============================================================
SIMBOLOS    = ["SPY", "QQQ", "DIA"]   # SP500, NAS100, DOW (ETFs con historia larga)
INICIO      = "2015-01-01"
FIN         = "2026-05-01"
INTERVALO   = "1d"                     # diario (maximo historia en yfinance gratis)
N_TRIALS    = 80                       # combinaciones que prueba optuna
CAPITAL     = 10000
OUTPUT_DIR  = r"C:\Users\alber\tradingview-scripts\analisis"

# ============================================================
# DESCARGA DE DATOS
# ============================================================
print("Descargando datos...")
raw = yf.download(SIMBOLOS, start=INICIO, end=FIN,
                  interval=INTERVALO, auto_adjust=True, progress=False)
closes = raw["Close"].dropna()
highs  = raw["High"].dropna()
lows   = raw["Low"].dropna()
print(f"OK: {len(closes)} dias | {closes.index[0].date()} - {closes.index[-1].date()}")

# ============================================================
# FUNCIONES DE INDICADORES
# ============================================================
def calc_ema(s, n):
    return s.ewm(span=n, adjust=False).mean()

def calc_atr(h, l, c, n=14):
    tr = pd.concat([h - l,
                    (h - c.shift()).abs(),
                    (l - c.shift()).abs()], axis=1).max(axis=1)
    return tr.ewm(span=n, adjust=False).mean()

def calc_macd(c, fast, slow, sig):
    m = calc_ema(c, fast) - calc_ema(c, slow)
    s = calc_ema(m, sig)
    return m, s

def calc_adx(h, l, c, n=14):
    up   = h.diff()
    down = -l.diff()
    dm_p = np.where((up > down) & (up > 0), up, 0.0)
    dm_m = np.where((down > up) & (down > 0), down, 0.0)
    atr_s = calc_atr(h, l, c, n)
    di_p  = 100 * pd.Series(dm_p, index=c.index).ewm(span=n, adjust=False).mean() / atr_s
    di_m  = 100 * pd.Series(dm_m, index=c.index).ewm(span=n, adjust=False).mean() / atr_s
    dx    = (100 * (di_p - di_m).abs() / (di_p + di_m).replace(0, np.nan))
    return dx.ewm(span=n, adjust=False).mean()

# ============================================================
# BACKTEST CON VECTORBT (rapido, para un simbolo)
# ============================================================
def backtest(simbolo, ema_r, ema_l, ema_t, adx_th, atr_mult):
    c = closes[simbolo].dropna()
    h = highs[simbolo].reindex(c.index)
    l = lows[simbolo].reindex(c.index)

    er  = calc_ema(c, ema_r)
    el  = calc_ema(c, ema_l)
    et  = calc_ema(c, ema_t)
    ml, sl = calc_macd(c, 12, 26, 9)
    adx = calc_adx(h, l, c, 14)
    atr = calc_atr(h, l, c, 14).shift(1)

    cross_up  = (er > el) & (er.shift() <= el.shift())
    trend_up  = c > et
    macd_up   = ml > sl
    adx_ok    = adx > adx_th

    entries = cross_up & trend_up & macd_up & adx_ok
    entries = entries.fillna(False)

    sl_pts = atr * atr_mult
    tp_pts = atr * atr_mult * 2.0

    pf = vbt.Portfolio.from_signals(
        c,
        entries=entries,
        exits=pd.Series(False, index=c.index),
        sl_stop=sl_pts / c,
        tp_stop=tp_pts / c,
        init_cash=CAPITAL,
        fees=0.0005,
        slippage=0.001,
        freq="1D"
    )
    stats = pf.stats()
    trades_n = int(stats.get("Total Trades", 0))
    factor   = float(stats.get("Profit Factor", 0) or 0)
    dd       = float(stats.get("Max Drawdown [%]", 100) or 100)
    ret      = float(stats.get("Total Return [%]", -100) or -100)
    return trades_n, factor, dd, ret, pf

# ============================================================
# FUNCION OBJETIVO PARA OPTUNA
# (optimiza factor de ganancia medio en los 3 simbolos)
# ============================================================
def objetivo(trial):
    ema_r   = trial.suggest_int("ema_r",   5,  15)
    ema_l   = trial.suggest_int("ema_l",  18,  35)
    ema_t   = trial.suggest_int("ema_t", 150, 250)
    adx_th  = trial.suggest_int("adx_th", 15,  30)
    atr_m   = trial.suggest_float("atr_m", 1.2, 3.0, step=0.1)

    if ema_r >= ema_l:
        return 0.0

    factores = []
    trades_t = 0
    for sym in SIMBOLOS:
        try:
            n, f, dd, ret, _ = backtest(sym, ema_r, ema_l, ema_t, adx_th, atr_m)
            if n < 10:          # descarta combinaciones con muy pocas operaciones
                return 0.0
            if dd > 25:         # descarta drawdowns excesivos
                return 0.0
            factores.append(f)
            trades_t += n
        except Exception:
            return 0.0

    return float(np.mean(factores))

# ============================================================
# OPTIMIZACION CON OPTUNA
# ============================================================
print(f"\nOptimizando {N_TRIALS} combinaciones en SPY + QQQ + DIA...")
print("(esto tarda 1-2 minutos)\n")

study = optuna.create_study(direction="maximize",
                            sampler=optuna.samplers.TPESampler(seed=42))
study.optimize(objetivo, n_trials=N_TRIALS, show_progress_bar=True)

best = study.best_params
best_val = study.best_value
print(f"\n{'='*50}")
print(f"  MEJORES PARAMETROS ENCONTRADOS")
print(f"{'='*50}")
print(f"  EMA Rapida   : {best['ema_r']}")
print(f"  EMA Lenta    : {best['ema_l']}")
print(f"  EMA Tendencia: {best['ema_t']}")
print(f"  ADX Umbral   : {best['adx_th']}")
print(f"  ATR Mult SL  : {best['atr_m']}")
print(f"  Factor medio : {best_val:.3f}")
print(f"{'='*50}")

# ============================================================
# BACKTEST FINAL CON MEJORES PARAMETROS + REPORTE QUANTSTATS
# ============================================================
print("\nGenerando reportes finales...\n")

for sym in SIMBOLOS:
    n, f, dd, ret, pf = backtest(
        sym,
        best["ema_r"], best["ema_l"], best["ema_t"],
        best["adx_th"], best["atr_m"]
    )
    meses   = len(closes) / 21
    ops_mes = n / meses
    print(f"  {sym}: {n} trades ({ops_mes:.1f}/mes) | Factor {f:.3f} | DD {dd:.1f}% | Ret {ret:.1f}%")

    # Reporte quantstats
    ret_series = pf.returns().dropna()
    ret_series.index = pd.to_datetime(ret_series.index).tz_localize(None)

    bench = closes[sym].pct_change().dropna()
    bench.index = pd.to_datetime(bench.index).tz_localize(None)

    out = os.path.join(OUTPUT_DIR, f"reporte_{sym.lower()}_optimizado.html")
    qs.reports.html(ret_series, benchmark=bench,
                    title=f"EMA+MACD Optimizado — {sym}",
                    output=out)
    print(f"  Reporte: {out}")

print(f"\nTODO LISTO. Abre los HTML en tu navegador.")
print(f"\nCODIGO PINE SCRIPT para estos parametros:")
print(f"  emaRapidaLen = {best['ema_r']}")
print(f"  emaLentaLen  = {best['ema_l']}")
print(f"  emaTendLen   = {best['ema_t']}")
print(f"  adxUmbral    = {best['adx_th']}")
print(f"  atrMult      = {best['atr_m']}")
