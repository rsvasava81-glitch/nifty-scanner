import yfinance as yf
import requests
import os

# Telegram Bot Token ane Chat ID (Environment variables athva direct ahiya)
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
            else:
                print("Status: Trading inside range.")
                
    except Exception as e:
        print(f"Error for {name}: {e}")