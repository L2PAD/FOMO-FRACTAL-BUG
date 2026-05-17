"""BTC ↔ SPX Hybrid Layer — cross-market correlation intelligence.

Computes:
- 30d rolling correlation between BTC and SPX daily returns
- BTC beta to SPX
- SPX regime (trend via EMA20/EMA50 + sigmoid)
- Divergence score (BTC vs expected move from SPX)
- Hybrid confidence impact adjustment

Data from Yahoo Finance (no API key required).
"""
import time
import math
import logging
import statistics
import requests
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger("macro_v2.hybrid")

_cache = {
    "spx": {"data": None, "ts": 0},
    "btc_yf": {"data": None, "ts": 0},
    "result": {"data": None, "ts": 0},
}

CACHE_TTL_HISTORY = 900  # 15 min
CACHE_TTL_RESULT = 300   # 5 min
YF_BASE = "https://query1.finance.yahoo.com/v8/finance/chart"
CORR_WINDOW = 30
EMA_FAST = 20
EMA_SLOW = 50


def _fetch_yf_chart(symbol, range_str="1y", interval="1d"):
    """Fetch OHLCV from Yahoo Finance."""
    try:
        resp = requests.get(
            f"{YF_BASE}/{symbol}",
            params={"interval": interval, "range": range_str},
            headers={"User-Agent": "MarketCoreEngine/1.0"},
            timeout=15,
        )
        if resp.status_code != 200:
            logger.warning("YF %s returned %d", symbol, resp.status_code)
            return None
        data = resp.json()
        result = data.get("chart", {}).get("result", [])
        if not result:
            return None
        r = result[0]
        timestamps = r.get("timestamp", [])
        quotes = r.get("indicators", {}).get("quote", [{}])[0]
        closes = quotes.get("close", [])
        if len(timestamps) != len(closes):
            return None
        # Filter out None values
        points = []
        for ts, c in zip(timestamps, closes):
            if c is not None and ts is not None:
                points.append({"t": ts, "close": float(c)})
        return points
    except Exception as e:
        logger.warning("YF fetch %s failed: %s", symbol, e)
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


def _fetch_spx():
    return _fetch_yf_chart("%5EGSPC", "1y", "1d")


def _fetch_btc_yf():
    return _fetch_yf_chart("BTC-USD", "1y", "1d")


def _log_returns(prices):
    """Compute log returns from price series."""
    returns = []
    for i in range(1, len(prices)):
        if prices[i - 1] > 0 and prices[i] > 0:
            returns.append(math.log(prices[i] / prices[i - 1]))
        else:
            returns.append(0.0)
    return returns


def _ema(values, span):
    """Exponential moving average."""
    if not values:
        return 0.0
    alpha = 2.0 / (span + 1)
    ema = values[0]
    for v in values[1:]:
        ema = alpha * v + (1 - alpha) * ema
    return ema


def _sigmoid(x):
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def _correlation(xs, ys):
    """Pearson correlation between two equal-length lists."""
    n = min(len(xs), len(ys))
    if n < 5:
        return 0.0
    xs, ys = xs[:n], ys[:n]
    mx = sum(xs) / n
    my = sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / n
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs) / n)
    sy = math.sqrt(sum((y - my) ** 2 for y in ys) / n)
    if sx < 1e-10 or sy < 1e-10:
        return 0.0
    return max(-1.0, min(1.0, cov / (sx * sy)))


def _align_by_date(btc_points, spx_points):
    """Align BTC and SPX data by date (trading days only)."""
    spx_by_date = {}
    for p in spx_points:
        day = datetime.fromtimestamp(p["t"], tz=timezone.utc).strftime("%Y-%m-%d")
        spx_by_date[day] = p["close"]

    aligned_btc = []
    aligned_spx = []
    for p in btc_points:
        day = datetime.fromtimestamp(p["t"], tz=timezone.utc).strftime("%Y-%m-%d")
        if day in spx_by_date:
            aligned_btc.append(p["close"])
            aligned_spx.append(spx_by_date[day])

    return aligned_btc, aligned_spx


def compute_hybrid(riskoff_prob=0.5):
    """Compute BTC ↔ SPX hybrid layer metrics.

    Args:
        riskoff_prob: Current macro risk-off probability (for hybrid impact scaling)

    Returns:
        dict with correlation30d, beta, spxRegime, trendScore,
        divergenceScore, hybridImpact
    """
    now = time.time()
    cached = _cache["result"]
    if cached["data"] is not None and (now - cached["ts"]) < CACHE_TTL_RESULT:
        # Re-scale hybridImpact with current riskoff
        result = dict(cached["data"])
        result["hybridImpact"] = _compute_impact(
            result["correlation30d"], result["trendScore"], riskoff_prob
        )
        return result

    # Fetch data in parallel
    with ThreadPoolExecutor(max_workers=2) as pool:
        f_spx = pool.submit(lambda: _get_cached("spx", CACHE_TTL_HISTORY, _fetch_spx))
        f_btc = pool.submit(lambda: _get_cached("btc_yf", CACHE_TTL_HISTORY, _fetch_btc_yf))
        spx_data = f_spx.result()
        btc_data = f_btc.result()

    if not spx_data or not btc_data or len(spx_data) < 50 or len(btc_data) < 50:
        logger.warning("Insufficient data for hybrid layer (SPX=%s, BTC=%s)",
                        len(spx_data) if spx_data else 0,
                        len(btc_data) if btc_data else 0)
        return _fallback_result()

    # Align by trading day
    btc_prices, spx_prices = _align_by_date(btc_data, spx_data)
    if len(btc_prices) < 50:
        logger.warning("Only %d aligned days — need at least 50", len(btc_prices))
        return _fallback_result()

    # Log returns
    btc_rets = _log_returns(btc_prices)
    spx_rets = _log_returns(spx_prices)

    # 1. 30d Rolling Correlation
    corr_30d = _correlation(btc_rets[-CORR_WINDOW:], spx_rets[-CORR_WINDOW:])

    # 2. BTC Beta to SPX: cov(btc, spx) / var(spx)
    n = min(len(btc_rets), len(spx_rets), CORR_WINDOW)
    br = btc_rets[-n:]
    sr = spx_rets[-n:]
    mean_sr = sum(sr) / n
    var_spx = sum((s - mean_sr) ** 2 for s in sr) / n
    mean_br = sum(br) / n
    cov_bs = sum((b - mean_br) * (s - mean_sr) for b, s in zip(br, sr)) / n
    beta = cov_bs / var_spx if var_spx > 1e-12 else 1.0
    beta = max(-5.0, min(5.0, beta))

    # 3. SPX Regime: EMA20 vs EMA50 trend strength
    ema_fast = _ema(spx_prices[-EMA_SLOW:], EMA_FAST)
    ema_slow = _ema(spx_prices[-EMA_SLOW:], EMA_SLOW)
    spx_vol = statistics.stdev(spx_rets[-30:]) if len(spx_rets) >= 30 else 0.01
    trend_raw = (ema_fast - ema_slow) / (spx_prices[-1] if spx_prices[-1] > 0 else 1)
    trend_score = _sigmoid(trend_raw / max(spx_vol, 0.001))

    if trend_score > 0.6:
        spx_regime = "RISK_ON"
    elif trend_score < 0.4:
        spx_regime = "RISK_OFF"
    else:
        spx_regime = "NEUTRAL"

    # 4. Divergence Score
    btc_7d_ret = sum(btc_rets[-7:]) if len(btc_rets) >= 7 else 0
    spx_7d_ret = sum(spx_rets[-7:]) if len(spx_rets) >= 7 else 0
    expected_btc = beta * spx_7d_ret
    div_raw = btc_7d_ret - expected_btc
    ret_std = statistics.stdev(btc_rets[-30:]) if len(btc_rets) >= 30 else 0.03
    div_score = math.tanh(div_raw / max(ret_std, 0.001))
    div_score = max(-1.0, min(1.0, div_score))

    if div_score > 0.4:
        div_state = "BTC_OUTPERFORMS"
    elif div_score < -0.4:
        div_state = "BTC_UNDERPERFORMS"
    else:
        div_state = "NEUTRAL"

    # 5. Hybrid Impact
    hybrid_impact = _compute_impact(corr_30d, trend_score, riskoff_prob)

    result = {
        "ok": True,
        "correlation30d": round(corr_30d, 3),
        "beta": round(beta, 2),
        "spxRegime": spx_regime,
        "trendScore": round(trend_score, 3),
        "divergenceScore": round(div_score, 3),
        "divergenceState": div_state,
        "hybridImpact": round(hybrid_impact, 3),
        "meta": {
            "alignedDays": len(btc_prices),
            "spxLast": round(spx_prices[-1], 2),
            "btcLast": round(btc_prices[-1], 2),
            "spx7dReturn": round(spx_7d_ret * 100, 2),
            "btc7dReturn": round(btc_7d_ret * 100, 2),
        },
    }

    _cache["result"]["data"] = result
    _cache["result"]["ts"] = now

    logger.info("Hybrid layer: corr=%.2f, beta=%.2f, spx=%s, div=%.2f, impact=%.3f",
                corr_30d, beta, spx_regime, div_score, hybrid_impact)

    return result


def _compute_impact(corr_30d, trend_score, riskoff_prob):
    """Hybrid confidence adjustment: corr * trend * (1 - riskoff) * 0.15, clamped."""
    raw = corr_30d * trend_score * (1 - riskoff_prob) * 0.15
    return round(max(-0.20, min(0.20, raw)), 3)


def _fallback_result():
    return {
        "ok": False,
        "correlation30d": 0.0,
        "beta": 1.0,
        "spxRegime": "UNKNOWN",
        "trendScore": 0.5,
        "divergenceScore": 0.0,
        "divergenceState": "NEUTRAL",
        "hybridImpact": 0.0,
        "meta": {"alignedDays": 0, "spxLast": 0, "btcLast": 0, "spx7dReturn": 0, "btc7dReturn": 0},
    }
