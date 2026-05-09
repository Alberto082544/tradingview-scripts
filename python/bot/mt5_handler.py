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
    "XAUUSD":    "XAUUSD",
    "SPX":       "US500",
    "SPY":       "US500",
    "US500":     "US500",
    "SPX500":    "US500",
    "NAS100":    "USTEC",
    "NAS100USD": "USTEC",
    "NDX100":    "USTEC",
    "USTEC":     "USTEC",
    "BTCUSD":    "BTCUSD",
    "EURUSD":    "EURUSD",
    "GBPUSD":    "GBPUSD",
}

# SL/TP automático cuando la alerta no los envía (% sobre precio de entrada)
# (sl_pct, tp_pct) → RR 1:2 por defecto
_AUTO_SLTP = {
    "XAUUSD":  (0.006, 0.012),
    "US500":   (0.005, 0.010),
    "USTEC":   (0.006, 0.012),
    "EURUSD":  (0.003, 0.006),
    "GBPUSD":  (0.003, 0.006),
    "BTCUSD":  (0.010, 0.020),
    "_DEFAULT": (0.005, 0.010),
}


def _auto_sltp(symbol: str, signal: str, price: float):
    sl_pct, tp_pct = _AUTO_SLTP.get(symbol, _AUTO_SLTP["_DEFAULT"])
    if signal == "LONG":
        return round(price * (1 - sl_pct), 2), round(price * (1 + tp_pct), 2)
    else:
        return round(price * (1 + sl_pct), 2), round(price * (1 - tp_pct), 2)


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
    sl, tp: 0 = calcular automáticamente
    """
    if not MT5_AVAILABLE:
        return {"success": False, "error": "MetaTrader5 no instalado"}

    if not _connect():
        return {"success": False, "error": "No se pudo conectar a MT5"}

    symbol = SYMBOL_MAP.get(ticker, ticker)

    import time

    info = mt5.symbol_info(symbol)
    if info is None:
        mt5.shutdown()
        return {"success": False, "error": f"Símbolo {symbol} no encontrado en MT5"}

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

    # Auto SL/TP si la alerta no los envía
    if sl == 0 or tp == 0:
        sl, tp = _auto_sltp(symbol, signal, price)
        print(f"[MT5] Auto SL/TP calculado: sl={sl} tp={tp}")

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
        "sl":      sl,
        "tp":      tp,
    }
