import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN   = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
WEBHOOK_SECRET   = os.getenv("WEBHOOK_SECRET", "bvortex2024")
PORT             = int(os.getenv("PORT", 5000))

MT5_LOGIN        = int(os.getenv("MT5_LOGIN", 0))
MT5_PASSWORD     = os.getenv("MT5_PASSWORD", "")
MT5_SERVER       = os.getenv("MT5_SERVER", "")
LOT_SIZE         = float(os.getenv("LOT_SIZE", 0.01))
