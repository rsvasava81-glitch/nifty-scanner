from datetime import datetime
import os
import time
import pandas as pd
import requests

# Telegram Bot Token and Chat ID
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.getenv("CHAT_ID", "")

# રિસ્ક મેનેજમેન્ટ સેટિંગ્સ
RISK_REWARD_RATIO = 2.0


def send_telegram_alert(message):
  url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
  payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
  try:
    response = requests.post(url, json=payload)
    return response.json()
  except Exception as e:
    print(f"Telegram alert error: {e}")


def get_nse_session():
  """NSE સાઈટ પરથી કૂકી મેળવીને સેશન સેટ કરવા માટેનું ફંક્શન"""
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
  except Exception as e:
    print(f"Session creation error: {e}")
  return session


def get_advanced_market_signals():
  session = get_nse_session()
  url = "https://www.nseindia.com/api/allIndices"

  try:
    response = session.get(url, timeout=10)
    if response.status_code == 200:
      data = response.json()
      signals = []

      for index in data.get("data", []):
        symbol = index.get("indexSymbol")
        # મુખ્ય પાંચ ઇન્ડેક્સને ટ્રેક કરવા
        target_symbols = [
            "NIFTY 50",
            "NIFTY BANK",
            "NIFTY FIN SERVICE",
            "NIFTY MIDSELECT",
            "SENSEX",
        ]

        if symbol in target_symbols:
          name = index.get("symbol", symbol)
          ltp = float(index.get("last", 0))
          open_p = float(index.get("open", 0))
          high = float(index.get("high", 0))
          low = float(index.get("low", 0))
          prev_close = float(index.get("previousClose", 0))

          # મલ્ટી-ટાઈમફ્રેમ લિક્વિડિટી હન્ટિંગ અને રિવર્સલ લોજિક
          # જો પ્રાઈસ ડેઇલી/વન-અવર રેન્જની બહાર જઈને પાછી ફરે (False Breakout / Liquidity Sweep)
          signal_type = "⏳ Waiting for Liquidity Sweep"
          entry = ltp
          stop_loss = 0
          target = 0

          # ઉદાહરણ તરીકે: જો પ્રાઈસ લો તોડીને પાછી ઉપર આવે (Bullish Sweep / Liquidity Hunt)
          if ltp > low and ltp <= (low + (high - low) * 0.15):
            signal_type = (
                "🟢 BULLISH LIQUIDITY HUNT (BUY) - Support Reversal"
            )
            stop_loss = (
                low - 15
            )  # એકદમ નાનો ટાઈટ એસ.એલ. (લક્ષ્યાંક મુજબ કસ્ટમાઇઝ કરી શકાય)
            risk = entry - stop_loss
            target = entry + (risk * RISK_REWARD_RATIO)

          # જો પ્રાઈસ હાઈ તોડીને પાછી નીચે જાય (Bearish Sweep / Liquidity Hunt)
          elif ltp < high and ltp >= (high - (high - low) * 0.15):
            signal_type = "🔴 BEARISH LIQUIDITY HUNT (SELL) - Resistance Reversal"
            stop_loss = (
                high + 15
            )  # એકદમ નાનો ટાઈટ એસ.એલ. (લક્ષ્યાંક મુજબ કસ્ટમાઇઝ કરી શકાય)
            risk = stop_loss - entry
            target = entry - (risk * RISK_REWARD_RATIO)
          else:
            # ડિફોલ્ટ ORB લેવલ્સ જો હન્ટિંગ ન થયું હોય
            stop_loss = low
            target = high

          signals.append({
              "name": name,
              "ltp": ltp,
              "high": high,
              "low": low,
              "signal": signal_type,
              "entry": entry,
              "sl": stop_loss,
              "target": target,
          })
      return signals
  except Exception as e:
    print(f"Error fetching index data: {e}")
  return []


# Main Execution
print("--- Advanced Liquidity Hunting & Tight SL Scanner Started ---")
market_data = get_advanced_market_signals()

if market_data:
  message_report = (
      "🎯 *Advanced Liquidity Hunting & Tight SL Report*\n\n"
  )

  for item in market_data:
    msg = (
        f"*{item['name']}*\n"
        f"• *Status:* {item['signal']}\n"
        f"• *Spot Price:* `{item['ltp']}`\n"
        f"• *Daily/1H High:* `{item['high']}` | *Low:* `{item['low']}`\n"
        f"• *Entry:* `{item['entry']:.2f}`\n"
        f"• *Tight Stop Loss:* `{item['sl']:.2f}`\n"
        f"• *Target (2:1):* `{item['target']:.2f}`\n\n"
    )
    message_report += msg

  # ટેલિગ્રામ પર એલર્ટ મોકલવું
  send_telegram_alert(message_report)
  print("Advanced Liquidity scan report sent successfully to Telegram!")
else:
  print("No market data fetched.")
