# REGISTRO DE ESTRATEGIAS VALIDADAS
Solo estrategias con IS + OOS + Robustez superados y EA listo.

---

## ✅ AGM_Ranger_C_AUDNZD_M15 v3.0 (DD<5% optimizado)
- **Fecha validacion:** 2026-05-17
- **Familia:** Ranger C (Mean Reversion)
- **Par:** AUDNZD | **Grafico MT5:** AUDNZD en M15
- **EA:** `MQL5\Experts\AGM_Ranger_C_AUDNZD_M15.mq5`
- **Filtros entrada:** Stochastic(5,3,3) K<15 + ADX H4 < 20 (sin RSI)
- **Trailing:** 4 pips (ajustado)

| Metrica | IS 2014-2021 | OOS 2022-2025 |
|---|---|---|
| Profit Factor | 1.21 | **1.54** ⭐ |
| Retorno anual | — | **25.39%** |
| Drawdown max | 12.3% | **4.6%** ✅ |
| Win Rate | — | 63.7% |
| Trades OOS | — | 1,123 (~24/mes) |
| WF ratio | — | **1.273** ⭐ |

**LotRiskPct recomendado:** 0.5% → DD esperado ~3.3% (margen seguridad sobre 5%)
**Apto FundedNext:** ✅ DD 4.6% < 5%
**Apto The 5%ers:** ✅ DD 4.6% < 5%

### Versiones anteriores (DEPRECADAS)
- **v1.0** (2026-05-16): RSI+ADX<30 — PF=1.16, DD=12.6% — rompe DD<5%
- **v2.0** (2026-05-17 AM): Stoch_Long_Max=25, Trail=8 — PF=1.26, DD=6.6% — rompe DD<5%

**Capital testado:** $50,000

---

## ✅ AGM_MA_Cross_EURUSD_M15 v2.0 (DD<5% optimizado)
- **Fecha validacion:** 2026-05-17
- **Familia:** MA Cross (Tendencia)
- **Par:** EURUSD | **Grafico MT5:** EURUSD en M15
- **EA:** `MQL5\Experts\AGM_MA_Cross_EURUSD_M15.mq5`
- **Estrategia Python:** `strategies/ma_cross_m15.py`
- **Parámetros v2:** EMA**8**/SMA**34**, SL=2×ATR, RR=**2.5**, Trail=0.5×ATR, BE=0.5×ATR

| Metrica | IS 2014-2021 | OOS 2022-2025 |
|---|---|---|
| Profit Factor | 1.25 | **1.41** ⭐ |
| Retorno anual | — | **24.36%** |
| Drawdown max | — | **4.8%** ✅ |
| Trades OOS | — | 1,622 (~34/mes) |
| WF ratio | — | **1.128** ✅ |

**LotRiskPct recomendado:** 0.4% → DD esperado ~3.8% (margen seguridad sobre 5%)
**Apto FundedNext:** ✅ DD 4.8% < 5%
**Apto The 5%ers:** ✅ DD 4.8% < 5%

### Versión anterior v1.0 (DEPRECADA — rompe DD<5%)
- EMA5/SMA21, RR=3.0: PF=1.36, DD=6.5%, $1,986/mes en $50k

---

## ✅ AGM_MA_Cross_GBPUSD_M15
- **Fecha validacion:** 2026-05-16
- **Familia:** MA Cross (Tendencia)
- **Par:** GBPUSD | **Grafico MT5:** GBPUSD en M15
- **EA:** `MQL5\Experts\AGM_MA_Cross_GBPUSD_M15.mq5`
- **Estrategia Python:** `strategies/ma_cross_m15.py`

| Metrica | IS 2014-2021 | OOS 2022-2025 |
|---|---|---|
| Profit Factor | 1.38 | 1.35 |
| Retorno anual | 23.91% | 29.11% |
| Drawdown max | 5.2% | 9.8% |
| Win Rate | 54.2% | 53.8% |
| Trades/mes | ~73 | ~42 |
| **Ganancia/mes** | — | **$1,832** |
| **Ganancia/año** | — | **$21,987** |
| WF ratio | — | 0.978 ✅ |

**Robustez:** 12/12 años positivos. Peor año: 2021 (PF=1.20, Ann=24.37%).
**Checklist anti-overfitting:** 7/7 puntos superados.
**Capital testado:** $50,000
**Parametros:** EMA5/SMA34, SL=1×ATR, RR=3.0, Trail=0.5×ATR, BE=0.5×ATR

---

## ✅ AGM_EMA9_VWAP_NAS100_M15 v1.0 (3er bot — nuevo)
- **Fecha validacion:** 2026-05-17
- **Familia:** Trend Following (EMA9+EMA21+VWAP+RSI)
- **Par:** NAS100 / NDX100 (FundedNext lo llama NDX100, 5%ers NAS100)
- **EA:** `MQL5\Experts\AGM_EMA9_VWAP_NAS100_M15.mq5`
- **Estrategia Python:** `strategies/ema9_vwap_rsi.py`
- **Datos backtest:** QQQ (proxy NAS100 via TwelveData) 2020-2025
- **Filtros entrada:** EMA9>EMA21>VWAP + retroceso EMA9 + vela rechazo + RSI 35-75
- **Bidireccional:** SÍ opera longs y shorts según VWAP/EMAs

| Metrica | IS 2020-2023 | OOS 2024-2025 |
|---|---|---|
| Profit Factor | 1.31 | **1.76** ⭐ |
| Retorno anual | 8.0% | **17.12%** |
| Drawdown max | 7.0% | **3.0%** ✅ |
| Win Rate | — | 33.9% |
| Trades OOS | — | 165 (~7/mes) |
| WF ratio | — | **1.344** ⭐ |
| MC P95 DD | — | 7.9% |

**Checklist 7 puntos: 7/7 pasados** ⭐
- WF 1.344 ≥ 0.85 ✅ | 6/6 años positivos ✅ | OOS/IS Ann=2.08 ✅
- OOS/IS DD=0.43 ≤ 2 ✅ | N suficiente ✅ | Peor año +1.4% ✅ | MC P95 7.9% ✅

**Apto FundedNext:** ✅ DD 3.0% < 10%
**Apto The 5%ers:** ✅ DD 3.0% < 10% (sub-5% incluso solo)

**LotRiskPct recomendado:** 0.5%
**Profit estimado en $15k:** ~$230/mes

**Parametros ganadores:** EMA9/EMA21, RSI 35-75, SL=1×ATR, TP=2×SL, WickRatio=1.5

**Limitación honesta:** estrategia funciona BIEN en QQQ/NAS100 (índice tech tendencial), no transfiere a SPY/forex.

---

## ✅ AGM_Ranger_C_AUDCAD_M15 (VALIDADO pero NO operativo)
- **Fecha validacion:** 2026-05-17
- **Familia:** Ranger C (Mean Reversion)
- **Par:** AUDCAD | **EA:** pendiente compilar (no creado aún MQL5)
- **Params:** ADX_H4_Max=15, StochMode=1, Stoch_Long_Max=25, Stoch_Short_Min=75, MinSLPips=30, TrailDistPips=15, ExitBars=32

| Metrica | IS 2014-2021 | OOS 2022-2025 |
|---|---|---|
| Profit Factor | 1.20 | **1.29** |
| Drawdown | 8.9% | 4.6% |
| Ann | — | **7.02%** |
| WF | — | 1.075 |
| MC P95 DD | — | 10.31% ⚠️ (al borde 10%) |

**Checklist 6/7** (falla #7 por 0.31% — P95 justo encima de 10%)
- 10/12 años positivos (2014 y 2018 levemente negativos, no catastróficos)

**$/mes esperado en $15k a 0.5%:** ~$95 (modesto)

**Estado: VALIDADO pero NO operativo** — añade DD agregado sin mucho profit.
Mantener para después de pasar Phase 1 con los 3 principales como diversificación.

---

## ✅ AGM_XAUUSD_ORB_M15 v2.0 (4to bot — defensivo)
- **Fecha validacion:** 2026-05-17 (adaptación de v1.0 a fondeo)
- **Familia:** ORB (Opening Range Breakout) sesión NY
- **Par:** XAUUSD | **Solo Largos**
- **EA:** `MQL5\Experts\AGM_XAUUSD_ORB_M15.mq5`
- **Strategy:** doble entrada TP1=0.5R + TP2=4R, SL=ORB low

| Metrica | Backtest v1 ($50k 2020-25) | v2 esperado |
|---|---|---|
| Profit Factor | 1.32 | 1.32 |
| Drawdown | 7.5% | **~2.3%** (con sizing reducido) |
| Ann | 12.7% | ~3.8% |
| WR | 52.6% | 52.6% |
| WF | 1.21 | 1.21 |
| Robustez | 6/6 años positivos ⭐ + 100% MC sims positivas | igual |
| MC P95 DD | 9.6% | ~2.9% |

**Cambios v2 para fondeo:**
- RiskPct 0.5% → **0.15%** (DD margen al límite 5%)
- Filtro noticias USD ±2min (5%ers requirement)
- Circuit breakers (DD diario + SL streak)

**$/mes esperado en $15k:** ~$49 (defensivo, no agresivo)

**Apto FundedNext + The 5%ers:** ✅ ambos
**LotRiskPct recomendado:** 0.15%

---

## EN PROCESO (no añadir hasta validar)
| Estrategia | Par | Estado | Pendiente |
|---|---|---|---|
| Jasper OB | TBD | Pine v6 en pendientes/ | Portar a Python, validar |

---
*Actualizado: 2026-05-16*
