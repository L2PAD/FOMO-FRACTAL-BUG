"""
P1.1 — Bybit Adapter
Reads Bybit data from MongoDB (exchange_bybit_snapshots / exchange_bybit_observations)
and normalizes into NormalizedMarketData.

Phase 1: Read from what's available. If no Bybit data → returns None.
"""

from typing import Optional, Dict, List
from pymongo import MongoClient, DESCENDING
import os
from . import NormalizedMarketData

_client = None
_db = None


def _get_db():
    global _client, _db
    if _db is None:
        mongo_url = os.environ.get("MONGO_URL")
        _client = MongoClient(mongo_url)
        _db = _client["intelligence_engine"]
    return _db


def get_bybit_spot(symbol: str) -> Optional[NormalizedMarketData]:
    """Fetch latest Bybit spot data for a symbol. Returns None if not available."""
    db = _get_db()

    # Try bybit observations first
    doc = db["exchange_bybit_observations"].find_one(
        {"symbol": symbol}, {"_id": 0}, sort=[("timestamp", DESCENDING)]
    )
    if doc:
        ind = doc.get("indicators", {})
        of = doc.get("orderFlow", {})
        price_data = doc.get("market", {})
        vol_data = doc.get("volume", {})

        def _v(key):
            raw = ind.get(key, {})
            return float(raw.get("value", raw) if isinstance(raw, dict) else (raw or 0))

        return NormalizedMarketData(
            symbol=symbol,
            venue="bybit",
            price=float(price_data.get("price", 0) or 0),
            volume24h=float(vol_data.get("total", 0) or 0),
            volatility=abs(_v("atr_normalized")),
            funding=_v("funding_pressure"),
            oi=_v("oi_level"),
            spread=_v("spread_pressure"),
            orderflow_bias=str(of.get("aggressorBias", "")).lower() or None,
            orderflow_strength=float(of.get("dominance", 0) or 0),
            timestamp=doc.get("timestamp", 0),
        )

    # Try bybit snapshots
    snap = db["exchange_bybit_snapshots"].find_one(
        {"symbol": symbol}, {"_id": 0}, sort=[("ts", DESCENDING)]
    )
    if snap:
        f = snap.get("features", {})
        return NormalizedMarketData(
            symbol=symbol,
            venue="bybit",
            price=float(snap.get("price_usd", snap.get("price", 0)) or 0),
            volume24h=float(snap.get("volume_24h", 0) or 0),
            volatility=float(f.get("volatility", 0) or 0),
            funding=float(f.get("funding_rate", 0) or 0),
            oi=float(f.get("oi_usd", 0) or 0),
            spread=float(f.get("spread", 0.3) or 0.3),
            orderflow_bias=None,
            orderflow_strength=None,
            timestamp=int(snap.get("ts", 0) or 0),
        )

    return None


def get_bybit_batch(symbols: List[str]) -> Dict[str, NormalizedMarketData]:
    """Batch fetch Bybit data. Returns {symbol: NormalizedMarketData}."""
    db = _get_db()
    result = {}

    # Check if bybit collections even exist
    collections = db.list_collection_names()
    has_obs = "exchange_bybit_observations" in collections
    has_snap = "exchange_bybit_snapshots" in collections

    if not has_obs and not has_snap:
        return result

    # Batch from observations
    if has_obs:
        pipeline = [
            {"$match": {"symbol": {"$in": symbols}}},
            {"$sort": {"timestamp": -1}},
            {"$group": {"_id": "$symbol", "doc": {"$first": "$$ROOT"}}},
        ]
        for r in db["exchange_bybit_observations"].aggregate(pipeline):
            sym = r["_id"]
            doc = r["doc"]
            ind = doc.get("indicators", {})
            of = doc.get("orderFlow", {})
            price_data = doc.get("market", {})
            vol_data = doc.get("volume", {})

            def _v(key):
                raw = ind.get(key, {})
                return float(raw.get("value", raw) if isinstance(raw, dict) else (raw or 0))

            result[sym] = NormalizedMarketData(
                symbol=sym,
                venue="bybit",
                price=float(price_data.get("price", 0) or 0),
                volume24h=float(vol_data.get("total", 0) or 0),
                volatility=abs(_v("atr_normalized")),
                funding=_v("funding_pressure"),
                oi=_v("oi_level"),
                spread=_v("spread_pressure"),
                orderflow_bias=str(of.get("aggressorBias", "")).lower() or None,
                orderflow_strength=float(of.get("dominance", 0) or 0),
                timestamp=doc.get("timestamp", 0),
            )

    # Fill gaps from snapshots
    if has_snap:
        missing = [s for s in symbols if s not in result]
        if missing:
            for snap in db["exchange_bybit_snapshots"].find(
                {"symbol": {"$in": missing}}, {"_id": 0}
            ):
                sym = snap.get("symbol", "")
                if sym not in result:
                    f = snap.get("features", {})
                    result[sym] = NormalizedMarketData(
                        symbol=sym,
                        venue="bybit",
                        price=float(snap.get("price_usd", snap.get("price", 0)) or 0),
                        volume24h=float(snap.get("volume_24h", 0) or 0),
                        volatility=float(f.get("volatility", 0) or 0),
                        funding=float(f.get("funding_rate", 0) or 0),
                        oi=float(f.get("oi_usd", 0) or 0),
                        spread=float(f.get("spread", 0.3) or 0.3),
                        orderflow_bias=None,
                        orderflow_strength=None,
                        timestamp=int(snap.get("ts", 0) or 0),
                    )

    return result
