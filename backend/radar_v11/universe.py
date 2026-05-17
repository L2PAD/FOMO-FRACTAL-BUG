"""
ALT RADAR V11 — Universe Split Service
========================================
Splits symbol universe into: Spot Main / Spot Alpha / Futures.
Alpha: seeded from whitelist into dedicated collection.
Main: from exchange_symbol_universe (excluding alpha).
Futures: from universe_symbols_v2 (perp, enabled).
"""

from pymongo import MongoClient
from typing import List, Dict
import os

# Alpha whitelist — Binance Alpha tokens (low liquidity, early stage)
ALPHA_WHITELIST = [
    "COOKIEUSDT", "MOVEUSDT", "THEUSDT", "DEGENUSDT", "TURBOUSDT",
    "WIFUSDT", "BRETTUSDT", "POPCATUSDT", "NEIROUSDT",
    "ACTUSDT", "PNUTUSDT", "BANUSDT", "GRIFFAINUSDT",
    "AI16ZUSDT", "GOATUSDT", "FARTCOINUSDT",
    "PENGUUSDT", "CGPTUSDT", "CHILLGUYUSDT", "SUSDT",
    "MEWUSDT", "BOMEUSDT", "PEPEUSDT", "FLOKIUSDT",
    "BONKUSDT", "DOGSUSDT", "SHIBUSDT", "LUNCUSDT",
]

COL_MAIN = "exchange_symbol_universe"
COL_ALPHA = "exchange_symbol_universe_alpha"

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


def ensure_alpha_universe() -> int:
    """Seed alpha whitelist into dedicated collection. Returns count."""
    db = _get_db()
    col = db[COL_ALPHA]
    for sym in ALPHA_WHITELIST:
        col.update_one(
            {"symbol": sym},
            {"$set": {"symbol": sym, "source": "whitelist"}},
            upsert=True,
        )
    return col.count_documents({})


def get_spot_main_symbols() -> List[str]:
    """Spot Main = symbols from exchange_symbol_universe + symbols from snapshots."""
    db = _get_db()
    alpha_set = set(ALPHA_WHITELIST)

    # Primary: exchange_symbol_universe
    universe_docs = list(db[COL_MAIN].find({}, {"_id": 0, "symbol": 1}))
    universe_syms = set(d["symbol"] for d in universe_docs)

    # Expand: all base symbols from exchange_symbol_snapshots → convert to USDT pairs
    snapshot_docs = db["exchange_symbol_snapshots"].find({}, {"_id": 0, "base": 1})
    for d in snapshot_docs:
        sym = d["base"] + "USDT"
        if sym not in alpha_set:
            universe_syms.add(sym)

    return sorted(universe_syms)


def get_spot_alpha_symbols() -> List[str]:
    """Spot Alpha: dynamic universe if enabled, else static whitelist."""
    dynamic_enabled = os.environ.get("ALPHA_DYNAMIC_ENABLED", "true").lower() == "true"

    if dynamic_enabled:
        from .alpha_builder import get_dynamic_alpha_symbols
        dynamic = get_dynamic_alpha_symbols()
        if len(dynamic) >= 10:
            return dynamic

    # Fallback: static whitelist
    db = _get_db()
    ensure_alpha_universe()
    docs = list(db[COL_ALPHA].find({}, {"_id": 0, "symbol": 1}))
    return sorted([d["symbol"] for d in docs])


def get_futures_symbols() -> List[str]:
    """Futures = perpetual symbols from universe_symbols_v2."""
    db = _get_db()
    docs = list(db["universe_symbols_v2"].find(
        {"marketType": "perp", "enabled": True},
        {"_id": 0, "symbol": 1}
    ))
    return sorted(list(set(d["symbol"] for d in docs)))


def get_universe_counts() -> Dict:
    """Return counts for each universe segment."""
    return {
        "spotMainCount": len(get_spot_main_symbols()),
        "spotAlphaCount": len(get_spot_alpha_symbols()),
        "futuresCount": len(get_futures_symbols()),
    }
