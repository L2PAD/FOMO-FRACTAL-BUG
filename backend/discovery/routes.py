"""
Discovery API Routes
====================
GET /api/discovery/status   — Discovery worker status
GET /api/discovery/wallets  — Wallet registry (paginated)
GET /api/discovery/clusters — Wallet clusters
GET /api/discovery/scores   — Smart money scores
GET /api/discovery/prices   — Token prices
GET /api/discovery/signals  — Discovery-generated signals
"""

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from datetime import datetime, timezone
import os

from motor.motor_asyncio import AsyncIOMotorClient

router = APIRouter(prefix="/api/discovery", tags=["discovery"])


def _serialize_doc(doc: dict) -> dict:
    """Convert datetime objects in a document to ISO strings for JSON serialization."""
    if not doc:
        return doc
    result = {}
    for k, v in doc.items():
        if isinstance(v, datetime):
            result[k] = v.isoformat()
        elif isinstance(v, list):
            result[k] = [_serialize_doc(item) if isinstance(item, dict) else (item.isoformat() if isinstance(item, datetime) else item) for item in v]
        elif isinstance(v, dict):
            result[k] = _serialize_doc(v)
        else:
            result[k] = v
    return result

_client = None


def _get_db():
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    return _client[os.environ.get("DB_NAME", "intelligence_engine")]


@router.get("/status")
async def discovery_status():
    """Discovery worker status and stats."""
    try:
        db = _get_db()
        status = await db.discovery_status.find_one({"key": "discovery_worker"}, {"_id": 0})
        counts = {
            "wallet_registry": await db.wallet_registry.count_documents({}),
            "wallet_clusters": await db.wallet_clusters.count_documents({}),
            "wallet_scores": await db.wallet_scores.count_documents({}),
            "token_prices": await db.token_prices.count_documents({}),
            "discovery_signals": await db.discovery_signals.count_documents({}),
        }
        return JSONResponse(content={
            "ok": True,
            "status": status or {"status": "not_started"},
            "counts": counts,
        })
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.get("/wallets")
async def discovery_wallets(
    wallet_type: str = Query(None, description="Filter by type: exchange, whale, active_wallet, multi_exchange_user"),
    limit: int = Query(50),
    offset: int = Query(0),
):
    """Wallet registry with pagination."""
    try:
        db = _get_db()
        query = {}
        if wallet_type:
            query["type"] = wallet_type

        total = await db.wallet_registry.count_documents(query)
        wallets = await db.wallet_registry.find(
            query, {"_id": 0}
        ).sort("last_seen", -1).skip(offset).limit(limit).to_list(limit)

        # Serialize datetime objects for JSON
        wallets = [_serialize_doc(w) for w in wallets]

        return JSONResponse(content={
            "ok": True,
            "wallets": wallets,
            "total": total,
            "limit": limit,
            "offset": offset,
        })
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.get("/clusters")
async def discovery_clusters(
    cluster_type: str = Query(None, description="Filter: exchange_cluster, fund_cluster, unknown_cluster"),
    limit: int = Query(20),
):
    """Wallet clusters."""
    try:
        db = _get_db()
        query = {}
        if cluster_type:
            query["cluster_type"] = cluster_type

        clusters = await db.wallet_clusters.find(
            query, {"_id": 0}
        ).sort("cluster_score", -1).limit(limit).to_list(limit)

        return JSONResponse(content={
            "ok": True,
            "clusters": clusters,
            "count": len(clusters),
        })
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.get("/scores")
async def discovery_scores(
    min_score: float = Query(0.0, description="Minimum smart money score"),
    limit: int = Query(50),
):
    """Smart money wallet scores."""
    try:
        db = _get_db()
        query = {}
        if min_score > 0:
            query["smart_money_score"] = {"$gte": min_score}

        scores = await db.wallet_scores.find(
            query, {"_id": 0}
        ).sort("smart_money_score", -1).limit(limit).to_list(limit)

        # Enrich with wallet registry info
        for s in scores:
            reg = await db.wallet_registry.find_one(
                {"address": s["wallet"]}, {"_id": 0, "label": 1, "type": 1, "entity": 1}
            )
            if reg:
                s["wallet_label"] = reg.get("label", "")
                s["wallet_type"] = reg.get("type", "")
                s["entity"] = reg.get("entity", "")

        return JSONResponse(content={
            "ok": True,
            "scores": scores,
            "count": len(scores),
        })
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.get("/prices")
async def discovery_prices():
    """Token prices cache."""
    try:
        db = _get_db()
        prices = await db.token_prices.find({}, {"_id": 0}).to_list(100)
        return JSONResponse(content={
            "ok": True,
            "prices": prices,
            "count": len(prices),
        })
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.get("/signals")
async def discovery_signals(
    signal_type: str = Query(None),
    chain: str = Query(None),
    limit: int = Query(50),
):
    """Discovery-generated signals (SMART_MONEY_ACCUMULATION, CLUSTER_ACTIVITY, etc.)."""
    try:
        db = _get_db()
        query = {}
        if signal_type:
            query["signal_type"] = signal_type
        if chain:
            query["chain"] = chain

        signals = await db.discovery_signals.find(
            query, {"_id": 0}
        ).sort("score", -1).limit(limit).to_list(limit)

        # Build cluster name map for human-readable display
        cluster_name_map = {}
        type_counters: dict = {}
        cluster_docs = await db.wallet_clusters.find(
            {}, {"_id": 0, "cluster_id": 1, "cluster_type": 1}
        ).sort("cluster_score", -1).to_list(500)
        for cl in cluster_docs:
            cid = cl.get("cluster_id", "")
            ctype = cl.get("cluster_type", "unknown")
            type_label = ctype.replace("_cluster", "").replace("_", " ").title()
            type_counters[ctype] = type_counters.get(ctype, 0) + 1
            cluster_name_map[cid] = f"{type_label} Cluster #{type_counters[ctype]}"

        # Enrich entity names
        for s in signals:
            entity = s.get("entity", "")
            if entity and entity.startswith("Cluster "):
                cid = entity.replace("Cluster ", "")
                if cid in cluster_name_map:
                    s["entity"] = cluster_name_map[cid]

        return JSONResponse(content={
            "ok": True,
            "signals": signals,
            "count": len(signals),
        })
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})
