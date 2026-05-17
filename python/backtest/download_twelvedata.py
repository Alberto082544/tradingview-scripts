"""Descarga M15 de SPY (=SP500) y QQQ (=NAS100) desde TwelveData.
Plan Basic gratis: 800 req/dia, 8 req/min, max 5000 barras por request.
Paginamos por trimestres para mantenernos bajo 5000."""
import sys, os, json, time, urllib.request, urllib.parse
from datetime import datetime, timedelta
import pandas as pd

sys.stdout.reconfigure(encoding='utf-8')

KEY = '646f36aa62c34c5db1090636c045890c'
OUT_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')

SIMBOLOS = {
    'SPY':  'SP500_proxy',
    'QQQ':  'NAS100_proxy',
}

INTERVAL  = '15min'
DATE_START = datetime(2014, 1, 1)
DATE_END   = datetime(2026, 1, 1)

# Pausa entre requests para respetar 8/min (con margen → 1 cada 8 segundos)
DELAY = 8


def fetch_chunk(symbol, start, end):
    params = {
        'symbol': symbol,
        'interval': INTERVAL,
        'start_date': start.strftime('%Y-%m-%d %H:%M:%S'),
        'end_date':   end.strftime('%Y-%m-%d %H:%M:%S'),
        'apikey': KEY,
        'outputsize': 5000,
        'order': 'asc',
        'format': 'JSON',
    }
    url = 'https://api.twelvedata.com/time_series?' + urllib.parse.urlencode(params)
    r = urllib.request.urlopen(url, timeout=30)
    return json.loads(r.read())


def descargar(symbol, nombre_salida):
    print(f"\n=== Descargando {symbol} ({nombre_salida}) ===", flush=True)
    chunks = []
    cur = DATE_START
    n_req = 0
    while cur < DATE_END:
        next_cur = cur + timedelta(days=90)  # ~trimestres
        if next_cur > DATE_END:
            next_cur = DATE_END
        try:
            data = fetch_chunk(symbol, cur, next_cur)
            if 'values' in data:
                vals = data['values']
                if vals:
                    df = pd.DataFrame(vals)
                    chunks.append(df)
                    print(f"  {cur.date()} -> {next_cur.date()}: {len(vals)} barras", flush=True)
                else:
                    print(f"  {cur.date()} -> {next_cur.date()}: 0 barras", flush=True)
            else:
                print(f"  {cur.date()} -> {next_cur.date()}: ERROR {data.get('message', '?')[:60]}", flush=True)
                if 'limit' in data.get('message', '').lower():
                    print("  Limite de rate alcanzado, esperando 60s...", flush=True)
                    time.sleep(60)
                    continue
        except Exception as e:
            print(f"  Excepcion: {e}", flush=True)
        cur = next_cur
        n_req += 1
        time.sleep(DELAY)

    if not chunks:
        print(f"  Sin datos para {symbol}", flush=True)
        return None

    df = pd.concat(chunks, ignore_index=True)
    df['datetime'] = pd.to_datetime(df['datetime'])
    df = df.sort_values('datetime').drop_duplicates('datetime').reset_index(drop=True)
    # Asegurar columnas estándar
    for col in ['open', 'high', 'low', 'close']:
        if col in df.columns:
            df[col] = df[col].astype(float)
    df = df.rename(columns={'datetime': 'time'})

    # Filtrar volumen si existe
    cols_out = [c for c in ['time', 'open', 'high', 'low', 'close', 'volume'] if c in df.columns]
    df = df[cols_out]

    out_path = os.path.join(OUT_DIR, f'{nombre_salida}_M15_twelvedata.csv')
    df.to_csv(out_path, index=False)
    print(f"  ✓ Total: {len(df):,} barras  ({df['time'].iloc[0]} -> {df['time'].iloc[-1]})", flush=True)
    print(f"  → Guardado: {out_path}", flush=True)
    return df


if __name__ == '__main__':
    for sym, nombre in SIMBOLOS.items():
        descargar(sym, nombre)
    print("\n=== DESCARGA COMPLETA ===", flush=True)
