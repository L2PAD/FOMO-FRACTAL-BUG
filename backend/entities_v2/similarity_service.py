"""
Entities V2 — Phase 7: Similarity Engine
==========================================
Finds entities with similar behaviour, correlated flows,
overlapping token activity, and comparable portfolios.

Similarity Pipeline:
  entity_behaviour_v2     → behaviour type match, confidence distance
  entity_token_matrix_v2  → shared tokens, role overlap, flow share
  entity_flows_v2         → direction correlation, velocity, volume
  entity_holdings_v2      → token overlap, stablecoin ratio, concentration

Score weights:
  0.35 behaviour + 0.30 token_matrix + 0.20 flows + 0.15 portfolio

Persisted to: entity_similarity_v2
"""

import os
import time
import math
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


# ══════════════════════════════════════════════════════════
#  DATA LOADERS
# ══════════════════════════════════════════════════════════

def _load_all_entity_data() -> dict:
    """Load all entity data needed for similarity computation."""
    db = _get_db()

    entities = {e["slug"]: e for e in db["entities_v2"].find({"status": "active"}, {"_id": 0})}
    behaviours = {b["entity_slug"]: b for b in db["entity_behaviour_v2"].find({}, {"_id": 0})}
    matrices = {m["entity_slug"]: m for m in db["entity_token_matrix_v2"].find({}, {"_id": 0})}
    flows = {f["entity_slug"]: f for f in db["entity_flows_v2"].find({}, {"_id": 0})}
    holdings = {h["entity_slug"]: h for h in db["entity_holdings_v2"].find({}, {"_id": 0})}

    return {
        "entities": entities,
        "behaviours": behaviours,
        "matrices": matrices,
        "flows": flows,
        "holdings": holdings,
    }


# ══════════════════════════════════════════════════════════
#  SIMILARITY COMPONENTS
# ══════════════════════════════════════════════════════════

BEHAVIOUR_TYPES = ["accumulation", "distribution", "market_making", "liquidity_provision", "treasury", "mixed"]


def _behaviour_similarity(b1: dict, b2: dict) -> tuple[float, list[str]]:
    """
    Behaviour similarity (weight: 0.35).
    - Type match: 0.70 of component
    - Confidence proximity: 0.30 of component
    """
    reasons = []

    bt1 = b1.get("behaviour_type", "mixed")
    bt2 = b2.get("behaviour_type", "mixed")
    c1 = b1.get("confidence", 0)
    c2 = b2.get("confidence", 0)

    # Type match score
    if bt1 == bt2:
        type_score = 1.0
        if bt1 != "mixed":
            reasons.append(f"same behaviour: {bt1}")
    else:
        # Partial match for related types
        related = {
            ("accumulation", "treasury"): 0.4,
            ("distribution", "market_making"): 0.3,
            ("market_making", "liquidity_provision"): 0.5,
            ("liquidity_provision", "treasury"): 0.2,
        }
        pair = tuple(sorted([bt1, bt2]))
        type_score = related.get(pair, 0.0)
        if type_score > 0.2:
            reasons.append(f"related behaviour: {bt1}/{bt2}")

    # Confidence proximity (1 - |c1 - c2|)
    conf_score = 1.0 - abs(c1 - c2)

    # Both insufficient data → high similarity but low value
    if c1 == 0 and c2 == 0:
        type_score = 0.5
        conf_score = 1.0
        reasons.append("both insufficient data")

    score = type_score * 0.70 + conf_score * 0.30
    return round(score, 4), reasons


def _token_matrix_similarity(m1: dict, m2: dict) -> tuple[float, list[str]]:
    """
    Token activity overlap (weight: 0.30).
    - Shared token overlap (Jaccard on priced tokens)
    - Flow share cosine similarity
    - Role distribution similarity
    - Stablecoin dependency proximity
    """
    reasons = []

    t1 = {t["token_address"]: t for t in m1.get("tokens", []) if t.get("flow_volume_usd", 0) > 0}
    t2 = {t["token_address"]: t for t in m2.get("tokens", []) if t.get("flow_volume_usd", 0) > 0}

    if not t1 and not t2:
        return 0.5, ["both no token activity"]
    if not t1 or not t2:
        return 0.0, []

    # Jaccard overlap on active tokens
    shared = set(t1.keys()) & set(t2.keys())
    union = set(t1.keys()) | set(t2.keys())
    jaccard = len(shared) / len(union) if union else 0

    if shared:
        shared_symbols = [t1[a]["symbol"] for a in list(shared)[:3]]
        reasons.append(f"shared tokens: {', '.join(shared_symbols)}")

    # Flow share cosine similarity on shared tokens
    cosine = 0.0
    if shared:
        dot = sum(t1[a]["flow_share"] * t2[a]["flow_share"] for a in shared)
        mag1 = math.sqrt(sum(t1[a]["flow_share"] ** 2 for a in t1))
        mag2 = math.sqrt(sum(t2[a]["flow_share"] ** 2 for a in t2))
        cosine = dot / (mag1 * mag2) if mag1 > 0 and mag2 > 0 else 0

    # Role distribution similarity
    roles1 = m1.get("role_breakdown", {})
    roles2 = m2.get("role_breakdown", {})
    vol1 = m1.get("total_flow_volume_usd", 1)
    vol2 = m2.get("total_flow_volume_usd", 1)

    role_vec1 = {}
    role_vec2 = {}
    for r in set(list(roles1.keys()) + list(roles2.keys())):
        role_vec1[r] = roles1.get(r, {}).get("volume_usd", 0) / vol1 if vol1 > 0 else 0
        role_vec2[r] = roles2.get(r, {}).get("volume_usd", 0) / vol2 if vol2 > 0 else 0

    role_sim = 0.0
    if role_vec1 and role_vec2:
        all_roles = set(list(role_vec1.keys()) + list(role_vec2.keys()))
        dot_r = sum(role_vec1.get(r, 0) * role_vec2.get(r, 0) for r in all_roles)
        mag_r1 = math.sqrt(sum(v ** 2 for v in role_vec1.values()))
        mag_r2 = math.sqrt(sum(v ** 2 for v in role_vec2.values()))
        role_sim = dot_r / (mag_r1 * mag_r2) if mag_r1 > 0 and mag_r2 > 0 else 0

    # Stablecoin dependency proximity
    sd1 = m1.get("stablecoin_dependency", 0)
    sd2 = m2.get("stablecoin_dependency", 0)
    stable_sim = 1.0 - abs(sd1 - sd2)

    if sd1 >= 0.8 and sd2 >= 0.8:
        reasons.append("stablecoin dominance")

    score = jaccard * 0.25 + cosine * 0.25 + role_sim * 0.30 + stable_sim * 0.20
    return round(score, 4), reasons


def _flow_similarity(f1: dict, f2: dict) -> tuple[float, list[str]]:
    """
    Flow correlation (weight: 0.20).
    - Direction match
    - Velocity proximity (log-scale)
    - Volume ratio similarity
    """
    reasons = []

    at1 = f1.get("all_time", {})
    at2 = f2.get("all_time", {})

    in1 = at1.get("inflow_usd", 0)
    out1 = at1.get("outflow_usd", 0)
    in2 = at2.get("inflow_usd", 0)
    out2 = at2.get("outflow_usd", 0)
    vol1 = in1 + out1
    vol2 = in2 + out2

    if vol1 <= 0 and vol2 <= 0:
        return 0.5, ["both no flow data"]
    if vol1 <= 0 or vol2 <= 0:
        return 0.0, []

    # Direction match
    dir1 = f1.get("direction", "balanced")
    dir2 = f2.get("direction", "balanced")

    if dir1 == dir2:
        dir_score = 1.0
        if dir1 != "balanced":
            reasons.append(f"same direction: {dir1}")
    else:
        dir_pairs = {
            ("balanced", "inflow_dominant"): 0.4,
            ("balanced", "outflow_dominant"): 0.4,
            ("inflow_dominant", "outflow_dominant"): 0.0,
        }
        pair = tuple(sorted([dir1, dir2]))
        dir_score = dir_pairs.get(pair, 0.2)

    # Inflow ratio proximity
    ratio1 = in1 / vol1
    ratio2 = in2 / vol2
    ratio_sim = 1.0 - abs(ratio1 - ratio2)

    # Velocity proximity (log-scale to handle different magnitudes)
    v1 = f1.get("flow_velocity", 0)
    v2 = f2.get("flow_velocity", 0)
    if v1 > 0 and v2 > 0:
        log_diff = abs(math.log10(max(v1, 1)) - math.log10(max(v2, 1)))
        vel_sim = max(0, 1.0 - log_diff / 3)  # 3 orders of magnitude = 0
        if vel_sim >= 0.7:
            reasons.append("similar velocity")
    else:
        vel_sim = 0.0

    score = dir_score * 0.40 + ratio_sim * 0.35 + vel_sim * 0.25
    return round(score, 4), reasons


def _portfolio_similarity(h1: dict, h2: dict) -> tuple[float, list[str]]:
    """
    Portfolio overlap (weight: 0.15).
    - Token overlap (Jaccard on held tokens)
    - Stablecoin ratio similarity
    - Concentration similarity
    """
    reasons = []

    tokens1 = {t.get("token_address", ""): t for t in h1.get("holdings", []) if t.get("value_usd", 0) > 0}
    tokens2 = {t.get("token_address", ""): t for t in h2.get("holdings", []) if t.get("value_usd", 0) > 0}

    if not tokens1 and not tokens2:
        return 0.5, ["both no holdings"]
    if not tokens1 or not tokens2:
        return 0.0, []

    # Token overlap (Jaccard)
    shared = set(tokens1.keys()) & set(tokens2.keys())
    union = set(tokens1.keys()) | set(tokens2.keys())
    jaccard = len(shared) / len(union) if union else 0

    if shared:
        reasons.append(f"shared holdings: {len(shared)} tokens")

    # Stablecoin ratio similarity
    port1 = h1.get("portfolio", {})
    port2 = h2.get("portfolio", {})

    stable1 = port1.get("stablecoin_share", 0)
    stable2 = port2.get("stablecoin_share", 0)
    stable_sim = 1.0 - abs(stable1 - stable2)

    # Concentration similarity
    conc1 = port1.get("concentration_score", 50)
    conc2 = port2.get("concentration_score", 50)
    conc_sim = 1.0 - abs(conc1 - conc2) / 100

    score = jaccard * 0.40 + stable_sim * 0.35 + conc_sim * 0.25
    return round(score, 4), reasons


# ══════════════════════════════════════════════════════════
#  COMPOSITE SIMILARITY
# ══════════════════════════════════════════════════════════

def _compute_pair_similarity(
    slug_a: str, slug_b: str, all_data: dict
) -> dict:
    """Compute composite similarity between two entities."""
    b_a = all_data["behaviours"].get(slug_a, {})
    b_b = all_data["behaviours"].get(slug_b, {})
    m_a = all_data["matrices"].get(slug_a, {})
    m_b = all_data["matrices"].get(slug_b, {})
    f_a = all_data["flows"].get(slug_a, {})
    f_b = all_data["flows"].get(slug_b, {})
    h_a = all_data["holdings"].get(slug_a, {})
    h_b = all_data["holdings"].get(slug_b, {})

    beh_score, beh_reasons = _behaviour_similarity(b_a, b_b)
    tok_score, tok_reasons = _token_matrix_similarity(m_a, m_b)
    flow_score, flow_reasons = _flow_similarity(f_a, f_b)
    port_score, port_reasons = _portfolio_similarity(h_a, h_b)

    composite = round(
        beh_score * 0.35 + tok_score * 0.30 + flow_score * 0.20 + port_score * 0.15,
        4,
    )

    # Merge top reasons
    all_reasons = beh_reasons + tok_reasons + flow_reasons + port_reasons
    top_reasons = all_reasons[:5] if all_reasons else ["low data overlap"]

    return {
        "similarity_score": composite,
        "reasons": top_reasons,
        "components": {
            "behaviour": round(beh_score, 4),
            "token_matrix": round(tok_score, 4),
            "flows": round(flow_score, 4),
            "portfolio": round(port_score, 4),
        },
    }


# ══════════════════════════════════════════════════════════
#  SIMILARITY BUILDER
# ══════════════════════════════════════════════════════════

def build_entity_similarity(slug: str) -> dict | None:
    """Build similarity rankings for a single entity."""
    db = _get_db()
    entity = db["entities_v2"].find_one({"slug": slug}, {"_id": 0})
    if not entity:
        return None

    all_data = _load_all_entity_data()
    slugs = [s for s in all_data["entities"] if s != slug]

    similar = []
    for other_slug in slugs:
        pair = _compute_pair_similarity(slug, other_slug, all_data)
        other_ent = all_data["entities"][other_slug]
        other_beh = all_data["behaviours"].get(other_slug, {})

        similar.append({
            "slug": other_slug,
            "name": other_ent.get("name", other_slug),
            "type": other_ent.get("type", "unknown"),
            "category": other_ent.get("category", "unknown"),
            "behaviour_type": other_beh.get("behaviour_type", "mixed"),
            "similarity_score": pair["similarity_score"],
            "reasons": pair["reasons"],
            "components": pair["components"],
        })

    similar.sort(key=lambda x: x["similarity_score"], reverse=True)

    now = datetime.now(timezone.utc)
    result = {
        "entity": {
            "slug": entity["slug"],
            "name": entity["name"],
            "type": entity["type"],
            "category": entity["category"],
        },
        "top_similar": similar[:10],
        "total_compared": len(similar),
        "computed_at": now.isoformat(),
    }

    # Persist
    col = db["entity_similarity_v2"]
    col.create_index([("entity_slug", ASCENDING)], unique=True, background=True)
    col.update_one(
        {"entity_slug": slug},
        {"$set": {"entity_slug": slug, **result, "computed_at": now.isoformat()}},
        upsert=True,
    )

    _cache.clear()
    return result


def build_all_similarities() -> dict:
    """Build similarity rankings for all entities."""
    db = _get_db()
    entities = list(db["entities_v2"].find({"status": "active"}, {"_id": 0, "slug": 1}))

    stats = {
        "total_entities": len(entities),
        "computed": 0,
        "errors": 0,
    }

    for ent in entities:
        try:
            result = build_entity_similarity(ent["slug"])
            if result:
                stats["computed"] += 1
        except Exception as e:
            stats["errors"] += 1
            print(f"[Similarity] Error for {ent['slug']}: {e}")

    stats["built_at"] = datetime.now(timezone.utc).isoformat()
    _cache.clear()
    return stats


# ══════════════════════════════════════════════════════════
#  QUERY FUNCTIONS
# ══════════════════════════════════════════════════════════

def get_entity_similar(slug: str) -> dict | None:
    """Get similar entities for a given entity."""
    ck = f"similar:{slug}"
    cached = _cache_get(ck)
    if cached:
        return cached

    db = _get_db()
    entity = db["entities_v2"].find_one({"slug": slug}, {"_id": 0})
    if not entity:
        return None

    stored = db["entity_similarity_v2"].find_one({"entity_slug": slug}, {"_id": 0})
    if stored:
        stored.pop("entity_slug", None)
        _cache_set(ck, stored)
        return stored

    # Compute on-the-fly
    result = build_entity_similarity(slug)
    if result:
        _cache_set(ck, result)
    return result


def get_similarity_map() -> dict:
    """Cross-entity similarity map — clusters and groups."""
    db = _get_db()
    all_sim = list(db["entity_similarity_v2"].find({}, {"_id": 0}))

    if not all_sim:
        return {"total_entities": 0, "clusters": [], "pairs": []}

    # Extract strongest pairs (avoid duplicates)
    seen_pairs = set()
    strong_pairs = []

    for sim in all_sim:
        slug_a = sim.get("entity", {}).get("slug", sim.get("entity_slug", "?"))
        for partner in sim.get("top_similar", [])[:5]:
            slug_b = partner["slug"]
            pair_key = tuple(sorted([slug_a, slug_b]))
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)

            if partner["similarity_score"] >= 0.30:
                strong_pairs.append({
                    "entity_a": slug_a,
                    "entity_b": slug_b,
                    "similarity_score": partner["similarity_score"],
                    "reasons": partner["reasons"][:3],
                })

    strong_pairs.sort(key=lambda x: x["similarity_score"], reverse=True)

    # Group by behaviour type
    behaviour_groups: dict = {}
    for sim in all_sim:
        slug = sim.get("entity", {}).get("slug", sim.get("entity_slug", "?"))
        # Look up behaviour
        beh = db["entity_behaviour_v2"].find_one({"entity_slug": slug}, {"_id": 0})
        bt = beh.get("behaviour_type", "mixed") if beh else "mixed"
        if bt not in behaviour_groups:
            behaviour_groups[bt] = []
        behaviour_groups[bt].append({
            "slug": slug,
            "name": sim.get("entity", {}).get("name", slug),
            "type": sim.get("entity", {}).get("type", "unknown"),
        })

    clusters = [
        {
            "behaviour_type": bt,
            "entity_count": len(members),
            "entities": members,
        }
        for bt, members in behaviour_groups.items()
    ]
    clusters.sort(key=lambda x: x["entity_count"], reverse=True)

    return {
        "total_entities": len(all_sim),
        "total_strong_pairs": len(strong_pairs),
        "clusters": clusters,
        "top_pairs": strong_pairs[:20],
    }
