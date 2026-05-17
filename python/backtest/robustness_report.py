"""
Genera informe completo de robustez para las dos mejores estrategias GBPJPY v8.
Tests: walk-forward, Monte Carlo, sensibilidad de parámetros, estabilidad anual.
Salida: reports/GBPJPY_Strategy_Report.md
"""
import os, sys, random
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd
import numpy as np
from datetime import datetime
from strategies.gbpjpy_v2 import add_indicators, generate_signals

# ── Configuración común ───────────────────────────────────────────────────────
DUKAS_CSV   = r"C:\Users\alber\OneDrive\Desktop\Nueva carpeta\GBPJPY_M1_dukas.csv"
PIP         = 0.01
USDJPY      = 145.0
INITIAL_CAP = 50_000.0
RISK_PCT    = 0.005
MAX_LOTS    = 4.0
SESSION_START  = 7
SESSION_END    = 19
BAD_HOURS      = {8}
MAX_TRADES_DAY = 5
ORDER_EXPIRY   = 24
MAX_SL_FILTER  = 30 * PIP
MIN_SL         = 15 * PIP

# ── Definición de las 2 estrategias ──────────────────────────────────────────
STRATEGIES = {
    "A_Balanceada": {
        "tp_mult": 3.0, "be_mult": 0.8,
        "trail_act": 0, "trail_dist": 0, "exit_bars": 30,
        "label": "Estrategia A — Balanceada",
        "desc": "Relacion riesgo/beneficio equilibrada. Orientada a capital estable con DD controlado.",
    },
    "B_MaxRendimiento": {
        "tp_mult": 5.0, "be_mult": 1.5,
        "trail_act": 0, "trail_dist": 0, "exit_bars": 80,
        "label": "Estrategia B — Maximo Rendimiento",
        "desc": "TP amplio y BE tardio permiten capturar tendencias largas. Mayor P&L, mayor DD.",
    },
}

def pip_val():
    return (PIP * 100_000) / USDJPY

def calc_lots(eq, sl_d):
    sp = sl_d / PIP
    return min(round(eq * RISK_PCT / (sp * pip_val()), 2), MAX_LOTS) if sp > 0 else 0

def load_data(start, end):
    df_m1 = pd.read_csv(DUKAS_CSV, header=None,
        names=["date","time","open","high","low","close","volume","v2","sp"],
        dtype={"date": str, "time": str})
    df_m1["datetime"] = pd.to_datetime(df_m1["date"] + " " + df_m1["time"], format="%Y.%m.%d %H:%M")
    df_m1.set_index("datetime", inplace=True)
    df_m1 = df_m1[["open","high","low","close","volume"]]
    df_m1 = df_m1[(df_m1.index >= start) & (df_m1.index <= end)]
    df_m15 = df_m1.resample("15min").agg({"open":"first","high":"max","low":"min","close":"last","volume":"sum"}).dropna()
    df_h4  = df_m1.resample("4h").agg({"open":"first","high":"max","low":"min","close":"last","volume":"sum"}).dropna()
    return df_m15, df_h4

def run_bt(df, p, initial_cap=INITIAL_CAP):
    trades=[]; equity=initial_cap; position=None; pending=None
    trades_today=0; last_date=None
    tp_mult=p["tp_mult"]; be_mult=p["be_mult"]
    trail_act=p["trail_act"]; trail_dist=p["trail_dist"]; exit_bars=p["exit_bars"]

    for i in range(1, len(df)):
        row=df.iloc[i]; dt=df.index[i]; date=dt.date()
        bh=row["high"]; bl=row["low"]
        if date != last_date: trades_today=0; last_date=date

        if position is not None:
            d=position["direction"]; position["bars_held"]+=1
            entry=position["entry"]; sl_d=position["sl_d"]
            gain = bh - entry if d=="long" else entry - bl
            if not position["be_done"] and gain >= be_mult * sl_d:
                position["sl"]=entry; position["be_done"]=True
            if trail_act > 0:
                if not position["ts_active"] and gain >= trail_act * sl_d:
                    position["ts_active"] = True
                if position["ts_active"]:
                    ts = trail_dist * sl_d
                    if d=="long":
                        nsl = bh - ts
                        if nsl > position["sl"]: position["sl"] = nsl
                    else:
                        nsl = bl + ts
                        if nsl < position["sl"]: position["sl"] = nsl
            sl=position["sl"]; tp=position["tp"]; ep=et=None
            if d=="long":
                if bl<=sl: ep,et=sl,"SL"
                elif bh>=tp: ep,et=tp,"TP"
            else:
                if bh>=sl: ep,et=sl,"SL"
                elif bl<=tp: ep,et=tp,"TP"
            if ep is None and position["bars_held"]>=exit_bars:
                ep,et=row["close"],"TIME"
            if ep is not None:
                pnl=(ep-entry)/PIP*(1 if d=="long" else -1)*pip_val()*position["lots"]
                equity+=pnl
                trades.append({"pnl":round(pnl,2),"exit_type":et,"equity":round(equity,2),
                                "direction":d,"entry_dt":position["entry_dt"]})
                position=None

        if pending is not None and position is None:
            ep_p=pending["entry_price"]
            hit=(pending["direction"]=="long" and bh>=ep_p) or (pending["direction"]=="short" and bl<=ep_p)
            if hit:
                sl_d = max(float(pending["sl_dist"]), MIN_SL)
                tp_d = sl_d * tp_mult
                lots = calc_lots(equity, sl_d)
                if lots > 0:
                    sgn=1 if pending["direction"]=="long" else -1
                    position={"direction":pending["direction"],"entry":ep_p,
                              "sl":ep_p-sgn*sl_d,"tp":ep_p+sgn*tp_d,"lots":lots,
                              "bars_held":0,"be_done":False,"ts_active":False,
                              "sl_d":sl_d,"entry_dt":dt}
                    trades_today+=1
                pending=None
            else:
                pending["bars_alive"]+=1
                if pending["bars_alive"]>=ORDER_EXPIRY: pending=None

        if position is not None or pending is not None: continue
        if dt.hour < SESSION_START or dt.hour >= SESSION_END: continue
        if dt.hour in BAD_HOURS: continue
        if dt.weekday() >= 5 or (dt.weekday()==4 and dt.hour>=20): continue
        if trades_today >= MAX_TRADES_DAY: continue

        sig=None
        if bool(row.get("long_signal")) and pd.notna(row.get("entry_price")): sig="long"
        elif bool(row.get("short_signal")) and pd.notna(row.get("entry_price")): sig="short"
        if sig and row["sl"] > MAX_SL_FILTER: continue
        if sig:
            pending={"direction":sig,"entry_price":row["entry_price"],
                     "sl_dist":row["sl"],"tp_dist":row["tp"],"bars_alive":0}

    if not trades: return None
    t=pd.DataFrame(trades)
    n=len(t); wr=(t["pnl"]>0).mean()*100; pnl=t["pnl"].sum()
    wins=t.loc[t["pnl"]>0,"pnl"]; losss=t.loc[t["pnl"]<0,"pnl"]
    pf=wins.sum()/abs(losss.sum()) if len(losss)>0 and losss.sum()!=0 else 0
    dd=(t["equity"].cummax()-t["equity"]).max()
    return {"n":n,"pnl":round(pnl,0),"wr":round(wr,1),"pf":round(pf,2),
            "dd":round(dd,0),"dd_pct":round(dd/initial_cap*100,1),
            "avg_w":round(wins.mean(),0) if len(wins)>0 else 0,
            "avg_l":round(losss.mean(),0) if len(losss)>0 else 0,
            "exits":t["exit_type"].value_counts().to_dict(),
            "trades_df":t}

def yearly_stats(t):
    t=t.copy(); t["year"]=pd.to_datetime(t["entry_dt"]).dt.year
    rows=[]
    for yr, g in t.groupby("year"):
        eq=g["equity"]; pnl=g["pnl"].sum()
        wr=(g["pnl"]>0).mean()*100
        dd=(eq.cummax()-eq).max()
        rows.append({"Ano":yr,"Trades":len(g),"P&L":f"${pnl:,.0f}","WR":f"{wr:.1f}%","DD":f"${dd:,.0f}"})
    return pd.DataFrame(rows)

def walk_forward(df, p):
    # Train 2020-2022, Test 2023-2025
    train_start=datetime(2020,1,1); train_end=datetime(2022,12,31)
    test_start=datetime(2023,1,1);  test_end=datetime(2025,12,31)
    df_train=df[(df.index>=train_start)&(df.index<=train_end)]
    df_test =df[(df.index>=test_start) &(df.index<=test_end)]
    r_train=run_bt(df_train, p)
    r_test =run_bt(df_test,  p)
    return r_train, r_test

def monte_carlo(trades_df, n_sim=500, seed=42):
    """Aleatoriza el orden de los trades y calcula DD en cada simulación."""
    random.seed(seed); np.random.seed(seed)
    pnls = trades_df["pnl"].values
    dds=[]
    for _ in range(n_sim):
        shuffled=np.random.permutation(pnls)
        eq=INITIAL_CAP + np.cumsum(shuffled)
        eq_full=np.concatenate([[INITIAL_CAP], eq])
        dd=(np.maximum.accumulate(eq_full)-eq_full).max()
        dds.append(dd/INITIAL_CAP*100)
    dds=np.array(dds)
    return {"p50":round(np.percentile(dds,50),1),
            "p90":round(np.percentile(dds,90),1),
            "p95":round(np.percentile(dds,95),1),
            "p99":round(np.percentile(dds,99),1),
            "mean":round(dds.mean(),1)}

def sensitivity(df, p, param, values):
    """Varía un parámetro y registra P&L y PF."""
    rows=[]
    for v in values:
        pp={**p, param:v}
        r=run_bt(df, pp)
        if r: rows.append({param:v,"P&L":f"${r['pnl']:,.0f}","WR":f"{r['wr']}%","PF":r['pf'],"DD":f"{r['dd_pct']}%"})
    return pd.DataFrame(rows)

def fmt_exits(e):
    sl=e.get("SL",0); tp=e.get("TP",0); tm=e.get("TIME",0); tot=sl+tp+tm
    return f"SL:{sl}({sl/tot*100:.0f}%)  TP:{tp}({tp/tot*100:.0f}%)  TIME:{tm}({tm/tot*100:.0f}%)"

def main():
    print("Cargando datos 2020-2025...")
    start=datetime(2020,1,1); end=datetime(2025,12,31)
    df_m15, df_h4 = load_data(start, end)
    print("Calculando indicadores...")
    df = add_indicators(df_m15.copy(), df_h4.copy())
    df = generate_signals(df)

    lines=[]
    lines.append("# GBPJPY M15 — Informe de Estrategias")
    lines.append(f"\n> Generado: {datetime.now().strftime('%Y-%m-%d %H:%M')} | Periodo: 2020–2025 | Capital: $50.000 | Riesgo/trade: 0.5%")
    lines.append("\n---\n")

    for key, p in STRATEGIES.items():
        print(f"\nAnalizando {p['label']}...")
        r_full = run_bt(df, p)
        if not r_full:
            print("  Sin trades"); continue
        t = r_full["trades_df"]

        # ── Walk-forward ──────────────────────────────────────────────────────
        print("  Walk-forward...")
        r_train, r_test = walk_forward(df, p)

        # ── Monte Carlo ───────────────────────────────────────────────────────
        print("  Monte Carlo (500 sim)...")
        mc = monte_carlo(t)

        # ── Sensibilidad ──────────────────────────────────────────────────────
        print("  Sensibilidad de parametros...")
        base_tp = p["tp_mult"]
        sens_tp = sensitivity(df, p, "tp_mult", [base_tp*0.7, base_tp*0.85, base_tp, base_tp*1.15, base_tp*1.3])
        base_be = p["be_mult"]
        sens_be = sensitivity(df, p, "be_mult", [max(0.3,base_be*0.7), base_be*0.85, base_be, base_be*1.15, base_be*1.3])

        # ── Anuales ───────────────────────────────────────────────────────────
        yr = yearly_stats(t)

        # ── Redactar sección ──────────────────────────────────────────────────
        lines.append(f"\n---\n\n## {p['label']}")
        lines.append(f"\n{p['desc']}\n")

        lines.append("\n### Parametros")
        lines.append(f"| Parametro | Valor |")
        lines.append(f"|-----------|-------|")
        lines.append(f"| TP multiplo | {p['tp_mult']}x SL |")
        lines.append(f"| Break-Even activa tras | {p['be_mult']}x SL de ganancia |")
        lines.append(f"| Trailing stop | {'Si — activa a '+str(p['trail_act'])+'x SL, dist '+str(p['trail_dist'])+'x SL' if p['trail_act']>0 else 'No'} |")
        lines.append(f"| Salida por tiempo | {p['exit_bars']} barras ({p['exit_bars']*15//60}h {p['exit_bars']*15%60}min) |")
        lines.append(f"| Filtro SL maximo | 30 pips |")
        lines.append(f"| Sesion operativa | 07:00–18:00 UTC (excluye hora 08:00) |")
        lines.append(f"| Riesgo por trade | 0.5% del capital |")

        lines.append("\n### Resultados Completos (2020–2025)")
        lines.append(f"| Metrica | Valor |")
        lines.append(f"|---------|-------|")
        lines.append(f"| Capital inicial | $50.000 |")
        lines.append(f"| Capital final | ${INITIAL_CAP+r_full['pnl']:,.0f} |")
        lines.append(f"| P&L total | **${r_full['pnl']:,.0f}** (+{r_full['pnl']/INITIAL_CAP*100:.0f}%) |")
        lines.append(f"| Rendimiento anualizado | ~{(((INITIAL_CAP+r_full['pnl'])/INITIAL_CAP)**(1/5.5)-1)*100:.1f}% |")
        lines.append(f"| Operaciones totales | {r_full['n']} ({r_full['n']/5.5:.0f}/ano aprox.) |")
        lines.append(f"| Win Rate | **{r_full['wr']}%** |")
        lines.append(f"| Profit Factor | **{r_full['pf']}** |")
        lines.append(f"| Max Drawdown | **${r_full['dd']:,.0f} ({r_full['dd_pct']}%)** |")
        lines.append(f"| Media ganancia | ${r_full['avg_w']:,.0f} |")
        lines.append(f"| Media perdida | ${r_full['avg_l']:,.0f} |")
        lines.append(f"| Ratio gan/perd | {abs(r_full['avg_w']/r_full['avg_l']):.2f}x |")
        lines.append(f"| Tipos de salida | {fmt_exits(r_full['exits'])} |")

        lines.append("\n### Rendimiento por Ano")
        lines.append(yr.to_markdown(index=False))

        lines.append("\n### Pruebas de Robustez\n")

        lines.append("#### 1. Walk-Forward (Train 2020–2022 / Test 2023–2025)")
        lines.append(f"| Periodo | Trades | P&L | WR | PF | DD |")
        lines.append(f"|---------|--------|-----|----|----|-----|")
        if r_train:
            lines.append(f"| **IN-SAMPLE** (2020–2022) | {r_train['n']} | ${r_train['pnl']:,.0f} | {r_train['wr']}% | {r_train['pf']} | {r_train['dd_pct']}% |")
        if r_test:
            lines.append(f"| **OUT-OF-SAMPLE** (2023–2025) | {r_test['n']} | ${r_test['pnl']:,.0f} | {r_test['wr']}% | {r_test['pf']} | {r_test['dd_pct']}% |")
        if r_train and r_test:
            degradation = (r_train['pf'] - r_test['pf']) / r_train['pf'] * 100
            verdict = "SUPERA" if r_test['pf'] >= r_train['pf'] * 0.75 else "DEGRADACION SIGNIFICATIVA"
            lines.append(f"\n> **Veredicto walk-forward:** {verdict} — degradacion PF: {degradation:.1f}%")

        lines.append("\n#### 2. Monte Carlo — Distribucion de Drawdown (500 simulaciones)")
        lines.append(f"| Percentil | DD Esperado |")
        lines.append(f"|-----------|-------------|")
        lines.append(f"| Mediana (P50) | {mc['p50']}% |")
        lines.append(f"| Percentil 90 | {mc['p90']}% |")
        lines.append(f"| Percentil 95 | {mc['p95']}% |")
        lines.append(f"| Peor caso (P99) | {mc['p99']}% |")
        lines.append(f"\n> **Capital minimo recomendado** para soportar el DD P95: ${INITIAL_CAP*(1+mc['p95']/100)/(1-0.3):.0f}")

        lines.append("\n#### 3. Sensibilidad — TP Multiplicador")
        lines.append(sens_tp.to_markdown(index=False))

        lines.append("\n#### 4. Sensibilidad — Break-Even Multiplicador")
        lines.append(sens_be.to_markdown(index=False))

        if r_train and r_test:
            overall_robust = r_test['pf'] >= 1.2 and r_test['pnl'] > 0
            lines.append(f"\n### Conclusion de Robustez")
            lines.append(f"{'ESTRATEGIA ROBUSTA' if overall_robust else 'REVISAR — posible sobreajuste'}: ")
            lines.append(f"- Out-of-sample PF = {r_test['pf']} ({'>=1.2 OK' if r_test['pf']>=1.2 else '<1.2 ALERTA'})")
            lines.append(f"- Out-of-sample P&L = ${r_test['pnl']:,.0f} ({'positivo OK' if r_test['pnl']>0 else 'negativo ALERTA'})")
            lines.append(f"- DD P95 Monte Carlo = {mc['p95']}% ({'<=30% OK' if mc['p95']<=30 else '>30% ALERTA'})")

    # ── Comparativa final ─────────────────────────────────────────────────────
    lines.append("\n---\n\n## Comparativa de Estrategias")
    lines.append(f"\n| Metrica | Estrategia A (Balanceada) | Estrategia B (Max Rendimiento) | Objetivo |")
    lines.append(f"|---------|--------------------------|-------------------------------|----------|")

    results={}
    for key, p in STRATEGIES.items():
        r=run_bt(df, p)
        if r: results[key]=r

    if len(results)==2:
        rA=results["A_Balanceada"]; rB=results["B_MaxRendimiento"]
        lines.append(f"| P&L 5 anos | ${rA['pnl']:,.0f} | ${rB['pnl']:,.0f} | > $50k |")
        lines.append(f"| Win Rate | {rA['wr']}% | {rB['wr']}% | > 20% |")
        lines.append(f"| Profit Factor | {rA['pf']} | {rB['pf']} | > 1.4 |")
        lines.append(f"| Max Drawdown | {rA['dd_pct']}% | {rB['dd_pct']}% | < 25% |")
        lines.append(f"| Trades/ano | ~{rA['n']//5} | ~{rB['n']//5} | — |")
        lines.append(f"| TP Ratio | {STRATEGIES['A_Balanceada']['tp_mult']}x | {STRATEGIES['B_MaxRendimiento']['tp_mult']}x | — |")
        lines.append(f"\n**Recomendacion:**")
        lines.append(f"- Cuenta < $75k o trader conservador: **Estrategia A**")
        lines.append(f"- Cuenta > $75k o busca maximo crecimiento: **Estrategia B**")

    lines.append("\n---\n")
    lines.append("*Informe generado automaticamente. El rendimiento pasado no garantiza resultados futuros.*")

    report = "\n".join(lines)
    os.makedirs("reports", exist_ok=True)
    with open("reports/GBPJPY_Strategy_Report.md", "w", encoding="utf-8") as f:
        f.write(report)
    print("\nInforme guardado en: reports/GBPJPY_Strategy_Report.md")

if __name__ == "__main__":
    main()
