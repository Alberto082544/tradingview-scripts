# Comparativa cruzada 4 bots Phase 1 — Engine custom + fees realistas

**Fecha**: 2026-05-23
**Periodo**: 2018-01-01 → 2024-12-31 (7 años, ~170k barras M15 por símbolo)
**Capital inicial**: 15.000 USD
**Fees aplicados**: 0,3 pips comisión + 0,5 pips slippage = ~0,8 pips coste por trade

---

## Resumen

| Bot | PF | DD% | NetPnL USD | NetReturn % | Trades | WR% | Veredicto |
|---|---|---|---|---|---|---|---|
| AUDNZD Ranger-C Stoch | **1,00** | 39 % | -222 | -1,5 % | 2.671 | 52,5 % | ❌ Break-even, DD alto |
| AUDCAD Ranger-C | **0,96** | 54 % | **-6.188** | -41,3 % | 5.650 | 54,1 % | ❌ **Perdedor fuerte** |
| GBPUSD MA Cross | **1,23** | 18,9 % | **+137.611** | +917 % | 4.680 | 54,5 % | ✅ **Ganador** |
| EURUSD MA Cross | **1,20** | 12,3 % | **+103.715** | +691 % | 4.763 | 53,3 % | ✅ **Ganador** |

---

## Análisis por bot

### 1. AUDNZD Ranger-C Stoch
- Python custom dice break-even (PF 1,00) con DD 39%
- Coincide con MT5 (PF 0,48, DD 57%) en veredicto: **no funciona**
- También VectorBT optimizado 42 combos: **ningún combo positivo**
- **Decisión**: PARAR el lunes ✅

### 2. AUDCAD Ranger-C
- Python custom con datos completos 2018-2024: **-6.188 USD en 5.650 trades** (-41% return)
- DD máximo **54%** → inviable para cuenta de fondeo (límite 10%)
- Contradice la memoria "PF 1,36 OOS 12/12 años" → posible que esa validación fuera con params optimizados específicos, no defaults
- MT5 (PF 0,62, DD 22%) también dice perdedor pero menos catastrófico
- **Decisión**: PARAR el lunes ✅

### 3. GBPUSD MA Cross 🎯
- Python custom: **PF 1,23, NetPnL +137k USD, DD solo 18,9%** en 7 años
- ⚠️ Pero MT5 con ticks reales decía **PF 0,45, -94% DD** — divergencia BRUTAL
- Posibles causas de la divergencia (a investigar):
  - Spreads reales del broker FN >> 0,8 pips asumidos en Python
  - .ex5 tiene lógica adicional no en .mq5 base (parche MaxATR=35, BE, trailing distinto)
  - DEFAULT_PARAMS está overfitted al periodo entero (no hubo WF)
- **Decisión**: NO parar, investigar divergencia. **Candidato a mantener**

### 4. EURUSD MA Cross 🎯
- Python custom: **PF 1,20, NetPnL +103k USD, DD 12,3%** en 7 años
- ⚠️ MT5 decía **PF 0,65, -46% DD** — divergencia significativa
- Mismas causas posibles que GBPUSD
- **Decisión**: NO parar, investigar divergencia. **Candidato a mantener**

---

## Conclusiones cruzadas

### Lo que coincide en TODAS las fuentes (parar)
- **AUDNZD**: 3 sistemas dicen no funciona → PARAR
- **AUDCAD**: Python custom dice -41%, MT5 dice -22% → PARAR

### Lo que diverge (investigar antes de decidir)
- **GBPUSD**: Python +917% vs MT5 -94% → algo no cuadra entre el .py y el .ex5 o los spreads
- **EURUSD**: Python +691% vs MT5 -46% → mismo problema

### Las divergencias pueden venir de:
1. **Spreads del broker FN reales** mucho mayores que 0,8 pips (común en GBPUSD/EURUSD: 1-3 pips con noticias)
2. **El .ex5 (MQL5) tiene lógica adicional** no presente en el .py (BE, trailing ATR, MaxATR filtro, etc.)
3. **DEFAULT_PARAMS del .py podrían estar overfitted** al periodo entero (Python no hizo WF en este test)
4. **Bug del simulador MT5**: poco probable (calidad 100% con ticks reales)

---

## Próximos pasos sugeridos

### Inmediato (lunes)
1. Parar **AUDNZD** y **AUDCAD** en FN+5%ers (sangría confirmada en 2 fuentes)
2. Mantener **GBPUSD** y **EURUSD** mientras se investiga la divergencia
3. Cargar **NDX100** (es el bot con mejor calidad Python según GT-Score)

### Esta semana
4. Walk-Forward real en VectorBT para GBPUSD y EURUSD (validar que el +917% / +691% no es overfit)
5. Comparar línea a línea `strategies/ma_cross_m15.py` vs `AGM_MA_Cross_GBPUSD_M15.mq5` para encontrar la lógica que diverge
6. Backtest MT5 con spreads forzados a 1,5 y 2,0 pips fijos (ver dónde el .ex5 empieza a perder)

---

## Archivos generados

- `vectorbt_bridge/examples/run_multi_bot_vbt.py` — script comparativa
- `vectorbt_bridge/output/multi_bot_comparison.csv` — datos
- `vectorbt_bridge/output/COMPARATIVA_4_BOTS.md` — este documento

---

*Análisis automático generado 2026-05-23 como parte de la migración a VectorBT.*
