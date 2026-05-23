"""
Backtest XAUUSD ORB v2 — replica fiel del EA AGM_XAUUSD_ORB_M15.mq5.

Logica:
- ORB = primera vela M15 de NY (13:30 GMT)
- Filtro rango ORB en % del precio [Min, Max]
- Senal LONG: close M15 anterior > orbHigh -> entry = open M15 actual
- Doble entrada: lots a TP1 (rng*0.5) + lots a TP2 (rng*4)
- SL = orbLow para ambas
- BE en TP2 cuando precio toca TP1
- EOS cierre al fin de sesion (20 GMT)
- LongOnly = true (default EA)
- MaxTradesDay = 1
- RiskPct = 0.30% (default v2.1)

PnL: precio_diff / 0.01 * $1 / lote estandar = 100 USD por $1 de movimiento por lote.
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
MT5_CSV = r"C:\Users\alber\tradingview-scripts\python\data\XAUUSD_M15_mt5.csv"
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "reports")

INITIAL = 50_000.0
RISK_PCT = 0.0030    # 0.30%
MAX_LOTS = 4.0
USD_PER_DOLLAR_MOVE_PER_LOT = 100  # XAU 1 lote estandar = 100 oz; $1 movimiento = $100 USD

NY_HOUR = 13
NY_MINUTE = 30
NY_END_HOUR = 20
TP1_MULT = 0.5
TP2_MULT = 4.0
LONG_ONLY = True


def cargar_dataset_completo():
    """Carga Dukascopy M1 + agrega MT5 reciente, deduplica."""
    print("  Cargando Dukascopy M1...")
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
    print(f"  Dukascopy M15: {len(df15):,} barras {df15.index[0]} -> {df15.index[-1]}")

    if os.path.exists(MT5_CSV):
        print(f"  Cargando MT5 M15 reciente...")
        df_mt5 = pd.read_csv(MT5_CSV, parse_dates=["time"], index_col="time")
        df_mt5 = df_mt5.rename(columns={"open": "Open", "high": "High", "low": "Low",
                                         "close": "Close", "tick_volume": "Volume"})
        df_mt5 = df_mt5[["Open", "High", "Low", "Close", "Volume"]]
        print(f"  MT5 M15: {len(df_mt5):,} barras {df_mt5.index[0]} -> {df_mt5.index[-1]}")
        # Combinar, prevalece Dukascopy donde se solapan
        cutoff = df15.index.max()
        df_mt5_new = df_mt5[df_mt5.index > cutoff]
        if len(df_mt5_new):
            df15 = pd.concat([df15, df_mt5_new]).sort_index()
            print(f"  Anadidas {len(df_mt5_new):,} barras MT5 frescas (despues {cutoff})")
    print(f"  Dataset final: {len(df15):,} barras {df15.index[0]} -> {df15.index[-1]}")
    return df15


def calc_lots(equity, sl_dist):
    if sl_dist <= 0:
        return 0.0
    risk_usd = equity * RISK_PCT
    # $1 de SL distance = $100 USD por lote estandar (XAU 100 oz)
    lots = risk_usd / (sl_dist * USD_PER_DOLLAR_MOVE_PER_LOT)
    lots = min(max(round(lots, 2), 0.01), MAX_LOTS)
    return lots


def run_orb_backtest(df15, filter_fn, label):
    print(f"  >>> {label}")
    equity = INITIAL
    trades = []
    eq_curve = [INITIAL]

    df15 = df15.copy()
    df15["date"] = df15.index.date

    for date, day in df15.groupby("date"):
        if pd.Timestamp(date).dayofweek >= 5:
            continue

        # Localizar barra ORB (13:30) y siguientes de la sesion
        sess = day[(day.index.hour >= NY_HOUR) & (day.index.hour < NY_END_HOUR)]
        if len(sess) < 2:
            continue
        orb = sess[(sess.index.hour == NY_HOUR) & (sess.index.minute == NY_MINUTE)]
        if len(orb) == 0:
            continue
        orb_h = float(orb["High"].iloc[0])
        orb_l = float(orb["Low"].iloc[0])
        orb_c = float(orb["Close"].iloc[0])
        orb_range = orb_h - orb_l
        if orb_range <= 0:
            continue
        if not filter_fn(orb_h, orb_l, orb_c):
            continue

        # Barras post-ORB (siguientes a la barra ORB, dentro de NY)
        orb_time = orb.index[0]
        post = sess[sess.index > orb_time]
        if len(post) < 1:
            continue

        # Senal: close anterior > orb_high (siempre comparamos con la barra previa a la actual)
        # En el primer paso, la "barra previa" es la ORB. Si su close ya >= orb_high, esperamos
        # confirmacion en la siguiente barra. Lo que dice el EA: "close1 > orbHigh" cuando
        # ya hay posicion. Aqui, simplificamos: cuando entra en una barra cuyo close anterior > orb_h.

        prev_close = orb_c
        entry_done = False
        for i, (t, bar) in enumerate(post.iterrows()):
            if entry_done:
                break
            # Senal LONG: prev_close > orb_h (vela anterior cerro arriba)
            if prev_close > orb_h:
                # Entry = open de esta barra
                entry = float(bar["Open"])
                sl = orb_l
                sl_dist = entry - sl
                if sl_dist <= 0:
                    prev_close = float(bar["Close"])
                    continue
                tp1 = entry + orb_range * TP1_MULT
                tp2 = entry + orb_range * TP2_MULT
                lots = calc_lots(equity, sl_dist)
                if lots <= 0:
                    prev_close = float(bar["Close"])
                    continue

                # Simular las 2 posiciones (TP1 y TP2) durante el resto de la sesion
                bars_remaining = post.iloc[i:]
                result_p1, result_p2 = simulate_double(bars_remaining, entry, sl, tp1, tp2, lots)
                pnl_usd = result_p1["pnl_usd"] + result_p2["pnl_usd"]
                equity += pnl_usd
                eq_curve.append(equity)
                trades.append({
                    "date": str(date), "entry_time": str(t),
                    "entry": round(entry, 2), "sl": round(sl, 2),
                    "tp1": round(tp1, 2), "tp2": round(tp2, 2),
                    "orb_range_usd": round(orb_range, 2),
                    "orb_range_pct": round(100 * orb_range / orb_c, 3),
                    "lots_each": lots, "lots_total": round(2 * lots, 2),
                    "p1_exit": result_p1["exit_type"], "p1_pnl_usd": round(result_p1["pnl_usd"], 2),
                    "p2_exit": result_p2["exit_type"], "p2_pnl_usd": round(result_p2["pnl_usd"], 2),
                    "pnl_usd": round(pnl_usd, 2),
                    "equity": round(equity, 2),
                })
                entry_done = True
            prev_close = float(bar["Close"])

    return pd.DataFrame(trades), eq_curve


def simulate_double(bars, entry, sl, tp1, tp2, lots):
    """Simula 2 posiciones LONG (TP1 y TP2) con BE en TP2 cuando precio toca TP1."""
    p1 = {"entry": entry, "sl": sl, "tp": tp1, "exit_type": None, "exit_price": None, "lots": lots}
    p2 = {"entry": entry, "sl": sl, "tp": tp2, "exit_type": None, "exit_price": None, "lots": lots}
    p1_hit = False

    for _, bar in bars.iterrows():
        h = float(bar["High"]); l = float(bar["Low"]); c = float(bar["Close"])

        # Posicion 1
        if p1["exit_type"] is None:
            if l <= p1["sl"]:
                p1["exit_type"] = "SL"; p1["exit_price"] = p1["sl"]
            elif h >= p1["tp"]:
                p1["exit_type"] = "TP1"; p1["exit_price"] = p1["tp"]
                p1_hit = True
                # Mover SL de P2 a entry (BE)
                p2["sl"] = max(p2["sl"], p2["entry"])

        # Posicion 2 (despues de procesar p1 por si activo BE)
        if p2["exit_type"] is None:
            if l <= p2["sl"]:
                p2["exit_type"] = "SL_BE" if p1_hit else "SL"
                p2["exit_price"] = p2["sl"]
            elif h >= p2["tp"]:
                p2["exit_type"] = "TP2"; p2["exit_price"] = p2["tp"]

        if p1["exit_type"] is not None and p2["exit_type"] is not None:
            break

    # EOS: cerrar al close de la ultima barra si seguia abierta
    if len(bars):
        last_close = float(bars["Close"].iloc[-1])
        if p1["exit_type"] is None:
            p1["exit_type"] = "EOS"; p1["exit_price"] = last_close
        if p2["exit_type"] is None:
            p2["exit_type"] = "EOS"; p2["exit_price"] = last_close

    # PnL en USD (LONG)
    for p in (p1, p2):
        if p["exit_price"] is None:
            p["pnl_usd"] = 0.0
        else:
            p["pnl_usd"] = (p["exit_price"] - p["entry"]) * USD_PER_DOLLAR_MOVE_PER_LOT * p["lots"]

    return p1, p2


def calc_metrics(trades, eq_curve):
    if len(trades) == 0:
        return {"n": 0, "pnl": 0, "wr": 0, "pf": 0, "dd_pct": 0, "ann_pct": 0, "expectancy": 0}
    pnl = float(trades["pnl_usd"].sum())
    wins = trades.loc[trades["pnl_usd"] > 0, "pnl_usd"]
    losses = trades.loc[trades["pnl_usd"] < 0, "pnl_usd"]
    wr = 100 * (trades["pnl_usd"] > 0).mean()
    pf = float(wins.sum()) / abs(float(losses.sum())) if len(losses) and losses.sum() != 0 else 0
    eq = np.array(eq_curve)
    peak = np.maximum.accumulate(eq)
    dd = abs(float(((eq - peak) / peak).min())) * 100
    yrs = (pd.to_datetime(trades["date"].iloc[-1]) - pd.to_datetime(trades["date"].iloc[0])).days / 365.25
    ann = ((INITIAL + pnl) / INITIAL) ** (1 / max(yrs, 0.01)) - 1
    expectancy = pnl / len(trades)
    return {"n": len(trades), "pnl": round(pnl, 0), "wr": round(wr, 1),
            "pf": round(pf, 2), "dd_pct": round(dd, 2),
            "ann_pct": round(ann * 100, 2), "expectancy": round(expectancy, 2)}


def main():
    print("=" * 72)
    print("  XAUUSD ORB v2 — Backtest fiel del EA (Dukascopy 2010-mar2026 + MT5 abr-may2026)")
    print("=" * 72)

    df15 = cargar_dataset_completo()

    filtros = [
        ("Pips fijos [40, 150]", lambda h, l, c: 40 * 0.1 <= (h - l) <= 150 * 0.1),
        ("Pct precio [0.15, 0.55]", lambda h, l, c: 0.15 <= 100 * (h - l) / c <= 0.55),
    ]

    resumen = {}
    for label, fn in filtros:
        print()
        trades, eq = run_orb_backtest(df15, fn, label)
        m = calc_metrics(trades, eq)
        resumen[label] = (trades, m)
        print(f"    Trades: {m['n']}  WR: {m['wr']}%  PF: {m['pf']}  DD: {m['dd_pct']}%"
              f"  PnL: ${m['pnl']:,.0f}  Ann: {m['ann_pct']}%  Expectancy: ${m['expectancy']}")

        # Year-by-year
        if len(trades) > 0:
            trades["year"] = pd.to_datetime(trades["date"]).dt.year
            print(f"    Por anio:")
            print(f"    {'Year':<6} {'N':>3} {'PnL $':>9} {'WR':>6} {'TP1%':>5} {'TP2%':>5}")
            for y, g in trades.groupby("year"):
                pnl_y = float(g["pnl_usd"].sum())
                n = len(g)
                wr = 100 * (g["pnl_usd"] > 0).mean()
                tp1_pct = 100 * (g["p1_exit"] == "TP1").mean()
                tp2_pct = 100 * (g["p2_exit"] == "TP2").mean()
                print(f"    {int(y):<6} {n:>3} ${pnl_y:>8,.0f} {wr:>5.1f}% {tp1_pct:>4.0f}% {tp2_pct:>4.0f}%")

    # Comparativa
    print()
    print("=" * 72)
    print("  COMPARATIVA")
    print("=" * 72)
    print(f"  {'Filtro':<28} {'Trades':>7} {'WR':>6} {'PF':>5} {'DD':>6} {'PnL':>10} {'Ann':>6}")
    for label, (_, m) in resumen.items():
        print(f"  {label:<28} {m['n']:>7} {m['wr']:>5.1f}% {m['pf']:>5.2f} {m['dd_pct']:>5.2f}%"
              f" ${m['pnl']:>9,.0f} {m['ann_pct']:>5.2f}%")

    # Guardar trades
    for label, (t, _) in resumen.items():
        safe = label.replace(" ", "_").replace("[", "").replace("]", "").replace(",", "").replace("%", "pct").replace(".", "p")
        t.to_csv(os.path.join(OUT_DIR, f"XAUUSD_ORB_v2_bt_{safe}.csv"), index=False)
    print(f"\n  Trades en reports/XAUUSD_ORB_v2_bt_*.csv")


if __name__ == "__main__":
    main()
