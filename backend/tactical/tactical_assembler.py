"""
Tactical Assembler
====================
Block X — Main entry point

Orchestrates: snapshot → signals → fusion → advice.

Usage:
    from tactical.tactical_assembler import build_tactical_assessment
    result = build_tactical_assessment("BTC")
"""

import os
from datetime import datetime, timezone

from pymongo import MongoClient

from tactical.tactical_signal_builder import build_tactical_signals
from tactical.tactical_fusion_engine import fuse_tactical_signals
from tactical.tactical_advisor import build_tactical_advice
from tactical.tactical_types import MicrostructureSnapshot, TacticalAdvice
from exchange.normalization.asset_normalizer import normalize_features


def _get_db():
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017/intelligence_engine")
    db_name = os.environ.get("DB_NAME", "intelligence_engine")
    return MongoClient(mongo_url)[db_name]


def build_tactical_assessment(asset: str = "BTC") -> dict:
    """
    Build complete tactical assessment from latest microstructure data.

    Pipeline: fetch snapshot → build signals → fuse → advise.
    """
    snap = _fetch_latest_snapshot(asset)
    if not snap:
        return {
            "ok": False,
            "error": "No microstructure data available",
            "advice": _default_advice(),
        }

    # Pipeline (Block 7.4: pass asset for threshold adaptation)
    signals = build_tactical_signals(snap, asset)
    fusion = fuse_tactical_signals(signals)
    advice = build_tactical_advice(fusion, snap)

    return {
        "ok": True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "asset": asset,
        "advice": advice,
        "signals": signals,
        "fusion": {
            "score": fusion["score"],
            "bias": fusion["bias"],
            "signal_strength": fusion["signal_strength"],
            "active_signals": fusion["active_signals"],
        },
        "snapshot_age_seconds": snap.get("_age_seconds", None),
        "normalized": {
            "imbalance_norm": snap.get("imbalance_norm", 0),
            "liq_long_norm": snap.get("liq_long_norm", 0),
            "liq_short_norm": snap.get("liq_short_norm", 0),
            "funding_norm": snap.get("funding_norm", 0),
            "volatility_norm": snap.get("volatility_norm", 0),
        },
    }


def build_tactical_from_snapshot(snap: MicrostructureSnapshot, asset: str = "BTC") -> dict:
    """Build tactical assessment from a pre-built snapshot (for backfill).
    Block 7.3: adds *_norm fields via asset normalization."""
    # Add normalized features
    snap = _enrich_with_normalization(snap, asset)

    signals = build_tactical_signals(snap, asset)
    fusion = fuse_tactical_signals(signals)
    advice = build_tactical_advice(fusion, snap)
    return {
        "advice": advice,
        "signals": signals,
        "fusion": {
            "score": fusion["score"],
            "bias": fusion["bias"],
            "signal_strength": fusion["signal_strength"],
            "active_signals": fusion["active_signals"],
        },
    }


def _fetch_latest_snapshot(asset: str) -> MicrostructureSnapshot | None:
    """Fetch and normalize the latest exchange observation.
    Block 7.3: enriches snapshot with *_norm fields."""
    db = _get_db()

    symbol = f"{asset}USDT"
    doc = db["exchange_observations"].find_one(
        {"symbol": symbol},
        {"_id": 0},
        sort=[("timestamp", -1)],
    )

    if not doc:
        return None

    of = doc.get("orderFlow") or {}
    liq = doc.get("liquidations") or {}
    vol = doc.get("volume") or {}
    oi = doc.get("openInterest") or {}
    market = doc.get("market") or {}

    # Get funding context
    funding = _fetch_latest_funding(symbol, db)

    # Calculate age — robust to ts being millis-int OR python datetime
    ts_raw = doc.get("timestamp") or doc.get("ts") or doc.get("createdAt") or 0
    if isinstance(ts_raw, datetime):
        ts_ms = ts_raw.replace(tzinfo=ts_raw.tzinfo or timezone.utc).timestamp() * 1000
    elif isinstance(ts_raw, (int, float)):
        # Could already be seconds OR millis; coerce to millis
        ts_ms = float(ts_raw) * 1000 if ts_raw < 1e12 else float(ts_raw)
    else:
        ts_ms = 0
    age = (datetime.now(timezone.utc).timestamp() * 1000 - ts_ms) / 1000

    snap = {
        "imbalance": of.get("imbalance", 0.0),
        "dominance": of.get("dominance", 0.5),
        "aggressor_bias": of.get("aggressorBias", "NEUTRAL"),
        "long_liq_volume": liq.get("longVolume", 0),
        "short_liq_volume": liq.get("shortVolume", 0),
        "cascade_active": liq.get("cascadeActive", False),
        "cascade_direction": liq.get("cascadeDirection", ""),
        "cascade_phase": liq.get("cascadePhase", ""),
        "funding_score": funding.get("fundingScore", 0.0),
        "funding_trend": funding.get("fundingTrend", 0.0),
        "funding_label": funding.get("label", "NEUTRAL"),
        "absorption": of.get("absorption", False),
        "absorption_side": of.get("absorptionSide", ""),
        "volume_delta": vol.get("delta", 0),
        "oi_delta_pct": oi.get("deltaPct", 0),
        "uncertainty": 0.5,  # default, enriched by caller if available
        "regime": (doc.get("regime") or {}).get("type", "UNKNOWN"),
        "phase": None,
        "_age_seconds": round(age),
        "_raw_timestamp": ts_ms,
        "_volatility": market.get("volatility", 0),
    }

    # Block 7.3: add normalized features
    snap = _enrich_with_normalization(snap, asset)

    return snap


def _enrich_with_normalization(snap: dict, asset: str) -> dict:
    """Block 7.3: Add *_norm fields alongside originals. No mutation of raw values."""
    norm_input = {
        "imbalance": snap.get("imbalance", 0),
        "longVolume": snap.get("long_liq_volume", 0),
        "shortVolume": snap.get("short_liq_volume", 0),
        "funding_score": snap.get("funding_score", 0),
        "volatility": snap.get("_volatility", 0),
    }
    normed = normalize_features(norm_input, asset)
    snap["imbalance_norm"] = normed.get("imbalance_norm", 0)
    snap["liq_long_norm"] = normed.get("liq_long_norm", 0)
    snap["liq_short_norm"] = normed.get("liq_short_norm", 0)
    snap["funding_norm"] = normed.get("funding_norm", 0)
    snap["volatility_norm"] = normed.get("volatility_norm", 0)
    return snap


def _fetch_latest_funding(symbol: str, db) -> dict:
    """Get latest funding context."""
    doc = db["exchange_funding_context"].find_one(
        {"symbol": symbol},
        {"_id": 0},
        sort=[("ts", -1)],
    )
    return doc or {}


def _default_advice() -> TacticalAdvice:
    """Fallback advice when no data is available."""
    return {
        "tacticalBias": "neutral",
        "tradeQuality": "low",
        "executionAdvice": "wait",
        "volatilityExpectation": "moderate",
        "reasonFlags": ["no_data"],
        "signalStrength": 0.0,
        "fusionScore": 0.0,
        "note": "No microstructure data available — defer to strategic forecast",
    }
