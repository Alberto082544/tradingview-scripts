"""Consulta DeepSeek 6 sombreros: fracaso del grid restrictivo AUDNZD-Stoch."""
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
SECUENCIAL y SIN MEZCLAR ROLES. Decision: que hacer con AUDNZD-Stoch tras
fracaso del grid restrictivo que TU mismo recomendaste en consulta previa.

--- CONTEXTO COMPLETO ---

Familia Ranger C = Mean Reversion BB + RSI + ADX_H4 (lateral) + Stoch
opcional. En produccion ya con AUDNZD (sin Stoch) y AUDCAD (con Stoch).

En consulta previa recomendaste grid restrictivo para AUDNZD con StochMode=2:
  - MinSL [20,25]
  - ExitBars [16,20]
  - ADX_H4_Max [20,25]
  - Resto fijo: StochMode=2, Stoch_L=20, Stoch_S=75, RSI_L=40, RSI_S=60
  - 8 combos totales
  - Filtros post-opt: OOS_DD<=6%, OOS_PF>=1.10, WF>=1.0

EJECUCION: 2 combos pasaron los filtros post-opt. Validamos ambos con
year-by-year + Monte Carlo (2000 iteraciones).

--- COMBO #1: MinSL=25 Exit=16 ADX<20 (mejor por score) ---

Year-by-year (12 anyos 2014-2025):
  2014 PF=1.08 +$616    | 2015 PF=0.99 -$78    | 2016 PF=1.15 +$1.785
  2017 PF=0.82 -$1.901  | 2018 PF=0.75 -$2.512 | 2019 PF=1.21 +$1.374
  2020 PF=1.11 +$917    | 2021 PF=1.69 +$3.427 | 2022 PF=1.70 +$9.115
  2023 PF=0.92 -$968    | 2024 PF=1.39 +$2.911 | 2025 PF=1.00 +$49

  Anyos positivos: 8/12 (FALLA regla >=10/12)
  DD historico: 11.82%
  MC P50/P95/P99: 9.01% / 14.15% / 16.80%
  MC P95 < 2x DD: PASA (14.15% < 23.64%)
  VEREDICTO: DUDOSO regimen-dependiente

--- COMBO #2: MinSL=20 Exit=20 ADX<20 ---

Year-by-year:
  2014 PF=1.19 +$1.650  | 2015 PF=1.00 -$25     | 2016 PF=1.47 +$6.871
  2017 PF=0.75 -$3.944  | 2018 PF=0.71 -$4.328  | 2019 PF=1.15 +$1.493
  2020 PF=1.23 +$2.486  | 2021 PF=1.76 +$5.002  | 2022 PF=1.56 +$10.493
  2023 PF=1.11 +$1.598  | 2024 PF=1.26 +$3.115  | 2025 PF=1.12 +$1.764

  Anyos positivos: 9/12 (FALLA regla >=10/12 por POCO)
  DD historico: 15.55%
  MC P50/P95/P99: 10.01% / 16.15% / 19.53%
  MC P95 < 2x DD: PASA (16.15% < 31.10%)
  VEREDICTO: DUDOSO regimen-dependiente

--- PATRON OBSERVADO ---

AMBOS combos fallan en 2017-2018:
  - 2017: PF 0.75-0.82 (~$1.9k-$3.9k de perdida)
  - 2018: PF 0.71-0.75 (~$2.5k-$4.3k de perdida)
  - Combo #2 pierde MUCHO mas en 2018 que combo #1 (-$4.3k vs -$2.5k)

Hipotesis del usuario: 2017-2018 en AUDNZD hubo tendencia prolongada
(no lateralidad). El filtro ADX<20 + mean reversion + Stoch quedo
"esperando" rebotes que no llegaban → SL repetidos.

OBSERVACION CRITICA: el OOS de la opt (2022-2025) NO incluia 2017-2018,
por eso parecio robusto. El filtro post-opt OOS_DD<=6% engaño porque
solo evaluaba ese periodo.

--- LA VERSION SIN STOCH (en produccion) ---

AUDNZD sin Stoch (ranger_c_audnzd_m15.py) lleva en cuenta real desde
2026-05-20 con LotRiskPct=0.7. Sin validacion year-by-year reciente
(la haremos despues si decides que vale la pena seguir).

--- 4 OPCIONES POSIBLES ---

(A1) Descartar Stoch en AUDNZD definitivamente y mantener version sin Stoch
     en produccion. Aceptar que el Stoch no aporta edge ROBUSTO en este par.

(A2) Validar AUDNZD-sin-Stoch year-by-year antes de descartar Stoch, para
     confirmar que sin Stoch funciona en 2017-2018 donde Stoch falla.

(A3) Anyadir filtro adicional anti-tendencia (ATR creciente / ADX_M15 alto)
     SOLO para Stoch en AUDNZD: si hay tendencia detectada, desactivar Stoch
     y caer a RSI solo. Hibrido.

(A4) Esperar resultados del grid normal completo AUDNZD-Stoch (corriendo,
     ~30 min), por si encuentra combo robusto con StochMode=0 (RSI solo) o
     parametros distintos que aguanten 2017-2018.

--- INSTRUCCIONES 6 SOMBREROS ---

Aplica los 6 sombreros SECUENCIAL.

⚪ BLANCO  Datos verificables. Patron 2017-2018 confirmado en ambos combos.
   Que sabemos? Que NO sabemos pero deberiamos?

🔴 ROJO   Como te sientes con esto? Frustracion por fracaso grid restrictivo
   que tu mismo recomendaste? Sin justificar.

⚫ NEGRO   Que riesgos hay en cada opcion A1-A4? Riesgo de descartar edge real?
   Riesgo de seguir buscando edge que no existe? Riesgo de complejidad anyadida?

🟡 AMARILLO  Que valor tiene cada opcion si funciona? Aprendizaje, edge real,
   simplicidad?

🟢 VERDE  Hay opciones (A5)(A6) NO consideradas? Filtros alternativos al Stoch
   (Williams %R, CCI), aproximaciones bayesianas, regime detection (HMM)?

🔵 AZUL  Sintesis. Recomendacion CONCRETA y accionable. Si dices A2, dame el
   plan exacto. Si A3, dame el filtro especifico. Si descartar, justifica.
   Reconoce si tu recomendacion previa fue erronea o no.

Espanyol. Conciso. Accionable.
"""

print("Consultando DeepSeek sobre fracaso grid restrictivo AUDNZD...")
print()
resp = client.chat.completions.create(
    model="deepseek-chat",
    messages=[
        {"role": "system", "content": "Eres equipo 6 sombreros. Aplicas el metodo con rigor y reconoces errores propios. Espanyol. Accionable."},
        {"role": "user", "content": CONTEXTO},
    ],
    temperature=0.4,
    max_tokens=3500,
)

print("=" * 72)
print("  DeepSeek 6 sombreros — fracaso grid restrictivo AUDNZD")
print("=" * 72)
print()
print(resp.choices[0].message.content)
print()
print("=" * 72)
print(f"  Tokens: in={resp.usage.prompt_tokens}, out={resp.usage.completion_tokens}")
print("=" * 72)
