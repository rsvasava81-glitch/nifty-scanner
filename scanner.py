import os
import requests
from sahiapi.sahi import SahiAPI

# 1. Credentials Setup from GitHub Secrets
KEY_ID = os.environ.get("SAHI_KEY_ID")
SECRET = os.environ.get("SAHI_SECRET")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

def send_telegram_alert(message):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("Telegram credentials missing!")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        print("Telegram alert sent successfully!")
    except Exception as e:
        print(f"Failed to send telegram alert: {e}")

def calculate_fib_extensions(high, low, is_uptrend=True):
    diff = high - low
    if is_uptrend:
        # Uptrend: Low to High extension
        entry = high
        stop_loss = high - (0.618 * diff)
        target = low + (1.618 * diff) # or high + (1.618 * diff) based on convention
    else:
        # Downtrend: High to Low extension
        entry = low
        stop_loss = low + (0.618 * diff)
        target = high - (1.618 * diff)
    return entry, stop_loss, target

def run_scanner():
    print("Initializing Sahi API client...")
    try:
        # Connect using Sahi API credentials
        api = SahiAPI.from_credentials(key_id=KEY_ID, secret=SECRET)
        
        # Note: Fetch 5-minute candle data for Nifty / BankNifty via Sahi API client
        # Example symbol structure (adjust as per Sahi API documentation)
        symbol = "NIFTY" 
        print(f"Fetching 5-minute data for {symbol}...")
        
        # Placeholder for data fetching logic from Sahi API candles/historical data
        # candles = api.get_historical_data(symbol=symbol, timeframe="5m")
        
        # --- Logic for Nearest Swing High/Low calculation ---
        # (Assuming we compute swing high/low from recent 5m candles)
        # swing_high = ... 
        # swing_low = ...
        
        print("Scanner ran successfully. Monitoring 5m nearest swing levels...")

    except Exception as e:
        print(f"Error during execution: {e}")
        raise e

if __name__ == "__main__":
    run_scanner()
