"""
Aplica GT-Score a los 5 bots validados con sus params reales del EA en MT5.
Ranking GT-Score vs ranking percibido por las metricas legacy (PF, DD, anyos+).

Bots evaluados:
- AUDCAD Ranger C Stoch (top combo opt)
- AUDNZD Ranger C v3 (EA real Stoch K<15)
- GBPUSD MA Cross v1 (EA real)
- EMA9_VWAP NAS100 (EA real sobre QQQ proxy)
- AUDNZD-Stoch combo #1 restrictivo (DUDOSO regimen)
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd
import numpy as np
from utils.gt_score import gt_score

CAPITAL = 50_000.0


def evaluar(bot_name, modulo, df_path, params, pip, pip_val):
    """Carga datos, corre backtest, calcula GT-Score."""
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
        raise ValueError(f"Modulo {modulo} no soportado")

    if len(trades) == 0:
        return None

    pnls = trades["pnl"].astype(float).values
    timestamps = pd.to_datetime(trades["exit_dt"]).values
    detail = gt_score(pnls, timestamps, CAPITAL, return_details=True)
    detail["bot"] = bot_name
    detail["n_trades"] = len(trades)
    detail["total_pnl"] = float(pnls.sum())
    detail["ann_pct"] = round(pnls.sum() / CAPITAL * 100 / 12, 2)  # aprox sobre 12 anyos
    return detail


def main():
    base = os.path.join(os.path.dirname(__file__), "..", "data")

    bots = [
        {
            "name": "AUDCAD Ranger-C Stoch (top combo)",
            "modulo": "ranger_c_audcad",
            "df_path": os.path.join(base, "AUDCAD_M15_histdata.csv"),
            "pip": 0.0001, "pip_val": 7.3,
            "params": {
                'BB_Period':20,'BB_StdDev':2.0,'RSI_Period':14,'ADX_H4_Period':14,'ATR_Period':14,
                'Stoch_K':5,'Stoch_D':3,'ADX_H4_Max':20,'RSI_Long_Max':40,'RSI_Short_Min':60,
                'RSI_Confirm':1,'StochMode':2,'Stoch_Long_Max':20,'Stoch_Short_Min':75,
                'BB_Mid_TP':0,'MinSLPips':20,'TrailDistPips':8,'ExitBars':24,
                'SL_ATR_Mult':1.5,'MaxSLPips':999,'TP_ATR_Mult':0,'TrailActivate':0.5,
                'SessionStart':0,'SessionEnd':23,'BadHour':-1,'MaxTradesDay':5,
                'LotRiskPct':0.7,'MaxLots':4.0,
            },
        },
        {
            "name": "AUDNZD Ranger-C v3 (EA real Stoch K<15)",
            "modulo": "ranger_c_audnzd_stoch",
            "df_path": os.path.join(base, "AUDNZD_M15_histdata.csv"),
            "pip": 0.0001, "pip_val": 6.0,
            "params": {
                'BB_Period':20,'BB_StdDev':2.0,'RSI_Period':14,'ADX_H4_Period':14,'ATR_Period':14,
                'Stoch_K':5,'Stoch_D':3,'ADX_H4_Max':20,'RSI_Long_Max':45,'RSI_Short_Min':55,
                'RSI_Confirm':0,'StochMode':1,'Stoch_Long_Max':15,'Stoch_Short_Min':75,
                'BB_Mid_TP':0,'MinSLPips':20,'TrailDistPips':4,'ExitBars':32,
                'SL_ATR_Mult':1.5,'MaxSLPips':999,'TP_ATR_Mult':0,'TrailActivate':0.5,
                'SessionStart':0,'SessionEnd':23,'BadHour':8,'MaxTradesDay':5,
                'LotRiskPct':0.5,'MaxLots':4.0,
            },
        },
        {
            "name": "AUDNZD Ranger-C Stoch combo restrictivo #1 (DUDOSO)",
            "modulo": "ranger_c_audnzd_stoch",
            "df_path": os.path.join(base, "AUDNZD_M15_histdata.csv"),
            "pip": 0.0001, "pip_val": 6.0,
            "params": {
                'BB_Period':20,'BB_StdDev':2.0,'RSI_Period':14,'ADX_H4_Period':14,'ATR_Period':14,
                'Stoch_K':5,'Stoch_D':3,'ADX_H4_Max':20,'RSI_Long_Max':40,'RSI_Short_Min':60,
                'RSI_Confirm':1,'StochMode':2,'Stoch_Long_Max':20,'Stoch_Short_Min':75,
                'BB_Mid_TP':0,'MinSLPips':25,'TrailDistPips':8,'ExitBars':16,
                'SL_ATR_Mult':1.5,'MaxSLPips':999,'TP_ATR_Mult':0,'TrailActivate':0.5,
                'SessionStart':0,'SessionEnd':23,'BadHour':-1,'MaxTradesDay':5,
                'LotRiskPct':0.7,'MaxLots':4.0,
            },
        },
        {
            "name": "GBPUSD MA Cross v1 (EA real)",
            "modulo": "ma_cross",
            "df_path": os.path.join(base, "GBPUSD_M15_histdata.csv"),
            "pip": 0.0001, "pip_val": 10.0,
            "params": {
                'EMA_Fast':5,'SMA_Slow':34,'Dir_EMA_Fast':5,'Dir_SMA_Slow':34,
                'ATR_Period':14,'SL_ATR_Mult':1.0,'RR':3.0,
                'BE_Trigger':0.5,'BE_Offset':0.0001,
                'Trail_Start':1.5,'Trail_Dist':0.5,
                'MaxSpreadPips':3.0,'LotRiskPct':0.5,'MaxLots':4.0,
            },
        },
        {
            "name": "EMA9+VWAP NAS100 (EA real sobre QQQ)",
            "modulo": "ema9_vwap_rsi",
            "df_path": os.path.join(base, "NAS100_proxy_M15_twelvedata.csv"),
            "pip": 1.0, "pip_val": 100.0,
            "params": {
                'EMA_Fast':9,'EMA_Mid':21,'RSI_Period':14,
                'RSI_Buy_Min':35,'RSI_Buy_Max':75,'RSI_Sell_Min':30,'RSI_Sell_Max':65,
                'ATR_Period':14,'SL_ATR_Mult':1.0,'MinSLPips':0.5,
                'BE_Mult':2.0,'TP1_Mult':2.0,'TP1_Pct':0.5,
                'Trail_EMA':1,'WickRatio':1.5,'MaxTradesDay':3,
                'SessionStart':0,'SessionEnd':23,
                'LotRiskPct':0.5,'MaxLots':4.0,'Commission':0.0,
            },
        },
    ]

    print("=" * 90)
    print("  GT-Score sobre 5 bots reales (CAPITAL=$50.000)")
    print("=" * 90)

    results = []
    for b in bots:
        print(f"\n[{b['name']}] Cargando datos y backtest...")
        try:
            res = evaluar(b["name"], b["modulo"], b["df_path"], b["params"], b["pip"], b["pip_val"])
            if res is None:
                print("  Sin trades, skip")
                continue
            results.append(res)
            r = res["components_raw"]
            n = res["components_normalized"]
            print(f"  GT-Score: {res['gt_score']:.4f}")
            print(f"    PSR:       {r['psr']:.4f} (norm {n['psr']:.4f})")
            print(f"    p-value:   {r['pvalue']:.6f} (norm {n['pval']:.4f})")
            print(f"    Consist.:  {r['consistency']:.4f} (norm {n['cons']:.4f})")
            print(f"    TVaR ES95: {r['tvar_es95']:.6f} (norm {n['tvar']:.4f})")
            print(f"  N trades: {res['n_trades']:,} | Total PnL: ${res['total_pnl']:,.0f}")
        except Exception as e:
            print(f"  ERROR: {e}")

    if results:
        print("\n" + "=" * 90)
        print("  RANKING POR GT-SCORE")
        print("=" * 90)
        results.sort(key=lambda x: x["gt_score"], reverse=True)
        for i, r in enumerate(results, 1):
            print(f"  {i}. GT={r['gt_score']:.4f}  N={r['n_trades']:>5}  ${r['total_pnl']:>12,.0f}  {r['bot']}")


if __name__ == "__main__":
    main()
