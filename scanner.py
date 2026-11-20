def fetch_market_data(symbol: str, cfg: dict, inst_id: str, headers: dict):
    min_p = cfg["min_price"]
    max_p = cfg["max_price"]

    now_ist = datetime.now(IST)
    from_ist = (now_ist - timedelta(days=5)).replace(hour=9, minute=15, second=0, microsecond=0)
    to_ist = now_ist.replace(microsecond=0)

    fmt_candidates = [
        (from_ist.strftime("%Y-%m-%d %H:%M:%S"), to_ist.strftime("%Y-%m-%d %H:%M:%S")),
        (from_ist.strftime("%Y-%m-%dT%H:%M:%S+05:30"), to_ist.strftime("%Y-%m-%dT%H:%M:%S+05:30")),
        (from_ist.strftime("%Y-%m-%dT%H:%M:%S"), to_ist.strftime("%Y-%m-%dT%H:%M:%S")),
    ]

    df = None
    for f_str, t_str in fmt_candidates:
        for attempt in range(2):
            c_resp = safe_get(
                f"{SAHI_API_BASE_URL}/v1/marketdata/candles",
                headers=headers,
                params={
                    "i": int(inst_id) if inst_id.isdigit() else inst_id,
                    "instrument_id": int(inst_id) if inst_id.isdigit() else inst_id,
                    "size": "5m",
                    "from": f_str,
                    "to": t_str,
                },
            )
            if c_resp is None:
                continue

            print(f"[{symbol}] Candles HTTP {c_resp.status_code} ({f_str})")
            if c_resp.status_code == 429:
                print(f"[{symbol}] Rate limited -> waiting 8s...")
                time.sleep(8.0)
                continue

            if c_resp.status_code == 400:
                print(f"[{symbol}] Candles body: {c_resp.text[:200]}")
                break

            if c_resp.status_code == 200:
                try:
                    df = parse_candles(c_resp.json(), min_p, max_p)
                except Exception:
                    df = None
                break

        if df is not None:
            break
        time.sleep(2.0)

    if df is None:
        print(f"[{symbol}] Real 5m candles not available -> skipped.")
        return None, None

    time.sleep(3.0)

    oc_resp = safe_get(
        f"{SAHI_API_BASE_URL}/v1/marketdata/optionchain",
        headers=headers,
        params={"underlying_id": int(inst_id) if inst_id.isdigit() else inst_id},
    )
    oi = {"pcr": 1.0, "call_oi": 0.0, "put_oi": 0.0, "source": "Standard"}
    if oc_resp is not None and oc_resp.status_code == 200:
        try:
            oi = parse_option_chain(oc_resp.json())
        except Exception:
            pass

    return df, oi
