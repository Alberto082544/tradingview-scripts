import requests
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID


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
    signal  = data.get("signal", "?")
    ticker  = data.get("ticker", "?")
    tf      = data.get("tf", "?")
    close   = data.get("close", "?")
    sl      = data.get("sl", "?")
    tp      = data.get("tp", "?")

    emoji   = "🟢" if signal == "LONG" else "🔴"
    dir_txt = "▲ COMPRA (LONG)" if signal == "LONG" else "▼ VENTA (SHORT)"

    return (
        f"{emoji} <b>SEÑAL {signal} — BVortex</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>{ticker}</b> | {tf}H\n"
        f"💰 Entrada: <b>{close}</b>\n"
        f"🛑 SL: <b>{sl}</b>\n"
        f"🎯 TP: <b>{tp}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"<i>{dir_txt}</i>\n"
        f"▶️ Activa el bot en MT5"
    )
