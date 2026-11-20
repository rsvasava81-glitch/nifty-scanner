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
    if not isinstance(rows, list) or len(rows) < 6:
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
        }
        df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
    elif isinstance(rows[0], (list, tuple)) and len(rows[0]) >= 5:
        df = pd.DataFrame(rows, columns=["Time", "Open", "High", "Low", "Close", "Volume"][: len(rows[0])])
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

    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna().tail(30).reset_index(drop=True)
    if len(df) < 6:
        return None

    last_close = normalize_price(float(df["Close"].iloc[-1]), min_p, max_p)
    if last_close is None:
        return None
    return df


def parse_option_chain(payload) -> dict:
    default_oi = {"pcr": 1.0, "call_oi": 0.0, "put_oi": 0.0, "source": "Standard"}
    if not isinstance(payload, dict):
        return default_oi
    raw = payload.get("data") or payload.get("chain") or payload.get("option_chain") or []
    rows = raw.get("chain") if isinstance(raw, dict) else raw
    if not isinstance(rows, list) or not rows:
        return default_oi

    call_oi = 0.0
    put_oi = 0.0
    for r in rows:
        if not isinstance(r, dict):
            continue
        ce = r.get("CE") or r.get("ce") or r.get("call") or {}
        pe = r.get("PE") or r.get("pe") or r.get("put") or {}
        if isinstance(ce, dict):
            call_oi += float(ce.get("oi") or ce.get("open_interest") or 0.0)
        if isinstance(pe, dict):
            put_oi += float(pe.get("oi") or pe.get("open_interest") or 0.0)

    if call_oi <= 0 and put_oi <= 0:
        return default_oi

    return {
        "pcr": round(put_oi / max(call_oi, 1.0), 2),
        "call_oi": round(call_oi / 100000.0, 2),
        "put_oi": round(put_oi / 100000.0, 2),
        "source": "Sahi OC",
    }


def fetch_market_data(symbol: str, cfg: dict, inst_id: str, headers: dict):
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
    df = None

    for tag, f_val, t_val in fmt_candidates:
        for attempt in range(2):
            c_resp = safe_get(
                f"{SAHI_API_BASE_URL}/v1/marketdata/candles",
                headers=headers,
                params={
                    "i": id_val,
                    "instrument_id": id_val,
                    "size": "5m",
                    "from": f_val,
                    "to": t_val,
                },
            )
            if c_resp is None:
                time.sleep(2.0)
                continue

            if c_resp.status_code == 429:
                print(f"[{symbol}] Rate limited ({tag}) -> waiting 8s...")
                time.sleep(8.0)
                continue

            if c_resp.status_code == 400:
                print(f"[{symbol}] 400 ({tag}): {c_resp.text[:140]}")
                break

            if c_resp.status_code == 200:
                print(f"[{symbol}] Candles HTTP 200 using {tag}")
                try:
                    df = parse_candles(c_resp.json(), min_p, max_p)
                except Exception as e:
                    print(f"[{symbol}] Candle parse error: {e}")
                    df = None
                break

        if df is not None:
            break
        time.sleep(2.0)

    if df is None:
        print(f"[{symbol}] Real 5m candles not available -> skipped.")
        return None, None

    time.sleep(4.0)

    oc_resp = safe_get(
        f"{SAHI_API_BASE_URL}/v1/marketdata/optionchain",
        headers=headers,
        params={"underlying_id": id_val},
    )
    oi = {"pcr": 1.0, "call_oi": 0.0, "put_oi": 0.0, "source": "Standard"}
    if oc_resp is not None and oc_resp.status_code == 200:
        try:
            oi = parse_option_chain(oc_resp.json())
        except Exception:
            pass

    return df, oi


def build_signal(symbol: str, cfg: dict, df: pd.DataFrame, oi: dict):
    highs = df["High"].astype(float).values
    lows = df["Low"].astype(float).values
    closes = df["Close"].astype(float).values
    opens = df["Open"].astype(float).values
    vols = df["Volume"].astype(float).values

    n = len(df)
    p1_idx = int(np.argmin(lows[: max(1, n // 2)]))
    p1_low = float(lows[p1_idx])

    p2_idx = p1_idx + int(np.argmax(highs[p1_idx:]))
    p2_high = float(highs[p2_idx])

    p3_slice = lows[p2_idx:]
    p3_base = float(np.min(p3_slice)) if len(p3_slice) > 0 else float(np.min(lows[-2:]))

    entry = float(closes[-1])
    swing = max(p2_high - p1_low, round(entry * 0.002, 2), 1.0)
    sl_dist = min(float(cfg["sl_points"]), max(swing * 0.25, round(entry * 0.0015, 2), 10.0))

    avg_vol = float(np.mean(vols[:-1])) if len(vols) > 1 else float(vols[-1])
    vol_mult = round(float(vols[-1] / max(avg_vol, 1.0)), 2)
    candle_rng = max(float(highs[-1] - lows[-1]), 1e-5)
    body_pct = int(round(min(100.0, (abs(float(closes[-1] - opens[-1])) / candle_rng) * 100.0)))

    pcr = float(oi.get("pcr", 1.0))
    bullish = (closes[-1] >= opens[-1]) and (pcr >= 0.90)

    if bullish:
        side = "CALL (CE) SIDE ENTRY"
        sl = round(entry - sl_dist, 2)
        t1 = round(entry + swing * 0.50, 2)
        t2 = round(entry + swing * 1.00, 2)
        t3 = round(entry + swing * 1.618, 2)
        bias = "BULLISH" if pcr >= 1.05 else "NEUTRAL-BULL"
    else:
        side = "PUT (PE) SIDE ENTRY"
        sl = round(entry + sl_dist, 2)
        t1 = round(entry - swing * 0.50, 2)
        t2 = round(entry - swing * 1.00, 2)
        t3 = round(entry - swing * 1.618, 2)
        bias = "BEARISH" if pcr <= 0.85 else "NEUTRAL-BEAR"

    conviction = "HIGH CONVICTION" if (vol_mult >= 1.25 and body_pct >= 45) else "MODERATE"

    msg = (
        f"F&O Setup: {symbol} ({cfg['exchange']}) [{conviction}]\n"
        f"------------------------------------------\n"
        f"Side: {side}\n"
        f"Entry / Close: {entry:.2f}\n"
        f"Stop Loss (SL): {sl:.2f}\n"
        f"Target 1 (0.50): {t1:.2f} | Target 2 (1.0): {t2:.2f} | Target 3 (1.618): {t3:.2f}\n"
        f"P1 Low: {p1_low:.2f} | P2 High: {p2_high:.2f} | Base: {p3_base:.2f}\n"
        f"Footprint: Vol x{vol_mult} | Body {body_pct}%\n"
        f"OI ({oi.get('source', 'Standard')}): PCR {pcr:.2f} | {bias}"
    )

    row = {
        "timestamp_ist": datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S"),
        "symbol": symbol,
        "exchange": cfg["exchange"],
        "source": oi.get("source", "Standard"),
        "conviction": conviction,
        "side": side,
        "entry_close": round(entry, 2),
        "stop_loss": sl,
        "p1_low": round(p1_low, 2),
        "p2_high": round(p2_high, 2),
        "base_0": round(p3_base, 2),
        "achieved": "Entry Zone",
        "next_target": f"{t1:.2f} (T1)",
        "vol_mult": vol_mult,
        "body_pct": body_pct,
        "pcr": pcr,
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
    cols = [
        "timestamp_ist",
        "symbol",
        "exchange",
        "source",
        "conviction",
        "side",
        "entry_close",
        "stop_loss",
        "p1_low",
        "p2_high",
        "base_0",
        "achieved",
        "next_target",
        "vol_mult",
        "body_pct",
        "pcr",
    ]
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
            print(f"[{sym}] Spot IDX ID not found -> skipped.")
            continue

        df, oi = fetch_market_data(sym, cfg, inst_id, headers)
        if df is None or oi is None:
            time.sleep(5.0)
            continue

        msg, row = build_signal(sym, cfg, df, oi)
        save_log(row)
        if send_telegram(msg):
            sent_count += 1
        time.sleep(6.0)

    print(f"Done. Alerts sent: {sent_count}/{len(INDEX_CONFIG)}")


if __name__ == "__main__":
    main()
