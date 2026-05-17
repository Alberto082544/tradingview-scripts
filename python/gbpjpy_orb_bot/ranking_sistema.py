"""
SISTEMA DE RANKING DE ESTRATEGIAS
Puntuación 0-100 por criterios ponderados.
Para añadir una estrategia nueva: añadir un dict a ESTRATEGIAS y ejecutar el script.
"""

import json

# ─────────────────────────────────────────────
# BASE DE DATOS DE ESTRATEGIAS
# Añade aquí cada nueva estrategia que desarrolles
# ─────────────────────────────────────────────
ESTRATEGIAS = [
    {
        "nombre": "Bot Oro — Apertura NY",
        "activo": "XAUUSD",
        "tipo": "Ruptura apertura",
        "capital": 50000,
        "pnl_total": 38964,
        "rentabilidad_pct": 77.9,
        "años": 6,
        "profit_factor": 1.32,
        "winrate": 52.6,
        "max_dd_pct": 7.5,
        "anos_negativos": 0,
        "wf_ratio": 1.21,
        "mc_pct_positivo": 100,
        "mc_dd_p95": 9.6,
    },
    {
        "nombre": "Bot GBPJPY — Conservador",
        "activo": "GBPJPY",
        "tipo": "Seguimiento tendencia",
        "capital": 50000,
        "pnl_total": 51789,
        "rentabilidad_pct": 103.5,
        "años": 6,
        "profit_factor": 1.46,
        "winrate": 20.6,
        "max_dd_pct": 9.8,
        "anos_negativos": 0,
        "wf_ratio": 1.07,
        "mc_pct_positivo": 70,
        "mc_dd_p95": 13.0,
    },
    {
        "nombre": "Bot GBPJPY — Agresivo",
        "activo": "GBPJPY",
        "tipo": "Seguimiento tendencia",
        "capital": 50000,
        "pnl_total": 62274,
        "rentabilidad_pct": 124.5,
        "años": 6,
        "profit_factor": 1.45,
        "winrate": 18.7,
        "max_dd_pct": 13.6,
        "anos_negativos": 1,
        "wf_ratio": 1.06,
        "mc_pct_positivo": 60,
        "mc_dd_p95": 19.4,
    },
    {
        "nombre": "Bot GBPJPY — Apertura Londres",
        "activo": "GBPJPY",
        "tipo": "Ruptura apertura",
        "capital": 50000,
        "pnl_total": 24251,
        "rentabilidad_pct": 48.5,
        "años": 6,
        "profit_factor": 1.10,
        "winrate": 39.1,
        "max_dd_pct": 9.7,
        "anos_negativos": 0,
        "wf_ratio": 0.96,
        "mc_pct_positivo": 37,
        "mc_dd_p95": 17.0,
    },
    {
        "nombre": "AGM Ranger v5 — Mean Reversion GBPJPY",
        "activo": "GBPJPY",
        "tipo": "Mean Reversion BB+RSI+ADX",
        "capital": 50000,
        "pnl_total": 2470,         # 11 años a 0.7% riesgo (×1.4 vs backtest 0.5%)
        "rentabilidad_pct": 4.94,  # total 11 años
        "años": 11,
        "profit_factor": 1.24,
        "winrate": 53.6,
        "max_dd_pct": 1.5,         # 1.1% a 0.5% → 1.54% a 0.7%
        "anos_negativos": 2,       # 2019 y 2020
        "wf_ratio": 1.27,          # OOS PF 1.47 / IS PF 1.16
        "mc_pct_positivo": 95,     # ruin=0%, P95 DD=3.2% — casi todas positivas
        "mc_dd_p95": 3.2,
    },
    # ── Bots validados 2026-05-16 — métricas OOS (2022-2025, 4 años) ──
    {
        "nombre": "AGM MA Cross — EURUSD M15",
        "activo": "EURUSD",
        "tipo": "MA Cross H4+M15 (Tendencia)",
        "capital": 50000,
        "pnl_total": 95316,
        "rentabilidad_pct": 122.84,  # 30.71%/año × 4 años OOS
        "años": 4,
        "profit_factor": 1.36,
        "winrate": 68.9,
        "max_dd_pct": 6.5,
        "anos_negativos": 0,         # 12/12 años positivos
        "wf_ratio": 0.958,
        "mc_pct_positivo": 100,
        "mc_dd_p95": 12.8,
    },
    {
        "nombre": "AGM MA Cross — GBPUSD M15",
        "activo": "GBPUSD",
        "tipo": "MA Cross H4+M15 (Tendencia)",
        "capital": 50000,
        "pnl_total": 87947,
        "rentabilidad_pct": 116.44,  # 29.11%/año × 4 años OOS
        "años": 4,
        "profit_factor": 1.35,
        "winrate": 53.8,
        "max_dd_pct": 9.8,
        "anos_negativos": 0,         # 12/12 años positivos
        "wf_ratio": 0.978,
        "mc_pct_positivo": 100,
        "mc_dd_p95": 13.5,
    },
    {
        "nombre": "AGM Ranger C — AUDNZD M15",
        "activo": "AUDNZD",
        "tipo": "Mean Reversion BB+RSI+ADX",
        "capital": 50000,
        "pnl_total": 51392,
        "rentabilidad_pct": 87.32,   # 21.83%/año × 4 años OOS
        "años": 4,
        "profit_factor": 1.16,
        "winrate": 59.7,
        "max_dd_pct": 12.6,
        "anos_negativos": 1,         # 11/12 años positivos (2018 rojo)
        "wf_ratio": 1.045,
        "mc_pct_positivo": 100,
        "mc_dd_p95": 23.2,
    },
]

# ─────────────────────────────────────────────
# CRITERIOS Y PESOS
# ─────────────────────────────────────────────
CRITERIOS = {
    "Ganancia anual":            {"peso": 0.20, "mejor": "max", "min": 0,   "max": 25},
    "Ratio ganancia/perdida":    {"peso": 0.15, "mejor": "max", "min": 1.0, "max": 1.6},
    "Funciona en datos nuevos":  {"peso": 0.20, "mejor": "max", "min": 0.8, "max": 1.3},
    "% simulaciones ganadoras":  {"peso": 0.20, "mejor": "max", "min": 0,   "max": 100},
    "Perdida maxima":            {"peso": 0.15, "mejor": "min", "min": 5,   "max": 25},
    "Anos en perdidas":          {"peso": 0.10, "mejor": "min", "min": 0,   "max": 3},
}

def score_metrica(valor, config):
    mn, mx = config["min"], config["max"]
    ratio = (valor - mn) / (mx - mn)
    ratio = max(0.0, min(1.0, ratio))
    return ratio * 10 if config["mejor"] == "max" else (1 - ratio) * 10

def calcular_scores(estrategias):
    for e in estrategias:
        rent_anual = (e["rentabilidad_pct"] / e["años"])
        valores = {
            "Ganancia anual":            rent_anual,
            "Ratio ganancia/perdida":    e["profit_factor"],
            "Funciona en datos nuevos":  e["wf_ratio"],
            "% simulaciones ganadoras":  e["mc_pct_positivo"],
            "Perdida maxima":            e["max_dd_pct"],
            "Anos en perdidas":          e["anos_negativos"],
        }
        e["_rent_anual"] = round(rent_anual, 1)
        e["_scores"] = {}
        total = 0
        for crit, cfg in CRITERIOS.items():
            s = score_metrica(valores[crit], cfg)
            e["_scores"][crit] = round(s, 1)
            total += s * cfg["peso"]
        e["_score_total"] = round(total * 10, 1)  # 0-100
    return sorted(estrategias, key=lambda x: x["_score_total"], reverse=True)

def color_score(s):
    if s >= 75: return "#1a7a3a"
    if s >= 55: return "#2a7a2a"
    if s >= 40: return "#e67e22"
    return "#c0392b"

def bar(s, max_s=100):
    pct = int(s / max_s * 100)
    col = color_score(s)
    return f'<div style="background:#eee;border-radius:4px;height:8px;width:100%"><div style="background:{col};width:{pct}%;height:8px;border-radius:4px"></div></div>'

def generar_html(estrategias):
    rows = ""
    for i, e in enumerate(estrategias):
        medal = ["🥇","🥈","🥉","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣"][i] if i < 8 else str(i+1)
        col = color_score(e["_score_total"])
        nota = max(1, min(10, round(e["_score_total"] / 10)))
        score_bars = "".join(
            f'<tr><td style="color:#888;font-size:0.8em;padding:2px 0">{c}</td>'
            f'<td style="padding:2px 0 2px 8px;font-size:0.8em;font-weight:700;color:{color_score(v*10)}">{v:.1f}/10</td>'
            f'<td style="padding:2px 0 2px 8px;width:80px">{bar(v*10, 10)}</td></tr>'
            for c, v in e["_scores"].items()
        )
        rows += f"""
        <div style="background:white;border-radius:12px;box-shadow:0 2px 10px rgba(0,0,0,0.08);overflow:hidden;margin-bottom:16px">
          <div style="display:flex;align-items:center;padding:14px 20px;border-bottom:1px solid #eee">
            <span style="font-size:1.5em;margin-right:12px">{medal}</span>
            <div style="flex:1">
              <div style="font-weight:700;font-size:1em;color:#1a3a6b">{e['nombre']} <span style="background:{col};color:white;border-radius:20px;padding:2px 10px;font-size:0.85em;margin-left:6px">{nota}/10</span></div>
              <div style="font-size:0.78em;color:#999">{e['activo']} · {e['tipo']}</div>
            </div>
            <div style="text-align:right">
              <div style="font-size:2em;font-weight:800;color:{col}">{e['_score_total']}</div>
              <div style="font-size:0.72em;color:#999;text-transform:uppercase">/ 100</div>
            </div>
          </div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:0">
            <div style="padding:14px 20px;border-right:1px solid #f0f0f0">
              <table style="width:100%;border-collapse:collapse">{score_bars}</table>
            </div>
            <div style="padding:14px 20px">
              <table style="width:100%;border-collapse:collapse;font-size:0.85em">
                <tr><td style="color:#888;padding:2px 0">P&amp;L total</td><td style="text-align:right;font-weight:700;color:#1a7a3a">+${e['pnl_total']:,}</td></tr>
                <tr><td style="color:#888;padding:2px 0">Rentabilidad anual</td><td style="text-align:right;font-weight:700">+{e['_rent_anual']}%</td></tr>
                <tr><td style="color:#888;padding:2px 0">Profit Factor</td><td style="text-align:right;font-weight:700">{e['profit_factor']}</td></tr>
                <tr><td style="color:#888;padding:2px 0">Drawdown máx.</td><td style="text-align:right;font-weight:700">{e['max_dd_pct']}%</td></tr>
                <tr><td style="color:#888;padding:2px 0">Walk-Forward</td><td style="text-align:right;font-weight:700">{e['wf_ratio']}</td></tr>
                <tr><td style="color:#888;padding:2px 0">MC % positivo</td><td style="text-align:right;font-weight:700">{e['mc_pct_positivo']}%</td></tr>
              </table>
            </div>
          </div>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Ranking Estrategias</title>
<style>
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{ font-family:Segoe UI,Arial,sans-serif; background:#f0f2f5; color:#222; }}
  .header {{ background:linear-gradient(135deg,#1a3a6b,#2a5298); color:white; padding:28px 36px; }}
  .header h1 {{ font-size:1.6em; font-weight:700; }}
  .header p {{ font-size:0.88em; opacity:0.7; margin-top:4px; }}
  .container {{ max-width:820px; margin:0 auto; padding:28px 20px 50px; }}
  .criterios {{ background:white; border-radius:10px; padding:16px 20px; margin-bottom:24px;
               box-shadow:0 2px 8px rgba(0,0,0,0.07); font-size:0.83em; color:#555; }}
  .criterios strong {{ color:#1a3a6b; }}
</style>
</head>
<body>
<div class="header">
  <h1>Ranking de Estrategias</h1>
  <p>Ordenadas de mejor a peor · Puntuación 0–100 · Capital $50,000 · Backtest 2020–2025</p>
</div>
<div class="container">
  <div class="criterios">
    <strong>Criterios de puntuacion:</strong>
    Ganancia anual (20%) · Ratio ganancia/perdida (15%) · Funciona en datos nuevos (20%) · % simulaciones ganadoras (20%) · Perdida maxima (15%) · Anos en perdidas (10%)
  </div>
  {rows}
  <p style="font-size:0.75em;color:#aaa;text-align:center;margin-top:8px">
    Generado automáticamente por ranking_sistema.py · {__import__('datetime').date.today()}
  </p>
</div>
</body>
</html>"""
    return html

if __name__ == "__main__":
    ranked = calcular_scores(ESTRATEGIAS)
    html = generar_html(ranked)
    out = r"C:\Users\alber\OneDrive\Desktop\ORB_BOTS_COMPLETO\RANKING_ESTRATEGIAS.html"
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print("\n RANKING FINAL")
    print("-" * 45)
    for i, e in enumerate(ranked):
        print(f"  {i+1}. {e['nombre']:<30} {e['_score_total']:>5}/100")
    print(f"\n Guardado en: {out}")
