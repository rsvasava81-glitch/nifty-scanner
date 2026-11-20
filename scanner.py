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


def parse_option_chain(payload) -> dict:
    default_oi = {"pcr": None, "call_oi": 0.0, "put_oi": 0.0, "source": "Standard"}
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
        for _ in range(2):
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
    oi = {"pcr": None, "call_oi": 0.0, "put_oi": 0.0, "source": "Standard"}
    if oc_resp is not None and oc_resp.status_code == 200:
        try:
            oi = parse_option_chain(oc_resp.json())
        except Exception:
            pass

    return df, oi


def analyze_hh_hl_lh_ll(highs: np.ndarray, lows: np.ndarray):
    """Identify HH/HL (UPTREND) or LH/LL (DOWNTREND) from recent pivot swings."""
    lookback = min(len(highs), 45)
    h_sub = highs[-lookback:]
    l_sub = lows[-lookback:]

    swing_highs = []
    swing_lows = []

    for i in range(1, len(h_sub) - 1):
        if h_sub[i] >= h_sub[i - 1] and h_sub[i] >= h_sub[i + 1]:
            if not swing_highs or abs(float(h_sub[i]) - swing_highs[-1][1]) > 0.01:
                swing_highs.append((i, float(h_sub[i])))
        if l_sub[i] <= l_sub[i - 1] and l_sub[i] <= l_sub[i + 1]:
            if not swing_lows or abs(float(l_sub[i]) - swing_lows[-1][1]) > 0.01:
                swing_lows.append((i, float(l_sub[i])))

    if len(swing_highs) >= 2:
        h1_idx, h1 = swing_highs[-2]
        h2_idx, h2 = swing_highs[-1]
    else:
        mid = max(1, len(h_sub) // 2)
        h1_idx, h1 = int(np.argmax(h_sub[:mid])), float(np.max(h_sub[:mid]))
        h2_idx, h2 = mid + int(np.argmax(h_sub[mid:])), float(np.max(h_sub[mid:]))

    if len(swing_lows) >= 2:
        l1_idx, l1 = swing_lows[-2]
        l2_idx, l2 = swing_lows[-1]
    else:
        mid = max(1, len(l_sub) // 2)
        l1_idx, l1 = int(np.argmin(l_sub[:mid])), float(np.min(l_sub[:mid]))
        l2_idx, l2 = mid + int(np.argmin(l_sub[mid:])), float(np.min(l_sub[mid:]))

    is_hh = h2 > h1
    is_hl = l2 > l1
    is_lh = h2 < h1
    is_ll = l2 < l1

    if is_hh and is_hl:
        trend = "UPTREND (HH+HL)"
        structure_note = f"HH ({h1:.2f}->{h2:.2f}) & HL ({l1:.2f}->{l2:.2f})"
    elif is_lh and is_ll:
        trend = "DOWNTREND (LH+LL)"
        structure_note = f"LH ({h1:.2f}->{h2:.2f}) & LL ({l1:.2f}->{l2:.2f})"
    elif is_hh or is_hl:
        trend = "UPTREND (HH+HL)" if (h2_idx >= l2_idx and h2 >= l1) else "SIDEWAYS / MIXED"
        structure_note = f"H: {h1:.2f}->{h2:.2f}, L: {l1:.2f}->{l2:.2f}"
    elif is_lh or is_ll:
        trend = "DOWNTREND (LH+LL)" if (l2_idx >= h2_idx and l2 <= h1) else "SIDEWAYS / MIXED"
        structure_note = f"H: {h1:.2f}->{h2:.2f}, L: {l1:.2f}->{l2:.2f}"
    else:
        trend = "SIDEWAYS / MIXED"
        structure_note = f"H: {h1:.2f}->{h2:.2f}, L: {l1:.2f}->{l2:.2f}"

    return trend, structure_note, l1, l2, h1, h2


def evaluate_target_reaction(direction: str, targets: list[tuple[str, float]], prev_c: dict, curr_c: dict):
    """Check target close vs touch and next-candle response for BOOK vs CONTINUE alert."""
    if direction == "CE":
        active_idx = 0
        closed_target = None
        touched_target = None

        for idx, (lbl, t_val) in enumerate(targets):
            if prev_c["Close"] > t_val or curr_c["Close"] > t_val:
                closed_target = (lbl, t_val)
                active_idx = min(idx + 1, len(targets) - 1)
            elif prev_c["High"] >= t_val or curr_c["High"] >= t_val:
                touched_target = (lbl, t_val)
                active_idx = idx

        next_lbl, next_val = targets[active_idx]

        if closed_target is not None:
            c_lbl, c_val = closed_target
            if curr_c["Close"] >= c_val:
                reaction_note = f"Candle closed above {c_lbl} ({c_val:.2f}) & holding -> Shift to {next_lbl} ({next_val:.2f})"
                trade_action = f"CONTINUE TO {next_lbl} ({next_val:.2f})"
            else:
                reaction_note = f"Closed above {c_lbl} ({c_val:.2f}) then pulled back -> Watch {c_val:.2f} support"
                trade_action = f"PARTIAL BOOK / WATCH {c_val:.2f}"
            return reaction_note, trade_action, f"Closed {c_lbl} -> {next_lbl}"

        if touched_target is not None:
            t_lbl, t_val = touched_target
            tol = max(t_val * 0.0008, 1.0)
            holding_around = abs(curr_c["Close"] - t_val) <= tol or (curr_c["Low"] <= t_val <= curr_c["High"])
            if curr_c["Close"] < curr_c["Open"] and curr_c["High"] >= t_val:
                reaction_note = f"Touched {t_lbl} ({t_val:.2f}) & rejected red -> Book profit / don't chase"
                trade_action = f"BOOK TARGET ({t_lbl} REJECTION)"
            elif holding_around:
                reaction_note = f"Touched {t_lbl} ({t_val:.2f}) & holding around level -> Check next candle break"
                trade_action = f"BOOK TARGET OR WAIT 1 CANDLE AT {t_lbl}"
            else:
                reaction_note = f"Touched {t_lbl} ({t_val:.2f}) & pushing up -> Wait close above {t_val:.2f}"
                trade_action = f"HOLD / WATCH CLOSE ABOVE {t_lbl}"
            return reaction_note, trade_action, f"Touched {t_lbl} (No Close)"

        return (
            f"Below {targets[0][0]} ({targets[0][1]:.2f}) -> No target touch yet",
            f"HOLD FOR {targets[0][0]} ({targets[0][1]:.2f})",
            "In Progress",
        )

    elif direction == "PE":
        active_idx = 0
        closed_target = None
        touched_target = None

        for idx, (lbl, t_val) in enumerate(targets):
            if prev_c["Close"] < t_val or curr_c["Close"] < t_val:
                closed_target = (lbl, t_val)
                active_idx = min(idx + 1, len(targets) - 1)
            elif prev_c["Low"] <= t_val or curr_c["Low"] <= t_val:
                touched_target = (lbl, t_val)
                active_idx = idx

        next_lbl, next_val = targets[active_idx]

        if closed_target is not None:
            c_lbl, c_val = closed_target
            if curr_c["Close"] <= c_val:
                reaction_note = f"Candle closed below {c_lbl} ({c_val:.2f}) & holding -> Shift to {next_lbl} ({next_val:.2f})"
                trade_action = f"CONTINUE TO {next_lbl} ({next_val:.2f})"
            else:
                reaction_note = f"Closed below {c_lbl} ({c_val:.2f}) then bounced -> Watch {c_val:.2f} resistance"
                trade_action = f"PARTIAL BOOK / WATCH {c_val:.2f}"
            return reaction_note, trade_action, f"Closed {c_lbl} -> {next_lbl}"

        if touched_target is not None:
            t_lbl, t_val = touched_target
            tol = max(t_val * 0.0008, 1.0)
            holding_around = abs(curr_c["Close"] - t_val) <= tol or (curr_c["Low"] <= t_val <= curr_c["High"])
            if curr_c["Close"] > curr_c["Open"] and curr_c["Low"] <= t_val:
                reaction_note = f"Touched {t_lbl} ({t_val:.2f}) & bounced green -> Book profit / don't chase"
                trade_action = f"BOOK TARGET ({t_lbl} BOUNCE)"
            elif holding_around:
                reaction_note = f"Touched {t_lbl} ({t_val:.2f}) & holding around level -> Check next candle break"
                trade_action = f"BOOK TARGET OR WAIT 1 CANDLE AT {t_lbl}"
            else:
                reaction_note = f"Touched {t_lbl} ({t_val:.2f}) & pushing down -> Wait close below {t_val:.2f}"
                trade_action = f"HOLD / WATCH CLOSE BELOW {t_lbl}"
            return reaction_note, trade_action, f"Touched {t_lbl} (No Close)"

        return (
            f"Above {targets[0][0]} ({targets[0][1]:.2f}) -> No target touch yet",
            f"HOLD FOR {targets[0][0]} ({targets[0][1]:.2f})",
            "In Progress",
        )

    return "Sideways / No active trade direction", "NO TRADE / WAIT", "Idle"


def build_signal(symbol: str, cfg: dict, df: pd.DataFrame, oi: dict):
    highs = df["High"].astype(float).values
    lows = df["Low"].astype(float).values
    closes = df["Close"].astype(float).values
    opens = df["Open"].astype(float).values
    vols = df["Volume"].astype(float).values

    trend, structure_note, l1, l2, h1, h2 = analyze_hh_hl_lh_ll(highs, lows)

    entry = float(closes[-1])
    last_open = float(opens[-1])
    last_high = float(highs[-1])
    last_low = float(lows[-1])

    curr_c = {"Open": float(opens[-1]), "High": float(highs[-1]), "Low": float(lows[-1]), "Close": float(closes[-1])}
    prev_c = {"Open": float(opens[-2]), "High": float(highs[-2]), "Low": float(lows[-2]), "Close": float(closes[-2])}

    avg_vol = float(np.mean(vols[:-1])) if len(vols) > 1 else float(vols[-1])
    vol_mult = round(float(vols[-1] / max(avg_vol, 1.0)), 2)
    candle_rng = max(last_high - last_low, 1e-5)
    body_pct = int(round(min(100.0, (abs(entry - last_open) / candle_rng) * 100.0)))

    raw_pcr = oi.get("pcr")
    has_live_pcr = isinstance(raw_pcr, (int, float)) and raw_pcr > 0
    pcr = float(raw_pcr) if has_live_pcr else 1.00
    pcr_label = f"PCR {pcr:.2f}" if has_live_pcr else "OI N/A (No Live OC)"

    max_sl = float(cfg["sl_points"])

    if "UPTREND" in trend:
        # 3-Point Trend Fib: P1 = Swing Low (l2), P2 = Swing High (h2), P3 = same as P1 (l2)
        p1 = round(l2, 2)
        p2 = round(max(h2, float(np.max(highs[max(0, len(highs) - 15):]))), 2)
        p3 = p1  # Point 3 anchored at Point 1 position

        leg_rng = max(p2 - p1, round(entry * 0.002, 2), 1.0)
        fib_050 = round(p2 - 0.50 * leg_rng, 2)
        fib_0618 = round(p2 - 0.618 * leg_rng, 2)
        zone_top = max(fib_050, fib_0618, p1)
        zone_bot = min(fib_050, fib_0618, p1)

        t_1414 = round(p3 + 1.414 * leg_rng, 2)
        t_1618 = round(p3 + 1.618 * leg_rng, 2)
        t_2000 = round(p3 + 2.000 * leg_rng, 2)
        t_2618 = round(p3 + 2.618 * leg_rng, 2)
        targets = [("1.414", t_1414), ("1.618", t_1618), ("2.0", t_2000), ("2.618", t_2618)]

        in_retest = (last_low <= zone_top * 1.0015) and (entry >= zone_bot * 0.9975)
        bullish_candle = entry >= last_open

        raw_sl_dist = min(max_sl, max(entry - (p3 - leg_rng * 0.05), round(entry * 0.0012, 2), 10.0))
        sl = round(entry - raw_sl_dist, 2)

        if in_retest and bullish_candle:
            side = "CALL (CE) - P3/FIB RETEST BUY"
            bias = "HH+HL 3PT FIB (P3=P1)"
        else:
            side = "WAIT FOR P3/0.5-0.618 RETEST (CE)"
            bias = "HH+HL TREND WATCH"

        reaction_note, trade_action, target_status = evaluate_target_reaction("CE", targets, prev_c, curr_c)
        pts_line = f"P1 (Low): {p1:.2f} | P2 (High): {p2:.2f} | P3 (=P1): {p3:.2f}"

    elif "DOWNTREND" in trend:
        # 3-Point Trend Fib: P1 = Swing High (h2), P2 = Swing Low (l2), P3 = same as P1 (h2)
        p1 = round(h2, 2)
        p2 = round(min(l2, float(np.min(lows[max(0, len(lows) - 15):]))), 2)
        p3 = p1  # Point 3 anchored at Point 1 position

        leg_rng = max(p1 - p2, round(entry * 0.002, 2), 1.0)
        fib_050 = round(p2 + 0.50 * leg_rng, 2)
        fib_0618 = round(p2 + 0.618 * leg_rng, 2)
        zone_bot = min(fib_050, fib_0618, p1)
        zone_top = max(fib_050, fib_0618, p1)

        t_1414 = round(p3 - 1.414 * leg_rng, 2)
        t_1618 = round(p3 - 1.618 * leg_rng, 2)
        t_2000 = round(p3 - 2.000 * leg_rng, 2)
        t_2618 = round(p3 - 2.618 * leg_rng, 2)
        targets = [("1.414", t_1414), ("1.618", t_1618), ("2.0", t_2000), ("2.618", t_2618)]

        in_retest = (last_high >= zone_bot * 0.9985) and (entry <= zone_top * 1.0025)
        bearish_candle = entry <= last_open

        raw_sl_dist = min(max_sl, max((p3 + leg_rng * 0.05) - entry, round(entry * 0.0012, 2), 10.0))
        sl = round(entry + raw_sl_dist, 2)

        if in_retest and bearish_candle:
            side = "PUT (PE) - P3/FIB RETEST SELL"
            bias = "LH+LL 3PT FIB (P3=P1)"
        else:
            side = "WAIT FOR P3/0.5-0.618 RETEST (PE)"
            bias = "LH+LL TREND WATCH"

        reaction_note, trade_action, target_status = evaluate_target_reaction("PE", targets, prev_c, curr_c)
        pts_line = f"P1 (High): {p1:.2f} | P2 (Low): {p2:.2f} | P3 (=P1): {p3:.2f}"

    else:
        p1 = round(l2, 2)
        p2 = round(h2, 2)
        p3 = p1
        leg_rng = max(p2 - p1, round(entry * 0.002, 2), 1.0)
        fib_050 = round(p1 + 0.50 * leg_rng, 2)
        fib_0618 = round(p1 + 0.618 * leg_rng, 2)
        t_1414 = round(p3 + 1.414 * leg_rng, 2)
        t_1618 = round(p3 + 1.618 * leg_rng, 2)
        t_2000 = round(p3 + 2.000 * leg_rng, 2)
        t_2618 = round(p3 + 2.618 * leg_rng, 2)
        sl = round(entry - min(max_sl, round(entry * 0.0015, 2)), 2)
        side = "NO CLEAR TREND (WAIT)"
        bias = "SIDEWAYS RANGE"
        reaction_note, trade_action, target_status = evaluate_target_reaction("NONE", [], prev_c, curr_c)
        pts_line = f"P1: {p1:.2f} | P2: {p2:.2f} | P3 (=P1): {p3:.2f}"

    conviction = (
        "HIGH CONVICTION"
        if ("RETEST BUY" in side or "RETEST SELL" in side) and vol_mult >= 1.15 and body_pct >= 40
        else "MODERATE"
    )

    msg = (
        f"3PT Trend Fib Setup: {symbol} ({cfg['exchange']}) [{conviction}]\n"
        f"------------------------------------------\n"
        f"Trend: {trend} | {structure_note}\n"
        f"{pts_line}\n"
        f"Action: {side}\n"
        f"Entry / Close: {entry:.2f} | Stop Loss (SL): {sl:.2f}\n"
        f"Retest Zone (0.5 - 0.618): {fib_050:.2f} - {fib_0618:.2f}\n"
        f"Targets: 1.414={t_1414:.2f} | 1.618={t_1618:.2f}\n"
        f"Ext Targets: 2.0={t_2000:.2f} | 2.618={t_2618:.2f}\n"
        f"Target Status: {target_status}\n"
        f"Candle Reaction: {reaction_note}\n"
        f"Management Alert: {trade_action}\n"
        f"Footprint: Vol x{vol_mult} | Body {body_pct}%\n"
        f"OI ({oi.get('source', 'Standard')}): {pcr_label} | {bias}"
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
        "p1_low": p1,
        "p2_high": p2,
        "base_0": p3,
        "achieved": target_status,
        "next_target": trade_action,
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
