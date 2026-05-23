# Cómo backtestear bien en MetaTrader 5 — Buenas prácticas

> **Investigación**: 2026-05-23
> **Fuentes**: MQL5 docs, Alphaheim, AlfaTactix, eareview.net, ForTraders, MQL5 Blog
> **Propósito**: protocolo correcto para validar EAs en MT5 sin caer en falsos positivos

---

## 1. Los 5 errores más comunes (y cómo evitarlos)

| Error | Consecuencia | Solución |
|---|---|---|
| **Ignorar trading costs** (spread, comisión, swap) | Backtest +20% más optimista que la realidad | Configurar spread variable + comisión real del broker |
| **Spread por defecto ~0** | Resultado "demasiado bueno" en scalping/intradía | Usar "Current spread" o spread del momento |
| **Datos de baja calidad** (interpolados desde M1) | Resultados aleatorios, sobre todo con SL/TP cercanos | Importar tick data real (Tickstory/TDS) o usar broker con buen histórico |
| **Optimizar sin validación forward** | Curve-fitting: gana en backtest, pierde en real | Walk-Forward o split IS/OOS manual |
| **Confiar en "99% modelado"** | El label no garantiza realismo | Comprobar tick data REAL del broker |

---

## 2. Calidad de datos (el FUNDAMENTO)

### 2.1 Jerarquía de calidad

1. **Tick data real importado** (Tick Data Suite, Tickstory) → máxima precisión, recomendado para producción
2. **Tick data del propio broker** → buena si el broker tiene historial completo
3. **"Every tick" generado desde M1** → aceptable para EAs no-scalping
4. **"OHLC M1"** → solo para validación rápida, no producción
5. **"Only open prices"** → solo para EAs que abren/cierran en apertura de vela

### 2.2 Cómo descargar histórico M1 del broker en MT5

1. `Herramientas → Opciones → Gráficos` → "Máx. barras" = `999999999`
2. Reiniciar MT5
3. `Vista → Símbolos` → seleccionar símbolo → pestaña **"Barras"**
4. Periodo: M1, rango: el que necesites, **Solicitar**
5. Esperar a que se descargue (puede tardar minutos)
6. Repetir para cada símbolo a testear

### 2.3 Atajo: importar tick data externo

- Crear símbolo personalizado: `Symbols → Create Custom Symbol`
- Importar archivos M1 y tick separados
- Activar el símbolo en Market Watch
- Backtest sobre el símbolo `_TDS` o como lo nombres

---

## 3. Configuración correcta del Strategy Tester

### 3.1 Pestaña Configuración

| Campo | Valor recomendado | Por qué |
|---|---|---|
| **Modelado** | `Cada tick a base de ticks reales` (si hay ticks importados) o `Todos los ticks` (si no) | Mayor realismo |
| **Retrasos** | `Sin retrasos, ejecución ideal` para primer test | Después emular slippage realista |
| **Optimización** | `Deshabilitado` para validar, `Rápida (genético)` para optimizar | Genético explora ~5-10% del espacio |
| **Criterio óptimo** | `Máximo factor de recuperación` (Net Profit / Max DD) | Premia rentabilidad ajustada al riesgo |
| **Depósito inicial** | El de la cuenta REAL ($15.000 si es FN) | Para que el sizing sea coherente |
| **Apalancamiento** | El del broker | Para márgenes reales |

### 3.2 Spread (CRÍTICO)

MT5 por defecto usa **spread actual** del broker en el momento del test. Eso es **MALO**:
- Con mercados cerrados (fin de semana) el spread está inflado 5-10×
- Resultado: el backtest pierde por culpa del spread anormal
- Solución: en el dropdown "Spread", elegir **"Current spread"** O introducir un spread fijo realista (1-2 pips para majors, 5-10 para crosses, 30+ para índices)

### 3.3 Comisión

Si el broker cobra comisión (típico en cuentas ECN/Raw), hay que añadirla en la **especificación del símbolo**:
- `Vista → Símbolos → símbolo → pestaña Especificación`
- Ver campo `Commission` → debería tener el valor real del broker
- Si pone 0 y tu broker SÍ cobra, el backtest infla resultados

---

## 4. Walk-Forward — la única defensa contra el overfit

### 4.1 Por qué es OBLIGATORIO

Optimización pura sin WF = **curve fitting garantizado**. El bot funcionará perfecto en backtest y fallará en real.

### 4.2 Cómo activarlo en MT5

En pestaña **Configuración** del tester:
- **Periodo Forward** = `1/2` (50% IS, 50% OOS) o `1/3` (66% IS, 33% OOS)
- MT5 optimiza en IS, valida en OOS automáticamente
- Pestaña **"Optimización Forward"** muestra resultados

### 4.3 Alternativa manual (más control)

1. Optimizar en `2018.01.01 → 2022.12.31` (5 años IS)
2. Anotar TOP 5 combos
3. Validar cada uno en `2023.01.01 → 2024.12.31` (2 años OOS)
4. Si el TOP 1 en OOS sigue siendo PF > 1.2 → VÁLIDO
5. Si el TOP 1 IS pierde en OOS → OVERFIT, descartar

---

## 5. Optimización — qué params y cómo

### 5.1 Reglas de oro

- **Máx 4-5 params optimizados simultáneamente** (más = combinatoria explota + overfit alto)
- **Rangos razonables** (no probar SL desde 0.1 a 100, sino 0.8 a 3.0)
- **Pasos pequeños** (Paso=0.2 mejor que Paso=1 para floats)
- **Genético rápido** si los combos totales > 1000, exhaustivo si <500

### 5.2 Orden de optimización

Si optimizas uno a uno (más interpretable):
1. **SL_ATR_Mult** primero (más impactante)
2. **RR** después (depende del SL)
3. **EMA_Fast / SMA_Slow** (afecta señales de entrada)
4. **Filtros adicionales** (ADX, RSI, sesión)

Si optimizas en bloque:
1. Solo los 4 principales arriba
2. Genético rápido + criterio "Factor de recuperación"

### 5.3 Estabilidad de parámetros (el "green blob")

Después de optimizar, mira el **mapa 3D** de resultados (`Resultados de Optimización` → vista gráfica).
- Si los buenos combos están **agrupados** en una región → ROBUSTO
- Si el mejor combo está **aislado** rodeado de pésimos → FLUKE / OVERFIT

---

## 6. Checklist de validación post-optimización

Antes de poner un bot en producción real, debe pasar **TODOS** estos:

| # | Métrica | Umbral | Por qué |
|---|---|---|---|
| 1 | **WF ratio (OOS PF / IS PF)** | ≥ 0.85 | Detecta overfit obvio |
| 2 | **Años positivos** | ≥ 10/12 con PF > 1 | Robustez en distintos regímenes |
| 3 | **OOS Net Profit %** | > 0 | El bot gana en datos no vistos |
| 4 | **DD OOS** | ≤ 2× DD IS | El DD no se dispara fuera del IS |
| 5 | **N trades IS** | ≥ 200 | Estadística suficiente |
| 6 | **N trades OOS** | ≥ 100 | Validación con muestra grande |
| 7 | **Peor año** | PF ≥ 0.80, return ≥ -20% | Sin años catastróficos |
| 8 | **DD máximo** | ≤ 15% (cuenta fondeo 10% buffer) | Compatible con prop firm |

---

## 7. Forward test (después del backtest)

Una vez pase el checklist, **NO ir directo a real**:

1. **Demo durante 2-4 semanas** con sizing real
2. Comparar trades demo vs trades del backtest del mismo periodo
3. Si demo da PF similar → producción
4. Si demo diverge mucho del backtest → algo está mal (broker, ejecución, slippage)

---

## 8. Errores específicos que cometimos hoy (lecciones)

### 8.1 Confiar en optimización Python sin spread real

- Python sin spread dijo "GBPUSD con SL=0.5 da PF 1.45"
- MT5 con spread real dijo "PF 0.52, -99% DD"
- **Lección**: SL pequeños (<1×ATR) son MUY sensibles al spread. Python sin modelar spread sobreestima brutalmente

### 8.2 No verificar caché de inputs del Strategy Tester

- Recompilar el .ex5 NO actualiza los inputs cacheados en `MQL5/Profiles/Tester/<EA>.set`
- **Lección**: después de recompilar, en el tester ir a `Parámetros de entrada` → click derecho → "Cargar predeterminados" (o editar manualmente)

### 8.3 Asumir que "calidad 100%" garantiza realismo

- Calidad 100% con ticks generados ≠ calidad 100% con ticks reales del broker
- **Lección**: para EAs sensibles al precio (SL/TP cercanos), usar `Cada tick a base de ticks reales`

---

## 9. Plan de validación correcto (orden estricto)

Para validar un EA nuevo, este es el flujo correcto:

1. **Descargar histórico M1** del broker (Vista → Símbolos → Barras → Solicitar) hasta 99% calidad
2. **Backtest único** con defaults del EA, periodo COMPLETO, modelado real ticks
3. Si PF > 0.8 → continuar. Si PF < 0.5 → posiblemente bot defectuoso, no perder más tiempo
4. **Optimización 1 param a la vez** sobre IS (70% de los datos)
5. Anotar los 3 mejores valores de cada param
6. **Backtest manual** con combinación de mejores en OOS (30% restante)
7. **Aplicar checklist 8 puntos** de la sección 6
8. **Demo 2-4 semanas** con sizing real
9. **Producción con sizing reducido** primero (0.25× lo normal)
10. **Monitorización semanal** comparando real vs backtest

---

## 10. Resumen ejecutivo (5 reglas)

1. **Datos**: usa ticks reales del broker o importados, no interpolación M1
2. **Spread**: configura realista (no actual con mercados cerrados)
3. **Walk-Forward obligatorio**: nunca optimices sin separar IS/OOS
4. **Pocos params**: máximo 4-5 a la vez. Más → overfit garantizado
5. **Checklist 8 puntos**: si no pasa todos, NO va a producción

---

*Documento de referencia para validación de EAs en MetaTrader 5. Aplicar SIEMPRE antes de pasar cualquier bot a cuentas reales.*
