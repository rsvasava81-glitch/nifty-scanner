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

def calculate_fib_and_targets(high, low, current_close_price, is_uptrend=True):
    """
    Calculates Fibonacci levels accurately based on trend direction,
    and checks candle close to activate the next upper target.
    """
    fib_range = abs(high - low)
    levels = {}
    
    # Correct Fibonacci & Extension Calculation based on Trend
    if is_uptrend:
        # Market upar jatu hoy tyare (Low thi High)
        levels['0.0'] = low
        levels['0.382'] = low + (fib_range * 0.382)
        levels['0.5']   = low + (fib_range * 0.5)
        levels['0.618'] = low + (fib_range * 0.618)
        levels['1.0']   = high
        levels['1.414'] = low + (fib_range * 1.414)
        levels['1.618'] = low + (fib_range * 1.618)
        levels['2.0']   = low + (fib_range * 2.0)
    else:
        # Market niche padtu hoy tyare (High thi Low)
        levels['0.0'] = high
        levels['0.382'] = high - (fib_range * 0.382)
        levels['0.5']   = high - (fib_range * 0.5)
        levels['0.618'] = high - (fib_range * 0.618)
        levels['1.0']   = low
        levels['1.414'] = high - (fib_range * 1.414)
        levels['1.618'] = high - (fib_range * 1.618)
        levels['2.0']   = high - (fib_range * 2.0)

    # Dynamic Target Activation (Candle Close Check)
    active_target = None
    next_target = None
    
    # Sort levels by price ascending
    sorted_levels = sorted(levels.items(), key=lambda x: x[1])
    
    for i, (level_name, price) in enumerate(sorted_levels):
        if current_close_price >= price:
            active_target = level_name
            # Jyare target ni upar close aape tyare agal no target active thase
            if i + 1 < len(sorted_levels):
                next_target = sorted_levels[i + 1][0]
            else:
                next_target = "All Targets Achieved!"
                
    return levels, active_target, next_target

def main():
    # --- Live Market Integration Example (Tamara Sahi API data sathe connect karo) ---
    # Example values for testing:
    swing_high = 25250.00
    swing_low = 25141.35
    current_close = 25241.00  # Live candle close price
    uptrend_status = True     # True for bounce/uptrend, False for downtrend
    
    levels, achieved, upcoming = calculate_fib_and_targets(
        swing_high, swing_low, current_close, is_uptrend=uptrend_status
    )
    
    # Message formatting for Telegram
    msg = (
        f"🚨 *F&O Fibonacci Signal Update*\n"
        f"-----------------------------------\n"
        f"✅ Achieved Target / Level: *{achieved}*\n"
        f"🎯 Next Active Target: *{upcoming}*\n"
        f"📈 Current Candle Close: `{current_close}`"
    )
    
    send_telegram_alert(msg)

if __name__ == "__main__":
    main()
