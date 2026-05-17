"""
GBPJPY ORB — Config DD19 (Solo Largos)
=======================================
Sesion: Londres 08:00 GMT | Solo Largos
Backtest 2020-2025:
  P&L   : +$48,502 (+97%)
  WR    : 39.1%
  PF    : 1.10
  DD Max: 19.3%  ← bajo drawdown
  Trades: 2,322
"""
DATA_PATH       = r"C:\Users\alber\OneDrive\Desktop\Nueva carpeta\GBPJPY_M1_dukas.csv"
INITIAL_CAPITAL = 50_000.0
RISK_PCT        = 0.005
MAX_LOTS        = 4.0

SESSION         = "LONDON"
NY_START_H, NY_START_M, NY_END_H   = 13, 30, 20
LDN_START_H, LDN_START_M, LDN_END_H = 8, 0, 16

MIN_RANGE_PIPS  = 5
MAX_RANGE_PIPS  = 30
TP1_MULT        = 1.5
TP2_MULT        = 5.0
BE_OFFSET_PIPS  = 0
USE_DOUBLE_ENTRY= True
CLOSE_EOS       = True
MAX_TRADES_DAY  = 2
DIRECTION       = "LONG_ONLY"

_pip            = 0.01
_pip_usd        = 6.9
