"""
Entities V2 — Phase 2: Address Attribution Engine
====================================================
Scans on-chain data sources, builds materialized activity index
for every address attributed to an entity.

Data sources:
  onchain_v2_erc20_logs          — ERC20 transfers (from/to/value/token)
  onchain_v2_address_labels      — Cross-reference labels
  wallet_counterparty_flow_buckets — Pre-aggregated counterparty flows
  onchain_v2_dex_swaps           — DEX swap activity
  cex_flow_buckets               — CEX flow data

Target collection:
  entity_address_activity_v2     — Materialized activity per address
"""

import os
import time
from datetime import datetime, timezone
from pymongo import MongoClient, ASCENDING, DESCENDING

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
_CACHE_TTL = 300


def _cache_get(k: str):
    e = _cache.get(k)
    return e["data"] if e and time.time() - e["ts"] < _CACHE_TTL else None


def _cache_set(k: str, data):
    _cache[k] = {"data": data, "ts": time.time()}


# ══════════════════════════════════════════════════════════
#  INDEX BUILDER
# ══════════════════════════════════════════════════════════

def build_address_activity_index() -> dict:
    """
    Scan all on-chain sources and build/update activity index
    for every address in entity_addresses_v2.
    Idempotent — safe to call repeatedly.
    """
    db = _get_db()
    addr_col = db["entity_addresses_v2"]
    activity_col = db["entity_address_activity_v2"]
    erc20_col = db["onchain_v2_erc20_logs"]
    labels_col = db["onchain_v2_address_labels"]
    counterparty_col = db["wallet_counterparty_flow_buckets"]
    dex_col = db["onchain_v2_dex_swaps"]

    # Ensure indexes on activity collection
    activity_col.create_index([("address", ASCENDING)], unique=True, background=True)
    activity_col.create_index([("entity_slug", ASCENDING)], background=True)
    activity_col.create_index([("total_tx_count", DESCENDING)], background=True)

    # Get all entity addresses
    all_addresses = list(addr_col.find({}, {"_id": 0}))
    now = datetime.now(timezone.utc)

    stats = {
        "total_addresses": len(all_addresses),
        "with_erc20_activity": 0,
        "with_label_match": 0,
        "with_counterparty_flows": 0,
        "with_dex_activity": 0,
        "indexed": 0,
    }

    for addr_doc in all_addresses:
        address = addr_doc["address"]
        entity_slug = addr_doc["entity_slug"]
        chain = addr_doc.get("chain", "ethereum")
        chain_id = 1 if chain == "ethereum" else 0

        activity = {
            "address": address,
            "entity_slug": entity_slug,
            "entity_name": addr_doc.get("entity_name", ""),
            "entity_type": addr_doc.get("entity_type", ""),
            "chain": chain,
            "role": addr_doc.get("role", "unknown"),
            "attribution_confidence": addr_doc.get("confidence", 0),
            "attribution_source": addr_doc.get("source", "unknown"),
        }

        # ── 1. ERC20 Transfer Activity ──
        # Note: skip $toLong on value field — wei values overflow int64
        erc20_sent = list(erc20_col.aggregate([
            {"$match": {"from": address}},
            {"$group": {
                "_id": None,
                "count": {"$sum": 1},
                "first_block": {"$min": "$blockNumber"},
                "last_block": {"$max": "$blockNumber"},
                "first_ts": {"$min": "$indexedAt"},
                "last_ts": {"$max": "$indexedAt"},
                "unique_tokens": {"$addToSet": "$tokenAddress"},
                "unique_counterparties": {"$addToSet": "$to"},
            }}
        ]))

        erc20_recv = list(erc20_col.aggregate([
            {"$match": {"to": address}},
            {"$group": {
                "_id": None,
                "count": {"$sum": 1},
                "first_block": {"$min": "$blockNumber"},
                "last_block": {"$max": "$blockNumber"},
                "first_ts": {"$min": "$indexedAt"},
                "last_ts": {"$max": "$indexedAt"},
                "unique_tokens": {"$addToSet": "$tokenAddress"},
                "unique_counterparties": {"$addToSet": "$from"},
            }}
        ]))

        sent = erc20_sent[0] if erc20_sent else None
        recv = erc20_recv[0] if erc20_recv else None

        sent_count = sent["count"] if sent else 0
        recv_count = recv["count"] if recv else 0
        total_tx = sent_count + recv_count

        # Combine unique tokens and counterparties
        tokens_sent = set(sent["unique_tokens"]) if sent else set()
        tokens_recv = set(recv["unique_tokens"]) if recv else set()
        cp_sent = set(sent["unique_counterparties"]) if sent else set()
        cp_recv = set(recv["unique_counterparties"]) if recv else set()

        all_tokens = list(tokens_sent | tokens_recv)
        all_counterparties = list(cp_sent | cp_recv)

        # Determine first/last seen
        first_block = min(
            sent.get("first_block", float("inf")) if sent else float("inf"),
            recv.get("first_block", float("inf")) if recv else float("inf"),
        )
        last_block = max(
            sent.get("last_block", 0) if sent else 0,
            recv.get("last_block", 0) if recv else 0,
        )
        first_ts = min(
            sent.get("first_ts", float("inf")) if sent else float("inf"),
            recv.get("first_ts", float("inf")) if recv else float("inf"),
        )
        last_ts = max(
            sent.get("last_ts", 0) if sent else 0,
            recv.get("last_ts", 0) if recv else 0,
        )

        activity["erc20"] = {
            "sent_count": sent_count,
            "recv_count": recv_count,
            "total_tx_count": total_tx,
            "unique_tokens_count": len(all_tokens),
            "unique_counterparties_count": len(all_counterparties),
            "first_block": first_block if first_block != float("inf") else None,
            "last_block": last_block if last_block > 0 else None,
            "first_seen_ts": first_ts if first_ts != float("inf") else None,
            "last_seen_ts": last_ts if last_ts > 0 else None,
            "top_tokens": all_tokens[:20],
            "top_counterparties": all_counterparties[:20],
        }
        activity["total_tx_count"] = total_tx

        if total_tx > 0:
            stats["with_erc20_activity"] += 1

        # ── 2. Address Label Cross-Reference ──
        label = labels_col.find_one({"address": address}, {"_id": 0})
        if label:
            stats["with_label_match"] += 1
            activity["label"] = {
                "name": label.get("name"),
                "type": label.get("type"),
                "subtype": label.get("subtype"),
                "label_confidence": label.get("confidence", 0),
                "label_source": label.get("source"),
                "entity_id": label.get("entityId"),
                "cluster_id": label.get("clusterId"),
                "tags": label.get("tags", []),
            }
        else:
            activity["label"] = None

        # ── 3. Counterparty Flow Data ──
        cp_flows = list(counterparty_col.find(
            {"walletAddress": address},
            {"_id": 0, "counterpartyAddress": 1, "inUsd": 1, "outUsd": 1, "netUsd": 1, "transfers": 1, "bucketDate": 1},
        ).sort("bucketDate", -1).limit(100))

        if cp_flows:
            stats["with_counterparty_flows"] += 1
            total_in = sum(f.get("inUsd", 0) for f in cp_flows)
            total_out = sum(f.get("outUsd", 0) for f in cp_flows)
            total_transfers = sum(f.get("transfers", 0) for f in cp_flows)
            unique_cps = list(set(f.get("counterpartyAddress", "") for f in cp_flows))

            activity["counterparty_flows"] = {
                "total_inflow_usd": round(total_in, 2),
                "total_outflow_usd": round(total_out, 2),
                "net_flow_usd": round(total_in - total_out, 2),
                "total_transfers": total_transfers,
                "unique_counterparties": len(unique_cps),
                "date_range": {
                    "first": cp_flows[-1].get("bucketDate") if cp_flows else None,
                    "last": cp_flows[0].get("bucketDate") if cp_flows else None,
                },
                "top_counterparties": unique_cps[:10],
            }
        else:
            activity["counterparty_flows"] = None

        # ── 4. DEX Activity ──
        dex_as_sender = dex_col.count_documents({"sender": address})
        dex_as_recipient = dex_col.count_documents({"recipient": address})
        dex_total = dex_as_sender + dex_as_recipient

        if dex_total > 0:
            stats["with_dex_activity"] += 1
            # Get protocol breakdown
            dex_protocols = list(dex_col.aggregate([
                {"$match": {"$or": [{"sender": address}, {"recipient": address}]}},
                {"$group": {"_id": "$protocol", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
                {"$limit": 5},
            ]))
            activity["dex"] = {
                "total_swaps": dex_total,
                "as_sender": dex_as_sender,
                "as_recipient": dex_as_recipient,
                "protocols": {p["_id"]: p["count"] for p in dex_protocols if p["_id"]},
            }
        else:
            activity["dex"] = None

        # ── 5. Compute Activity Score ──
        score = _compute_activity_score(activity)
        activity["activity_score"] = score

        # ── 6. Determine Activity Status ──
        activity["status"] = _determine_status(activity)

        # ── Timestamps ──
        activity["indexed_at"] = now.isoformat()

        # Upsert into activity collection
        activity_col.update_one(
            {"address": address},
            {"$set": activity, "$setOnInsert": {"created_at": now.isoformat()}},
            upsert=True,
        )
        stats["indexed"] += 1

    # Clear caches
    _cache.clear()

    stats["built_at"] = now.isoformat()
    return stats


def _compute_activity_score(activity: dict) -> int:
    """
    Compute 0-100 activity score based on multiple signals.
    Higher = more active/verified address.
    """
    score = 0

    # ERC20 activity (max 40 points)
    erc20 = activity.get("erc20", {})
    tx_count = erc20.get("total_tx_count", 0)
    if tx_count > 0:
        score += min(15, tx_count)  # 1pt per tx, max 15
        score += min(10, erc20.get("unique_tokens_count", 0) * 2)  # 2pt per token
        score += min(10, erc20.get("unique_counterparties_count", 0))  # 1pt per cp
        if erc20.get("last_seen_ts"):
            score += 5  # Recently active bonus

    # Label match (max 20 points)
    label = activity.get("label")
    if label:
        score += 10
        label_conf = label.get("label_confidence", 0)
        if isinstance(label_conf, (int, float)):
            score += min(10, int(label_conf * 10))

    # Counterparty flows (max 20 points)
    cp = activity.get("counterparty_flows")
    if cp:
        score += 5
        vol = cp.get("total_inflow_usd", 0) + cp.get("total_outflow_usd", 0)
        if vol > 100_000:
            score += 5
        if vol > 1_000_000:
            score += 5
        score += min(5, cp.get("unique_counterparties", 0))

    # DEX activity (max 10 points)
    dex = activity.get("dex")
    if dex:
        score += min(10, dex.get("total_swaps", 0))

    # Attribution confidence bonus (max 10 points)
    attr_conf = activity.get("attribution_confidence", 0)
    score += min(10, attr_conf // 10)

    return min(100, score)


def _determine_status(activity: dict) -> str:
    """Determine address activity status."""
    erc20 = activity.get("erc20", {})
    tx_count = erc20.get("total_tx_count", 0)

    if tx_count == 0 and not activity.get("counterparty_flows") and not activity.get("dex"):
        return "dormant"

    last_ts = erc20.get("last_seen_ts")
    if last_ts:
        # If last activity within ~30 days (rough estimate from indexedAt ms)
        age_ms = time.time() * 1000 - last_ts
        if age_ms < 30 * 86400 * 1000:
            return "active"
        return "stale"

    if activity.get("counterparty_flows") or activity.get("dex"):
        return "active"

    return "unknown"


# ══════════════════════════════════════════════════════════
#  QUERY FUNCTIONS
# ══════════════════════════════════════════════════════════

def get_entity_addresses_with_activity(slug: str) -> dict | None:
    """
    Get all addresses for an entity, enriched with activity metrics.
    Returns entity info + addresses array with activity data.
    """
    ck = f"addr_activity:{slug}"
    cached = _cache_get(ck)
    if cached:
        return cached

    db = _get_db()

    # Get entity
    entity = db["entities_v2"].find_one({"slug": slug}, {"_id": 0})
    if not entity:
        return None

    # Get activity records for all entity addresses
    activities = list(db["entity_address_activity_v2"].find(
        {"entity_slug": slug},
        {"_id": 0},
    ).sort("activity_score", -1))

    # If no activity records, fall back to raw addresses
    if not activities:
        raw_addrs = list(db["entity_addresses_v2"].find(
            {"entity_slug": slug},
            {"_id": 0},
        ))
        activities = [{
            "address": a["address"],
            "entity_slug": slug,
            "chain": a.get("chain", "ethereum"),
            "role": a.get("role", "unknown"),
            "attribution_confidence": a.get("confidence", 0),
            "attribution_source": a.get("source", "unknown"),
            "activity_score": 0,
            "status": "not_indexed",
            "erc20": None,
            "label": None,
            "counterparty_flows": None,
            "dex": None,
        } for a in raw_addrs]

    # Compute entity-level aggregates
    total_tx = sum(a.get("total_tx_count", 0) for a in activities)
    active_count = sum(1 for a in activities if a.get("status") == "active")
    dormant_count = sum(1 for a in activities if a.get("status") == "dormant")
    avg_score = round(
        sum(a.get("activity_score", 0) for a in activities) / max(len(activities), 1)
    )

    # Total USD flows
    total_inflow = sum(
        (a.get("counterparty_flows") or {}).get("total_inflow_usd", 0)
        for a in activities
    )
    total_outflow = sum(
        (a.get("counterparty_flows") or {}).get("total_outflow_usd", 0)
        for a in activities
    )

    result = {
        "entity": {
            "slug": entity["slug"],
            "name": entity["name"],
            "type": entity["type"],
            "category": entity["category"],
        },
        "summary": {
            "total_addresses": len(activities),
            "active_addresses": active_count,
            "dormant_addresses": dormant_count,
            "total_tx_count": total_tx,
            "avg_activity_score": avg_score,
            "total_inflow_usd": round(total_inflow, 2),
            "total_outflow_usd": round(total_outflow, 2),
            "net_flow_usd": round(total_inflow - total_outflow, 2),
        },
        "addresses": activities,
    }

    _cache_set(ck, result)
    return result


def get_entity_address_activity_detail(slug: str) -> dict | None:
    """
    Detailed activity breakdown for an entity.
    Aggregates across all addresses to produce entity-level intelligence.
    """
    ck = f"addr_detail:{slug}"
    cached = _cache_get(ck)
    if cached:
        return cached

    db = _get_db()

    entity = db["entities_v2"].find_one({"slug": slug}, {"_id": 0})
    if not entity:
        return None

    activities = list(db["entity_address_activity_v2"].find(
        {"entity_slug": slug},
        {"_id": 0},
    ))

    if not activities:
        return {
            "entity": {
                "slug": entity["slug"],
                "name": entity["name"],
                "type": entity["type"],
            },
            "indexed": False,
            "message": "No activity data. Run /api/entities/v2/address-index/build first.",
        }

    # Aggregate token exposure across all addresses
    all_tokens = set()
    for a in activities:
        erc20 = a.get("erc20") or {}
        all_tokens.update(erc20.get("top_tokens", []))

    # Aggregate counterparty exposure
    all_counterparties = set()
    for a in activities:
        cp = a.get("counterparty_flows") or {}
        all_counterparties.update(cp.get("top_counterparties", []))

    # Resolve counterparties to entities where possible
    resolved_counterparties = []
    labels_col = db["onchain_v2_address_labels"]
    for cp_addr in list(all_counterparties)[:20]:
        label = labels_col.find_one({"address": cp_addr}, {"_id": 0, "name": 1, "entityId": 1, "type": 1})
        resolved_counterparties.append({
            "address": cp_addr,
            "entity_id": label.get("entityId") if label else None,
            "name": label.get("name") if label else None,
            "type": label.get("type") if label else None,
        })

    # DEX protocol breakdown
    dex_protocols: dict = {}
    for a in activities:
        dex = a.get("dex") or {}
        for proto, count in (dex.get("protocols") or {}).items():
            dex_protocols[proto] = dex_protocols.get(proto, 0) + count

    # Label coverage
    labeled = sum(1 for a in activities if a.get("label"))

    # Per-address summary (compact)
    address_breakdown = []
    for a in activities:
        address_breakdown.append({
            "address": a["address"],
            "role": a.get("role", "unknown"),
            "activity_score": a.get("activity_score", 0),
            "status": a.get("status", "unknown"),
            "tx_count": a.get("total_tx_count", 0),
            "has_label": a.get("label") is not None,
            "has_flows": a.get("counterparty_flows") is not None,
            "has_dex": a.get("dex") is not None,
        })

    result = {
        "entity": {
            "slug": entity["slug"],
            "name": entity["name"],
            "type": entity["type"],
            "category": entity["category"],
        },
        "indexed": True,
        "coverage": {
            "total_addresses": len(activities),
            "with_erc20_data": sum(1 for a in activities if (a.get("erc20") or {}).get("total_tx_count", 0) > 0),
            "with_labels": labeled,
            "with_counterparty_flows": sum(1 for a in activities if a.get("counterparty_flows")),
            "with_dex_activity": sum(1 for a in activities if a.get("dex")),
        },
        "token_exposure": {
            "unique_tokens": len(all_tokens),
            "tokens": list(all_tokens)[:30],
        },
        "counterparty_graph": {
            "unique_counterparties": len(all_counterparties),
            "resolved": resolved_counterparties,
        },
        "dex_activity": {
            "total_swaps": sum((a.get("dex") or {}).get("total_swaps", 0) for a in activities),
            "protocols": dex_protocols,
        },
        "address_breakdown": sorted(address_breakdown, key=lambda x: x["activity_score"], reverse=True),
    }

    _cache_set(ck, result)
    return result


def get_address_index_status() -> dict:
    """Health check for the address activity index."""
    db = _get_db()

    total_addresses = db["entity_addresses_v2"].count_documents({})
    indexed = db["entity_address_activity_v2"].count_documents({})
    active = db["entity_address_activity_v2"].count_documents({"status": "active"})
    dormant = db["entity_address_activity_v2"].count_documents({"status": "dormant"})
    stale = db["entity_address_activity_v2"].count_documents({"status": "stale"})

    # Last index time
    last = db["entity_address_activity_v2"].find_one(
        {}, {"_id": 0, "indexed_at": 1},
        sort=[("indexed_at", -1)],
    )

    # Score distribution
    score_ranges = {
        "high_75_100": db["entity_address_activity_v2"].count_documents({"activity_score": {"$gte": 75}}),
        "medium_50_74": db["entity_address_activity_v2"].count_documents({"activity_score": {"$gte": 50, "$lt": 75}}),
        "low_25_49": db["entity_address_activity_v2"].count_documents({"activity_score": {"$gte": 25, "$lt": 50}}),
        "minimal_0_24": db["entity_address_activity_v2"].count_documents({"activity_score": {"$lt": 25}}),
    }

    return {
        "total_entity_addresses": total_addresses,
        "indexed": indexed,
        "coverage_pct": round(indexed / max(total_addresses, 1) * 100, 1),
        "status_breakdown": {
            "active": active,
            "dormant": dormant,
            "stale": stale,
            "not_indexed": total_addresses - indexed,
        },
        "score_distribution": score_ranges,
        "last_indexed_at": last.get("indexed_at") if last else None,
    }
