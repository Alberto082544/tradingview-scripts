"""
Lee las secciones clave del EA Strategy 4.45.147.mq5 y pide a DeepSeek
que las convierta en una estrategia Python lista para el BacktestEngine.
El resultado se guarda en strategies/gbpjpy_sq_4_45_147.py
"""

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

MQ5_PATH = r"C:\Users\alber\OneDrive\Desktop\Strategy 4.45.147.mq5"
OUT_PATH  = os.path.join(os.path.dirname(__file__), "..", "strategies", "gbpjpy_sq_4_45_147.py")

# Solo enviamos las secciones relevantes para ahorrar tokens de DeepSeek
STRATEGY_LOGIC = """
== PARÁMETROS CLAVE ==
MABarOpensPeriod1 = 20   → SMA(20) del Close en M15
MABarOpensPeriod2 = 100  → SMMA(100) del Close en M15
MABarOpensPeriod3 = 30   → SMA(30) del Close en H4  (subchart2)
MABarOpensPeriod4 = 40   → EMA(40) del Low en M15 (para LONG) / EMA(40) del High en M15 (para SHORT)
ATRHigherPeriod1 = 14    → ATR(14) en H4 (subchart2)
RSIPeriod1 = 50          → RSI(50) del Low en H4 para LONG / RSI(50) del High en H4 para SHORT
PriceEntryMult1 = 0.7
StopLossCoef1 = 1.8
ProfitTargetCoef1 = 2.6
TrailingStopCoef1 = 1.2
TrailingActCef1 = 1.1
MoveSL2BECoef1 = 1.1
ExitAfterBars1 = 10

== SEÑALES ==
LONG cuando (todas en barra nueva):
  1. Open_M15[1] > SMA(20)[1]
  2. Open_M15[1] > SMMA(100)[1]
  3. Open_H4[1]  > SMA(30)[1]   ← filtro multi-TF
  4. Open_M15[1] > EMA(40,Low)[1]
  5. ATR(14)[H4][1] > 0.5
  6. RSI(50,Low)[H4] bajando en las últimas 2 barras

SHORT cuando (todas en barra nueva), solo si NO hay LONG:
  1. Open_M15[1] < SMA(20)[1]
  2. Open_M15[1] < SMMA(100)[1]
  3. Open_H4[1]  < SMA(30)[1]
  4. Open_M15[1] < EMA(40,High)[1]
  5. ATR(14)[H4][1] > 0.5
  6. RSI(50,High)[H4] subiendo en las últimas 2 barras

== ENTRADA ==
LONG:  BUY STOP en  Highest(50,High) + 0.7 × SmallestRange(50)
SHORT: SELL STOP en Lowest(50,Low)   - 0.7 × SmallestRange(50)

Donde SmallestRange(N) = mínimo de (High-Low) de las últimas N barras

== SL / TP ==
SL   = 1.8 × ATR(20)  desde el precio de entrada
TP   = 2.6 × ATR(30)  desde el precio de entrada

== GESTIÓN DURANTE LA OPERACIÓN ==
Move-SL-to-BE: cuando el precio se aleje 1.1×ATR(50) a favor, mover SL al precio de entrada
Trailing Stop: activar cuando el precio se aleje 1.1×ATR(90) a favor; trailing de 1.2×ATR(185)
Exit after Bars: cerrar forzosamente tras 10 barras en M15

== FILTROS ==
- Solo operar de 07:00 a 20:00 (hora del servidor)
- No operar fines de semana (cerrar viernes a las 20:00)
- Máx. 5 operaciones por día
- SL mínimo 13 pips, máximo 40 pips (1 pip GBPJPY = 0.01)
- TP mínimo 15 pips, máximo 80 pips

== MONEY MANAGEMENT ==
Riesgo: 0.5% del balance por operación
Lotes = (balance × 0.005) / (SL_en_pips × pip_value_por_lote)
"""

PROMPT = f"""Eres un experto en backtesting cuantitativo con Python.

Convierte esta estrategia de trading (MT5/MQL5) a Python puro.

{STRATEGY_LOGIC}

REQUISITOS DEL CÓDIGO:
1. Usa pandas y numpy únicamente (sin TA-Lib).
2. Crea dos funciones principales:
   - add_indicators(df_m15: pd.DataFrame, df_h4: pd.DataFrame) -> pd.DataFrame
     Añade al df_m15 todas las columnas necesarias (MAs, ATRs, RSI, Highest, Lowest, SmallestRange)
     usando df_h4 para los indicadores de temporalidad alta.
   - generate_signals(df: pd.DataFrame) -> pd.DataFrame
     Añade columnas: 'long_signal', 'short_signal', 'entry_price', 'sl', 'tp'
     basadas en los criterios descritos.
3. Implementa SMMA (Smoothed Moving Average / Wilder's MA) correctamente.
4. Implementa SmallestRange(N) = min(high-low) de las últimas N barras.
5. Las columnas de H4 deben alinearse al M15 con merge_asof o reindex+ffill.
6. Añade comentarios concisos donde la lógica no sea obvia.
7. NO implementes trailing stop ni move-to-BE en estas funciones
   (lo hará el motor de backtest barra a barra).
8. Incluye al inicio del archivo las constantes de configuración como variables globales.

Devuelve SOLO el código Python, sin explicaciones adicionales.
El archivo se guardará como strategies/gbpjpy_sq_4_45_147.py
"""


def call_deepseek(prompt: str) -> str:
    key = os.getenv("DEEPSEEK_API_KEY")
    if not key:
        raise ValueError("Falta DEEPSEEK_API_KEY en .env")
    client = OpenAI(api_key=key, base_url="https://api.deepseek.com")
    resp = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=3000,
    )
    return resp.choices[0].message.content


def main():
    print("  Enviando lógica de estrategia a DeepSeek...")
    code = call_deepseek(PROMPT)

    # Limpiar bloques de markdown si DeepSeek los incluye
    if code.startswith("```"):
        lines = code.splitlines()
        code = "\n".join(
            line for line in lines
            if not line.strip().startswith("```")
        )

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(code)

    print(f"  Estrategia guardada → {OUT_PATH}")
    print("\n  *** Revisa el archivo antes de correr el backtest ***")


if __name__ == "__main__":
    main()
