# Sistema de Trading Algorítmico — Alberto (AGM)
**Documento de presentación para terceros — Mayo 2026**

---

## 1. Resumen en una frase

Sistema personal de **trading algorítmico cuantitativo** que combina **Python + MetaTrader 5 + un equipo de agentes de inteligencia artificial** para operar de forma automática en cuentas de **fondeo** (prop firms), con el objetivo de superar evaluaciones y obtener cuentas reales financiadas por terceros.

---

## 2. Idea de negocio

Una **prop firm** es una empresa que te presta capital para operar — si tú generas beneficios sin saltarte sus reglas de gestión de riesgo, te quedas con un porcentaje (típicamente 80–90 %) sin tener que arriesgar capital propio.

**Estado actual del usuario:**
- 2 cuentas en fase de evaluación
  - **FundedNext: $15,000**
  - **The 5%ers: $5,000**
- Reglas comunes: **DD máx 5 % diario / 5 % total**, objetivo Phase 1 = **+5–8 % de beneficio**
- Una vez superadas las 2 fases → cuenta real financiada con profit split

El sistema busca pasar Phase 1 y 2 **sin intervención manual**, dejando a los bots operar sin saltarse reglas.

---

## 3. Arquitectura del sistema

```
                  ┌──────────────────────┐
                  │   CLAUDE (Anthropic) │  Coordinador, escribe código,
                  │   modelo Opus 4.7    │  toma decisiones, gestiona memoria
                  └──────────┬───────────┘
                             │
       ┌─────────────────────┼──────────────────────┐
       ▼                     ▼                      ▼
┌──────────────┐    ┌──────────────────┐   ┌──────────────────┐
│  CrewAI      │    │  Python +        │   │  MetaTrader 5    │
│  3 agentes   │    │  pandas/numpy    │   │  + EAs MQL5      │
│  DeepSeek    │    │                  │   │                  │
└──────┬───────┘    └────────┬─────────┘   └────────┬─────────┘
       │                     │                      │
       ▼                     ▼                      ▼
  Investigación        Backtesting           Ejecución en
  diaria automática    + optimización         vivo en 2 cuentas
  (DuckDuckGo +        de estrategias         de fondeo
   YouTube +
   ficheros locales)
```

### Componentes

**a) Claude Opus 4.7** — el coordinador
- Interpreta lo que pide el usuario
- Escribe scripts en Python y Expert Advisors en MQL5
- Memoria persistente entre sesiones (sabe lo que se hizo días anteriores)
- Gestiona el flujo: research → backtest → validación → producción

**b) CrewAI Trading Researcher** — equipo de IA con DeepSeek
- **Buscador** (DeepSeek Chat): rastrea internet (DuckDuckGo, YouTube)
- **Analista** (DeepSeek Reasoner): valida hallazgos contra el sistema actual
- **Risk Manager** (DeepSeek Chat): calcula position sizing con Kelly fraccional
- **Reporter** (DeepSeek Chat): genera informe final
- Los agentes **leen ficheros locales** del proyecto (REGISTRO_ESTRATEGIAS, reports CSV)
  para comparar hallazgos con las métricas reales y rechazar lo redundante
- Se invoca **bajo demanda** con un tema concreto (no es periódico diario)

**c) Python (motor de backtesting)**
- `strategies/` — estrategias de trading codificadas en pandas/numpy
- `backtest/` — scripts de optimización paramétrica (grids con multiprocessing)
- `data/` — históricos M15 de forex en CSV (12 años, Dukascopy + histdata)
- `reports/` — resultados de cada optimización

**d) MetaTrader 5 + EAs MQL5**
- Cada estrategia validada se traduce a un **Expert Advisor (EA)** en MQL5
- Los EAs se instalan en los terminales de las dos prop firms
- Se ejecutan automáticamente 24/5 leyendo el chart M15 en tiempo real
- Cada EA tiene un MagicNumber único para no pisarse

---

## 4. Estrategias activas

Solo se opera lo que pasa un **checklist de 7 puntos anti-sobreoptimización**:

| Punto | Criterio |
|-------|----------|
| 1 | Walk-Forward ratio (OOS/IS) ≥ 0.85 |
| 2 | ≥ 10/12 años positivos |
| 3 | OOS Ann ≥ 50 % de IS Ann |
| 4 | OOS DD ≤ 2× IS DD |
| 5 | N ≥ 200 (IS) / 100 (OOS) |
| 6 | Peor año Ann ≥ −20 % |
| 7 | Cluster de parámetros estable (sensibilidad) |

### Bots validados y en producción

| EA | Familia | Par | Timeframe | PF OOS | DD OOS | WF | $/mes ($15k) |
|----|---------|-----|-----------|--------|--------|----|--------------:|
| **AGM_Ranger_C_AUDNZD_M15 v3** | Mean Reversion | AUDNZD | M15 | **1.54** | **4.6 %** | 1.273 | ~$226 |
| **AGM_MA_Cross_EURUSD_M15 v2** | Trend Following | EURUSD | M15 | **1.41** | **4.8 %** | 1.128 | ~$244 |

**Suma esperada en $15k**: ~$470/mes (3.1 % mensual)
→ Phase 1 (target +5 %) en ~1.6 meses
→ Phase 1 (target +8 %) en ~2.6 meses

### Bots probados pero descartados

| EA | Motivo descarte |
|----|-----------------|
| GBPJPY (varios) | Mean reversion no funciona — sesgo estructural JPY |
| AUDCAD | Profit demasiado bajo para el riesgo añadido |
| GBPUSD (MA Cross) | DD natural justo en el límite 5 %, sin margen |

---

## 5. Familias de estrategia (las 2 que usamos)

### a) **Ranger C — Mean Reversion** (rango lateral)
- **Hipótesis:** mercado tiende a volver a la media cuando se aleja demasiado
- **Indicadores:**
  - Bollinger Bands (20, 2) en M15 — toque de banda = señal de entrada
  - Stochastic (5,3,3) — confirma giro
  - ADX H4 < 20 — filtro de régimen (solo si NO hay tendencia fuerte)
- **Salida:** Trailing stop ajustado (4 pips), o tiempo (32 barras = 8h)
- **Mejor pareja:** **AUDNZD** (par naturalmente lateral, sin tendencia estructural)

### b) **MA Cross — Trend Following** (tendencia)
- **Hipótesis:** seguir el cruce de medias móviles en dirección del trend
- **Indicadores:**
  - EMA 8 / SMA 34 en M15 — cruce = señal de entrada
  - EMA 8 / SMA 34 en H4 — filtro: solo operar a favor del cruce de H4
  - ATR — define SL y trailing
- **SL:** 2 × ATR; **TP:** 2.5 × SL; **Break-Even:** 0.5 × ATR; **Trailing:** 0.5 × ATR
- **Mejor pareja:** **EURUSD** (líquido, trends limpios)

### Regla maestra del sistema
> **Toda estrategia debe usar 2 temporalidades**:
> H4 (o superior) para filtrar régimen + M15/M30 para el gatillo de entrada.

---

## 6. Flujo de trabajo típico (de idea a producción)

```
1. IDEA / HALLAZGO
   - El usuario plantea algo, o el CrewAI lo descubre investigando
   - Ejemplo: "el filtro ADX<20 triplica Sharpe en mean reversion"

2. BACKTEST RÁPIDO
   - Script Python con los datos M15 del par
   - 1 sola configuración para ver si la idea tiene base
   - ~30 segundos

3. OPTIMIZACIÓN PARAMÉTRICA
   - Grid search con multiprocessing (11 workers)
   - 200-5000 combinaciones según el grid
   - IS 2014-2021, OOS 2022-2025
   - ~3-10 minutos

4. FILTRADO Y VALIDACIÓN
   - Solo combos con OOS PF > 1.0, DD bajo, N suficiente
   - Aplicar checklist 7 puntos anti-overfitting
   - Robustez year-by-year (¿cuántos años positivos?)

5. RISK MANAGER (CrewAI)
   - Calcula LotRiskPct usando Kelly fraccional
   - Considera el DD máximo de la prop firm (5%)
   - Output: % de riesgo por trade en USD reales

6. TRADUCCIÓN A MQL5
   - Reescribir la estrategia validada como Expert Advisor
   - Compilar con MetaEditor (F7)

7. INSTALACIÓN EN MT5
   - Copiar .ex5 a la carpeta MQL5/Experts del terminal
   - Arrastrar al chart correspondiente en M15
   - Activar "Permitir trading algorítmico"

8. MONITORIZACIÓN
   - El EA opera 24/5 sin intervención
   - Si toca DD diario > 3% → pausa preventiva
   - Si toca DD total > 4% → parada (margen al 5% real)
```

---

## 7. Posibilidades / Roadmap

### Inmediato (próximas semanas)
- **Pasar Phase 1 en ambas cuentas** (~1.6 meses esperado)
- **Pasar Phase 2** con mismo sizing (~2 meses adicionales)
- Validar 3ª estrategia complementaria (Stoch+ADX en EURUSD pendiente)

### Medio plazo (1-3 meses)
- **Diversificación a índices** (NAS100, SP500, DAX40, UK100)
  - Pendiente resolver problema de descarga de datos M15 históricos
  - Opciones evaluadas: Dukascopy, TwelveData, Polygon.io, MT5 directo
- **Filtro Hidden Regime (HMM)** para detectar régimen de mercado
- **Migración a aiomql** (librería async MT5) para escalar a múltiples bots concurrentes

### Largo plazo (3-12 meses)
- Pairs trading con cointegración (AUDNZD ↔ AUDCAD, NAS100 ↔ SP500)
- Sistema multi-cuenta con orquestación centralizada
- Investigación CrewAI semanal de hallazgos del sector → filtrado automático

### Capacidades del agente IA (CrewAI) — qué hace cada vez que se lanza
1. Busca en internet (DuckDuckGo + YouTube transcripts) un tema concreto
2. Lee el estado real del sistema (REGISTRO_ESTRATEGIAS, métricas en CSVs)
3. Analiza con un modelo de razonamiento profundo (DeepSeek R1)
4. Calcula sizing recomendado si el hallazgo es implementable (Kelly fraccional)
5. Genera informe markdown estructurado con veredictos (IMPLEMENTAR / INVESTIGAR / DESCARTAR)
6. **Coste por ejecución**: ~$0.10-0.30 (DeepSeek API es barata)

---

## 8. Ejemplo real de mejora reciente (17 mayo 2026)

**Punto de partida:** EA AUDNZD v1 con DD OOS 12.6% → rompe regla DD<5% de las prop firms.

**Proceso:**
1. CrewAI investigó "Stochastic + ADX en mean reversion" → identificó filtro ADX<20
2. Backtest A/B vs baseline → confirmó mejora (PF 1.16→1.26, DD 12.6%→6.6%)
3. Segunda ronda con grid más estricto buscando DD<5% → encontró 147 combos
4. Mejor combo seleccionado: Stochastic_Long_Max=15, TrailDistPips=4
5. **Resultado v3:** PF 1.54, DD 4.6%, WF 1.273 (+329% en WF respecto a v1)
6. EA traducido a MQL5, instalado en los 2 terminales, listo para operar

**Tiempo total:** ~2 horas (Claude + CrewAI + scripts existentes)

---

## 9. Stack técnico resumido

| Capa | Tecnología |
|------|------------|
| Coordinación / código | Claude Opus 4.7 (Anthropic) |
| Investigación IA | CrewAI + DeepSeek API |
| Backtesting | Python 3.13 + pandas + numpy + multiprocessing |
| Datos forex | Dukascopy + histdata.com (12 años M15) |
| Conectividad | MetaTrader5 Python API |
| Ejecución | MQL5 EAs en MT5 (FundedNext + Five Percent terminals) |
| Memoria persistente | Sistema de archivos markdown indexado |
| Control versiones | Git + GitHub (Alberto082544/tradingview-scripts) |

---

## 10. Métricas de honestidad

**Lo que SÍ hace bien el sistema:**
- Backtests rigurosos con IS/OOS y walk-forward
- Anti-sobreoptimización con checklist obligatorio
- Sizing matemático (Kelly fraccional) no improvisado
- Trazabilidad completa: cada decisión queda en memoria + git
- Integración real (no es solo paper trading: opera en MT5 de verdad)

**Lo que NO hace (limitaciones honestas):**
- No tiene execution algorítmica sofisticada (TWAP/VWAP, fills inteligentes)
- No detecta automáticamente cisnes negros (eventos macro extremos)
- Depende del Mac/PC local encendido (sin VPS aún)
- Los backtests asumen datos de Dukascopy/histdata que no son tick a tick

---

*Documento generado el 2026-05-17 — refleja el estado del sistema en ese momento.
La realidad evoluciona rápido; el archivo de referencia más actualizado siempre es
`REGISTRO_ESTRATEGIAS.md` para los bots activos y `INFO_FONDEO.md` para el plan de cuentas.*
