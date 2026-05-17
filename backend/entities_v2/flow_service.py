"""
Entities V2 — Phase 4: Flow Engine
=====================================
Computes capital flows (inflow, outflow, net) for each entity
across time windows, with token-level breakdown and exchange
interaction tracking.

Pipeline:
  entity_addresses_v2 → onchain_v2_erc20_logs
    → direction classification (in/out)
    → USD pricing (onchain_v2_token_prices + token_registry)
    → time-window bucketing (1h, 4h, 24h, 7d, 30d)
    → exchange interaction layer (via onchain_v2_address_labels)

Output collection:
  entity_flows_v2 — Materialized flow data per entity
"""

import os
import time
from datetime import datetime, timezone
from pymongo import MongoClient, ASCENDING, DESCENDING

_client = None
_db = None

WINDOWS = {
    "1h": 3600,
    "4h": 14400,
    "24h": 86400,
    "7d": 604800,
    "30d": 2592000,
}


def _get_db():
    global _client, _db
    if _db is None:
        _client = MongoClient(os.environ.get("MONGO_URL"))
        _db = _client[os.environ.get("DB_NAME", "test_database")]
    return _db


_cache: dict = {}
_CACHE_TTL = 300


def _cache_get(k: str):
    e = _cache.get(k)
    return e["data"] if e and time.time() - e["ts"] < _CACHE_TTL else None


def _cache_set(k: str, data):
    _cache[k] = {"data": data, "ts": time.time()}


# ── Shared reference data (loaded once per build cycle) ──
_token_meta: dict | None = None
_token_prices: dict | None = None
_exchange_addrs: set | None = None
_exchange_labels: dict | None = None

STABLECOIN_ADDRESSES = {
    "0xdac17f958d2ee523a2206206994597c13d831ec7",
    "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
    "0x6b175474e89094c44da98b954eedeac495271d0f",
    "0x4fabb145d64652a948d72533023f6e7a623c7c53",
    "0x8e870d67f660d95d5be530380d0ec0bd388289e1",
    "0x4c9edd5852cd905f086c759e8383e09bff1e68b3",
}


def _load_refs():
    """Load token meta, prices, and exchange address labels."""
    global _token_meta, _token_prices, _exchange_addrs, _exchange_labels

    db = _get_db()

    # Token metadata
    _token_meta = {}
    for doc in db["token_registry"].find({"chain": "ethereum"}, {"_id": 0}):
        addr = doc["address"].lower()
        if addr not in _token_meta:
            _token_meta[addr] = {
                "symbol": doc.get("symbol", "???"),
                "decimals": doc.get("decimals", 18),
            }

    # Token prices
    _token_prices = {}
    for doc in db["onchain_v2_token_prices"].find({"chainId": 1}, {"_id": 0}):
        _token_prices[doc["token"].lower()] = doc.get("priceUsd", 0)
    for stable in STABLECOIN_ADDRESSES:
        if stable not in _token_prices:
            _token_prices[stable] = 1.0

    # Exchange addresses from labels
    _exchange_addrs = set()
    _exchange_labels = {}
    for doc in db["onchain_v2_address_labels"].find(
        {"type": "exchange"}, {"_id": 0, "address": 1, "entityId": 1, "name": 1}
    ):
        addr = doc["address"].lower()
        _exchange_addrs.add(addr)
        _exchange_labels[addr] = {
            "entity_id": doc.get("entityId"),
            "name": doc.get("name"),
        }

    # Also add our own entity exchange addresses
    for doc in db["entity_addresses_v2"].find(
        {"entity_type": "exchange"}, {"_id": 0, "address": 1, "entity_slug": 1, "entity_name": 1}
    ):
        addr = doc["address"].lower()
        _exchange_addrs.add(addr)
        if addr not in _exchange_labels:
            _exchange_labels[addr] = {
                "entity_id": doc.get("entity_slug"),
                "name": doc.get("entity_name"),
            }


def _value_to_usd(token_addr: str, raw_value_str: str) -> float:
    """Convert raw ERC20 value string to USD."""
    try:
        raw = int(raw_value_str)
    except (ValueError, TypeError):
        return 0.0
    if raw <= 0:
        return 0.0

    decimals = (_token_meta or {}).get(token_addr, {}).get("decimals", 18)
    balance = raw / (10 ** decimals)
    price = (_token_prices or {}).get(token_addr, 0)
    return balance * price


def _token_symbol(token_addr: str) -> str:
    return (_token_meta or {}).get(token_addr, {}).get("symbol", token_addr[:10] + "...")


# ══════════════════════════════════════════════════════════
#  FLOW BUILDER
# ══════════════════════════════════════════════════════════

def build_entity_flows(slug: str) -> dict | None:
    """Compute flows for a single entity across all time windows."""
    db = _get_db()
    entity = db["entities_v2"].find_one({"slug": slug}, {"_id": 0})
    if not entity:
        return None

    addresses = [
        doc["address"] for doc in
        db["entity_addresses_v2"].find({"entity_slug": slug}, {"_id": 0, "address": 1})
    ]
    if not addresses:
        return _empty_flows(entity)

    _load_refs()

    now_ms = time.time() * 1000
    erc20 = db["onchain_v2_erc20_logs"]

    # Fetch ALL transfers for entity addresses (both directions)
    entity_addr_set = set(addresses)
    transfers = []

    for addr in addresses:
        # Inflows (addr is receiver)
        for doc in erc20.find({"to": addr}, {"_id": 0, "from": 1, "to": 1, "tokenAddress": 1, "value": 1, "indexedAt": 1}):
            token = (doc.get("tokenAddress") or "").lower()
            usd = _value_to_usd(token, doc.get("value", "0"))
            counterparty = doc.get("from", "").lower()
            transfers.append({
                "direction": "in",
                "address": addr,
                "counterparty": counterparty,
                "token": token,
                "usd": usd,
                "ts": doc.get("indexedAt", 0),
                "is_exchange": counterparty in _exchange_addrs,
                "exchange_label": _exchange_labels.get(counterparty),
            })

        # Outflows (addr is sender)
        for doc in erc20.find({"from": addr}, {"_id": 0, "from": 1, "to": 1, "tokenAddress": 1, "value": 1, "indexedAt": 1}):
            token = (doc.get("tokenAddress") or "").lower()
            usd = _value_to_usd(token, doc.get("value", "0"))
            counterparty = doc.get("to", "").lower()
            # Skip self-transfers between entity's own addresses
            if counterparty in entity_addr_set:
                continue
            transfers.append({
                "direction": "out",
                "address": addr,
                "counterparty": counterparty,
                "token": token,
                "usd": usd,
                "ts": doc.get("indexedAt", 0),
                "is_exchange": counterparty in _exchange_addrs,
                "exchange_label": _exchange_labels.get(counterparty),
            })

    if not transfers:
        return _empty_flows(entity)

    # ── Build windowed flows ──
    windowed = {}
    for window_name, window_sec in WINDOWS.items():
        cutoff = now_ms - window_sec * 1000
        window_txs = [t for t in transfers if t["ts"] >= cutoff]
        windowed[window_name] = _aggregate_window(window_txs, window_sec)

    # ── All-time flows ──
    all_time = _aggregate_window(transfers, None)

    # ── Token flows (all time) ──
    token_flows = _aggregate_token_flows(transfers)

    # ── Exchange interactions ──
    exchange_flows = _aggregate_exchange_flows(transfers)

    # ── Flow velocity (all time, using total data span, min 1 day) ──
    ts_vals = [t["ts"] for t in transfers if t["ts"] > 0]
    if len(ts_vals) >= 2:
        span_sec = max((max(ts_vals) - min(ts_vals)) / 1000, 86400)  # min 1 day
        total_vol = all_time["inflow_usd"] + all_time["outflow_usd"]
        velocity_per_day = total_vol / (span_sec / 86400)
    else:
        total_vol = all_time["inflow_usd"] + all_time["outflow_usd"]
        velocity_per_day = total_vol  # single data point = daily rate

    now = datetime.now(timezone.utc)

    result = {
        "entity": {
            "slug": entity["slug"],
            "name": entity["name"],
            "type": entity["type"],
            "category": entity["category"],
        },
        "flows": windowed,
        "all_time": all_time,
        "flow_velocity": round(velocity_per_day, 2),
        "direction": _classify_direction(all_time),
        "token_flows": token_flows[:20],
        "exchange_interactions": exchange_flows[:10],
        "meta": {
            "total_transfers": len(transfers),
            "addresses_scanned": len(addresses),
            "data_span_days": round((max(ts_vals) - min(ts_vals)) / 1000 / 86400, 1) if len(ts_vals) >= 2 else 0,
        },
        "computed_at": now.isoformat(),
    }

    # Persist
    flows_col = db["entity_flows_v2"]
    flows_col.create_index([("entity_slug", ASCENDING)], unique=True, background=True)
    flows_col.update_one(
        {"entity_slug": slug},
        {"$set": {"entity_slug": slug, **result, "computed_at": now.isoformat()}},
        upsert=True,
    )

    _cache.clear()
    return result


def _aggregate_window(txs: list, window_sec: int | None) -> dict:
    """Aggregate transfers into inflow/outflow/net."""
    inflow = sum(t["usd"] for t in txs if t["direction"] == "in")
    outflow = sum(t["usd"] for t in txs if t["direction"] == "out")
    net = inflow - outflow
    in_count = sum(1 for t in txs if t["direction"] == "in")
    out_count = sum(1 for t in txs if t["direction"] == "out")

    return {
        "inflow_usd": round(inflow, 2),
        "outflow_usd": round(outflow, 2),
        "net_flow_usd": round(net, 2),
        "inflow_count": in_count,
        "outflow_count": out_count,
        "total_count": in_count + out_count,
    }


def _aggregate_token_flows(txs: list) -> list:
    """Per-token flow aggregation."""
    token_data: dict = {}
    for t in txs:
        token = t["token"]
        if token not in token_data:
            token_data[token] = {"in_usd": 0, "out_usd": 0, "count": 0}
        if t["direction"] == "in":
            token_data[token]["in_usd"] += t["usd"]
        else:
            token_data[token]["out_usd"] += t["usd"]
        token_data[token]["count"] += 1

    total_vol = sum(d["in_usd"] + d["out_usd"] for d in token_data.values())
    result = []
    for token_addr, data in token_data.items():
        vol = data["in_usd"] + data["out_usd"]
        result.append({
            "token_address": token_addr,
            "symbol": _token_symbol(token_addr),
            "inflow_usd": round(data["in_usd"], 2),
            "outflow_usd": round(data["out_usd"], 2),
            "net_flow_usd": round(data["in_usd"] - data["out_usd"], 2),
            "volume_usd": round(vol, 2),
            "volume_share": round(vol / total_vol, 4) if total_vol > 0 else 0,
            "transfer_count": data["count"],
        })
    result.sort(key=lambda x: x["volume_usd"], reverse=True)
    return result


def _aggregate_exchange_flows(txs: list) -> list:
    """Aggregate entity ↔ exchange interactions."""
    exchange_data: dict = {}
    for t in txs:
        if not t["is_exchange"]:
            continue
        label = t.get("exchange_label") or {}
        exch_id = label.get("entity_id") or t["counterparty"][:12]
        exch_name = label.get("name") or exch_id

        if exch_id not in exchange_data:
            exchange_data[exch_id] = {"name": exch_name, "in_usd": 0, "out_usd": 0, "count": 0}

        if t["direction"] == "in":
            # Entity received FROM exchange
            exchange_data[exch_id]["in_usd"] += t["usd"]
        else:
            # Entity sent TO exchange
            exchange_data[exch_id]["out_usd"] += t["usd"]
        exchange_data[exch_id]["count"] += 1

    result = []
    for exch_id, data in exchange_data.items():
        net = data["in_usd"] - data["out_usd"]
        result.append({
            "exchange_id": exch_id,
            "exchange_name": data["name"],
            "flow_from_exchange_usd": round(data["in_usd"], 2),
            "flow_to_exchange_usd": round(data["out_usd"], 2),
            "net_flow_usd": round(net, 2),
            "direction": "from_exchange" if net > 0 else "to_exchange" if net < 0 else "balanced",
            "transfer_count": data["count"],
        })
    result.sort(key=lambda x: abs(x["net_flow_usd"]), reverse=True)
    return result


def _classify_direction(agg: dict) -> str:
    """Classify dominant flow direction."""
    inflow = agg.get("inflow_usd", 0)
    outflow = agg.get("outflow_usd", 0)
    total = inflow + outflow
    if total == 0:
        return "no_activity"
    ratio = inflow / total
    if ratio > 0.6:
        return "inflow_dominant"
    elif ratio < 0.4:
        return "outflow_dominant"
    return "balanced"


def _empty_flows(entity: dict) -> dict:
    empty_window = {
        "inflow_usd": 0, "outflow_usd": 0, "net_flow_usd": 0,
        "inflow_count": 0, "outflow_count": 0, "total_count": 0,
    }
    return {
        "entity": {
            "slug": entity["slug"], "name": entity["name"],
            "type": entity["type"], "category": entity["category"],
        },
        "flows": {w: dict(empty_window) for w in WINDOWS},
        "all_time": dict(empty_window),
        "flow_velocity": 0,
        "direction": "no_activity",
        "token_flows": [],
        "exchange_interactions": [],
        "meta": {"total_transfers": 0, "addresses_scanned": 0, "data_span_days": 0},
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }


# ══════════════════════════════════════════════════════════
#  QUERY FUNCTIONS
# ══════════════════════════════════════════════════════════

def get_entity_net_flow(slug: str) -> dict | None:
    """Net flow summary across all windows."""
    ck = f"netflow:{slug}"
    cached = _cache_get(ck)
    if cached:
        return cached

    db = _get_db()
    entity = db["entities_v2"].find_one({"slug": slug}, {"_id": 0})
    if not entity:
        return None

    stored = db["entity_flows_v2"].find_one({"entity_slug": slug}, {"_id": 0})
    if not stored:
        # Compute on-the-fly
        built = build_entity_flows(slug)
        if not built:
            return _empty_flows(entity)
        stored = built

    result = {
        "entity": stored.get("entity", {"slug": slug, "name": entity["name"], "type": entity["type"], "category": entity["category"]}),
        "flows": stored.get("flows", {}),
        "all_time": stored.get("all_time", {}),
        "flow_velocity": stored.get("flow_velocity", 0),
        "direction": stored.get("direction", "no_activity"),
        "meta": stored.get("meta", {}),
        "computed_at": stored.get("computed_at"),
    }
    _cache_set(ck, result)
    return result


def get_entity_flows_full(slug: str) -> dict | None:
    """Full flow data including token flows and exchange interactions."""
    ck = f"flows_full:{slug}"
    cached = _cache_get(ck)
    if cached:
        return cached

    db = _get_db()
    entity = db["entities_v2"].find_one({"slug": slug}, {"_id": 0})
    if not entity:
        return None

    stored = db["entity_flows_v2"].find_one({"entity_slug": slug}, {"_id": 0})
    if not stored:
        built = build_entity_flows(slug)
        if not built:
            return _empty_flows(entity)
        stored = built

    # Remove internal DB fields
    stored.pop("entity_slug", None)
    _cache_set(ck, stored)
    return stored


def get_entity_token_flows(slug: str) -> dict | None:
    """Token-level flow breakdown for an entity."""
    ck = f"token_flows:{slug}"
    cached = _cache_get(ck)
    if cached:
        return cached

    db = _get_db()
    entity = db["entities_v2"].find_one({"slug": slug}, {"_id": 0})
    if not entity:
        return None

    stored = db["entity_flows_v2"].find_one({"entity_slug": slug}, {"_id": 0})
    if not stored:
        built = build_entity_flows(slug)
        if not built:
            return None
        stored = built

    result = {
        "entity": stored.get("entity", {"slug": slug, "name": entity["name"], "type": entity["type"], "category": entity["category"]}),
        "token_flows": stored.get("token_flows", []),
        "total_tokens": len(stored.get("token_flows", [])),
        "computed_at": stored.get("computed_at"),
    }
    _cache_set(ck, result)
    return result


def build_all_entity_flows() -> dict:
    """Build flows for all entities."""
    db = _get_db()
    entities = list(db["entities_v2"].find({"status": "active"}, {"_id": 0, "slug": 1}))

    stats = {
        "total_entities": len(entities),
        "computed": 0,
        "with_flows": 0,
        "total_volume_usd": 0.0,
        "errors": 0,
    }

    for ent in entities:
        try:
            result = build_entity_flows(ent["slug"])
            if result:
                stats["computed"] += 1
                vol = result["all_time"]["inflow_usd"] + result["all_time"]["outflow_usd"]
                if vol > 0:
                    stats["with_flows"] += 1
                    stats["total_volume_usd"] += vol
        except Exception as e:
            stats["errors"] += 1
            print(f"[Flows] Error building for {ent['slug']}: {e}")

    stats["total_volume_usd"] = round(stats["total_volume_usd"], 2)
    stats["built_at"] = datetime.now(timezone.utc).isoformat()
    _cache.clear()
    return stats


def get_flows_overview() -> dict:
    """Overview of all entity flows — ranked by volume."""
    db = _get_db()
    flows_col = db["entity_flows_v2"]

    all_flows = list(flows_col.find(
        {}, {"_id": 0, "entity_slug": 1, "entity": 1, "all_time": 1,
             "flow_velocity": 1, "direction": 1, "meta": 1, "computed_at": 1},
    ))

    leaderboard = []
    for f in all_flows:
        at = f.get("all_time", {})
        vol = at.get("inflow_usd", 0) + at.get("outflow_usd", 0)
        leaderboard.append({
            "entity_slug": f.get("entity_slug"),
            "entity_name": (f.get("entity") or {}).get("name", f.get("entity_slug")),
            "inflow_usd": at.get("inflow_usd", 0),
            "outflow_usd": at.get("outflow_usd", 0),
            "net_flow_usd": at.get("net_flow_usd", 0),
            "total_volume_usd": round(vol, 2),
            "flow_velocity": f.get("flow_velocity", 0),
            "direction": f.get("direction", "no_activity"),
            "transfers": (f.get("meta") or {}).get("total_transfers", 0),
        })

    leaderboard.sort(key=lambda x: x["total_volume_usd"], reverse=True)

    total_volume = sum(e["total_volume_usd"] for e in leaderboard)
    with_flows = sum(1 for e in leaderboard if e["total_volume_usd"] > 0)

    return {
        "total_entities": len(leaderboard),
        "entities_with_flows": with_flows,
        "total_volume_usd": round(total_volume, 2),
        "leaderboard": leaderboard[:20],
    }
