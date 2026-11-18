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

def calculate_perfect_trade_setup(swing_low, swing_high_reference, current_close_price, is_uptrend=True):
    fib_range = abs(swing_high_reference - swing_low)
    levels = {}
    
    if is_uptrend:
        trade_type = "🟢 CALL (CE) SIDE ENTRY"
        stop_loss = swing_low
        
        # Exact Fibonacci & Extension Levels Calculation
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
        
        # Target Progression based on Candle Close
        if current_close_price >= levels['2.618']:
            achieved, next_target = '2.618', 'All Targets Achieved! (Wait for New Swing)'
        elif current_close_price >= levels['2.272']:
            achieved, next_target = '2.272', f'{levels["2.618"]:.2f} (T4)'
        elif current_close_price >= levels['2.0']:
            achieved, next_target = '2.0', f'{levels["2.272"]:.2f} (T3)'
        elif current_close_price >= levels['1.618']:
            achieved, next_target = '1.618', f'{levels["2.0"]:.2f} & {levels["2.272"]:.2f} (T2)'
        elif current_close_price >= levels['1.414']:
            achieved, next_target = '1.414', f'{levels["1.618"]:.2f} (T1)'
        elif current_close_price >= levels['1.0']:
            achieved, next_target = '1.0 (High)', f'{levels["1.414"]:.2f} (Next Target)'
        elif current_close_price >= levels['0.618']:
            achieved, next_target = '0.618', f'{levels["1.414"]:.2f} (Next Target)'
        else:
            achieved, next_target = 'Retracement Zone', f'{levels["1.0"]:.2f}'
            
    else:
        trade_type = "🔴 PUT (PE) SIDE ENTRY"
        stop_loss = swing_high_reference
        
        levels['0.0']   = swing_high_reference
        levels['0.382'] = swing_high_reference - (fib_range * 0.382)
        levels['0.5']   = swing_high_reference - (fib_range * 0.5)
        levels['0.618'] = swing_high_reference - (fib_range * 0.618)
        levels['1.0']   = swing_low
        levels['1.414'] = swing_high_reference - (fib_range * 1.414)
        levels['1.618'] = swing_high_reference - (fib_range * 1.618)
        levels['2.0']   = swing_high_reference - (fib_range * 2.0)
        levels['2.272'] = swing_high_reference - (fib_range * 2.272)
        levels['2.618'] = swing_high_reference - (fib_range * 2.618)
        
        if current_close_price <= levels['2.618']:
            achieved, next_target = '2.618', 'All Targets Achieved! (Wait for New Swing)'
        elif current_close_price <= levels['2.272']:
            achieved, next_target = '2.272', f'{levels["2.618"]:.2f}'
        elif current_close_price <= levels['2.0']:
            achieved, next_target = '2.0', f'{levels["2.272"]:.2f}'
        elif current_close_price <= levels['1.618']:
            achieved, next_target = '1.618', f'{levels["2.0"]:.2f}'
        elif current_close_price <= levels['1.414']:
            achieved, next_target = '1.414', f'{levels["1.618"]:.2f}'
        else:
            achieved, next_target = 'Retracement Zone', f'{levels["1.414"]:.2f}'

    return trade_type, stop_loss, achieved, next_target, levels

def main():
    # Watchlist for NSE & BSE F&O Indices
    indices_watchlist = [
        {"name": "NIFTY 50 (NSE)", "high": 25214.27, "low": 25141.80, "close": 25216.50, "uptrend": True},
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
        
        trade_type, sl, achieved, target, lvl = calculate_perfect_trade_setup(
            swing_low, swing_high_ref, current_close, is_uptrend=uptrend_status
        )
        
        # Clean & Perfect Telegram Alert Format
        msg = (
            f"🎯 *F&O Trade Setup: {symbol_name}*\n"
            f"-----------------------------------\n"
            f"{trade_type}\n"
            f"📌 *High:* `{swing_high_ref}` | *Low:* `{swing_low}`\n"
            f"📥 *Candle Close:* `{current_close}`\n"
            f"🛑 *Stop Loss (SL):* `{sl}`\n"
            f"✅ *Achieved Level:* `{achieved}`\n"
            f"🎯 *Next Target:* `{target}`"
        )
        
        send_telegram_alert(msg)
        time.sleep(1)

if __name__ == "__main__":
    main()
