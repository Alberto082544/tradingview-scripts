"""
Backtest Python del XAUUSD ORB con el filtro NUEVO en % del precio.

Replica la logica del EA (NY 13:30 GMT, primera M15, TP1=0.5xR, TP2=4xR,
LongOnly, MaxTradesDay=1) sobre el dataset Dukascopy 2010-2026.

Compara:
- Filtro original [40, 150] pips fijos
- Filtro nuevo  [0.15%, 0.55%] del precio
"""
import os
import sys
import warnings

warnings.filterwarnings("ignore")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import numpy as np
import pandas as pd

CSV = r"C:\Users\alber\OneDrive\Desktop\DATOS_CSV\2026.5.8XAUUSD_M1_dukas-M1-No Session.csv"
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "reports")
PIP = 0.1   # XAU pip = $0.10
PIP_VAL = 10.0  # $10 por pip por lote estandar
INITIAL = 50_000.0
RISK_PCT = 0.005  # 0.5%

# Sesion NY M15: 13:30 GMT - 20:00 GMT
NY_START_H = 13
NY_START_M = 30
NY_END_H = 20

# Estrategia
TP1_MULT = 0.5
TP2_MULT = 4.0
LONG_ONLY = True
MAX_TRADES_DAY = 1


def cargar_m15():
    print("Cargando CSV M1 y agregando a M15...")
    df = pd.read_csv(CSV, dtype={
        "Date": str, "Time": str,
        "Open": np.float32, "High": np.float32, "Low": np.float32, "Close": np.float32,
        "Volume": np.int32,
    })
    df["datetime"] = pd.to_datetime(df["Date"] + " " + df["Time"], format="%Y%m%d %H:%M:%S")
    df = df.set_index("datetime").drop(columns=["Date", "Time"])
    df15 = df.resample("15min").agg({
        "Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum",
    }).dropna()
    return df15


def run_backtest(df15, filter_fn, label):
    """Ejecuta backtest. filter_fn(orb_high, orb_low, orb_close) -> bool."""
    equity = INITIAL
    trades = []

    df15 = df15.copy()
    df15["hour"] = df15.index.hour
    df15["minute"] = df15.index.minute
    df15["date"] = df15.index.date

    for date, day in df15.groupby("date"):
        if pd.Timestamp(date).dayofweek >= 5:
            continue
        # Encontrar barra ORB (13:30 GMT)
        orb = day[(day["hour"] == NY_START_H) & (day["minute"] == NY_START_M)]
        if len(orb) == 0:
            continue
        orb_row = orb.iloc[0]
        orb_high = orb_row["High"]
        orb_low = orb_row["Low"]
        orb_close = orb_row["Close"]
        orb_range = orb_high - orb_low
        if orb_range <= 0:
            continue
        if not filter_fn(orb_high, orb_low, orb_close):
            continue
        # Barras siguientes hasta NY_END_H
        post = day[(day["hour"] >= NY_START_H) &
                   ((day["hour"] > NY_START_H) | (day["minute"] > NY_START_M)) &
                   (day["hour"] < NY_END_H)]
        if len(post) == 0:
            continue
        # Senal: precio cierre rompe orb_high (LONG) o orb_low (SHORT si !LongOnly)
        traded = False
        for _, bar in post.iterrows():
            if not LONG_ONLY:
                if bar["Close"] < orb_low and not traded:
                    # SHORT
                    entry = bar["Close"]
                    sl = orb_high
                    sl_dist = sl - entry
                    if sl_dist <= 0:
                        continue
                    tp1 = entry - orb_range * TP1_MULT
                    tp2 = entry - orb_range * TP2_MULT
                    pnl, exit_type = _simular(post, entry, sl, tp1, tp2, "short", bar.name)
                    risk_usd = equity * RISK_PCT
                    lots = min(risk_usd / (sl_dist / PIP * PIP_VAL), 4.0)
                    pnl_usd = pnl * lots
                    equity += pnl_usd
                    trades.append({"date": date, "dir": "short", "entry": entry,
                                   "sl": sl, "tp1": tp1, "tp2": tp2,
                                   "pnl_pips": round(pnl / PIP, 1), "pnl_usd": round(pnl_usd, 2),
                                   "exit_type": exit_type, "equity": round(equity, 2),
                                   "lots": round(lots, 2), "orb_range_pct": 100 * orb_range / orb_close})
                    traded = True
                    break
            if bar["Close"] > orb_high and not traded:
                # LONG
                entry = bar["Close"]
                sl = orb_low
                sl_dist = entry - sl
                if sl_dist <= 0:
                    continue
                tp1 = entry + orb_range * TP1_MULT
                tp2 = entry + orb_range * TP2_MULT
                pnl, exit_type = _simular(post, entry, sl, tp1, tp2, "long", bar.name)
                risk_usd = equity * RISK_PCT
                lots = min(risk_usd / (sl_dist / PIP * PIP_VAL), 4.0)
                pnl_usd = pnl * lots
                equity += pnl_usd
                trades.append({"date": date, "dir": "long", "entry": entry,
                               "sl": sl, "tp1": tp1, "tp2": tp2,
                               "pnl_pips": round(pnl / PIP, 1), "pnl_usd": round(pnl_usd, 2),
                               "exit_type": exit_type, "equity": round(equity, 2),
                               "lots": round(lots, 2), "orb_range_pct": 100 * orb_range / orb_close})
                traded = True
                break

    return pd.DataFrame(trades)


def _simular(bars, entry, sl, tp1, tp2, direction, t_start):
    """Simulacion simple: TP1 (50% lots) + TP2 (50%) o SL completo."""
    bars_after = bars[bars.index > t_start]
    tp1_hit = False
    pnl_total = 0.0  # en USD por lote
    for _, bar in bars_after.iterrows():
        if direction == "long":
            if not tp1_hit and bar["High"] >= tp1:
                pnl_total += (tp1 - entry) * 0.5
                tp1_hit = True
            if bar["Low"] <= sl:
                if tp1_hit:
                    pnl_total += (sl - entry) * 0.5
                else:
                    pnl_total += (sl - entry)
                return pnl_total, "SL"
            if bar["High"] >= tp2:
                pnl_total += (tp2 - entry) * 0.5 if tp1_hit else (tp2 - entry)
                return pnl_total, "TP2"
        else:
            if not tp1_hit and bar["Low"] <= tp1:
                pnl_total += (entry - tp1) * 0.5
                tp1_hit = True
            if bar["High"] >= sl:
                if tp1_hit:
                    pnl_total += (entry - sl) * 0.5
                else:
                    pnl_total += (entry - sl)
                return pnl_total, "SL"
            if bar["Low"] <= tp2:
                pnl_total += (entry - tp2) * 0.5 if tp1_hit else (entry - tp2)
                return pnl_total, "TP2"
    # Cierre EOS
    last = bars_after.iloc[-1] if len(bars_after) else None
    if last is not None:
        if direction == "long":
            close = (last["Close"] - entry) * (0.5 if tp1_hit else 1.0)
        else:
            close = (entry - last["Close"]) * (0.5 if tp1_hit else 1.0)
        pnl_total += close
    return pnl_total, "EOS"


def calc_metrics(trades):
    if len(trades) == 0:
        return {"n": 0, "pnl": 0, "wr": 0, "pf": 0, "dd_pct": 0, "ann_pct": 0}
    pnl = trades["pnl_usd"].sum()
    wins = trades.loc[trades["pnl_usd"] > 0, "pnl_usd"]
    losses = trades.loc[trades["pnl_usd"] < 0, "pnl_usd"]
    wr = 100 * (trades["pnl_usd"] > 0).mean()
    pf = wins.sum() / abs(losses.sum()) if len(losses) and losses.sum() != 0 else 0
    eq = np.concatenate([[INITIAL], (INITIAL + trades["pnl_usd"].cumsum()).values])
    peak = np.maximum.accumulate(eq)
    dd = abs(((eq - peak) / peak).min()) * 100
    yrs = (pd.to_datetime(trades["date"].iloc[-1]) - pd.to_datetime(trades["date"].iloc[0])).days / 365.25
    ann = ((INITIAL + pnl) / INITIAL) ** (1 / max(yrs, 0.01)) - 1
    return {"n": len(trades), "pnl": round(pnl, 0), "wr": round(wr, 1),
            "pf": round(pf, 2), "dd_pct": round(dd, 2),
            "ann_pct": round(ann * 100, 2)}


def main():
    print("=" * 70)
    print("  XAUUSD ORB - Backtest filtro % vs pips fijos (Dukascopy 2010-2026)")
    print("=" * 70)
    df15 = cargar_m15()
    print(f"  {len(df15):,} barras M15 cargadas")

    filtros = [
        ("Pips fijos [40, 150]", lambda h, l, c: 40 * PIP <= (h - l) <= 150 * PIP),
        ("% precio [0.15, 0.55]", lambda h, l, c: 0.15 <= 100 * (h - l) / c <= 0.55),
    ]

    resultados = {}
    for label, fn in filtros:
        print(f"\n  >>> {label}")
        trades = run_backtest(df15, fn, label)
        m = calc_metrics(trades)
        resultados[label] = (trades, m)
        print(f"    Trades: {m['n']}  WR: {m['wr']}%  PF: {m['pf']}  DD: {m['dd_pct']}%  PnL: ${m['pnl']:,.0f}  Ann: {m['ann_pct']}%")

        # Por anio
        if len(trades):
            trades["year"] = pd.to_datetime(trades["date"]).dt.year
            print(f"    Por anio:")
            for y, g in trades.groupby("year"):
                pnl_y = g["pnl_usd"].sum()
                n = len(g)
                wr = 100 * (g["pnl_usd"] > 0).mean()
                print(f"      {int(y)}: N={n:>3}  PnL=${pnl_y:>9,.0f}  WR={wr:>5.1f}%")

    # Guardar
    for label, (t, _) in resultados.items():
        safe = label.replace(" ", "_").replace("[", "").replace("]", "").replace(",", "").replace("%", "pct").replace(".", "p")
        t.to_csv(os.path.join(OUT_DIR, f"XAUUSD_ORB_bt_{safe}.csv"), index=False)

    print("\n  Reports en reports/XAUUSD_ORB_bt_*.csv")


if __name__ == "__main__":
    main()
