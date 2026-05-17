"""
GBPJPY Bot — Motor de backtest barra a barra
"""
import pandas as pd
import numpy as np
from config import (INITIAL_CAPITAL, RISK_PCT, MAX_LOTS, USDJPY_RATE,
                    TP_MULT, BE_MULT, EXIT_BARS, MAX_SL_PIPS, MIN_SL_PIPS,
                    SESSION_START, SESSION_END, BAD_HOURS,
                    MAX_TRADES_DAY, ORDER_EXPIRY)

PIP = 0.01


def pip_value():
    return (PIP * 100_000) / USDJPY_RATE


def calc_lots(equity, sl_distance):
    sl_pips = sl_distance / PIP
    if sl_pips <= 0:
        return 0.0
    lots = (equity * RISK_PCT) / (sl_pips * pip_value())
    return min(round(lots, 2), MAX_LOTS)


def run_backtest(df: pd.DataFrame) -> pd.DataFrame:
    """
    Motor bar-by-bar con órdenes stop pendientes.
    Implementa: Break-Even, salida por tiempo.
    """
    trades       = []
    equity       = INITIAL_CAPITAL
    position     = None
    pending      = None
    trades_today = 0
    last_date    = None
    min_sl       = MIN_SL_PIPS * PIP
    max_sl       = MAX_SL_PIPS * PIP

    for i in range(1, len(df)):
        row  = df.iloc[i]
        dt   = df.index[i]
        date = dt.date()
        bh   = row["high"]
        bl   = row["low"]

        if date != last_date:
            trades_today = 0
            last_date    = date

        # 1. Gestión de posición activa
        if position is not None:
            d     = position["direction"]
            entry = position["entry"]
            sl_d  = position["sl_d"]
            position["bars_held"] += 1

            # Break-Even
            if not position["be_done"]:
                gain = bh - entry if d == "long" else entry - bl
                if gain >= BE_MULT * sl_d:
                    position["sl"]     = entry
                    position["be_done"] = True

            # Chequeo SL / TP / Tiempo
            sl = position["sl"]
            tp = position["tp"]
            ep = et = None
            if d == "long":
                if bl <= sl: ep, et = sl, "SL"
                elif bh >= tp: ep, et = tp, "TP"
            else:
                if bh >= sl: ep, et = sl, "SL"
                elif bl <= tp: ep, et = tp, "TP"
            if ep is None and position["bars_held"] >= EXIT_BARS:
                ep, et = row["close"], "TIME"

            if ep is not None:
                pnl_pips = (ep - entry) / PIP if d == "long" else (entry - ep) / PIP
                pnl      = pnl_pips * pip_value() * position["lots"]
                equity  += pnl
                trades.append({
                    "entry_dt":    position["entry_dt"],
                    "exit_dt":     dt,
                    "direction":   d,
                    "entry_price": entry,
                    "exit_price":  ep,
                    "lots":        position["lots"],
                    "sl_pips":     sl_d / PIP,
                    "pnl":         round(pnl, 2),
                    "exit_type":   et,
                    "equity":      round(equity, 2),
                    "bars_held":   position["bars_held"],
                })
                position = None

        # 2. Activar orden pendiente
        if pending is not None and position is None:
            ep_p = pending["entry_price"]
            hit  = ((pending["direction"] == "long"  and bh >= ep_p) or
                    (pending["direction"] == "short" and bl <= ep_p))
            if hit:
                sl_d = float(np.clip(pending["sl_dist"], min_sl, max_sl))
                tp_d = sl_d * TP_MULT
                lots = calc_lots(equity, sl_d)
                if lots > 0:
                    sgn = 1 if pending["direction"] == "long" else -1
                    position = {
                        "direction": pending["direction"],
                        "entry":     ep_p,
                        "sl":        ep_p - sgn * sl_d,
                        "tp":        ep_p + sgn * tp_d,
                        "lots":      lots,
                        "bars_held": 0,
                        "be_done":   False,
                        "sl_d":      sl_d,
                        "entry_dt":  dt,
                    }
                    trades_today += 1
                pending = None
            else:
                pending["bars_alive"] += 1
                if pending["bars_alive"] >= ORDER_EXPIRY:
                    pending = None

        # 3. Nueva señal
        if position is not None or pending is not None:
            continue
        if dt.hour < SESSION_START or dt.hour >= SESSION_END:
            continue
        if dt.hour in BAD_HOURS:
            continue
        if dt.weekday() >= 5 or (dt.weekday() == 4 and dt.hour >= 20):
            continue
        if trades_today >= MAX_TRADES_DAY:
            continue

        sig = None
        if bool(row.get("long_signal"))  and pd.notna(row.get("entry_price")):
            sig = "long"
        elif bool(row.get("short_signal")) and pd.notna(row.get("entry_price")):
            sig = "short"

        # Filtro de calidad: solo SL natural <= MAX_SL_PIPS
        if sig and row["sl"] > max_sl:
            continue

        if sig:
            pending = {
                "direction":   sig,
                "entry_price": row["entry_price"],
                "sl_dist":     row["sl"],
                "bars_alive":  0,
            }

    return pd.DataFrame(trades)


def print_results(trades: pd.DataFrame):
    if len(trades) == 0:
        print("Sin operaciones ejecutadas.")
        return

    n    = len(trades)
    pnl  = trades["pnl"].sum()
    wr   = (trades["pnl"] > 0).mean() * 100
    wins = trades.loc[trades["pnl"] > 0, "pnl"]
    loss = trades.loc[trades["pnl"] < 0, "pnl"]
    pf   = wins.sum() / abs(loss.sum()) if len(loss) > 0 else 0
    dd   = (trades["equity"].cummax() - trades["equity"]).max()
    exits = trades["exit_type"].value_counts().to_dict()

    print()
    print("=" * 55)
    print("  RESULTADOS DEL BACKTEST — GBPJPY M15")
    print("=" * 55)
    print(f"  Capital inicial:     ${INITIAL_CAPITAL:,.0f}")
    print(f"  Capital final:       ${INITIAL_CAPITAL + pnl:,.0f}")
    print(f"  P&L total:           ${pnl:,.0f}  ({pnl/INITIAL_CAPITAL*100:.1f}%)")
    print(f"  Operaciones:         {n}")
    print(f"  Win Rate:            {wr:.1f}%")
    print(f"  Profit Factor:       {pf:.2f}")
    print(f"  Max Drawdown:        ${dd:,.0f}  ({dd/INITIAL_CAPITAL*100:.1f}%)")
    if len(wins) > 0:
        print(f"  Media ganancia:      ${wins.mean():,.0f}")
    if len(loss) > 0:
        print(f"  Media perdida:       ${abs(loss.mean()):,.0f}")
    print(f"  Salidas: SL={exits.get('SL',0)}  TP={exits.get('TP',0)}  TIME={exits.get('TIME',0)}")
    print("=" * 55)
