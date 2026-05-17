"""Live market data provider — CryptoCompare + CoinPaprika + Alternative.me.

Data sources:
- CryptoCompare /data/v2/histoday — BTC + ETH daily price history (365d)
- CoinPaprika /v1/global — current BTC dominance, total market cap
- CoinPaprika /v1/tickers — current coin market caps for calibration
- Alternative.me /fng/ — Fear & Greed index history (365d)

Historical dominance is modeled from price histories + current snapshot anchor.
"""
import time
import math
import logging
import requests
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger("macro_v2.live_data")

_cache = {
    "btc_hist": {"data": None, "ts": 0},
    "eth_hist": {"data": None, "ts": 0},
    "global": {"data": None, "ts": 0},
    "tickers": {"data": None, "ts": 0},
    "fng": {"data": None, "ts": 0},
    "series": {"data": None, "ts": 0},
}

HISTORY_CACHE_TTL = 900
SNAPSHOT_CACHE_TTL = 120
SERIES_CACHE_TTL = 600

CC_BASE = "https://min-api.cryptocompare.com"
CP_BASE = "https://api.coinpaprika.com/v1"
FNG_URL = "https://api.alternative.me/fng/"
REQUEST_TIMEOUT = 15


def _fetch_json(url, params=None):
    try:
        resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT, headers={
            "Accept": "application/json",
        })
        if resp.status_code == 200:
            return resp.json()
        logger.warning("API %s returned %d", url, resp.status_code)
    except Exception as e:
        logger.warning("API %s failed: %s", url, e)
    return None


def _get_cached(key, ttl, fetcher):
    now = time.time()
    c = _cache[key]
    if c["data"] is not None and (now - c["ts"]) < ttl:
        return c["data"]
    data = fetcher()
    if data is not None:
        c["data"] = data
        c["ts"] = now
    return c["data"]


def _fetch_cc_histoday(fsym, limit=365):
    """Fetch daily OHLCV from CryptoCompare."""
    d = _fetch_json(f"{CC_BASE}/data/v2/histoday", {"fsym": fsym, "tsym": "USD", "limit": limit})
    if d and d.get("Response") == "Success":
        return d["Data"]["Data"]
    return None


def fetch_btc_history():
    return _get_cached("btc_hist", HISTORY_CACHE_TTL, lambda: _fetch_cc_histoday("BTC", 365))


def fetch_eth_history():
    return _get_cached("eth_hist", HISTORY_CACHE_TTL, lambda: _fetch_cc_histoday("ETH", 365))


def fetch_global():
    return _get_cached("global", SNAPSHOT_CACHE_TTL, lambda: _fetch_json(f"{CP_BASE}/global"))


def fetch_tickers_top():
    """Fetch top tickers from CoinPaprika for calibration."""
    def _fetch():
        data = _fetch_json(f"{CP_BASE}/tickers", {"quotes": "USD"})
        if not data or not isinstance(data, list):
            return None
        top = {}
        for c in data[:50]:
            q = c.get("quotes", {}).get("USD", {})
            top[c["symbol"]] = {
                "price": q.get("price", 0),
                "market_cap": q.get("market_cap", 0),
            }
        return top
    return _get_cached("tickers", SNAPSHOT_CACHE_TTL, _fetch)


def fetch_fear_greed(limit=365):
    return _get_cached("fng", HISTORY_CACHE_TTL,
                       lambda: _fetch_json(FNG_URL, {"limit": limit, "format": "json"}))


def build_live_series(limit=365):
    """Build macro series from live API data.

    Returns list of {t, btcPrice, altIndex, btcDom, stableDom, fearGreed, marketVol}.
    """
    now = time.time()
    cached = _cache["series"]
    if cached["data"] is not None and (now - cached["ts"]) < SERIES_CACHE_TTL:
        stored = cached["data"]
        if len(stored) >= min(limit, 30):
            return stored[-limit:] if len(stored) > limit else stored

    logger.info("Building live series from CryptoCompare + CoinPaprika + Alternative.me...")

    # Fetch all data sources in parallel (different APIs, no rate limit conflict)
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {
            pool.submit(fetch_btc_history): "btc_hist",
            pool.submit(fetch_eth_history): "eth_hist",
            pool.submit(fetch_global): "global",
            pool.submit(fetch_tickers_top): "tickers",
            pool.submit(lambda: fetch_fear_greed(limit)): "fng",
        }
        results = {}
        for f in as_completed(futures):
            results[futures[f]] = f.result()

    btc_hist = results.get("btc_hist")
    eth_hist = results.get("eth_hist")
    global_data = results.get("global")
    tickers = results.get("tickers")
    fng_data = results.get("fng")

    if not btc_hist or len(btc_hist) < 10:
        logger.warning("BTC history unavailable — cannot build live series")
        return None

    # Current market state from CoinPaprika for anchoring
    current_total_mcap = 2.4e12
    if global_data:
        current_total_mcap = global_data.get("market_cap_usd", 2.4e12)

    # Current market caps from tickers
    current_btc_mcap = 0
    current_eth_mcap = 0
    current_stable_mcap = 0
    if tickers:
        current_btc_mcap = tickers.get("BTC", {}).get("market_cap", 0)
        current_eth_mcap = tickers.get("ETH", {}).get("market_cap", 0)
        for sym in ("USDT", "USDC", "DAI", "BUSD"):
            current_stable_mcap += tickers.get(sym, {}).get("market_cap", 0)

    # BTC supply estimate (for historical mcap calc)
    btc_latest_price = btc_hist[-1]["close"] if btc_hist else 67000
    btc_supply = current_btc_mcap / btc_latest_price if btc_latest_price > 0 and current_btc_mcap > 0 else 19_700_000

    # ETH supply estimate
    eth_latest_price = eth_hist[-1]["close"] if eth_hist else 2000
    eth_supply = current_eth_mcap / eth_latest_price if eth_latest_price > 0 and current_eth_mcap > 0 else 120_000_000

    # Build ETH price lookup by timestamp
    eth_by_ts = {}
    if eth_hist:
        for p in eth_hist:
            eth_by_ts[p["time"]] = p["close"]

    # Build F&G lookup by date
    fng_by_date = {}
    if fng_data and "data" in fng_data:
        for entry in fng_data["data"]:
            ts = int(entry.get("timestamp", 0))
            if ts:
                day = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
                fng_by_date[day] = float(entry.get("value", 50))

    # "Other alts" mcap current
    other_mcap_now = max(0, current_total_mcap - current_btc_mcap - current_eth_mcap - current_stable_mcap)

    points = []
    prev_btc_close = None

    for p in btc_hist:
        ts = p["time"]
        btc_close = p["close"]
        if btc_close <= 0:
            continue

        # Historical BTC market cap
        btc_mcap = btc_close * btc_supply

        # Historical ETH market cap
        eth_price = eth_by_ts.get(ts, eth_latest_price)
        eth_mcap = eth_price * eth_supply

        # Stable mcap: roughly constant (stablecoins don't swing much)
        stable_mcap = current_stable_mcap if current_stable_mcap > 0 else current_total_mcap * 0.075

        # Other alts: scale with ETH performance relative to current
        eth_ratio = eth_price / eth_latest_price if eth_latest_price > 0 else 1.0
        other_mcap = other_mcap_now * eth_ratio

        # Estimated total market cap
        total_mcap = btc_mcap + eth_mcap + stable_mcap + other_mcap
        if total_mcap <= 0:
            total_mcap = btc_mcap * 1.8

        # Dominance
        btc_dom = (btc_mcap / total_mcap) * 100
        stable_dom = (stable_mcap / total_mcap) * 100

        # Alt index: alt market cap in billions
        alt_mcap = max(0, total_mcap - btc_mcap - stable_mcap)
        alt_index = alt_mcap / 1e9

        # Fear & Greed
        day_str = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
        fg = fng_by_date.get(day_str, 50.0)

        # Volatility: absolute daily log return
        if prev_btc_close and prev_btc_close > 0:
            market_vol = abs(math.log(btc_close / prev_btc_close))
        else:
            market_vol = 0.02

        points.append({
            "t": ts,
            "btcPrice": round(btc_close, 2),
            "altIndex": round(alt_index, 2),
            "btcDom": round(max(30, min(80, btc_dom)), 2),
            "stableDom": round(max(2, min(25, stable_dom)), 2),
            "fearGreed": round(max(1, min(99, fg)), 1),
            "marketVol": round(market_vol, 4),
        })
        prev_btc_close = btc_close

    if len(points) < 10:
        logger.warning("Only %d live points — insufficient", len(points))
        return None

    last = points[-1]
    logger.info("Live series: %d pts, BTC=$%.0f, btcDom=%.1f%%, stableDom=%.1f%%, F&G=%.0f",
                len(points), last["btcPrice"], last["btcDom"], last["stableDom"], last["fearGreed"])

    _cache["series"]["data"] = points
    _cache["series"]["ts"] = time.time()
    return points[-limit:] if len(points) > limit else points


def get_live_snapshot():
    """Quick current snapshot from CoinPaprika + Alternative.me."""
    global_data = fetch_global()
    fng_data = fetch_fear_greed(1)
    tickers = fetch_tickers_top()

    if not global_data:
        return None

    btc_dom = global_data.get("bitcoin_dominance_percentage", 55.0)
    total_mcap = global_data.get("market_cap_usd", 0)

    btc_price = 0
    stable_mcap = 0
    if tickers:
        btc_price = tickers.get("BTC", {}).get("price", 0)
        for sym in ("USDT", "USDC", "DAI", "BUSD"):
            stable_mcap += tickers.get(sym, {}).get("market_cap", 0)

    stable_dom = (stable_mcap / total_mcap * 100) if total_mcap > 0 else 7.5
    alt_mcap = max(0, total_mcap - total_mcap * btc_dom / 100 - stable_mcap)
    alt_index = alt_mcap / 1e9

    fg = 50.0
    if fng_data and "data" in fng_data and fng_data["data"]:
        fg = float(fng_data["data"][0].get("value", 50))

    return {
        "asOf": int(time.time()),
        "fearGreed": round(fg, 1),
        "btcDom": round(btc_dom, 2),
        "stableDom": round(stable_dom, 2),
        "btcPrice": round(btc_price, 2),
        "altIndex": round(alt_index, 2),
        "marketVol": 0.02,
    }


def is_live_available():
    """Quick health check — can we reach CryptoCompare?"""
    try:
        resp = requests.get(f"{CC_BASE}/data/v2/histoday",
                            params={"fsym": "BTC", "tsym": "USD", "limit": 1},
                            timeout=5)
        if resp.status_code == 200:
            d = resp.json()
            return d.get("Response") == "Success"
    except Exception:
        pass
    return False
