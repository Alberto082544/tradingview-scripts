"""Segunda consulta DeepSeek con info ya confirmada para llegar al CONSENSO FINAL."""
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
ACTUALIZACION: hemos avanzado en la investigacion del problema GBPJPY. Lo que sigue es
informacion CONFIRMADA leyendo archivos directamente. Quiero tu validacion del consenso
final y un plan EJECUTABLE.

--- HECHOS CONFIRMADOS ---

A) Las cuentas son:
   - FundedNext $15k (terminal 89FE26..., login 14030310)
   - The 5%ers $5k (terminal 4C23..., login 52869162, broker = Capital Point Trading)

B) Posicion GBPJPY abierta ya CERRADA por el usuario a las 21:01 con ganancia (+12 pips).
   Riesgo inmediato resuelto. Falta limpiar el sistema.

C) Strategy 4.85.147.mq5 — INSPECCION DIRECTA:
   - Linea 5: "Generated at 03/31/2026 19:20"
   - Linea 7: "Backtested on GBPJPY_M1_dukas / M15,H1,M30"
   - Linea 10: copyright "StrategyQuant.com"
   - Linea 85: input int MagicNumber = 11111
   - Lineas 164,167: Subchart1Symbol = "GBPJPY_M1_dukas", Subchart2Symbol idem
   - Tamano: 318KB (StrategyQuant export tipico)

   Conclusion: ES UN BOT DE STRATEGYQUANT GENERADO AUTOMATICAMENTE PARA OPERAR GBPJPY.
   Probabilidad de ser el culpable: 97%

D) Los ORB_MultiSymbol* y ORB_AGM_Indices SI son del usuario (copyright "AGM v4.7",
   "Alberto Custom", "AGM / BlackSheep Quant Lab"). NO son externos.
   Tambien tienen referencias a GBPJPY pero como parte de un listado multi-simbolo.
   Probabilidad de ser el culpable: <3% (no se ve actividad de estos EAs en logs hoy)

E) Operaciones GBPJPY de hoy en FundedNext (14 deals, todas con tamanos 0.38-0.82 lotes):
   - 07:45 buy 0.82 a 213.221
   - 10:13 sell 0.82 a 213.019 (cerro previo)
   - ... (varios mas hasta 18:09)
   - 19:30 buy 0.67 a 212.996 (esta era la que estaba abierta)
   - 21:01 sell 0.67 a 213.115 (cerrada por usuario, +12 pips ganancia)

   Magic number en deals NO esta visible en logs (MT5 no lo logea por defecto).
   Pero el lotaje fijo y la frecuencia coinciden con un bot de StrategyQuant.

F) Otros problemas detectados (ya en plan):
   - AGM_MA_Cross_EURUSD_M15 cargado en grafico M30 (debe ser M15) → genera senales malas
   - AGM_Ranger_C_AUDNZD_M15 duplicado en grafico EURUSD (ya removido por usuario 20:17)
   - AGM_XAUUSD_ORB_M15 filtro de rango [40,150] pips mal calibrado para oro (rangos reales ~350)
   - The 5%ers (Capital Point) tiene SELL 2.25 lotes EURUSD ABIERTA con SL trailing
     (cuenta $5k, lotaje muy alto, posible MA_Cross en M30 mal configurado)

G) Inventario EAs final (lo que el usuario quiere mantener vs eliminar):
   MANTENER (Phase 1):
   - AGM_Ranger_C_AUDNZD_M15
   - AGM_MA_Cross_EURUSD_M15 (corregir TF en The 5%ers a M15)
   - AGM_EMA9_VWAP_NAS100_M15
   - AGM_XAUUSD_ORB_M15 (arreglar filtro)
   - Pendiente crear: AGM_Ranger_C_AUDCAD_M15 (top combo de hoy)

   ELIMINAR:
   - Strategy 4.85.147 (StrategyQuant externo, opera GBPJPY sin permiso)
   - AGM_JasperOB_NAS100_M15 (descartado por baja PF)
   - TBS_GIROS_EA (externo en The 5%ers)
   - Todos los ORB_MultiSymbol_* y ORB_v4_8_AGM (multi-version old, posibles conflictos)
   - ORB_AGM_Indices_v1.0 (antiguo, reemplazado por nada concreto)
   - AGM_Ranger.ex5 y AGM_Ranger_C_AUDNZD.ex5 sin sufijo M15 en The 5%ers (versiones viejas)

--- PREGUNTAS ESPECIFICAS PARA CONSENSO FINAL ---

1. Coincides en que Strategy 4.85.147 es el culpable al 97% confirmado?
   ¿Sigue habiendo riesgo de que sea otro EA?

2. Plan limpieza paso a paso DEFINITIVO (numera y se claro): cierre MT5,
   borrar archivos .ex5 y .mq5 concretos, verificar carga al reabrir.

3. The 5%ers tiene SELL 2.25 lotes EURUSD ABIERTA. Para una cuenta $5k:
   - 2.25 lotes EURUSD = $22.5 por pip
   - SL inicial 73 pips = -$1642 (32% de la cuenta) — IMPOSIBLE, demasiado riesgo
   - SL actual ~40 pips = -$900 (18%)
   ¿Cierro tambien manualmente? Si entry 1.16500 y precio actual ~1.16500, riesgo bajo
   solo si cierra al breakeven. ¿Es seguro dejarla con SL trailing hasta TP 1.16317?

4. Despues de limpiar, ¿como evitar que en el futuro alguien se instale un EA
   externo en MQL5/Experts sin que el usuario lo sepa? ¿Que mecanismos
   (alarma, hash check, whitelist) propondrias?

5. ¿Algo critico que se me siga escapando?

Responde en espanol, conciso, con lista numerada de pasos al final. Tu rol: validador
final. Discrepa libremente si ves errores.
"""

print("Consultando DeepSeek (2da vuelta) para consenso final...")
print()
resp = client.chat.completions.create(
    model="deepseek-chat",
    messages=[
        {"role": "system", "content": "Eres un experto senior en MetaTrader 5 y prop firms. Tu rol AHORA es validador final: confirma o discrepa con el diagnostico, no inventes. Se conciso y accionable."},
        {"role": "user", "content": CONTEXTO},
    ],
    temperature=0.2,
    max_tokens=2200,
)

print("=" * 70)
print("  CONSENSO FINAL - DeepSeek validacion")
print("=" * 70)
print()
print(resp.choices[0].message.content)
print()
print(f"  Tokens usados: in={resp.usage.prompt_tokens}, out={resp.usage.completion_tokens}")
