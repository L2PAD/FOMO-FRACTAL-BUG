"""
Unlock API Routes
Layer 2: Token Unlocks
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Optional, List
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/unlocks", tags=["unlocks"])


def get_unlock_service():
    """Dependency to get unlock service"""
    from server import db
    from ..services.unlock_service import UnlockService
    return UnlockService(db)


# ═══════════════════════════════════════════════════════════════
# PROJECTS
# ═══════════════════════════════════════════════════════════════

@router.get("/projects")
async def list_projects(
    search: Optional[str] = Query(None, description="Search by name or symbol"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    service = Depends(get_unlock_service)
):
    """List all projects with unlock data"""
    projects = await service.list_projects(limit=limit, offset=offset, search=search)
    total = await service.count_projects()
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "total": total,
        "limit": limit,
        "offset": offset,
        "projects": projects
    }


@router.get("/projects/{project_id}")
async def get_project(
    project_id: str,
    service = Depends(get_unlock_service)
):
    """Get project details"""
    project = await service.get_project(project_id)
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "project": project
    }


@router.get("/projects/{project_id}/summary")
async def get_project_summary(
    project_id: str,
    service = Depends(get_unlock_service)
):
    """Get unlock summary for a project"""
    summary = await service.get_project_summary(project_id)
    
    if not summary:
        raise HTTPException(status_code=404, detail="Project not found")
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        **summary
    }


@router.get("/projects/{project_id}/unlocks")
async def get_project_unlocks(
    project_id: str,
    include_past: bool = Query(False, description="Include past unlocks"),
    limit: int = Query(50, ge=1, le=200),
    service = Depends(get_unlock_service)
):
    """Get all unlocks for a specific project"""
    # Check project exists
    project = await service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    unlocks = await service.get_project_unlocks(
        project_id=project_id,
        include_past=include_past,
        limit=limit
    )
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "project_id": project_id,
        "project_symbol": project.get('symbol'),
        "count": len(unlocks),
        "unlocks": unlocks
    }


# ═══════════════════════════════════════════════════════════════
# UNLOCKS
# ═══════════════════════════════════════════════════════════════

@router.get("")
async def list_unlocks(
    project_id: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    from_date: Optional[str] = Query(None, description="ISO date string"),
    to_date: Optional[str] = Query(None, description="ISO date string"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    service = Depends(get_unlock_service)
):
    """List all token unlocks with filters"""
    # Parse dates
    from_dt = datetime.fromisoformat(from_date) if from_date else None
    to_dt = datetime.fromisoformat(to_date) if to_date else None
    
    unlocks = await service.list_unlocks(
        project_id=project_id,
        category=category,
        from_date=from_dt,
        to_date=to_dt,
        limit=limit,
        offset=offset
    )
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "count": len(unlocks),
        "limit": limit,
        "offset": offset,
        "unlocks": unlocks
    }


@router.get("/upcoming")
async def get_upcoming_unlocks(
    days: int = Query(30, ge=1, le=180, description="Days ahead"),
    min_value_usd: Optional[float] = Query(None, description="Minimum USD value"),
    min_percent: Optional[float] = Query(None, description="Minimum % of supply"),
    limit: int = Query(50, ge=1, le=200),
    service = Depends(get_unlock_service)
):
    """Get upcoming token unlocks"""
    unlocks = await service.get_upcoming_unlocks(
        days=days,
        min_value_usd=min_value_usd,
        min_percent=min_percent,
        limit=limit
    )
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "days": days,
        "count": len(unlocks),
        "unlocks": unlocks
    }


@router.get("/calendar")
async def get_unlock_calendar(
    year: int = Query(None, description="Year filter"),
    month: int = Query(None, ge=1, le=12, description="Month filter"),
    min_percent: Optional[float] = Query(None, description="Minimum % of supply"),
    service = Depends(get_unlock_service)
):
    """
    Get unlock calendar view grouped by date.
    Returns unlocks organized by date for calendar display.
    """
    from datetime import datetime, timezone, timedelta
    from collections import defaultdict
    from server import db
    
    now = datetime.now(timezone.utc)
    
    # Default to current year/month if not specified
    target_year = year or now.year
    target_month = month or now.month
    
    # Calculate date range for the month
    start_date = datetime(target_year, target_month, 1, tzinfo=timezone.utc)
    if target_month == 12:
        end_date = datetime(target_year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end_date = datetime(target_year, target_month + 1, 1, tzinfo=timezone.utc)
    
    # Query directly to handle both 'date' and 'unlock_date' fields
    query = {
        "$or": [
            {"date": {"$gte": start_date.isoformat(), "$lt": end_date.isoformat()}},
            {"unlock_date": {"$gte": start_date, "$lt": end_date}}
        ]
    }
    
    cursor = db.token_unlocks.find(query)
    unlocks = await cursor.to_list(500)
    
    # Filter by min_percent if specified
    if min_percent:
        unlocks = [u for u in unlocks if (u.get("percent_supply") or u.get("unlock_percent") or 0) >= min_percent]
    
    # Group by date
    calendar = defaultdict(list)
    for unlock in unlocks:
        # Handle both date formats
        date_str = unlock.get("date") or unlock.get("unlock_date")
        if date_str:
            # Extract date part only
            if isinstance(date_str, str):
                date_key = date_str[:10]
            else:
                date_key = date_str.strftime("%Y-%m-%d") if hasattr(date_str, 'strftime') else str(date_str)[:10]
            
            calendar[date_key].append({
                "project": unlock.get("project_name") or unlock.get("project_id"),
                "symbol": unlock.get("symbol"),
                "category": unlock.get("category"),
                "amount_tokens": unlock.get("amount_tokens") or unlock.get("unlock_amount"),
                "amount_usd": unlock.get("amount_usd") or unlock.get("unlock_value_usd"),
                "percent_supply": unlock.get("percent_supply") or unlock.get("unlock_percent")
            })
    
    # Convert to sorted list
    calendar_items = [
        {
            "date": date,
            "unlock_count": len(items),
            "total_value_usd": sum(i.get("amount_usd") or 0 for i in items),
            "unlocks": items
        }
        for date, items in sorted(calendar.items())
    ]
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "year": target_year,
        "month": target_month,
        "days_with_unlocks": len(calendar_items),
        "total_unlocks": len(unlocks),
        "calendar": calendar_items
    }




@router.get("/{unlock_id}")
async def get_unlock(
    unlock_id: str,
    service = Depends(get_unlock_service)
):
    """Get specific unlock by ID"""
    unlock = await service.get_unlock(unlock_id)
    
    if not unlock:
        raise HTTPException(status_code=404, detail="Unlock not found")
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "unlock": unlock
    }


# ═══════════════════════════════════════════════════════════════
# SYNC & STATS
# ═══════════════════════════════════════════════════════════════

@router.post("/sync")
async def sync_unlocks(
    source: str = Query("dropstab", description="Data source"),
    service = Depends(get_unlock_service)
):
    """Manually trigger unlock data sync"""
    from ..scraper.dropstab import dropstab_scraper
    
    try:
        if source == "dropstab":
            result = await dropstab_scraper.sync_all()
            
            # Save projects
            for project in result['projects']:
                await service.create_project(project)
            
            # Save unlocks
            count = await service.bulk_upsert_unlocks(result['unlocks'])
            
            return {
                "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
                "source": source,
                "success": True,
                "projects_synced": len(result['projects']),
                "unlocks_synced": count,
                "raw_fetched": result['raw_count']
            }
        else:
            raise HTTPException(status_code=400, detail=f"Unknown source: {source}")
            
    except Exception as e:
        logger.error(f"[Unlock Sync] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/overview")
async def get_stats(
    service = Depends(get_unlock_service)
):
    """Get unlock statistics"""
    stats = await service.stats()
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        **stats
    }
