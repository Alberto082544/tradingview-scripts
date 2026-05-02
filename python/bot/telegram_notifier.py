import requests
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID

# Activos monitorizados y sus timeframes recomendados
ACTIVOS = {
    "XAUUSD": {"tf_optimo": "60",  "nombre": "Oro"},
    "SPX":    {"tf_optimo": "240", "nombre": "S&P 500"},
    "SPY":    {"tf_optimo": "240", "nombre": "S&P 500 ETF"},
    "BTCUSD": {"tf_optimo": "60",  "nombre": "Bitcoin"},
    "ETHUSD": {"tf_optimo": "60",  "nombre": "Ethereum"},
    "EURUSD": {"tf_optimo": "60",  "nombre": "EUR/USD"},
}


def send_message(text: str) -> bool:
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        return r.status_code == 200
    except Exception as e:
        print(f"[Telegram] Error: {e}")
        return False


def format_signal(data: dict) -> str:
    signal = data.get("signal", "?")
    ticker = data.get("ticker", "?")
    tf     = data.get("tf", "?")
    close  = data.get("close", "?")
    sl     = data.get("sl", "?")
    tp     = data.get("tp", "?")

    emoji    = "🟢" if signal == "LONG"  else "🔴"
    dir_txt  = "▲ COMPRA (LONG)"        if signal == "LONG" else "▼ VENTA (SHORT)"
    mt5_dir  = "BUY"                    if signal == "LONG" else "SELL"

    info     = ACTIVOS.get(ticker, {})
    nombre   = info.get("nombre", ticker)
    tf_label = f"{tf}min" if tf.isdigit() else tf

    # Calcular riesgo aproximado (distancia SL)
    try:
        riesgo = round(abs(float(close) - float(sl)), 2)
        beneficio = round(abs(float(tp) - float(close)), 2)
    except Exception:
        riesgo = "?"
        beneficio = "?"

    return (
        f"{emoji} <b>SEÑAL {signal} — BVortex</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>{nombre} ({ticker})</b> | {tf_label}\n"
        f"💰 Entrada : <b>{close}</b>\n"
        f"🛑 SL      : <b>{sl}</b>  ({riesgo} pts)\n"
        f"🎯 TP      : <b>{tp}</b>  ({beneficio} pts)\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"MT5 → <code>{mt5_dir} {ticker} SL:{sl} TP:{tp}</code>\n"
        f"▶️ <b>Activa el bot en MT5 — {dir_txt}</b>"
    )
