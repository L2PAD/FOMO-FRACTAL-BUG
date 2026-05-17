"""
Labs providers — extract normalized feature maps from MongoDB.
Layer A: exchange_observations (primary, 38 indicators)
Layer B: exchange_symbol_snapshots (fallback)
"""

from typing import Dict, Optional, List
from pymongo import MongoClient, DESCENDING
import os
import time

_client = None
_db = None


def _get_db():
    global _client, _db
    if _db is None:
        mongo_url = os.environ.get("MONGO_URL")
        db_name = os.environ.get("DB_NAME")
        _client = MongoClient(mongo_url)
        _db = _client[db_name]
    return _db


def _ind_val(obs: dict, name: str) -> Optional[float]:
    """Extract indicator value from observation."""
    ind = obs.get("indicators", {}).get(name, {})
    if isinstance(ind, dict):
        v = ind.get("value")
        if v is not None:
            return float(v)
    return None


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def extract_features(obs: dict) -> Dict[str, dict]:
    """
    Convert raw observation into a flat feature_map.
    Each feature: {norm: 0..1, raw: original_value, source: "obs"}.
    Handles both direct indicators and computed synthetic features.
    """
    fm = {}

    # Direct indicators (already normalized 0..1)
    # "unipolar" means 0=normal, 1=extreme (vs bipolar: 0.5=normal)
    direct_unipolar = [
        "spread_pressure", "liquidity_vacuum", "liquidity_walls",
        "stop_hunt_probability", "position_crowding", "large_position_presence",
        "participation_intensity", "relative_volume", "absorption_strength",
    ]
    direct_bipolar = [
        "trend_slope", "macd_delta", "volume_delta", "oi_delta",
        "funding_pressure", "whale_side_bias", "book_imbalance", "roc",
    ]
    direct_raw = [
        "depth_density", "range_compression", "atr_normalized", "vwap_deviation",
        "rsi_normalized", "volume_index", "volume_price_response",
        "oi_level", "contrarian_pressure_index", "long_short_ratio",
        "stochastic", "momentum_decay",
    ]

    for key in direct_unipolar:
        v = _ind_val(obs, key)
        if v is not None:
            norm = _clamp(v)
            fm[key] = {"norm": norm, "raw": v, "source": "obs", "unipolar": True}

    for key in direct_bipolar:
        v = _ind_val(obs, key)
        if v is not None:
            norm = _clamp((v + 1.0) / 2.0)  # -1..1 → 0..1
            fm[key] = {"norm": norm, "raw": v, "source": "obs"}

    for key in direct_raw:
        v = _ind_val(obs, key)
        if v is not None:
            norm = _clamp(v)
            fm[key] = {"norm": norm, "raw": v, "source": "obs"}

    # Synthetic: directional momentum balance
    dm = _ind_val(obs, "directional_momentum_balance")
    if dm is not None:
        fm["dir_momentum"] = {"norm": _clamp((dm + 1.0) / 2.0), "raw": dm, "source": "obs"}

    # Synthetic: EMA alignment (all EMAs close = compression, aligned = trend)
    ef = _ind_val(obs, "ema_distance_fast")
    em = _ind_val(obs, "ema_distance_mid")
    es = _ind_val(obs, "ema_distance_slow")
    if ef is not None and em is not None and es is not None:
        alignment = _clamp(1.0 - (abs(ef) + abs(em) + abs(es)) * 3)
        fm["ema_alignment"] = {"norm": alignment, "raw": round(alignment, 4), "source": "obs"}

    # Synthetic: order flow imbalance (from top-level)
    of = obs.get("orderFlow", {})
    of_imb = of.get("imbalance")
    if of_imb is not None:
        fm["of_imbalance"] = {"norm": _clamp((float(of_imb) + 1.0) / 2.0), "raw": float(of_imb), "source": "obs"}

    of_dom = of.get("dominance")
    if of_dom is not None:
        fm["of_dominance"] = {"norm": _clamp(float(of_dom)), "raw": float(of_dom), "source": "obs"}

    aggressor = str(of.get("aggressorBias", "")).upper()
    agg_val = 0.7 if aggressor == "BUY" else 0.3 if aggressor == "SELL" else 0.5
    fm["aggressor_bias"] = {"norm": agg_val, "raw": aggressor, "source": "obs"}

    # Synthetic: liquidation pressure (from top-level)
    liqs = obs.get("liquidations", {})
    cascade = 1.0 if liqs.get("cascadeActive") else 0.0
    liq_long = float(liqs.get("longVolume24h", 0) or 0)
    liq_short = float(liqs.get("shortVolume24h", 0) or 0)
    liq_total = liq_long + liq_short
    liq_intensity = _clamp(liq_total / 1e7) if liq_total > 0 else 0.0
    liq_pressure = _clamp(cascade * 0.5 + liq_intensity * 0.5)
    fm["liq_pressure"] = {"norm": liq_pressure, "raw": liq_total, "source": "obs", "unipolar": True}

    # Synthetic: data quality metrics
    indicators = obs.get("indicators", {})
    total_expected = 38
    present = sum(1 for k, v in indicators.items() if isinstance(v, dict) and v.get("value") is not None)
    fm["coverage_ratio"] = {"norm": _clamp(present / total_expected), "raw": present, "source": "obs"}

    ts = obs.get("timestamp")
    if ts:
        from datetime import datetime
        try:
            if isinstance(ts, str):
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            else:
                dt = ts
            age_sec = (datetime.now(dt.tzinfo) - dt).total_seconds() if dt.tzinfo else 0
            fm["freshness_inv"] = {"norm": _clamp(1.0 - age_sec / 900), "raw": age_sec, "source": "obs"}
        except Exception:
            fm["freshness_inv"] = {"norm": 0.5, "raw": 0, "source": "obs"}
    else:
        fm["freshness_inv"] = {"norm": 0.5, "raw": 0, "source": "obs"}

    # Synthetic: signal alignment from hasConflict
    has_conflict = obs.get("hasConflict", False)
    fm["signal_alignment"] = {"norm": 0.3 if has_conflict else 0.8, "raw": not has_conflict, "source": "obs"}

    return fm


def get_observation(symbol: str) -> Optional[dict]:
    """Get latest observation for symbol."""
    db = _get_db()
    return db["exchange_observations"].find_one(
        {"symbol": symbol}, {"_id": 0}, sort=[("timestamp", DESCENDING)]
    )


def get_snapshot(symbol: str) -> Optional[dict]:
    """Get latest snapshot (fallback)."""
    db = _get_db()
    return db["exchange_symbol_snapshots"].find_one(
        {"symbol": symbol}, {"_id": 0}, sort=[("timestamp", DESCENDING)]
    )


def extract_snapshot_features(snap: dict) -> Dict[str, dict]:
    """Extract basic features from snapshot (fewer indicators)."""
    fm = {}
    # Snapshots have top-level market data
    market = snap.get("market", {})
    if market.get("volatility") is not None:
        fm["atr_normalized"] = {"norm": _clamp(float(market["volatility"])), "raw": market["volatility"], "source": "snapshot"}
    if market.get("spread") is not None:
        fm["spread_pressure"] = {"norm": _clamp(float(market["spread"])), "raw": market["spread"], "source": "snapshot"}

    of = snap.get("orderFlow", {})
    if of.get("imbalance") is not None:
        fm["of_imbalance"] = {"norm": _clamp((float(of["imbalance"]) + 1.0) / 2.0), "raw": float(of["imbalance"]), "source": "snapshot"}

    v = snap.get("volume", {})
    if v.get("ratio") is not None:
        fm["volume_index"] = {"norm": _clamp(float(v["ratio"])), "raw": v["ratio"], "source": "snapshot"}

    fm["coverage_ratio"] = {"norm": 0.3, "raw": 3, "source": "snapshot"}
    fm["freshness_inv"] = {"norm": 0.5, "raw": 0, "source": "snapshot"}

    return fm


def get_feature_map(symbol: str) -> tuple:
    """
    Returns (feature_map, freshness_sec, source_type).
    Primary: observations. Fallback: snapshots.
    """
    obs = get_observation(symbol)
    if obs and obs.get("indicators"):
        fm = extract_features(obs)
        ts = obs.get("timestamp")
        freshness = 60  # default
        if ts:
            from datetime import datetime, timezone
            try:
                if isinstance(ts, str):
                    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                else:
                    dt = ts
                freshness = int((datetime.now(timezone.utc) - dt.replace(tzinfo=timezone.utc)).total_seconds()) if not dt.tzinfo else int((datetime.now(dt.tzinfo) - dt).total_seconds())
            except Exception:
                pass
        return fm, abs(freshness), "obs"

    snap = get_snapshot(symbol)
    if snap:
        fm = extract_snapshot_features(snap)
        return fm, 300, "snapshot"

    return {}, 9999, "snapshot"


def get_all_symbols() -> List[str]:
    """Get all symbols that have observations."""
    db = _get_db()
    return db["exchange_observations"].distinct("symbol")
