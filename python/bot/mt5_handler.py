import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from config import MT5_LOGIN, MT5_PASSWORD, MT5_SERVER, LOT_SIZE

try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False
    print("[MT5] MetaTrader5 no instalado — modo solo Telegram")

SYMBOL_MAP = {
    "XAUUSD": "XAUUSD",
    "SPX":    "US500",
    "SPY":    "US500",
    "US500":  "US500",
    "ES1!":   "US500",   # S&P 500 futuros → MT5 US500
    "NAS100": "NAS100",
    "NQ1!":   "NAS100",  # Nasdaq futuros → MT5 NAS100
    "NDX":    "NAS100",
    "BTCUSD": "BTCUSD",
    "EURUSD": "EURUSD",
}


def _connect() -> bool:
    if not MT5_AVAILABLE:
        return False
    if not mt5.initialize(login=MT5_LOGIN, password=MT5_PASSWORD, server=MT5_SERVER):
        print(f"[MT5] Error conexión: {mt5.last_error()}")
        return False
    return True


def execute_order(signal: str, ticker: str, sl: float, tp: float) -> dict:
    """
    signal: "LONG" | "SHORT"
    ticker: ticker de TradingView (ej: "XAUUSD", "SPX")
    sl, tp: niveles calculados por la estrategia
    Devuelve dict con resultado.
    """
    if not MT5_AVAILABLE:
        return {"success": False, "error": "MetaTrader5 no instalado"}

    if not _connect():
        return {"success": False, "error": "No se pudo conectar a MT5"}

    symbol = SYMBOL_MAP.get(ticker, ticker)

    import time

    # Verificar que el símbolo existe
    info = mt5.symbol_info(symbol)
    if info is None:
        mt5.shutdown()
        return {"success": False, "error": f"Símbolo {symbol} no encontrado en MT5"}

    # Añadir al Market Watch y esperar a que cargue
    if not info.visible:
        mt5.symbol_select(symbol, True)
        for _ in range(10):
            time.sleep(0.5)
            info = mt5.symbol_info(symbol)
            if info and info.visible:
                break

    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        mt5.shutdown()
        return {"success": False, "error": f"No hay precio para {symbol}"}

    order_type = mt5.ORDER_TYPE_BUY if signal == "LONG" else mt5.ORDER_TYPE_SELL
    price = tick.ask if signal == "LONG" else tick.bid

    request = {
        "action":       mt5.TRADE_ACTION_DEAL,
        "symbol":       symbol,
        "volume":       float(LOT_SIZE),
        "type":         order_type,
        "price":        price,
        "sl":           float(sl),
        "tp":           float(tp),
        "deviation":    10,
        "magic":        202600,
        "comment":      "BVortex Bot",
        "type_time":    mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request)
    mt5.shutdown()

    if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
        code = result.retcode if result else "None"
        return {"success": False, "error": f"MT5 retcode {code}"}

    return {
        "success": True,
        "order":   result.order,
        "volume":  result.volume,
        "price":   result.price,
    }
