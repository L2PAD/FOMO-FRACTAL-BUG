"""
On-Chain Admin V2 Routes — Full admin panel API
Serves the tabbed admin interface (Overview, Engine, Infrastructure, Governance, Research, Validation)
"""

from fastapi import APIRouter, Query, Body
from fastapi.responses import JSONResponse
from . import service

router = APIRouter(tags=["onchain-admin-v2"])


# ─── Runtime & Governance (OverviewTab / EngineTab props) ───

@router.get("/api/v10/onchain-v2/admin/runtime")
async def get_runtime():
    try:
        data = await service.get_runtime_status()
        return JSONResponse(content={"ok": True, **data})
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.get("/api/v10/onchain-v2/admin/governance/state")
async def get_governance_state():
    try:
        data = await service.get_governance_state()
        return JSONResponse(content={"ok": True, **data})
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


# ─── InfrastructureTab ───

@router.get("/api/v10/onchain-v2/admin/rpc")
async def get_rpc_config():
    try:
        data = await service.get_rpc_config()
        return JSONResponse(content=data)
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.get("/api/v10/onchain-v2/admin/snapshot/backfill-metrics")
async def get_backfill_metrics():
    try:
        data = await service.get_snapshot_metrics()
        return JSONResponse(content=data)
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.post("/api/v10/onchain-v2/admin/snapshot/tick")
async def force_snapshot():
    try:
        data = await service.force_snapshot_tick()
        return JSONResponse(content=data)
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


# ─── GovernanceTab ───

@router.get("/api/v10/onchain-v2/admin/governance/audit")
async def get_audit(limit: int = Query(30)):
    try:
        data = await service.get_audit_log(limit)
        return JSONResponse(content=data)
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.get("/api/v10/onchain-v2/admin/governance/policy/active")
async def get_active_policy():
    try:
        data = await service.get_active_policy()
        return JSONResponse(content=data)
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.post("/api/v10/onchain-v2/admin/governance/policy/dry-run")
async def policy_dry_run(body: dict = Body({})):
    try:
        data = await service.run_policy_dry_run(body)
        return JSONResponse(content=data)
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.get("/api/v10/onchain-v2/admin/rolling/{asset}")
async def get_rolling(asset: str, window: str = Query("30d")):
    try:
        data = await service.get_rolling_stats(asset, window)
        return JSONResponse(content=data)
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.get("/api/v10/onchain-v2/admin/drift/{asset}")
async def get_drift(asset: str):
    try:
        data = await service.get_drift_data(asset)
        return JSONResponse(content=data)
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.post("/api/v10/onchain-v2/admin/baseline/{asset}/score")
async def recompute_baseline(asset: str):
    try:
        data = await service.recompute_baseline(asset)
        return JSONResponse(content=data)
    except Exception as e:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


# ─── ResearchTab (v6 observation) ───

@router.get("/api/v6/observation/stats")
async def observation_stats():
    db = service.get_db()
    total = await db.observation_log.count_documents({})
    by_decision = {}
    if total > 0:
        pipeline = [{"$group": {"_id": "$decision", "count": {"$sum": 1}}}]
        async for doc in db.observation_log.aggregate(pipeline):
            by_decision[doc["_id"]] = doc["count"]
    return JSONResponse(content={"total": total, "byDecision": by_decision})


@router.get("/api/v6/observation/metrics/summary")
async def observation_metrics():
    return JSONResponse(content={
        "falseConfidenceRate": 0,
        "avgConfidence": 0,
        "totalValidated": 0,
    })


@router.get("/api/v6/observation/ml/status")
async def ml_status():
    return JSONResponse(content={
        "loaded": False,
        "version": "0.0.0",
        "accuracy": 0,
        "trainingSamples": 0,
    })


@router.post("/api/v6/observation/ml/train")
async def ml_train():
    return JSONResponse(content={"ok": True, "message": "Training not available in lite mode"})


# ─── ValidationTab (v7 validation) ───

@router.get("/api/v7/validation/stats")
async def validation_stats():
    db = service.get_db()
    total = await db.validation_results.count_documents({})
    by_verdict = {}
    by_impact = {}
    if total > 0:
        pipeline = [{"$group": {"_id": "$verdict", "count": {"$sum": 1}}}]
        async for doc in db.validation_results.aggregate(pipeline):
            by_verdict[doc["_id"]] = doc["count"]
        pipeline2 = [{"$group": {"_id": "$impact", "count": {"$sum": 1}}}]
        async for doc in db.validation_results.aggregate(pipeline2):
            by_impact[doc["_id"]] = doc["count"]

    confirms = by_verdict.get("CONFIRMS", 0)
    contradicts = by_verdict.get("CONTRADICTS", 0)
    t = confirms + contradicts or 1

    return JSONResponse(content={
        "validation": {
            "total": total,
            "by_verdict": by_verdict,
            "by_impact": by_impact,
        },
        "kpis": {
            "use_confirm_rate": f"{confirms / t * 100:.1f}%",
            "use_contradict_rate": f"{contradicts / t * 100:.1f}%",
            "miss_confirm_rate": "0.0%",
            "false_positive_reduced": "0.0%",
        },
        "timestamp": None,
    })


@router.get("/api/v7/validation/contradictions")
async def validation_contradictions(limit: int = Query(20)):
    db = service.get_db()
    docs = await db.validation_results.find(
        {"verdict": "CONTRADICTS"}, {"_id": 0}
    ).sort("timestamp", -1).limit(limit).to_list(limit)
    return JSONResponse(content={"contradictions": docs})


@router.post("/api/v7/validation/batch")
async def validation_batch():
    return JSONResponse(content={"ok": True, "message": "Batch validation not available in lite mode"})
