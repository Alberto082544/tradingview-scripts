"""Consulta DeepSeek 6 sombreros: AUDNZD-v3 real falla 10/12 pero 8 anyos seguidos positivos."""
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
ROL: Equipo de validacion estrategica. Aplica 6 sombreros de Edward de Bono
SECUENCIAL y SIN MEZCLAR ROLES. Decision: mantener o pausar EA en cuenta REAL.

--- SITUACION REAL ---

Bot AGM_Ranger_C_AUDNZD_M15 v3 esta operando en cuentas de fondeo:
- FundedNext $15k (sizing real LotRiskPct=0.5)
- Capital Point $5k (sizing real LotRiskPct=0.5)

Configuracion v3:
- Stochastic K<15 (SOLO Stoch, sin RSI)
- ADX H4<20 (mercado lateral)
- MinSL=20 pips, Trail=4 pips, ExitBars=32 barras
- BadHour=8 (hora bloqueada: transicion Asia-Londres)
- Circuit breakers + filtro noticias activos
- MagicNumber=202601

--- VALIDACION YEAR-BY-YEAR (12 anyos 2014-2025, $50k base) ---

  Anio  Trades  WR%    PF    PnL$       DD%
  2014    176  55.7  0.99   -90        7.7  [-]
  2015    178  56.2  0.85  -2.772     7.8  [-]   <-- peor anyo
  2016    289  67.8  1.54  +11.759    3.5  [+]
  2017    279  59.1  0.97   -773      9.4  [-]
  2018    295  59.3  1.15  +4.019     7.7  [+]   <-- aguanta donde restrictivos fallan
  2019    265  61.5  1.35  +7.941     4.7  [+]
  2020    263  63.5  1.27  +7.624     6.1  [+]
  2021    246  65.4  1.48  +11.241    4.0  [+]
  2022    347  66.9  1.60  +26.459    3.7  [+]
  2023    213  61.0  1.36  +11.801    7.0  [+]
  2024    261  62.1  1.55  +16.094    6.7  [+]
  2025    286  64.7  1.83  +24.538    4.4  [+]

  Anyos positivos: 9 de 12 (FALLA regla >=10/12)
  Anyos negativos: 2014, 2015, 2017
  Anyos POSITIVOS CONSECUTIVOS: 8 (2018-2025) <-- DATO CLAVE

--- METRICAS GLOBALES ---

  N trades total: 3.098 (muy alto, no overfit por pocos trades)
  DD historico orden real: 8.70%
  MC P50/P95/P99: 6.37% / 10.17% / 12.46%
  MC P95 < 2x DD historico (17.41%): PASA
  Annual % sobre $50k: 19.64%
  PnL promedio/anyo: $9.820

--- ESCALADO A CUENTAS REALES ---

  Cuenta $15k FundedNext: ~$2.946/anyo esperado, DD esperado ~$1.305 (8.70%)
  Cuenta $5k  Capital Pt: ~$982/anyo esperado, DD esperado ~$435

  Limite prop firm tipico: DD diario 5%, DD total 10%
  Year-malo 2015: -5.5% sobre cap = -$827 ($15k) / -$275 ($5k)
  Year-malo 2017 DD intra-anual 9.4%: $1.410 ($15k) / $470 ($5k)
    -> Apurado pero dentro de limite 10% en cuenta $5k

--- LA DECISION ---

Bot esta operando AHORA con dinero real. Tres opciones:

(M1) MANTENER + vigilancia activa.
    Razon: 8 anyos seguidos positivos sugieren regimen actual favorable.
    Annual 19.64% es muy atractivo. Vigilar DD diario, parar si pasa 5%.
    Riesgo: si vuelve regimen 2014-2017, perdida real ~5% del cap.

(P) PAUSAR EA inmediatamente.
    Razon: regla 10/12 no se cumple. Riesgo de regimen no controlado.
    Costo: perder ~$2.946/anyo en FundedNext + ~$982 en Capital Point.

(R) REDUCIR sizing 0.5 -> 0.3 + mantener.
    Razon: compromiso. Annual cae a ~12% pero peor anyo cae a -3.3%.
    Margen mayor frente a limite prop firm.

--- CONTEXTO ADICIONAL ---

El usuario tiene reglas anti-overfit estrictas:
- feedback_validacion_estrategias (checklist 7 puntos, OBLIGATORIO)
- feedback_regimen_dependiente (year-by-year + MC<2xDD)
- feedback_ea_safety_obligatorio (filtro noticias + circuit breakers)

El bot tecnicamente FALLA un punto (10/12), pero pasa todos los demas.
La pregunta es: ¿8 anyos seguidos positivos COMPENSA el fallo en 2014-2015-2017?

Hipotesis alternativa: el mercado FX cambio estructuralmente en 2018 (post-Trump,
post-Brexit, mas intervencion banca central). Si esa estructura persiste, los 8
anyos seguidos no son aleatorios sino reflejo del regimen actual.

Hipotesis pesimista: el regimen 2014-2017 vuelve cuando menos lo espero, y el
bot pierde justo cuando es mas grave (cuenta cargada).

--- INSTRUCCIONES 6 SOMBREROS ---

⚪ BLANCO  Datos verificables. Que sabemos del regimen 2014-2017 vs 2018+?
   Que falta para mejor decision?

🔴 ROJO   Como te sientes con esto? Miedo a apagar bot rentable? Avaricia por
   annual 19.6%? Sin justificar.

⚫ NEGRO   Escenarios de fracaso de cada opcion M1/P/R. Que pasa si vuelve
   2015 con cuenta cargada? Que pasa si pauso bot rentable y mantengo capital
   parado?

🟡 AMARILLO  Que ganamos con cada opcion? Annual, paz mental, opcionalidad.

🟢 VERDE   Opciones no consideradas. Detectar regimen en tiempo real?
   Tomar profit cada N meses? Stop-loss agregado anual?

🔵 AZUL  Sintesis y decision concreta. Si M1, plan de vigilancia exacto. Si P,
   plan de re-deploy futuro. Si R, justificar el nuevo sizing.

Espanyol. Conciso. Accionable. Esta decision afecta $20k reales del usuario.
"""

print("Consultando DeepSeek con 6 sombreros sobre AUDNZD-v3 real...")
print()
resp = client.chat.completions.create(
    model="deepseek-chat",
    messages=[
        {"role": "system", "content": "Eres equipo 6 sombreros. Conoces la diferencia entre decision tecnica y decision financiera con dinero real. Espanyol. Accionable. Sin clichés."},
        {"role": "user", "content": CONTEXTO},
    ],
    temperature=0.4,
    max_tokens=3500,
)

print("=" * 72)
print("  DeepSeek 6 sombreros — AUDNZD-v3 real, mantener o pausar?")
print("=" * 72)
print()
print(resp.choices[0].message.content)
print()
print("=" * 72)
print(f"  Tokens: in={resp.usage.prompt_tokens}, out={resp.usage.completion_tokens}")
print("=" * 72)
