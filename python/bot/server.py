import json
import sys
import os
import logging

sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask, request, jsonify
from telegram_notifier import send_message, format_signal
from mt5_handler import execute_order
from config import WEBHOOK_SECRET, PORT

# Logging a archivo (append)
_log_path = os.path.join(os.path.dirname(__file__), "flask.log")
_handler = logging.FileHandler(_log_path, encoding="utf-8")
_handler.setFormatter(logging.Formatter("[%(asctime)s] %(message)s", datefmt="%d/%m/%Y %H:%M:%S"))
logging.basicConfig(level=logging.INFO, handlers=[_handler])
log = logging.getLogger(__name__)

app = Flask(__name__)

# TradingView envía "buy"/"sell" — mapeamos a LONG/SHORT
_ACTION = {"buy": "LONG", "sell": "SHORT", "long": "LONG", "short": "SHORT"}


@app.route("/webhook", methods=["POST"])
def webhook():
    secret = request.args.get("secret") or request.headers.get("X-Secret", "")
    if secret != WEBHOOK_SECRET:
        log.warning("Intento no autorizado desde %s", request.remote_addr)
        return jsonify({"error": "unauthorized"}), 401

    raw = request.get_data(as_text=True)
    log.info("RAW recibido: %s", raw)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        log.warning("Payload no es JSON: %s", raw)
        send_message(f"⚠️ Señal sin parsear:\n{raw}")
        return jsonify({"status": "ok", "parsed": False})

    # Telegram
    msg = format_signal(data)
    ok_tg = send_message(msg)
    log.info("Telegram enviado: %s", ok_tg)

    # Extraer campos — acepta "signal" o "action", y "buy"/"sell"
    action  = str(data.get("signal", data.get("action", ""))).lower()
    signal  = _ACTION.get(action, "")
    ticker  = str(data.get("ticker", "")).upper().strip()
    sl      = float(data.get("sl", 0) or 0)
    tp      = float(data.get("tp", 0) or 0)

    # position_size: >0 = entrada long, 0 = cierre, <0 = entrada short
    try:
        pos_size = float(data.get("position_size", 1) or 1)
    except (ValueError, TypeError):
        pos_size = 1.0

    mt5_result = {"success": False, "error": "sin señal de entrada válida"}

    if signal == "LONG" and ticker and pos_size > 0:
        log.info("Ejecutando LONG %s sl=%s tp=%s", ticker, sl, tp)
        mt5_result = execute_order(signal, ticker, sl, tp)
        log.info("MT5 resultado: %s", mt5_result)

    elif signal == "SHORT" and ticker and pos_size < 0:
        log.info("Ejecutando SHORT %s sl=%s tp=%s", ticker, sl, tp)
        mt5_result = execute_order(signal, ticker, sl, tp)
        log.info("MT5 resultado: %s", mt5_result)

    else:
        log.info("Señal ignorada (cierre o datos incompletos): signal=%s ticker=%s pos=%s",
                 signal, ticker, pos_size)
        mt5_result = {"success": False, "error": f"ignorado: signal={signal} pos={pos_size}"}

    return jsonify({"status": "ok", "telegram": ok_tg, "mt5": mt5_result})


@app.route("/ping", methods=["GET"])
def ping():
    return jsonify({"status": "running", "bot": "BVortex"})


if __name__ == "__main__":
    log.info("BVortex Bot arrancado en puerto %s", PORT)
    print(f"[BVortex Bot] Servidor arrancado en puerto {PORT}")
    print(f"[BVortex Bot] Webhook URL: http://localhost:{PORT}/webhook?secret={WEBHOOK_SECRET}")
    app.run(host="0.0.0.0", port=PORT)
