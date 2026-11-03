from datetime import datetime
import csv
import os
import pandas as pd
import requests

# Telegram Bot Token and Chat ID
TELEGRAM_BOT_TOKEN = os.getenv(
    "TELEGRAM_BOT_TOKEN", "8881124725:AAHAF8SGGMkplIUPoRu JrGS3O099aP1w"
)
CHAT_ID = os.getenv("CHAT_ID", "/161195228")

MAX_LOSS_PER_TRADE = 1000
RISK_REWARD_RATIO = 2.0


def send_telegram_alert(message):
  url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
  payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
  try:
    response = requests.post(url, json=payload)
    return response.json()
  except Exception as e:
    print(f"Telegram alert error: {e}")


def get_live_index_data(symbol):
  """NSE ની ઓપન પબ્લિક એપીઆઈમાંથી લાઈવ સ્પોટ પ્રાઈસ ફેચ કરવાનું ફંક્શન"""
  headers = {
      "User-Agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
          " like Gecko) Chrome/120.0.0.0 Safari/537.36"
      ),
      "Accept": "*/*",
      "Accept-Language": "en-US,en;q=0.9",
  }
  session = requests.Session()
  session.headers.update(headers)
  try:
    session.get("https://www.nseindia.com", timeout=10)
    url = "https://www.nseindia.com/api/allIndices"
    response = session.get(url, timeout=10)
    if response.status_code == 200:
      data = response.json()
      for index in data.get("data", []):
        if index.get("indexSymbol") == symbol:
          return {
              "lastPrice": float(index.get("last", 0)),
              "open": float(index.get("open", 0)),
              "high": float(index.get("high", 0)),
              "low": float(index.get("low", 0)),
              "previousClose": float(index.get("previousClose", 0)),
          }
  except Exception as e:
    print(f"Error for {symbol}: {e}")
  return None


# Main Execution
print("--- GitHub Actions Market Breakout Scanner Started ---")

indices = [
    {"name": "NIFTY 50", "symbol": "NIFTY 50"},
    {"name": "BANK NIFTY", "symbol": "NIFTY BANK"},
    {"name": "FIN NIFTY", "symbol": "NIFTY FIN SERVICE"},
    {"name": "MIDCAP NIFTY", "symbol": "NIFTY MIDSELECT"},
    {"name": "SENSEX", "symbol": "SENSEX"},
]

message_report = "🚀 *Live Market Scanner Test Report*\n\n"

for idx in indices:
  data = get_live_index_data(idx["symbol"])
  if data:
    msg = (
        f"*{idx['name']}*\nPrice: `{data['lastPrice']}`\nHigh: `{data['high']}` |"
        f" Low: `{data['low']}`\n\n"
    )
    print(f"Live {idx['name']} Price: {data['lastPrice']}")
    message_report += msg
  else:
    print(f"Error for {idx['name']}: Could not fetch live data")

# ટેલિગ્રામ પર મેસેજ મોકલવા માટે
send_telegram_alert(message_report)
print("Telegram alert sent successfully!")
