"""Ejecuta el crew para varios temas seguidos, renombrando cada informe
con un sufijo para que no se sobrescriban."""
import sys
import os
import shutil
from datetime import date
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

from trading_researcher.crew import TradingResearcher

TEMAS = [
    ("stoch_adx", "Combinaciones de filtros Stochastic y ADX en mean reversion forex M15"),
    ("aiomql_migration", "aiomql librería async MetaTrader5 Python migración desde MetaTrader5 oficial ejemplos código"),
    ("kelly_forex_m15", "Kelly fraccional dinámico position sizing forex M15 implementación práctica"),
]

OUTPUT_DIR = Path("output")
INFORME_BASE = OUTPUT_DIR / f"informe_{date.today().isoformat()}.md"
RIESGO_BASE = OUTPUT_DIR / "riesgo.md"
BUSQ_BASE = OUTPUT_DIR / "busqueda_raw.md"
ANAL_BASE = OUTPUT_DIR / "analisis.md"


def run_one(slug: str, tema: str) -> None:
    print(f"\n{'='*70}\n[LANZANDO] {slug} → {tema}\n{'='*70}", flush=True)
    inputs = {"tema_dia": tema, "fecha_hoy": date.today().isoformat()}
    TradingResearcher().crew().kickoff(inputs=inputs)

    suffix = f"_{slug}"
    for base in (INFORME_BASE, RIESGO_BASE, BUSQ_BASE, ANAL_BASE):
        if base.exists():
            target = base.with_name(base.stem + suffix + base.suffix)
            shutil.move(str(base), str(target))
            print(f"  → renombrado: {target.name}", flush=True)

    print(f"[OK] {slug} completado\n", flush=True)


if __name__ == "__main__":
    for slug, tema in TEMAS:
        try:
            run_one(slug, tema)
        except Exception as e:
            print(f"[FALLO] {slug}: {e}", flush=True)

    print("\n=== BATCH COMPLETADO ===", flush=True)
    print("Informes generados:")
    for f in sorted(OUTPUT_DIR.glob(f"informe_{date.today().isoformat()}_*.md")):
        print(f"  - {f.name}")
