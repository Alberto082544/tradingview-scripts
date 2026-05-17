# PLAN DE TRADING — CUENTAS DE FONDEO (DEFINITIVO)
**Actualizado: 2026-05-17**

## Reglas confirmadas (ambas cuentas)
- **DD diario máx: 5%**
- **DD total máx: 5%** ← ESTRICTO

## Setup

| Cuenta | Capital | Prop firm | Terminal |
|--------|---------|-----------|----------|
| A | $15,000 | FundedNext | `FundedNext MT5 Terminal` |
| B | $5,000 | The 5%ers | `Five Percent Online MetaTrader 5` |

---

## 🟢 Bots viables (los 2 con DD<5% optimizado)

### 1. AGM_Ranger_C_AUDNZD_M15 v3.0
- Stochastic(5,3,3) K<15 + ADX H4 < 20 + Trail 4 pips
- **OOS: PF=1.54 | DD=4.6% | Ann=25.4% | WF=1.273**
- LotRiskPct recomendado: **0.5%**
- DD esperado real: **~3.3%** (margen 1.7% al límite)

### 2. AGM_MA_Cross_EURUSD_M15 v2.0
- EMA8/SMA34, SL=2×ATR, RR=2.5
- **OOS: PF=1.41 | DD=4.8% | Ann=24.4% | WF=1.128**
- LotRiskPct recomendado: **0.4%**
- DD esperado real: **~3.8%** (margen 1.2% al límite)

### ❌ GBPUSD — DESCARTADO (DD natural 5.0% sin margen)

---

## 📊 Profit esperado por cuenta

### Cuenta A — $15,000 FundedNext

| Bot | LotRisk | DD esperado | $/mes |
|-----|---------|-------------|-------|
| AUDNZD v3 | 0.5% | ~3.3% | ~$226 |
| EURUSD v2 | 0.4% | ~3.8% | ~$244 |
| **TOTAL** | | **~5-6% (agregado)** | **~$470** |

% mensual: 3.1% sobre $15k
- Target Phase 1 5% ($750) → **~1.6 meses** ✅
- Target Phase 1 8% ($1,200) → **~2.6 meses** ✅

### Cuenta B — $5,000 The 5%ers

| Bot | LotRisk | DD esperado | $/mes |
|-----|---------|-------------|-------|
| AUDNZD v3 | 0.5% | ~3.3% | ~$75 |
| EURUSD v2 | 0.4% | ~3.8% | ~$81 |
| **TOTAL** | | **~5-6% (agregado)** | **~$156** |

% mensual: 3.1% sobre $5k
- Target Phase 1 5% ($250) → **~1.6 meses** ✅

---

## ⚠️ Reglas de gestión de riesgo

1. **Si los 2 bots están abiertos a la vez:** vigilar DD agregado < 4%
2. **Pausar si DD diario > 3%** (margen al 5% diario)
3. **PARAR TODO si DD total > 4%** (margen al 5% total)
4. **No añadir más bots** hasta pasar Phase 2 (DD se acumula)

### Correlación esperada AUDNZD ↔ EURUSD
Son estrategias de **regímenes opuestos** (mean reversion vs tendencia) y **divisas no correladas** → DD agregado real probable **~4-5%**, no la suma de ambos (~7%).

---

## 🔧 Estado de los EAs

| EA | Versión | Ubicaciones | Estado |
|----|---------|-------------|--------|
| AGM_Ranger_C_AUDNZD_M15 | **v3.0** | FundedNext + 5%ers + originales | ⚠️ F7 en MetaEditor |
| AGM_MA_Cross_EURUSD_M15 | **v2.0** | FundedNext + 5%ers + originales | ⚠️ F7 en MetaEditor |
| AGM_MA_Cross_GBPUSD_M15 | v1.0 | (descartado para fondeo) | — |

### Pasos para activar (manual):

1. Abrir **FundedNext MT5 Terminal**:
   - Navigator → Experts → click derecho → Refresh
   - Doble-click AGM_Ranger_C_AUDNZD_M15 → F7 → compilar
   - Doble-click AGM_MA_Cross_EURUSD_M15 → F7 → compilar
   - Arrastrar AUDNZD al gráfico **AUDNZD M15** (verificar LotRiskPct=0.5)
   - Arrastrar EURUSD al gráfico **EURUSD M15** (verificar LotRiskPct=0.4)

2. Abrir **Five Percent Online MetaTrader 5**:
   - Mismos pasos. Compilar y arrastrar los 2 bots.

### MagicNumbers
- AUDNZD = 202601
- EURUSD = 202610

---

## 📈 Próximo paso (después de fondeo)
Optimización completa de **índices** (NAS100/US500/DAX/UK100) con metodología 7 puntos anti-overfitting. Apuntado en memoria.

---
*Generado automáticamente — 17/05/2026 tras búsqueda DD<5% con 633 combos probados.*
