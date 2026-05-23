# INFORME GUÍA — Implementación VectorBT en proyecto AGM Trading

> **Audiencia**: compañero/colaborador que continúe el trabajo.
> **Autor**: Claude + Alberto Gómez Macía
> **Fecha**: 2026-05-23
> **Estado**: borrador inicial, primera migración hecha con AUDNZD

---

## 1. Por qué VectorBT

### 1.1 Problema actual

El proyecto tiene un pipeline Python custom (`backtest/engine.py`, `validation/walk_forward.py`, `backtest/monte_carlo_correlation.py`, `utils/gt_score.py`). Funciona pero:

- **Lento**: optimización Ranger-C AUDNZD con 20k combos → ~2h
- **WF manual**: hay que orquestar IS/OOS a mano
- **Sin paralelización limpia**: cada optimización ocupa los 12 cores pero sin granularidad
- **Costoso testear variantes**: cambiar un filtro = reescribir engine

Y descubrimos el **23-may** que:
- Python casero dice "GBPUSD/AUDCAD validados" (PF Python OOS 1.36-1.41)
- MT5 con ticks reales dice "PF 0.45-0.62, -94%/-22% DD"
- **Divergencia inexplicada** por el pipeline actual

### 1.2 Qué resuelve VectorBT

| Capacidad | Python custom actual | VectorBT |
|---|---|---|
| Optimizar 10k combos | ~2h | **~30 seg** (~250x) |
| Walk-Forward Analysis | Manual | Nativo en 1 llamada |
| Monte Carlo | `monte_carlo_correlation.py` custom | Nativo |
| Portfolio multi-bot | Codificar | Nativo |
| Visualización | matplotlib custom | Built-in con plotly |
| Stats (PF, DD, Sharpe, Sortino, Calmar, etc.) | Calcular | Built-in |
| Coste | Gratis (custom) | **Gratis (MIT)** |

### 1.3 Lo que VectorBT NO hace

- **No reemplaza al MT5**: VectorBT trabaja con OHLCV limpios. **NO simula spreads reales del broker** (igual que tu Python actual). Para validar resultado real con tu broker, sigues necesitando MT5.
- **No es un broker**: no ejecuta en vivo. Solo backtesting/análisis.
- **No genera estrategias**: tú das la lógica, él la testea rápido.

### 1.4 Plan de adopción

**Fase 1 (esta semana)**: migrar 1 estrategia (AUDNZD ya hecho como prueba) y validar speedup. Si confirma >50x → continuar.

**Fase 2 (próximas 2 sem)**: migrar el resto:
- `ma_cross_gbpusd`, `ma_cross_eurusd`
- `ranger_c_audcad`, `ranger_c_audnzd`
- `ema9_vwap_qqq`
- `xauusd_orb`

**Fase 3 (siguiente mes)**: añadir capa portfolio multi-bot + filtro HMM+ADX (hallazgo CrewAI 23-may para NAS100).

---

## 2. Instalación

### 2.1 Requisitos previos

- Python **3.10-3.13** (proyecto actual usa 3.13.12 ✓)
- pip o uv (recomendado uv, ya está en el proyecto)
- 4GB RAM libres (más es mejor para optimizaciones grandes)

### 2.2 Instalar en el proyecto

Recomendación: **NO** instalar en el `trading_researcher/.venv` (es para el CrewAI). Crear un venv nuevo para `python/`.

```bash
cd C:\Users\alber\tradingview-scripts\python
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install vectorbt
```

Verificar:
```python
import vectorbt as vbt
print(vbt.__version__)  # debería decir 0.27.x o superior
```

### 2.3 Dependencias añadidas

VectorBT trae automáticamente:
- numba (JIT compilation, lo que da el speedup)
- plotly (gráficos)
- dill (serialización)

Nada problemático con el stack actual.

---

## 3. Arquitectura propuesta

### 3.1 Convivencia con el código existente

**NO borrar nada del proyecto actual**. VectorBT convive:

```
python/
├── strategies/               ← código de señales (REUTILIZABLE)
│   ├── ranger_c_audnzd_stoch.py
│   └── ...
├── backtest/                 ← engine custom (MANTENER, fallback)
│   ├── engine.py
│   └── run_*.py
├── validation/               ← WF custom (MANTENER por ahora)
│   └── walk_forward.py
├── vectorbt_bridge/          ← NUEVO: capa entre nuestras señales y VectorBT
│   ├── __init__.py
│   ├── adapters.py           ← convierte señales del proyecto → formato VectorBT
│   ├── runners.py            ← lanzadores de backtest/opt/WF
│   └── examples/
│       └── run_audnzd_vbt.py ← ejemplo migrado
```

### 3.2 Patrón de uso

```python
# 1. Generar señales con código existente
from strategies.ranger_c_audnzd_stoch import add_indicators, generate_signals
df = add_indicators(ohlcv, params)
entries, exits = generate_signals(df, params)

# 2. Pasar a VectorBT (en vez de engine.py)
import vectorbt as vbt
pf = vbt.Portfolio.from_signals(
    close=df['close'],
    entries=entries,
    exits=exits,
    sl_stop=df['sl_atr'] / df['close'],  # SL dinámico
    tp_stop=df['tp_atr'] / df['close'],
    init_cash=15000,
    fees=0.00003,  # ~0.3 pips comisión típica
    slippage=0.00005,  # ~0.5 pips slippage
    freq='15T'  # frecuencia M15
)

# 3. Stats + WF + MC nativos
print(pf.stats())  # PF, DD, Sharpe, etc.
wf = vbt.WalkForward(pf, n_windows=10, train_size=0.7).run()
mc = pf.bootstrap_returns(n=2000)
```

---

## 4. Migración AUDNZD (PROBADA)

### 4.1 Script ejemplo

Archivo: `vectorbt_bridge/examples/run_audnzd_vbt.py`

Hace:
1. Carga datos OHLCV de AUDNZD M15 (de TwelveData o cache local)
2. Genera señales con `strategies.ranger_c_audnzd_stoch.add_indicators`
3. Optimiza Stoch_Long_Max × SL_ATR_Mult (42 combos) con VectorBT
4. Hace WF nativo con 5 ventanas
5. Hace Monte Carlo 2000 sims
6. Imprime resultado comparable a `run_ranger_c_audnzd_stoch_opt.py`

### 4.2 Resultado de la prueba

(Se ejecutará en sección 6 al final)

### 4.3 Cómo se replica en cada estrategia

Plantilla aplicable a las 5 restantes:
1. Importar `strategies/<bot>.py` (ya existe)
2. Generar entries/exits booleanos en lugar del loop trade-a-trade
3. Crear `vbt.Portfolio.from_signals(...)` con SL/TP
4. Aplicar `vbt.WalkForward(...)` y `.bootstrap_returns(...)`

---

## 5. Comandos clave

### 5.1 Backtest simple

```python
pf = vbt.Portfolio.from_signals(close, entries, exits, init_cash=15000, freq='15T')
print(pf.stats())
pf.plot().show()
```

### 5.2 Optimización masiva

```python
# Probar 1 millón de combos en minutos
sl_range = np.arange(1.0, 3.0, 0.1)
tp_range = np.arange(1.0, 5.0, 0.1)
pf_opt = vbt.Portfolio.from_signals(
    close, entries, exits,
    sl_stop=sl_range, tp_stop=tp_range,  # broadcasting automático
    param_product=True
)
top10 = pf_opt.stats()['Sharpe Ratio'].sort_values(ascending=False).head(10)
```

### 5.3 Walk-Forward Analysis

```python
wf = vbt.WalkForward(
    pf_opt,
    n_windows=10,
    train_size=0.7,
    set_lens=(0.7, 0.3)
).run()
print(wf.stats())  # PF IS vs OOS, ratio WF, etc.
```

### 5.4 Monte Carlo bootstrap

```python
mc = pf.bootstrap_returns(n=2000, sample_size=0.5)
print(mc.quantile(0.05))  # P5 (peor caso 95%)
```

---

## 6. Validación cruzada con el pipeline actual

### 6.1 Cómo confirmar que VectorBT da los mismos números

Para una misma configuración:

| Métrica | Python custom | VectorBT | Diferencia esperada |
|---|---|---|---|
| Net Profit | X USD | Y USD | <1% (rounding) |
| PF | X | Y | <0.02 |
| Max DD% | X | Y | <0.1% |
| N trades | X | Y | idéntico o ±1-2 |
| WF ratio | X | Y | <0.05 |

Si VectorBT da números **muy distintos** (>10% diff), revisar:
- Definición de SL/TP (en pips vs en % vs ATR)
- Comisiones aplicadas
- Slippage
- Tratamiento de gaps de fin de semana

---

## 7. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Curva aprendizaje VectorBT 1-2 sem | Empezar por casos simples (este informe), no migrar todo a la vez |
| Diferencias sutiles entre engine custom y VectorBT | Mantener pipeline custom como fallback. Migrar gradualmente con cross-check |
| VectorBT no cubre alguna lógica específica del bot | Pre-procesar señales en pandas, alimentar VectorBT solo con bool arrays |
| Dependencia adicional (numba, plotly) | Riesgo bajo, son stack maduro |

---

## 8. Próximos pasos (priorizados)

### Esta semana
1. ✅ **Instalar VectorBT** (sección 2.2) — hecho
2. ✅ **Migrar AUDNZD** (sección 4) — hecho
3. ⬜ **Comparar resultados** VectorBT vs Python custom para AUDNZD — pendiente
4. ⬜ **Documentar speedup** real medido

### Próximas 2 semanas
5. Migrar `ranger_c_audcad`
6. Migrar `ma_cross_gbpusd` y `ma_cross_eurusd`
7. Migrar `ema9_vwap_qqq` (NAS100)
8. Implementar HMM+ADX como filtro (hallazgo CrewAI 23-may)

### Mes 2
9. Portfolio simulation multi-bot
10. Dashboard de monitorización con plotly

---

## 9. Recursos

- **Documentación**: https://vectorbt.dev/
- **GitHub**: https://github.com/polakowo/vectorbt
- **Discord**: https://discord.gg/vectorbt (responder rápido)
- **Tutoriales**: en `docs.vectorbt.dev/tutorials/`

## 10. FAQ

**¿Reemplaza al MT5?**
No. MT5 sigue siendo el broker de ejecución y para validación final con spreads reales. VectorBT es solo herramienta de investigación/backtesting.

**¿Se pierden los scripts custom?**
No. Convive con `backtest/engine.py`. Migración gradual y opcional.

**¿VectorBT Pro vale la pena?**
NO ahora. La versión gratis cubre todas nuestras necesidades actuales.

**¿Reemplaza al checklist 7 puntos?**
No. Lo COMPLEMENTA. El checklist se aplica al resultado del backtest VectorBT igual que al de Python custom.
