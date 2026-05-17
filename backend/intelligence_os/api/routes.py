"""
Intelligence OS — API Routes
==============================
Exposes the Intelligence OS through FastAPI routes.
Prefixed with /api/intel-os/
"""
from fastapi import APIRouter
from intelligence_os.core.logging_config import get_logger

log = get_logger("api")

router = APIRouter(prefix="/api/intel-os", tags=["Intelligence OS"])

# These will be set on startup
_full_cycle = None
_db = None


def init_api(db, full_cycle):
    global _full_cycle, _db
    _full_cycle = full_cycle
    _db = db


@router.get("/health")
async def health():
    if _db is None:
        return {"ok": False, "error": "DB not initialized"}

    from intelligence_os.ops.health_service import HealthService
    health_svc = HealthService(_db)
    summary = await health_svc.get_summary()
    return {"ok": True, "health": summary}


@router.get("/source-matrix")
async def source_matrix():
    from intelligence_os.ops.parser_registry import get_source_matrix
    matrix = get_source_matrix()
    return {
        "ok": True,
        "sources": [
            {
                "name": s.name,
                "domain": s.domain.value,
                "tier": s.tier.value,
                "method": s.method.value,
                "enabled": s.enabled,
                "fallback_chain": s.fallback_chain,
                "raw_collection": s.raw_collection,
                "sync_interval_min": s.sync_interval_min,
            }
            for s in matrix
        ],
    }


@router.get("/trust")
async def trust_scores():
    if _db is None:
        return {"ok": False}
    from intelligence_os.ops.trust_service import TrustService
    trust = TrustService(_db)
    scores = await trust.get_all_trust()
    return {"ok": True, "trust": scores}


@router.get("/canonical/stats")
async def canonical_stats():
    if _db is None:
        return {"ok": False}
    from intelligence_os.canonical.pipeline import CanonicalPipeline
    pipeline = CanonicalPipeline(_db)
    stats = await pipeline.get_stats()
    return {"ok": True, "canonical": stats}


@router.get("/raw/stats")
async def raw_stats():
    if _db is None:
        return {"ok": False}
    from intelligence_os.raw.repositories import RawRepository
    repo = RawRepository(_db)
    stats = await repo.get_stats()
    return {"ok": True, "raw": stats}


@router.post("/cycle/full")
async def run_full_cycle():
    if _full_cycle is None:
        return {"ok": False, "error": "Full cycle not initialized"}
    result = await _full_cycle.run_full_cycle()
    return result


@router.post("/cycle/ingestion")
async def run_ingestion():
    if _full_cycle is None:
        return {"ok": False}
    result = await _full_cycle.run_ingestion_only()
    return result


@router.post("/cycle/canonical")
async def run_canonical():
    if _full_cycle is None:
        return {"ok": False}
    result = await _full_cycle.run_canonical_only()
    return result


@router.post("/cycle/intelligence")
async def run_intelligence():
    if _full_cycle is None:
        return {"ok": False}
    result = await _full_cycle.run_intelligence_only()
    return result


@router.get("/unlocks/upcoming")
async def upcoming_unlocks():
    if _db is None:
        return {"ok": False}
    from intelligence_os.domains.unlocks.intelligence import UnlocksIntelligence
    intel = UnlocksIntelligence(_db)
    unlocks = await intel.get_upcoming_windows(days=7)
    return {"ok": True, "unlocks": unlocks}


@router.get("/cycle/history")
async def cycle_history():
    if _db is None:
        return {"ok": False}
    cursor = _db["ops_cycle_health"].find(
        {}, {"_id": 0}
    ).sort("cycle_completed_at", -1).limit(10)
    history = await cursor.to_list(length=10)
    return {"ok": True, "history": history}


# ═══════════════════════════════════════════════════════════════
# WATCHDOG & TWITTER HYBRID ENDPOINTS
# ═══════════════════════════════════════════════════════════════


@router.get("/ops/watchdog/status")
async def watchdog_status():
    if _db is None:
        return {"ok": False}
    from intelligence_os.ops.watchdog_cycle import WatchdogCycle
    wc = WatchdogCycle(_db)
    report = await wc.run()
    return {"ok": True, "report": report}


@router.get("/ops/watchdog/incidents")
async def watchdog_incidents():
    if _db is None:
        return {"ok": False}
    from intelligence_os.ops.incident_logger import IncidentLogger
    il = IncidentLogger(_db)
    incidents = await il.get_recent(limit=20)
    stats = await il.get_stats()
    return {"ok": True, "incidents": incidents, "stats": stats}


@router.post("/ops/watchdog/recover")
async def watchdog_recover():
    if _db is None:
        return {"ok": False}
    from intelligence_os.ops.watchdog_cycle import WatchdogCycle
    wc = WatchdogCycle(_db)
    report = await wc.run()
    return {"ok": True, "report": report}


@router.get("/ops/twitter/status")
async def twitter_status():
    if _db is None:
        return {"ok": False}
    from intelligence_os.ops.twitter_watchdog import TwitterWatchdog
    tw = TwitterWatchdog(_db)
    status = await tw.check()
    return {"ok": True, "twitter": status}


@router.get("/ops/sessions")
async def session_status():
    if _db is None:
        return {"ok": False}
    from intelligence_os.ops.session_rotation import SessionRotation
    sr = SessionRotation(_db)
    status = await sr.get_session_status()
    return {"ok": True, "sessions": status}


@router.post("/twitter/hybrid/run")
async def run_twitter_hybrid():
    """Run Twitter hybrid ingestion for all top actors."""
    if _db is None:
        return {"ok": False}
    from intelligence_os.ingestion.twitter.hybrid_service import TwitterHybridService

    actors = [
        "CryptoHayes", "DefiIgnas", "TheCryptoDog", "inversebrah",
        "AltcoinGordon", "MoustacheXBT", "Pentosh1", "CryptoCobain",
        "RaoulGMI", "ZssBecker", "blaboratorio",
    ]

    hybrid = TwitterHybridService(_db)
    result = await hybrid.run_batch(actors)
    return result


@router.get("/ops/flags")
async def system_flags():
    if _db is None:
        return {"ok": False}
    cursor = _db["system_flags"].find({}, {"_id": 0})
    flags = await cursor.to_list(length=50)
    return {"ok": True, "flags": flags}
