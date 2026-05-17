import os
import sys
import io

os.makedirs("reports", exist_ok=True)
sys.path.insert(0, os.path.dirname(__file__))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from backtest.engine import BacktestEngine
from risk.montecarlo import MonteCarlo
from validation.walk_forward import WalkForward
from ai.analyst import analizar_backtest, guardar_informe

print("\n" + "=" * 60)
print("   TRADING FRAMEWORK — EMA + MACD v5  |  SPY 4H")
print("=" * 60)

# ── CAPA 1: BACKTEST ─────────────────────────────────────────
print("\n▶ CAPA 1 — Backtest")
engine = BacktestEngine(symbol="SPY", interval="1h", initial_capital=10_000)
trades = engine.run()

if trades.empty:
    print("  Sin operaciones — revisa los datos disponibles.")
    sys.exit()

total_pnl = trades["pnl"].sum()
win_rate  = (trades["pnl"] > 0).mean() * 100
avg_win   = trades.loc[trades["pnl"] > 0, "pnl"].mean()
avg_loss  = trades.loc[trades["pnl"] < 0, "pnl"].mean()

print(f"  Operaciones : {len(trades)}")
print(f"  P&L Total   : ${total_pnl:,.2f}")
print(f"  Win Rate    : {win_rate:.1f} %")
print(f"  Media win   : ${avg_win:,.2f}  |  Media loss: ${avg_loss:,.2f}")

# ── CAPA 2: MONTE CARLO ──────────────────────────────────────
print("\n▶ CAPA 2 — Monte Carlo (10.000 iter.)")
mc = MonteCarlo(trades, initial_capital=10_000, iterations=10_000)
mc_results = mc.run()
mc.print_report()
mc.plot("reports/montecarlo.png")

# ── CAPA 3: WALK-FORWARD ─────────────────────────────────────
print("\n▶ CAPA 3 — Walk-Forward (5 periodos)")
wf = WalkForward(symbol="SPY", interval="1h", n_splits=5, train_pct=0.70)
wf.run()
wf.report()

# ── CAPA 4: ANÁLISIS DEEPSEEK ────────────────────────────────
print("\n▶ CAPA 4 — Análisis DeepSeek (coordinado por Claude)")
try:
    informe = analizar_backtest(trades, mc_results, wf._rows)
    guardar_informe(informe)
    print("\n── INFORME ──────────────────────────────────────────")
    print(informe)
    print("─────────────────────────────────────────────────────")
except Exception as e:
    print(f"  DeepSeek no disponible: {e}")

print("\n✔ Análisis completado. Revisa la carpeta reports/\n")
