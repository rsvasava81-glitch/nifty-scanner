import pandas as pd
import requests


def get_live_index_data(symbol):
    """NSE ની ઓપન પબ્લિક એપીઆઈમાંથી લાઈવ સ્પોટ પ્રાઈસ ફેચ કરવાનું ફંક્શન"""
    # NSE રિક્વેસ્ટ માટે જરૂરી હેડર્સ
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            " (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
    }

    session = requests.Session()
    session.headers.update(headers)

    try:
        # NSE કૂકીઝ મેળવવા માટે પહેલા હોમપેજ હિટ કરવું પડે છે
        session.get("https://www.nseindia.com", timeout=10)

        # ઇન્ડેક્સ ડેટા એન્ડપોઇન્ટ
        url = "https://www.nseindia.com/api/allIndices"
        response = session.get(url, timeout=10)

        if response.status_code == 200:
            data = response.json()
            for index in data.get("data", []):
                if index.get("indexSymbol") == symbol:
                    # લાઈવ ડેટા રીટર્ન કરશે
                    return {
                        "lastPrice": index.get("last"),
                        "open": index.get("open"),
                        "high": index.get("high"),
                        "low": index.get("low"),
                        "previousClose": index.get("previousClose"),
                    }
    except Exception as e:
        print(f"NSE API ડેટા ફેચ કરવામાં ભૂલ: {e}")

    return None


# ઉદાહરણ તરીકે NIFTY 50 નો લાઈવ ડેટા મેળવવો:
# symbol ઓપ્શન્સ: 'NIFTY 50', 'NIFTY BANK', 'NIFTY FIN SERVICE', 'NIFTY MIDSELECT'
live_data = get_live_index_data("NIFTY 50")
if live_data:
    print(f"Live NIFTY 50 Price: {live_data['lastPrice']}") yf
import requests
import os
import csv
from datetime import datetime

# Telegram Bot Token ane Chat ID
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8883124725:AAHAF8SGg3MkpliUPoBcJr8S30mlBQ15K9w")  
CHAT_ID = os.getenv("CHAT_ID", "7161195228")                

MAX_LOSS_PER_TRADE = 1000  
RISK_REWARD_RATIO = 2.0    

def send_telegram_alert(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        }
        response = requests.post(url, json=payload)
        return response.json()
    except Exception as e:
        print("Telegram Error:", e)

def log_trade_to_csv(index_name, action, entry, target, stop_loss, lots):
    file_exists = os.path.isfile("trade_log.csv")
    try:
        with open("trade_log.csv", mode="a", newline="") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["Timestamp", "Index", "Action", "Entry", "Target", "StopLoss", "Lots"])
            
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            writer.writerow([current_time, index_name, action, entry, target, stop_loss, lots])
        print(f"Trade logged successfully for {index_name}")
    except Exception as e:
        print("CSV Logging Error:", e)

indices = {
    "NIFTY 50": {"symbol": "^NSEI", "lot_size": 25},
    "BANK NIFTY": {"symbol": "^NSEBANK", "lot_size": 15},
    "FIN NIFTY": {"symbol": "NIFTY_FIN_SERVICE.NS", "lot_size": 25},
    "MIDCAP NIFTY": {"symbol": "^NSEMDCP50", "lot_size": 50},
    "SENSEX": {"symbol": "^BSESN", "lot_size": 10}
}

print("--- GitHub Actions Market Breakout Scanner Started ---")

for name, info in indices.items():
    try:
        data = yf.Ticker(info["symbol"])
        df = data.history(period="1d", interval="5m")
        
        if not df.empty:
            current_price = df['Close'].iloc[-1]
            high_price = df['High'].max()
            low_price = df['High'].min()
            
            print(f"\n[ {name} ] Price: {current_price:.2f} | High: {high_price:.2f}")
            
            if current_price >= high_price:
                entry = current_price
                stop_loss = low_price  
                risk_per_share = entry - stop_loss
                
                if risk_per_share > 0:
                    shares_or_qty = MAX_LOSS_PER_TRADE / risk_per_share
                    lots = max(1, round(shares_or_qty / info["lot_size"]))
                    target = entry + (risk_per_share * RISK_REWARD_RATIO)
                    
                    alert_msg = (
                        f"🚨 *BULLISH BREAKOUT & RISK PLAN* 🚨\n\n"
                        f"📊 Index: *{name}*\n"
                        f"🟢 Action: *BUY CE*\n"
                        f"📍 Entry: *₹{entry:.2f}*\n"
                        f"🎯 Target (1:2): *₹{target:.2f}*\n"
                        f"🔴 Stop Loss: *₹{stop_loss:.2f}*\n"
                        f"📦 Recommended Lots: *{lots} Lot(s)*\n"
                        f"💰 Max Risk: *₹{MAX_LOSS_PER_TRADE}*"
                    )
                    print(f"ALERT SENT FOR {name}")
                    send_telegram_alert(alert_msg)
                    log_trade_to_csv(name, "BUY CE", round(entry, 2), round(target, 2), round(stop_loss, 2), lots)
                        
            elif current_price <= low_price:
                entry = current_price
                stop_loss = high_price
                risk_per_share = stop_loss - entry
                
                if risk_per_share > 0:
                    shares_or_qty = MAX_LOSS_PER_TRADE / risk_per_share
                    lots = max(1, round(shares_or_qty / info["lot_size"]))
                    target = entry - (risk_per_share * RISK_REWARD_RATIO)
                    
                    alert_msg = (
                        f"🚨 *BEARISH BREAKDOWN & RISK PLAN* 🚨\n\n"
                        f"📊 Index: *{name}*\n"
                        f"🔴 Action: *BUY PE*\n"
                        f"📍 Entry: *₹{entry:.2f}*\n"
                        f"🎯 Target (1:2): *₹{target:.2f}*\n"
                        f"🟢 Stop Loss: *₹{stop_loss:.2f}*\n"
                        f"📦 Recommended Lots: *{lots} Lot(s)*\n"
                        f"💰 Max Risk: *₹{MAX_LOSS_PER_TRADE}*"
                    )
                    print(f"ALERT SENT FOR {name}")
                    send_telegram_alert(alert_msg)
                    log_trade_to_csv(name, "BUY PE", round(entry, 2), round(target, 2), round(stop_loss, 2), lots)
            else:
                print("Status: Trading inside range.")
                
    except Exception as e:
        print(f"Error for {name}: {e}")
