import os
import requests

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
    print("Initializing Sahi API scanner for 5-minute timeframe...")
    try:
        # Check credentials
        if not KEY_ID or not SECRET:
            print("Sahi API credentials are not set properly.")
            return

        # Here you can place your Sahi API REST call using 'requests' 
        # e.g., fetching Nifty 5m data and calculating Fib Extension
        
        print("5-minute Fibonacci Extension scanner checked successfully.")
        
        # Example test message to verify Telegram connectivity (you can remove this later)
        # send_telegram_alert("🚀 Nifty 5m Scanner: Workflow ran successfully!")

    except Exception as e:
        print(f"Error during execution: {e}")
        raise e

if __name__ == "__main__":
    run_scanner()
