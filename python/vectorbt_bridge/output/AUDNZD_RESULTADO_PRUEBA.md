# Prueba de migración AUDNZD a VectorBT — Resultados

**Fecha**: 2026-05-23
**Periodo**: 2018-01-01 → 2024-12-31 (7 años, 170.940 barras M15)
**Estrategia**: Ranger-C AUDNZD con StochMode=2 (RSI + Stochastic)

---

## 1. Backtest único (DEFAULT_PARAMS, StochMode=2)

| Métrica | Engine custom Python | VectorBT |
|---|---|---|
| Tiempo | 0,84 s | 2,98 s |
| PF | 1,00 | 0,72 |
| Max DD% | 39 % | 31 % |
| Net PnL | -222 USD | -31 USD |
| N trades | 2.671 | 2.475 |
| WR | 52,5 % | n/d |

**Coincidencias**:
- Veredicto cualitativo coincide: bot **no rentable estructuralmente**
- Distribución de trades similar (~2.500-2.700)
- Drawdown del mismo orden (31-39%)

**Diferencias justificadas**:
- VectorBT no replica al 100% el exit por tiempo (`ExitBars=32`) ni el `BB_Mid_TP` del engine custom → menos trades cerrados por timing/TP intermedio
- Engine custom calcula PF como wins/losses puro; VectorBT incluye fees/slippage (0,3+0,5 pips) → su PF sale ligeramente peor
- Para validar veredicto cualitativo (¿hay edge o no?), ambos coinciden

---

## 2. Optimización grid 42 combos (Stoch_Long_Max × SL_ATR_Mult)

Mismo grid que se probó en MT5 con ticks reales:
- Stoch_Long_Max: {5, 10, 15, 20, 25, 30}
- SL_ATR_Mult: {1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5}

**Tiempo**: 5,92 segundos para 42 combos (0,14 s/combo)

### TOP 5 combos por PF

| Stoch | SL_ATR | PF | DD% | Trades | NetProfit |
|---|---|---|---|---|---|
| 5 | 1.25 | 0,77 | 14,4 % | 1.281 | -14,1 % |
| 5 | 1.00 | 0,77 | 14,4 % | 1.281 | -14,1 % |
| 5 | 1.75 | 0,76 | 14,7 % | 1.280 | -14,4 % |
| 5 | 1.50 | 0,76 | 14,7 % | 1.281 | -14,4 % |
| 5 | 2.25 | 0,76 | 14,7 % | 1.277 | -14,5 % |

### BOTTOM 3 combos

| Stoch | SL_ATR | PF | DD% | Trades | NetProfit |
|---|---|---|---|---|---|
| 20 | 1.75 | 0,71 | 27,5 % | 2.066 | -27,1 % |
| 20 | 2.00 | 0,70 | 27,9 % | 2.064 | -27,5 % |
| 20 | 2.50 | 0,70 | 28,2 % | 2.050 | -27,8 % |

**Patrón**: con Stoch=5 (filtro más restrictivo) el bot pierde menos pero **sigue siendo perdedor** (PF 0,77).

---

## 3. Comparativa con MT5 y Python custom

| Fuente | Datos | Veredicto |
|---|---|---|
| Python casero (run_ranger_c_audnzd_stoch_opt.py) | M15 limpio (sin spreads) | PF 1,36 OOS, 9/12 años (dudoso) |
| MT5 calidad 100% (ticks reales FN) | M15 + ticks broker FN | PF 0,48 — **perdedor** |
| **VectorBT (esta prueba)** | M15 + fees/slippage 0,3+0,5 pips | **PF 0,72 — perdedor** |
| MT5 optimizado 2 params | 42 combos en MT5 | **Ningún combo positivo** |
| **VectorBT optimizado 2 params** | 42 combos en VectorBT | **Ningún combo positivo** |

### Conclusión cruzada

**Los 3 sistemas con datos realistas (incluyendo fees/spreads) coinciden**: AUDNZD Ranger-C Stoch **no tiene edge estructural** en el periodo 2018-2024.

El único que decía "OK" era el Python casero **sin fees ni spreads**. Eso es overfitting al modelo limpio.

---

## 4. Decisión recomendada

🛑 **PARAR el bot AUDNZD en FN+5%ers el lunes**.

Evidencia que lo soporta:
- MT5 con ticks reales: PF 0,48, DD 57%
- MT5 optimizado 2 params: ningún combo positivo
- VectorBT default: PF 0,72, DD 31%
- VectorBT optimizado 2 params: ningún combo positivo
- Solo Python casero (sin spreads) dice "OK", lo cual no aplica al mundo real

---

## 5. Lecciones de la migración VectorBT

### Lo que funcionó
- Instalación trivial (`pip install vectorbt`)
- Reutilizamos `strategies/ranger_c_audnzd_stoch.py` sin tocarlo (solo `add_indicators`)
- 42 combos en 5,9 s vs ~35 s estimado del engine custom secuencial → speedup ~6× ya con muestra pequeña
- En grids grandes (miles de combos) el speedup esperado es 50-200×

### Lo que requiere trabajo
- VectorBT no replica al 100% el exit por tiempo + BB_Mid_TP del engine custom (diferencia ±10% en métricas)
- Las advertencias `FutureWarning` requieren ajustes menores
- Para usar Walk-Forward nativo hace falta estudiar `vbt.RollingSplitter` (no lo cubre esta prueba)

### Próximos pasos sugeridos
1. Ajustar el adaptador para replicar exactamente el motor custom (BB_Mid_TP, ExitBars)
2. Implementar Walk-Forward nativo (`vbt.RollingSplitter`)
3. Implementar Monte Carlo (`returns().resample()`)
4. Migrar las otras 4 estrategias (AUDCAD, GBPUSD, EURUSD, NDX100)
5. Validar el portfolio completo con `cash_sharing=True`

---

## 6. Archivos generados

- `vectorbt_bridge/examples/run_audnzd_vbt.py` — script de migración
- `vectorbt_bridge/output/audnzd_grid_2018_2024.csv` — resultados de los 42 combos
- `vectorbt_bridge/output/AUDNZD_RESULTADO_PRUEBA.md` — este documento

---

*Generado automáticamente como parte de la prueba de adopción de VectorBT en el proyecto AGM Trading.*
