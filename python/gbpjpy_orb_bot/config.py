"""
GBPJPY ORB Bot — Configuración
Edita DATA_PATH con la ruta a tu CSV de Dukascopy antes de ejecutar.
"""

DATA_PATH = r"C:\Users\alber\OneDrive\Desktop\Nueva carpeta\GBPJPY_M1_dukas.csv"

START_YEAR  = 2020
START_MONTH = 1
END_YEAR    = 2025
END_MONTH   = 12

INITIAL_CAPITAL = 50_000.0
RISK_PCT        = 0.01       # 1% riesgo por lote (doble entrada = 0.5% cada una)
MAX_LOTS        = 4.0

# ── Sesiones (UTC/GMT) ─────────────────────────────────────────────────────────
SESSION         = "LONDON"   # "NY", "LONDON", "BOTH"  ← Londres es la mejor sesión para GBPJPY
NY_START_H      = 13
NY_START_M      = 30         # 13:30 GMT = 09:30 EST
NY_END_H        = 20

LDN_START_H     = 8
LDN_START_M     = 0          # 08:00 GMT
LDN_END_H       = 16

# ── Rango ORB ──────────────────────────────────────────────────────────────────
MIN_RANGE_PIPS  = 5          # Rango mínimo aceptable en pips JPY
MAX_RANGE_PIPS  = 30         # Rango máximo (optimizado: 30 pips)

# ── TP / SL ────────────────────────────────────────────────────────────────────
TP1_MULT        = 1.5        # TP1 = rango × 1.5  (posición 1)
TP2_MULT        = 5.0        # TP2 = rango × 5.0  (posición 2 - dejar correr)
BE_OFFSET_PIPS  = 0          # Mover SL a entry exacto cuando TP1 se alcanza
USE_DOUBLE_ENTRY= True       # 2 posiciones por señal (TP1 + TP2)
CLOSE_EOS       = True       # Cerrar al final de sesión Londres

MAX_TRADES_DAY  = 2
DIRECTION       = "LONG_ONLY"  # Solo largos en GBPJPY Londres ← tendencia alcista histórica
