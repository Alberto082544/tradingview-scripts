"""Re-consulta DeepSeek con DATOS OOS REALES del CSV de opt AUDCAD-Stoch."""
import os
import sys
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

client = OpenAI(
    api_key=os.environ["DEEPSEEK_API_KEY"],
    base_url="https://api.deepseek.com/v1",
)

CONTEXTO = """
ROL: Equipo de validacion estrategica para quant trader en cuentas de fondeo
reales. Esta es una RE-CONSULTA tras descubrir datos que faltaban en la primera
ronda. Tu primera recomendacion (B' + E') fue cauta porque te faltaba info
sobre OOS y WF del combo ganador. AHORA TENEMOS ESOS DATOS.

--- DATOS NUEVOS DEL CSV DE OPTIMIZACION ---

Total combos evaluados en el grid: 20.736

COMBO GANADOR (score 1.144):
  StochMode=2, RSI_L=40, RSI_S=60, RSI_Confirm=1, MinSL=20, ExitBars=24,
  TrailDist=8, BB_Mid_TP=0, Stoch_Long_Max=20, Stoch_Short_Min=75,
  ADX_H4_Max=20

  IS (in-sample):  N=1024, PF=1.20, DD=7.6%, WR=59.5%, Ann=5.93%
  OOS (out-sample): N=608,  PF=1.36, DD=5.80%, WR=62.3%, Ann=11.41%
  WF_ratio: 1.133

ROBUSTEZ DEL TOP 10 (por score):
  - Todos los top 10 tienen StochMode=2 (RSI+Stoch confirman)
  - RSI_Long_Max=40 en 9 de 10 (uno con 50)
  - MinSL=20 en 7 de 10, MinSL=12 en 3 de 10
  - ExitBars=24 en 7 de 10, ExitBars=32 en 3 de 10
  - WF_ratio range: 0.908 - 1.133, mediana ~1.08
  - OOS_PF range: 1.19 - 1.36
  - OOS_DD range: 5.4% - 10.0%

TOP 10 POR OOS_PF (con oos_n>=30) MUESTRA:
  - 5 combos con OOS_PF entre 1.36 y 1.38
  - Algunos con OOS_Ann hasta 17%, pero IS_DD alto (>14%) sugiere overfit IS
  - El combo con menor IS_DD y mejor OOS combinado sigue siendo el "ganador"

--- CHECKLIST 7 PUNTOS RECALCULADO ---

| # | Criterio | Valor real | Pass |
|---|----------|------------|------|
| 1 | OOS_PF >= 1.10 | 1.36 | SI |
| 2 | WF >= 1.00 | 1.133 | SI |
| 3 | N OOS >= 30 | 608 | SI |
| 4 | year-by-year positivos | 12/12 anios | SI |
| 5 | MC < 2x DD historico | MC p99 20.85% vs limite 15.18% | NO |
| 6 | Sensibilidad parametrica | Top 10 dominado por mismos params | SI |
| 7 | Sentido economico | BB+RSI+Stoch mean reversion con ADX H4 | SI |

6 de 7 pasan. El unico fallo es MC alto. Pero notar:
- OOS_DD REAL = 5.80% (muy bajo)
- MC p99 al 20.85% es heuristico sobre 1.629 trades agregados
- La regla MC<2xDD es CONSERVADORA, no canonica

--- OPCIONES REVISADAS ---

(A') Deploy AUDCAD-Stoch con SIZING REDUCIDO al 50% (LotRiskPct 0.7 → 0.35).
    Con sizing mitad, el MC p99 EFECTIVO baja a ~10% (dentro prop firm).
    Edge OOS_PF=1.36 capturado parcialmente. Reversible si falla.

(B') Re-optimizar con grid restrictivo para forzar MC<15% sin tocar sizing.
    Coste probable: PF baja a 1.10-1.20. Tiempo de re-opt.

(C') Mantener AUDCAD SIN Stoch (OOS_PF=1.24 actual). Ahora claramente
    INFERIOR a (A') ya que con sizing reducido capturas mejor edge.

(D') Descartar Stoch en familia. INVALIDADA por evidencia: Stoch=2 es
    robusto, top 10 lo confirma.

--- PREGUNTA REFINADA ---

Aplica 6 sombreros con ESTOS DATOS NUEVOS sobre el debate revisado:
A' (sizing reducido), B' (re-opt restrictiva), C' (no tocar nada).

Pregunta especifica:
- ¿La opcion A' (sizing reducido) es defendible cuantitativamente, o sigues
  recomendando B' incluso con OOS_PF=1.36 demostrado?
- ¿Cual es el coste de oportunidad de NO deployar A' ahora? (Cada semana sin
  Stoch = perdiendo edge OOS de 0.12 puntos PF y 5pp de annual return).
- ¿Que TEST DECISIVO podriamos hacer en 1-2 dias (no 2 semanas) para validar
  A' o descartarla? Especifico, no generico.

Responde aplicando 6 sombreros SECUENCIAL (blanco, rojo, negro, amarillo,
verde, azul). En espanyol, conciso y accionable. Si tu veredicto cambia
respecto a la primera consulta, dilo explicitamente.
"""

print("Re-consultando DeepSeek con datos OOS reales del CSV...")
print()
resp = client.chat.completions.create(
    model="deepseek-chat",
    messages=[
        {"role": "system", "content": "Eres un equipo de pensamiento estrategico que aplica 6 sombreros con rigor. Esta es una RE-CONSULTA con datos nuevos: si tu veredicto cambia respecto a la primera vuelta, debes decirlo explicitamente. Conciso y accionable. Espanyol."},
        {"role": "user", "content": CONTEXTO},
    ],
    temperature=0.4,
    max_tokens=3500,
)

print("=" * 72)
print("  RESPUESTA DeepSeek v2 — con OOS reales")
print("=" * 72)
print()
print(resp.choices[0].message.content)
print()
print("=" * 72)
print(f"  Tokens: in={resp.usage.prompt_tokens}, out={resp.usage.completion_tokens}")
print("=" * 72)
