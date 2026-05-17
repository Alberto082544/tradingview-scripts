# Monitor — herramientas de seguimiento

## 1. `monitor_bots.py` — Métricas semanales de los bots en MT5

```bash
python monitor/monitor_bots.py              # ambos terminales (FN + 5%ers)
python monitor/monitor_bots.py FN           # solo FundedNext
python monitor/monitor_bots.py FP           # solo Five Percent
python monitor/monitor_bots.py --days 30    # ultimos 30 dias
```

Muestra: trades/bot, W/L, PnL, PF, DD, posiciones abiertas.

---

## 2. `check_communities.py` — Reddit auto-scan

Revisa cada 72h las comunidades trading y filtra posts relevantes
(forex, prop firm, walk-forward, MT5, etc.).

```bash
python monitor/check_communities.py             # consola
python monitor/check_communities.py --save      # guarda en reports/communities_*.md
python monitor/check_communities.py --hours 96  # ultimas 96h en vez de 72
```

---

## 🤖 Programar 3 veces/semana en Windows (Task Scheduler)

**Plan recomendado:** Lunes, Miércoles, Viernes a las **08:00**

### Pasos

1. **Abrir Task Scheduler**
   - Pulsa `Win + R` → escribe `taskschd.msc` → Enter

2. **Crear tarea básica**
   - Panel derecho → **"Crear tarea básica..."**

3. **Configurar pantallas:**

   | Pantalla | Valor |
   |----------|-------|
   | Nombre | `Monitor Comunidades Trading` |
   | Descripción | Revisa Reddit cada 2-3 días |
   | Desencadenador | Semanalmente |
   | Día | Lunes, Miércoles, Viernes |
   | Hora | 08:00 |
   | Acción | Iniciar un programa |
   | Programa/script | `C:\Users\alber\tradingview-scripts\python\monitor\check_communities.bat` |
   | Iniciar en | `C:\Users\alber\tradingview-scripts\python\monitor` |

4. **Click Finalizar**

5. **Probar manualmente:**
   - Click derecho sobre la tarea recién creada → **Ejecutar**
   - Debería abrirse ventana negra unos segundos
   - Verificar archivo en `reports/communities_*.md`

### Alternativa simple: el .bat directo

Si no quieres usar Task Scheduler, simplemente:
- Crea un acceso directo del `.bat` en tu escritorio
- Doble click cuando quieras revisar manualmente

---

## 3. Revisar los reportes generados

Cada ejecución guarda `reports/communities_YYYY-MM-DD_HHMM.md`.

Para verlo:
- Abrir el archivo con Notepad o VS Code
- O leerlo en GitHub si haces push del repo

Los archivos están ignorados en `.gitignore` (carpeta `reports/`) — no se suben.

---

## Mantenimiento

El filtro de keywords está en `check_communities.py`. Si ves muchos falsos
positivos, edita las listas:
- `KEYWORDS_RELEVANT` → quitar las muy genéricas (ej: 'gold' suelto)
- `KEYWORDS_NOISE` → añadir frases de marketing que aparezcan repetidas

Si quieres añadir más subreddits, edita `SUBREDDITS` (línea ~13).
