"""Herramientas locales para que los agentes lean nuestro estado real
de estrategias y backtests, evitando hablar en abstracto."""
from pathlib import Path
from crewai.tools import tool

PYTHON_DIR = Path(r"C:\Users\alber\tradingview-scripts\python")
REPORTS_DIR = PYTHON_DIR / "reports"
REGISTRO = PYTHON_DIR / "REGISTRO_ESTRATEGIAS.md"

MAX_CHARS = 6000


@tool("Leer Registro de Estrategias")
def read_registro() -> str:
    """Devuelve el registro de estrategias validadas con sus métricas
    (pares, timeframe, PF, WF, DD, USD/mes). Úsalo para saber qué tenemos
    ya validado antes de proponer algo nuevo."""
    if not REGISTRO.exists():
        return f"No existe el registro en {REGISTRO}"
    text = REGISTRO.read_text(encoding="utf-8", errors="ignore")
    return text[:MAX_CHARS]


@tool("Listar Reportes Disponibles")
def list_reports() -> str:
    """Lista los archivos de resultados en reports/ (CSVs de optimización,
    .md de robustez). Úsalo antes de pedir contenido específico."""
    if not REPORTS_DIR.exists():
        return f"No existe {REPORTS_DIR}"
    files = sorted(p.name for p in REPORTS_DIR.iterdir() if p.is_file())
    return "Reportes disponibles:\n" + "\n".join(f"  - {f}" for f in files)


@tool("Leer Reporte")
def read_report(filename: str) -> str:
    """Lee el contenido de un reporte de reports/ por nombre exacto.
    Para CSVs devuelve cabecera + primeras 20 filas. Para .md devuelve
    todo el contenido (truncado a 6000 chars)."""
    path = REPORTS_DIR / filename
    if not path.exists():
        return f"No existe {filename}. Usa list_reports() primero."
    if path.suffix == ".csv":
        try:
            import csv
            with path.open("r", encoding="utf-8", errors="ignore") as f:
                reader = csv.reader(f)
                rows = []
                for i, row in enumerate(reader):
                    if i > 20:
                        break
                    rows.append(" | ".join(row))
                return f"{filename} (primeras 20 filas):\n" + "\n".join(rows)
        except Exception as e:
            return f"Error leyendo CSV: {e}"
    text = path.read_text(encoding="utf-8", errors="ignore")
    return f"{filename}:\n{text[:MAX_CHARS]}"
