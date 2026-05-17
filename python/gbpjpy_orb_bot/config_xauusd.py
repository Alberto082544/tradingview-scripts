"""
XAUUSD ORB Bot — Configuracion Optima (DD Minimizado)
======================================================
Grid search: 648 combinaciones | Datos: Dukascopy 2020-2025
Mejor config DD<15%: NY LONG_ONLY TP1=0.5x TP2=4.0x Rng=40-150p

Resultados backtest:
  P&L total   : +$77,928  (+155.9% sobre $50,000)
  Winrate     : 52.6%
  Profit Factor: 1.32
  Max Drawdown: 14.9%
  Trades      : 1,364
"""

DATA_PATH       = r"C:\Users\alber\OneDrive\Desktop\Nueva carpeta\2026.5.8XAUUSD_M1_dukas-M1-No Session.csv"
INITIAL_CAPITAL = 50_000.0
RISK_PCT        = 0.005   # 0.5% por posicion

# Sesion: Nueva York 13:30-20:00 GMT
SESSION      = "NY"
NY_START_H   = 13
NY_START_M   = 30
NY_END_H     = 20

# No se usan Londres en este activo
LDN_START_H  = 8
LDN_START_M  = 0
LDN_END_H    = 16

# Parametros de la estrategia
MIN_RANGE_PIPS  = 40     # Rango minimo de apertura (40 pips XAU = $4)
MAX_RANGE_PIPS  = 150    # Rango maximo de apertura (150 pips XAU = $15)
TP1_MULT        = 0.5    # TP1 rapido: 0.5x rango (mejora WR a 52.6%)
TP2_MULT        = 4.0    # TP2 extension: 4x rango
BE_OFFSET_PIPS  = 0      # BE en entry exacto tras TP1
USE_DOUBLE_ENTRY= True   # 2 posiciones por senal
CLOSE_EOS       = True   # Cierre al fin de sesion (20:00 GMT)
MAX_TRADES_DAY  = 1      # 1 senal diaria suficiente en XAU
DIRECTION       = "LONG_ONLY"  # Sesgo alcista demostrado en NY session

# Pip para XAU
_pip            = 0.1    # 1 pip XAU = $0.10
_pip_usd        = 10.0   # $10 por pip por lote estandar
MAX_LOTS        = 4.0
