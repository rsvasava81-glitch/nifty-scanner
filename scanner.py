import os
import requests
import pandas as pd
import numpy as np
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

def detect_swings(highs, lows, window=5):
    """
    Automatic Pivot Swing Detection for Internal / Outside Swings.
    """
    high_series = pd.Series(highs)
    low_series = pd.Series(lows)
    
    # Find rolling local maxima and minima
    rolling_max = high_series.rolling(window=2*window+1, center=True).max()
    rolling_min = low_series.rolling(window=2*window+1, center=True).min()
    
    swing_highs = high_series[high_series == rolling_max].dropna()
    swing_lows = low_series[low_series == rolling_min].dropna()
    
    # Get the latest significant swing points
    latest_high = swing_highs.iloc[-1] if not swing_highs.empty else highs[-1]
    latest_low = swing_lows.iloc[-1] if not swing_lows.empty else lows[-1]
    
    return latest_low, latest_high

def calculate_dynamic_fib_setup(df_candles, window=5):
    """
    Calculates Trend-Based Fibonacci Extension automatically using detected swings.
    """
    highs = df_candles['High'].values
    lows = df_candles['Low'].values
    closes = df_candles['Close'].values
    
    current_close = closes[-1]
    swing_low, swing_high = detect_swings(highs, lows, window=window)
    
    # Determine Trend Direction (Uptrend if Low occurred before High in recent context)
    is_uptrend = swing_low < swing_high
    fib_range = abs(swing_high - swing_low)
    levels = {}
    
    if is_uptrend:
        trade_type = "🟢 CALL (CE) SIDE ENTRY"
        stop_loss = swing_low
        
        levels['0.0']   = swing_low
        levels['0.382'] = swing_low + (fib_range * 0.382)
        levels['0.5']   = swing_low + (fib_range * 0.5)
        levels['0.618'] = swing_low + (fib_range * 0.618)
        levels['1.0']   = swing_high
        levels['1.414'] = swing_low + (fib_range * 1.414)
        levels['1.618'] = swing_low + (fib_range * 1.618)
        levels['2.0']   = swing_low + (fib_range * 2.0)
        levels['2.272'] = swing_low + (fib_range * 2.272)
        levels['2.618'] = swing_low + (fib_range * 2.618)
        
        # Target Progression based on Candle Close
        if current_close >= levels['2.618']:
            achieved, target = '2.618', 'All Targets Achieved! (Wait for New Swing)'
        elif current_close >= levels['2.272']:
            achieved, target = '2.272', f'{levels["2.618"]:.2f} (T4)'
        elif current_close >= levels['2.0']:
            achieved, target = '2.0', f'{levels["2.272"]:.2f} (T3)'
        elif current_close >= levels['1.618']:
            achieved, target = '1.618', f'{levels["2.0"]:.2f} & {levels["2.272"]:.2f} (T2)'
        elif current_close >= levels['1.414']:
            achieved, target = '1.414', f'{levels["1.618"]:.2f} (T1)'
        elif current_close >= levels['0.618']:
            achieved, target = '0.618', f'{levels["1.414"]:.2f} (Next Target)'
        else:
            achieved, target = 'Retracement Zone', f'{levels["1.0"]:.2f}'
            
    else:
        trade_type = "🔴 PUT (PE) SIDE ENTRY"
        stop_loss = swing_high
        
        levels['0.0']   = swing_high
        levels['0.382'] = swing_high - (fib_range * 0.382)
        levels['0.5']   = swing_high - (fib_range * 0.5)
        levels['0.618'] = swing_high - (fib_range * 0.618)
        levels['1.0']   = swing_low
        levels['1.414'] = swing_high - (fib_range * 1.414)
        levels['1.618'] = swing_high - (fib_range * 1.618)
        levels['2.0']   = swing_high - (fib_range * 2.0)
        levels['2.272'] = swing_high - (fib_range * 2.272)
        levels['2.618'] = swing_high - (fib_range * 2.618)
        
        if current_close <= levels['2.618']:
            achieved, target = '2.618', 'All Targets Achieved! (Wait for New Swing)'
        elif current_close <= levels['1.414']:
            achieved, target = '1.414', f'{levels["1.618"]:.2f}'
        else:
            achieved, target = 'Retracement Zone', f'{levels["1.414"]:.2f}'

    return trade_type, stop_loss, achieved, target, swing_low, swing_high, current_close

def main():
    # Example market indices watchlist with dummy or live candle data frames
    # In live execution, fetch OHLC dataframe from your broker/sahi app API.
    
    # Simulating recent candle dataframe for demonstration
    sample_data = {
        'High': [25180, 25210, 25190, 25214.27, 25220, 25236.5],
        'Low': [25141.8, 25160, 25170, 25190, 25200, 25212.0],
        'Close': [25160, 25190, 25180, 25210, 25216.5, 25236.5]
    }
    df = pd.DataFrame(sample_data)
    
    indices_watchlist = [
        {"name": "NIFTY 50 (NSE)", "data": df, "window": 2},
        # Add other indices data here...
    ]
    
    for item in indices_watchlist:
        symbol_name = item["name"]
        candles_df = item["data"]
        win = item["window"]
        
        trade_type, sl, achieved, target, s_low, s_high, current_close = calculate_dynamic_fib_setup(candles_df, window=win)
        
        msg = (
            f"🚀 *Auto-Swing F&O Setup: {symbol_name}*\n"
            f"-----------------------------------\n"
            f"{trade_type}\n"
            f"📌 *Detected Swing High:* `{s_high}`\n"
            f"📌 *Detected Swing Low:* `{s_low}`\n"
            f"📥 *Candle Close:* `{current_close}`\n"
            f"🛑 *Stop Loss (SL):* `{sl}`\n"
            f"✅ *Achieved Level:* `{achieved}`\n"
            f"🎯 *Next Target:* `{target}`"
        )
        
        send_telegram_alert(msg)
        time.sleep(1)

if __name__ == "__main__":
    main()
