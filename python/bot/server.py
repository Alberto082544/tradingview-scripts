import json
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask, request, jsonify
from telegram_notifier import send_message, format_signal
from mt5_handler import execute_order
from config import WEBHOOK_SECRET, PORT

app = Flask(__name__)


@app.route("/webhook", methods=["POST"])
def webhook():
    secret = request.args.get("secret") or request.headers.get("X-Secret", "")
    if secret != WEBHOOK_SECRET:
        return jsonify({"error": "unauthorized"}), 401

    raw = request.get_data(as_text=True)
    print(f"[Webhook] Recibido: {raw}")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        send_message(f"⚠️ Señal recibida (sin parsear):\n{raw}")
        return jsonify({"status": "ok", "parsed": False})

    # 1) Telegram
    msg = format_signal(data)
    ok_tg = send_message(msg)
    print(f"[Telegram] Enviado: {ok_tg}")

    # 2) MT5
    signal = data.get("signal", "")
    ticker = data.get("ticker", "")
    sl     = data.get("sl", 0)
    tp     = data.get("tp", 0)

    mt5_result = {"success": False, "error": "sin datos"}
    if signal in ("LONG", "SHORT") and ticker and sl and tp:
        mt5_result = execute_order(signal, ticker, float(sl), float(tp))
        print(f"[MT5] {mt5_result}")

    return jsonify({"status": "ok", "telegram": ok_tg, "mt5": mt5_result})


@app.route("/ping", methods=["GET"])
def ping():
    return jsonify({"status": "running", "bot": "BVortex"})


if __name__ == "__main__":
    print(f"[BVortex Bot] Servidor arrancado en puerto {PORT}")
    print(f"[BVortex Bot] Webhook URL: http://localhost:{PORT}/webhook?secret={WEBHOOK_SECRET}")
    app.run(host="0.0.0.0", port=PORT)
