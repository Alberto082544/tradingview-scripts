"""Consulta DeepSeek para consenso final sobre filtro XAUUSD ORB."""
import os
import sys
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

client = OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com/v1")

CONTEXTO = """
PROBLEMA A RESOLVER: el EA AGM_XAUUSD_ORB_M15 (ORB sesion NY, M15) tiene un filtro de
rango ORB que ha quedado obsoleto. No opera en condiciones actuales del mercado.

--- DATOS DE BACKTEST ORIGINAL ---

- Backtest 2020-2025 con datos Dukascopy M1
- Filtro usado: MinRangePips=40, MaxRangePips=150 (donde 1 pip XAU = $0.10)
- Resultados (segun yearly_xauusd.csv reportado):
  Year  trades  wr     pf    pnl     dd
  2020  224     50.0%  1.15  $4537   7.2%
  2021  226     48.2%  1.02  $493    10.3%
  2022  194     54.1%  1.34  $7977   8.4%
  2023  164     53.0%  1.43  $8863   8.9%
  2024  278     54.3%  1.40  $14718  9.2%
  2025  278     54.7%  1.39  $14083  5.9%
  TOTAL: 1364 trades, 52.6% WR, PF 1.32, DD 14.9%, PnL +$77,928 sobre $50k

- El filtro [40, 150] en pips ABSOLUTOS funcionaba en ese periodo: cobertura 67%

--- DATOS DE RANGOS REALES (analisis 2026-05-19, dataset 2010-2026) ---

Anio  N    Avg$   Med$   AvgPips  AvgPct(precio)
2017  257  $2.20  $1.85  22.0p    0.175%
2018  258  $2.06  $1.71  20.6p    0.162%
2019  258  $2.78  $2.43  27.8p    0.198%
2020  259  $5.77  $4.79  57.7p    0.326%
2021  258  $5.16  $4.61  51.6p    0.287%
2022  258  $5.31  $4.74  53.1p    0.294%
2023  257  $5.27  $4.21  52.7p    0.271%
2024  259  $6.98  $6.09  69.8p    0.295%
2025  258 $10.37  $8.55 103.7p    0.299%
2026   60 $22.68 $18.21 226.8p    0.464%  <-- aqui esta el problema

PRECIO XAU: paso de $1100 (2010) a $5597 (2026 max) — multiplicador 5x.
El rango en pips ABSOLUTOS se dispara con el precio.
Pero el rango en % del PRECIO se mantiene estable entre 0.15%-0.55%.

--- COBERTURA DEL FILTRO ACTUAL [40, 150] pips ---

- En 2017-2019: 0-10% (rangos demasiado pequeños)
- En 2020-2025: 67% (funcionaba)
- En 2026: 0-10% (rangos demasiado grandes)

EL BOT NO OPERA EN 2026 porque el rango medio (227 pips) supera el MaxRangePips=150.

--- 3 OPCIONES PROPUESTAS ---

A) FILTRO RELATIVO al precio (% del Close): ej [0.15%, 0.55%] del precio actual.
   Pro: robusto a cambios de precio a largo plazo
   Con: hay que modificar el codigo del EA, y los inputs ya no son en pips

B) FILTRO ABSOLUTO recalibrado: ej [40, 220] pips para captar tambien rangos actuales.
   Pro: cambio minimo, solo modificar inputs en MT5
   Con: vuelve a quedar obsoleto si XAU sigue subiendo

C) FILTRO ABSOLUTO con auto-calibracion dinamica: el bot calcula media movil del rango
   de los ultimos 30-60 dias y usa percentiles (P10-P90) como filtro.
   Pro: se adapta solo
   Con: mayor complejidad, riesgo de calibrar mal en momentos de cambio rapido

--- PREGUNTAS PARA CONSENSO FINAL ---

1. Cual de las 3 opciones (A/B/C) recomiendas para una cuenta de fondeo $15k con limite
   DD diario 5%? Justifica.

2. Si recomiendas A (filtro relativo), que % concretos (min, max) usarias y por que?

3. Hay algo critico que se me escape? Por ejemplo:
   - El backtest fue con [40,150] y dio PF 1.32. Si cambio a un rango mas amplio,
     ¿estoy perdiendo el edge probado del backtest?
   - ¿Conviene re-optimizar TODO el grid (TP_Mult, MaxTradesDay, etc) con el filtro nuevo?

4. Para una primera prueba en demo, ¿que params concretos pondrias? (no me digas
   "depende", dame numeros).

Responde en espanol, conciso y directo. Estructura clara con numeros.
"""

print("Consultando DeepSeek sobre filtro XAUUSD ORB...")
print()
resp = client.chat.completions.create(
    model="deepseek-chat",
    messages=[
        {"role": "system", "content": "Eres senior quant especializado en ORB para metales. Tu rol: validar y mejorar diagnostico. Conciso, especifico, no inventar."},
        {"role": "user", "content": CONTEXTO},
    ],
    temperature=0.2,
    max_tokens=2200,
)

print("=" * 70)
print("  RESPUESTA DEEPSEEK")
print("=" * 70)
print()
print(resp.choices[0].message.content)
print()
print(f"  Tokens: in={resp.usage.prompt_tokens}, out={resp.usage.completion_tokens}")
