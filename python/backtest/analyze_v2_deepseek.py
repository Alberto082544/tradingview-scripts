"""
Analiza trades de v2 con DeepSeek para identificar filtros que mejoren la estrategia.
Re-corre v2 con trades detallados, saca estadísticas por año/hora/dirección y pide
recomendaciones concretas de código a DeepSeek.
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd
import numpy as np
from datetime import datetime
from dotenv import load_dotenv
from strategies.gbpjpy_v2 import add_indicators, generate_signals

load_dotenv()

DUKAS_CSV  = r"C:\Users\alber\OneDrive\Desktop\Nueva carpeta\GBPJPY_M1_dukas.csv"
START_DATE = datetime(2020, 1, 1)
END_DATE   = datetime(2025, 12, 31)
PIP=0.01; USDJPY=145.0; INITIAL_CAP=50000.0; RISK_PCT=0.005; MAX_LOTS=4.0
SESSION_START=7; SESSION_END=20; MAX_TRADES_DAY=5; ORDER_EXPIRY=24; EXIT_BARS=30
MIN_SL=15*PIP; MAX_SL=80*PIP; MIN_TP=30*PIP; MAX_TP=200*PIP

def pip_val():
    return (PIP * 100_000) / USDJPY

def calc_lots(eq, sl_d):
    sp = sl_d / PIP
    return min(round(eq * RISK_PCT / (sp * pip_val()), 2), MAX_LOTS) if sp > 0 else 0

def load_data():
    df_m1 = pd.read_csv(DUKAS_CSV, header=None,
        names=["date","time","open","high","low","close","volume","v2","sp"],
        dtype={"date": str, "time": str})
    df_m1["datetime"] = pd.to_datetime(df_m1["date"] + " " + df_m1["time"], format="%Y.%m.%d %H:%M")
    df_m1.set_index("datetime", inplace=True)
    df_m1 = df_m1[["open","high","low","close","volume"]]
    df_m1 = df_m1[(df_m1.index >= START_DATE) & (df_m1.index <= END_DATE)]
    df_m15 = df_m1.resample("15min").agg({"open":"first","high":"max","low":"min","close":"last","volume":"sum"}).dropna()
    df_h4  = df_m1.resample("4h").agg({"open":"first","high":"max","low":"min","close":"last","volume":"sum"}).dropna()
    return df_m15, df_h4

def run_backtest_detailed(df):
    trades=[]; equity=INITIAL_CAP; position=None; pending=None
    trades_today=0; last_date=None

    for i in range(1, len(df)):
        row=df.iloc[i]; dt=df.index[i]; date=dt.date()
        bh=row["high"]; bl=row["low"]

        if date != last_date:
            trades_today=0; last_date=date

        if position is not None:
            d=position["direction"]; position["bars_held"]+=1
            if not position["be_done"]:
                if (d=="long" and bh-position["entry"]>=position["atr"]) or \
                   (d=="short" and position["entry"]-bl>=position["atr"]):
                    position["sl"]=position["entry"]; position["be_done"]=True
            sl=position["sl"]; tp=position["tp"]; ep=et=None
            if d=="long":
                if bl<=sl: ep,et=sl,"SL"
                elif bh>=tp: ep,et=tp,"TP"
            else:
                if bh>=sl: ep,et=sl,"SL"
                elif bl<=tp: ep,et=tp,"TP"
            if ep is None and position["bars_held"]>=EXIT_BARS:
                ep,et=row["close"],"TIME"
            if ep is not None:
                pnl=(ep-position["entry"])/PIP*(1 if d=="long" else -1)*pip_val()*position["lots"]
                equity+=pnl
                trades.append({
                    "entry_dt": position["entry_dt"],
                    "exit_dt": dt,
                    "direction": d,
                    "entry_price": position["entry"],
                    "exit_price": ep,
                    "lots": position["lots"],
                    "sl_pips": position["sl_pips"],
                    "tp_pips": position["tp_pips"],
                    "atr_entry": position["atr"],
                    "rsi_entry": position["rsi"],
                    "hour": position["hour"],
                    "pnl": round(pnl, 2),
                    "exit_type": et,
                    "equity": round(equity, 2),
                    "bars_held": position["bars_held"],
                })
                position=None

        if pending is not None and position is None:
            ep_p=pending["entry_price"]
            hit=(pending["direction"]=="long" and bh>=ep_p) or \
                (pending["direction"]=="short" and bl<=ep_p)
            if hit:
                sl_d=float(np.clip(pending["sl_dist"], MIN_SL, MAX_SL))
                tp_d=float(np.clip(pending["tp_dist"], MIN_TP, MAX_TP))
                lots=calc_lots(equity, sl_d)
                if lots > 0:
                    sgn=1 if pending["direction"]=="long" else -1
                    position={
                        "direction": pending["direction"],
                        "entry": ep_p,
                        "sl": ep_p-sgn*sl_d,
                        "tp": ep_p+sgn*tp_d,
                        "lots": lots,
                        "bars_held": 0,
                        "be_done": False,
                        "atr": pending["atr"],
                        "entry_dt": dt,
                        "sl_pips": sl_d/PIP,
                        "tp_pips": tp_d/PIP,
                        "rsi": pending["rsi"],
                        "hour": dt.hour,
                    }
                    trades_today+=1
                pending=None
            else:
                pending["bars_alive"]+=1
                if pending["bars_alive"]>=ORDER_EXPIRY: pending=None

        if position is not None or pending is not None: continue
        if dt.hour<SESSION_START or dt.hour>=SESSION_END: continue
        if dt.weekday()>=5 or (dt.weekday()==4 and dt.hour>=20): continue
        if trades_today>=MAX_TRADES_DAY: continue

        sig=None
        if bool(row.get("long_signal")) and pd.notna(row.get("entry_price")): sig="long"
        elif bool(row.get("short_signal")) and pd.notna(row.get("entry_price")): sig="short"

        if sig:
            pending={"direction":sig,"entry_price":row["entry_price"],
                     "sl_dist":row["sl"],"tp_dist":row["tp"],
                     "atr":row.get("atr14",0.2),
                     "rsi":row.get("rsi14",50),
                     "bars_alive":0}

    return pd.DataFrame(trades)

def build_stats(t):
    t["year"]   = pd.to_datetime(t["entry_dt"]).dt.year
    t["winner"] = (t["pnl"] > 0)

    # Por año
    by_year = t.groupby("year").agg(
        trades=("pnl","count"),
        pnl=("pnl","sum"),
        wr=("winner","mean"),
    ).round({"pnl":0,"wr":3})

    # Por hora
    by_hour = t.groupby("hour").agg(
        trades=("pnl","count"),
        pnl=("pnl","sum"),
        wr=("winner","mean"),
    ).round({"pnl":0,"wr":3})

    # Por dirección
    by_dir = t.groupby("direction").agg(
        trades=("pnl","count"),
        pnl=("pnl","sum"),
        wr=("winner","mean"),
    ).round({"pnl":0,"wr":3})

    # Distribución SL pips
    sl_dist = t.groupby(pd.cut(t["sl_pips"], bins=[0,20,30,40,50,60,80]))["pnl"].agg(["count","sum","mean"]).round(0)

    # Barras en posición: wins vs losses
    bars_win  = t.loc[t["winner"], "bars_held"].describe()
    bars_loss = t.loc[~t["winner"], "bars_held"].describe()

    return by_year, by_hour, by_dir, sl_dist, bars_win, bars_loss

def ask_deepseek(stats_text, t):
    from openai import OpenAI
    key = os.getenv("DEEPSEEK_API_KEY")
    client = OpenAI(api_key=key, base_url="https://api.deepseek.com")

    n    = len(t)
    pnl  = t["pnl"].sum()
    wr   = (t["pnl"]>0).mean()*100
    wins = t.loc[t["pnl"]>0,"pnl"]
    loss = t.loc[t["pnl"]<0,"pnl"]
    pf   = wins.sum()/abs(loss.sum()) if len(loss)>0 else 0
    dd   = (t["equity"].cummax()-t["equity"]).max()

    prompt = f"""Eres un quant experto en estrategias de trading. Analiza estos resultados detallados de backtest GBPJPY M15 (2020-2025) y dame recomendaciones CONCRETAS en Python para mejorar la estrategia.

## Resultados Globales
- Capital: $50.000 | Trades: {n} | P&L: ${pnl:,.0f}
- WinRate: {wr:.1f}% | PF: {pf:.2f} | Max DD: ${dd:,.0f} ({dd/50000*100:.1f}%)
- Media ganancia: ${wins.mean():.0f} | Media pérdida: ${loss.mean():.0f}

## Desglose Detallado
{stats_text}

## Estrategia actual (v2)
- Pullback a 38.2% del rango de 20 barras en M15
- Filtro tendencia: precio > EMA200 H4, EMA20 > EMA100 M15, slope EMA20 > 0
- Entrada: mercado (open de la siguiente barra)
- SL: distancia al swing low/high de 10 barras (mín 1×ATR14)
- TP: 3× SL
- Move to BE tras 1×ATR de ganancia
- EXIT_BARS=30 (salida por tiempo)
- Sesión: 07:00-20:00 UTC, máx 5 trades/día

## Preguntas
1. ¿Qué horas eliminarías? ¿Por qué?
2. ¿Deberías tradear solo longs, solo shorts, o ambas? ¿Por qué?
3. ¿Qué filtro Python concreto (una condición) eliminaría más trades perdedores sin tocar los ganadores?
4. ¿Cómo mejorarías el exit? (TP ratio, exit_bars, trailing)
5. ¿Qué año fue peor y por qué?

Responde en español. Sé específico con valores numéricos y código Python cuando sea posible. Máximo 500 palabras."""

    resp = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role":"user","content":prompt}],
        temperature=0.2, max_tokens=800,
    )
    return resp.choices[0].message.content

def main():
    print("Cargando datos...")
    df_m15, df_h4 = load_data()
    print("Calculando indicadores v2...")
    df = add_indicators(df_m15.copy(), df_h4.copy())
    df = generate_signals(df)
    print("Corriendo backtest detallado...")
    t = run_backtest_detailed(df)
    print(f"Trades: {len(t)}")

    if len(t) == 0:
        print("Sin trades")
        return

    by_year, by_hour, by_dir, sl_dist, bw, bl = build_stats(t)

    print("\n=== POR AÑO ===")
    print(by_year.to_string())
    print("\n=== POR HORA ===")
    print(by_hour.to_string())
    print("\n=== POR DIRECCIÓN ===")
    print(by_dir.to_string())
    print("\n=== SL PIPS (distribución) ===")
    print(sl_dist.to_string())
    print(f"\n=== BARRAS EN POSICIÓN ===")
    print(f"Ganadores — media: {bw['mean']:.1f}  mediana: {bw['50%']:.0f}")
    print(f"Perdedores — media: {bl['mean']:.1f}  mediana: {bl['50%']:.0f}")

    stats_text = f"""
Por año:
{by_year.to_string()}

Por hora de entrada:
{by_hour.to_string()}

Por dirección:
{by_dir.to_string()}

Distribución SL en pips:
{sl_dist.to_string()}

Barras en posición — ganadores: media={bw['mean']:.1f}, mediana={bw['50%']:.0f}
Barras en posición — perdedores: media={bl['mean']:.1f}, mediana={bl['50%']:.0f}
Salidas: {t['exit_type'].value_counts().to_dict()}
"""

    print("\nConsultando DeepSeek...")
    resp = ask_deepseek(stats_text, t)
    print("\n" + "="*70)
    print(resp.encode("utf-8", errors="replace").decode("utf-8"))
    print("="*70)

    os.makedirs("reports", exist_ok=True)
    t.to_csv("reports/trades_v2_detailed.csv", index=False)
    with open("reports/deepseek_v2_analysis.md", "w", encoding="utf-8") as f:
        f.write("# DeepSeek Analysis — v2 Detailed\n\n")
        f.write(f"## Stats\n\nPor año:\n{by_year.to_string()}\n\n")
        f.write(f"Por hora:\n{by_hour.to_string()}\n\n")
        f.write(f"Por dirección:\n{by_dir.to_string()}\n\n")
        f.write(f"## DeepSeek Recommendations\n\n{resp}\n")
    print("\nInforme guardado en reports/deepseek_v2_analysis.md")

if __name__ == "__main__":
    main()
