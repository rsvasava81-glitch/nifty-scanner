from datetime import datetime
import csv
import os
import pandas as pd
import requests

# Telegram Bot Token and Chat ID
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.getenv("CHAT_ID", "")

# રિસ્ક મેનેજમેન્ટ સેટિંગ્સ
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

message_report = "🚀 *ORB Trade Scanner & Levels Report*\n\n"

for idx in indices:
  data = get_live_index_data(idx["symbol"])
  if data:
    ltp = data["lastPrice"]
    high = data["high"]
    low = data["low"]

    # ORB Breakout Logic & Targets Calculation
    signal = "Neutral / Waiting"
    entry = ltp
    if ltp >= high:
      signal = "🟢 BULLISH BREAKOUT (BUY)"
      stop_loss = low
      risk = entry - stop_loss
      target = entry + (risk * RISK_REWARD_RATIO)
    elif ltp <= low:
      signal = "🔴 BEARISH BREAKOUT (SELL)"
      stop_loss = high
      risk = stop_loss - entry
      target = entry - (risk * RISK_REWARD_RATIO)
    else:
      stop_loss = low
      target = high

    msg = (
        f"*{idx['name']}* | Status: {signal}\n"
        f"• *Spot Price:* `{ltp}`\n"
        f"• *ORB High:* `{high}` | *ORB Low:* `{low}`\n"
        f"• *Entry:* `{entry:.2f}`\n"
        f"• *Stop Loss:* `{stop_loss:.2f}`\n"
        f"• *Target (2:1):* `{target:.2f}`\n\n"
    )
    message_report += msg
  else:
    print(f"Error for {idx['name']}: Could not fetch live data")

# ટેલિગ્રામ પર કમ્પ્લીટ રિપોર્ટ મોકલવા માટે
send_telegram_alert(message_report)
print("ORB Scanner report sent successfully to Telegram!")
