"""
GBPJPY Bot — Configuración
Edita DATA_PATH con la ruta a tu CSV de Dukascopy antes de ejecutar.
"""

# ── RUTA AL ARCHIVO DE DATOS ──────────────────────────────────────────────────
# Descarga gratis en: https://www.dukascopy.com/trading-tools/widgets/tools/historical_data_feed/
# Formato: GBPJPY M1, exportar como CSV
DATA_PATH = r"C:\ruta\a\tu\GBPJPY_M1_dukas.csv"

# ── FECHAS DEL BACKTEST ───────────────────────────────────────────────────────
START_YEAR  = 2020
START_MONTH = 1
END_YEAR    = 2025
END_MONTH   = 12

# ── CAPITAL Y RIESGO ──────────────────────────────────────────────────────────
INITIAL_CAPITAL = 50_000.0   # Capital inicial en USD
RISK_PCT        = 0.005      # Riesgo por operación: 0.5%
MAX_LOTS        = 4.0        # Máximo de lotes por operación
USDJPY_RATE     = 145.0      # Tipo de cambio aproximado USD/JPY

# ── PARÁMETROS DE LA ESTRATEGIA ───────────────────────────────────────────────
TP_MULT         = 5.0    # Take Profit = 5 × Stop Loss
BE_MULT         = 1.5    # Break-Even activa cuando ganancia >= 1.5 × SL
EXIT_BARS       = 80     # Salida por tiempo (80 barras M15 = 20 horas)
MAX_SL_PIPS     = 30     # Solo trades con SL natural <= 30 pips
MIN_SL_PIPS     = 15     # Stop Loss mínimo

# ── SESIÓN OPERATIVA ──────────────────────────────────────────────────────────
SESSION_START   = 7      # Hora UTC de inicio
SESSION_END     = 19     # Hora UTC de fin (no opera desde las 19:00)
BAD_HOURS       = {8}    # Horas excluidas (históricamente malas)
MAX_TRADES_DAY  = 5      # Máximo de operaciones por día
ORDER_EXPIRY    = 24     # Barras hasta que expira una orden pendiente

# ── INDICADORES ───────────────────────────────────────────────────────────────
RSI_PERIOD      = 14
EMA_FAST        = 20
EMA_SLOW        = 100
EMA_H4          = 200
ATR_PERIOD      = 14
PULLBACK_RATIO  = 0.382   # Nivel Fibonacci de retroceso
