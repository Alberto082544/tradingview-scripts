import os
from openai import OpenAI
from dotenv import load_dotenv
import pandas as pd

load_dotenv()

_client = None

def _get_client() -> OpenAI:
    global _client
    if _client is None:
        key = os.getenv("DEEPSEEK_API_KEY")
        if not key:
            raise ValueError("Falta DEEPSEEK_API_KEY en el archivo .env")
        _client = OpenAI(api_key=key, base_url="https://api.deepseek.com")
    return _client


def analizar_backtest(trades: pd.DataFrame, mc_results: dict, wf_rows: list) -> str:
    """
    Envía los resultados a DeepSeek y devuelve un informe en español.
    Claude revisa este output antes de usarlo.
    """
    # Preparar resumen numérico compacto (menos tokens)
    n       = len(trades)
    pnl     = trades["pnl"].sum()
    wr      = (trades["pnl"] > 0).mean() * 100
    avg_w   = trades.loc[trades["pnl"] > 0, "pnl"].mean() if (trades["pnl"] > 0).any() else 0
    avg_l   = trades.loc[trades["pnl"] < 0, "pnl"].mean() if (trades["pnl"] < 0).any() else 0
    ror     = mc_results.get("risk_of_ruin", 0) * 100
    dd95    = mc_results.get("drawdown_95pct", 0) * 100
    med_eq  = mc_results.get("median_equity", 0)

    oos_lines = "\n".join(
        f"  Periodo {r.get('Periodo','?')}: IS={r.get('IS P&L %','?')}  OOS={r.get('OOS P&L %','?')}"
        for r in wf_rows
    )

    prompt = f"""Eres un analista cuantitativo senior. Analiza estos resultados de backtest y redacta un informe profesional en español. Sé directo y conciso.

BACKTEST (SPY 4H — EMA+MACD v5):
- Operaciones: {n}
- P&L Total: ${pnl:.2f}
- Win Rate: {wr:.1f}%
- Media ganancia: ${avg_w:.2f}
- Media pérdida: ${avg_l:.2f}

MONTE CARLO (10.000 iter.):
- Probabilidad de Ruina: {ror:.2f}%
- Drawdown Máx. 95% confianza: {dd95:.2f}%
- Capital final mediano: ${med_eq:.2f}

WALK-FORWARD (5 periodos):
{oos_lines}

Redacta: 1) Evaluación general, 2) Puntos fuertes, 3) Riesgos, 4) Recomendaciones de mejora."""

    client = _get_client()
    resp   = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=800,
    )
    return resp.choices[0].message.content


def guardar_informe(texto: str, path: str = "reports/analysis.md"):
    os.makedirs("reports", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("# Informe DeepSeek — EMA+MACD v5\n\n")
        f.write(texto)
    print(f"  Informe guardado → {path}")
