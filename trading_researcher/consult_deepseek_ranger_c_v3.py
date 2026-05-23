"""Consulta DeepSeek con 6 sombreros: disenyar grid restrictivo AUDNZD-Stoch."""
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
ROL: Equipo de validacion estrategica. Apply 6 sombreros de Edward de Bono
SECUENCIAL y SIN MEZCLAR ROLES, para una decision concreta de disenyo de grid
de optimizacion.

--- CONTEXTO RECIENTE ---

He ejecutado opt AUDCAD con Stoch y el combo ganador es:
  StochMode=2, MinSL=20, ExitBars=24, TrailDist=8, RSI_L=40, RSI_S=60
  OOS_PF=1.36, OOS_DD=5.8%, WF=1.133, N OOS=608
  PERO: MC p99 = 20.85% (falla regla MC<2x DD historico, limite 15.18%)

Solucion AUDCAD: deploy con LotRiskPct=0.5 (mitad del 0.7 del backtest),
para que MC efectivo baje a ~14.9% (apenas dentro de prop firm).

--- AHORA, MISMO ENFOQUE PARA AUDNZD ---

Ya lance grid normal AUDNZD-Stoch (en ejecucion en paralelo, copia del de AUDCAD).
Quiero ADEMAS lanzar grid RESTRICTIVO que ataque el problema del MC desde
el disenyo, no via sizing.

--- DECISIONES DE DISENYO QUE NECESITO ---

(1) QUE PARAMETROS ENDURECER respecto al grid normal?
    Grid normal actual:
      MinSLPips: [12, 20]         → restrictivo: [?, ?]
      ExitBars:  [16, 24, 32]     → restrictivo: [?, ?]
      TrailDist: [8, 12]          → restrictivo: [?, ?]
      ADX_H4_Max:[20, 25, 30, 35] → restrictivo: [?, ?]
      StochMode: [0, 1, 2]        → restrictivo: [?]
      RSI_Long_Max: [40, 45, 50]  → restrictivo: [?]
      RSI_Short_Min:[50, 55, 60]  → restrictivo: [?]

    Hipotesis (cuestionables):
    - MinSL alto = perdidas individuales mas bajas → MC mas estable
    - ExitBars bajo = menos exposicion temporal → MC mas estable
    - Trail amplio = mas espacio pero menos cierres prematuros
    - ADX_H4_Max bajo = solo lateralidad fuerte → menor varianza
    - Si StochMode=2 ganador en AUDCAD, fijarlo a [2] solo
    - RSI mas estricto (RSI_L=40, RSI_S=60) = menos pero mejores trades

(2) QUE SCORING usar para encontrar lo "robusto"?
    Score normal: is_pf*0.4 + oos_pf*0.6 - is_dd*0.02
    Restrictivo: ¿score que penalice MC alto? ¿que penalice anyo con PF<1.10?
    ¿score multi-objetivo (PF, DD, consistencia anyo a anyo)?

(3) QUE FILTROS POST-OPT aplicar al CSV antes de elegir ganador?
    Ejemplo: descartar combos con OOS_DD>6% antes de ordenar por PF.

(4) HAY ALGUN PARAMETRO DEL GRID NORMAL que YA es OK y no hay que tocar?

--- APLICA 6 SOMBREROS SECUENCIAL ---

⚪ BLANCO  Datos verificables: que sabemos sobre el espacio de parametros tras
   AUDCAD? Que combos cluster aparecen como robustos? Que falta saber?

🔴 ROJO   Si fueras el quant: que params endurecer te genera CONFIANZA y
   cuales DUDA? Sin justificar.

⚫ NEGRO  Que riesgo trae endurecer cada parametro? Trampa de sobre-restringir
   = grid demasiado estrecho, no se encuentra nada robusto.

🟡 AMARILLO  Que ganamos con cada cambio? Si grid restrictivo encuentra combo
   con MC<15% y PF>1.10, que oportunidad abre?

🟢 VERDE  Ideas NO obvias. Que parametros podriamos anyadir o eliminar del
   grid que no estamos considerando? Sugerencias creativas.

🔵 AZUL  Sintesis: ESPECIFICACION CONCRETA del grid restrictivo que voy a
   implementar como `run_ranger_c_audnzd_stoch_restrictivo_opt.py`.
   Lista exacta de valores por dimension. Scoring. Filtros post-opt.

Espanyol. Conciso y accionable. No teoria, especificacion lista para implementar.
"""

print("Consultando DeepSeek con 6 sombreros sobre grid restrictivo AUDNZD...")
print()
resp = client.chat.completions.create(
    model="deepseek-chat",
    messages=[
        {"role": "system", "content": "Eres un equipo de pensamiento estrategico que aplica 6 sombreros con rigor. Output: especificacion concreta de grid de optimizacion, lista para implementar en Python. Espanyol."},
        {"role": "user", "content": CONTEXTO},
    ],
    temperature=0.4,
    max_tokens=3000,
)

print("=" * 72)
print("  DeepSeek 6 sombreros — grid restrictivo AUDNZD-Stoch")
print("=" * 72)
print()
print(resp.choices[0].message.content)
print()
print("=" * 72)
print(f"  Tokens: in={resp.usage.prompt_tokens}, out={resp.usage.completion_tokens}")
print("=" * 72)
