================================================================
  GBPJPY Bot — Estrategia Balanceada
  Version 1.0 | 2026-05-08
================================================================

RESULTADOS HISTORICOS (2020-2025)
----------------------------------
  Capital: $50.000 -> $153.577  (+207%)
  WR: 20.6%  |  PF: 1.46  |  DD: 19.6%
  NINGUN AÑO NEGATIVO en 5 años

INSTALACION
-----------
  pip install -r requirements.txt

CONFIGURACION
-------------
  Editar config.py -> DATA_PATH = "ruta\a\GBPJPY_M1.csv"
  Datos gratis: dukascopy.com/trading-tools/

USO
---
  python main.py

ARCHIVOS
--------
  main.py      - Ejecutar este
  config.py    - Parametros (TP=3x, BE=0.8x, SL max 30 pips)
  strategy.py  - Logica de señales
  backtest.py  - Motor de simulacion
================================================================
