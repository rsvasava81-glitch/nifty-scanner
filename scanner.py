import os
import time
import requests
import pandas as pd
import numpy as np

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

# Sahi API config (set SAHI_ACCESS_TOKEN in GitHub Secrets)
SAHI_BASE_URL = os.environ.get("SAHI_BASE_URL", "https://api.sahi.com")
SAHI_ACCESS_TOKEN = os.environ.get("SAHI_ACCESS_TOKEN") or os.environ.get("SAHI_KEY_ID")

# Sahi scrip-master na integer instrument_id ahi fill karo (e.g., {"NIFTY 50": 12345, ...})
INSTRUMENT_MAP = {
    "NIFTY 50": {"instrument_id": os.environ.get("NIFTY_INST_ID"), "exchange": "NSE", "sl_cap": 65.0},
    "BANKNIFTY": {"instrument_id": os.environ.get("BANKNIFTY_INST_ID"), "exchange": "NSE", "sl_cap": 150.0},
    "FINNIFTY": {"instrument_id": os.environ.get("FINNIFTY_INST_ID"), "exchange": "NSE", "sl_cap": 70.0},
    "MIDCAP NIFTY": {"instrument_id": os.environ.get("MIDCAP_INST_ID"), "exchange": "NSE", "sl_cap": 45.0},
    "SENSEX": {"instrument_id": os.environ.get("SENSEX_INST_ID"), "exchange": "BSE", "sl_cap": 200.0},
}


def send_telegram_alert(message: str) -> bool:
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("ERROR: TELEGRAM_BOT_TOKEN athva CHAT_ID set nathi.")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "disable_web_page_preview": True,
    }
    try:
        resp = requests.post(url, json=payload, timeout=15)
        print("Telegram Status:", resp.status_code)
        resp.raise_for_status()
        return True
    except Exception as e:
        print("Telegram Send Error:", e)
        return False


def sahi_headers() -> dict:
    return {
        "Authorization": f"Bearer {SAHI_ACCESS_TOKEN}",
        "Accept": "application/json",
    }


def fetch_sahi_candles_and_oi(symbol: str, cfg: dict):
    """
    Sahi Market Data API mathi candles ane option chain (OI/PCR) fetch kare chhe.
    Jo instrument_id / token missing hoy ke API empty response aape to fallback data aape chhe.
    """
    inst_id = cfg.get("instrument_id")

    if SAHI_ACCESS_TOKEN and inst_id:
        try:
            # 1) Historical Candles
            c_url = f"{SAHI_BASE_URL}/v1/marketdata/candles"
            c_params = {"instrument_id": int(inst_id), "interval": "5m"}
            c_resp = requests.get(c_url, headers=sahi_headers(), params=c_params, timeout=15)
            if c_resp.status_code == 200:
                c_json = c_resp.json()
                rows = c_json.get("data") or c_json.get("candles") or []
                if len(rows) >= 6:
                    df = pd.DataFrame(rows)
                    rename_map = {
                        "open": "Open", "high": "High", "low": "Low",
                        "close": "Close", "volume": "Volume"
                    }
                    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
                    for col in ["Open", "High", "Low", "Close", "Volume"]:
                        if col not in df.columns:
                            df[col] = 0.0
                    df = df[["Open", "High", "Low", "Close", "Volume"]].tail(40).reset_index(drop=True)
                else:
                    df = None
            else:
                print(f"[{symbol}] Sahi Candles Status: {c_resp.status_code}")
                df = None

            # 2) Option Chain OI & PCR
            oc_url = f"{SAHI_BASE_URL}/v1/marketdata/optionchain"
            oc_params = {"instrument_id": int(inst_id)}
            oc_resp = requests.get(oc_url, headers=sahi_headers(), params=oc_params, timeout=15)
            oi_summary = None
            if oc_resp.status_code == 200:
                oc_json = oc_resp.json()
                chain = oc_json.get("data") or oc_json.get("chain") or []
                total_call_oi = 0.0
                total_put_oi = 0.0
                for row in chain:
                    ce = row.get("CE") or row.get("call") or {}
                    pe = row.get("PE") or row.get("put") or {}
                    total_call_oi += float(ce.get("oi") or ce.get("open_interest") or 0.0)
                    total_put_oi += float(pe.get("oi") or pe.get("open_interest") or 0.0)

                if total_call_oi > 0 or total_put_oi > 0:
                    pcr = round(total_put_oi / max(total_call_oi, 1.0), 2)
                    oi_summary = {
                        "pcr": pcr,
                        "call_oi": round(total_call_oi / 100000.0, 2),  # Lakhs
                        "put_oi": round(total_put_oi / 100000.0, 2),    # Lakhs
                        "source": "Sahi Live OC",
                    }

            if df is not None and oi_summary is not None:
                return df, oi_summary
        except Exception as e:
            print(f"[{symbol}] Sahi API Error: {e}")

    # Fallback structure (when instrument_id / token not set or market closed)
    if symbol == "NIFTY 50":
        df = pd.DataFrame({
            "Open":   [25165.0, 25198.0, 25215.0, 25202.0, 25212.0, 25224.0],
            "High":   [25205.0, 25238.48, 25228.0, 25214.0, 25232.0, 25248.0],
            "Low":    [25141.80, 25195.0, 25205.0, 25197.02, 25208.0, 25221.0],
            "Close":  [25198.0, 25215.0, 25208.0, 25204.0, 25225.0, 25244.5],
            "Volume": [110000, 185000, 120000, 105000, 195000, 240000],
        })
        oi_summary = {"pcr": 1.18, "call_oi": 142.5, "put_oi": 168.2, "source": "Fallback"}
        return df, oi_summary

    base = 51300.0 if "BANK" in symbol else (23300.0 if "FIN" in symbol else (12450.0 if "MID" in symbol else 82200.0))
    step = base * 0.0015
    df = pd.DataFrame({
        "Open":   [base, base + step, base + 2 * step, base + 1.2 * step, base + 1.8 * step, base + 2.6 * step],
        "High":   [base + 1.5 * step, base + 3.2 * step, base + 2.4 * step, base + 1.7 * step, base + 2.9 * step, base + 3.8 * step],
        "Low":    [base - 0.8 * step, base + 0.9 * step, base + 1.1 * step, base + 0.5 * step, base + 1.1 * step, base + 2.1 * step],
        "Close":  [base + step, base + 2.2 * step, base + 1.4 * step, base + 1.1 * step, base + 2.5 * step, base + 3.5 * step],
        "Volume": [90000, 150000, 100000, 95000, 160000, 210000],
    })
    oi_summary = {"pcr": 1.06, "call_oi": 95.0, "put_oi": 100.7, "source": "Fallback"}
    return df, oi_summary


def analyze_footprint_and_oi(df: pd.DataFrame, oi: dict):
    vol = df["Volume"].astype(float).values
    opens = df["Open"].astype(float).values
    highs = df["High"].astype(float).values
    lows = df["Low"].astype(float).values
    closes = df["Close"].astype(float).values

    avg_vol = np.mean(vol[:-1]) if len(vol) > 1 else vol[-1]
    vol_mult = round(float(vol[-1] / avg_vol), 2) if avg_vol > 0 else 1.0

    rng = max(float(highs[-1] - lows[-1]), 1e-5)
    body_pct = int(round(min(100.0, (abs(float(closes[-1] - opens[-1])) / rng) * 100.0)))
    bull_candle = bool(closes[-1] > opens[-1])
    footprint_ok = (vol_mult >= 1.25) and (body_pct >= 45)

    pcr = float(oi.get("pcr", 1.0))
    if pcr >= 1.05:
        oi_bias = "BULLISH (Put Support)"
    elif pcr <= 0.85:
        oi_bias = "BEARISH (Call Resistance)"
    else:
        oi_bias = "NEUTRAL"

    return vol_mult, body_pct, bull_candle, footprint_ok, pcr, oi_bias


def generate_signal(symbol: str, cfg: dict, df: pd.DataFrame, oi: dict) -> str:
    highs = df["High"].astype(float).values
    lows = df["Low"].astype(float).values
    closes = df["Close"].astype(float).values
    n = len(df)

    # 3-Point Trend-Based Swing Detection:
    # P1: Impulse Low | P2: Impulse High | P3: Pullback Base (0.0)
    p1_idx = int(np.argmin(lows[: max(1, n // 2)]))
    p1_low = float(lows[p1_idx])

    p2_slice = highs[p1_idx:]
    p2_idx = p1_idx + int(np.argmax(p2_slice))
    p2_high = float(highs[p2_idx])

    p3_slice = lows[p2_idx:]
    p3_base = float(np.min(p3_slice)) if len(p3_slice) > 0 else float(np.min(lows[-2:]))

    current_close = float(closes[-1])
    impulse_range = max(p2_high - p1_low, 1.0)
    sl_cap = float(cfg.get("sl_cap", 65.0))

    vol_mult, body_pct, bull_candle, footprint_ok, pcr, oi_bias = analyze_footprint_and_oi(df, oi)

    bull_pts = (1 if current_close >= p3_base else 0) + (1 if bull_candle else 0) + (2 if "BULLISH" in oi_bias else 0)
    bear_pts = (1 if current_close < p3_base else 0) + (0 if bull_candle else 1) + (2 if "BEARISH" in oi_bias else 0)

    if bull_pts >= bear_pts:
        side = "CALL (CE) SIDE ENTRY"
        base_ref = p3_base
        sl = max(p3_base, current_close - sl_cap)
        t_05 = base_ref + impulse_range * 0.50
        t_0618 = base_ref + impulse_range * 0.618
        t_1414 = base_ref + impulse_range * 1.414
        t_1618 = base_ref + impulse_range * 1.618
        t_200 = base_ref + impulse_range * 2.00

        if current_close >= t_1618:
            achieved, next_target = "1.618", f"{t_200:.2f} (2.0 Ext)"
        elif current_close >= t_1414:
            achieved, next_target = "1.414", f"{t_1618:.2f} (1.618 Ext)"
        elif current_close >= t_0618:
            achieved, next_target = "0.618", f"{t_1414:.2f} (1.414 Ext)"
        elif current_close >= t_05:
            achieved, next_target = "0.50", f"{t_0618:.2f} (0.618 Ext)"
        else:
            achieved, next_target = "Base / Pullback", f"{t_05:.2f} (0.50 Ext)"
    else:
        side = "PUT (PE) SIDE ENTRY"
        base_ref = p2_high
        sl = min(p2_high, current_close + sl_cap)
        t_05 = base_ref - impulse_range * 0.50
        t_0618 = base_ref - impulse_range * 0.618
        t_1414 = base_ref - impulse_range * 1.414
        t_1618 = base_ref - impulse_range * 1.618
        t_200 = base_ref - impulse_range * 2.00

        if current_close <= t_1618:
            achieved, next_target = "1.618", f"{t_200:.2f} (2.0 Ext)"
        elif current_close <= t_1414:
            achieved, next_target = "1.414", f"{t_1618:.2f} (1.618 Ext)"
        elif current_close <= t_0618:
            achieved, next_target = "0.618", f"{t_1414:.2f} (1.414 Ext)"
        elif current_close <= t_05:
            achieved, next_target = "0.50", f"{t_0618:.2f} (0.618 Ext)"
        else:
            achieved, next_target = "Top / Pullback", f"{t_05:.2f} (0.50 Ext)"

    tag = "HIGH CONVICTION" if (footprint_ok and oi_bias != "NEUTRAL") else "MODERATE"
    return (
        f"F&O Setup: {symbol} ({cfg['exchange']}) [{tag}]\n"
        f"------------------------------------------\n"
        f"Side: {side}\n"
        f"Entry / Close: {current_close:.2f}\n"
        f"Stop Loss (SL): {sl:.2f}\n"
        f"P1 Low: {p1_low:.2f} | P2 High: {p2_high:.2f} | Base: {p3_base:.2f}\n"
        f"Achieved Level: {achieved}\n"
        f"Next Target: {next_target}\n"
        f"Footprint: Vol x{vol_mult} | Body {body_pct}%\n"
        f"Option Chain ({oi.get('source', 'OC')}): PCR {pcr:.2f} | {oi_bias} | Call {oi.get('call_oi', 0):.1f}L / Put {oi.get('put_oi', 0):.1f}L"
    )


def main():
    sent = 0
    for sym, cfg in INSTRUMENT_MAP.items():
        df, oi = fetch_sahi_candles_and_oi(sym, cfg)
        msg = generate_signal(sym, cfg, df, oi)
        if send_telegram_alert(msg):
            sent += 1
        time.sleep(1)
    print(f"Sent {sent}/{len(INSTRUMENT_MAP)} alerts.")


if __name__ == "__main__":
    main()
