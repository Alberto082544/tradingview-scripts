"""Consulta DeepSeek 6 sombreros: ¿descartar o arreglar bots del portfolio Phase 1?"""
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
SECUENCIAL y SIN MEZCLAR ROLES. Decision: ¿descartar algun bot del portfolio
Phase 1, o intentar arreglar los problematicos?

--- PORTFOLIO PHASE 1 (5 bots, operando en FundedNext $15k + The 5%ers $5k) ---

Hoy 2026-05-22 hemos validado los 5 bots con year-by-year + Monte Carlo + GT-Score
(metrica anti-overfitting con 40% PSR, 25% p-value, 20% consistencia anyos, 15% TVaR).

### Bot 1: AUDCAD Ranger-C Stoch (Mean Reversion)
- Stoch + RSI + BB + ADX H4. Backtest 2014-2025 = 12 anyos.
- Year-by-year: 12/12 anyos positivos
- DD historico real: 7.59% | MC P95: 17.03% (FALLA regla MC<2xDD = 15.18%)
- OOS PF=1.36 (2022-2025), N total 1.629 trades
- GT-Score: 0.9458 (notable)
- TVaR_norm: 0.6391 (cola algo gorda)
- Solucion actual: deploy con LotRiskPct=0.5 (71% del backtest 0.7) → MC efectivo ~14.9%
- Annual real esperado: ~$4.500/anyo sobre $50k

### Bot 2: AUDNZD Ranger-C v3 (Stoch K<15 SOLO)
- Stoch (sin RSI) + BB + ADX H4. Backtest 12 anyos.
- Year-by-year: **9/12 anyos positivos** (FALLA regla 10/12)
- Anyos malos: 2014 (-$90), 2015 (-$2.772), 2017 (-$773)
- 8 anyos CONSECUTIVOS positivos 2018-2025
- DD historico real: 8.70% | MC P95: 10.17% (PASA)
- N: 3.098 trades | Annual: 19.6%
- GT-Score: 0.9043 (notable bajo)
- Consistency_norm: 0.75 (penalizado por 9/12)

### Bot 3: GBPUSD MA Cross v1 (Tendencia)
- EMA5/SMA34 + filtro D1. Backtest 12 anyos.
- Year-by-year: 12/12 anyos positivos
- DD historico real: 5.30% | MC P95: 15.73% (FALLA MC<2xDD = 10.60%)
- N: 6.269 trades (muy alto) | Annual: 52% sobre $50k (¡muy alto!)
- GT-Score: 0.9586 (sobresaliente bajo)
- RR efectivo real: 1.15 (config dice 3.0, BE+trail cortan TP)
- Parche aplicado HOY: filtro MaxATR=35 pips para evitar SL anormales

### Bot 4: EMA9+VWAP NAS100 (Trend Following)
- EMA9/EMA21+VWAP+RSI+vela rechazo. SOLO 6 anyos de datos (QQQ proxy 2020-2025).
- Year-by-year: 6/6 anyos positivos (todos OK)
- DD historico real: 3.0% | MC P95: 7.91% (PASA)
- N: 547 trades (BAJO comparado con otros) | Annual: 17.1%
- GT-Score: 0.9910 (¡el mejor del portfolio!)
- Limitacion: solo 6 anyos de historico
- Validado sobre QQQ (ETF), no NAS100 CFD directo
- Anyo 2022 fue flojo: PF=1.11, DD=11.61% (memoria del 18-may decia que era el bot menos eficiente del portfolio por DD/PnL ratio)

### Bot 5 (no en producción, era prueba): AUDNZD-Stoch combo restrictivo
- GT-Score: 0.7597 (suspenso)
- TVaR_norm: 0.00 (cola muy gorda)
- DESCARTADO ya hoy. No esta en producccion.

--- LA DECISION ---

Las dudas son:

(D1) AUDNZD Ranger-C v3: ¿descartar por regimen-dependiente (9/12 anyos)?
    O ¿mantener vigilancia activa porque 8 anyos seguidos en verde?

(D2) GBPUSD: MC P95 al 15.7% (muy alto) viola la regla MC<2xDD.
    ¿Vivimos con riesgo aceptando 12/12 anyos? ¿Reducimos sizing?
    ¿Lo "arreglamos" con cambios en BE/Trail?
    Tentativa hoy: opt BE/Trail/MaxATR dio combo con RR_eff 2.52 pero DD subio a 14.8%.

(D3) NAS100: GT-Score el mas alto (0.99) pero PnL absoluto bajo ($6.188/4anyos en
    cuenta real $15k segun memoria). ¿Mantener? ¿Subir sizing?
    Pendiente revisar si bajar LotRiskPct 0.5→0.4 sigue tiene sentido.

(D4) AUDCAD: GT=0.95 OK pero MC alto. Mismo dilema que GBPUSD.

(D5) ¿Algun bot vale la pena ARREGLAR? Como?
    Posibles ideas:
    - Filtro de regimen (HMM, ADX-D1 estructural, ATR semanal)
    - Stop-loss anual automatico
    - Detector cambio de regimen para pausar bot
    - Reescribir logica de entrada del problematico

--- CONTEXTO ADICIONAL ---

Capital total real: $20.000 (15k + 5k)
Limite prop firm tipico: DD diario 5%, DD total 10%
Filosofia usuario: validacion completa anti-overfit, year-by-year, MC, sentido economico
Restricciones: no quiere descartar bot rentable, pero tampoco quiere reventar cuenta

--- INSTRUCCIONES 6 SOMBREROS ---

⚪ BLANCO  Datos verificables. Que sabemos de cada bot? Que falta? Cual es el
   verdadero riesgo agregado del portfolio? (correlaciones, contribucion DD)

🔴 ROJO   Como te sientes con cada bot? Confianza, miedo, ganas de descartar.
   Sin justificar.

⚫ NEGRO  Riesgo de cada opcion:
   - Descartar bot rentable: perdida edge real
   - Mantener bot regimen-dep: posible perdida cuenta
   - Intentar arreglar: complejidad anyadida, sobreoptimizacion
   - No hacer nada: regimen puede volver

🟡 AMARILLO  Oportunidad. Si se mantienen los 5 robustos: $X/anyo seguro.
   Si se arregla AUDNZD: bot adicional sin riesgo.
   Si se reduce sizing GBPUSD: ¿perdida marginal compensa seguridad?

🟢 VERDE  Ideas no obvias para arreglar bots problematicos:
   - Filtros nuevos
   - Combinaciones (ensemble)
   - Reglas de pausa dinamica
   - Otra cosa creativa

🔵 AZUL  Sintesis y decision concreta:
   Para CADA bot (1-5): MANTENER tal cual / MANTENER con ajuste / ARREGLAR (como?) / DESCARTAR
   Si arreglar: plan exacto.
   Si descartar: justificar perdida de edge.
   Si mantener: condiciones de vigilancia.

Espanyol. Conciso. Accionable. Decision afecta $20k REALES del usuario.
"""

print("Consultando DeepSeek sobre portfolio Phase 1...")
print()
resp = client.chat.completions.create(
    model="deepseek-chat",
    messages=[
        {"role": "system", "content": "Eres equipo 6 sombreros. Aplicas el metodo con rigor, sin mezclar roles. Espanyol. Accionable. Esta decision afecta dinero real."},
        {"role": "user", "content": CONTEXTO},
    ],
    temperature=0.4,
    max_tokens=4000,
)

print("=" * 72)
print("  DeepSeek 6 sombreros — Portfolio Phase 1 ¿descartar o arreglar?")
print("=" * 72)
print()
print(resp.choices[0].message.content)
print()
print("=" * 72)
print(f"  Tokens: in={resp.usage.prompt_tokens}, out={resp.usage.completion_tokens}")
print("=" * 72)
