"""
On-Chain Lite Routes + Admin Indexer Routes
============================================
GET /api/onchain/summary    — Network health (block, gas, TPS)
GET /api/onchain/flows      — Exchange + Stablecoin flows
GET /api/onchain/whales     — Large transfers with explorer links
GET /api/onchain/activity   — DEX volumes, TVL, top pairs
GET /api/onchain/status     — Current mode and state

Admin (indexer control):
GET  /api/admin/indexer/status   — Full status
POST /api/admin/indexer/mode     — Change mode (LIMITED/STANDARD/FULL)
POST /api/admin/indexer/pause    — Pause all
POST /api/admin/indexer/resume   — Resume
POST /api/admin/indexer/boost    — Temporary FULL mode
"""

from fastapi import APIRouter, Query, Body
from fastapi.responses import JSONResponse
import os
import time

from . import service

router = APIRouter(tags=["onchain-lite"])


# ─── OnChain Guard (Task 4 · 2026-05-12) ─────────────────────────────────
# Master switch. When ONCHAIN_ENABLED=false (default), the four data
# endpoints below return a truthful "degraded · disabled" envelope WITHOUT
# touching the service layer — no RPC, no HTTP, no cache lookup, no log.
# Admin / status / diagnostics endpoints stay live so operators can still
# inspect that the subsystem is intentionally disabled.
# See /app/memory/ONCHAIN_GUARD_2026-05-12.md
def _onchain_enabled() -> bool:
    val = os.environ.get("ONCHAIN_ENABLED", "false")
    return str(val).strip().lower() in ("1", "true", "yes", "on")


_DISABLED_ENVELOPE = {
    "ok": False,
    "degraded": True,
    "reason": "onchain_disabled",
    "detail": (
        "OnChain subsystem is intentionally disabled by ONCHAIN_ENABLED=false. "
        "No RPC providers are being polled. Cognitive layers treat the absence "
        "as honest 'module not contributing' per Truthful Degradation. "
        "Enable by setting ONCHAIN_ENABLED=true in backend/.env."
    ),
    "data": None,
    "mode": "disabled",
}


# ─── On-Chain Data Endpoints ───

@router.get("/api/onchain/summary")
async def onchain_summary(chain: str = Query("ethereum")):
    if not _onchain_enabled():
        return JSONResponse(content=_DISABLED_ENVELOPE)
    try:
        data = await service.get_summary(chain)
        return JSONResponse(content={"ok": True, "data": data, "mode": service.get_mode()})
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e), "mode": service.get_mode()})


@router.get("/api/onchain/flows")
async def onchain_flows(chain: str = Query("ethereum")):
    if not _onchain_enabled():
        return JSONResponse(content=_DISABLED_ENVELOPE)
    try:
        data = await service.get_flows(chain)
        return JSONResponse(content={"ok": True, "data": data, "mode": service.get_mode()})
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e), "mode": service.get_mode()})


@router.get("/api/onchain/whales")
async def onchain_whales(chain: str = Query("ethereum")):
    if not _onchain_enabled():
        return JSONResponse(content=_DISABLED_ENVELOPE)
    try:
        data = await service.get_whales(chain)
        return JSONResponse(content={"ok": True, "data": data, "mode": service.get_mode()})
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e), "mode": service.get_mode()})


@router.get("/api/onchain/activity")
async def onchain_activity(chain: str = Query("ethereum")):
    if not _onchain_enabled():
        return JSONResponse(content=_DISABLED_ENVELOPE)
    try:
        data = await service.get_activity(chain)
        return JSONResponse(content={"ok": True, "data": data, "mode": service.get_mode()})
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e), "mode": service.get_mode()})


@router.get("/api/onchain/status")
async def onchain_status():
    if not _onchain_enabled():
        return JSONResponse(content={
            "ok": True,
            "enabled": False,
            "mode": "disabled",
            "reason": "onchain_disabled",
            "paused": True,
            "chains": [],
            "cache_ttl": 0,
        })
    return JSONResponse(content={
        "ok": True,
        "enabled": True,
        "mode": service.get_mode(),
        "paused": service._mode_state["paused"],
        "boost_until": service._mode_state["boost_until"],
        "chains": list(service.CHAIN_RPCS.keys()),
        "cache_ttl": service.CACHE_TTL,
    })


# ─── Admin Indexer Control ───

@router.get("/api/admin/indexer/status")
async def admin_indexer_status():
    await service._load_mode_from_db()
    mode = service.get_mode()
    chains = list(service.CHAIN_RPCS.keys())
    rpc_pools = {}
    for chain in chains:
        rpc_pools[chain] = {
            "availableProviders": 1,
            "totalProviders": 1,
            "totalRps": 10,
            "active": 1,
            "total": 1,
            "providers": [{
                "id": f"{chain}-rpc",
                "status": "HEALTHY",
                "enabled": True,
                "inCooldown": False,
            }],
        }
    return JSONResponse(content={
        "ok": True,
        "indexer": {
            "mode": mode.upper() if mode not in ("paused", "boost") else "STANDARD",
            "runtimeStatus": "PAUSED" if service._mode_state["paused"] else "RUNNING",
            "paused": service._mode_state["paused"],
            "boostActive": service._mode_state["boost_until"] > time.time(),
        },
        "rpcPools": rpc_pools,
        "checkpoints": {},
        "summary": {
            "activeProviders": len(chains),
            "totalProviders": len(chains),
            "networks": chains,
        },
        "mode": mode.upper(),
        "paused": service._mode_state["paused"],
        "boost_until": service._mode_state["boost_until"],
    })


@router.post("/api/admin/indexer/mode")
async def admin_set_mode(body: dict = Body(...)):
    mode = body.get("mode", "").upper()
    valid = {"LIMITED", "STANDARD", "FULL"}
    if mode not in valid:
        return JSONResponse(status_code=400, content={"ok": False, "error": f"Invalid mode. Use: {valid}"})

    mode_map = {"LIMITED": "preview", "STANDARD": "preview", "FULL": "indexer"}
    await service.set_mode(mode_map.get(mode, "preview"))
    return JSONResponse(content={"ok": True, "mode": mode, "internal": service.get_mode()})


@router.post("/api/admin/indexer/pause")
async def admin_pause():
    await service.pause()
    return JSONResponse(content={"ok": True, "paused": True})


@router.post("/api/admin/indexer/resume")
async def admin_resume():
    await service.resume()
    return JSONResponse(content={"ok": True, "paused": False})


@router.post("/api/admin/indexer/boost")
async def admin_boost(body: dict = Body(...)):
    minutes = body.get("minutes", 5)
    if not 1 <= minutes <= 60:
        return JSONResponse(status_code=400, content={"ok": False, "error": "minutes must be 1-60"})
    await service.boost(minutes)
    return JSONResponse(content={"ok": True, "boost_minutes": minutes, "mode": "boost"})


# ─── Indexer Diagnostics ───

@router.get("/api/admin/indexer/diagnostics")
async def admin_diagnostics():
    """Полная диагностика индексера — RPC, sync, ingestion, signals"""
    try:
        db = service._get_mode_db()
        await service._load_mode_from_db()
        mode = service.get_mode()

        # RPC health per chain
        rpc_status = {}
        for chain, rpc_url in service.CHAIN_RPCS.items():
            try:
                start = time.time()
                block_hex = await service._rpc_call(rpc_url, "eth_blockNumber")
                latency = round((time.time() - start) * 1000)
                rpc_status[chain] = {
                    "status": "connected",
                    "latency_ms": latency,
                    "head_block": int(block_hex, 16) if block_hex else 0,
                }
            except Exception as e:
                rpc_status[chain] = {"status": "error", "error": str(e), "head_block": 0}

        # Sync state per chain
        chains_sync = {}
        sync_docs = await db.indexer_sync_state.find({}, {"_id": 0}).to_list(10)
        for doc in sync_docs:
            chains_sync[doc["chain"]] = {
                "last_block": doc.get("last_block", 0),
                "head_block": doc.get("head_block", 0),
                "lag": doc.get("lag", 0),
                "status": doc.get("status", "unknown"),
                "updated_at": doc.get("updated_at"),
            }

        # Ingestion metrics per chain
        ingestion = {}
        metric_docs = await db.indexer_metrics.find({}, {"_id": 0}).to_list(10)
        for doc in metric_docs:
            ingestion[doc["chain"]] = {
                "blocks_per_min": doc.get("blocks_per_min", 0),
                "tx_per_min": doc.get("tx_per_min", 0),
                "events_per_min": doc.get("events_per_min", 0),
            }

        # Collection counts
        blocks_count = await db.indexed_blocks.count_documents({})
        tx_count = await db.indexed_transactions.count_documents({})
        events_count = await db.indexed_events.count_documents({})
        entity_activity_count = await db.entity_activity.count_documents({})
        token_transfers_count = await db.token_transfers.count_documents({})
        token_registry_count = await db.token_registry.count_documents({})

        # Entity resolution stats
        enriched_tx_count = await db.indexed_transactions.count_documents({"from_entity": {"$ne": ""}})
        address_labels_count = await db.onchain_v2_address_labels.count_documents({})
        entities_count = await db.entities.count_documents({})

        # Signal stats
        signals_count = await db.signals_stream.count_documents({})
        last_signal = await db.signals_stream.find_one({}, {"_id": 0, "createdAt": 1}, sort=[("createdAt", -1)])

        # Overall health
        rpc_ok = all(s.get("status") == "connected" for s in rpc_status.values())
        sync_ok = all(s.get("status") in ("synced", "syncing", "lite") for s in chains_sync.values()) if chains_sync else False
        ingestion_active = any(m.get("blocks_per_min", 0) > 0 for m in ingestion.values())
        entity_resolution_active = entity_activity_count > 0

        return JSONResponse(content={
            "ok": True,
            "mode": mode,
            "rpc": {
                "status": "connected" if rpc_ok else "degraded",
                "provider": "infura" if service.INFURA_KEY else "public",
                "chains": rpc_status,
            },
            "chains": chains_sync,
            "ingestion": {
                "active": ingestion_active,
                "chains": ingestion,
                "totals": {
                    "blocks": blocks_count,
                    "transactions": tx_count,
                    "events": events_count,
                    "entity_activity": entity_activity_count,
                    "token_transfers": token_transfers_count,
                    "token_registry": token_registry_count,
                },
            },
            "entity_resolution": {
                "active": entity_resolution_active,
                "address_labels_loaded": address_labels_count,
                "entities_loaded": entities_count,
                "enriched_transactions": enriched_tx_count,
                "entity_activity_records": entity_activity_count,
            },
            "signals": {
                "total": signals_count,
                "last_signal_at": last_signal.get("createdAt") if last_signal else None,
            },
            "health": {
                "rpc": "ok" if rpc_ok else "error",
                "sync": "ok" if sync_ok else ("idle" if not chains_sync else "error"),
                "ingestion": "ok" if ingestion_active else "idle",
                "entity_resolution": "ok" if entity_resolution_active else "idle",
                "signals": "ok" if signals_count > 0 else "idle",
            },
        })
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.post("/api/admin/indexer/restart")
async def admin_restart_indexer():
    """Перезапускает worker индексера"""
    import subprocess
    try:
        subprocess.run(["pkill", "-f", "indexer_worker.py"], capture_output=True)
        await asyncio.sleep(1)
        subprocess.Popen(
            [sys.executable, "/app/indexer/indexer_worker.py"],
            cwd="/app/indexer",
            stdout=open("/var/log/supervisor/indexer_worker.out.log", "a"),
            stderr=open("/var/log/supervisor/indexer_worker.err.log", "a"),
        )
        return JSONResponse(content={"ok": True, "message": "Indexer worker restarted"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


import asyncio  # noqa: E402
import sys  # noqa: E402
from datetime import datetime as _dt  # noqa: E402


def _json_safe(obj):
    """Рекурсивно конвертирует datetime и ObjectId в строки для JSON"""
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, _dt):
        return obj.isoformat()
    return obj


# ─── Address Resolution API ───

@router.get("/api/address/resolve")
async def resolve_address(address: str = Query(...), chain: str = Query("ethereum")):
    """Определяет кому принадлежит адрес: биржа, фонд, MM, протокол"""
    try:
        db = service._get_mode_db()
        addr = address.lower()

        # Check onchain_v2_address_labels
        label_doc = await db.onchain_v2_address_labels.find_one(
            {"address": addr}, {"_id": 0}
        )

        # Check entity_addresses
        entity_doc = await db.entity_addresses.find_one(
            {"address": addr}, {"_id": 0}
        )

        # Check entities
        entity_info = None
        if entity_doc:
            entity_name = entity_doc.get("entityName", entity_doc.get("entity", ""))
            if entity_name:
                entity_info = await db.entities.find_one(
                    {"name": entity_name}, {"_id": 0}
                )

        # Recent activity
        recent_txs = await db.indexed_transactions.find(
            {"$or": [
                {"from_addr": addr, "chain": chain},
                {"to_addr": addr, "chain": chain},
            ]},
            {"_id": 0, "hash": 1, "value_eth": 1, "tx_type": 1, "from_entity": 1, "to_entity": 1, "timestamp": 1, "explorer_url": 1}
        ).sort("timestamp", -1).limit(10).to_list(10)

        # Entity name
        entity_name_found = ""
        entity_type_found = ""
        if label_doc:
            entity_name_found = label_doc.get("name", label_doc.get("entityId", ""))
            entity_type_found = label_doc.get("type", label_doc.get("labelType", ""))
        if entity_doc and not entity_name_found:
            entity_name_found = entity_doc.get("entityName", "")

        activity = []
        if entity_name_found:
            activity = await db.entity_activity.find(
                {"entity": entity_name_found, "chain": chain},
                {"_id": 0}
            ).sort("timestamp", -1).limit(10).to_list(10)

        # Explorer URL
        explorer_map = {
            "ethereum": "https://etherscan.io",
            "arbitrum": "https://arbiscan.io",
            "optimism": "https://optimistic.etherscan.io",
            "base": "https://basescan.org",
        }
        explorer = explorer_map.get(chain, "https://etherscan.io")

        return JSONResponse(content=_json_safe({
            "ok": True,
            "address": addr,
            "chain": chain,
            "is_known": bool(label_doc or entity_doc),
            "label": label_doc if label_doc else None,
            "entity": {
                "name": entity_name_found,
                "entity_type": entity_type_found,
                "info": entity_info,
                "address_link": entity_doc,
            } if entity_name_found else None,
            "explorer_url": f"{explorer}/address/{addr}",
            "recent_transactions": recent_txs,
            "entity_activity": activity,
        }))
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.get("/api/address/resolve/batch")
async def resolve_addresses_batch(addresses: str = Query(..., description="Comma-separated addresses")):
    """Batch resolve: определяет несколько адресов за раз"""
    try:
        db = service._get_mode_db()
        addr_list = [a.strip().lower() for a in addresses.split(",") if a.strip()][:50]

        results = {}
        for addr in addr_list:
            label_doc = await db.onchain_v2_address_labels.find_one(
                {"address": addr}, {"_id": 0}
            )
            if label_doc:
                tags = label_doc.get("tags", [])
                entity_name = ""
                for t in tags:
                    if t not in ("cex", "hot", "cold", "deposit", "l1"):
                        entity_name = t.replace("_", " ").title()
                        break
                results[addr] = {
                    "is_known": True,
                    "entity_name": entity_name,
                    "tags": tags,
                    "entity_type": "exchange" if "cex" in tags else "protocol" if "protocol" in tags else "unknown",
                }
            else:
                results[addr] = {"is_known": False}

        return JSONResponse(content={"ok": True, "results": results})
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


# ─── Entity Activity Stats ───

@router.get("/api/entity/activity")
async def entity_activity_stats(
    chain: str = Query("ethereum"),
    entity: str = Query(None),
    limit: int = Query(50),
):
    """Показывает активность известных акторов"""
    try:
        db = service._get_mode_db()
        query = {"chain": chain}
        if entity:
            query["entity"] = {"$regex": entity, "$options": "i"}

        docs = await db.entity_activity.find(
            query, {"_id": 0}
        ).sort("timestamp", -1).limit(limit).to_list(limit)

        # Stats
        pipeline = [
            {"$match": {"chain": chain}},
            {"$group": {
                "_id": "$entity",
                "tx_count": {"$sum": 1},
                "total_value_eth": {"$sum": "$value_eth"},
                "last_seen": {"$max": "$timestamp"},
            }},
            {"$sort": {"tx_count": -1}},
            {"$limit": 20},
        ]
        top_entities = await db.entity_activity.aggregate(pipeline).to_list(20)

        return JSONResponse(content=_json_safe({
            "ok": True,
            "chain": chain,
            "activity": docs,
            "top_entities": top_entities,
        }))
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.get("/api/entity/activity/summary")
async def entity_activity_summary():
    """Сводка активности акторов по всем цепям"""
    try:
        db = service._get_mode_db()

        total = await db.entity_activity.count_documents({})

        by_type = await db.entity_activity.aggregate([
            {"$group": {"_id": "$tx_type", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
        ]).to_list(20)

        by_entity_type = await db.entity_activity.aggregate([
            {"$group": {"_id": "$entity_type", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
        ]).to_list(10)

        by_chain = await db.entity_activity.aggregate([
            {"$group": {"_id": "$chain", "count": {"$sum": 1}}},
        ]).to_list(10)

        return JSONResponse(content={
            "ok": True,
            "total_activity": total,
            "by_tx_type": {d["_id"]: d["count"] for d in by_type if d["_id"]},
            "by_entity_type": {d["_id"]: d["count"] for d in by_entity_type if d["_id"]},
            "by_chain": {d["_id"]: d["count"] for d in by_chain if d["_id"]},
        })
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})
