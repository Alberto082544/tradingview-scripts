"""Consulta independiente a DeepSeek sobre el estado de las cuentas de fondeo."""
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
SITUACION: Estoy operando dos cuentas de fondeo (FundedNext $15k y Capital Point $5k) con varios EAs en MetaTrader 5.
Hoy 2026-05-19 estan pasando cosas raras. Necesito un analisis independiente para llegar a un consenso de solucion.

--- INVENTARIO DE EAs INSTALADOS ---

FundedNext (89FE26...):
- AGM_EMA9_VWAP_NAS100_M15 (mio, Phase 1)
- AGM_JasperOB_NAS100_M15 (mio, descartado pero archivo aun ahi)
- AGM_MA_Cross_EURUSD_M15 (mio, Phase 1)
- AGM_Ranger_C_AUDNZD_M15 (mio, Phase 1)
- AGM_XAUUSD_ORB_M15 (mio, Phase 1)
- ORB_AGM_Indices_v1.0 (mio, antiguo)
- ORB_MultiSymbol_v4_0_FN (NO recuerdo bien si es mio)
- ORB_MultiSymbol_v4_4_ES (NO recuerdo bien)
- ORB_MultiSymbol_v4_7_AGM_1 (NO recuerdo bien)
- ORB_MultiSymbol_v5_0_ES (NO recuerdo bien)
- Strategy 4.85.147 (BOT EXTERNO, no es mio)

Capital Point (4C23...):
- AGM_MA_Cross_EURUSD_M15
- AGM_MA_Cross_GBPUSD_M15
- AGM_Ranger.ex5 (antiguo, version vieja)
- AGM_Ranger_C_AUDNZD.ex5 (antiguo, version vieja)
- ORB_MultiSymbol_v4_10_AGM
- ORB_MultiSymbol_v4_4_ES
- ORB_MultiSymbol_v4_7_ES (varios duplicados)
- ORB_MultiSymbol_v5.05_ES
- ORB_MultiSymbol_v5_06_AGM_1
- ORB_v4_8_AGM
- TBS_GIROS_EA (BOT EXTERNO, no es mio)

--- TRADES DE HOY 2026-05-19 ---

CAPITAL POINT (cuenta 52869162):
02:15:04  SELL 2.25 lotes EURUSD a 1.16500  (SL=1.16573, TP=1.16317)
02:36-19:30  trailing ajustando SL hacia abajo gradualmente (hasta 1.16456)
Posicion sigue ABIERTA al cierre del log.
Lotes 2.25 con cuenta $5k = riesgo enorme

FUNDEDNEXT (cuenta 14030310):
02:15:01  SELL 0.62 lotes AUDNZD a 1.22070 (cerro posicion anterior, neto)
07:45  BUY  0.82 GBPJPY a 213.221
10:13  SELL 0.82 GBPJPY a 213.019 (-17 pips → ~-1190 GBP perdida)
11:45  SELL 0.81 GBPJPY a 213.239
13:00  BUY  0.46 GBPJPY a 213.314
14:15  SELL 0.46 GBPJPY a 213.367
14:26  BUY  0.81 GBPJPY a 213.441
16:00  BUY  0.69 GBPJPY a 213.172
16:30  SELL 0.38 GBPJPY a 213.095
16:52  BUY  0.38 GBPJPY a 213.029
16:57  SELL 0.69 GBPJPY a 212.935
17:00  BUY  0.63 GBPJPY a 213.047
18:09  SELL 0.63 GBPJPY a 213.083
19:30  BUY  0.67 GBPJPY a 212.996 (SIGUE ABIERTA)

--- LOGS MQL5 DE HOY (lo que escribieron los EAs) ---

FundedNext:
- AGM_Ranger_C_AUDNZD_M15 cargado en gráfico AUDNZD,M15 (correcto)
- AGM_Ranger_C_AUDNZD_M15 cargado TAMBIEN en gráfico EURUSD,M15 (incorrecto, duplicado)
- Ambos disparan "Circuit breaker SL consecutivo 1/3, 2/3, 3/3" a las 10:13, 14:26 y 16:57.
- AGM_XAUUSD_ORB_M15 rechaza rangos: "ORB NY ignorado: rango=349.8p fuera de [40,150]" → no opera
- A las 20:17 el usuario removio manualmente:
    - AGM_Ranger_C_AUDNZD_M15 (EURUSD,M15) → removed
    - AGM_XAUUSD_ORB_M15 (XAUUSD,M15) → removed

Capital Point: solo logs del AGM_MA_Cross_EURUSD_M15 corriendo en gráfico M30 (debería ser M15)
Y un solo mensaje del XAUUSD_ORB_EA: "ORB NY ignorado: rango=352.0p fuera de [40,150]"

--- HECHOS RAROS ---

1. El EA AGM_Ranger_C_AUDNZD_M15 está usando _Symbol del gráfico al que esta adjunto, asi
   que al estar duplicado en gráfico EURUSD operaria EURUSD, NO GBPJPY. Pero las operaciones
   reales de hoy son GBPJPY. Los logs MQL5 no muestran NINGUN EA adjunto a gráfico GBPJPY.
   ¿De donde salen las 14 operaciones GBPJPY?

2. Los lotes en GBPJPY (0.38-0.82) son ENORMES para una cuenta de $15k con sizing
   conservador. Mis EAs AGM operan con 0.05-0.15 lotes típicamente. Esto huele a
   bot externo o EA antiguo con sizing fijo.

3. En Capital Point hay un SELL 2.25 lotes EURUSD que tampoco coincide con mis EAs
   (sería ~0.05-0.10 lotes con $5k). Posible bot externo o copy trader.

4. El AGM_MA_Cross_EURUSD_M15 en Capital Point está cargado en gráfico M30, pero
   fue optimizado para M15. Eso operaría con señales distintas a las planificadas.

5. AGM_XAUUSD_ORB_M15: el filtro de rango [40,150] pips no encaja con los rangos
   reales del oro (~350 pips). El bot NUNCA opera. ¿Bug del filtro? ¿Pip mal calibrado?

--- PREGUNTAS PARA TI (DeepSeek) ---

1. Quien crees que esta abriendo las operaciones GBPJPY si ningun EA AGM esta cargado
   en grafico GBPJPY? Lista de candidatos sospechosos por orden de probabilidad y razon.

2. Que pasos concretos y EN QUE ORDEN recomendarias al usuario para:
   (a) Detener inmediatamente los bots que operan mal
   (b) Identificar el culpable de las operaciones GBPJPY
   (c) Limpiar y dejar SOLO los EAs de Phase 1 (AUDNZD, EURUSD MA Cross, NAS100 EMA9+VWAP, AUDCAD nuevo)
   (d) Verificar que no quedan bots fantasma despues de la limpieza

3. ¿Hay riesgo de que las operaciones GBPJPY rompan el limite de DD diario de FundedNext (5% suele ser)?
   Lotes 0.38-0.82 en GBPJPY con $15k cuenta.

4. ¿Algun problema que se me escape?

Por favor responde en español, conciso pero completo. Tu rol es validador independiente,
si discrepas con mi diagnostico, dilo claro.
"""

print("Consultando DeepSeek... (modelo: deepseek-chat)")
print()
resp = client.chat.completions.create(
    model="deepseek-chat",
    messages=[
        {"role": "system", "content": "Eres un experto en MetaTrader 5, trading algoritmico y prop firms. Tu rol es analizar problemas de bots reales en cuentas de fondeo. Se conciso, directo y no inventes informacion. Si algo no tienes claro, dilo."},
        {"role": "user", "content": CONTEXTO},
    ],
    temperature=0.3,
    max_tokens=2000,
)

print("=" * 70)
print("  RESPUESTA DE DEEPSEEK")
print("=" * 70)
print()
print(resp.choices[0].message.content)
print()
print("=" * 70)
print(f"  Tokens usados: in={resp.usage.prompt_tokens}, out={resp.usage.completion_tokens}")
print("=" * 70)
