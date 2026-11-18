import os
import requests

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

def calculate_fib_extension(high, low, is_uptrend=True):
    """
    Calculates Trend-Based Fibonacci Extension levels for both Uptrend and Downtrend.
    """
    diff = high - low
    levels = {}
    
    if is_uptrend:
        # Uptrend: Low to High extension (Bullish setup)
        levels['entry_0.5'] = high - (0.5 * diff)
        levels['stop_loss_0.618'] = high - (0.618 * diff)
        levels['t_1.414'] = high + (1.414 * diff)
        levels['t_1.618'] = high + (1.618 * diff)
        levels['t_2.000'] = high + (2.000 * diff)
        levels['t_2.272'] = high + (2.272 * diff)
        levels['t_2.618'] = high + (2.618 * diff)
    else:
        # Downtrend: High to Low extension (Bearish setup - Corrected logic)
        # Entry ane SL high/low na beech ma retracement par thay
        levels['entry_0.5'] = low + (0.5 * diff)
        levels['stop_loss_0.618'] = low + (0.618 * diff)
        
        # Targets down side: Low mathi minus thase etle price niche jetr targets malse
        levels['t_1.414'] = low - (1.414 * diff)
        levels['t_1.618'] = low - (1.618 * diff)
        levels['t_2.000'] = low - (2.000 * diff)
        levels['t_2.272'] = low - (2.272 * diff)
        levels['t_2.618'] = low - (2.618 * diff)
        
    return levels

def run_scanner():
    print("Running 5-minute Trend-Based Fibonacci Extension Scanner...")
    try:
        if not KEY_ID or not SECRET:
            print("Sahi API credentials are not set properly.")
            return

        # Testing values based on your previous chart high and low
        sample_high = 25319.51
        sample_low = 25141.80
        
        # Calculate Downtrend Fib Extension with corrected logic
        fib_levels = calculate_fib_extension(sample_high, sample_low, is_uptrend=False)
        
        alert_msg = (
            f"📉 *5-Min Downtrend Fib Extension Alert*\n"
            f"High: `{sample_high}` | Low: `{sample_low}`\n"
            f"• 0.5 Level: `{fib_levels['entry_0.5']:.2f}`\n"
            f"• 0.618 SL: `{fib_levels['stop_loss_0.618']:.2f}`\n"
            f"• Target 1.618: `{fib_levels['t_1.618']:.2f}`\n"
            f"• Target 2.0: `{fib_levels['t_2.000']:.2f}`\n"
            f"• Target 2.272: `{fib_levels['t_2.272']:.2f}`"
        )
        
        send_telegram_alert(alert_msg)
        print("Scanner executed and corrected alert sent successfully!")

    except Exception as e:
        print(f"Error during execution: {e}")
        raise e

if __name__ == "__main__":
    run_scanner()
