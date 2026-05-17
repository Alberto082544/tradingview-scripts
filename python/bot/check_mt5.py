import sys
sys.path.insert(0,'C:/Users/alber/tradingview-scripts/python/bot')
from config import MT5_LOGIN, MT5_PASSWORD, MT5_SERVER
import MetaTrader5 as mt5, time

mt5.initialize(login=MT5_LOGIN, password=MT5_PASSWORD, server=MT5_SERVER)
info = mt5.account_info()
out = [f'OK: {info.login} {info.balance} {info.currency} {info.server}']
for sym in ['XAUUSD','US500','USTEC']:
    mt5.symbol_select(sym, True)
    time.sleep(0.4)
    t = mt5.symbol_info_tick(sym)
    out.append(f'{sym}: {"bid="+str(t.bid) if t and t.bid>0 else "sin precio"}')
mt5.shutdown()
open('mt5_out2.txt','w').write('\n'.join(out))
