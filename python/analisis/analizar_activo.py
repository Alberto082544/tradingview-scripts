"""Analisis tecnico en tiempo real de un activo vía TwelveData.

Descarga ultimas N barras, calcula indicadores y da veredicto.

Uso:
  python analisis/analizar_activo.py BTC/USD 1h
  python analisis/analizar_activo.py GBP/JPY 1h
  python analisis/analizar_activo.py BTC/USD 15min
"""
import sys, os, json, urllib.request, urllib.parse
sys.stdout.reconfigure(encoding='utf-8')
from datetime import datetime
import pandas as pd
import numpy as np

# Cargar API key
from pathlib import Path
ENV_PATH = Path(__file__).resolve().parents[2] / 'trading_researcher' / '.env'
for line in ENV_PATH.read_text(encoding='utf-8').splitlines():
    if '=' in line and not line.strip().startswith('#'):
        k, v = line.split('=', 1)
        os.environ.setdefault(k.strip(), v.strip())

KEY = os.environ['TWELVEDATA_API_KEY']


def fetch(symbol, interval, n=200):
    params = {'symbol': symbol, 'interval': interval, 'apikey': KEY, 'outputsize': n}
    url = 'https://api.twelvedata.com/time_series?' + urllib.parse.urlencode(params)
    r = urllib.request.urlopen(url, timeout=20)
    data = json.loads(r.read())
    if 'values' not in data:
        return None, data.get('message', 'error')
    df = pd.DataFrame(data['values'])
    df['datetime'] = pd.to_datetime(df['datetime'])
    df = df.sort_values('datetime').set_index('datetime')
    for c in ['open','high','low','close']:
        df[c] = df[c].astype(float)
    return df, None


def indicators(df):
    df = df.copy()
    df['ema9']   = df['close'].ewm(span=9,   adjust=False).mean()
    df['ema21']  = df['close'].ewm(span=21,  adjust=False).mean()
    df['ema50']  = df['close'].ewm(span=50,  adjust=False).mean()
    df['ema200'] = df['close'].ewm(span=200, adjust=False).mean()
    # RSI
    delta = df['close'].diff()
    gain = delta.clip(lower=0).ewm(com=13, min_periods=14).mean()
    loss = (-delta).clip(lower=0).ewm(com=13, min_periods=14).mean()
    df['rsi'] = 100 - (100 / (1 + gain / loss.replace(0, np.nan)))
    # ATR
    hl = df['high'] - df['low']
    hc = (df['high'] - df['close'].shift()).abs()
    lc = (df['low']  - df['close'].shift()).abs()
    tr = pd.concat([hl,hc,lc], axis=1).max(axis=1)
    df['atr'] = tr.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    # Niveles soporte/resistencia (ult 50 barras)
    df['high50'] = df['high'].rolling(50).max()
    df['low50']  = df['low'].rolling(50).min()
    return df


def analizar(df, simbolo):
    last = df.iloc[-1]
    prev = df.iloc[-2]
    close = last['close']
    high50 = last['high50']
    low50 = last['low50']
    atr = last['atr']
    rsi = last['rsi']

    print(f"\n{'='*78}")
    print(f"  ANALISIS  {simbolo}  —  {last.name.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*78}")
    print(f"\n  Precio actual: {close:.4f}")
    print(f"  Cambio ultima vela: {((close-prev['close'])/prev['close']*100):+.2f}%")
    print(f"\n  EMA9 :  {last['ema9']:.4f}   ({'arriba' if close>last['ema9'] else 'abajo'})")
    print(f"  EMA21:  {last['ema21']:.4f}   ({'arriba' if close>last['ema21'] else 'abajo'})")
    print(f"  EMA50:  {last['ema50']:.4f}   ({'arriba' if close>last['ema50'] else 'abajo'})")
    print(f"  EMA200: {last['ema200']:.4f}   ({'arriba' if close>last['ema200'] else 'abajo'})")
    print(f"\n  RSI(14): {rsi:.1f}   ({rsi_zone(rsi)})")
    print(f"  ATR(14): {atr:.4f}   (~{atr/close*100:.2f}% del precio)")
    print(f"\n  RANGO ULTIMAS 50 BARRAS:")
    print(f"    High: {high50:.4f}  (a {(high50-close)/close*100:+.2f}% del actual)")
    print(f"    Low:  {low50:.4f}   (a {(low50-close)/close*100:+.2f}% del actual)")
    pos_rango = (close - low50) / (high50 - low50) * 100 if high50 != low50 else 50
    print(f"    Posicion en rango: {pos_rango:.1f}% (0=low, 100=high)")

    # ===== Estructura =====
    print(f"\n  ESTRUCTURA:")
    bull = last['ema9'] > last['ema21'] > last['ema50']
    bear = last['ema9'] < last['ema21'] < last['ema50']
    if bull and close > last['ema200']:
        estructura = "ALCISTA fuerte (todas EMAs alineadas + sobre EMA200)"
    elif bull:
        estructura = "ALCISTA corto plazo (EMAs cortas OK, pero bajo EMA200)"
    elif bear and close < last['ema200']:
        estructura = "BAJISTA fuerte (todas EMAs alineadas + bajo EMA200)"
    elif bear:
        estructura = "BAJISTA corto plazo"
    else:
        estructura = "LATERAL / mixto (EMAs cruzadas)"
    print(f"    {estructura}")

    # ===== Veredicto =====
    print(f"\n  VEREDICTO TECNICO:")
    setups = []
    # Sobreventa en tendencia alcista
    if (bull or close > last['ema200']) and rsi < 35:
        setups.append("LONG potencial: tendencia alcista + RSI sobreventa")
    # Sobrecompra en tendencia alcista (precaucion)
    if bull and rsi > 75:
        setups.append("Tendencia alcista pero SOBRECOMPRADA — esperar pullback")
    # Sobreventa en bajista
    if bear and rsi < 25:
        setups.append("Tendencia bajista pero SOBREVENDIDA — posible rebote, no entrada")
    # Sobrecompra en bajista
    if (bear or close < last['ema200']) and rsi > 65:
        setups.append("SHORT potencial: tendencia bajista + RSI sobrecompra")
    # Cerca de niveles clave
    if (high50 - close) / close < 0.005:
        setups.append("Cerca de high de 50 barras — resistencia clave, riesgo de rechazo")
    if (close - low50) / close < 0.005:
        setups.append("Cerca de low de 50 barras — soporte clave, posible rebote")
    # Lateral
    if not bull and not bear:
        setups.append("Mercado LATERAL — operar mean reversion si rebota en extremos")

    if not setups:
        setups.append("Sin setup claro ahora mismo — esperar mejor oportunidad")
    for s in setups:
        print(f"    - {s}")

    # Niveles para operar
    print(f"\n  NIVELES (si decides entrar):")
    print(f"    SL tecnico ajustado (1.5×ATR): {1.5*atr:.4f} ({1.5*atr/close*100:.2f}%)")
    print(f"    TP 1R: {close + 1.5*atr:.4f} long / {close - 1.5*atr:.4f} short")
    print(f"    TP 2R: {close + 3.0*atr:.4f} long / {close - 3.0*atr:.4f} short")
    print(f"    TP 3R: {close + 4.5*atr:.4f} long / {close - 4.5*atr:.4f} short")


def rsi_zone(rsi):
    if rsi >= 70: return "SOBRECOMPRADO"
    if rsi <= 30: return "SOBREVENDIDO"
    if rsi >= 60: return "alcista"
    if rsi <= 40: return "bajista"
    return "neutro"


def main():
    if len(sys.argv) < 2:
        print("Uso: python analisis/analizar_activo.py SIMBOLO [INTERVAL]")
        print("Ejemplos: BTC/USD 1h, GBP/JPY 15min")
        return
    simbolo = sys.argv[1]
    interval = sys.argv[2] if len(sys.argv) > 2 else '1h'

    print(f"Descargando {simbolo} {interval}...")
    df, err = fetch(simbolo, interval)
    if df is None:
        print(f"Error: {err}")
        return
    print(f"  {len(df)} barras desde {df.index[0]} hasta {df.index[-1]}")
    df = indicators(df)
    analizar(df, f"{simbolo} {interval}")


if __name__ == '__main__':
    main()
