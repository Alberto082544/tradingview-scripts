"""Revisa comunidades Reddit (r/algotrading, r/Forex, r/PropFirmTrading, etc.)
y reporta posts relevantes de las ultimas 72h.

Sin API key — usa RSS publico de Reddit.

Uso:
  python monitor/check_communities.py             # output a consola
  python monitor/check_communities.py --save      # guarda informe en reports/

Para programar 3 veces/semana, ver monitor/README.md
"""
import sys, os, argparse
sys.stdout.reconfigure(encoding='utf-8')

import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
import re

# Subreddits a revisar
SUBREDDITS = [
    'algotrading',
    'Forex',
    'PropFirmTrading',
    'Daytrading',
    'algotradingsystems',
]

# Palabras clave que indican que el post es RELEVANTE para nosotros
# Si el titulo/descripcion contiene cualquiera de estas → reportar
KEYWORDS_RELEVANT = [
    # estrategias relevantes
    'mean reversion', 'trend following', 'walk-forward', 'walk forward',
    'overfit', 'overfitting', 'monte carlo', 'sharpe',
    # indicadores que usamos
    'vwap', 'ema', 'adx', 'bollinger', 'stochrsi', 'stoch rsi', 'order block', 'fvg',
    'smart money',
    # prop firms
    'fundednext', 'funded next', '5%ers', 'the5ers', 'prop firm', 'evaluation',
    'phase 1', 'phase 2', 'drawdown limit',
    # mercados que operamos
    'audnzd', 'eurusd', 'nas100', 'nasdaq', 'xauusd', 'gold',
    # plataformas
    'mt5', 'metatrader 5', 'mql5', 'python trading',
    # conceptos clave
    'kelly criterion', 'kelly sizing', 'position sizing', 'risk management',
    'backtest', 'optimization', 'hmm', 'regime',
]

# Spam/ruido a IGNORAR
KEYWORDS_NOISE = [
    'free signals', 'join my', 'dm me', 'telegram group', 'whatsapp', 'discord invite',
    'how much can i make', 'is this profitable', '100% win', 'no losses',
    'crypto only', 'memecoin', 'shitcoin',
]


def fetch_rss(sub):
    url = f'https://www.reddit.com/r/{sub}/.rss?limit=30'
    req = urllib.request.Request(url, headers={'User-Agent': 'AGM-TradingMonitor/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.read().decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"  [{sub}] error: {e}")
        return None


def parse_entries(xml_text):
    """Parsea feed Atom de Reddit."""
    ns = {'atom': 'http://www.w3.org/2005/Atom'}
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        return []
    entries = []
    for entry in root.findall('atom:entry', ns):
        title   = (entry.find('atom:title', ns).text or '').strip()
        content = (entry.find('atom:content', ns).text or '').strip()
        updated = (entry.find('atom:updated', ns).text or '').strip()
        link_elem = entry.find('atom:link', ns)
        link = link_elem.get('href') if link_elem is not None else ''
        author = ''
        author_elem = entry.find('atom:author', ns)
        if author_elem is not None:
            name_elem = author_elem.find('atom:name', ns)
            if name_elem is not None:
                author = name_elem.text or ''
        # Parse ISO 8601 con timezone
        try:
            dt = datetime.fromisoformat(updated.replace('Z', '+00:00'))
        except Exception:
            dt = datetime.now(timezone.utc)
        entries.append({'title':title, 'content':content, 'updated':dt,
                        'link':link, 'author':author})
    return entries


def es_relevante(entry):
    """Filtro: titulo o resumen contiene keyword relevante y NO contiene ruido."""
    texto = (entry['title'] + ' ' + entry['content']).lower()
    # Quitar HTML basico
    texto = re.sub(r'<[^>]+>', ' ', texto)
    # Filtrar ruido primero
    for noise in KEYWORDS_NOISE:
        if noise in texto:
            return False, None
    # Buscar keywords
    matched = [k for k in KEYWORDS_RELEVANT if k in texto]
    return (len(matched) > 0), matched


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--save', action='store_true', help='Guardar reporte en reports/')
    p.add_argument('--hours', type=int, default=72, help='Ventana en horas (defecto 72)')
    args = p.parse_args()

    desde = datetime.now(timezone.utc) - timedelta(hours=args.hours)
    print(f"Revisando ultimas {args.hours}h en {len(SUBREDDITS)} subreddits...\n")

    relevantes_global = []

    for sub in SUBREDDITS:
        xml = fetch_rss(sub)
        if xml is None:
            continue
        entries = parse_entries(xml)
        relevantes_sub = []
        for e in entries:
            if e['updated'] < desde:
                continue
            ok, matches = es_relevante(e)
            if ok:
                e['matches'] = matches
                e['sub'] = sub
                relevantes_sub.append(e)
                relevantes_global.append(e)
        print(f"  r/{sub:20s} {len(entries):>2} posts → {len(relevantes_sub)} relevantes")

    # Ordenar por fecha desc
    relevantes_global.sort(key=lambda e: e['updated'], reverse=True)

    print(f"\n{'='*78}")
    print(f"  RELEVANTES TOTAL: {len(relevantes_global)}")
    print(f"{'='*78}")

    lines = [f"# Reporte comunidades — {datetime.now().strftime('%Y-%m-%d %H:%M')}",
             f"Ventana: {args.hours}h | Subreddits: {len(SUBREDDITS)}",
             f"Posts relevantes encontrados: {len(relevantes_global)}", ""]

    if not relevantes_global:
        print("  Nada relevante esta semana. Revisar de nuevo en 2-3 dias.")
        lines.append("**Sin novedades relevantes.**\n")
    else:
        for e in relevantes_global:
            ago = (datetime.now(timezone.utc) - e['updated']).total_seconds() / 3600
            print(f"\n  [r/{e['sub']}] hace {ago:.1f}h por {e['author']}")
            print(f"  Titulo: {e['title'][:100]}")
            print(f"  Match:  {', '.join(e['matches'][:5])}")
            print(f"  Link:   {e['link']}")

            lines.append(f"## [{e['sub']}] {e['title']}")
            lines.append(f"- **Hace:** {ago:.1f}h por u/{e['author']}")
            lines.append(f"- **Match keywords:** {', '.join(e['matches'])}")
            lines.append(f"- **Link:** {e['link']}\n")

    if args.save:
        out_dir = os.path.join(os.path.dirname(__file__), '..', 'reports')
        os.makedirs(out_dir, exist_ok=True)
        fname = f"communities_{datetime.now().strftime('%Y-%m-%d_%H%M')}.md"
        out_path = os.path.join(out_dir, fname)
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        print(f"\n  Guardado: {out_path}")


if __name__ == '__main__':
    main()
