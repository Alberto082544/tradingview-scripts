"""
Consulta independiente a DeepSeek: qué aspectos atacar a continuación.
Contexto completo de la sesión 23-may.
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
SOY un trader algorítmico operando 2 cuentas de fondeo:
- FundedNext $15.000
- The 5%ers $5.000

QUÉ HE DESCUBIERTO HOY 23-may (después de 2 semanas operando y testeando):

1. **Mis 4 bots forex actuales NO funcionan en MT5 con datos reales**:
   - AUDNZD Ranger-C: PF 0.48, DD 57% (confirmado por 3 fuentes: Python, MT5, VectorBT)
   - AUDCAD Ranger-C: PF 0.62, DD 22% (Python custom: -41% return en 7 años)
   - GBPUSD MA Cross: PF 0.45, DD 94% (optimización MT5 con 99 valores de SL, NINGÚN combo positivo)
   - EURUSD MA Cross: PF 0.51, DD 99% (idem GBPUSD, ningún combo de SL_ATR rentable)

2. **Mi optimización en Python ENGAÑA**:
   - VectorBT con spread 1.5 pips decía: GBPUSD PF 1.45, EURUSD PF 1.49 con SL=0.5*ATR
   - MT5 con spread real broker decía: GBPUSD PF 0.52, EURUSD PF 0.51 con esos mismos params
   - Conclusión: SL pequeño es MUY vulnerable al spread real

3. **MT5 cachea inputs en archivos .set** → recompilar el .ex5 no actualiza el tester si el .set tiene inputs viejos. He aprendido a editar el .set directamente con Python.

4. **Sospecha actual del usuario**: el backtest puede estar usando spread inflado de mercado cerrado (sábado/domingo). Decidimos posponer backtest MT5 hasta entre semana.

5. **EA SMC FVG v9.4 multisímbolo** (encontrado hoy):
   - 856 líneas MQL5, basado en SMC (Smart Money Concepts) de Ivan/César
   - 3 capas temporales: H4 tendencia → H1/M30 FVG → M15 entrada con patrones
   - Acabo de portarlo a Python (versión simplificada)
   - Backtest multi-activo en 11 activos (forex + oro + índices): casi cero trades con filtros originales
   - Versión relajada en marcha (sin RSI, sin EMA, sin sesión, FVG impulso 4 pips)

6. **NDX100 EMA9_VWAP** está en mi cartera Phase 1 pero NUNCA OPERÓ porque el EA no estaba cargado en chart. Pendiente cargar lunes.

7. **GT-Score (función objetivo anti-overfitting)** implementado. NDX100 tiene GT-Score 0.99 según Python.

8. **Informe CrewAI 23-may** recomendó: VectorBT (instalado), HMM+ADX para NAS100 (pendiente).

INFRAESTRUCTURA TÉCNICA QUE TENGO:
- Python 3.13 con engine custom de backtest
- VectorBT 1.0 instalado y funcionando
- CrewAI Trading Researcher operativo (DeepSeek + HuggingFace)
- Datos M15 históricos 2018-2024 para 6 pares forex + GBPJPY
- Datos M15 más cortos para XAUUSD, NAS100, SP500, US500, UK100
- MetaTrader 5 con cuentas FN + 5%ers + datos ticks reales del broker
- GitHub con todo el código (Alberto082544/tradingview-scripts)

PREGUNTAS PARA TI:

1. **Diagnóstico**: dada toda esta info, ¿qué aspectos del workflow estoy fallando? Ya sé que confiar en Python sin spread real es uno. ¿Qué otros errores estructurales ves?

2. **Prioridades**: si tuvieras que ordenarme 5 acciones concretas para los próximos 7 días (en orden de mayor impacto/riesgo), ¿cuáles serían?

3. **Estrategias prometedoras**: dado que MA Cross y Ranger-C parecen no funcionar en este broker, ¿qué TIPO de estrategia me recomendarías investigar?
   (Ej: mean reversion en par cointegrado, momentum breakout, pairs trading, ML, etc.)

4. **Sobre SMC/FVG**: ¿crees que vale la pena seguir invirtiendo tiempo en validar este EA, o el resultado preliminar (casi cero trades) ya es señal de descarte?

5. **Sobre NDX100**: ¿qué configuración inicial probarías para validarlo correctamente en MT5 (datos reales) la próxima semana?

6. **Trampas a evitar**: ¿qué errores típicos cometen los traders algorítmicos en mi situación (cuentas pequeñas, validación incompleta, prisa por encontrar bot rentable)?

7. **¿Algo importante que se me escape?** Honesto. Si crees que estoy enfocado mal, dilo.

Responde en español, conciso pero completo. Soy técnico (programador con conocimientos cuant medios), no edulcores. Si crees que debo dejar de optimizar y simplemente comprar señales o suscripción a algo, dilo claro.
"""

print("Consultando DeepSeek (deepseek-chat)…")
print()
resp = client.chat.completions.create(
    model="deepseek-chat",
    messages=[
        {"role": "system", "content": "Eres un experto senior en trading algorítmico cuantitativo, MetaTrader 5, Python, validación estadística y psicología del trader retail con cuentas pequeñas. Conoces tanto la teoría académica como la realidad de prop firms. Tu rol es validador externo brutalmente honesto. No edulcores. Si crees que el usuario debe rendirse o cambiar de enfoque radicalmente, dilo claro."},
        {"role": "user", "content": CONTEXTO},
    ],
    temperature=0.3,
    max_tokens=3500,
)

print("=" * 80)
print("  RESPUESTA DE DEEPSEEK — Próximos pasos")
print("=" * 80)
print()
print(resp.choices[0].message.content)
print()
print("=" * 80)
print(f"  Tokens: in={resp.usage.prompt_tokens}, out={resp.usage.completion_tokens}")
print("=" * 80)
