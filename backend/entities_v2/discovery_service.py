"""
Entities V2 — Phase 12: Entity Discovery Engine
==================================================
Automatically discovers new market actors from unknown wallet clusters
and high-activity unattributed addresses.

Discovery Pipeline:
  entity_clusters_v2     → cluster candidates
  entity_attributions_v2 → filter low-attribution clusters
  onchain_v2_erc20_logs  → activity analysis, counterparty network
  entity_behaviour_v2    → behaviour coherence scoring
  entity_token_matrix_v2 → token pattern analysis

Score weights:
  0.30 cluster_size + 0.25 capital_activity + 0.20 behaviour_coherence
  + 0.15 token_pattern + 0.10 counterparty_network

Persisted to: entity_discovery_v2
"""

import os
import time
from datetime import datetime, timezone
from collections import defaultdict
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


# All known entity addresses (for exclusion)
def _get_all_entity_addrs(db) -> set:
    return set(a["address"].lower() for a in db["entity_addresses_v2"].find({}, {"_id": 0, "address": 1}))


# ══════════════════════════════════════════════════════════
#  DISCOVERY SIGNALS
# ══════════════════════════════════════════════════════════

def _score_cluster_size(members: list[dict]) -> tuple[float, list[str]]:
    """Signal 1: Cluster size (weight 0.30)."""
    size = len(members)
    reasons = []
    if size >= 15:
        score = 1.0
        reasons.append(f"large cluster: {size} wallets")
    elif size >= 8:
        score = 0.7
        reasons.append(f"medium cluster: {size} wallets")
    elif size >= 4:
        score = 0.4
        reasons.append(f"small cluster: {size} wallets")
    else:
        score = 0.1
    return round(score, 4), reasons


def _score_capital_activity(db, members: list[dict]) -> tuple[float, dict, list[str]]:
    """Signal 2: Capital activity (weight 0.25)."""
    addrs = [m["address"].lower() for m in members[:30]]
    reasons = []

    if not addrs:
        return 0.0, {}, []

    # Count total transfers
    out_count = db["onchain_v2_erc20_logs"].count_documents({"from": {"$in": addrs}})
    in_count = db["onchain_v2_erc20_logs"].count_documents({"to": {"$in": addrs}})
    total = out_count + in_count

    # Unique tokens
    out_tokens = set(db["onchain_v2_erc20_logs"].distinct("tokenAddress", {"from": {"$in": addrs}}))
    in_tokens = set(db["onchain_v2_erc20_logs"].distinct("tokenAddress", {"to": {"$in": addrs}}))
    all_tokens = out_tokens | in_tokens

    # Direction
    if total > 0:
        ratio = in_count / total
        direction = "inflow_dominant" if ratio >= 0.65 else ("outflow_dominant" if ratio <= 0.35 else "balanced")
    else:
        direction = "none"

    activity = {
        "total_transfers": total,
        "outbound": out_count,
        "inbound": in_count,
        "unique_tokens": len(all_tokens),
        "direction": direction,
    }

    # Score based on transfer volume
    if total >= 500:
        score = 1.0
        reasons.append("very high activity")
    elif total >= 100:
        score = 0.7
        reasons.append("high activity")
    elif total >= 20:
        score = 0.4
        reasons.append("moderate activity")
    elif total >= 5:
        score = 0.2
    else:
        score = 0.05

    return round(score, 4), activity, reasons


def _score_behaviour_coherence(activity: dict) -> tuple[float, str, list[str]]:
    """Signal 3: Behaviour coherence (weight 0.20). Infer behaviour from activity."""
    reasons = []
    direction = activity.get("direction", "none")
    total = activity.get("total_transfers", 0)
    tokens = activity.get("unique_tokens", 0)

    if total == 0:
        return 0.0, "unknown_cluster", []

    # Infer behaviour type
    if direction == "balanced" and tokens >= 10:
        beh_type = "possible_market_maker"
        score = 0.8
        reasons.append("balanced flows + token diversity")
    elif direction == "balanced" and total >= 50:
        beh_type = "possible_market_maker"
        score = 0.7
        reasons.append("high-volume balanced flows")
    elif direction == "inflow_dominant" and tokens >= 5:
        beh_type = "possible_fund"
        score = 0.6
        reasons.append("accumulation pattern")
    elif direction == "outflow_dominant" and tokens >= 5:
        beh_type = "possible_fund"
        score = 0.5
        reasons.append("distribution pattern")
    elif total >= 100:
        beh_type = "possible_whale"
        score = 0.6
        reasons.append("high transaction count")
    elif tokens >= 15:
        beh_type = "possible_protocol_actor"
        score = 0.5
        reasons.append("diverse token interaction")
    else:
        beh_type = "unknown_cluster"
        score = 0.2

    return round(score, 4), beh_type, reasons


def _score_token_pattern(db, members: list[dict], known_entity_addrs: set) -> tuple[float, list[str], list[str]]:
    """Signal 4: Token pattern (weight 0.15)."""
    addrs = [m["address"].lower() for m in members[:20]]
    reasons = []

    if not addrs:
        return 0.0, [], []

    tokens = list(db["onchain_v2_erc20_logs"].aggregate([
        {"$match": {"$or": [{"from": {"$in": addrs}}, {"to": {"$in": addrs}}]}},
        {"$group": {"_id": "$tokenAddress", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10},
    ]))

    if not tokens:
        return 0.0, [], []

    # Look up token symbols from token_registry
    dominant_tokens = []
    for t in tokens[:5]:
        tr = db["token_registry"].find_one({"address": t["_id"]}, {"_id": 0, "symbol": 1})
        sym = tr["symbol"] if tr else t["_id"][:8]
        dominant_tokens.append(sym)

    # Score: more concentrated = more interesting
    total_txs = sum(t["count"] for t in tokens)
    top3_share = sum(t["count"] for t in tokens[:3]) / total_txs if total_txs > 0 else 0

    if top3_share >= 0.8:
        score = 0.8
        reasons.append(f"concentrated tokens: {', '.join(dominant_tokens[:3])}")
    elif top3_share >= 0.5:
        score = 0.5
        reasons.append(f"dominant tokens: {', '.join(dominant_tokens[:3])}")
    else:
        score = 0.3
        reasons.append("diverse token pattern")

    return round(score, 4), dominant_tokens, reasons


def _score_counterparty_network(db, members: list[dict], known_entity_addrs: set) -> tuple[float, list[str]]:
    """Signal 5: Counterparty network (weight 0.10)."""
    addrs = [m["address"].lower() for m in members[:20]]
    reasons = []

    if not addrs:
        return 0.0, []

    # Find counterparties
    cps_out = set(db["onchain_v2_erc20_logs"].distinct("to", {"from": {"$in": addrs}}))
    cps_in = set(db["onchain_v2_erc20_logs"].distinct("from", {"to": {"$in": addrs}}))
    all_cps = cps_out | cps_in

    # How many known entities does this cluster interact with?
    known_interactions = all_cps & known_entity_addrs
    num_known = len(known_interactions)

    if num_known >= 5:
        score = 1.0
        reasons.append(f"interacts with {num_known} known entities")
    elif num_known >= 3:
        score = 0.7
        reasons.append(f"connected to {num_known} known entities")
    elif num_known >= 1:
        score = 0.4
        reasons.append("some entity connections")
    else:
        score = 0.1

    return round(score, 4), reasons


def _classify_type(beh_type: str, activity: dict) -> str:
    """Final type classification."""
    return beh_type


# ══════════════════════════════════════════════════════════
#  DISCOVERY BUILDER
# ══════════════════════════════════════════════════════════

def build_discovery() -> dict:
    """Run the discovery engine across all clusters."""
    db = _get_db()
    known_addrs = _get_all_entity_addrs(db)

    # Get all cluster data
    all_cluster_docs = list(db["entity_clusters_v2"].find({}, {"_id": 0}))

    # Get all attributions (to filter out well-attributed clusters)
    attr_map = {}
    for a in db["entity_attributions_v2"].find({}, {"_id": 0}):
        attr_map[a["cluster_id"]] = a

    candidates = []

    for doc in all_cluster_docs:
        parent_entity = doc.get("entity_slug", doc.get("entity", {}).get("slug", "?"))

        for cl in doc.get("clusters", []):
            cluster_id = cl["cluster_id"]
            members = cl.get("members", [])

            if len(members) < 2:
                continue

            # Check attribution — skip clusters that are well-attributed to parent
            attr = attr_map.get(cluster_id, {})
            attr_score = attr.get("attribution_score", 0)
            attr_entity = attr.get("possible_entity", "")

            # If well-attributed to parent, skip (it's already identified)
            if attr_score >= 0.70 and attr_entity == parent_entity:
                continue

            # Score all signals
            size_score, size_reasons = _score_cluster_size(members)
            cap_score, activity, cap_reasons = _score_capital_activity(db, members)
            beh_score, beh_type, beh_reasons = _score_behaviour_coherence(activity)
            tok_score, dominant_tokens, tok_reasons = _score_token_pattern(db, members, known_addrs)
            cp_score, cp_reasons = _score_counterparty_network(db, members, known_addrs)

            # Composite discovery score
            discovery_score = round(
                size_score * 0.30
                + cap_score * 0.25
                + beh_score * 0.20
                + tok_score * 0.15
                + cp_score * 0.10,
                4,
            )

            candidate_type = _classify_type(beh_type, activity)
            all_reasons = size_reasons + cap_reasons + beh_reasons + tok_reasons + cp_reasons

            candidate = {
                "cluster_id": cluster_id,
                "parent_entity": parent_entity,
                "candidate_type": candidate_type,
                "discovery_score": discovery_score,
                "confidence": round(min(1.0, discovery_score * 1.2), 2),
                "wallets": len(members),
                "dominant_tokens": dominant_tokens[:5],
                "signals": all_reasons[:6],
                "components": {
                    "cluster_size": size_score,
                    "capital_activity": cap_score,
                    "behaviour_coherence": beh_score,
                    "token_pattern": tok_score,
                    "counterparty_network": cp_score,
                },
                "activity": activity,
                "attribution": {
                    "current_score": attr_score,
                    "current_entity": attr_entity,
                    "level": attr.get("attribution_level", "unknown"),
                },
            }

            candidates.append(candidate)

            # Persist
            db["entity_discovery_v2"].update_one(
                {"cluster_id": cluster_id},
                {"$set": {**candidate, "computed_at": datetime.now(timezone.utc).isoformat()}},
                upsert=True,
            )

    candidates.sort(key=lambda x: x["discovery_score"], reverse=True)

    # Create index
    db["entity_discovery_v2"].create_index([("cluster_id", ASCENDING)], unique=True, background=True)

    # Stats
    type_dist = {}
    for c in candidates:
        t = c["candidate_type"]
        type_dist[t] = type_dist.get(t, 0) + 1

    now = datetime.now(timezone.utc)
    stats = {
        "total_candidates": len(candidates),
        "type_distribution": type_dist,
        "top_candidates": candidates[:10],
        "built_at": now.isoformat(),
    }

    _cache.clear()
    return stats


# ══════════════════════════════════════════════════════════
#  QUERY FUNCTIONS
# ══════════════════════════════════════════════════════════

def get_discovery_candidates() -> dict:
    """Get all discovery candidates."""
    ck = "discovery:all"
    cached = _cache_get(ck)
    if cached:
        return cached

    db = _get_db()
    all_disc = list(db["entity_discovery_v2"].find({}, {"_id": 0}))

    if not all_disc:
        return {"total_candidates": 0, "type_distribution": {}, "candidates": []}

    all_disc.sort(key=lambda x: x.get("discovery_score", 0), reverse=True)

    # Resolve wallet addresses from cluster members
    cluster_ids = set()
    for c in all_disc:
        cid = c.get("cluster_id", "")
        if cid:
            parent = cid.rsplit("_cluster_", 1)[0] if "_cluster_" in cid else ""
            if parent:
                cluster_ids.add(parent)
    cluster_members = {}
    for parent_slug in cluster_ids:
        doc = db["entity_clusters_v2"].find_one(
            {"entity_slug": parent_slug}, {"_id": 0, "clusters": 1}
        )
        if doc:
            for cl in (doc.get("clusters") or []):
                cid = cl.get("cluster_id", "")
                members = cl.get("members", [])
                cluster_members[cid] = [m.get("address", "").lower() for m in members[:5] if m.get("address")]

    for c in all_disc:
        cid = c.get("cluster_id", "")
        c["wallet_addresses"] = cluster_members.get(cid, [])[:5]

    type_dist = {}
    for c in all_disc:
        t = c.get("candidate_type", "unknown_cluster")
        type_dist[t] = type_dist.get(t, 0) + 1

    result = {
        "total_candidates": len(all_disc),
        "type_distribution": type_dist,
        "candidates": all_disc,
    }

    _cache_set(ck, result)
    return result


def get_discovery_detail(cluster_id: str) -> dict | None:
    """Get discovery details for a specific cluster."""
    ck = f"discovery:{cluster_id}"
    cached = _cache_get(ck)
    if cached:
        return cached

    db = _get_db()
    stored = db["entity_discovery_v2"].find_one({"cluster_id": cluster_id}, {"_id": 0})
    if stored:
        _cache_set(ck, stored)
        return stored

    return None
