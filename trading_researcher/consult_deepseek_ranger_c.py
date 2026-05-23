"""Consulta DeepSeek con 6 sombreros sobre destino AUDCAD-Stoch (resultado DUDOSO)."""
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
ROL: Eres un equipo de validacion estrategica para un quant trader que opera
cuentas de fondeo reales. Aplica el metodo 6 sombreros de Edward de Bono,
SECUENCIALMENTE y SIN MEZCLAR ROLES.

--- CONTEXTO REAL (verificado 2026-05-21) ---

Familia Ranger C = Mean Reversion BB(20,2) + RSI(14) + ADX_H4<umbral (filtro
regimen lateral) sobre H4 (filtro) + M15 (gatillo). En produccion ya con AUDNZD
desde 2026-05-20 y AUDCAD desde 2026-05-18 en Phase 1 (4 bots en cuentas reales
de $15k FundedNext y $5k Capital Point).

La version AUDCAD actualmente en portfolio es la corrida SIN estocastico
(2026-05-16, OOS_PF=1.24, WF=1.07). Ahora hemos ejecutado una opt CON
estocastico y los resultados son ambivalentes.

--- RESULTADO OPTIMIZACION AUDCAD CON ESTOCASTICO (ejecutada 2026-05-18 23:02) ---

Fichero: reports/Ranger_C_AUDCAD_Opt_Results.csv
Validacion: reports/AUDCAD_top_validation_summary.json

Mejor combo encontrado:
  StochMode=2 (RSI Y Stoch deben confirmar)
  Stoch_Long_Max=20, Stoch_Short_Min=75, Stoch_K=5, Stoch_D=3
  ADX_H4_Max=20, RSI_Long_Max=40, RSI_Short_Min=60, RSI_Confirm=1
  MinSLPips=20, ExitBars=24, TrailDistPips=8
  SL_ATR_Mult=1.5

Resultados (12 anyos 2014-2025):
  N trades total: 1.629
  DD historico: 7.59%
  Monte Carlo p50/p95/p99: 9.94% / 17.03% / 20.85%
  Anyos positivos: 12 de 12
  consistency_ok=true, mc_ok=FALSE
  Veredicto JSON: "DUDOSO: anios consistentes pero MC alto, sequencia depende del orden"

Year-by-year PF (las cifras son PF, no Profit):
  2014: 1.30  | 2015: 1.18  | 2016: 1.05  | 2017: 1.03  (flojo)
  2018: 1.21  | 2019: 1.07  | 2020: 1.46  | 2021: 1.45
  2022: 1.56  | 2023: 1.37  | 2024: 1.11  | 2025: 1.46

DD anyos: 4.32% (2020) min, 8.98% (2024) max. Coherente con DD historico 7.59%.

--- REGLA QUE VIOLA ---

El usuario tiene como regla anti-overfit: MC maxDD < 2x maxDD historico.
2 x 7.59% = 15.18%. El MC p99 es 20.85% (DENTRO p95 17.03% > 15.18% tambien).
Falla la regla.

Riesgo prop firm: DD diario tipico 5%, DD total tipico 10%. Un escenario MC malo
del 17-20% reventaria la cuenta.

--- LAS CUATRO OPCIONES A EVALUAR ---

(A') Aceptar el resultado DUDOSO y deployar AUDCAD-Stoch reemplazando la version
    sin stoch en Phase 1. Asumir riesgo MC alto a cambio de mas trades y
    consistencia anyo a anyo. Mantener vigilancia diaria.

(B') Re-optimizar AUDCAD con grid mas restrictivo para forzar MC bajo:
    aumentar MinSLPips (limitar perdida por trade), reducir ExitBars (cerrar
    antes), penalizar Stoch_Long_Max bajos. Buscar combo con MC p99 < 15%
    aunque PF baje a 1.10-1.20.

(C') Mantener AUDCAD SIN Stoch (version actual ya en portfolio, OOS_PF=1.24,
    WF=1.07) y NO tocar. Pasar a explorar Stoch en AUDNZD-stoch (variante
    ya escrita pero sin grid de opt).

(D') Descartar Stoch en toda la familia Ranger C. Hipotesis: si en AUDCAD el
    MC se descontrola con Stoch, probable que en AUDNZD tambien. El edge ya
    viene de BB+RSI+ADX_H4, anyadir Stoch puede ser ruido sobre-ajustado.

--- FILOSOFIA DEL USUARIO ---

- Checklist 7 puntos anti-overfit OBLIGATORIO (OOS_PF>=1.10, WF>=1.00,
  N>=30, anyo-a-anyo positivos, MC<2xDD, sensibilidad, sentido economico).
- Veredicto NO solo PF+DD. Tambien N trades, Annual%, WF, MC.
- Trampa regimen-dependiente: nunca validar solo con OOS reciente.
- Cuentas de fondeo reales con limites DD agresivos.

--- INSTRUCCIONES 6 SOMBREROS ---

Aplica los 6 sombreros EN ESTE ORDEN ESTRICTO. Cada uno es un experto distinto
con su propia logica. NO mezclar roles. Profundo, concreto, accionable.

⚪ BLANCO (hechos objetivos)
   Solo datos verificables del dossier. Que falta saber para mejor decision?
   No emitas juicio.

🔴 ROJO (emocion / intuicion)
   Si fueras el trader, que sentirias ante cada opcion? Miedo a reventar la
   cuenta? Avaricia por mas trades? Cansancio de re-optimizar? Sin justificar.

⚫ NEGRO (riesgos)
   Escenarios donde cada opcion FRACASA. Trampa overfit al anyadir Stoch sobre
   BB+RSI+ADX. Riesgo prop firm. Riesgo de cambiar bot en produccion.

🟡 AMARILLO (oportunidad)
   Si cada opcion funciona, que valor REAL aporta. Escalabilidad a AUDNZD u
   otros pares. Que se gana frente al riesgo.

🟢 VERDE (creatividad)
   Hay opciones NO consideradas? (E')? (F')? Alternativas al Stoch (Williams %R,
   CCI, Z-score, regime filter HMM)? Mezclas? Filtros adicionales?

🔵 AZUL (sintesis y decision)
   Integra los 5 anteriores. Elimina contradicciones. Recomendacion CONCRETA:
   que hacer HOY, en que orden, que vigilar, cuando parar. Si recomiendas
   B', detalla el grid propuesto. Si C' o D', justifica el descarte.

Responde en espanyol. No inventes datos.
"""

print("Consultando DeepSeek con 6 sombreros sobre AUDCAD-Stoch DUDOSO...")
print()
resp = client.chat.completions.create(
    model="deepseek-chat",
    messages=[
        {"role": "system", "content": "Eres un equipo de pensamiento estrategico que simula 6 expertos distintos analizando una decision real de quant trading algoritmico. Aplicas el metodo 6 sombreros de Edward de Bono con rigor: secuencial, sin mezclar roles, profundo, concreto y accionable. Responde en espanyol."},
        {"role": "user", "content": CONTEXTO},
    ],
    temperature=0.4,
    max_tokens=3500,
)

print("=" * 72)
print("  RESPUESTA DeepSeek — 6 SOMBREROS sobre AUDCAD-Stoch DUDOSO")
print("=" * 72)
print()
print(resp.choices[0].message.content)
print()
print("=" * 72)
print(f"  Tokens: in={resp.usage.prompt_tokens}, out={resp.usage.completion_tokens}")
print("=" * 72)
