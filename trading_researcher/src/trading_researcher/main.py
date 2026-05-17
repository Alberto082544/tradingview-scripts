#!/usr/bin/env python
"""
Trading Researcher — Crew de investigación diaria de trading algorítmico.
Uso: uv run python -m trading_researcher.main
  o: uv run crewai run

Temas sugeridos para cada día:
  - "mean reversion strategies Python 2024"
  - "walk-forward optimization backtesting"
  - "MetaTrader 5 Python automation"
  - "Pine Script v6 new features"
  - "pairs trading forex algorítmico"
  - "machine learning trading signals"
  - "risk management position sizing quant"
"""
import sys
from trading_researcher.crew import TradingResearcher


TEMAS_ROTACION = [
    "mean reversion trading strategies Python backtesting 2025",
    "walk-forward optimization overfitting prevention quant trading",
    "MetaTrader 5 Python automation EA development",
    "forex algorithmic trading new strategies 2025",
    "Pine Script TradingView strategy optimization",
    "pairs trading statistical arbitrage forex",
    "machine learning trading signals filtering",
]


def run(tema: str = None):
    from datetime import date
    import hashlib
    if tema is None:
        dia = date.today().toordinal()
        tema = TEMAS_ROTACION[dia % len(TEMAS_ROTACION)]

    print(f"\n{'='*60}")
    print(f"  Trading Researcher — {date.today()}")
    print(f"  Tema: {tema}")
    print(f"{'='*60}\n")

    inputs = {"tema_dia": tema, "fecha_hoy": date.today().isoformat()}
    result = TradingResearcher().crew().kickoff(inputs=inputs)
    print(f"\n{'='*60}")
    print("  Investigación completada.")
    print(f"  Ver informe en: output/informe_{date.today().isoformat()}.md")
    print(f"{'='*60}\n")
    return result


if __name__ == "__main__":
    tema = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else None
    run(tema)
