import requests
from config import ALPACA_API_KEY, ALPACA_SECRET_KEY

BASE = "https://paper-api.alpaca.markets"
HEADERS = {
    "APCA-API-KEY-ID": ALPACA_API_KEY,
    "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY
}

try:
    r = requests.get(f"{BASE}/v2/account", headers=HEADERS, timeout=10)
    data = r.json()
    print("Status:       ", data.get("status"))
    print("Buying Power: ", data.get("buying_power"))
    print("Equity:       ", data.get("equity"))
except Exception as e:
    print("[ALPACA ERROR]", e)
