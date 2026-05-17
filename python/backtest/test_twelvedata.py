"""Test rapido API TwelveData: ver que simbolos de indice funcionan."""
import sys, json, urllib.request
sys.stdout.reconfigure(encoding='utf-8')

KEY = '646f36aa62c34c5db1090636c045890c'

simbolos = ['SPX', 'NDX', 'DJI', 'DAX', 'UKX', 'SPY', 'QQQ', 'IWM']

for s in simbolos:
    url = f'https://api.twelvedata.com/time_series?symbol={s}&interval=15min&apikey={KEY}&outputsize=5'
    try:
        r = urllib.request.urlopen(url, timeout=15)
        data = json.loads(r.read())
        if 'values' in data:
            n = len(data['values'])
            d0 = data['values'][-1]['datetime'] if n else '-'
            dn = data['values'][0]['datetime'] if n else '-'
            close = data['values'][0]['close'] if n else '-'
            print(f'  {s:6s}: OK  {n} barras M15 ({d0} -> {dn}) precio: {close}')
        elif 'code' in data:
            print(f'  {s:6s}: FAIL {data.get("message", "?")[:60]}')
        else:
            print(f'  {s:6s}: ?  {str(data)[:80]}')
    except Exception as e:
        print(f'  {s:6s}: error  {e}')
