"""
Consulta independiente a DeepSeek sobre EA SMC FVG + plan de validación.
Para contrastar mi análisis con uno externo y llegar a conclusión más sólida.
"""
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
SITUACIÓN: Tengo un EA llamado "EA_SMC_Tendencia_FVG.mq5" v9.4 generado por IA (Claude)
basado en metodología SMC (Smart Money Concepts) de Ivan/César. Es multi-símbolo.

LÓGICA DEL EA (resumida):
- H4: detección de tendencia (swings ≥3 + EMA200 confirma)
- TF FVG configurable por símbolo (H1, M30 o M15): detecta Fair Value Gaps con impulso ≥8 pips
- M15: gestiona estados FVG (ACTIVE → TOUCHED → FILLED) y entra en pullback con confirmación de patrón
- Patrones de entrada: Doji, Pinbar, Engulfing
- Filtros: RSI H1 (28/72), EMA50 H1, sesión 7-21 GMT, spread ≤3.5 pips
- Risk management: 2 tickets (TP1=1:2, TP2=1:3), BE+buffer cuando TP1 hit
- SL = ATR(H1) × SL_ATR_Mult (input configurable, default 1.5), max 80 pips
- 856 líneas, multi-símbolo (9 pares preconfigurados)

HIPÓTESIS DEL AUTOR (lo que él dice que funciona, NO verificado por mí):
- En EURUSD y EURGBP rentable con: TF_FVG=H1, SL_ATR_Mult=1.0
- Para pares más volátiles (GBPJPY, USDJPY): TF_FVG=M30, SL_ATR_Mult>1.0
- Razón: a más volatilidad → TF más rápido (capturar antes de diluirse) + más SL (no salir por ruido)

DATOS REALES DE ATR(H1) que YO he calculado en los últimos 200 H1:
- EURGBP: 5.8 pips (0.66× EURUSD)
- AUDCAD: 7.7 pips (0.86× EURUSD)
- AUDNZD: 8.2 pips (0.92× EURUSD)
- EURUSD: 8.9 pips (1.00× referencia)
- GBPUSD: 12.3 pips (1.38× EURUSD)
- GBPJPY: 27.2 pips (3.06× EURUSD) — MUY VOLÁTIL

MI CONTEXTO COMPLETO:
Hoy 23-may descubrí que mis bots actuales:
- AUDNZD Ranger-C: confirmado SIN edge (3 fuentes coinciden: Python custom, MT5 ticks reales, VectorBT 42 combos)
- AUDCAD Ranger-C: pierde -41% return con datos completos 2018-2024
- GBPUSD MA Cross: con params optimizados (EMA=3/SMA=55/SL=0.5/RR=3.0) da PF OOS 1.45, DD 9.2%, WF ratio 0.92
- EURUSD MA Cross: con params nuevos (EMA=8/SMA=34/SL=0.5/RR=3.0) da PF OOS 1.49, DD 5.6%, WF ratio 1.20
- NDX100 EMA9+VWAP: no operaba (no cargado), GT-Score Python 0.99

Mis bots ganadores son MA Cross simples con SL pequeño + RR alto.

LO QUE QUIERO DE TI:

1. ¿Tiene sentido teórico la hipótesis "pares más volátiles → FVG en TF más rápido + más SL"?
   ¿O es una racionalización ad-hoc?

2. La estrategia SMC + FVG en H1/M30/M15: ¿hay evidencia académica o de quants de que
   tenga edge real? ¿O es metodología discutida sin base estadística?

3. Para validar el EA con MINIMO RIESGO de overfit, ¿qué protocolo propones?
   (sabiendo que el EA es complejo, multi-símbolo, y multi-TF)

4. Dado que YA tengo 2 bots validados (GBPUSD y EURUSD MA Cross con PF OOS 1.45-1.49),
   ¿vale la pena el esfuerzo de validar este EA SMC (semanas de backtest multi-símbolo),
   o es mejor dedicar el tiempo a: (a) cargar NDX100, (b) buscar HMM+ADX para NDX100,
   (c) optimizar más params de los MA Cross actuales?

5. Si decido probarlo igualmente, ¿qué CONFIGURACIÓN INICIAL específica recomiendas
   para EURUSD (el par "supuestamente rentable" del autor) en backtest 2018-2024 con
   calidad 100% (ticks reales del broker FN), para tener un punto cero objetivo?

6. ¿Algún riesgo oculto del EA que se me escape? (multi-tickets, multi-símbolo,
   gestión de BE+buffer, conflicto magic number con otros bots, etc.)

Responde en español, conciso pero completo. Soy técnico, no edulcores. Si crees que
es mejor descartarlo, dilo claro y explica por qué.
"""

print("Consultando DeepSeek (modelo deepseek-chat)…")
print()
resp = client.chat.completions.create(
    model="deepseek-chat",
    messages=[
        {"role": "system", "content": "Eres un experto en trading algorítmico cuantitativo, MetaTrader 5, Python y validación estadística de estrategias. Conoces SMC, FVG, ICT y también los críticos académicos de estas metodologías. Tu rol es validador externo independiente: si crees que algo es overfit, sesgo de superviviencia o no tiene base, dilo claro. No edulcores."},
        {"role": "user", "content": CONTEXTO},
    ],
    temperature=0.3,
    max_tokens=3000,
)

print("=" * 75)
print("  RESPUESTA DE DEEPSEEK")
print("=" * 75)
print()
print(resp.choices[0].message.content)
print()
print("=" * 75)
print(f"  Tokens: in={resp.usage.prompt_tokens}, out={resp.usage.completion_tokens}")
print("=" * 75)
