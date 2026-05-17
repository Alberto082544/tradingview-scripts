================================================================
  GBPJPY ORB Bot — Ruptura de Rango de Apertura
  Version 1.0 | 2026-05-08
================================================================

RESULTADOS HISTORICOS (2020-2025)
----------------------------------
  Capital: $50.000 -> $102.626  (+105%)
  WR: 41%  |  PF: 1.11  |  DD: 17.4%
  NINGUN AÑO NEGATIVO en 6 años
  Walk-Forward PASS | Sensibilidad PASS

ESTRATEGIA
----------
  - Sesion: SOLO Londres (08:00-16:00 GMT)
  - Direccion: Solo Largos (sesgo alcista GBPJPY)
  - Rango: primera vela M15 de sesion (5-30 pips)
  - TP1: rango x1.5 | TP2: rango x5.0
  - SL: extremo inferior del rango
  - Doble entrada: TP1 cierra, TP2 con break-even automatico

INSTALACION
-----------
  pip install -r requirements.txt

CONFIGURACION
-------------
  Editar config.py -> DATA_PATH = "ruta\a\GBPJPY_M1.csv"
  Datos gratis: dukascopy.com/trading-tools/ -> M1 -> GBPJPY

USO
---
  python main.py          (backtest completo)
  python optimize_orb.py  (optimizador multi-activo)
  python robustness.py    (pruebas de robustez)

ARCHIVOS
--------
  main.py             - Backtest principal
  config.py           - Parametros (editar DATA_PATH aqui)
  strategy.py         - Logica de señales ORB
  backtest.py         - Motor de simulacion
  optimize_orb.py     - Grid search multi-activo
  robustness.py       - Walk-forward + Monte Carlo
  GBPJPY_ORB_EA.mq5  - Expert Advisor para MetaTrader 5
  reports/            - Informes y resultados
================================================================
