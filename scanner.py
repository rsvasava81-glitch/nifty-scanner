import os
import requests
import time

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

def calculate_fib_and_targets(swing_low, swing_high_reference, current_close_price, is_uptrend=True):
    fib_range = abs(swing_high_reference - swing_low)
    levels = {}
    
    if is_uptrend:
        levels['0.0']   = swing_low
        levels['0.382'] = swing_low + (fib_range * 0.382)
        levels['0.5']   = swing_low + (fib_range * 0.5)
        levels['0.618'] = swing_low + (fib_range * 0.618)
        levels['1.0']   = swing_high_reference
        levels['1.414'] = swing_low + (fib_range * 1.414)
        levels['1.618'] = swing_low + (fib_range * 1.618)
        levels['2.0']   = swing_low + (fib_range * 2.0)
        levels['2.272'] = swing_low + (fib_range * 2.272)
        levels['2.618'] = swing_low + (fib_range * 2.618)
    else:
        levels['0.0']   = swing_high_reference
        levels['0.382'] = swing_high_reference - (fib_range * 0.382)
        levels['0.5']   = swing_high_reference - (fib_range * 0.5)
        levels['0.618'] = swing_high_reference - (fib_range * 0.618)
        levels['1.0']   = swing_low

    active_target = None
    next_target = None
    
    sorted_levels = sorted(levels.items(), key=lambda x: x[1])
    
    for i, (level_name, price) in enumerate(sorted_levels):
        if current_close_price >= price:
            active_target = level_name
            if i + 1 < len(sorted_levels):
                next_target = sorted_levels[i + 1][0]
            else:
                next_target = "All Targets Achieved!"
                
    return levels, active_target, next_target

def main():
    # --- NSE ane BSE F&O Indices Watchlist ---
    indices_watchlist = [
        {"name": "NIFTY 50 (NSE)", "high": 25214.68, "low": 25141.80, "close": 25236.49, "uptrend": True},
        {"name": "BANKNIFTY (NSE)", "high": 51500.00, "low": 51200.00, "close": 51350.00, "uptrend": True},
        {"name": "FINNIFTY (NSE)", "high": 23400.00, "low": 23250.00, "close": 23320.00, "uptrend": True},
        {"name": "MIDCAP NIFTY (NSE)", "high": 12500.00, "low": 12400.00, "close": 12460.00, "uptrend": True},
        {"name": "SENSEX (BSE)", "high": 82500.00, "low": 82000.00, "close": 82250.00, "uptrend": True}
    ]
    
    for item in indices_watchlist:
        symbol_name = item["name"]
        swing_high_ref = item["high"]
        swing_low = item["low"]
        current_close = item["close"]
        uptrend_status = item["uptrend"]
        
        levels, achieved, upcoming = calculate_fib_and_targets(
            swing_low, swing_high_ref, current_close, is_uptrend=uptrend_status
        )
        
        # Telegram Message Formatting
        msg = (
            f"🚀 *F&O Target Update: {symbol_name}*\n"
            f"-----------------------------------\n"
            f"📌 *High:* `{swing_high_ref}` | *Low:* `{swing_low}`\n"
            f"✅ Achieved Level: *{achieved}*\n"
            f"🎯 Next Active Target: *{upcoming}*\n"
            f"📈 Current Candle Close: `{current_close}`"
        )
        
        send_telegram_alert(msg)
        time.sleep(1) # Telegram API spam limit avoid karva mate

if __name__ == "__main__":
    main()
