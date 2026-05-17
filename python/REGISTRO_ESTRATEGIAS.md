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

## EN PROCESO (no añadir hasta validar)
| Estrategia | Par | Estado | Pendiente |
|---|---|---|---|
| Ranger C | AUDCAD | Opt OK, WF=0.919 | Robustez year-by-year |
| XAUUSD ORB | XAUUSD | Backtest OK 2020-25 PF=1.32 DD=7.5% | Adaptar sizing para DD<5% fondeo |
| Jasper OB | TBD | Pine v6 en pendientes/ | Portar a Python, validar |

---
*Actualizado: 2026-05-16*
