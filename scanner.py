import pandas as pd
import numpy as np

def detect_swings(df, window=5):
    """
    Automatic Swing Detection for Internal (Minor) and Outside (Major) Swings.
    - window = 3 or 5 for Internal/Nana swings
    - window = 15 or 20 for Outside/Mota swings
    """
    df['Swing_High'] = df['High'][(df['High'] == df['High'].rolling(window=2*window+1, center=True).max())]
    df['Swing_Low'] = df['Low'][(df['Low'] == df['Low'].rolling(window=2*window+1, center=True).min())]
    return df

def calculate_trend_fib_extension(swing_low, swing_high, current_close, is_uptrend=True):
    fib_range = abs(swing_high - swing_low)
    levels = {}
    
    if is_uptrend:
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
        
        # Target Progression Logic based on Candle Close
        if current_close >= levels['1.618']:
            achieved, target = '1.618', f'T3: {levels["2.0"]:.2f} & {levels["2.272"]:.2f}'
        elif current_close >= levels['0.618']:
            achieved, target = '0.618', f'T1: {levels["1.414"]:.2f}'
        else:
            achieved, target = 'Retracement Zone', f'Target: {levels["1.0"]:.2f}'
            
    return achieved, target, levels
