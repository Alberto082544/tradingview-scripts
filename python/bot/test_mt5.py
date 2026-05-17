import MetaTrader5 as mt5
from dotenv import load_dotenv
import os

load_dotenv()
login    = int(os.getenv("MT5_LOGIN"))
password = os.getenv("MT5_PASSWORD")
server   = os.getenv("MT5_SERVER")

print(f"Conectando: login={login} server={server}")
ok = mt5.initialize(login=login, password=password, server=server)
print(f"Conexion OK: {ok}")
if not ok:
    print(f"Error: {mt5.last_error()}")
else:
    info = mt5.account_info()
    print(f"Balance       : {info.balance}")
    print(f"trade_allowed : {info.trade_allowed}")
    print(f"trade_expert  : {info.trade_expert}")

    sym = mt5.symbol_info("XAUUSD")
    if sym:
        print(f"XAUUSD visible     : {sym.visible}")
        print(f"XAUUSD filling_mode: {sym.filling_mode}")
        print(f"XAUUSD trade_mode  : {sym.trade_mode}")
    else:
        print("XAUUSD no encontrado")

    mt5.shutdown()
