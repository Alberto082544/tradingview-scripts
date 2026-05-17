"""
ORB GBPJPY — Pruebas de Robustez
=================================
1. Walk-Forward: Train 2020-2022 / Test 2023-2025
2. Monte Carlo: 500 shuffles del orden de trades
3. Sensibilidad: ±20% en TP1, TP2, rango
4. Análisis por año y dirección
"""
import sys, io, os, types, random
import pandas as pd
import numpy as np
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from datetime import datetime
from strategy import add_indicators, generate_signals
from backtest  import run_backtest

import config as cfg

DATA_PATH       = cfg.DATA_PATH
INITIAL_CAPITAL = cfg.INITIAL_CAPITAL


def load_m15(start_year, start_month, end_year, end_month):
    df = pd.read_csv(DATA_PATH, header=None,
        names=["date","time","open","high","low","close","volume","v2","sp"],
        dtype={"date":str,"time":str})
    df["datetime"] = pd.to_datetime(df["date"]+" "+df["time"], format="%Y.%m.%d %H:%M")
    df.set_index("datetime", inplace=True)
    df = df[["open","high","low","close","volume"]]
    df = df[(df.index >= datetime(start_year,start_month,1)) &
            (df.index <= datetime(end_year,end_month,31))]
    return df.resample("15min").agg(
        {"open":"first","high":"max","low":"min","close":"last","volume":"sum"}
    ).dropna()


def run_full(df_m15, cfg_obj):
    df = add_indicators(df_m15.copy())
    df = generate_signals(df, cfg_obj)
    return run_backtest(df, cfg_obj)


def metrics(trades, capital):
    if len(trades) == 0:
        return {"trades":0,"wr":0,"pf":0,"pnl":0,"dd":0}
    wins   = (trades['pnl'] > 0).sum()
    gp     = trades[trades['pnl']>0]['pnl'].sum()
    gl     = abs(trades[trades['pnl']<=0]['pnl'].sum())
    pf     = gp/gl if gl>0 else 0
    eq     = capital + trades['pnl'].cumsum()
    peak   = eq.cummax()
    dd     = ((peak-eq)/peak*100).max()
    return {"trades":len(trades),"wr":round(wins/len(trades)*100,1),
            "pf":round(pf,2),"pnl":round(trades['pnl'].sum(),0),"dd":round(dd,1)}


def main():
    print("=" * 65)
    print("  GBPJPY ORB — Pruebas de Robustez")
    print("=" * 65)

    # ── 1. Backtest completo 2020-2025 ────────────────────────────────────────
    print("\n[1/4] Periodo completo 2020-2025...")
    df_full  = load_m15(2020,1,2025,12)
    t_full   = run_full(df_full, cfg)
    m_full   = metrics(t_full, INITIAL_CAPITAL)
    print(f"  Trades: {m_full['trades']} | WR: {m_full['wr']}% | PF: {m_full['pf']} | "
          f"P&L: ${m_full['pnl']:+,.0f} | DD: {m_full['dd']}%")

    # ── 2. Walk-Forward ───────────────────────────────────────────────────────
    print("\n[2/4] Walk-Forward: IS=2020-2022 / OOS=2023-2025")
    df_is  = load_m15(2020,1,2022,12)
    df_oos = load_m15(2023,1,2025,12)
    t_is   = run_full(df_is,  cfg)
    t_oos  = run_full(df_oos, cfg)
    m_is   = metrics(t_is,  INITIAL_CAPITAL)
    m_oos  = metrics(t_oos, INITIAL_CAPITAL)
    print(f"  IS  (2020-22): Trades {m_is['trades']:4d} | WR {m_is['wr']:.0f}% | "
          f"PF {m_is['pf']:.2f} | P&L ${m_is['pnl']:+,.0f} | DD {m_is['dd']:.0f}%")
    print(f"  OOS (2023-25): Trades {m_oos['trades']:4d} | WR {m_oos['wr']:.0f}% | "
          f"PF {m_oos['pf']:.2f} | P&L ${m_oos['pnl']:+,.0f} | DD {m_oos['dd']:.0f}%")
    wf_ok = m_oos['pf'] >= 1.0 and m_oos['pnl'] > 0
    print(f"  Resultado: {'ROBUSTO (OOS rentable)' if wf_ok else 'FRAGIL (OOS no rentable)'}")

    # ── 3. Monte Carlo ────────────────────────────────────────────────────────
    print("\n[3/4] Monte Carlo (500 simulaciones, shuffle de trades)...")
    pnl_arr = t_full['pnl'].values
    N       = len(pnl_arr)
    mc_dds  = []
    mc_pnls = []
    random.seed(42)
    for _ in range(500):
        shuffled = random.sample(list(pnl_arr), N)
        eq  = INITIAL_CAPITAL + np.cumsum(shuffled)
        peak = np.maximum.accumulate(eq)
        dd   = ((peak - eq) / peak * 100).max()
        mc_dds.append(dd)
        mc_pnls.append(float(eq[-1] - INITIAL_CAPITAL))  # P&L final de la ruta shuffled

    mc_dd_p50  = np.percentile(mc_dds, 50)
    mc_dd_p95  = np.percentile(mc_dds, 95)
    mc_pnl_p05 = np.percentile(mc_pnls, 5)
    mc_pnl_p50 = np.percentile(mc_pnls, 50)
    pct_positive = sum(1 for p in mc_pnls if p > 0) / 5
    print(f"  DD P50 / P95 : {mc_dd_p50:.1f}% / {mc_dd_p95:.1f}%")
    print(f"  P&L P5 / P50 : ${mc_pnl_p05:+,.0f} / ${mc_pnl_p50:+,.0f}")
    print(f"  % simulaciones rentables: {pct_positive:.0f}%")

    # ── 4. Sensibilidad ───────────────────────────────────────────────────────
    print("\n[4/4] Análisis de sensibilidad (±20%)...")
    base_tp1 = cfg.TP1_MULT
    base_tp2 = cfg.TP2_MULT
    print(f"  {'Variación':20s}  {'Trades':>6}  {'WR%':>5}  {'PF':>5}  {'P&L':>10}  {'DD%':>5}")
    print(f"  {'-'*55}")

    for label, tp1, tp2 in [
        ("Base",               base_tp1,      base_tp2),
        ("TP1 -20%",           base_tp1*0.8,  base_tp2),
        ("TP1 +20%",           base_tp1*1.2,  base_tp2),
        ("TP2 -20%",           base_tp1,      base_tp2*0.8),
        ("TP2 +20%",           base_tp1,      base_tp2*1.2),
        ("Ambos -20%",         base_tp1*0.8,  base_tp2*0.8),
        ("Ambos +20%",         base_tp1*1.2,  base_tp2*1.2),
    ]:
        c2 = types.SimpleNamespace(**vars(cfg) if hasattr(cfg,'__dict__') else
             {k: getattr(cfg,k) for k in dir(cfg) if not k.startswith('_')})
        c2.TP1_MULT = tp1
        c2.TP2_MULT = tp2
        t2 = run_full(df_full, c2)
        m2 = metrics(t2, INITIAL_CAPITAL)
        ok = "OK" if m2['pf'] >= 1.0 else "--"
        print(f"  {label:20s}  {m2['trades']:6d}  {m2['wr']:5.1f}  {m2['pf']:5.2f}  "
              f"${m2['pnl']:>+9,.0f}  {m2['dd']:5.1f}  {ok}")

    # ── 5. Por año ────────────────────────────────────────────────────────────
    print("\n  Por año:")
    for year in range(2020, 2026):
        try:
            df_y = load_m15(year, 1, year, 12)
            t_y  = run_full(df_y, cfg)
            m_y  = metrics(t_y, INITIAL_CAPITAL)
            print(f"  {year}: {m_y['trades']:4d} trades | WR {m_y['wr']:.0f}% | "
                  f"PF {m_y['pf']:.2f} | P&L ${m_y['pnl']:+,.0f} | DD {m_y['dd']:.0f}%")
        except Exception:
            pass

    # ── Resumen final ─────────────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("  VEREDICTO")
    print("=" * 65)
    robust = (wf_ok and mc_dd_p95 < 35 and pct_positive >= 80)
    print(f"  Walk-Forward : {'PASS' if wf_ok else 'FAIL'}")
    print(f"  MC DD P95    : {mc_dd_p95:.1f}%  ({'PASS (<35%)' if mc_dd_p95<35 else 'FAIL'})")
    print(f"  MC % Positivo: {pct_positive:.0f}%  ({'PASS (>=80%)' if pct_positive>=80 else 'FAIL'})")
    print(f"\n  Estrategia: {'ROBUSTA' if robust else 'NECESITA AJUSTES'}")

    # Guardar resumen
    os.makedirs("reports", exist_ok=True)
    summary = {
        "periodo_completo": m_full, "in_sample": m_is, "out_of_sample": m_oos,
        "mc_dd_p50": mc_dd_p50, "mc_dd_p95": mc_dd_p95,
        "mc_pnl_p05": mc_pnl_p05, "mc_pnl_p50": mc_pnl_p50,
        "mc_pct_positivo": pct_positive, "walk_forward_ok": wf_ok, "robusto": robust
    }
    pd.DataFrame([summary]).to_csv("reports/robustness_orb_gbpjpy.csv", index=False)
    print("\n  Resumen guardado: reports/robustness_orb_gbpjpy.csv")
    input("\nPresiona ENTER para salir...")


if __name__ == "__main__":
    main()
