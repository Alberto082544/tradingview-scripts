# VectorBT — Beneficios y guía de adopción

> **Propósito**: explicar qué aporta VectorBT a un sistema de trading algorítmico y cómo incorporarlo a tu stack actual, sea cual sea.
> **Fecha**: 2026-05-23

---

## PARTE 1 — BENEFICIOS

## 1. Resumen ejecutivo (1 minuto)

VectorBT es una librería Python **open source (MIT)** para backtesting de estrategias que opera de forma **vectorizada** sobre NumPy + Numba. La diferencia con un backtest tradicional iterativo es brutal:

- **100-400× más rápido** que cualquier engine propio
- **Walk-Forward Analysis nativo** (algo que MT5 Strategy Tester no tiene)
- **Monte Carlo nativo** (sin código adicional)
- **Portfolio multi-bot integrado**
- **Coste: 0 €**. Madurez: 5 años. Comunidad: miles de quants.

Resuelve el cuello de botella típico de cualquier equipo cuant: **validar estrategias rápido y con rigor anti-overfitting**.

---

## 2. ¿Qué problemas resuelve?

### 2.1 El tiempo es el cuello de botella

Cualquier sistema serio de validación necesita:

| Paso | Engine tradicional | VectorBT |
|---|---|---|
| Backtest único (4 años M15) | 30-60 seg | **1-2 seg** |
| Optimización 10.000 combos | 1-2 horas | **30 seg** |
| Optimización 1 millón combos | Inviable | **5-10 min** |
| Walk-Forward 5 ventanas | 6-8 horas (manual) | **2 min nativo** |
| Monte Carlo 2.000 sims | 1 hora | **10 seg** |

→ Validar una nueva estrategia pasa de **10 horas a 30 minutos**.

### 2.2 Capacidades imposibles antes

- **Optimización masiva (>1M combos)**: viable solo con vectorización
- **Walk-Forward con N esquemas simultáneos**: una sola llamada prueba 10 configuraciones distintas de IS/OOS
- **Portfolio simulation**: simula N bots operando juntos, con correlaciones y DD agregado reales
- **Mapas de calor de parámetros** y dashboards interactivos con Plotly

### 2.3 Arbitra divergencias entre validaciones

Caso típico: un bot pasa la validación en Python casero pero falla en MT5 backtest (o al revés). Sin una tercera referencia rápida, no se puede decidir. VectorBT da esa tercera referencia en minutos:

- Si VectorBT confirma Python → el problema está en spreads/comisiones del broker
- Si VectorBT confirma MT5 → la validación Python era overfitting
- En ambos casos, **decisión informada en horas, no semanas**

---

## 3. Comparativa: antes y después de adoptar VectorBT

| Aspecto | Sin VectorBT | Con VectorBT |
|---|---|---|
| Validar nueva estrategia | 10-12 h | **30 min** |
| Explorar 10 variantes | 4-5 días | **5 horas** |
| Walk-Forward riguroso | Manual, 6-8 h | **2 min, automático** |
| Portfolio multi-bot | Aproximado o no hecho | **Exacto** |
| Decisión "bot a producción sí/no" | Lenta, incompleta | **Rápida, basada en N referencias** |
| Mantenimiento del backtester | Engine propio (carga) | **Comunidad lo mantiene** |
| Curva de aprendizaje | Ya invertida en propio | 1-2 semanas (puntual) |

---

## 4. Valor concreto (ROI estimado)

| Concepto | Cálculo | Valor |
|---|---|---|
| Tiempo por validación con engine propio | 10 h | — |
| Tiempo por validación con VectorBT | 30 min | — |
| **Ahorro por validación** | 9,5 h | — |
| Validaciones / mes (ritmo razonable) | 4 | 38 h/mes ahorradas |
| Coste/hora desarrollador (referencia) | 30-50 € | **1.140-1.900 €/mes** |
| **Coste anual VectorBT** | 0 € | — |
| **ROI anual estimado** | ahorro neto | **13.000-22.000 €/año** |

(Sin contar el valor cualitativo de tomar decisiones más rápido y con más datos)

---

## 5. ¿Qué NO resuelve VectorBT?

Es importante saber dónde NO llega, para no esperar lo que no da:

- **NO simula spreads reales del broker** (usa OHLCV limpios). Para validación final con tu broker concreto, sigues necesitando MT5/MT4/cTrader.
- **NO ejecuta en vivo**. Es solo investigación/backtesting.
- **NO genera estrategias**. Tú das la lógica, él la testea rápido.
- **NO sustituye al control humano**: sigues necesitando el checklist anti-overfitting (Walk-Forward ratio, años positivos, MC, etc.). VectorBT lo automatiza, no lo decide.

VectorBT es la **fase de investigación**; tu broker es la **fase de confirmación operativa**. Ambos necesarios; no se sustituyen.

---

## 6. Riesgos identificados y mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|
| Curva de aprendizaje 1-2 semanas | Alta | Bajo (puntual) | Empezar por casos simples; documentación abundante |
| Dependencia de librería externa | Baja | Bajo | 5 años de madurez, MIT, comunidad activa |
| Resultados ligeramente distintos al engine propio | Media | Medio | Cross-check primeros migrados; mantener engine propio como fallback |
| Sin soporte de spreads broker reales | 100% (limitación, no riesgo) | Medio | Combinar con backtest broker para validación final |

**Riesgo neto**: bajo. Mitigaciones simples y reversibles.

---

## 7. Recomendación

**ADOPTAR**, en migración gradual de 4-6 semanas.

Razones:
1. Resuelve cuellos de botella reales (velocidad, WF, MC)
2. ROI cuantificable y positivo
3. Coste cero
4. Riesgo bajo y reversible
5. Habilita capacidades nuevas imposibles con engine propio

---

---

## PARTE 2 — GUÍA DE ADOPCIÓN A TU SISTEMA

> Esta sección es **genérica**. Aplica a cualquier sistema de trading algorítmico en Python, independientemente del broker, librerías o engine que uses.

## 8. Prerequisitos

- **Python 3.10-3.13** (verificar con `python --version`)
- **pip** o **uv** o **conda**
- **4 GB RAM** libres mínimo (más para optimizaciones grandes)
- Tus estrategias deben estar (o poder ponerse) en formato Python que genere **dos arrays booleanos**: entradas (`entries`) y salidas (`exits`)

## 9. Instalación

### Opción A — pip (más simple)

```bash
pip install vectorbt
```

### Opción B — entorno virtual (recomendado para proyectos serios)

```bash
python -m venv venv_vbt
source venv_vbt/bin/activate     # en Linux/Mac
venv_vbt\Scripts\activate         # en Windows
pip install vectorbt
```

### Opción C — uv (moderno, rápido)

```bash
uv add vectorbt
```

### Verificar

```python
import vectorbt as vbt
print(vbt.__version__)   # debe imprimir 0.27.x o superior
```

VectorBT instala automáticamente: NumPy, Pandas, Numba, Plotly, Dill. No suele dar conflictos.

## 10. Concepto central — el "Portfolio"

VectorBT trabaja sobre un objeto **`vbt.Portfolio`** que se construye a partir de:

- **`close`**: serie de precios de cierre (pandas Series con índice DateTime)
- **`entries`** y **`exits`**: dos arrays booleanos del mismo tamaño que `close`, donde `True` = abrir / cerrar
- **`size`**: cantidad por trade (opcional, por defecto todo el capital)
- **`fees`**, **`slippage`**: opcionales
- **`sl_stop`**, **`tp_stop`**: stop loss / take profit (opcional, en % del precio)

A partir de ahí, todo (PnL, DD, Sharpe, equity, Monte Carlo, WF, plots) son métodos del Portfolio.

## 11. Patrón de migración en 4 pasos

Sea cual sea tu sistema actual (engine propio, backtesting.py, zipline, etc.), la migración sigue siempre estos 4 pasos:

### Paso 1 — Cargar datos OHLCV en pandas

```python
import pandas as pd
df = pd.read_csv("mi_simbolo_M15.csv", parse_dates=['time'], index_col='time')
# df debe tener columnas: open, high, low, close, volume
```

### Paso 2 — Generar señales boolean con TU lógica de estrategia

Usar el código que ya tengas. Solo necesitas que la salida sea **2 arrays booleanos** del mismo tamaño que el DataFrame:

```python
# Ejemplo: cruce de medias móviles
ma_fast = df['close'].rolling(5).mean()
ma_slow = df['close'].rolling(34).mean()
entries = (ma_fast > ma_slow) & (ma_fast.shift() <= ma_slow.shift())  # cruce arriba
exits   = (ma_fast < ma_slow) & (ma_fast.shift() >= ma_slow.shift())  # cruce abajo
```

Si tu sistema actual ya genera estos arrays, esto es directo. Si no, refactoriza la función `generate_signals(df) -> (entries, exits)`.

### Paso 3 — Crear el Portfolio

```python
import vectorbt as vbt

pf = vbt.Portfolio.from_signals(
    close=df['close'],
    entries=entries,
    exits=exits,
    init_cash=10000,
    fees=0.00003,        # 0,3 pips típicos (ajusta a tu broker)
    slippage=0.00005,    # 0,5 pips slippage (ajusta)
    freq='15T'           # frecuencia M15 (15 minutos)
)
```

### Paso 4 — Sacar métricas y gráficos

```python
# Métricas estándar (PF, DD, Sharpe, Sortino, Calmar, expectancy, win rate, etc.)
print(pf.stats())

# Equity curve interactiva
pf.plot().show()

# Lista de trades
print(pf.trades.records_readable)
```

Eso es todo para un backtest único. **El sistema ya está migrado.**

## 12. Capacidades extra (lo que justifica adoptar VectorBT)

### 12.1 Optimización masiva

Pasa **listas** de parámetros donde antes pasabas valores únicos. VectorBT calcula automáticamente todas las combinaciones:

```python
import numpy as np

sl_grid = np.arange(0.005, 0.030, 0.005)   # 5 valores de SL
tp_grid = np.arange(0.010, 0.060, 0.010)   # 5 valores de TP

pf_opt = vbt.Portfolio.from_signals(
    close=df['close'],
    entries=entries,
    exits=exits,
    sl_stop=sl_grid,
    tp_stop=tp_grid,
    param_product=True   # producto cartesiano: 5×5 = 25 combos en este caso
)

# Mejor combo por Sharpe
best = pf_opt.sharpe_ratio().idxmax()
print(f"Mejor SL/TP: {best}")
```

Con 10 parámetros optimizados a 10 valores cada uno = 10^10 = 10.000 millones de combos. **No literal** (necesitarías genético), pero hace 1 millón sin esfuerzo en pocos minutos.

### 12.2 Walk-Forward Analysis nativo

```python
# Dividir en 10 ventanas IS/OOS automáticamente
splitter = vbt.RollingSplitter(
    n=10,
    train_len=int(len(df) * 0.7),
    test_len=int(len(df) * 0.3)
)

wf_results = []
for train_idx, test_idx in splitter.split(df.index):
    train_close = df['close'].iloc[train_idx]
    test_close = df['close'].iloc[test_idx]
    # ... optimizar en train, evaluar en test ...
    wf_results.append({'is_pf': ..., 'oos_pf': ..., 'ratio': ...})
```

(La sintaxis exacta varía según versión; ver `docs.vectorbt.dev/tutorials/`)

### 12.3 Monte Carlo bootstrap

```python
returns = pf.returns()
# Bootstrap 2.000 escenarios remuestrando trades con reemplazo
import numpy as np
np.random.seed(42)
mc_returns = np.array([
    returns.sample(frac=1.0, replace=True).cumsum().iloc[-1]
    for _ in range(2000)
])
print(f"P5 (peor caso 95%): {np.percentile(mc_returns, 5):.2%}")
print(f"P50 (mediana):      {np.percentile(mc_returns, 50):.2%}")
print(f"P95 (mejor caso):   {np.percentile(mc_returns, 95):.2%}")
```

### 12.4 Portfolio multi-bot

```python
# Cada columna del DataFrame es un activo distinto
close_multi = pd.DataFrame({
    'AUDNZD': df_audnzd['close'],
    'GBPUSD': df_gbpusd['close'],
    'NAS100': df_nas100['close'],
})

entries_multi = pd.DataFrame({
    'AUDNZD': entries_audnzd,
    'GBPUSD': entries_gbpusd,
    'NAS100': entries_nas100,
})

exits_multi = pd.DataFrame({
    'AUDNZD': exits_audnzd,
    'GBPUSD': exits_gbpusd,
    'NAS100': exits_nas100,
})

pf_portfolio = vbt.Portfolio.from_signals(
    close=close_multi,
    entries=entries_multi,
    exits=exits_multi,
    init_cash=15000,
    cash_sharing=True   # capital compartido entre los 3 bots
)

print(pf_portfolio.stats())   # métricas agregadas del portfolio
```

## 13. Plan de migración recomendado (4-6 semanas)

### Semana 1 — Validación inicial
- Instalar VectorBT en entorno aislado
- Migrar **1 sola estrategia** como prueba (la más sencilla que tengas)
- Comparar resultados vs tu engine actual (deberían coincidir en ±1%)
- Medir el speedup real
- **Decisión**: si confirmaste que va bien, seguir. Si no, ajustar y volver a probar.

### Semanas 2-3 — Migración del resto
- Migrar progresivamente las demás estrategias
- **Mantener el engine propio en paralelo** como fallback durante esta fase
- Para cada migrada, hacer cross-check de 1-2 casos conocidos
- Documentar cualquier diferencia y reconciliarla

### Semana 4 — Capacidades nuevas
- Implementar Walk-Forward nativo en todas las estrategias migradas
- Añadir Monte Carlo a la rutina de validación
- Portfolio simulation multi-bot

### Semanas 5-6 — Industrialización
- Pipeline de validación automática (CI): cada estrategia nueva pasa por backtest + WF + MC sin intervención manual
- Dashboards interactivos con Plotly
- Retirar el engine propio cuando estés cómodo (o mantenerlo solo como referencia)

## 14. Checklist de validación con VectorBT (anti-overfitting)

Sobre los resultados de VectorBT aplicar siempre:

1. **Walk-Forward ratio**: OOS_PF / IS_PF ≥ 0,85 (ideal ≥ 0,95)
2. **Años positivos**: ≥ 10/12 con PF > 1,0
3. **Degradación IS→OOS**: OOS Ann% ≥ 50% del IS Ann%
4. **Drawdown OOS**: no debe ser > 2× el IS DD%
5. **Trades suficientes**: IS ≥ 200 trades, OOS ≥ 100 trades
6. **Peor año**: PF ≥ 0,80 y Ann% ≥ -20%
7. **Estabilidad de parámetros**: top 5 combos deben compartir ≥ 60% de parámetros similares

Si cualquiera falla en grado crítico, la estrategia NO se valida aunque el PF medio sea alto.

## 15. Recursos

- **Docs oficiales**: https://vectorbt.dev/
- **GitHub**: https://github.com/polakowo/vectorbt
- **Tutoriales**: https://vectorbt.dev/tutorials/
- **Discord**: https://discord.gg/vectorbt
- **Ejemplos**: https://github.com/polakowo/vectorbt/tree/master/examples

## 16. FAQ rápido

**¿Reemplaza mi engine actual?**
No de golpe. Convive en paralelo durante semanas. Sustitúyelo cuando estés convencido.

**¿Sirve para cualquier estrategia?**
Sí, mientras puedas expresarla como 2 arrays booleanos (entries/exits). Cubre 95% de estrategias técnicas.

**¿Y las estrategias muy complejas con state machine?**
También, pero pre-calcula el state machine en pandas/numpy antes y pasa solo los booleanos finales a VectorBT.

**¿VectorBT Pro vale la pena?**
La versión gratis cubre todo lo descrito. Pro ($0-2.000 €/año) añade features avanzadas (Kalman filters, ML integration, datos premium). No hace falta para empezar.

**¿Funciona en Linux/Mac/Windows?**
Sí, los tres. Solo Python+pip.

**¿Tiene comunidad activa?**
Sí: Discord con respuestas en horas, GitHub con commits recientes, mantenedor a tiempo completo.

---

**Resumen final**: VectorBT es una de las mejores inversiones de tiempo que puede hacer un equipo cuant individual o pequeño. Coste cero, ROI alto, riesgo bajo, capacidades nuevas. La curva de 1-2 semanas se amortiza en la primera validación que harías a partir de entonces.
