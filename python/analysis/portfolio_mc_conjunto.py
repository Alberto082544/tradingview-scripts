"""
MC conjunto del portfolio Phase 1 con correlaciones REALES y sizing actualizado.

Bots y sizing real (2026-05-22):
  - AUDCAD Ranger-C Stoch:  LotRiskPct=0.4 (bajado hoy)
  - AUDNZD Ranger-C v3:     LotRiskPct=0.5 (EA real Stoch K<15)
  - GBPUSD MA Cross v1:     LotRiskPct=0.5
  - EMA9_VWAP NAS100:       LotRiskPct=0.4 (bajado hoy)

Capital backtest: $50.000 (estandar para comparar metricas).

Calcula:
  1. Equity diaria de cada bot
  2. Correlaciones reales (returns diarios)
  3. DD historico AGREGADO (orden real)
  4. Monte Carlo: re-shuffle trades de cada bot independientemente
     y recalcular DD agregado 2000 veces
  5. Compara con suma ingenua de DDs individuales (beneficio diversificacion)
  6. Veredicto vs limite prop firm 10%
"""
import os
import sys
import warnings

warnings.filterwarnings("ignore", category=UserWarning)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import numpy as np
import pandas as pd

CAPITAL = 50_000.0
MC_RUNS = 2000
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "reports")


def calc_dd_pct(equity_series, initial=CAPITAL):
    """DD max % sobre serie de equity acumulada."""
    eq = np.asarray(equity_series, dtype=float)
    peak = np.maximum.accumulate(eq)
    dd = (eq - peak) / peak
    return abs(float(dd.min()) * 100.0)


def cargar_bot(name, modulo, df_path, params, pip, pip_val):
    """Ejecuta backtest y devuelve DataFrame con trades."""
    df_raw = pd.read_csv(df_path, index_col=0, parse_dates=True)
    if modulo == "ranger_c_audcad":
        from strategies.ranger_c_audcad_m15 import add_indicators, run_backtest
        df = add_indicators(df_raw, params)
        trades = run_backtest(df, params, CAPITAL)
    elif modulo == "ranger_c_audnzd_stoch":
        from strategies.ranger_c_audnzd_stoch import add_indicators, run_backtest
        df = add_indicators(df_raw, params)
        trades = run_backtest(df, params, CAPITAL)
    elif modulo == "ma_cross":
        from strategies.ma_cross_m15 import add_indicators, run_backtest
        df = add_indicators(df_raw, params)
        trades = run_backtest(df, params, CAPITAL, pip, pip_val)
    elif modulo == "ema9_vwap_rsi":
        from strategies.ema9_vwap_rsi import add_indicators, run_backtest
        df = add_indicators(df_raw, params)
        trades = run_backtest(df, params, CAPITAL, pip, pip_val)
    else:
        raise ValueError(f"Modulo desconocido: {modulo}")

    if len(trades) == 0:
        return None
    trades = trades.copy()
    trades["exit_dt"] = pd.to_datetime(trades["exit_dt"])
    trades["bot"] = name
    return trades


def equity_diaria_por_bot(trades, fecha_min, fecha_max, capital=CAPITAL):
    """Equity diaria sobre rango de fechas comun."""
    df = trades.copy()
    df["fecha"] = df["exit_dt"].dt.normalize()
    pnl_diario = df.groupby("fecha")["pnl"].sum()

    rango = pd.date_range(fecha_min, fecha_max, freq="D")
    pnl_d = pnl_diario.reindex(rango, fill_value=0.0)
    equity = capital + pnl_d.cumsum()
    return equity


def main():
    # Definicion de bots con sizing REAL actual
    bots = [
        {
            "name": "AUDCAD",
            "modulo": "ranger_c_audcad",
            "df_path": os.path.join(DATA_DIR, "AUDCAD_M15_histdata.csv"),
            "pip": 0.0001, "pip_val": 7.3,
            "lotrisk_real": 0.4,
            "params_base": {
                'BB_Period':20,'BB_StdDev':2.0,'RSI_Period':14,'ADX_H4_Period':14,'ATR_Period':14,
                'Stoch_K':5,'Stoch_D':3,'ADX_H4_Max':20,'RSI_Long_Max':40,'RSI_Short_Min':60,
                'RSI_Confirm':1,'StochMode':2,'Stoch_Long_Max':20,'Stoch_Short_Min':75,
                'BB_Mid_TP':0,'MinSLPips':20,'TrailDistPips':8,'ExitBars':24,
                'SL_ATR_Mult':1.5,'MaxSLPips':999,'TP_ATR_Mult':0,'TrailActivate':0.5,
                'SessionStart':0,'SessionEnd':23,'BadHour':-1,'MaxTradesDay':5,
                'MaxLots':4.0,
            },
        },
        {
            "name": "AUDNZD v3",
            "modulo": "ranger_c_audnzd_stoch",
            "df_path": os.path.join(DATA_DIR, "AUDNZD_M15_histdata.csv"),
            "pip": 0.0001, "pip_val": 6.0,
            "lotrisk_real": 0.5,
            "params_base": {
                'BB_Period':20,'BB_StdDev':2.0,'RSI_Period':14,'ADX_H4_Period':14,'ATR_Period':14,
                'Stoch_K':5,'Stoch_D':3,'ADX_H4_Max':20,'RSI_Long_Max':45,'RSI_Short_Min':55,
                'RSI_Confirm':0,'StochMode':1,'Stoch_Long_Max':15,'Stoch_Short_Min':75,
                'BB_Mid_TP':0,'MinSLPips':20,'TrailDistPips':4,'ExitBars':32,
                'SL_ATR_Mult':1.5,'MaxSLPips':999,'TP_ATR_Mult':0,'TrailActivate':0.5,
                'SessionStart':0,'SessionEnd':23,'BadHour':8,'MaxTradesDay':5,
                'MaxLots':4.0,
            },
        },
        {
            "name": "GBPUSD",
            "modulo": "ma_cross",
            "df_path": os.path.join(DATA_DIR, "GBPUSD_M15_histdata.csv"),
            "pip": 0.0001, "pip_val": 10.0,
            "lotrisk_real": 0.5,
            "params_base": {
                'EMA_Fast':5,'SMA_Slow':34,'Dir_EMA_Fast':5,'Dir_SMA_Slow':34,
                'ATR_Period':14,'SL_ATR_Mult':1.0,'RR':3.0,
                'BE_Trigger':0.5,'BE_Offset':0.0001,
                'Trail_Start':1.5,'Trail_Dist':0.5,
                'MaxSpreadPips':3.0,'MaxLots':4.0,
            },
        },
        {
            "name": "NAS100",
            "modulo": "ema9_vwap_rsi",
            "df_path": os.path.join(DATA_DIR, "NAS100_proxy_M15_twelvedata.csv"),
            "pip": 1.0, "pip_val": 100.0,
            "lotrisk_real": 0.4,
            "params_base": {
                'EMA_Fast':9,'EMA_Mid':21,'RSI_Period':14,
                'RSI_Buy_Min':35,'RSI_Buy_Max':75,'RSI_Sell_Min':30,'RSI_Sell_Max':65,
                'ATR_Period':14,'SL_ATR_Mult':1.0,'MinSLPips':0.5,
                'BE_Mult':2.0,'TP1_Mult':2.0,'TP1_Pct':0.5,
                'Trail_EMA':1,'WickRatio':1.5,'MaxTradesDay':3,
                'SessionStart':0,'SessionEnd':23,
                'MaxLots':4.0,'Commission':0.0,
            },
        },
    ]

    print("=" * 80)
    print("  MC CONJUNTO PORTFOLIO PHASE 1 con sizing real")
    print(f"  Capital backtest: ${CAPITAL:,.0f} | MC runs: {MC_RUNS:,}")
    print("=" * 80)

    bot_trades = {}
    fecha_mins, fecha_maxs = [], []
    for b in bots:
        params = {**b["params_base"], "LotRiskPct": b["lotrisk_real"]}
        print(f"\n[{b['name']}] LotRisk={b['lotrisk_real']} | Backtest...")
        tr = cargar_bot(b["name"], b["modulo"], b["df_path"], params, b["pip"], b["pip_val"])
        if tr is None or len(tr) == 0:
            print(f"  Sin trades, skip")
            continue
        bot_trades[b["name"]] = tr
        fecha_mins.append(tr["exit_dt"].min())
        fecha_maxs.append(tr["exit_dt"].max())
        print(f"  N={len(tr):,} | PnL={tr['pnl'].sum():,.0f} | DD individual={calc_dd_pct(CAPITAL + tr['pnl'].cumsum()):.2f}%")

    fecha_inicio = max(fecha_mins).normalize()  # rango comun: max(min)
    fecha_fin = min(fecha_maxs).normalize()     # rango comun: min(max)
    print(f"\nRango comun: {fecha_inicio.date()} -> {fecha_fin.date()}")

    # Equity diaria por bot
    equities = {}
    for name, tr in bot_trades.items():
        # filtrar trades dentro del rango comun
        tr_filt = tr[(tr["exit_dt"] >= fecha_inicio) & (tr["exit_dt"] <= fecha_fin)]
        eq = equity_diaria_por_bot(tr_filt, fecha_inicio, fecha_fin)
        equities[name] = eq

    # DataFrame de equity diaria por bot
    df_eq = pd.DataFrame(equities)
    # Returns diarios
    df_ret = df_eq.pct_change().fillna(0)

    # Correlaciones
    corr = df_ret.corr()
    print(f"\n=== CORRELACIONES (returns diarios) ===")
    print(corr.round(4).to_string())

    # Portfolio: cada bot aporta su PnL diario. Capital total = sum capital individual
    n_bots = len(equities)
    capital_total = n_bots * CAPITAL  # simulamos n_bots * $50k = $200k portfolio
    pnl_diario_bots = df_eq.diff().fillna(0)  # PnL diario por bot
    pnl_diario_portfolio = pnl_diario_bots.sum(axis=1)
    equity_portfolio = capital_total + pnl_diario_portfolio.cumsum()
    dd_portfolio_real = calc_dd_pct(equity_portfolio, initial=capital_total)

    # DDs individuales y suma ingenua
    dds_individuales = {}
    for name, eq in equities.items():
        dds_individuales[name] = calc_dd_pct(eq, initial=CAPITAL)
    suma_ingenua = sum(dds_individuales.values())

    print(f"\n=== DD INDIVIDUAL vs CONJUNTO ===")
    for name, dd in dds_individuales.items():
        print(f"  {name:<12} DD: {dd:.2f}%")
    print(f"  {'SUMA INGENUA':<12} {suma_ingenua:.2f}%  (peor caso teorico)")
    print(f"  {'CONJUNTO REAL':<12} {dd_portfolio_real:.2f}%  (orden real, con correlaciones)")
    if suma_ingenua > 0:
        beneficio = 100 * (1 - dd_portfolio_real / suma_ingenua)
        print(f"  Beneficio diversificacion: {beneficio:.1f}% menos DD")

    # Monte Carlo: re-shuffle trades de cada bot
    print(f"\n=== MONTE CARLO ({MC_RUNS:,} iteraciones) ===")
    rng = np.random.default_rng(42)
    dd_dist = np.empty(MC_RUNS, dtype=float)
    for i in range(MC_RUNS):
        eqs_perm = {}
        for name, tr in bot_trades.items():
            tr_filt = tr[(tr["exit_dt"] >= fecha_inicio) & (tr["exit_dt"] <= fecha_fin)].copy()
            # permutar PnLs manteniendo fechas
            pnls = tr_filt["pnl"].values.copy()
            rng.shuffle(pnls)
            tr_filt["pnl"] = pnls
            eqs_perm[name] = equity_diaria_por_bot(tr_filt, fecha_inicio, fecha_fin)
        df_eq_perm = pd.DataFrame(eqs_perm)
        pnl_d_perm = df_eq_perm.diff().fillna(0)
        eq_port_perm = capital_total + pnl_d_perm.sum(axis=1).cumsum()
        dd_dist[i] = calc_dd_pct(eq_port_perm, initial=capital_total)

    p50 = float(np.percentile(dd_dist, 50))
    p95 = float(np.percentile(dd_dist, 95))
    p99 = float(np.percentile(dd_dist, 99))
    print(f"  DD agregado historico: {dd_portfolio_real:.2f}%")
    print(f"  MC P50: {p50:.2f}%")
    print(f"  MC P95: {p95:.2f}%")
    print(f"  MC P99: {p99:.2f}%")

    # Veredicto prop firm
    print(f"\n=== VEREDICTO PROP FIRM (limite DD total tipico 10%) ===")
    if p95 < 10.0:
        verdict = f"PASA: P95={p95:.2f}% < 10%"
    elif p95 < 15.0:
        verdict = f"AJUSTADO: P95={p95:.2f}% (entre 10-15%, riesgo moderado)"
    else:
        verdict = f"FALLA: P95={p95:.2f}% > 15% (peligro)"
    print(f"  {verdict}")
    if 2 * dd_portfolio_real > 0:
        regla_mc = p95 < 2 * dd_portfolio_real
        print(f"  Regla MC P95 < 2x DD historico ({2*dd_portfolio_real:.2f}%): {'PASA' if regla_mc else 'FALLA'}")

    # Stats agregadas
    pnl_total = pnl_diario_portfolio.sum()
    n_dias = (fecha_fin - fecha_inicio).days
    n_years = n_dias / 365.25
    ann_pct = (pnl_total / capital_total) / n_years * 100
    print(f"\n=== STATS AGREGADAS ===")
    print(f"  Periodo: {n_years:.1f} anyos")
    print(f"  PnL total portfolio: ${pnl_total:,.0f}")
    print(f"  Annual: {ann_pct:.2f}% sobre ${capital_total:,.0f}")

    # Guardar resultados
    out_corr = os.path.join(OUT_DIR, "portfolio_correlations_22may.csv")
    out_mc = os.path.join(OUT_DIR, "portfolio_mc_dd_22may.csv")
    corr.to_csv(out_corr)
    pd.DataFrame({"dd_pct": dd_dist}).to_csv(out_mc, index=False)
    print(f"\n  Reports: {out_corr}\n  Reports: {out_mc}")


if __name__ == "__main__":
    main()
