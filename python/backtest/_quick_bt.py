import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from strategies.agm_ranger_v3 import add_indicators, run_backtest, compute_metrics, DEFAULT_PARAMS
import pandas as pd
import numpy as np

DUKAS_CACHE = "data/GBPJPY_M30_dukas.csv"
TZ_OFFSET   = 1
INITIAL_CAP = 50_000.0

best_params = dict(DEFAULT_PARAMS)
best_params.update({
    'RSI_Oversold': 32, 'RSI_Overbought': 68,
    'TP_Pips': 0, 'MinSLPips': 200,
    'TrailDistPips': 60, 'ExitBars': 15,
})

print("Cargando datos...", flush=True)
df = pd.read_csv(DUKAS_CACHE, index_col=0, parse_dates=True)
df = df[df.index >= "2015-01-01"]
print(f"Barras: {len(df)} | {df.index[0].date()} -> {df.index[-1].date()}", flush=True)

df_ind = add_indicators(df, best_params)
trades = run_backtest(df_ind, best_params, INITIAL_CAP, tz_offset=TZ_OFFSET)
m = compute_metrics(trades, INITIAL_CAP)

sep = "=" * 50
print(f"\n{sep}", flush=True)
print("BACKTEST COMPLETO 2015-2026 (params optimizados)", flush=True)
print(sep, flush=True)
print(f"Trades:         {m['n']}", flush=True)
print(f"PnL total:      ${m['pnl']:+.0f}", flush=True)
print(f"Win Rate:       {m['wr']}%", flush=True)
print(f"Profit Factor:  {m['pf']}", flush=True)
print(f"Max Drawdown:   {m['dd_pct']}%", flush=True)
print(f"Calmar:         {m['calmar']}", flush=True)
print(f"Avg win/loss:   ${m['avg_w']} / ${m['avg_l']}", flush=True)
print(f"Exits:          {m['exits']}", flush=True)

# Annual breakdown
trades["year"] = pd.to_datetime(trades["exit_dt"]).dt.year
print(f"\n{'':=<50}", flush=True)
print("DESGLOSE ANUAL", flush=True)
print(f"{'':=<50}", flush=True)
eq_running = INITIAL_CAP
for yr, g in trades.groupby("year"):
    pnl = g["pnl"].sum()
    wr  = (g["pnl"] > 0).mean() * 100
    n   = len(g)
    result = "VERDE" if pnl > 0 else "ROJO"
    print(f"{yr}: n={n:3d}  PnL=${pnl:+7.0f}  WR={wr:.0f}%  {result}", flush=True)
