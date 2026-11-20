import csv
import io
import os
import time
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import requests

IST = timezone(timedelta(hours=5, minutes=30))
LOG_FILE = "trade_log.csv"

TELEGRAM_TOKEN = (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
CHAT_ID = (os.environ.get("CHAT_ID") or "").strip()

SAHI_AUTH_BASE_URL = (os.environ.get("SAHI_AUTH_BASE_URL") or "https://apis.sahi.com").strip().rstrip("/")
SAHI_API_BASE_URL = (os.environ.get("SAHI_API_BASE_URL") or "https://direct.sahi.com").strip().rstrip("/")

SAHI_KEY_ID = (os.environ.get("SAHI_KEY_ID") or os.environ.get("SAHI_API_KEY") or "").strip()
SAHI_SECRET = (os.environ.get("SAHI_SECRET") or "").strip()
EXPLICIT_ACCESS_TOKEN = (os.environ.get("SAHI_ACCESS_TOKEN") or "").strip()

CACHED_TOKEN = None

INDEX_CONFIG = {
    "NIFTY 50": {
        "env_id": (os.environ.get("NIFTY_INST_ID") or "").strip(),
        "fallback_id": "10854",
        "exchange": "NSE",
        "min_price": 15000.0,
        "max_price": 40000.0,
        "sl_points": 55.0,
        "match_terms": ["NIFTY 50", "NIFTY50", "NIFTY INDEX"],
    },
    "BANKNIFTY": {
        "env_id": (os.environ.get("BANKNIFTY_INST_ID") or "").strip(),
        "fallback_id": "10829",
        "exchange": "NSE",
        "min_price": 35000.0,
        "max_price": 95000.0,
        "sl_points": 140.0,
        "match_terms": ["NIFTY BANK", "BANKNIFTY"],
    },
    "FINNIFTY": {
        "env_id": (os.environ.get("FINNIFTY_INST_ID") or "").strip(),
        "fallback_id": "10811",
        "exchange": "NSE",
        "min_price": 15000.0,
        "max_price": 45000.0,
        "sl_points": 65.0,
        "match_terms": ["NIFTY FIN SERVICE", "NIFTY FINANCIAL", "FINNIFTY"],
    },
    "MIDCAP NIFTY": {
        "env_id": (os.environ.get("MIDCAP_INST_ID") or "").strip(),
        "fallback_id": "11266",
        "exchange": "NSE",
        "min_price": 8000.0,
        "max_price": 25000.0,
        "sl_points": 40.0,
        "match_terms": ["NIFTY MID SELECT", "MIDCAP NIFTY", "MIDCPNIFTY"],
    },
    "SENSEX": {
        "env_id": (os.environ.get("SENSEX_INST_ID") or "").strip(),
        "fallback_id": "736320",
        "exchange": "BSE",
        "min_price": 50000.0,
        "max_price": 130000.0,
        "sl_points": 180.0,
        "match_terms": ["SENSEX"],
    },
}


def safe_get(url: str, headers: dict, params: dict | None = None, timeout: int = 15):
    try:
        return requests.get(url, headers=headers, params=params, timeout=timeout)
    except Exception as e:
        print(f"GET error [{url}]: {e}")
        return None


def safe_post(url: str, headers: dict, payload: dict, timeout: int = 15):
    try:
        return requests.post(url, headers=headers, json=payload, timeout=timeout)
    except Exception as e:
        print(f"POST error [{url}]: {e}")
        return None


def get_sahi_token() -> str | None:
    global CACHED_TOKEN
    if CACHED_TOKEN:
        return CACHED_TOKEN

    if SAHI_KEY_ID and SAHI_SECRET:
        url = f"{SAHI_AUTH_BASE_URL}/api/v1/apikeys/token"
        resp = safe_post(
            url,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            payload={"key_id": SAHI_KEY_ID, "secret": SAHI_SECRET},
        )
        if resp is not None:
            print(f"Auth HTTP {resp.status_code}")
            if resp.status_code in (200, 201):
                try:
                    data = resp.json()
                except Exception:
                    data = {}
                for obj in (data, data.get("data") if isinstance(data, dict) else None):
                    if isinstance(obj, dict):
                        for k in ("access_token", "token", "bearer_token", "jwt"):
                            val = obj.get(k)
                            if isinstance(val, str) and val.strip():
                                CACHED_TOKEN = val.strip()
                                return CACHED_TOKEN

    if EXPLICIT_ACCESS_TOKEN:
        CACHED_TOKEN = EXPLICIT_ACCESS_TOKEN
        return CACHED_TOKEN

    print("Auth missing: SAHI_KEY_ID/SAHI_SECRET or SAHI_ACCESS_TOKEN not set.")
    return None


def resolve_spot_ids(headers: dict) -> dict[str, str]:
    resolved: dict[str, str] = {}
    missing = []

    for name, cfg in INDEX_CONFIG.items():
        if cfg["env_id"]:
            resolved[name] = cfg["env_id"]
        else:
            missing.append(name)

    if missing:
        resp = safe_get("https://assets.sahi.com/external/instruments.csv", headers=headers, timeout=20)
        if resp is not None and resp.status_code == 200 and resp.text:
            try:
                df = pd.read_csv(io.StringIO(resp.text), low_memory=False)
                id_col = next((c for c in ("id", "instrument_id", "security_id", "token") if c in df.columns), None)
                search_cols = [
                    c for c in ("symbol", "trading_symbol", "company_name", "display_name", "name") if c in df.columns
                ]
                if id_col and search_cols:
                    df_work = df.copy()
                    if "instrument_type" in df_work.columns:
                        idx_df = df_work[
                            df_work["instrument_type"].fillna("").astype(str).str.strip().str.upper() == "IDX"
                        ]
                        if len(idx_df) > 0:
                            df_work = idx_df

                    for name in list(missing):
                        cfg = INDEX_CONFIG[name]
                        exch = cfg["exchange"].upper()
                        sub = df_work
                        if "exchange" in df_work.columns:
                            ex_sub = df_work[
                                df_work["exchange"].fillna("").astype(str).str.strip().str.upper() == exch
                            ]
                            if len(ex_sub) > 0:
                                sub = ex_sub

                        matched_row = None
                        for term in cfg["match_terms"]:
                            t_up = term.upper()
                            for col in search_cols:
                                s = sub[col].fillna("").astype(str).str.strip().str.upper()
                                hits = sub[s == t_up]
                                if len(hits) > 0:
                                    matched_row = hits.iloc[0]
                                    break
                            if matched_row is not None:
                                break

                        if matched_row is None:
                            for term in cfg["match_terms"]:
                                t_up = term.upper()
                                for col in search_cols:
                                    s = sub[col].fillna("").astype(str).str.strip().str.upper()
                                    hits = sub[s.str.contains(t_up, regex=False)]
                                    if len(hits) > 0:
                                        matched_row = hits.iloc[0]
                                        break
                                if matched_row is not None:
                                    break

                        if matched_row is not None and pd.notna(matched_row[id_col]):
                            inst_id = str(matched_row[id_col]).strip()
                            lbl = str(matched_row[search_cols[0]]).strip()
                            resolved[name] = inst_id
                            missing.remove(name)
                            print(f"[{name}] Spot IDX -> {inst_id} ({lbl})")
            except Exception as e:
                print(f"Instruments CSV parse error: {e}")

    for name in missing:
        fb_id = INDEX_CONFIG[name]["fallback_id"]
        resolved[name] = fb_id
        print(f"[{name}] Spot IDX -> {fb_id} (verified)")

    return resolved


def normalize_price(val: float, min_p: float, max_p: float) -> float | None:
    try:
        x = float(val)
    except Exception:
        return None
    if x <= 0:
        return None
    if min_p <= x <= max_p:
        return round(x, 2)
    as_rs = x / 100.0
    if min_p <= as_rs <= max_p:
        return round(as_rs, 2)
    return None


def parse_candles(payload, min_p: float, max_p: float) -> pd.DataFrame | None:
    if not isinstance(payload, dict):
        return None
    rows = payload.get("candles") or payload.get("data") or payload.get("ohlc") or []
    if isinstance(rows, dict):
        rows = rows.get("candles") or rows.get("data") or []
    if not isinstance(rows, list) or len(rows) < 12:
        return None

    if isinstance(rows[0], dict):
        df = pd.DataFrame(rows)
        col_map = {
            "open": "Open",
            "o": "Open",
            "high": "High",
            "h": "High",
            "low": "Low",
            "l": "Low",
            "close": "Close",
            "c": "Close",
            "volume": "Volume",
            "v": "Volume",
            "vol": "Volume",
        }
        df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
    elif isinstance(rows[0], (list, tuple)) and len(rows[0]) >= 5:
        raw_df = pd.DataFrame(rows)
        if raw_df.shape[1] >= 6:
            first_med = pd.to_numeric(raw_df.iloc[:, 0], errors="coerce").median()
            if pd.notna(first_med) and first_med > 1_000_000_000:
                df = pd.DataFrame({
                    "Open": raw_df.iloc[:, 1],
                    "High": raw_df.iloc[:, 2],
                    "Low": raw_df.iloc[:, 3],
                    "Close": raw_df.iloc[:, 4],
                    "Volume": raw_df.iloc[:, 5],
                })
            else:
                df = pd.DataFrame({
                    "Open": raw_df.iloc[:, 0],
                    "High": raw_df.iloc[:, 1],
                    "Low": raw_df.iloc[:, 2],
                    "Close": raw_df.iloc[:, 3],
                    "Volume": raw_df.iloc[:, 4],
                })
        else:
            df = pd.DataFrame({
                "Open": raw_df.iloc[:, 0],
                "High": raw_df.iloc[:, 1],
                "Low": raw_df.iloc[:, 2],
                "Close": raw_df.iloc[:, 3],
                "Volume": raw_df.iloc[:, 4],
            })
    else:
        return None

    for c in ("Open", "High", "Low", "Close"):
        if c not in df.columns:
            return None
        s = pd.to_numeric(df[c], errors="coerce")
        med = float(s.dropna().median()) if len(s.dropna()) > 0 else 0.0
        if med > max_p:
            s = s / 100.0
        df[c] = s

    if "Volume" not in df.columns:
        df["Volume"] = 100000.0
    df["Volume"] = pd.to_numeric(df["Volume"], errors="coerce").fillna(100000.0)

    df["High"] = np.maximum(df["High"], np.maximum(df["Open"], df["Close"]))
    df["Low"] = np.minimum(df["Low"], np.minimum(df["Open"], df["Close"]))

    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna().tail(60).reset_index(drop=True)
    if len(df) < 12:
        return None

    last_close = normalize_price(float(df["Close"].iloc[-1]), min_p, max_p)
    if last_close is None:
        return None
    return df


def fetch_candles(symbol: str, cfg: dict, inst_id: str, headers: dict) -> pd.DataFrame | None:
    min_p = cfg["min_price"]
    max_p = cfg["max_price"]

    now_ist = datetime.now(IST)
    from_ist = (now_ist - timedelta(days=5)).replace(hour=9, minute=15, second=0, microsecond=0)
    to_ist = now_ist.replace(microsecond=0)

    fmt_candidates = [
        ("epoch_s", str(int(from_ist.timestamp())), str(int(to_ist.timestamp()))),
        ("epoch_ms", str(int(from_ist.timestamp() * 1000)), str(int(to_ist.timestamp() * 1000))),
        ("iso_ist", from_ist.strftime("%Y-%m-%dT%H:%M:%S+05:30"), to_ist.strftime("%Y-%m-%dT%H:%M:%S+05:30")),
        ("dt_space", from_ist.strftime("%Y-%m-%d %H:%M:%S"), to_ist.strftime("%Y-%m-%d %H:%M:%S")),
    ]

    id_val = int(inst_id) if inst_id.isdigit() else inst_id

    for tag, f_val, t_val in fmt_candidates:
        for _ in range(2):
            resp = safe_get(
                f"{SAHI_API_BASE_URL}/v1/marketdata/candles",
                headers=headers,
                params={"i": id_val, "instrument_id": id_val, "size": "5m", "from": f_val, "to": t_val},
            )
            if resp is None:
                time.sleep(2.0)
                continue
            if resp.status_code == 429:
                print(f"[{symbol}] Rate limited ({tag}) -> waiting 8s...")
                time.sleep(8.0)
                continue
            if resp.status_code == 400:
                print(f"[{symbol}] 400 ({tag}): {resp.text[:140]}")
                break
            if resp.status_code == 200:
                df = parse_candles(resp.json(), min_p, max_p)
                if df is not None:
                    return df
                break
        time.sleep(2.0)

    print(f"[{symbol}] Candles not available -> skipped.")
    return None


def get_swings(highs: np.ndarray, lows: np.ndarray):
    sub_h = highs[-45:]
    sub_l = lows[-45:]
    sh = []
    sl = []

    for i in range(1, len(sub_h) - 1):
        if sub_h[i] >= sub_h[i - 1] and sub_h[i] >= sub_h[i + 1]:
            if not sh or abs(float(sub_h[i]) - sh[-1]) > 0.01:
                sh.append(float(sub_h[i]))
        if sub_l[i] <= sub_l[i - 1] and sub_l[i] <= sub_l[i + 1]:
            if not sl or abs(float(sub_l[i]) - sl[-1]) > 0.01:
                sl.append(float(sub_l[i]))

    h1, h2 = (
        (sh[-2], sh[-1])
        if len(sh) >= 2
        else (float(np.max(sub_h[: len(sub_h) // 2])), float(np.max(sub_h[len(sub_h) // 2 :])))
    )
    l1, l2 = (
        (sl[-2], sl[-1])
        if len(sl) >= 2
        else (float(np.min(sub_l[: len(sub_l) // 2])), float(np.min(sub_l[len(sub_l) // 2 :])))
    )
    return h1, h2, l1, l2


def build_fib_signal(symbol: str, cfg: dict, df: pd.DataFrame):
    """
    Returns (msg, row) if valid setup exists, or (None, None) when pullback fails to hold.
    Rules:
    - 3-Point Trend Fib with P3 = P1.
    - First stage targets: 1.414 and 1.618 (plus 2.0 reference); if candle closes beyond 1.618,
      next targets shift to 2.0, 2.272, 2.618.
    - If rejected at a target, let price retrace to nearest swing's 0.5-0.618 zone:
      hold/reject there -> new targets; fail to hold -> no signal (None).
    """
    highs = df["High"].astype(float).values
    lows = df["Low"].astype(float).values
    closes = df["Close"].astype(float).values
    opens = df["Open"].astype(float).values

    h1, h2, l1, l2 = get_swings(highs, lows)
    entry = float(closes[-1])
    c_open = float(opens[-1])
    c_high = float(highs[-1])
    c_low = float(lows[-1])
    p_close = float(closes[-2])
    p_open = float(opens[-2])
    p_high = float(highs[-2])
    p_low = float(lows[-2])
    max_sl = float(cfg["sl_points"])

    is_uptrend = (h2 > h1) and (l2 > l1)
    is_downtrend = (h2 < h1) and (l2 < l1)

    if is_uptrend:
        # P1 = l2, P2 = h2 (or recent high), P3 = P1 (l2)
        p1 = l2
        p2 = max(h2, float(np.max(highs[-10:])))
        p3 = p1
        leg = max(p2 - p1, round(entry * 0.002, 2), 1.0)

        fib_050 = p2 - 0.50 * leg
        fib_0618 = p2 - 0.618 * leg

        t_1414 = round(p3 + 1.414 * leg, 2)
        t_1618 = round(p3 + 1.618 * leg, 2)
        t_2000 = round(p3 + 2.000 * leg, 2)
        t_2272 = round(p3 + 2.272 * leg, 2)
        t_2618 = round(p3 + 2.618 * leg, 2)

        # Check if price rejected from target (touched/near target without closing past)
        rejected_at_target = (
            (p_high >= t_1414 and p_close <= t_1414 and c_close < p_high)
            or (c_high >= t_1414 and c_close < t_1414 and c_close < c_open)
        )

        if rejected_at_target:
            # Allow pullback to nearest swing 0.5 - 0.618 zone
            z_top = max(fib_050, fib_0618)
            z_bot = min(fib_050, fib_0618)
            pad = max((z_top - z_bot) * 0.25, entry * 0.0005, 1.0)
            in_retrace_zone = (c_low <= z_top + pad) and (c_high >= z_bot - pad)
            failed_hold = c_close < (z_bot - pad)

            if failed_hold:
                print(f"[{symbol}] Target rejection -> failed to hold 0.5-0.618 zone -> no signal.")
                return None, None

            if in_retrace_zone and (c_close >= c_open or c_low <= z_top):
                # New base from 0.618/P3 for fresh leg
                new_base = min(p3, z_bot)
                new_leg = max(entry - new_base, leg * 0.6, 1.0)
                t1 = round(entry + 1.414 * new_leg, 2)
                t2 = round(entry + 1.618 * new_leg, 2)
                t3 = round(entry + 2.272 * new_leg, 2)
                sl = round(entry - min(max_sl, max(entry - (z_bot - pad), 10.0)), 2)
                side = "CALL (CE)"
                logic = "Target Reject -> 0.5-0.618 Hold/Reject New Leg"
            else:
                # Still pulling back toward 0.5-0.618; wait for zone hold/reject
                print(f"[{symbol}] Target rejection -> pulling back toward 0.5-0.618 zone -> no signal yet.")
                return None, None
        else:
            # Closed above 1.618 -> next targets 2.0 and 2.272 (and 2.618)
            if p_close > t_1618 or c_close > t_1618:
                t1, t2, t3 = t_2000, t_2272, t_2618
                logic = "HH+HL + Closed >1.618 -> Next Targets 2 & 2.272"
            else:
                # 0.5 rejection/hold -> first targets 1.414 to 1.618 (with 2.0)
                t1, t2, t3 = t_1414, t_1618, t_2000
                logic = "HH+HL + 0.5 Reject/Hold -> Targets 1.414-1.618 (P3=P1)"

            sl_dist = min(max_sl, max(entry - (min(fib_0618, p3) - leg * 0.05), round(entry * 0.0012, 2), 10.0))
            sl = round(entry - sl_dist, 2)
            side = "CALL (CE)"

    elif is_downtrend:
        # P1 = h2, P2 = l2 (or recent low), P3 = P1 (h2)
        p1 = h2
        p2 = min(l2, float(np.min(lows[-10:])))
        p3 = p1
        leg = max(p1 - p2, round(entry * 0.002, 2), 1.0)

        fib_050 = p2 + 0.50 * leg
        fib_0618 = p2 + 0.618 * leg

        t_1414 = round(p3 - 1.414 * leg, 2)
        t_1618 = round(p3 - 1.618 * leg, 2)
        t_2000 = round(p3 - 2.000 * leg, 2)
        t_2272 = round(p3 - 2.272 * leg, 2)
        t_2618 = round(p3 - 2.618 * leg, 2)

        rejected_at_target = (
            (p_low <= t_1414 and p_close >= t_1414 and c_close > p_low)
            or (c_low <= t_1414 and c_close > t_1414 and c_close > c_open)
        )

        if rejected_at_target:
            z_bot = min(fib_050, fib_0618)
            z_top = max(fib_050, fib_0618)
            pad = max((z_top - z_bot) * 0.25, entry * 0.0005, 1.0)
            in_retrace_zone = (c_high >= z_bot - pad) and (c_low <= z_top + pad)
            failed_hold = c_close > (z_top + pad)

            if failed_hold:
                print(f"[{symbol}] Target rejection -> failed to hold 0.5-0.618 zone -> no signal.")
                return None, None

            if in_retrace_zone and (c_close <= c_open or c_high >= z_bot):
                new_top = max(p3, z_top)
                new_leg = max(new_top - entry, leg * 0.6, 1.0)
                t1 = round(entry - 1.414 * new_leg, 2)
                t2 = round(entry - 1.618 * new_leg, 2)
                t3 = round(entry - 2.272 * new_leg, 2)
                sl = round(entry + min(max_sl, max((z_top + pad) - entry, 10.0)), 2)
                side = "PUT (PE)"
                logic = "Target Reject -> 0.5-0.618 Hold/Reject New Leg"
            else:
                print(f"[{symbol}] Target rejection -> pulling back toward 0.5-0.618 zone -> no signal yet.")
                return None, None
        else:
            if p_close < t_1618 or c_close < t_1618:
                t1, t2, t3 = t_2000, t_2272, t_2618
                logic = "LH+LL + Closed <1.618 -> Next Targets 2 & 2.272"
            else:
                t1, t2, t3 = t_1414, t_1618, t_2000
                logic = "LH+LL + 0.5 Reject/Hold -> Targets 1.414-1.618 (P3=P1)"

            sl_dist = min(max_sl, max((max(fib_0618, p3) + leg * 0.05) - entry, round(entry * 0.0012, 2), 10.0))
            sl = round(entry + sl_dist, 2)
            side = "PUT (PE)"

    else:
        # No clear HH+HL or LH+LL trend -> check nearest swing 0.5-0.618 hold/reject
        leg = max(h2 - l2, round(entry * 0.002, 2), 1.0)
        z_050 = l2 + 0.50 * leg
        z_0618 = l2 + 0.618 * leg
        z_bot, z_top = min(z_050, z_0618), max(z_050, z_0618)
        pad = max((z_top - z_bot) * 0.25, entry * 0.0005, 1.0)

        if entry >= z_050 and c_close >= c_open:
            side = "CALL (CE)"
            logic = "Above 0.5 Zone Hold -> Targets 1.414-1.618"
            sl = round(entry - min(max_sl, max(entry - (z_bot - pad), 10.0)), 2)
            t1 = round(l2 + 1.414 * leg, 2)
            t2 = round(l2 + 1.618 * leg, 2)
            t3 = round(l2 + 2.272 * leg, 2)
        elif entry <= z_0618 and c_close <= c_open:
            side = "PUT (PE)"
            logic = "Below 0.618 Zone Reject -> Targets 1.414-1.618"
            sl = round(entry + min(max_sl, max((z_top + pad) - entry, 10.0)), 2)
            t1 = round(h2 - 1.414 * leg, 2)
            t2 = round(h2 - 1.618 * leg, 2)
            t3 = round(h2 - 2.272 * leg, 2)
        else:
            print(f"[{symbol}] No hold at 0.5-0.618 zone -> no signal.")
            return None, None

    msg = (
        f"{symbol} ({cfg['exchange']}) | {side}\n"
        f"Logic: {logic}\n"
        f"Entry: {entry:.2f}\n"
        f"SL: {sl:.2f}\n"
        f"Target 1: {t1:.2f}\n"
        f"Target 2: {t2:.2f}\n"
        f"Target 3: {t3:.2f}"
    )

    row = {
        "timestamp_ist": datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S"),
        "symbol": symbol,
        "exchange": cfg["exchange"],
        "side": side,
        "logic": logic,
        "entry": round(entry, 2),
        "sl": sl,
        "target_1": t1,
        "target_2": t2,
        "target_3": t3,
    }
    return msg, row


def send_telegram(msg: str) -> bool:
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("Telegram env missing.")
        return False
    resp = safe_post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        headers={"Content-Type": "application/json"},
        payload={"chat_id": CHAT_ID, "text": msg, "disable_web_page_preview": True},
    )
    if resp is None:
        return False
    print(f"Telegram HTTP {resp.status_code}")
    return 200 <= resp.status_code < 300


def save_log(row: dict):
    cols = ["timestamp_ist", "symbol", "exchange", "side", "logic", "entry", "sl", "target_1", "target_2", "target_3"]
    exists = os.path.isfile(LOG_FILE) and os.path.getsize(LOG_FILE) > 0
    try:
        with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            if not exists:
                w.writeheader()
            w.writerow(row)
    except Exception as e:
        print(f"CSV log error: {e}")


def main():
    print("Scanner started...")
    token = get_sahi_token()
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    ids = resolve_spot_ids(headers)
    sent_count = 0

    for sym, cfg in INDEX_CONFIG.items():
        inst_id = ids.get(sym)
        if not inst_id:
            continue
        df = fetch_candles(sym, cfg, inst_id, headers)
        if df is None:
            time.sleep(5.0)
            continue
        msg, row = build_fib_signal(sym, cfg, df)
        if msg is None or row is None:
            time.sleep(4.0)
            continue
        save_log(row)
        if send_telegram(msg):
            sent_count += 1
        time.sleep(6.0)

    print(f"Done. Alerts sent: {sent_count}/{len(INDEX_CONFIG)}")


if __name__ == "__main__":
    main()
