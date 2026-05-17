"""
Scheduler API Routes
====================
API endpoints for managing the data sync scheduler.
"""

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from typing import Optional
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/scheduler", tags=["Scheduler"])


def ts_now():
    return int(datetime.now(timezone.utc).timestamp() * 1000)


@router.get("/status")
async def get_scheduler_status():
    """Get scheduler status and all jobs"""
    from server import db
    from modules.scheduler.data_sync_scheduler import get_scheduler
    
    scheduler = get_scheduler(db)
    status = scheduler.get_status()
    
    return {
        "ts": ts_now(),
        **status
    }


@router.post("/start")
async def start_scheduler():
    """Start the scheduler"""
    from server import db
    from modules.scheduler.data_sync_scheduler import init_scheduler
    
    scheduler = init_scheduler(db, auto_start=True)
    
    return {
        "ts": ts_now(),
        "ok": True,
        "message": "Scheduler started",
        "status": scheduler.get_status()
    }


@router.post("/stop")
async def stop_scheduler():
    """Stop the scheduler"""
    from server import db
    from modules.scheduler.data_sync_scheduler import get_scheduler
    
    scheduler = get_scheduler(db)
    scheduler.stop()
    
    return {
        "ts": ts_now(),
        "ok": True,
        "message": "Scheduler stopped"
    }


@router.post("/jobs/{job_id}/run")
async def run_job_now(job_id: str, background_tasks: BackgroundTasks):
    """Trigger a job to run immediately"""
    from server import db
    from modules.scheduler.data_sync_scheduler import get_scheduler
    
    scheduler = get_scheduler(db)
    
    # Find job
    status = scheduler.get_status()
    job_exists = any(j["id"] == job_id for j in status["jobs"])
    
    if not job_exists:
        raise HTTPException(404, f"Job {job_id} not found")
    
    scheduler.run_job_now(job_id)
    
    return {
        "ts": ts_now(),
        "ok": True,
        "message": f"Job {job_id} triggered"
    }


@router.post("/jobs/{job_id}/pause")
async def pause_job(job_id: str):
    """Pause a scheduled job"""
    from server import db
    from modules.scheduler.data_sync_scheduler import get_scheduler
    
    scheduler = get_scheduler(db)
    scheduler.pause_job(job_id)
    
    return {
        "ts": ts_now(),
        "ok": True,
        "message": f"Job {job_id} paused"
    }


@router.post("/jobs/{job_id}/resume")
async def resume_job(job_id: str):
    """Resume a paused job"""
    from server import db
    from modules.scheduler.data_sync_scheduler import get_scheduler
    
    scheduler = get_scheduler(db)
    scheduler.resume_job(job_id)
    
    return {
        "ts": ts_now(),
        "ok": True,
        "message": f"Job {job_id} resumed"
    }


# ═══════════════════════════════════════════════════════════════
# HEALTH MONITORING ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@router.get("/health")
async def get_sources_health():
    """Get health status for all data sources"""
    from server import db
    from modules.scheduler.data_sync_scheduler import get_scheduler
    
    scheduler = get_scheduler(db)
    
    try:
        health = scheduler.get_health_status()
    except AttributeError:
        health = {}
    
    return {
        "ts": ts_now(),
        "sources": health
    }


@router.get("/health/{source_id}")
async def get_source_health(source_id: str):
    """Get health status for specific source"""
    from server import db
    from modules.scheduler.data_sync_scheduler import get_scheduler
    
    scheduler = get_scheduler(db)
    
    try:
        health = scheduler.get_health_status()
        if source_id not in health:
            return {"ts": ts_now(), "error": f"Source {source_id} not found"}
        return {"ts": ts_now(), **health[source_id]}
    except AttributeError:
        return {"ts": ts_now(), "error": "Health monitoring not available"}


@router.post("/health/{source_id}/pause")
async def pause_source(source_id: str, minutes: int = Query(60, ge=1, le=1440)):
    """Manually pause a source for specified minutes"""
    from server import db
    from modules.scheduler.data_sync_scheduler import get_scheduler
    
    scheduler = get_scheduler(db)
    
    try:
        scheduler.pause_source(source_id, minutes)
        return {
            "ts": ts_now(),
            "ok": True,
            "message": f"Source {source_id} paused for {minutes} minutes"
        }
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/health/{source_id}/unpause")
async def unpause_source(source_id: str):
    """Manually unpause a source"""
    from server import db
    from modules.scheduler.data_sync_scheduler import get_scheduler
    
    scheduler = get_scheduler(db)
    
    try:
        scheduler.unpause_source(source_id)
        return {
            "ts": ts_now(),
            "ok": True,
            "message": f"Source {source_id} unpaused"
        }
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/tiers")
async def get_tier_status():
    """Get tier execution status"""
    from server import db
    from modules.scheduler.data_sync_scheduler import get_scheduler
    
    scheduler = get_scheduler(db)
    status = scheduler.get_status()
    
    return {
        "ts": ts_now(),
        "tier_intervals": status.get("tier_intervals", {}),
        "last_tier_runs": status.get("last_tier_runs", {}),
        "jobs_by_tier": {
            tier: [j for j in status.get("jobs", []) if j.get("tier") == tier]
            for tier in [1, 2, 3, 4]
        }
    }


# ═══════════════════════════════════════════════════════════════
# MANUAL SYNC TRIGGERS (enhanced from routes_sync)
# ═══════════════════════════════════════════════════════════════

@router.post("/sync/defillama")
async def sync_defillama(background_tasks: BackgroundTasks):
    """Sync DefiLlama protocols and TVL data"""
    from server import db
    from modules.parsers.parser_defillama import sync_defillama_data
    
    background_tasks.add_task(sync_defillama_data, db, 100)
    
    return {
        "ts": ts_now(),
        "ok": True,
        "message": "DefiLlama sync started"
    }


@router.post("/sync/tokenunlocks")
async def sync_tokenunlocks(background_tasks: BackgroundTasks):
    """Sync token unlock schedules"""
    from server import db
    from modules.parsers.parser_tokenunlocks import sync_tokenunlocks_data
    
    background_tasks.add_task(sync_tokenunlocks_data, db, 90)
    
    return {
        "ts": ts_now(),
        "ok": True,
        "message": "TokenUnlocks sync started"
    }


@router.post("/sync/messari")
async def sync_messari(background_tasks: BackgroundTasks):
    """Sync Messari asset metrics"""
    from server import db
    from modules.parsers.parser_messari import sync_messari_data
    
    background_tasks.add_task(sync_messari_data, db, 50)
    
    return {
        "ts": ts_now(),
        "ok": True,
        "message": "Messari sync started"
    }


@router.post("/sync/all-new")
async def sync_all_new_sources(background_tasks: BackgroundTasks):
    """Sync all new data sources (DefiLlama, TokenUnlocks, Messari)"""
    from server import db
    from modules.parsers.parser_defillama import sync_defillama_data
    from modules.parsers.parser_tokenunlocks import sync_tokenunlocks_data
    from modules.parsers.parser_messari import sync_messari_data
    
    async def run_all():
        try:
            await sync_defillama_data(db, 100)
            await sync_tokenunlocks_data(db, 90)
            await sync_messari_data(db, 50)
            logger.info("All new sources sync complete")
        except Exception as e:
            logger.error(f"Sync all new error: {e}")
    
    background_tasks.add_task(run_all)
    
    return {
        "ts": ts_now(),
        "ok": True,
        "message": "All new sources sync started",
        "sources": ["defillama", "tokenunlocks", "messari"]
    }


# ═══════════════════════════════════════════════════════════════
# GITHUB DEVELOPER ACTIVITY ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@router.post("/sync/github")
async def sync_github(background_tasks: BackgroundTasks):
    """Sync GitHub developer activity data"""
    from server import db
    from modules.parsers.parser_github import sync_github_data
    
    background_tasks.add_task(sync_github_data, db, 5)
    
    return {
        "ts": ts_now(),
        "ok": True,
        "message": "GitHub sync started"
    }


@router.get("/github/summary")
async def get_github_summary_endpoint():
    """Get GitHub data summary"""
    from server import db
    from modules.parsers.parser_github import get_github_summary
    
    summary = await get_github_summary(db)
    
    return {
        "ts": ts_now(),
        **summary
    }


@router.get("/github/projects")
async def get_github_projects():
    """Get all projects with GitHub data"""
    from server import db
    from modules.parsers.parser_github import GitHubParser
    
    parser = GitHubParser(db)
    projects = await parser.get_all_github_data()
    await parser.close()
    
    return {
        "ts": ts_now(),
        "count": len(projects),
        "projects": projects
    }


@router.get("/github/projects/{project_key}")
async def get_github_project(project_key: str):
    """Get GitHub data for specific project"""
    from server import db
    from modules.parsers.parser_github import GitHubParser
    
    parser = GitHubParser(db)
    data = await parser.get_project_github_data(project_key)
    await parser.close()
    
    if not data:
        raise HTTPException(404, f"Project {project_key} not found")
    
    return {
        "ts": ts_now(),
        **data
    }


@router.post("/github/sync/{owner}/{repo}")
async def sync_single_github_repo(
    owner: str, 
    repo: str, 
    project: str = Query(None, description="Project name"),
    background_tasks: BackgroundTasks = None
):
    """Sync a single GitHub repository"""
    from server import db
    from modules.parsers.parser_github import GitHubParser
    
    parser = GitHubParser(db)
    
    try:
        result = await parser.sync_single_repo(owner, repo, project)
        return {
            "ts": ts_now(),
            **result
        }
    finally:
        await parser.close()



# ═══════════════════════════════════════════════════════════════
# DISCOVERY SCHEDULER ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@router.get("/discovery/status")
async def get_discovery_scheduler_status():
    """Get auto-discovery scheduler status"""
    from server import db
    from modules.scheduler.discovery_scheduler import get_discovery_scheduler
    
    scheduler = get_discovery_scheduler(db)
    return scheduler.get_status()


@router.post("/discovery/start")
async def start_discovery_scheduler():
    """Start the auto-discovery scheduler (runs every 60 minutes)"""
    from server import db
    from modules.scheduler.discovery_scheduler import get_discovery_scheduler
    
    scheduler = get_discovery_scheduler(db)
    result = scheduler.start()
    
    return {
        "ts": ts_now(),
        "ok": True,
        **result
    }


@router.post("/discovery/stop")
async def stop_discovery_scheduler():
    """Stop the auto-discovery scheduler"""
    from server import db
    from modules.scheduler.discovery_scheduler import get_discovery_scheduler
    
    scheduler = get_discovery_scheduler(db)
    result = scheduler.stop()
    
    return {
        "ts": ts_now(),
        "ok": True,
        **result
    }


@router.post("/discovery/run-now")
async def run_discovery_now(background_tasks: BackgroundTasks):
    """Trigger discovery immediately (runs in background)"""
    from server import db
    from modules.scheduler.discovery_scheduler import get_discovery_scheduler
    
    scheduler = get_discovery_scheduler(db)
    
    async def run():
        await scheduler.run_now()
    
    background_tasks.add_task(run)
    
    return {
        "ts": ts_now(),
        "ok": True,
        "message": "Discovery started in background"
    }



# ═══════════════════════════════════════════════════════════════
# EXCHANGE TREE SCHEDULER ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@router.get("/exchange/status")
async def get_exchange_scheduler_status():
    """Get Exchange Tree scheduler status"""
    from server import db
    from modules.scheduler.exchange_scheduler import get_exchange_scheduler
    
    scheduler = get_exchange_scheduler(db)
    
    return {
        "ts": ts_now(),
        **scheduler.get_status()
    }


@router.post("/exchange/start")
async def start_exchange_scheduler():
    """Start Exchange Tree scheduler"""
    from server import db
    from modules.scheduler.exchange_scheduler import init_exchange_scheduler
    
    scheduler = init_exchange_scheduler(db, auto_start=True)
    
    return {
        "ts": ts_now(),
        "ok": True,
        "message": "Exchange scheduler started"
    }


@router.post("/exchange/stop")
async def stop_exchange_scheduler():
    """Stop Exchange Tree scheduler"""
    from server import db
    from modules.scheduler.exchange_scheduler import get_exchange_scheduler
    
    scheduler = get_exchange_scheduler(db)
    scheduler.stop()
    
    return {
        "ts": ts_now(),
        "ok": True,
        "message": "Exchange scheduler stopped"
    }


@router.post("/exchange/{exchange_id}/pause")
async def pause_exchange(exchange_id: str):
    """Pause specific exchange"""
    from server import db
    from modules.scheduler.exchange_scheduler import get_exchange_scheduler
    
    scheduler = get_exchange_scheduler(db)
    scheduler.pause_exchange(exchange_id)
    
    return {
        "ts": ts_now(),
        "ok": True,
        "message": f"Exchange {exchange_id} paused"
    }


@router.post("/exchange/{exchange_id}/unpause")
async def unpause_exchange(exchange_id: str):
    """Unpause specific exchange"""
    from server import db
    from modules.scheduler.exchange_scheduler import get_exchange_scheduler
    
    scheduler = get_exchange_scheduler(db)
    scheduler.unpause_exchange(exchange_id)
    
    return {
        "ts": ts_now(),
        "ok": True,
        "message": f"Exchange {exchange_id} unpaused"
    }


# ═══════════════════════════════════════════════════════════════
# HEALTH ALERTS ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@router.get("/alerts")
async def get_health_alerts(
    tree: Optional[str] = Query(None, description="Filter by tree: intel or exchange"),
    active_only: bool = Query(True, description="Show only active alerts")
):
    """Get health alerts"""
    from server import db
    from modules.scheduler.health_alerts import get_alert_manager
    
    manager = get_alert_manager(db)
    
    if active_only:
        alerts = await manager.get_active_alerts(tree)
    else:
        alerts = await manager.get_recent_alerts(hours=24)
    
    return {
        "ts": ts_now(),
        "alerts": alerts,
        "stats": await manager.get_alert_stats()
    }


@router.get("/alerts/stats")
async def get_alert_stats():
    """Get alert statistics"""
    from server import db
    from modules.scheduler.health_alerts import get_alert_manager
    
    manager = get_alert_manager(db)
    
    return {
        "ts": ts_now(),
        **await manager.get_alert_stats()
    }


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str):
    """Acknowledge an alert"""
    from server import db
    from modules.scheduler.health_alerts import get_alert_manager
    
    manager = get_alert_manager(db)
    await manager.acknowledge_alert(alert_id)
    
    return {
        "ts": ts_now(),
        "ok": True,
        "message": f"Alert {alert_id} acknowledged"
    }


@router.post("/alerts/check")
async def run_health_check(background_tasks: BackgroundTasks):
    """Run health check and generate alerts"""
    from server import db
    from modules.scheduler.health_alerts import get_alert_manager
    from modules.scheduler.data_sync_scheduler import get_scheduler
    from modules.scheduler.exchange_scheduler import get_exchange_scheduler
    
    manager = get_alert_manager(db)
    
    async def check():
        # Check Intel Tree sources
        intel_scheduler = get_scheduler(db)
        intel_health = intel_scheduler.get_health_status()
        
        for source_id, health in intel_health.items():
            await manager.check_intel_source(source_id, health)
        
        # Check Exchange Tree
        try:
            exchange_scheduler = get_exchange_scheduler(db)
            exchange_status = exchange_scheduler.get_status()
            
            for exchange_id, health in exchange_status.get("health", {}).items():
                await manager.check_exchange(exchange_id, health)
        except:
            pass
    
    background_tasks.add_task(check)
    
    return {
        "ts": ts_now(),
        "ok": True,
        "message": "Health check started"
    }
