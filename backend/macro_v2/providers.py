"""Macro V2 data providers — Live APIs (CoinGecko + Alternative.me) + synthetic fallback."""
import time
import math
import random
import logging
from .config import CACHE_TTL
from .live_data import build_live_series, get_live_snapshot, is_live_available

logger = logging.getLogger("macro_v2.providers")

_series_cache = {"data": None, "ts": 0, "source": "none"}
_snapshot_cache = {"data": None, "ts": 0}


def _generate_synthetic_series(limit=365):
    """Generate realistic synthetic macro series when live APIs unavailable.
    Uses deterministic seed + sine waves for consistency across calls."""
    now = int(time.time())
    day_sec = 86400
    points = []

    rng = random.Random(42)

    base_btc = 67000
    base_alt = 1200
    base_btc_dom = 55.0
    base_stable_dom = 10.5
    base_fg = 50

    for i in range(limit):
        t = now - (limit - 1 - i) * day_sec
        day_frac = i / max(limit - 1, 1)

        # BTC price: slow trend + cycles
        btc_cycle = math.sin(2 * math.pi * day_frac * 3) * 0.08
        btc_drift = (day_frac - 0.5) * 0.15
        btc_noise = rng.gauss(0, 0.02)
        btc_price = base_btc * math.exp(btc_drift + btc_cycle + btc_noise)

        # Alt index: correlated but with relative strength shifts
        alt_cycle = math.sin(2 * math.pi * day_frac * 3 + 0.5) * 0.10
        alt_drift = (day_frac - 0.5) * 0.12
        alt_noise = rng.gauss(0, 0.03)
        alt_index = base_alt * math.exp(alt_drift + alt_cycle + alt_noise)

        # BTC dominance: inversely correlated with alt performance
        dom_cycle = math.sin(2 * math.pi * day_frac * 2) * 2.5
        btc_dom = base_btc_dom + dom_cycle + rng.gauss(0, 0.5)
        btc_dom = max(40, min(70, btc_dom))

        # Stable dominance: spikes during fear
        stable_cycle = -math.sin(2 * math.pi * day_frac * 2.5) * 1.5
        stable_dom = base_stable_dom + stable_cycle + rng.gauss(0, 0.3)
        stable_dom = max(5, min(20, stable_dom))

        # Fear & Greed: oscillates
        fg_cycle = math.sin(2 * math.pi * day_frac * 4) * 25
        fg = base_fg + fg_cycle + rng.gauss(0, 5)
        fg = max(5, min(95, fg))

        # Volatility
        vol = abs(btc_noise) + 0.01

        points.append({
            "t": t,
            "btcPrice": round(btc_price, 2),
            "altIndex": round(alt_index, 2),
            "btcDom": round(btc_dom, 2),
            "stableDom": round(stable_dom, 2),
            "fearGreed": round(fg, 1),
            "marketVol": round(vol, 4),
        })

    return points


def get_macro_series(limit=365):
    """Fetch macro series: live APIs first, synthetic fallback."""
    now = time.time()
    if _series_cache["data"] and (now - _series_cache["ts"]) < CACHE_TTL:
        return _series_cache["data"]

    # Try live data first
    try:
        live_points = build_live_series(limit)
        if live_points and len(live_points) >= 10:
            _series_cache["data"] = live_points
            _series_cache["ts"] = now
            _series_cache["source"] = "live"
            logger.info("Macro series: LIVE data (%d points)", len(live_points))
            return live_points
    except Exception as e:
        logger.warning("Live series fetch failed: %s", str(e))

    # Synthetic fallback
    logger.info("Macro series: falling back to SYNTHETIC data")
    points = _generate_synthetic_series(limit)
    _series_cache["data"] = points
    _series_cache["ts"] = now
    _series_cache["source"] = "synthetic"
    return points


def get_macro_snapshot_raw():
    """Fetch latest raw snapshot: live APIs first, then series fallback."""
    now = time.time()
    if _snapshot_cache["data"] and (now - _snapshot_cache["ts"]) < CACHE_TTL:
        return _snapshot_cache["data"]

    # Try live snapshot
    try:
        snap = get_live_snapshot()
        if snap:
            _snapshot_cache["data"] = snap
            _snapshot_cache["ts"] = now
            return snap
    except Exception as e:
        logger.warning("Live snapshot fetch failed: %s", str(e))

    # Fallback: use last point from series
    series = get_macro_series(30)
    if series:
        last = series[-1]
        snap = {
            "asOf": last["t"],
            "fearGreed": last["fearGreed"],
            "btcDom": last["btcDom"],
            "stableDom": last["stableDom"],
            "btcPrice": last["btcPrice"],
            "altIndex": last["altIndex"],
            "marketVol": last.get("marketVol"),
        }
        _snapshot_cache["data"] = snap
        _snapshot_cache["ts"] = now
        return snap

    return {
        "asOf": int(now),
        "fearGreed": 50,
        "btcDom": 55.0,
        "stableDom": 10.5,
        "btcPrice": 67000,
        "altIndex": 1200,
        "marketVol": 0.02,
    }


def get_data_source():
    """Return current data source: 'live' or 'synthetic'."""
    return _series_cache.get("source", "none")
