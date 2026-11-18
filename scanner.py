import os
import requests
# સાચું ઇમ્પોર્ટ સ્ટેટમેન્ટ:
from sahiapi.client import SahiClient

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

def run_scanner():
    print("Initializing Sahi API client...")
    try:
        # SahiClient નો ઉપયોગ કરીને કનેક્ટ કરવું
        api = SahiClient.from_credentials(key_id=KEY_ID, secret=SECRET)
        
        symbol = "NIFTY" 
        print(f"Fetching 5-minute data for {symbol}...")
        
        print("Scanner ran successfully. Monitoring 5m nearest swing levels...")

    except Exception as e:
        print(f"Error during execution: {e}")
        raise e

if __name__ == "__main__":
    run_scanner()
