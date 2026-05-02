import json
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask, request, jsonify
from telegram_notifier import send_message, format_signal
from config import WEBHOOK_SECRET, PORT

app = Flask(__name__)


@app.route("/webhook", methods=["POST"])
def webhook():
    # Verificar secret en header o query param
    secret = request.args.get("secret") or request.headers.get("X-Secret", "")
    if secret != WEBHOOK_SECRET:
        return jsonify({"error": "unauthorized"}), 401

    # TradingView manda el body como texto plano (el mensaje de la alerta)
    raw = request.get_data(as_text=True)
    print(f"[Webhook] Recibido: {raw}")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # Si no es JSON válido, mandamos el texto tal cual
        send_message(f"⚠️ Señal recibida (sin parsear):\n{raw}")
        return jsonify({"status": "ok", "parsed": False})

    msg = format_signal(data)
    ok  = send_message(msg)
    print(f"[Telegram] Enviado: {ok}")

    return jsonify({"status": "ok", "telegram": ok})


@app.route("/ping", methods=["GET"])
def ping():
    return jsonify({"status": "running", "bot": "BVortex"})


if __name__ == "__main__":
    print(f"[BVortex Bot] Servidor arrancado en puerto {PORT}")
    print(f"[BVortex Bot] Webhook URL: http://localhost:{PORT}/webhook?secret={WEBHOOK_SECRET}")
    app.run(host="0.0.0.0", port=PORT)
