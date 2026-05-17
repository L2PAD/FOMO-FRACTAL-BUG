"""
Entities V2 — Phase 9: Attribution Engine
==========================================
Hypothesizes entity identity for unknown wallet clusters.

Pipeline:
  entity_clusters_v2     → cluster members (discovered wallets)
  entity_behaviour_v2    → behaviour profiles for matching
  entity_token_matrix_v2 → token activity for matching
  entity_similarity_v2   → similarity scores
  onchain_v2_erc20_logs  → counterparty analysis

Score weights:
  0.35 counterparty_overlap + 0.25 behaviour_match
  + 0.25 token_activity + 0.15 flow_pattern

Attribution levels:
  known     (>= 0.80) — high-confidence match to known entity
  likely    (>= 0.50) — probable match
  possible  (>= 0.30) — weak hypothesis
  unknown   (< 0.30)  — unidentified actor

Persisted to: entity_attributions_v2
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


# ══════════════════════════════════════════════════════════
#  DATA LOADERS
# ══════════════════════════════════════════════════════════

def _load_entity_profiles(db) -> dict:
    """Load all entity profiles for attribution matching."""
    profiles = {}

    # Behaviour
    for b in db["entity_behaviour_v2"].find({}, {"_id": 0}):
        slug = b.get("entity_slug", "")
        if slug not in profiles:
            profiles[slug] = {}
        profiles[slug]["behaviour"] = b

    # Token matrix
    for m in db["entity_token_matrix_v2"].find({}, {"_id": 0}):
        slug = m.get("entity_slug", "")
        if slug not in profiles:
            profiles[slug] = {}
        profiles[slug]["matrix"] = m

    # Flows
    for f in db["entity_flows_v2"].find({}, {"_id": 0}):
        slug = f.get("entity_slug", "")
        if slug not in profiles:
            profiles[slug] = {}
        profiles[slug]["flows"] = f

    # Addresses (for counterparty matching)
    addr_map: dict = {}
    for a in db["entity_addresses_v2"].find({}, {"_id": 0}):
        addr = a["address"].lower()
        addr_map[addr] = a["entity_slug"]

    return profiles, addr_map


def _analyze_cluster_activity(db, cluster_members: list[dict]) -> dict:
    """Analyze on-chain activity of cluster members."""
    addrs = [m["address"].lower() for m in cluster_members[:50]]

    if not addrs:
        return {"counterparties": {}, "tokens": set(), "total_transfers": 0, "direction": "unknown"}

    # Outbound transfers from cluster wallets
    out_pipe = [
        {"$match": {"from": {"$in": addrs}}},
        {"$group": {
            "_id": "$to",
            "count": {"$sum": 1},
            "tokens": {"$addToSet": "$tokenAddress"},
        }},
        {"$sort": {"count": -1}},
        {"$limit": 50},
    ]

    # Inbound transfers to cluster wallets
    in_pipe = [
        {"$match": {"to": {"$in": addrs}}},
        {"$group": {
            "_id": "$from",
            "count": {"$sum": 1},
            "tokens": {"$addToSet": "$tokenAddress"},
        }},
        {"$sort": {"count": -1}},
        {"$limit": 50},
    ]

    counterparties: dict = {}
    total_out = 0
    total_in = 0
    all_tokens: set = set()

    for doc in db["onchain_v2_erc20_logs"].aggregate(out_pipe):
        addr = doc["_id"].lower()
        counterparties[addr] = counterparties.get(addr, {"out": 0, "in": 0, "tokens": set()})
        counterparties[addr]["out"] += doc["count"]
        counterparties[addr]["tokens"].update(doc["tokens"])
        total_out += doc["count"]
        all_tokens.update(doc["tokens"])

    for doc in db["onchain_v2_erc20_logs"].aggregate(in_pipe):
        addr = doc["_id"].lower()
        counterparties[addr] = counterparties.get(addr, {"out": 0, "in": 0, "tokens": set()})
        counterparties[addr]["in"] += doc["count"]
        counterparties[addr]["tokens"].update(doc["tokens"])
        total_in += doc["count"]
        all_tokens.update(doc["tokens"])

    total = total_out + total_in
    if total > 0:
        ratio = total_in / total
        if ratio >= 0.65:
            direction = "inflow_dominant"
        elif ratio <= 0.35:
            direction = "outflow_dominant"
        else:
            direction = "balanced"
    else:
        direction = "none"

    return {
        "counterparties": counterparties,
        "tokens": all_tokens,
        "total_transfers": total,
        "total_in": total_in,
        "total_out": total_out,
        "direction": direction,
    }


# ══════════════════════════════════════════════════════════
#  ATTRIBUTION SCORING
# ══════════════════════════════════════════════════════════

def _score_counterparty_overlap(
    cluster_activity: dict, entity_addr_map: dict, target_slug: str
) -> tuple[float, list[str]]:
    """Score counterparty overlap with known entities."""
    reasons = []
    counterparties = cluster_activity["counterparties"]

    if not counterparties:
        return 0.0, []

    # Check how many cluster counterparties are known entity addresses
    entity_interactions: dict = {}
    for addr, info in counterparties.items():
        entity_slug = entity_addr_map.get(addr)
        if entity_slug:
            total = info["out"] + info["in"]
            entity_interactions[entity_slug] = entity_interactions.get(entity_slug, 0) + total

    if not entity_interactions:
        return 0.0, []

    # Score: how much does the cluster interact with the target entity
    total_entity_txs = sum(entity_interactions.values())
    target_txs = entity_interactions.get(target_slug, 0)

    # Direct interaction with target entity
    if target_txs > 0:
        direct_score = min(1.0, target_txs / max(total_entity_txs, 1))
        reasons.append(f"direct interaction with {target_slug}")
    else:
        direct_score = 0.0

    # Interaction with related entities (same category)
    related_count = len(entity_interactions)
    diversity_score = min(1.0, related_count / 5)

    if related_count >= 2:
        top_entities = sorted(entity_interactions.items(), key=lambda x: x[1], reverse=True)[:3]
        reasons.append(f"interacts with {', '.join(e[0] for e in top_entities)}")

    score = direct_score * 0.6 + diversity_score * 0.4
    return round(score, 4), reasons


def _score_behaviour_match(
    cluster_activity: dict, entity_profiles: dict, target_slug: str
) -> tuple[float, list[str]]:
    """Score behaviour similarity between cluster and target entity."""
    reasons = []

    target_beh = entity_profiles.get(target_slug, {}).get("behaviour", {})
    if not target_beh:
        return 0.0, []

    target_type = target_beh.get("behaviour_type", "mixed")
    target_direction = target_beh.get("signals", {}).get("flow", {}).get("direction", "none")

    # Cluster direction
    cluster_dir = cluster_activity["direction"]

    # Direction match
    if cluster_dir == target_direction and cluster_dir != "none":
        dir_score = 1.0
        reasons.append(f"matching direction: {cluster_dir}")
    elif cluster_dir == "balanced" or target_direction == "balanced":
        dir_score = 0.4
    else:
        dir_score = 0.0

    # Infer cluster behaviour from direction
    cluster_beh = "mixed"
    if cluster_dir == "inflow_dominant":
        cluster_beh = "accumulation"
    elif cluster_dir == "outflow_dominant":
        cluster_beh = "distribution"
    elif cluster_dir == "balanced":
        cluster_beh = "liquidity_provision"

    if cluster_beh == target_type:
        type_score = 1.0
        reasons.append(f"behaviour match: {target_type}")
    elif (cluster_beh, target_type) in [
        ("accumulation", "treasury"),
        ("liquidity_provision", "market_making"),
    ]:
        type_score = 0.5
        reasons.append(f"related behaviour: {cluster_beh}/{target_type}")
    else:
        type_score = 0.0

    score = type_score * 0.6 + dir_score * 0.4
    return round(score, 4), reasons


def _score_token_activity(
    cluster_activity: dict, entity_profiles: dict, target_slug: str
) -> tuple[float, list[str]]:
    """Score token activity similarity between cluster and target entity."""
    reasons = []

    target_matrix = entity_profiles.get(target_slug, {}).get("matrix", {})
    if not target_matrix:
        return 0.0, []

    # Entity tokens
    entity_tokens = set()
    for t in target_matrix.get("tokens", []):
        if t.get("flow_volume_usd", 0) > 0:
            entity_tokens.add(t["token_address"].lower())

    cluster_tokens = set(t.lower() for t in cluster_activity.get("tokens", set()))

    if not entity_tokens or not cluster_tokens:
        return 0.0, []

    # Jaccard overlap
    shared = entity_tokens & cluster_tokens
    union = entity_tokens | cluster_tokens
    jaccard = len(shared) / len(union) if union else 0

    if shared:
        reasons.append(f"shared tokens: {len(shared)}")

    # Stablecoin presence check
    stablecoins = {
        "0xdac17f958d2ee523a2206206994597c13d831ec7",
        "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
        "0x6b175474e89094c44da98b954eedeac495271d0f",
    }
    cluster_has_stable = bool(cluster_tokens & stablecoins)
    entity_stable_dep = target_matrix.get("stablecoin_dependency", 0)

    stable_match = 0.0
    if cluster_has_stable and entity_stable_dep >= 0.5:
        stable_match = 0.8
        reasons.append("stablecoin activity match")
    elif not cluster_has_stable and entity_stable_dep < 0.3:
        stable_match = 0.5

    score = jaccard * 0.6 + stable_match * 0.4
    return round(score, 4), reasons


def _score_flow_pattern(
    cluster_activity: dict, entity_profiles: dict, target_slug: str
) -> tuple[float, list[str]]:
    """Score flow pattern similarity."""
    reasons = []

    target_flows = entity_profiles.get(target_slug, {}).get("flows", {})
    if not target_flows:
        return 0.0, []

    target_all = target_flows.get("all_time", {})
    t_in = target_all.get("inflow_usd", 0)
    t_out = target_all.get("outflow_usd", 0)
    t_total = t_in + t_out

    c_in = cluster_activity.get("total_in", 0)
    c_out = cluster_activity.get("total_out", 0)
    c_total = c_in + c_out

    if t_total <= 0 or c_total <= 0:
        return 0.0, []

    # Inflow ratio proximity
    t_ratio = t_in / t_total
    c_ratio = c_in / c_total
    ratio_sim = 1.0 - abs(t_ratio - c_ratio)

    if ratio_sim >= 0.8:
        reasons.append("flow ratio match")

    # Volume scale proximity (within 2 orders of magnitude)
    import math
    if c_total > 0 and t_total > 0:
        log_diff = abs(math.log10(max(c_total, 1)) - math.log10(max(t_total, 1)))
        scale_sim = max(0, 1.0 - log_diff / 3)
    else:
        scale_sim = 0.0

    score = ratio_sim * 0.7 + scale_sim * 0.3
    return round(score, 4), reasons


def _classify_attribution(score: float) -> str:
    """Classify attribution level from score."""
    if score >= 0.80:
        return "known"
    if score >= 0.50:
        return "likely"
    if score >= 0.30:
        return "possible"
    return "unknown"


# ══════════════════════════════════════════════════════════
#  ATTRIBUTION BUILDER
# ══════════════════════════════════════════════════════════

def build_cluster_attribution(entity_slug: str, cluster_id: str) -> dict | None:
    """Build attribution hypothesis for a specific cluster."""
    db = _get_db()

    # Find the cluster
    cluster_doc = db["entity_clusters_v2"].find_one(
        {"entity_slug": entity_slug}, {"_id": 0}
    )
    if not cluster_doc:
        return None

    target_cluster = None
    for cl in cluster_doc.get("clusters", []):
        if cl["cluster_id"] == cluster_id:
            target_cluster = cl
            break

    if not target_cluster:
        return None

    # Load profiles and address map
    profiles, addr_map = _load_entity_profiles(db)

    # Analyze cluster activity
    activity = _analyze_cluster_activity(db, target_cluster["members"])

    # Score against all known entities
    candidates = []
    for slug in profiles:
        cp_score, cp_reasons = _score_counterparty_overlap(activity, addr_map, slug)
        beh_score, beh_reasons = _score_behaviour_match(activity, profiles, slug)
        tok_score, tok_reasons = _score_token_activity(activity, profiles, slug)
        flow_score, flow_reasons = _score_flow_pattern(activity, profiles, slug)

        composite = round(
            cp_score * 0.35 + beh_score * 0.25 + tok_score * 0.25 + flow_score * 0.15,
            4,
        )

        all_reasons = cp_reasons + beh_reasons + tok_reasons + flow_reasons

        candidates.append({
            "entity_slug": slug,
            "entity_name": profiles[slug].get("behaviour", {}).get("entity", {}).get("name", slug),
            "attribution_score": composite,
            "attribution_level": _classify_attribution(composite),
            "signals": all_reasons[:5] if all_reasons else ["no matching signals"],
            "components": {
                "counterparty": cp_score,
                "behaviour": beh_score,
                "token_activity": tok_score,
                "flow_pattern": flow_score,
            },
        })

    candidates.sort(key=lambda x: x["attribution_score"], reverse=True)

    # Best candidate
    best = candidates[0] if candidates else None

    result = {
        "cluster_id": cluster_id,
        "parent_entity": entity_slug,
        "cluster_tier": target_cluster["tier"],
        "cluster_size": target_cluster["size"],
        "cluster_confidence": target_cluster["confidence"],
        "attribution": {
            "possible_entity": best["entity_slug"] if best else None,
            "entity_name": best["entity_name"] if best else None,
            "confidence": best["attribution_score"] if best else 0,
            "level": best["attribution_level"] if best else "unknown",
            "signals": best["signals"] if best else [],
        },
        "top_candidates": candidates[:5],
        "cluster_activity": {
            "total_transfers": activity["total_transfers"],
            "direction": activity["direction"],
            "unique_tokens": len(activity["tokens"]),
            "unique_counterparties": len(activity["counterparties"]),
        },
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }

    return result


def build_all_attributions() -> dict:
    """Build attributions for all clusters across all entities."""
    db = _get_db()
    all_cluster_docs = list(db["entity_clusters_v2"].find({}, {"_id": 0}))

    profiles, addr_map = _load_entity_profiles(db)

    stats = {
        "total_clusters": 0,
        "attributed": 0,
        "by_level": {},
        "errors": 0,
    }

    all_results = []

    for doc in all_cluster_docs:
        entity_slug = doc.get("entity_slug", "")
        for cl in doc.get("clusters", []):
            stats["total_clusters"] += 1
            cluster_id = cl["cluster_id"]

            try:
                activity = _analyze_cluster_activity(db, cl["members"][:30])

                # Score against all entities
                best_score = 0
                best_slug = None
                best_reasons = []
                best_components = {}

                for slug in profiles:
                    cp_s, cp_r = _score_counterparty_overlap(activity, addr_map, slug)
                    beh_s, beh_r = _score_behaviour_match(activity, profiles, slug)
                    tok_s, tok_r = _score_token_activity(activity, profiles, slug)
                    flow_s, flow_r = _score_flow_pattern(activity, profiles, slug)

                    composite = round(cp_s * 0.35 + beh_s * 0.25 + tok_s * 0.25 + flow_s * 0.15, 4)

                    if composite > best_score:
                        best_score = composite
                        best_slug = slug
                        best_reasons = (cp_r + beh_r + tok_r + flow_r)[:5]
                        best_components = {
                            "counterparty": cp_s,
                            "behaviour": beh_s,
                            "token_activity": tok_s,
                            "flow_pattern": flow_s,
                        }

                level = _classify_attribution(best_score)
                stats["by_level"][level] = stats["by_level"].get(level, 0) + 1
                if level != "unknown":
                    stats["attributed"] += 1

                attribution = {
                    "cluster_id": cluster_id,
                    "parent_entity": entity_slug,
                    "tier": cl["tier"],
                    "size": cl["size"],
                    "possible_entity": best_slug,
                    "attribution_score": best_score,
                    "attribution_level": level,
                    "signals": best_reasons if best_reasons else ["no matching signals"],
                    "components": best_components,
                    "cluster_activity": {
                        "total_transfers": activity["total_transfers"],
                        "direction": activity["direction"],
                        "unique_tokens": len(activity["tokens"]),
                    },
                }

                all_results.append(attribution)

                # Persist individual attribution
                db["entity_attributions_v2"].update_one(
                    {"cluster_id": cluster_id},
                    {"$set": {**attribution, "computed_at": datetime.now(timezone.utc).isoformat()}},
                    upsert=True,
                )

            except Exception as e:
                stats["errors"] += 1
                print(f"[Attribution] Error for {cluster_id}: {e}")

    # Create index
    db["entity_attributions_v2"].create_index(
        [("cluster_id", ASCENDING)], unique=True, background=True
    )

    stats["built_at"] = datetime.now(timezone.utc).isoformat()
    _cache.clear()
    return stats


# ══════════════════════════════════════════════════════════
#  QUERY FUNCTIONS
# ══════════════════════════════════════════════════════════

def get_cluster_attribution(cluster_id: str) -> dict | None:
    """Get attribution for a specific cluster."""
    ck = f"attr:{cluster_id}"
    cached = _cache_get(ck)
    if cached:
        return cached

    db = _get_db()
    stored = db["entity_attributions_v2"].find_one({"cluster_id": cluster_id}, {"_id": 0})
    if stored:
        _cache_set(ck, stored)
        return stored

    # Try to compute on-the-fly by finding the cluster
    parts = cluster_id.rsplit("_cluster_", 1)
    if len(parts) == 2:
        entity_slug = parts[0]
        result = build_cluster_attribution(entity_slug, cluster_id)
        if result:
            _cache_set(ck, result)
            return result

    return None


def get_entity_candidates() -> dict:
    """Get entity candidates — clusters with attribution hypotheses."""
    db = _get_db()
    all_attr = list(db["entity_attributions_v2"].find({}, {"_id": 0}))

    if not all_attr:
        return {"total_clusters": 0, "attributed": 0, "candidates": []}

    candidates = []
    by_level = {}

    for a in all_attr:
        level = a.get("attribution_level", "unknown")
        by_level[level] = by_level.get(level, 0) + 1

        candidates.append({
            "cluster_id": a["cluster_id"],
            "parent_entity": a.get("parent_entity", "?"),
            "tier": a.get("tier", "?"),
            "size": a.get("size", 0),
            "possible_entity": a.get("possible_entity"),
            "attribution_score": a.get("attribution_score", 0),
            "attribution_level": level,
            "signals": a.get("signals", []),
        })

    candidates.sort(key=lambda x: x["attribution_score"], reverse=True)

    return {
        "total_clusters": len(candidates),
        "attributed": sum(1 for c in candidates if c["attribution_level"] != "unknown"),
        "by_level": by_level,
        "candidates": candidates,
    }


def get_entity_cluster_attributions(slug: str) -> dict | None:
    """Get all cluster attributions for a specific entity."""
    db = _get_db()
    entity = db["entities_v2"].find_one({"slug": slug}, {"_id": 0})
    if not entity:
        return None

    attributions = list(db["entity_attributions_v2"].find(
        {"parent_entity": slug}, {"_id": 0}
    ))

    return {
        "entity": {
            "slug": entity["slug"],
            "name": entity["name"],
            "type": entity["type"],
            "category": entity["category"],
        },
        "total_clusters": len(attributions),
        "attributions": sorted(
            attributions, key=lambda x: x.get("attribution_score", 0), reverse=True
        ),
    }
