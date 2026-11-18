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
    swing_low = 25141.80        
    swing_high_ref = 25214.68   
    current_close = 25236.49    
    uptrend_status = True       
    
    levels, achieved, upcoming = calculate_fib_and_targets(
        swing_low, swing_high_ref, current_close, is_uptrend=uptrend_status
    )
    
    msg = (
        f"🚀 *F&O Target Update*\n"
        f"-----------------------------------\n"
        f"📌 *High:* `{swing_high_ref}` | *Low:* `{swing_low}`\n"
        f"✅ Achieved Level: *{achieved}*\n"
        f"🎯 Next Active Target: *{upcoming}*\n"
        f"📈 Current Candle Close: `{current_close}`"
    )
    
    send_telegram_alert(msg)

if __name__ == "__main__":
    main()
