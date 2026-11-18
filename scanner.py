import os
import requests
from sahiapi import SahiAPI

# --- 1. CREDENTIALS (GitHub Secrets) ---
KEY_ID = os.getenv("SAHI_KEY_ID")
SECRET = os.getenv("SAHI_SECRET")

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# --- 2. TELEGRAM ALERT FUNCTION ---
def send_telegram_alert(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        print("Telegram alert sent successfully!")
    else:
        print("Telegram Error:", response.text)

# --- 3. SAHI API CONNECTION ---
api = SahiAPI.from_credentials(key_id=KEY_ID, secret=SECRET)

# Scan karva mate na NSE & BSE Indices
INDICES = [
    {"name": "NIFTY 50", "symbol": "NIFTY", "segment": SahiAPI.EXCHANGE_SEGMENT_NSE},
    {"name": "BANK NIFTY", "symbol": "BANKNIFTY", "segment": SahiAPI.EXCHANGE_SEGMENT_NSE},
    {"name": "FIN NIFTY", "symbol": "FINNIFTY", "segment": SahiAPI.EXCHANGE_SEGMENT_NSE},
    {"name": "MIDCAP NIFTY", "symbol": "MIDCPNIFTY", "segment": SahiAPI.EXCHANGE_SEGMENT_NSE},
    {"name": "SENSEX", "symbol": "SENSEX", "segment": SahiAPI.EXCHANGE_SEGMENT_BSE},
]

# --- 4. FIBONACCI TREND EXTENSION STRATEGY LOGIC ---
def check_fib_extension(ltp, high, low):
    diff = high - low
    if diff <= 0:
        return None

    # Fibonacci Extension & Retracement levels
    ext_1_618 = round(high + (diff * 1.618), 2)
    retracement_0_618 = round(high - (diff * 0.618), 2)

    # Signal Logic: Jo price day's high break kare to Bullish Fibonacci Extension target
    if ltp >= high:
        return {
            "direction": "BULLISH (CE)",
            "entry": ltp,
            "sl": retracement_0_618,
            "target": ext_1_618
        }
    return None

# --- 5. MAIN SCANNER FUNCTION ---
def scan_market():
    for item in INDICES:
        try:
            # Instrument ID find karo
            inst = api.get_instruments_by_symbol(item["symbol"], item["segment"])[0]
            inst_id = inst["id"]

            # Live Quote (LTP, High, Low) fetch karo
            quote = api.get_quotes(inst_id)["data"][str(inst_id)]
            ltp = quote["last_trade_price"] / 100
            day_high = quote.get("high", ltp * 100) / 100
            day_low = quote.get("low", ltp * 100) / 100

            print(f"{item['name']} -> LTP: {ltp} | High: {day_high} | Low: {day_low}")

            # Fibonacci Extension Strategy Check karo
            signal = check_fib_extension(ltp, day_high, day_low)

            if signal:
                msg = (
                    f"🚀 *FIB EXTENSION ALERT: {item['name']}*\n\n"
                    f"📈 *Direction:* {signal['direction']}\n"
                    f"💰 *Entry:* `{signal['entry']}`\n"
                    f"🛑 *Stop Loss (0.618 Ret.):* `{signal['sl']}`\n"
                    f"🎯 *Target (1.618 Ext.):* `{signal['target']}`"
                )
                send_telegram_alert(msg)

        except Exception as e:
            print(f"Error scanning {item['name']}: {e}")

if __name__ == "__main__":
    scan_market()
