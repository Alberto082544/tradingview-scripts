"""Strategy Combiner — Agente DeepSeek que propone combos de filtros/estrategias.

Le da contexto del sistema actual y le pide N combos LÓGICOS a probar.
Cada combo viene con: que probar, en qué par, por qué tiene sentido, qué espera.

Uso:
  python monitor/strategy_combiner.py             # 5 propuestas defecto
  python monitor/strategy_combiner.py --n 10      # 10 propuestas
  python monitor/strategy_combiner.py --target audnzd  # solo combos para AUDNZD
"""
import sys, os, json, argparse
sys.stdout.reconfigure(encoding='utf-8')

# Cargar .env
from pathlib import Path
ENV_PATH = Path(__file__).resolve().parents[2] / 'trading_researcher' / '.env'
if ENV_PATH.exists():
    for line in ENV_PATH.read_text(encoding='utf-8').splitlines():
        if '=' in line and not line.strip().startswith('#'):
            k, v = line.split('=', 1)
            os.environ.setdefault(k.strip(), v.strip())

try:
    from openai import OpenAI
except ImportError:
    print("Falta openai: pip install openai")
    sys.exit(1)

API_KEY = os.environ.get('DEEPSEEK_API_KEY')
if not API_KEY:
    print("Falta DEEPSEEK_API_KEY en .env")
    sys.exit(1)

client = OpenAI(api_key=API_KEY, base_url="https://api.deepseek.com")

CONTEXTO_SISTEMA = """
# Sistema actual de trading algorítmico

## Bots validados y operativos (forex y NAS100)

| Bot | Familia | Par | PF OOS | DD | Ann | WF |
|-----|---------|-----|--------|----|------|----|
| AGM_Ranger_C_AUDNZD v3.3 | Mean Reversion | AUDNZD M15 | 1.54 | 4.6% | 25.4% | 1.27 |
| AGM_MA_Cross_EURUSD v2.3 | Trend Following | EURUSD M15 | 1.41 | 4.8% | 24.4% | 1.13 |
| AGM_EMA9_VWAP_NAS100 v1.0 | EMA9+VWAP+RSI | NAS100 M15 | 1.76 | 3.0% | 17.1% | 1.34 |
| AGM_XAUUSD_ORB v2.1 | Opening Range Breakout | XAUUSD M15 | 1.32 | 3.75% | 7.6% | 1.21 |
| AGM_JasperOB_NAS100 v1.0 | Order Block + EMA200 H4 | NAS100 M15 | 1.49 | 3.9% | 5.5% | 1.18 |

## Indicadores ya probados
- Bollinger Bands, RSI, Stochastic, ADX H4, EMA9/21/200, VWAP diario,
  ATR, ORB (Opening Range), Order Block, FVG (Fair Value Gap),
  vela rechazo (wick ratio)

## Datos disponibles para backtest
- Forex M15 12 años (2014-2025): EURUSD, GBPUSD, AUDNZD, AUDCAD, GBPJPY
- ÍNDICES M15 6 años (2020-2025): SPY (SP500 proxy), QQQ (NAS100 proxy)
- (NO disponibles: DAX, UK100, índices puros)

## Lo que YA he probado y NO funciona
- EMA9+VWAP+RSI en forex (PF<1.3 en todos)
- Ranger C en índices (mean reversion no encaja con tendencia)
- Stoch+ADX en EURUSD (reduce profit sin mejora)
- EMA200+StochRSI en EURUSD (PF OOS 0.7-1.1)
- Jasper OB SOLO (sin filtros) en forex (DD 30-49%)
- ORB v4.7 en SPY/QQQ (PF cerca de 1.0)

## Criterio para considerar viable un combo
- PF OOS > 1.3
- DD OOS < 10%
- WF ratio > 0.85
- N OOS >= 50 trades
- Idealmente: 7/7 checklist anti-overfit

## Restricciones operativas
- Las cuentas son fondeo: DD diario máx 5%, DD total máx 10%
- Bots deben ser bidireccionales (long+short) idealmente
- 2 temporalidades obligatorias: H4 filtro + M15 entrada
"""

PROMPT_PROPONER = """
Eres un quant trader experto. Tienes el sistema descrito arriba.

Necesito que propongas {n} **COMBOS NUEVOS A PROBAR** que NO he probado todavía.

Reglas:
1. Cada combo debe ser **realmente NUEVO** (no repetir lo ya descartado)
2. Debe ser LÓGICAMENTE COHERENTE (no aleatorio)
3. Justifica POR QUÉ podría funcionar (hipótesis del mercado, no solo numérica)
4. Indica qué métricas esperarías si funciona (PF, DD aproximados)
5. Aporta cosas distintas a lo que ya tengo

Posibles direcciones:
- Aplicar lógica de un bot ganador a otro par
- Combinar 2 indicadores de bots distintos
- Probar nueva familia (pairs trading, breakout, news)
- Filtro de régimen (HMM, Choppiness Index)
- Position sizing dinámico (Kelly)

{filtro_target}

Responde en JSON con esta estructura EXACTA:

```json
{{
  "combos": [
    {{
      "id": 1,
      "nombre": "Nombre corto descriptivo",
      "estrategia_base": "Familia o estrategia",
      "par": "EURUSD/AUDNZD/QQQ/etc",
      "timeframe": "M15 + H4",
      "indicadores_clave": ["EMA200 H4", "RSI <30", "etc"],
      "hipotesis": "Por qué tiene sentido (1-2 frases)",
      "esperado_pf": 1.4,
      "esperado_dd": 5.0,
      "esfuerzo_horas": 2,
      "prioridad": "alta/media/baja"
    }}
  ]
}}
```

NO añadas texto fuera del JSON. Solo el JSON.
"""


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--n', type=int, default=5, help='Numero de combos')
    p.add_argument('--target', type=str, default='', help='Filtrar combos para un par')
    args = p.parse_args()

    filtro_target = ""
    if args.target:
        filtro_target = f"\nPRIORIZAR combos enfocados en: **{args.target.upper()}**"

    prompt = CONTEXTO_SISTEMA + PROMPT_PROPONER.format(n=args.n, filtro_target=filtro_target)

    print(f"Llamando a DeepSeek para {args.n} combos...", flush=True)
    resp = client.chat.completions.create(
        model="deepseek-reasoner",  # razonamiento profundo
        messages=[
            {"role": "system", "content": "Eres un quant trader senior. Responde SIEMPRE en JSON valido sin texto extra."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
    )

    text = resp.choices[0].message.content
    # Extraer JSON
    if '```json' in text:
        text = text.split('```json')[1].split('```')[0].strip()
    elif '```' in text:
        text = text.split('```')[1].split('```')[0].strip()

    try:
        data = json.loads(text)
        combos = data.get('combos', [])
    except json.JSONDecodeError as e:
        print(f"Error parseando JSON: {e}")
        print("Respuesta cruda:")
        print(text[:2000])
        return

    print(f"\n{'='*88}")
    print(f"  PROPUESTAS DeepSeek ({len(combos)} combos)")
    print(f"{'='*88}\n")

    for c in combos:
        print(f"### [{c['id']}] {c['nombre']}")
        print(f"  Estrategia: {c.get('estrategia_base','')}")
        print(f"  Par: {c.get('par','')}  | Timeframe: {c.get('timeframe','')}")
        print(f"  Indicadores: {', '.join(c.get('indicadores_clave',[]))}")
        print(f"  Hipotesis: {c.get('hipotesis','')}")
        print(f"  Esperado: PF≈{c.get('esperado_pf','?')}, DD≈{c.get('esperado_dd','?')}%")
        print(f"  Esfuerzo: {c.get('esfuerzo_horas','?')}h | Prioridad: {c.get('prioridad','?')}")
        print()

    # Guardar
    out_dir = os.path.join(os.path.dirname(__file__), '..', 'reports')
    os.makedirs(out_dir, exist_ok=True)
    from datetime import datetime
    fname = f"combiner_propuestas_{datetime.now().strftime('%Y-%m-%d_%H%M')}.md"
    out_path = os.path.join(out_dir, fname)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(f"# Propuestas Strategy Combiner — {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
        for c in combos:
            f.write(f"## [{c['id']}] {c['nombre']}\n\n")
            f.write(f"- **Estrategia base:** {c.get('estrategia_base','')}\n")
            f.write(f"- **Par:** {c.get('par','')}\n")
            f.write(f"- **Timeframe:** {c.get('timeframe','')}\n")
            f.write(f"- **Indicadores:** {', '.join(c.get('indicadores_clave',[]))}\n")
            f.write(f"- **Hipótesis:** {c.get('hipotesis','')}\n")
            f.write(f"- **Esperado:** PF≈{c.get('esperado_pf','?')}, DD≈{c.get('esperado_dd','?')}%\n")
            f.write(f"- **Esfuerzo:** {c.get('esfuerzo_horas','?')}h\n")
            f.write(f"- **Prioridad:** {c.get('prioridad','?')}\n\n")

    print(f"  Guardado: {out_path}")


if __name__ == '__main__':
    main()
