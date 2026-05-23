"""
Análisis de correlación y DD agregado del portfolio Phase 1.

Calcula:
- Equity curves diarias de cada bot validado
- Matriz de correlación entre returns diarios
- DD individual vs DD agregado del portfolio
- Margen DD disponible para subir lotes / rescatar EURUSD v1.0 / añadir AUDCAD

Ventana: OOS 2022-2025 (4 años, idéntica para todos los bots).
Capital: $15,000 (cuenta de fondeo real).

NOTA: XAUUSD ORB no se incluye — no hay datos locales. Se añadirá cuando
descarguemos M15 de XAUUSD desde Dukascopy o similar.
"""
import os
import sys
import warnings

warnings.filterwarnings("ignore", category=UserWarning)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Forzar UTF-8 en stdout (Windows cp1252 peta con caracteres no-ASCII)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import numpy as np
import pandas as pd

# Configuración común
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "reports")
CAPITAL_PORTFOLIO = 15_000.0  # capital de la cuenta de fondeo real
OOS_START = "2022-01-01"
OOS_END = "2025-12-31"

os.makedirs(OUT_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# Configuración por bot (parámetros validados extraídos del REGISTRO)
# ---------------------------------------------------------------------------

BOTS = [
    {
        "id": "AUDNZD_RangerC",
        "data_file": "AUDNZD_M15_histdata.csv",
        "lot_risk_pct": 0.5,  # según registro v3.0
        "strategy": "ranger_c_audnzd_stoch",
        "params": {
            # Variante "C: Stoch solo + ADX<20" del AB test 2026-05-17
            "ADX_H4_Max": 20,
            "StochMode": 1,        # Stoch solo (sin RSI), igual que v3.0 operativa
            "Stoch_K": 5,
            "Stoch_D": 3,
            "Stoch_Long_Max": 25,
            "Stoch_Short_Min": 75,
            "BB_Mid_TP": 0,
            "MinSLPips": 20,
            "TrailDistPips": 8,
            "ExitBars": 32,
        },
    },
    {
        "id": "EURUSD_MACross",
        "data_file": "EURUSD_M15_histdata.csv",
        "lot_risk_pct": 0.4,  # según registro v2.0
        "strategy": "ma_cross_m15",
        "pair": "EURUSD",
        "params": {
            "EMA_Fast": 8,
            "SMA_Slow": 34,
            "Dir_EMA_Fast": 8,
            "Dir_SMA_Slow": 34,
            "ATR_Period": 14,
            "SL_ATR_Mult": 2.0,
            "RR": 2.5,
            "BE_Trigger": 0.5,
            "BE_Offset": 0.0002,
            "Trail_Start": 1.5,
            "Trail_Dist": 0.5,
            "MaxSpreadPips": 3.0,
            "LotRiskPct": 0.5,  # se reescala al final
            "MaxLots": 4.0,
        },
    },
    {
        "id": "NAS100_EMA9VWAP",
        "data_file": "NAS100_proxy_M15_twelvedata.csv",
        "lot_risk_pct": 0.5,  # según registro v1.0
        "strategy": "ema9_vwap_rsi",
        "params": None,  # usa DEFAULT_PARAMS
    },
    {
        "id": "AUDCAD_RangerC",
        "data_file": "AUDCAD_M15_histdata.csv",
        "lot_risk_pct": 0.5,  # conservador (top combo recomendaba 0.3-0.5)
        "strategy": "ranger_c_audcad_m15",
        "params": {
            # Top combo del 2026-05-18 (PF OOS 1.36, DD 5.8%, 12/12 anios+)
            "BB_Period": 20,
            "BB_StdDev": 2.0,
            "RSI_Period": 14,
            "ADX_H4_Period": 14,
            "ATR_Period": 14,
            "Stoch_K": 5,
            "Stoch_D": 3,
            "ADX_H4_Max": 20,
            "RSI_Long_Max": 40,
            "RSI_Short_Min": 60,
            "RSI_Confirm": 1,
            "StochMode": 2,
            "Stoch_Long_Max": 20,
            "Stoch_Short_Min": 75,
            "BB_Mid_TP": 0,
            "MinSLPips": 20,
            "TrailDistPips": 8,
            "ExitBars": 24,
            "SL_ATR_Mult": 1.5,
            "MaxSLPips": 999,
            "TP_ATR_Mult": 0,
            "TrailActivate": 0.5,
            "SessionStart": 0,
            "SessionEnd": 23,
            "BadHour": -1,
            "MaxTradesDay": 5,
            "MaxLots": 4.0,
        },
    },
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def trades_to_daily_equity(trades_df: pd.DataFrame, start_equity: float,
                           index: pd.DatetimeIndex) -> pd.Series:
    """Convierte trades (DataFrame) a serie de equity diaria.
    Equity al final de cada día = start_equity + cumsum(pnl de trades cerrados ese día).
    """
    if len(trades_df) == 0:
        return pd.Series(start_equity, index=index)
    exits = pd.to_datetime(trades_df["exit_dt"]).dt.normalize()
    pnls = trades_df["pnl"].astype(float).values
    daily_pnl = pd.Series(pnls, index=exits).groupby(level=0).sum()
    daily_pnl = daily_pnl.reindex(index, fill_value=0.0)
    equity = start_equity + daily_pnl.cumsum()
    return equity


def daily_index(start: str, end: str) -> pd.DatetimeIndex:
    return pd.date_range(start=start, end=end, freq="B")  # business days


def calc_max_dd_pct(equity: pd.Series) -> float:
    """DD máximo en %, respecto al peak previo."""
    if len(equity) == 0:
        return 0.0
    peak = equity.cummax()
    dd = (equity - peak) / peak
    return abs(float(dd.min()) * 100.0)


def annualised_return_pct(equity: pd.Series) -> float:
    if len(equity) < 2:
        return 0.0
    days = (equity.index[-1] - equity.index[0]).days
    if days <= 0:
        return 0.0
    total_ret = float(equity.iloc[-1] / equity.iloc[0])
    if total_ret <= 0:
        return 0.0
    return (total_ret ** (365.0 / days) - 1.0) * 100.0


# ---------------------------------------------------------------------------
# Backtests por bot (firmas distintas en cada strategy)
# ---------------------------------------------------------------------------

def run_audnzd(bot, df_raw):
    from strategies.ranger_c_audnzd_stoch import (
        add_indicators, run_backtest, DEFAULT_PARAMS,
    )
    params = {**DEFAULT_PARAMS, **bot["params"], "LotRiskPct": bot["lot_risk_pct"]}
    df = add_indicators(df_raw, params)
    df_oos = df.loc[OOS_START:OOS_END]
    trades = run_backtest(df_oos, params, initial_capital=CAPITAL_PORTFOLIO)
    return trades


def run_eurusd(bot, df_raw):
    from strategies.ma_cross_m15 import (
        add_indicators, run_backtest, PAIR_CONFIG,
    )
    cfg = PAIR_CONFIG[bot["pair"]]
    params = {**bot["params"], "LotRiskPct": bot["lot_risk_pct"]}
    df = add_indicators(df_raw, params)
    df_oos = df.loc[OOS_START:OOS_END]
    trades = run_backtest(df_oos, params, CAPITAL_PORTFOLIO, cfg["pip"], cfg["pip_val"])
    return trades


def run_nas100(bot, df_raw):
    from strategies.ema9_vwap_rsi import (
        add_indicators, run_backtest, DEFAULT_PARAMS,
    )
    base = DEFAULT_PARAMS if bot["params"] is None else bot["params"]
    params = {**base, "LotRiskPct": bot["lot_risk_pct"]}
    df = add_indicators(df_raw, params)
    df_oos = df.loc[OOS_START:OOS_END]
    trades = run_backtest(df_oos, params, CAPITAL_PORTFOLIO, pip=1.0, pip_val=100.0)
    return trades


def run_audcad(bot, df_raw):
    from strategies.ranger_c_audcad_m15 import (
        add_indicators, run_backtest,
    )
    params = {**bot["params"], "LotRiskPct": bot["lot_risk_pct"]}
    df = add_indicators(df_raw, params)
    df_oos = df.loc[OOS_START:OOS_END]
    trades = run_backtest(df_oos, params, CAPITAL_PORTFOLIO)
    return trades


RUNNERS = {
    "ranger_c_audnzd_stoch": run_audnzd,
    "ma_cross_m15": run_eurusd,
    "ema9_vwap_rsi": run_nas100,
    "ranger_c_audcad_m15": run_audcad,
}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 70)
    print("  ANALISIS DE CORRELACION Y DD AGREGADO - Portfolio Phase 1")
    print(f"  Ventana: {OOS_START} a {OOS_END} | Capital portfolio: ${CAPITAL_PORTFOLIO:,.0f}")
    print(f"  Cada bot simulado con LotRiskPct propio sobre ${CAPITAL_PORTFOLIO:,.0f}")
    print("=" * 70)

    idx = daily_index(OOS_START, OOS_END)

    equity_curves = {}
    individual_stats = {}

    for bot in BOTS:
        print(f"\n  -> {bot['id']}  (LotRiskPct {bot['lot_risk_pct']}%)")
        data_path = os.path.join(DATA_DIR, bot["data_file"])
        if not os.path.exists(data_path):
            print(f"    [!] Datos no encontrados: {data_path}, saltando.")
            continue

        # Cargar (algunos CSV tienen columna 'time' como index, otros sin nombre)
        try:
            df_raw = pd.read_csv(data_path, parse_dates=["time"], index_col="time")
        except (ValueError, KeyError):
            df_raw = pd.read_csv(data_path, index_col=0, parse_dates=True)

        if df_raw.index.min() > pd.Timestamp(OOS_START) or df_raw.index.max() < pd.Timestamp("2024-01-01"):
            print(f"    [!] Datos insuficientes ({df_raw.index.min()} a {df_raw.index.max()}), saltando.")
            continue

        runner = RUNNERS[bot["strategy"]]
        trades = runner(bot, df_raw)
        if not isinstance(trades, pd.DataFrame):
            trades = pd.DataFrame(trades, columns=[
                "entry_dt", "exit_dt", "direction", "pnl",
                "exit_type", "equity", "lots", "sl_pips",
            ])
        if len(trades) == 0:
            print("    [!] Sin trades, saltando.")
            continue

        # Equity individual = $15k + cumsum(pnl diario del bot).
        # Cada bot opera sobre el capital total con su LotRiskPct propio.
        equity = trades_to_daily_equity(trades, CAPITAL_PORTFOLIO, idx)
        equity_curves[bot["id"]] = equity

        dd_pct = calc_max_dd_pct(equity)
        ann_pct = annualised_return_pct(equity)
        total_pnl = float(equity.iloc[-1] - equity.iloc[0])
        individual_stats[bot["id"]] = {
            "trades": len(trades),
            "total_pnl": total_pnl,
            "ann_pct_on_slice": ann_pct,
            "dd_pct_on_slice": dd_pct,
            "lot_risk_pct": bot["lot_risk_pct"],
        }

        print(f"    Trades OOS: {len(trades)}  PnL: ${total_pnl:,.0f}  DD ind: {dd_pct:.1f}%  Ann (sobre su slice): {ann_pct:.1f}%")

    if len(equity_curves) < 2:
        print("\n  [X] Necesitamos al menos 2 bots con datos validos para correlacion.")
        return

    # ---- DataFrame combinado ----
    eq_df = pd.DataFrame(equity_curves)
    returns = eq_df.pct_change().fillna(0.0)

    # ---- Matriz correlación ----
    corr = returns.corr()

    # ---- Equity portfolio ----
    # Convertimos cada equity individual a PnL diario (delta sobre el capital inicial),
    # sumamos los PnLs diarios y reconstruimos la equity del portfolio.
    daily_pnl_each = eq_df.diff().fillna(eq_df.iloc[0] - CAPITAL_PORTFOLIO)
    portfolio_pnl_daily = daily_pnl_each.sum(axis=1)
    portfolio_eq = CAPITAL_PORTFOLIO + portfolio_pnl_daily.cumsum()
    portfolio_dd = calc_max_dd_pct(portfolio_eq)
    portfolio_ann = annualised_return_pct(portfolio_eq)
    portfolio_pnl = float(portfolio_eq.iloc[-1] - portfolio_eq.iloc[0])

    # ---- DD agregado "naive" (suma DDs individuales) ----
    naive_dd_sum = sum(s["dd_pct_on_slice"] for s in individual_stats.values())

    # ---- Output ----
    print("\n" + "=" * 70)
    print("  MATRIZ DE CORRELACION (returns diarios)")
    print("=" * 70)
    print(corr.round(3).to_string())

    print("\n" + "=" * 70)
    print("  ESTADISTICAS INDIVIDUALES (escaladas a $15k portfolio)")
    print("=" * 70)
    print(f"  {'Bot':<22} {'Trades':>7}  {'PnL OOS $':>12}  {'DD ind %':>9}  {'Ann %':>7}")
    for bot_id, s in individual_stats.items():
        print(f"  {bot_id:<22} {s['trades']:>7}  ${s['total_pnl']:>11,.0f}  {s['dd_pct_on_slice']:>8.2f}%  {s['ann_pct_on_slice']:>6.1f}%")

    print("\n" + "=" * 70)
    print("  PORTFOLIO (suma de equity curves)")
    print("=" * 70)
    print(f"  PnL total OOS ($15k):      ${portfolio_pnl:,.0f}")
    print(f"  Retorno anualizado:        {portfolio_ann:.2f}%")
    print(f"  DD maximo agregado real:   {portfolio_dd:.2f}%")
    print(f"  DD 'naive' (suma indiv):   {naive_dd_sum:.2f}%")
    print(f"  Beneficio diversificacion: {naive_dd_sum - portfolio_dd:.2f} pp"
          f" ({(1 - portfolio_dd/naive_dd_sum)*100:.0f}% menos DD)")

    # ---- Margen disponible ----
    print("\n" + "=" * 70)
    print("  MARGEN DD DISPONIBLE PARA PALANCAS")
    print("=" * 70)
    for limite in [5, 8, 10]:
        margen = limite - portfolio_dd
        factor_lote = limite / portfolio_dd if portfolio_dd > 0 else 0
        print(f"  Si DD limite {limite}%:  margen = {margen:.2f} pp"
              f"   ->  podriamos multiplicar lotes por {factor_lote:.2f}x"
              f"  (ganancia esperada: ${portfolio_pnl * factor_lote:,.0f}/4 anios)")

    # ---- Guardar reports ----
    corr.to_csv(os.path.join(OUT_DIR, "portfolio_correlation_matrix.csv"))
    eq_df.to_csv(os.path.join(OUT_DIR, "portfolio_equity_curves_daily.csv"))

    summary = {
        "individual": individual_stats,
        "portfolio_pnl": portfolio_pnl,
        "portfolio_ann_pct": portfolio_ann,
        "portfolio_dd_pct": portfolio_dd,
        "naive_dd_sum_pct": naive_dd_sum,
        "correlation_matrix": corr.round(4).to_dict(),
    }
    import json
    with open(os.path.join(OUT_DIR, "portfolio_correlation_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, default=str)

    print(f"\n  [OK] Reports guardados en:")
    print(f"    {os.path.join(OUT_DIR, 'portfolio_correlation_matrix.csv')}")
    print(f"    {os.path.join(OUT_DIR, 'portfolio_equity_curves_daily.csv')}")
    print(f"    {os.path.join(OUT_DIR, 'portfolio_correlation_summary.json')}")

    print("\n" + "=" * 70)
    print("  CONCLUSION BREVE")
    print("=" * 70)
    if portfolio_dd > 0:
        pct_savings = (1 - portfolio_dd / naive_dd_sum) * 100
        if pct_savings > 30:
            verdict = "Correlacion BAJA - alta diversificacion, mucho margen para subir lotes."
        elif pct_savings > 15:
            verdict = "Correlacion MODERADA - margen razonable para palanca A o B."
        else:
            verdict = "Correlacion ALTA - poco margen, subir lotes es arriesgado."
        print(f"  {verdict}")

if __name__ == "__main__":
    main()
