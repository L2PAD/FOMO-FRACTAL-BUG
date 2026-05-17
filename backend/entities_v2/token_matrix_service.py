"""
Entities V2 — Phase 5: Token Flow Matrix
==========================================
Structural analysis of token activity per entity.
Classifies each token's role (accumulation, distribution,
liquidity, neutral) and builds a matrix of token activity.

Builds on Phase 4 flow data (entity_flows_v2) and enriches
with role classification, dominance analysis, and dependency metrics.
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


STABLECOIN_ADDRESSES = {
    "0xdac17f958d2ee523a2206206994597c13d831ec7",  # USDT
    "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",  # USDC
    "0x6b175474e89094c44da98b954eedeac495271d0f",  # DAI
    "0x4fabb145d64652a948d72533023f6e7a623c7c53",  # BUSD
    "0x8e870d67f660d95d5be530380d0ec0bd388289e1",  # USDP
    "0x4c9edd5852cd905f086c759e8383e09bff1e68b3",  # USDe
}

MAJOR_ADDRESSES = {
    "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",  # WETH
    "0x2260fac5e5542a773aa44fbcfedf7c193bc2c599",  # WBTC
}


def _classify_token_role(inflow: float, outflow: float, volume_share: float) -> str:
    """
    Classify token role based on flow patterns.

    liquidity_token:    high share, balanced flow (bi-directional)
    accumulation_token: net inflow dominant (entity is buying/receiving)
    distribution_token: net outflow dominant (entity is selling/sending)
    neutral_token:      minimal volume or no priced flow
    """
    total = inflow + outflow
    if total <= 0:
        return "neutral_token"

    inflow_ratio = inflow / total

    # High-share tokens with balanced flow = liquidity
    if volume_share >= 0.15 and 0.35 <= inflow_ratio <= 0.65:
        return "liquidity_token"

    # Strong inflow bias = accumulation
    if inflow_ratio >= 0.70:
        return "accumulation_token"

    # Strong outflow bias = distribution
    if inflow_ratio <= 0.30:
        return "distribution_token"

    # Moderate share, somewhat balanced = liquidity
    if volume_share >= 0.05 and 0.35 <= inflow_ratio <= 0.65:
        return "liquidity_token"

    # Default: if slightly biased but not extreme
    if inflow_ratio > 0.5:
        return "accumulation_token"
    return "distribution_token"


def _compute_activity_score(volume_share: float, transfer_count: int, has_price: bool) -> int:
    """Token activity score 0-100."""
    score = 0
    # Volume share contribution (max 50)
    score += min(50, int(volume_share * 100))
    # Transfer count (max 30)
    score += min(30, transfer_count * 2)
    # Price availability bonus (20)
    if has_price:
        score += 20
    return min(100, score)


# ══════════════════════════════════════════════════════════
#  TOKEN MATRIX BUILDER
# ══════════════════════════════════════════════════════════

def build_entity_token_matrix(slug: str) -> dict | None:
    """Build token flow matrix for a single entity."""
    db = _get_db()
    entity = db["entities_v2"].find_one({"slug": slug}, {"_id": 0})
    if not entity:
        return None

    # Get Phase 4 flow data
    flow_data = db["entity_flows_v2"].find_one({"entity_slug": slug}, {"_id": 0})
    if not flow_data or not flow_data.get("token_flows"):
        return _empty_matrix(entity)

    raw_tokens = flow_data["token_flows"]
    if not raw_tokens:
        return _empty_matrix(entity)

    # Build matrix entries with role classification
    matrix = []
    for t in raw_tokens:
        inflow = t.get("inflow_usd", 0)
        outflow = t.get("outflow_usd", 0)
        vol = t.get("volume_usd", 0)
        share = t.get("volume_share", 0)
        addr = t.get("token_address", "").lower()
        has_price = vol > 0 or inflow > 0 or outflow > 0

        role = _classify_token_role(inflow, outflow, share)

        # Token class
        if addr in STABLECOIN_ADDRESSES:
            token_class = "stablecoin"
        elif addr in MAJOR_ADDRESSES:
            token_class = "major"
        else:
            token_class = "altcoin"

        matrix.append({
            "token_address": addr,
            "symbol": t.get("symbol", addr[:10] + "..."),
            "token_class": token_class,
            "role": role,
            "inflow_usd": round(inflow, 2),
            "outflow_usd": round(outflow, 2),
            "net_flow_usd": round(t.get("net_flow_usd", 0), 2),
            "flow_volume_usd": round(vol, 2),
            "flow_share": round(share, 4),
            "transfer_count": t.get("transfer_count", 0),
            "activity_score": _compute_activity_score(share, t.get("transfer_count", 0), has_price),
        })

    # Sort by flow volume
    matrix.sort(key=lambda x: x["flow_volume_usd"], reverse=True)

    # ── Dominance Analysis ──
    dominant = matrix[0] if matrix else None
    priced_tokens = [m for m in matrix if m["flow_volume_usd"] > 0]
    total_priced_vol = sum(m["flow_volume_usd"] for m in priced_tokens)

    # Top 3 concentration
    top3_share = sum(m["flow_share"] for m in matrix[:3])

    # ── Role breakdown ──
    roles = {}
    for m in matrix:
        r = m["role"]
        if r not in roles:
            roles[r] = {"count": 0, "volume_usd": 0, "tokens": []}
        roles[r]["count"] += 1
        roles[r]["volume_usd"] = round(roles[r]["volume_usd"] + m["flow_volume_usd"], 2)
        if len(roles[r]["tokens"]) < 5:
            roles[r]["tokens"].append(m["symbol"])

    # ── Stablecoin dependency ──
    stable_vol = sum(m["flow_volume_usd"] for m in matrix if m["token_class"] == "stablecoin")
    stablecoin_dependency = round(stable_vol / total_priced_vol, 4) if total_priced_vol > 0 else 0

    # ── Class breakdown ──
    class_breakdown = {}
    for cls in ["stablecoin", "major", "altcoin"]:
        cls_tokens = [m for m in matrix if m["token_class"] == cls]
        cls_vol = sum(m["flow_volume_usd"] for m in cls_tokens)
        class_breakdown[cls] = {
            "count": len(cls_tokens),
            "volume_usd": round(cls_vol, 2),
            "share": round(cls_vol / total_priced_vol, 4) if total_priced_vol > 0 else 0,
        }

    now = datetime.now(timezone.utc)

    result = {
        "entity": {
            "slug": entity["slug"],
            "name": entity["name"],
            "type": entity["type"],
            "category": entity["category"],
        },
        "dominant_asset": {
            "symbol": dominant["symbol"] if dominant else None,
            "flow_share": dominant["flow_share"] if dominant else 0,
            "role": dominant["role"] if dominant else None,
            "volume_usd": dominant["flow_volume_usd"] if dominant else 0,
        },
        "top3_concentration": round(top3_share, 4),
        "stablecoin_dependency": stablecoin_dependency,
        "total_tokens": len(matrix),
        "priced_tokens": len(priced_tokens),
        "total_flow_volume_usd": round(total_priced_vol, 2),
        "role_breakdown": roles,
        "class_breakdown": class_breakdown,
        "tokens": matrix,
        "computed_at": now.isoformat(),
    }

    # Persist
    col = db["entity_token_matrix_v2"]
    col.create_index([("entity_slug", ASCENDING)], unique=True, background=True)
    col.update_one(
        {"entity_slug": slug},
        {"$set": {"entity_slug": slug, **result, "computed_at": now.isoformat()}},
        upsert=True,
    )

    _cache.clear()
    return result


def _empty_matrix(entity: dict) -> dict:
    return {
        "entity": {
            "slug": entity["slug"], "name": entity["name"],
            "type": entity["type"], "category": entity["category"],
        },
        "dominant_asset": {"symbol": None, "flow_share": 0, "role": None, "volume_usd": 0},
        "top3_concentration": 0,
        "stablecoin_dependency": 0,
        "total_tokens": 0,
        "priced_tokens": 0,
        "total_flow_volume_usd": 0,
        "role_breakdown": {},
        "class_breakdown": {},
        "tokens": [],
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }


# ══════════════════════════════════════════════════════════
#  QUERY FUNCTIONS
# ══════════════════════════════════════════════════════════

def get_entity_token_matrix(slug: str) -> dict | None:
    """Get token flow matrix for an entity."""
    ck = f"tmatrix:{slug}"
    cached = _cache_get(ck)
    if cached:
        return cached

    db = _get_db()
    entity = db["entities_v2"].find_one({"slug": slug}, {"_id": 0})
    if not entity:
        return None

    stored = db["entity_token_matrix_v2"].find_one({"entity_slug": slug}, {"_id": 0})
    if stored:
        stored.pop("entity_slug", None)
        _cache_set(ck, stored)
        return stored

    # Compute on-the-fly
    result = build_entity_token_matrix(slug)
    if result:
        _cache_set(ck, result)
    return result


def build_all_token_matrices() -> dict:
    """Build token matrices for all entities."""
    db = _get_db()
    entities = list(db["entities_v2"].find({"status": "active"}, {"_id": 0, "slug": 1}))

    stats = {
        "total_entities": len(entities),
        "computed": 0,
        "with_tokens": 0,
        "errors": 0,
    }

    for ent in entities:
        try:
            result = build_entity_token_matrix(ent["slug"])
            if result:
                stats["computed"] += 1
                if result["total_tokens"] > 0:
                    stats["with_tokens"] += 1
        except Exception as e:
            stats["errors"] += 1
            print(f"[TokenMatrix] Error for {ent['slug']}: {e}")

    stats["built_at"] = datetime.now(timezone.utc).isoformat()
    _cache.clear()
    return stats


def get_token_matrix_overview() -> dict:
    """Cross-entity token analysis — which tokens are most traded."""
    db = _get_db()
    all_matrices = list(db["entity_token_matrix_v2"].find({}, {"_id": 0}))

    # Aggregate token activity across entities
    token_agg: dict = {}
    for mat in all_matrices:
        ent_slug = mat.get("entity_slug", "?")
        for t in mat.get("tokens", []):
            addr = t["token_address"]
            if addr not in token_agg:
                token_agg[addr] = {
                    "symbol": t["symbol"],
                    "token_class": t["token_class"],
                    "total_volume_usd": 0,
                    "total_transfers": 0,
                    "entities": [],
                    "roles": {},
                }
            token_agg[addr]["total_volume_usd"] += t["flow_volume_usd"]
            token_agg[addr]["total_transfers"] += t["transfer_count"]
            if t["flow_volume_usd"] > 0 or t["transfer_count"] > 0:
                token_agg[addr]["entities"].append({
                    "slug": ent_slug,
                    "role": t["role"],
                    "volume_usd": t["flow_volume_usd"],
                })
            role = t["role"]
            token_agg[addr]["roles"][role] = token_agg[addr]["roles"].get(role, 0) + 1

    # Sort by total volume
    token_list = []
    for addr, data in token_agg.items():
        token_list.append({
            "token_address": addr,
            "symbol": data["symbol"],
            "token_class": data["token_class"],
            "total_volume_usd": round(data["total_volume_usd"], 2),
            "total_transfers": data["total_transfers"],
            "entity_count": len(data["entities"]),
            "dominant_role": max(data["roles"], key=data["roles"].get) if data["roles"] else "neutral_token",
            "entities": data["entities"][:5],
        })
    token_list.sort(key=lambda x: x["total_volume_usd"], reverse=True)

    return {
        "total_unique_tokens": len(token_list),
        "tokens_with_volume": sum(1 for t in token_list if t["total_volume_usd"] > 0),
        "total_volume_usd": round(sum(t["total_volume_usd"] for t in token_list), 2),
        "top_tokens": token_list[:20],
    }
