"""
Entities V2 — Phase 8: Clustering Engine
==========================================
Automatically groups wallets into clusters based on on-chain
activity patterns around known entity addresses.

Clustering Signals:
  1. Shared counterparties — wallets interacting with same addresses
  2. Direct funding — wallets with direct transfers to/from entity
  3. Temporal correlation — transactions in similar time windows
  4. Token overlap — wallets trading same tokens as entity

Pipeline:
  entity_addresses_v2 → onchain_v2_erc20_logs
    → counterparty graph → signal scoring → cluster formation

Persisted to: entity_clusters_v2
"""

import os
import time
from datetime import datetime, timezone
from collections import defaultdict
from pymongo import MongoClient, ASCENDING
from mock_wallets import get_wallets_for_entity

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


# ══════════════════════════════════════════════════════════
#  CLUSTER BUILDER
# ══════════════════════════════════════════════════════════

def _build_counterparty_graph(db, entity_addrs: list[str]) -> dict:
    """Build counterparty interaction graph around entity addresses."""
    addr_set = set(a.lower() for a in entity_addrs)

    # All known entity addresses globally (to exclude from clusters)
    all_entity_addrs = set(
        a["address"].lower()
        for a in db["entity_addresses_v2"].find({}, {"_id": 0, "address": 1})
    )

    # Find outbound transfers: entity → counterparty
    outbound = db["onchain_v2_erc20_logs"].aggregate([
        {"$match": {"from": {"$in": list(addr_set)}}},
        {"$group": {
            "_id": "$to",
            "transfer_count": {"$sum": 1},
            "entity_sources": {"$addToSet": "$from"},
            "tokens": {"$addToSet": "$tokenAddress"},
            "blocks": {"$push": "$blockNumber"},
        }},
    ])

    # Find inbound transfers: counterparty → entity
    inbound = db["onchain_v2_erc20_logs"].aggregate([
        {"$match": {"to": {"$in": list(addr_set)}}},
        {"$group": {
            "_id": "$from",
            "transfer_count": {"$sum": 1},
            "entity_targets": {"$addToSet": "$to"},
            "tokens": {"$addToSet": "$tokenAddress"},
            "blocks": {"$push": "$blockNumber"},
        }},
    ])

    # Merge into counterparty graph
    graph: dict = {}

    for doc in outbound:
        addr = doc["_id"].lower()
        if addr in all_entity_addrs:
            continue
        graph[addr] = {
            "outbound_count": doc["transfer_count"],
            "inbound_count": 0,
            "entity_links_out": len(doc["entity_sources"]),
            "entity_links_in": 0,
            "tokens_out": set(doc["tokens"]),
            "tokens_in": set(),
            "blocks_out": doc["blocks"],
            "blocks_in": [],
        }

    for doc in inbound:
        addr = doc["_id"].lower()
        if addr in all_entity_addrs:
            continue
        if addr not in graph:
            graph[addr] = {
                "outbound_count": 0,
                "inbound_count": 0,
                "entity_links_out": 0,
                "entity_links_in": 0,
                "tokens_out": set(),
                "tokens_in": set(),
                "blocks_out": [],
                "blocks_in": [],
            }
        graph[addr]["inbound_count"] = doc["transfer_count"]
        graph[addr]["entity_links_in"] = len(doc["entity_targets"])
        graph[addr]["tokens_in"] = set(doc["tokens"])
        graph[addr]["blocks_in"] = doc["blocks"]

    return graph


def _score_cluster_candidate(info: dict, entity_token_set: set) -> dict:
    """Score a wallet as a potential cluster member."""
    total_transfers = info["outbound_count"] + info["inbound_count"]
    entity_links = info["entity_links_out"] + info["entity_links_in"]
    all_tokens = info["tokens_out"] | info["tokens_in"]

    # Signal 1: Direct interaction frequency
    interaction_score = min(1.0, total_transfers / 10)

    # Signal 2: Multi-address links (interacts with multiple entity addresses)
    multi_link_score = min(1.0, (entity_links - 1) / 3) if entity_links > 1 else 0

    # Signal 3: Bi-directional (both sends and receives)
    bidirectional = 1.0 if info["outbound_count"] > 0 and info["inbound_count"] > 0 else 0.0

    # Signal 4: Token overlap with entity
    token_overlap = 0.0
    if all_tokens and entity_token_set:
        shared = all_tokens & entity_token_set
        token_overlap = len(shared) / max(len(all_tokens), 1)

    # Signal 5: Temporal clustering (transactions in nearby blocks)
    all_blocks = sorted(info["blocks_out"] + info["blocks_in"])
    temporal_score = 0.0
    if len(all_blocks) >= 2:
        # Check if transactions are clustered (within 100 blocks ~ 20 min)
        gaps = [all_blocks[i + 1] - all_blocks[i] for i in range(len(all_blocks) - 1)]
        avg_gap = sum(gaps) / len(gaps) if gaps else float("inf")
        if avg_gap <= 100:
            temporal_score = 1.0
        elif avg_gap <= 1000:
            temporal_score = 0.5
        elif avg_gap <= 10000:
            temporal_score = 0.2

    # Composite confidence
    confidence = round(
        interaction_score * 0.25
        + multi_link_score * 0.25
        + bidirectional * 0.15
        + token_overlap * 0.20
        + temporal_score * 0.15,
        4,
    )

    # Determine role
    if info["inbound_count"] > info["outbound_count"] * 2:
        role = "receiver"
    elif info["outbound_count"] > info["inbound_count"] * 2:
        role = "sender"
    elif bidirectional:
        role = "intermediary"
    else:
        role = "peripheral"

    return {
        "confidence": confidence,
        "role": role,
        "signals": {
            "interaction": round(interaction_score, 4),
            "multi_link": round(multi_link_score, 4),
            "bidirectional": bidirectional,
            "token_overlap": round(token_overlap, 4),
            "temporal": round(temporal_score, 4),
        },
        "transfer_count": total_transfers,
        "entity_links": entity_links,
        "unique_tokens": len(all_tokens),
    }


def _form_clusters(candidates: list[dict], min_confidence: float = 0.10) -> list[dict]:
    """Group scored candidates into clusters by confidence tiers."""
    filtered = [c for c in candidates if c["confidence"] >= min_confidence]
    if not filtered:
        return []

    filtered.sort(key=lambda x: x["confidence"], reverse=True)

    # Tier-based clustering
    clusters = []

    # Tier 1: High confidence (>= 0.40)
    high = [c for c in filtered if c["confidence"] >= 0.40]
    if high:
        clusters.append({
            "tier": "high",
            "min_confidence": 0.40,
            "members": high,
        })

    # Tier 2: Medium confidence (0.20 - 0.40)
    medium = [c for c in filtered if 0.20 <= c["confidence"] < 0.40]
    if medium:
        clusters.append({
            "tier": "medium",
            "min_confidence": 0.20,
            "members": medium,
        })

    # Tier 3: Low confidence (0.10 - 0.20)
    low = [c for c in filtered if 0.10 <= c["confidence"] < 0.20]
    if low:
        clusters.append({
            "tier": "low",
            "min_confidence": 0.10,
            "members": low,
        })

    return clusters


def _get_entity_token_set(db, entity_addrs: list[str]) -> set:
    """Get set of tokens traded by entity addresses."""
    addr_set = list(set(a.lower() for a in entity_addrs))
    tokens_out = db["onchain_v2_erc20_logs"].distinct("tokenAddress", {"from": {"$in": addr_set}})
    tokens_in = db["onchain_v2_erc20_logs"].distinct("tokenAddress", {"to": {"$in": addr_set}})
    return set(t.lower() for t in tokens_out + tokens_in)


# ══════════════════════════════════════════════════════════
#  PUBLIC API
# ══════════════════════════════════════════════════════════

def build_entity_clusters(slug: str) -> dict | None:
    """Build wallet clusters for a single entity."""
    db = _get_db()
    entity = db["entities_v2"].find_one({"slug": slug}, {"_id": 0})
    if not entity:
        return None

    # Get entity addresses
    addrs = list(db["entity_addresses_v2"].find(
        {"entity_slug": slug}, {"_id": 0, "address": 1}
    ))
    entity_addrs = [a["address"] for a in addrs]

    if not entity_addrs:
        return _empty_clusters(entity)

    # Build counterparty graph
    graph = _build_counterparty_graph(db, entity_addrs)

    if not graph:
        return _empty_clusters(entity)

    # Get entity token set for overlap scoring
    entity_tokens = _get_entity_token_set(db, entity_addrs)

    # Score all counterparties
    candidates = []
    for addr, info in graph.items():
        score_data = _score_cluster_candidate(info, entity_tokens)
        candidates.append({
            "address": addr,
            **score_data,
        })

    # Form clusters
    clusters = _form_clusters(candidates)

    # Compute cluster-level metrics
    cluster_results = []
    cluster_idx = 0
    total_discovered = 0

    for cl in clusters:
        cluster_idx += 1
        members = cl["members"]
        total_discovered += len(members)

        total_transfers = sum(m["transfer_count"] for m in members)
        avg_confidence = round(sum(m["confidence"] for m in members) / len(members), 4)

        # Activity score: based on avg transfers and token diversity
        avg_tokens = sum(m["unique_tokens"] for m in members) / len(members)
        activity_score = round(min(1.0, (total_transfers / (len(members) * 5)) * 0.6 + (avg_tokens / 10) * 0.4), 4)

        cluster_results.append({
            "cluster_id": f"{slug}_cluster_{cluster_idx}",
            "tier": cl["tier"],
            "size": len(members),
            "confidence": avg_confidence,
            "activity_score": activity_score,
            "total_transfers": total_transfers,
            "members": [
                {
                    "address": m["address"],
                    "confidence": m["confidence"],
                    "role": m["role"],
                    "transfer_count": m["transfer_count"],
                    "entity_links": m["entity_links"],
                    "unique_tokens": m["unique_tokens"],
                }
                for m in members[:50]  # Cap per cluster
            ],
        })

    now = datetime.now(timezone.utc)

    result = {
        "entity": {
            "slug": entity["slug"],
            "name": entity["name"],
            "type": entity["type"],
            "category": entity["category"],
        },
        "known_addresses": len(entity_addrs),
        "total_counterparties": len(graph),
        "total_discovered": total_discovered,
        "clusters": cluster_results,
        "coverage_expansion": round(total_discovered / max(len(entity_addrs), 1), 2),
        "computed_at": now.isoformat(),
    }

    # Persist
    col = db["entity_clusters_v2"]
    col.create_index([("entity_slug", ASCENDING)], unique=True, background=True)
    col.update_one(
        {"entity_slug": slug},
        {"$set": {"entity_slug": slug, **result, "computed_at": now.isoformat()}},
        upsert=True,
    )

    _cache.clear()
    return result


def _empty_clusters(entity: dict) -> dict:
    return {
        "entity": {
            "slug": entity["slug"], "name": entity["name"],
            "type": entity["type"], "category": entity["category"],
        },
        "known_addresses": 0,
        "total_counterparties": 0,
        "total_discovered": 0,
        "clusters": [],
        "coverage_expansion": 0,
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }


def build_all_clusters() -> dict:
    """Build clusters for all entities."""
    db = _get_db()
    entities = list(db["entities_v2"].find({"status": "active"}, {"_id": 0, "slug": 1}))

    stats = {
        "total_entities": len(entities),
        "computed": 0,
        "total_discovered": 0,
        "entities_with_clusters": 0,
        "errors": 0,
    }

    for ent in entities:
        try:
            result = build_entity_clusters(ent["slug"])
            if result:
                stats["computed"] += 1
                disc = result["total_discovered"]
                stats["total_discovered"] += disc
                if disc > 0:
                    stats["entities_with_clusters"] += 1
        except Exception as e:
            stats["errors"] += 1
            print(f"[Clustering] Error for {ent['slug']}: {e}")

    stats["built_at"] = datetime.now(timezone.utc).isoformat()
    _cache.clear()
    return stats


# ══════════════════════════════════════════════════════════
#  QUERY FUNCTIONS
# ══════════════════════════════════════════════════════════

def get_entity_clusters(slug: str) -> dict | None:
    """Get wallet clusters for an entity."""
    ck = f"clusters:{slug}"
    cached = _cache_get(ck)
    if cached:
        return cached

    db = _get_db()
    entity = db["entities_v2"].find_one({"slug": slug}, {"_id": 0})
    if not entity:
        return None

    stored = db["entity_clusters_v2"].find_one({"entity_slug": slug}, {"_id": 0})
    if stored:
        stored.pop("entity_slug", None)
        _cache_set(ck, stored)
        return stored

    # Compute on-the-fly
    result = build_entity_clusters(slug)
    if result:
        _cache_set(ck, result)
    return result


def get_clusters_overview() -> dict:
    """Overview of all entity clusters."""
    db = _get_db()
    all_clusters = list(db["entity_clusters_v2"].find({}, {"_id": 0}))

    if not all_clusters:
        return {
            "total_entities": 0,
            "entities_with_clusters": 0,
            "total_discovered": 0,
            "entities": [],
        }

    entity_list = []
    total_disc = 0
    with_clusters = 0

    for c in all_clusters:
        disc = c.get("total_discovered", 0)
        total_disc += disc
        if disc > 0:
            with_clusters += 1

        entity_name = c.get("entity", {}).get("name", "?")
        entity_slug = c.get("entity", {}).get("slug", c.get("entity_slug", "?"))

        entity_list.append({
            "slug": entity_slug,
            "name": entity_name,
            "type": c.get("entity", {}).get("type", "?"),
            "known_addresses": c.get("known_addresses", 0),
            "total_counterparties": c.get("total_counterparties", 0),
            "total_discovered": disc,
            "cluster_count": len(c.get("clusters", [])),
            "coverage_expansion": c.get("coverage_expansion", 0),
            "wallet_addresses": get_wallets_for_entity(entity_name, limit=3),
        })

    entity_list.sort(key=lambda x: x["total_discovered"], reverse=True)

    return {
        "total_entities": len(all_clusters),
        "entities_with_clusters": with_clusters,
        "total_discovered": total_disc,
        "entities": entity_list,
    }
