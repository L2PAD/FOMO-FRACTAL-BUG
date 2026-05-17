"""
Entities V2 — Phase 11: Multichain Expansion
==============================================
Extends entity intelligence across multiple chains.

Pipeline:
  entity_addresses_v2 + entity_clusters_v2
    → per-chain activity in onchain_v2_erc20_logs
    → chain distribution, cross-chain flows, bridge detection

Supported chains:
  1      = Ethereum
  10     = Optimism
  42161  = Arbitrum
  8453   = Base

Persisted to: entity_chains_v2
"""

import os
import time
from datetime import datetime, timezone
from pymongo import MongoClient, ASCENDING

_client = None
_db = None


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


CHAIN_MAP = {
    1: {"name": "Ethereum", "short": "ETH", "type": "L1"},
    10: {"name": "Optimism", "short": "OP", "type": "L2"},
    42161: {"name": "Arbitrum", "short": "ARB", "type": "L2"},
    8453: {"name": "Base", "short": "BASE", "type": "L2"},
}

KNOWN_BRIDGES = {
    "0x99c9fc46f92e8a1c0dec1b1747d010903e884be1": "Optimism Bridge",
    "0x3154cf16ccdb4c6d922629664174b904d80f2c35": "Optimism Bridge L2",
    "0x4dbd4fc535ac27206064b68ffcf827b0a60bab3f": "Arbitrum Bridge",
    "0x8315177ab297ba92a06054ce80a67ed4dbd7ed3a": "Arbitrum Bridge L1",
    "0x3666f603cc164936c1b87e207f36beba4ac5f18a": "Base Bridge",
    "0x49048044d57e1c92a77f79988d21fa8faf74e97e": "Base Bridge L1",
    "0x1231deb6f5749ef6ce6943a275a1d3e7486f4eae": "LiFi Diamond",
    "0x2796317b0ff8538f253012862c06787adfb8ceb6": "Synapse Bridge",
    "0x3a23f943181408eac424116af7b7790c94cb97a5": "Socket Gateway",
}


def _get_entity_addresses(db, slug: str) -> list[str]:
    """Get entity addresses (known + top cluster members, capped for performance)."""
    known = [
        a["address"].lower()
        for a in db["entity_addresses_v2"].find({"entity_slug": slug}, {"_id": 0, "address": 1})
    ]
    cluster_doc = db["entity_clusters_v2"].find_one({"entity_slug": slug}, {"_id": 0, "clusters": 1})
    discovered = []
    if cluster_doc:
        for cl in cluster_doc.get("clusters", []):
            if cl["tier"] == "high":
                for m in cl.get("members", [])[:10]:  # Cap per cluster
                    discovered.append(m["address"].lower())
    # Total cap to keep queries fast on 1M+ docs
    return list(set(known + discovered))[:20]


def _analyze_chain_activity(db, addresses: list[str], chain_id: int) -> dict | None:
    """Analyze entity activity on a specific chain. Two indexed queries."""
    if not addresses:
        return None

    col = db["onchain_v2_erc20_logs"]

    # Outbound: uses chainId_1_from_1 index
    out_agg = list(col.aggregate([
        {"$match": {"chainId": chain_id, "from": {"$in": addresses}}},
        {"$group": {
            "_id": None, "count": {"$sum": 1},
            "tokens": {"$addToSet": "$tokenAddress"},
            "cps": {"$addToSet": "$to"},
            "senders": {"$addToSet": "$from"},
        }},
    ]))

    # Inbound: uses chainId_1_to_1 index
    in_agg = list(col.aggregate([
        {"$match": {"chainId": chain_id, "to": {"$in": addresses}}},
        {"$group": {
            "_id": None, "count": {"$sum": 1},
            "tokens": {"$addToSet": "$tokenAddress"},
            "cps": {"$addToSet": "$from"},
            "receivers": {"$addToSet": "$to"},
        }},
    ]))

    out_d = out_agg[0] if out_agg else {}
    in_d = in_agg[0] if in_agg else {}

    out_count = out_d.get("count", 0)
    in_count = in_d.get("count", 0)
    total = out_count + in_count

    if total == 0:
        return None

    all_tokens = set(out_d.get("tokens", [])) | set(in_d.get("tokens", []))
    all_cps = set(out_d.get("cps", [])) | set(in_d.get("cps", []))
    active_addrs = set(out_d.get("senders", [])) | set(in_d.get("receivers", []))

    bridge_interactions = [KNOWN_BRIDGES[a.lower()] for a in all_cps if a.lower() in KNOWN_BRIDGES]

    ratio = in_count / total
    direction = "inflow_dominant" if ratio >= 0.65 else ("outflow_dominant" if ratio <= 0.35 else "balanced")

    activity_score = min(100, round(
        (min(total, 1000) / 1000) * 40 + (min(len(all_tokens), 50) / 50) * 30 + (min(len(all_cps), 100) / 100) * 30
    ))

    ci = CHAIN_MAP.get(chain_id, {"name": f"Chain {chain_id}", "short": str(chain_id), "type": "unknown"})

    return {
        "chain_id": chain_id, "chain_name": ci["name"], "chain_short": ci["short"], "chain_type": ci["type"],
        "active_addresses": len(active_addrs),
        "outbound_transfers": out_count, "inbound_transfers": in_count, "total_transfers": total,
        "direction": direction, "unique_tokens": len(all_tokens),
        "unique_counterparties": len(all_cps), "activity_score": activity_score,
        "bridge_interactions": list(set(bridge_interactions)),
        "has_bridge_activity": len(bridge_interactions) > 0,
    }


def _detect_cross_chain(db, addresses: list[str]) -> list[dict]:
    """Find addresses active on multiple chains. Uses indexed queries."""
    cross = []
    col = db["onchain_v2_erc20_logs"]
    for addr in addresses[:8]:
        chains_active = []
        for cid in CHAIN_MAP:
            # Uses chainId_1_from_1 and chainId_1_to_1 indexes
            if col.find_one({"chainId": cid, "from": addr}, {"_id": 1}) or \
               col.find_one({"chainId": cid, "to": addr}, {"_id": 1}):
                chains_active.append({"chain_id": cid, "chain_name": CHAIN_MAP[cid]["name"]})
        if len(chains_active) >= 2:
            cross.append({"address": addr, "chains": chains_active, "chain_count": len(chains_active)})
    cross.sort(key=lambda x: x["chain_count"], reverse=True)
    return cross


def _bridge_summary(chains: list[dict]) -> list[dict]:
    bridges: dict = {}
    for ch in chains:
        for b in ch.get("bridge_interactions", []):
            if b not in bridges:
                bridges[b] = {"bridge": b, "chains": []}
            bridges[b]["chains"].append(ch["chain_name"])
    return list(bridges.values())


# ══════════════════════════════════════════════════════════
#  PUBLIC API
# ══════════════════════════════════════════════════════════

def build_entity_chains(slug: str) -> dict | None:
    db = _get_db()
    entity = db["entities_v2"].find_one({"slug": slug}, {"_id": 0})
    if not entity:
        return None

    addresses = _get_entity_addresses(db, slug)
    if not addresses:
        return _empty(entity)

    chains = []
    total_transfers = 0
    for cid in CHAIN_MAP:
        activity = _analyze_chain_activity(db, addresses, cid)
        if activity:
            chains.append(activity)
            total_transfers += activity["total_transfers"]

    for ch in chains:
        ch["distribution_share"] = round(ch["total_transfers"] / total_transfers, 4) if total_transfers > 0 else 0

    chains.sort(key=lambda x: x["total_transfers"], reverse=True)
    cross = _detect_cross_chain(db, addresses[:10])
    dominant = chains[0] if chains else None

    now = datetime.now(timezone.utc)
    result = {
        "entity": {"slug": entity["slug"], "name": entity["name"], "type": entity["type"], "category": entity["category"]},
        "total_addresses": len(addresses),
        "total_chains_active": len(chains),
        "total_transfers": total_transfers,
        "dominant_chain": {
            "chain_name": dominant["chain_name"], "chain_id": dominant["chain_id"],
            "distribution_share": dominant["distribution_share"], "transfers": dominant["total_transfers"],
        } if dominant else None,
        "chains": chains,
        "cross_chain_addresses": cross[:10],
        "cross_chain_count": len(cross),
        "has_multichain_activity": len(chains) >= 2,
        "bridge_summary": _bridge_summary(chains),
        "computed_at": now.isoformat(),
    }

    col = db["entity_chains_v2"]
    col.create_index([("entity_slug", ASCENDING)], unique=True, background=True)
    col.update_one({"entity_slug": slug}, {"$set": {"entity_slug": slug, **result, "computed_at": now.isoformat()}}, upsert=True)
    _cache.clear()
    return result


def _empty(entity: dict) -> dict:
    return {
        "entity": {"slug": entity["slug"], "name": entity["name"], "type": entity["type"], "category": entity["category"]},
        "total_addresses": 0, "total_chains_active": 0, "total_transfers": 0,
        "dominant_chain": None, "chains": [], "cross_chain_addresses": [],
        "cross_chain_count": 0, "has_multichain_activity": False, "bridge_summary": [],
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }


def build_all_chains() -> dict:
    db = _get_db()
    entities = list(db["entities_v2"].find({"status": "active"}, {"_id": 0, "slug": 1}))

    stats = {"total_entities": len(entities), "computed": 0, "multichain_entities": 0, "chain_coverage": {}, "errors": 0}

    for ent in entities:
        try:
            result = build_entity_chains(ent["slug"])
            if result:
                stats["computed"] += 1
                if result["has_multichain_activity"]:
                    stats["multichain_entities"] += 1
                for ch in result.get("chains", []):
                    cn = ch["chain_name"]
                    stats["chain_coverage"][cn] = stats["chain_coverage"].get(cn, 0) + 1
        except Exception as e:
            stats["errors"] += 1
            print(f"[Multichain] Error for {ent['slug']}: {e}")

    stats["built_at"] = datetime.now(timezone.utc).isoformat()
    _cache.clear()
    return stats


# ══════════════════════════════════════════════════════════
#  QUERY FUNCTIONS
# ══════════════════════════════════════════════════════════

def get_entity_chains(slug: str) -> dict | None:
    ck = f"chains:{slug}"
    cached = _cache_get(ck)
    if cached:
        return cached

    db = _get_db()
    entity = db["entities_v2"].find_one({"slug": slug}, {"_id": 0})
    if not entity:
        return None

    stored = db["entity_chains_v2"].find_one({"entity_slug": slug}, {"_id": 0})
    if stored:
        stored.pop("entity_slug", None)
        _cache_set(ck, stored)
        return stored

    result = build_entity_chains(slug)
    if result:
        _cache_set(ck, result)
    return result


def get_chains_overview() -> dict:
    db = _get_db()
    all_chains = list(db["entity_chains_v2"].find({}, {"_id": 0}))

    if not all_chains:
        return {"total_entities": 0, "multichain_entities": 0, "chain_coverage": {}, "entities": []}

    chain_stats: dict = {}
    entity_list = []
    multichain = 0

    for doc in all_chains:
        slug = doc.get("entity", {}).get("slug", doc.get("entity_slug", "?"))
        ca = doc.get("total_chains_active", 0)
        if ca >= 2:
            multichain += 1

        entity_list.append({
            "slug": slug,
            "name": doc.get("entity", {}).get("name", slug),
            "type": doc.get("entity", {}).get("type", "?"),
            "chains_active": ca,
            "total_transfers": doc.get("total_transfers", 0),
            "dominant_chain": doc.get("dominant_chain", {}).get("chain_name") if doc.get("dominant_chain") else None,
            "has_multichain": doc.get("has_multichain_activity", False),
            "cross_chain_count": doc.get("cross_chain_count", 0),
        })

        for ch in doc.get("chains", []):
            cn = ch["chain_name"]
            if cn not in chain_stats:
                chain_stats[cn] = {"chain_name": cn, "entities": 0, "total_transfers": 0}
            chain_stats[cn]["entities"] += 1
            chain_stats[cn]["total_transfers"] += ch["total_transfers"]

    entity_list.sort(key=lambda x: x["total_transfers"], reverse=True)

    return {
        "total_entities": len(all_chains),
        "multichain_entities": multichain,
        "chain_coverage": list(chain_stats.values()),
        "entities": entity_list,
    }
