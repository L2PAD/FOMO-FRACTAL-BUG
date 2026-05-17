"""
Data Sync Routes
================
API endpoints for triggering data synchronization from external sources.
"""

from fastapi import APIRouter, Query, BackgroundTasks
from typing import Optional
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/sync", tags=["Data Sync"])


def ts_now():
    return int(datetime.now(timezone.utc).timestamp() * 1000)


@router.post("/coingecko")
async def sync_coingecko(
    background_tasks: BackgroundTasks,
    full: bool = Query(False, description="Full sync including detailed profiles (slower)")
):
    """
    Sync market data from CoinGecko.
    
    - full=False: Quick sync of top 100 coins market data
    - full=True: Full sync including detailed profiles (slower due to rate limits)
    """
    from server import db
    from modules.parsers.parser_coingecko import sync_coingecko_data
    
    # Run in background to avoid timeout
    background_tasks.add_task(sync_coingecko_data, db, full)
    
    return {
        "ts": ts_now(),
        "ok": True,
        "message": "CoinGecko sync started in background",
        "full_sync": full
    }


@router.post("/cryptorank")
async def sync_cryptorank(background_tasks: BackgroundTasks):
    """
    Sync funding rounds and activities from CryptoRank.
    """
    from server import db
    from modules.parsers.parser_cryptorank import sync_cryptorank_data
    
    background_tasks.add_task(sync_cryptorank_data, db)
    
    return {
        "ts": ts_now(),
        "ok": True,
        "message": "CryptoRank sync started in background"
    }


@router.post("/activities")
async def sync_activities(background_tasks: BackgroundTasks):
    """
    Sync crypto activities from Dropstab, DropsEarn, and other sources.
    """
    from server import db
    from modules.parsers.parser_activities import sync_activities_data
    
    background_tasks.add_task(sync_activities_data, db)
    
    return {
        "ts": ts_now(),
        "ok": True,
        "message": "Activities sync started in background"
    }


@router.post("/defillama")
async def sync_defillama(background_tasks: BackgroundTasks):
    """
    Sync DeFi protocol data from DefiLlama.
    - TVL data
    - Protocol list
    - Chain data
    """
    from server import db
    from modules.parsers.parser_defillama import sync_defillama_data
    
    background_tasks.add_task(sync_defillama_data, db)
    
    return {
        "ts": ts_now(),
        "ok": True,
        "message": "DefiLlama sync started in background"
    }


@router.post("/all")
async def sync_all_sources(background_tasks: BackgroundTasks):
    """
    Sync data from all external sources:
    - CoinGecko (market data)
    - CryptoRank (funding, activities)
    - Dropstab/DropsEarn (campaigns)
    """
    from server import db
    from modules.parsers.parser_coingecko import sync_coingecko_data
    from modules.parsers.parser_cryptorank import sync_cryptorank_data
    from modules.parsers.parser_activities import sync_activities_data
    
    async def sync_all():
        try:
            await sync_coingecko_data(db, full=False)
            await sync_cryptorank_data(db)
            await sync_activities_data(db)
            logger.info("All sources sync complete")
        except Exception as e:
            logger.error(f"Sync all error: {e}")
    
    background_tasks.add_task(sync_all)
    
    return {
        "ts": ts_now(),
        "ok": True,
        "message": "Full data sync started in background",
        "sources": ["coingecko", "cryptorank", "dropstab", "dropsearn"]
    }


@router.get("/status")
async def get_sync_status():
    """
    Get data sync status - counts from each source.
    """
    from server import db
    
    # Count records by source
    stats = {}
    
    # Market data
    stats["market_data"] = await db.market_data.count_documents({})
    stats["market_coingecko"] = await db.market_data.count_documents({"source": "coingecko"})
    
    # Activities
    stats["activities_total"] = await db.crypto_activities.count_documents({})
    stats["activities_dropstab"] = await db.crypto_activities.count_documents({"source": "dropstab"})
    stats["activities_dropsearn"] = await db.crypto_activities.count_documents({"source": "dropsearn"})
    stats["activities_cryptorank"] = await db.crypto_activities.count_documents({"source": "cryptorank"})
    stats["activities_seed"] = await db.crypto_activities.count_documents({"source": "seed"})
    
    # Funding
    stats["funding_total"] = await db.intel_funding.count_documents({})
    stats["funding_cryptorank"] = await db.intel_funding.count_documents({"source": "cryptorank"})
    stats["funding_seed"] = await db.intel_funding.count_documents({"source": "seed"})
    
    # Projects
    stats["projects_total"] = await db.intel_projects.count_documents({})
    stats["project_profiles"] = await db.project_profiles.count_documents({})
    stats["project_links"] = await db.project_links.count_documents({})
    
    # Unlocks
    stats["unlocks_total"] = await db.token_unlocks.count_documents({})
    
    return {
        "ts": ts_now(),
        "stats": stats,
        "sources": {
            "coingecko": {"market_data": stats["market_coingecko"]},
            "cryptorank": {"funding": stats["funding_cryptorank"], "activities": stats["activities_cryptorank"]},
            "dropstab": {"activities": stats["activities_dropstab"]},
            "dropsearn": {"activities": stats["activities_dropsearn"]},
            "seed": {"activities": stats["activities_seed"], "funding": stats["funding_seed"]}
        }
    }



# ═══════════════════════════════════════════════════════════════
# AUTO-SYNC SCHEDULER ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@router.get("/scheduler/status")
async def get_scheduler_status():
    """Get auto-sync scheduler status"""
    from server import db
    from modules.sync_scheduler import get_sync_scheduler
    
    scheduler = get_sync_scheduler(db)
    
    # Get last sync log
    last_sync = await db.sync_logs.find_one(
        {"type": "auto_sync"},
        sort=[("timestamp", -1)]
    )
    
    # Count active sources
    active_sources = await db.data_sources.count_documents({"status": "active"})
    total_sources = await db.data_sources.count_documents({})
    
    return {
        "ts": ts_now(),
        "scheduler_running": scheduler.running if scheduler else False,
        "sync_interval_hours": scheduler.sync_interval_hours if scheduler else 1,
        "active_sources": active_sources,
        "total_sources": total_sources,
        "available_parsers": list(scheduler.parsers.keys()) if scheduler else [],
        "last_sync": {
            "timestamp": last_sync.get("timestamp") if last_sync else None,
            "sources_synced": last_sync.get("sources_synced", 0) if last_sync else 0,
            "errors": last_sync.get("errors", []) if last_sync else []
        }
    }


@router.post("/scheduler/run")
async def trigger_full_sync(background_tasks: BackgroundTasks):
    """Trigger sync of all active data sources"""
    from server import db
    from modules.sync_scheduler import get_sync_scheduler
    
    scheduler = get_sync_scheduler(db)
    
    if not scheduler:
        return {"ok": False, "error": "Scheduler not initialized"}
    
    # Run in background
    background_tasks.add_task(scheduler.sync_all_active)
    
    return {
        "ts": ts_now(),
        "ok": True,
        "message": "Full sync started in background"
    }


@router.post("/scheduler/source/{source_id}")
async def sync_single_source(source_id: str, background_tasks: BackgroundTasks):
    """Sync a specific data source"""
    from server import db
    from modules.sync_scheduler import get_sync_scheduler
    
    scheduler = get_sync_scheduler(db)
    
    if not scheduler:
        return {"ok": False, "error": "Scheduler not initialized"}
    
    if source_id not in scheduler.parsers:
        return {"ok": False, "error": f"No parser available for {source_id}"}
    
    # Run in background
    background_tasks.add_task(scheduler.sync_source, source_id)
    
    return {
        "ts": ts_now(),
        "ok": True,
        "source_id": source_id,
        "message": f"Sync started for {source_id}"
    }


@router.get("/scheduler/logs")
async def get_sync_logs(limit: int = Query(20, ge=1, le=100)):
    """Get sync history logs"""
    from server import db
    
    cursor = db.sync_logs.find(
        {"type": "auto_sync"}
    ).sort("timestamp", -1).limit(limit)
    
    logs = []
    async for log in cursor:
        log["_id"] = str(log["_id"])
        logs.append(log)
    
    return {
        "ts": ts_now(),
        "count": len(logs),
        "logs": logs
    }


@router.post("/scheduler/start")
async def start_scheduler():
    """Start the auto-sync scheduler (runs every hour)"""
    from server import db
    from modules.sync_scheduler import get_sync_scheduler
    
    scheduler = get_sync_scheduler(db)
    
    if scheduler.running:
        return {"ok": True, "message": "Scheduler already running"}
    
    await scheduler.start()
    return {"ok": True, "message": "Scheduler started (syncs every hour)"}


@router.post("/scheduler/stop")
async def stop_scheduler():
    """Stop the auto-sync scheduler"""
    from server import db
    from modules.sync_scheduler import get_sync_scheduler
    
    scheduler = get_sync_scheduler(db)
    
    if not scheduler.running:
        return {"ok": True, "message": "Scheduler not running"}
    
    await scheduler.stop()
    return {"ok": True, "message": "Scheduler stopped"}
