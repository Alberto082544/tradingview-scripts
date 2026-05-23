# EA SMC Tendencia FVG v9.4 — Análisis técnico completo

> **Fecha**: 2026-05-23
> **Código**: 856 líneas, MQL5
> **Estado**: pendiente validación con backtest

---

## 1. Resumen ejecutivo

EA multi-símbolo de **Smart Money Concepts (SMC)** que opera Fair Value Gaps (FVG) en dirección de tendencia macro H4. Diseñado por el creador para 9 pares forex preconfigurados con TF de FVG ajustable por par (H1/M30/M15).

Tres niveles temporales:
1. **H4**: tendencia macro (swings + EMA200)
2. **TF FVG** (H1/M30/M15 por símbolo): detección de Fair Value Gaps + impulso
3. **M15**: confirmación de entrada en pullback con patrones de vela

Gestión profesional: 2 tickets por trade (TP1 a 1:2, TP2 a 1:3), BE+buffer cuando TP1 hit.

---

## 2. Lógica completa paso a paso

### 2.1 Detección de tendencia (H4)
- Lookback: 30 velas H4 (~5 días)
- Detecta swing highs/lows (mayor/menor que vecinos)
- Cuenta swings alcistas vs bajistas
- Compara cierre H4 con EMA200 H4
- **TREND_BULL** si: ≥3 swings alcistas Y closeH4 > EMA200
- **TREND_BEAR** si: ≥3 swings bajistas Y closeH4 < EMA200
- **TREND_NONE** si ninguno → no opera

### 2.2 Detección de FVG (en TF configurable)
- Lookback: 50 velas del TF FVG
- **Bull FVG**: low de vela `i-1` > high de vela `i+1` (gap alcista entre 3 velas)
- **Bear FVG**: high de vela `i-1` < low de vela `i+1` (gap bajista)
- **Impulso mínimo**: body de la vela media ≥ 8 pips
- **Solo en dirección de tendencia macro** (no opera contra-tendencia)
- Hasta 50 FVGs simultáneos por símbolo en memoria

### 2.3 State machine de FVG
```
ACTIVE → TOUCHED → FILLED
              ↓
         INVALIDATED (si rompe sz×0.5 más allá)
         EXPIRED (si pasan MaxFVG_Age = 72h)
```
- **ACTIVE**: FVG recién detectado, esperando pullback
- **TOUCHED**: precio M15 entra en la zona del FVG
- **FILLED**: precio M15 cruza al lado opuesto (pullback completo)
- Solo entradas tras estado **FILLED**

### 2.4 Confirmación de entrada (M15)
**Pre-condiciones**:
- FVG state = FILLED
- Tiempo desde fill ≤ MaxM15Confirm (12 velas M15 = 3h)
- RSI H1 dentro de rango (28-72 default)
- Precio respeta EMA50 H1 (si filtro activo)

**3 patrones de confirmación (OR)**:
- **Patrón A**: vela anterior (barra 2) es Doji o Pinbar de rechazo + vela actual (barra 1) es envolvente direccional
- **Patrón B**: vela actual es Pinbar fuerte (mecha ≥60% del rango, cuerpo ≤35%)
- **Patrón C (FALLBACK)**: vela actual direccional con cuerpo ≥25% del rango ← MUY LAXO

**Validación final**:
- Cierre de barra 1 respeta la FVG (no la rompe)

### 2.5 Gestión de posición
- **SL** = pullbackExtreme ± ATR_H1 × SL_ATR_Mult
- **Bloqueo**: si distancia SL > MaxSLPips (80) → no opera
- **TP1** = entrada ± SL_dist × TP1_RR (2.0 default)
- **TP2** = entrada ± SL_dist × TP2_RR (3.0 default)
- **Lote total** calculado por riesgo % cuenta
- **Dividido en 2 tickets** iguales

**Cuando TP1 hit**:
- SL ticket 2 → BE + BE_BufferPips (2 pips por encima/debajo)
- Ticket 2 ya protegido, deja correr hasta TP2

---

## 3. Parámetros configurables (importantes)

### Riesgo
- `RiskPercent` = 1.0 → 1% del balance por operación
- `TP1_RR` = 2.0 (ratio TP1)
- `TP2_RR` = 3.0 (ratio TP2)
- `BE_BufferPips` = 2.0 (buffer BE)
- `SL_ATR_Mult` = 1.5 (multiplicador SL sobre ATR H1) ← **CRÍTICO**
- `MaxSLPips` = 80 (SL máximo bloqueado)

### Símbolos y TF
- `Symbols` = lista CSV (default: 9 majors + crosses)
- `FVG_TFs` = lista CSV de TF de FVG por símbolo

### Detección
- `SwingLookback` = 30 (velas H4 para swings)
- `TrendBars` = 3 (mínimo swings)
- `FVG_Lookback_H1` = 50 (velas a buscar FVGs)
- `ImpulseMinPips` = 8.0 (impulso mínimo)
- `MaxFVG_Age` = 72 (horas vida máxima FVG)
- `MaxM15Confirm` = 12 (velas M15 ventana confirmación)

### Patrones
- `DojiMaxBody` = 0.20 (cuerpo máx Doji)
- `PinbarMinWick` = 0.60 (mecha mínima Pinbar)
- `PinbarMaxBody` = 0.35
- `EngulfMinRatio` = 1.10

### Filtros
- `UseRSIFilter`, `RSI_OB=72`, `RSI_OS=28`
- `UseEMAFilter` (EMA50 H1)
- `UseSessionFilter` (7-21 GMT)
- `UseSpreadFilter` (max 3.5 pips)

---

## 4. Análisis crítico — fortalezas y debilidades

### ✅ Fortalezas
1. **Estructura multi-TF coherente**: macro (H4) → señal (H1) → entrada (M15)
2. **Risk management profesional**: 2 tickets, BE+buffer, sizing por riesgo %
3. **Filtros robustos**: RSI, EMA, sesión, spread
4. **Multi-símbolo en 1 EA**: ahorra esfuerzo operacional
5. **TF FVG configurable por par**: adaptable a volatilidad
6. **No opera contra-tendencia macro**: evita el peor escenario
7. **Patrones de vela bien definidos**: Doji, Pinbar, Engulfing tienen base estadística (Bulkowski)
8. **Validación FVG con state machine**: requiere TOCAR y RELLENAR antes de entrar → filtra fakeouts

### ⚠️ Debilidades / riesgos
1. **Patrón C demasiado laxo** ("vela direccional con cuerpo 25%") → puede generar muchas falsas señales
2. **Magic único 202509** compartido entre símbolos → conflictos si otros EAs usan magic cercano
3. **MaxSLPips=80 fijo**: en pares volátiles (GBPJPY ATR H1 ~27 pips → SL típico 40+ pips) puede bloquear muchas entradas válidas
4. **MaxFVG_Age=72h**: FVGs de 3 días pueden ser irrelevantes si el régimen cambió
5. **Sin Walk-Forward documentado**: nunca probado contra overfit
6. **Sin estadísticas históricas conocidas**: el autor no documenta PF, DD, WF de ningún periodo
7. **Cabecera "SMC EA - Claude"**: generado por IA, lógica no validada por trader humano experto
8. **Multi-símbolo + multi-TF dificulta backtest**: MT5 Strategy Tester opera 1 símbolo por sesión
9. **SMC/FVG es metodología controvertida**: academia discute si tiene edge real o es sesgo de confirmación

---

## 5. Plan de validación recomendado (cuando MT5 esté operativo)

### Fase 1 — Validación inicial (1 día)
1. Backtest MT5 **EURUSD** (par más líquido) con defaults del autor:
   - `Symbols` = "EURUSD"
   - `FVG_TFs` = "H1"
   - `SL_ATR_Mult` = 1.5
   - Periodo: 2018-2024
   - Modelado: Todos los ticks
2. Criterios de aceptación inicial:
   - PF ≥ 1.0
   - DD ≤ 20%
   - Trades ≥ 200 (estadística mínima)
3. Si **PF > 1.0** → pasar a Fase 2
4. Si **PF < 0.8** → descartar (no rentable ni base)

### Fase 2 — Walk-Forward (2-3 días)
Si Fase 1 OK:
1. Optimizar `SL_ATR_Mult` en IS 2018-2022 (5 valores: 0.8, 1.0, 1.2, 1.5, 2.0)
2. Validar en OOS 2023-2024
3. WF ratio ≥ 0.85 → válido
4. Aplicar checklist 7 puntos completo

### Fase 3 — Otros pares (1 semana)
1. Replicar Fase 1+2 en: GBPUSD, USDJPY, EURGBP, AUDUSD
2. Mantener config inicial (H1, SL=1.5) para ser justos
3. Identificar qué pares pasan el checklist

### Fase 4 — Demo 4 semanas
- Solo los pares que pasaron Fases 1-3
- Sizing real
- Comparar trades demo vs backtest del mismo periodo
- Si demo coincide → producción con sizing reducido (0.25× normal)

---

## 6. Configuración inicial recomendada para PRIMER backtest

```
=== GESTIÓN DE RIESGO ===
RiskPercent       = 1.0
TP1_RR            = 2.0
TP2_RR            = 3.0
BE_BufferPips     = 2.0
SL_ATR_Mult       = 1.5 (default conservador)
MaxSLPips         = 80.0

=== SÍMBOLOS ===
Symbols           = "EURUSD"  (solo uno para primer test)
FVG_TFs           = "H1"

=== DETECCIÓN ===
SwingLookback     = 30
TrendBars         = 3
FVG_Lookback_H1   = 50
ImpulseMinPips    = 8.0
MaxFVG_Age        = 72

=== CONFIRMACIÓN ===
MaxM15Confirm     = 12
MinBodyRatio      = 0.25
DojiMaxBody       = 0.20
PinbarMinWick     = 0.60
PinbarMaxBody     = 0.35
EngulfMinRatio    = 1.10

=== FILTROS ===
UseRSIFilter      = true
RSI_OB            = 72.0
RSI_OS            = 28.0
UseEMAFilter      = true
UseSessionFilter  = true
SessionStart      = 7
SessionEnd        = 21
UseSpreadFilter   = true
MaxSpreadPips     = 3.5

=== STRATEGY TESTER ===
Periodo           = M15
Intervalo         = 2018.01.01 → 2024.12.31
Modelado          = Todos los ticks
Depósito          = 15000
Apalancamiento    = 1:100
Optimización      = Deshabilitado (primer test)
Magic recomendado = 999509 (cambiar para no conflictar con otros)
```

---

## 7. Si vamos a portarlo a Python (sin MT5)

Esfuerzo estimado: **4-6 horas** de codificación.

Pasos:
1. Cargar OHLCV M15, H1, H4 del par
2. Función `detect_trend_h4()` → swings + EMA200
3. Función `detect_fvg(tf)` → escanea 3 velas adyacentes
4. Función `update_fvg_states()` → state machine
5. Función `check_entry()` → confirmación M15 + patrones
6. Función `manage_trades()` → 2 tickets con BE
7. Loop iterativo (NO vectorizable fácil por la state machine)
8. Métricas: PF, DD, WR, etc.

**No es prioritario**: si MT5 estará disponible entre semana, el backtest nativo es más fiable.

---

## 8. Conclusión

EA bien estructurado teóricamente pero **sin validación previa documentada**. Antes de cualquier uso real:
1. Backtest MT5 calidad 100% EURUSD 2018-2024 con defaults
2. Si PF > 1.0 → seguir validando
3. Si PF < 0.8 → descartar (probable que SMC/FVG no tenga edge en este broker)

**No esperar resultados milagrosos**: SMC/FVG es controvertido y puede ser solo sesgo de confirmación post-hoc. La única forma de saber: probarlo bien.

---

## 9. Referencias técnicas

- Código: `MQL5/Experts/Ea smc tendencia fvg.mq5` (terminal D0E8209F...)
- Línea inputs principales: 25-75
- Lógica entrada BUY: línea 548-651
- Lógica entrada SELL: línea 655-746
- Helpers (CalcLots, etc.): línea 753-820

---

*Documento de análisis técnico. Plan de validación supeditado a disponibilidad de MT5 en horario operativo (lunes a viernes).*
