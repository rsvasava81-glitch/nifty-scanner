import os
import requests
import pandas as pd
import numpy as np
import time

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

def automatic_trend_fib_scanner(df):
    """
    Automatically detects 3-Point Trend-Based Fibonacci Extension from OHLC data:
    Point 1: Impulse Start (Significant Low)
    Point 2: Impulse High (Peak after Low)
    Point 3: Pullback Base / 0.0 Level (Retracement Low after High)
    """
    highs = df['High'].values
    lows = df['Low'].values
    closes = df['Close'].values
    n = len(df)
    
    if n < 10:
        return None
        
    # 1. Automatically find Point 1 (Lowest Low in the first half)
    idx_p1 = lows[:n//2].argmin()
    p1_low = lows[idx_p1]
    
    # 2. Automatically find Point 2 (Highest High after Point 1)
    sub_highs = highs[idx_p1:n-2]
    if len(sub_highs) == 0:
        return None
    idx_p2 = idx_p1 + sub_highs.argmax()
    p2_high = highs[idx_p2]
    
    # 3. Automatically find Point 3 (Pullback Base / Low after Point 2)
    sub_lows = lows[idx_p2:]
    if len(sub_lows) == 0:
        return None
    idx_p3 = idx_p2 + sub_lows.argmin()
    p3_base = lows[idx_p3]
    
    # Impulse Range (Distance from Point 1 to Point 2)
    impulse_range = p2_high - p1_low
    if impulse_range <= 0:
        return None
        
    # Extension Levels projected dynamically from Point 3 (Base / 0.0)
    levels = {}
    levels['0.0']   = p3_base
    levels['0.382'] = p3_base + (impulse_range * 0.382)
    levels['0.5']   = p3_base + (impulse_range * 0.5)
    levels['0.618'] = p3_base + (impulse_range * 0.618)
    levels['1.0']   = p3_base + impulse_range
    levels['1.414'] = p3_base + (impulse_range * 1.414)
    levels['1.618'] = p3_base + (impulse_range * 1.618)
    levels['2.0']   = p3_base + (impulse_range * 2.0)
    levels['2.272'] = p3_base + (impulse_range * 2.272)
    levels['2.618'] = p3_base + (impulse_range * 2.618)
    
    current_close = closes[-1]
    trade_type = "🟢 CALL (CE) SIDE ENTRY"
    stop_loss = p3_base
    
    # Target Progression based on latest Candle Close
    if current_close >= levels['1.618']:
        achieved, target = '1.618', f'T3: {levels["2.0"]:.2f}'
    elif current_close >= levels['1.414']:
        achieved, target = '1.414', f'T2: {levels["1.618"]:.2f}'
    elif current_close >= levels['0.618']:
        achieved, target = '0.618 (Achieved)', f'T1 (1.414): {levels["1.414"]:.2f}'
    elif current_close >= levels['0.5']:
        achieved, target = '0.5', f'0.618 ({levels["0.618"]:.2f})'
    else:
        achieved, target = 'Base (0.0)', f'0.5 ({levels["0.5"]:.2f})'

    return trade_type, stop_loss, achieved, target, p3_base, p2_high, current_close, levels

def main():
    # Watchlist / Live Data Integration (Replace with sahi app API dataframe)
    # Here using sample dataframe reflecting live market swings
    sample_data = {
        'High': [25180, 25210, 25238.48, 25210, 25225, 25230],
        'Low': [25140, 25197.02, 25215, 25197.02, 25205, 25222.75],
        'Close': [25160, 25200, 25220, 25205, 25215, 25222.75]
    }
    df = pd.DataFrame(sample_data)
    
    result = automatic_trend_fib_scanner(df)
    if result:
        trade_type, sl, achieved, target, base_0, high_ref, current_close, lvl = result
        
        msg = (
            f"🎯 *Auto Trend-Fib Scanner: NIFTY 50 (NSE)*\n"
            f"-----------------------------------\n"
            f"{trade_type}\n"
            f"📌 *Base (0.0):* `{base_0:.2f}` | *Impulse High:* `{high_ref:.2f}`\n"
            f"📥 *Candle Close:* `{current_close:.2f}`\n"
            f"🛑 *Stop Loss (SL):* `{sl:.2f}`\n"
            f"✅ *Achieved Level:* `{achieved}`\n"
            f"🎯 *Next Target:* `{target}`\n"
            f"📊 *0.618 Level:* `{lvl['0.618']:.2f}`"
        )
        
        send_telegram_alert(msg)
    else:
        print("Not enough swing data for calculation.")

if __name__ == "__main__":
    main()
