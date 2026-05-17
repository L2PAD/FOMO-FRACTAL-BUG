"""
P1.1/P1.2 — Binance Adapter
Reads from existing exchange_observations + exchange_symbol_snapshots
and normalizes into NormalizedMarketData.
"""

from typing import Optional, Dict, List
from pymongo import MongoClient
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


def from_observation(symbol: str, obs: Dict) -> NormalizedMarketData:
    """Convert a rich observation document to NormalizedMarketData."""
    ind = obs.get("indicators", {})

    def _v(key):
        raw = ind.get(key, {})
        return float(raw.get("value", raw) if isinstance(raw, dict) else (raw or 0))

    of = obs.get("orderFlow", {})
    price_data = obs.get("market", {})
    vol_data = obs.get("volume", {})

    return NormalizedMarketData(
        symbol=symbol,
        venue="binance",
        price=float(price_data.get("price", 0) or 0),
        volume24h=float(vol_data.get("total", 0) or 0),
        volatility=abs(_v("atr_normalized")),
        funding=_v("funding_pressure"),
        oi=_v("oi_level"),
        spread=_v("spread_pressure"),
        orderflow_bias=str(of.get("aggressorBias", "")).lower() or None,
        orderflow_strength=float(of.get("dominance", 0) or 0),
        timestamp=obs.get("timestamp", 0),
    )


def from_snapshot(symbol: str, snap: Dict) -> NormalizedMarketData:
    """Convert a snapshot document to NormalizedMarketData."""
    f = snap.get("features", {})
    vol_log = f.get("volume_log") or 0
    ret_24h = f.get("ret_24h") or 0
    oi_usd = f.get("oi_usd") or 0
    funding = f.get("funding_rate") or 0

    return NormalizedMarketData(
        symbol=symbol,
        venue="binance",
        price=float(snap.get("price_usd", 0) or 0),
        volume24h=float(10 ** vol_log if vol_log > 0 else 0),
        volatility=min(1.0, abs(ret_24h) * 5),
        funding=funding,
        oi=oi_usd,
        spread=0.3,  # approximate for snapshots
        orderflow_bias=None,
        orderflow_strength=None,
        timestamp=0,
    )



def get_binance_batch(symbols: List[str]) -> Dict[str, NormalizedMarketData]:
    """P1.2: Batch fetch Binance data for divergence computation."""
    db = _get_db()
    result = {}

    # From observations (richest data)
    pipeline = [
        {"$match": {"symbol": {"$in": symbols}}},
        {"$sort": {"timestamp": -1}},
        {"$group": {"_id": "$symbol", "doc": {"$first": "$$ROOT"}}},
    ]
    for r in db["exchange_observations"].aggregate(pipeline):
        sym = r["_id"]
        doc = r["doc"]
        doc.pop("_id", None)
        result[sym] = from_observation(sym, doc)

    # Fill gaps from snapshots
    missing = [s for s in symbols if s not in result]
    if missing:
        bases = [s.replace("USDT", "") for s in missing]
        for snap in db["exchange_symbol_snapshots"].find(
            {"base": {"$in": bases}}, {"_id": 0}
        ):
            sym = snap.get("base", "") + "USDT"
            if sym not in result:
                result[sym] = from_snapshot(sym, snap)

    return result
