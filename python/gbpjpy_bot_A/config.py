"""
GBPJPY Bot A — Estrategia Balanceada — Configuración
Edita DATA_PATH con la ruta a tu CSV de Dukascopy antes de ejecutar.
"""

DATA_PATH = r"C:\ruta\a\tu\GBPJPY_M1_dukas.csv"

START_YEAR  = 2020
START_MONTH = 1
END_YEAR    = 2025
END_MONTH   = 12

INITIAL_CAPITAL = 50_000.0
RISK_PCT        = 0.005
MAX_LOTS        = 4.0
USDJPY_RATE     = 145.0

# ── Parámetros ESTRATEGIA A (Balanceada) ─────────────────────────────────────
TP_MULT         = 3.0    # Take Profit = 3 × Stop Loss
BE_MULT         = 0.8    # Break-Even cuando ganancia >= 0.8 × SL
EXIT_BARS       = 30     # Salida por tiempo (30 barras = 7h 30min)
MAX_SL_PIPS     = 30
MIN_SL_PIPS     = 15

SESSION_START   = 7
SESSION_END     = 19
BAD_HOURS       = {8}
MAX_TRADES_DAY  = 5
ORDER_EXPIRY    = 24

RSI_PERIOD      = 14
EMA_FAST        = 20
EMA_SLOW        = 100
EMA_H4          = 200
ATR_PERIOD      = 14
PULLBACK_RATIO  = 0.382
