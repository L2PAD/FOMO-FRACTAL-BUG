"""
Entities V2 — Foundation Service
==================================
Clean entity registry with proper types, attribution, and real addresses.
Replaces the legacy TS entities module.

Collections:
  entities_v2        — Entity registry
  entity_addresses_v2 — Address attribution
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


# ── Cache ──
_cache: dict = {}
_CACHE_TTL = 120


def _cache_get(k: str):
    e = _cache.get(k)
    return e["data"] if e and time.time() - e["ts"] < _CACHE_TTL else None


def _cache_set(k: str, data):
    _cache[k] = {"data": data, "ts": time.time()}


# ── Valid types/categories ──
ENTITY_TYPES = ["exchange", "fund", "market_maker", "protocol", "whale", "dao", "bridge", "unknown_cluster"]
ENTITY_CATEGORIES = ["CEX", "DEX", "VC", "MM", "Institution", "DeFi", "Foundation", "Treasury", "Bridge", "Unknown"]
ATTRIBUTION_SOURCES = ["verified", "tagged", "public", "heuristic", "clustered", "inferred"]


# ══════════════════════════════════════════════════════════
#  SEED
# ══════════════════════════════════════════════════════════

def seed_entities() -> dict:
    """Seed entity registry with real addresses. Idempotent."""
    from .seed import ENTITY_SEED

    db = _get_db()
    ent_col = db["entities_v2"]
    addr_col = db["entity_addresses_v2"]

    # Ensure indexes
    ent_col.create_index([("slug", ASCENDING)], unique=True, background=True)
    addr_col.create_index([("address", ASCENDING), ("chain", ASCENDING)], background=True)
    addr_col.create_index([("entity_slug", ASCENDING)], background=True)

    seeded = 0
    addresses_total = 0
    now = datetime.now(timezone.utc)

    for entry in ENTITY_SEED:
        slug = entry["slug"]

        # Upsert entity
        ent_doc = {
            "name": entry["name"],
            "slug": slug,
            "type": entry["type"],
            "category": entry["category"],
            "confidence": entry["confidence"],
            "description": entry["description"],
            "tags": entry.get("tags", []),
            "addresses_count": len(entry.get("addresses", [])),
            "status": "active",
            "updated_at": now.isoformat(),
        }
        result = ent_col.update_one(
            {"slug": slug},
            {"$set": ent_doc, "$setOnInsert": {"created_at": now.isoformat()}},
            upsert=True,
        )
        if result.upserted_id:
            seeded += 1

        # Upsert addresses
        for addr in entry.get("addresses", []):
            addr_doc = {
                "entity_slug": slug,
                "entity_name": entry["name"],
                "entity_type": entry["type"],
                "address": addr["address"].lower(),
                "chain": addr.get("chain", "ethereum"),
                "role": addr.get("role", "unknown"),
                "confidence": addr.get("confidence", 50),
                "source": addr.get("source", "unknown"),
                "updated_at": now.isoformat(),
            }
            addr_col.update_one(
                {"address": addr["address"].lower(), "chain": addr.get("chain", "ethereum")},
                {"$set": addr_doc, "$setOnInsert": {"first_seen": now.isoformat()}},
                upsert=True,
            )
            addresses_total += 1

    _cache.clear()

    return {
        "seeded": seeded,
        "updated": len(ENTITY_SEED) - seeded,
        "total_entities": len(ENTITY_SEED),
        "total_addresses": addresses_total,
    }


# ══════════════════════════════════════════════════════════
#  REGISTRY
# ══════════════════════════════════════════════════════════

def list_entities(
    entity_type: str | None = None,
    category: str | None = None,
    search: str | None = None,
    page: int = 1,
    limit: int = 50,
) -> dict:
    """List entities with filtering, search, and pagination."""
    ck = f"ent_list:{entity_type}:{category}:{search}:{page}:{limit}"
    cached = _cache_get(ck)
    if cached:
        return cached

    db = _get_db()
    ent_col = db["entities_v2"]
    addr_col = db["entity_addresses_v2"]

    query: dict = {"status": "active"}
    if entity_type:
        query["type"] = entity_type
    if category:
        query["category"] = category
    if search:
        query["name"] = {"$regex": search, "$options": "i"}

    total = ent_col.count_documents(query)
    skip = (page - 1) * limit
    cursor = ent_col.find(query, {"_id": 0}).sort("confidence", -1).skip(skip).limit(limit)
    entities = list(cursor)

    # Enrich with address count from address collection
    for ent in entities:
        actual_count = addr_col.count_documents({"entity_slug": ent["slug"]})
        ent["addresses_count"] = actual_count
        # Get primary addresses
        addrs = list(addr_col.find(
            {"entity_slug": ent["slug"]},
            {"_id": 0, "address": 1, "role": 1, "confidence": 1, "source": 1},
        ).sort("confidence", -1).limit(3))
        ent["primary_addresses"] = addrs

    result = {
        "entities": entities,
        "pagination": {
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": max(1, (total + limit - 1) // limit),
        },
    }
    _cache_set(ck, result)
    return result


def get_entity(slug: str) -> dict | None:
    """Get single entity by slug with all addresses."""
    ck = f"ent_detail:{slug}"
    cached = _cache_get(ck)
    if cached:
        return cached

    db = _get_db()
    ent = db["entities_v2"].find_one({"slug": slug}, {"_id": 0})
    if not ent:
        return None

    # All attributed addresses
    addresses = list(db["entity_addresses_v2"].find(
        {"entity_slug": slug},
        {"_id": 0},
    ).sort("confidence", -1))
    ent["addresses"] = addresses
    ent["addresses_count"] = len(addresses)

    # Address confidence breakdown
    sources = {}
    for a in addresses:
        src = a.get("source", "unknown")
        sources[src] = sources.get(src, 0) + 1
    ent["attribution_summary"] = {
        "total_addresses": len(addresses),
        "sources": sources,
        "avg_confidence": round(sum(a.get("confidence", 0) for a in addresses) / max(len(addresses), 1)),
        "chains": list(set(a.get("chain", "ethereum") for a in addresses)),
    }

    _cache_set(ck, ent)
    return ent


def search_entities(query: str, limit: int = 10) -> list:
    """Quick search across entities."""
    db = _get_db()
    cursor = db["entities_v2"].find(
        {"name": {"$regex": query, "$options": "i"}, "status": "active"},
        {"_id": 0, "name": 1, "slug": 1, "type": 1, "category": 1, "confidence": 1},
    ).limit(limit)
    return list(cursor)


def resolve_address(address: str, chain: str = "ethereum") -> dict | None:
    """Resolve an address to its entity."""
    db = _get_db()
    addr = db["entity_addresses_v2"].find_one(
        {"address": address.lower(), "chain": chain},
        {"_id": 0},
    )
    if not addr:
        return None
    return addr


def get_entity_types_summary() -> dict:
    """Summary of entity counts by type and category."""
    db = _get_db()
    pipeline = [
        {"$match": {"status": "active"}},
        {"$group": {"_id": {"type": "$type", "category": "$category"}, "count": {"$sum": 1}}},
    ]
    results = list(db["entities_v2"].aggregate(pipeline))
    by_type = {}
    by_category = {}
    for r in results:
        t = r["_id"]["type"]
        c = r["_id"]["category"]
        by_type[t] = by_type.get(t, 0) + r["count"]
        by_category[c] = by_category.get(c, 0) + r["count"]
    total = db["entities_v2"].count_documents({"status": "active"})
    total_addrs = db["entity_addresses_v2"].count_documents({})
    return {
        "total_entities": total,
        "total_addresses": total_addrs,
        "by_type": by_type,
        "by_category": by_category,
    }
