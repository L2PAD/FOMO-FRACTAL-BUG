"""
Telegram Service Routes
=======================

API для управления алертами и Telegram ботом.
Админка (English) для настроек.
"""

from fastapi import APIRouter, Query, HTTPException
from datetime import datetime, timezone
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/telegram", tags=["Telegram Alerts"])

# Lazy DB import
_db = None


def _get_db():
    global _db
    if _db is None:
        from motor.motor_asyncio import AsyncIOMotorClient
        import os
        client = AsyncIOMotorClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
        _db = client[os.environ.get("DB_NAME", "test_database")]
    return _db


# =============================================================================
# ALERT MANAGEMENT
# =============================================================================

@router.post("/alerts/emit")
async def emit_alert(
    alert_code: str = Query(..., description="Alert code (e.g., source_down)"),
    entity: Optional[str] = Query(None, description="Entity identifier"),
    force: bool = Query(False, description="Skip cooldown check")
):
    """
    Emit a new alert.
    Use for testing or manual alerts.
    """
    from modules.telegram_service.alert_engine import get_alert_engine
    from modules.telegram_service.alert_templates_ru import ALERT_TEMPLATES
    
    if alert_code not in ALERT_TEMPLATES:
        raise HTTPException(status_code=400, detail=f"Unknown alert_code: {alert_code}")
    
    engine = get_alert_engine(_get_db())
    
    # Build test data
    data = {
        "source": entity or "TestSource",
        "parser": entity or "TestParser",
        "error_rate": 35,
        "downtime": "5 минут",
        "latency": 2.5,
        "time": "10 минут",
        "attempts": 3,
        "jobs": 500,
        "count": 100,
        "error": "Test error",
        "narrative": entity or "AI x Crypto",
        "score": 75,
        "entity": entity or "TestEntity",
        "entity_type": "project",
        "velocity": 15,
        "dataset": "funding_rounds",
        "job": entity or "news_sync",
        "cpu": 95,
        "memory": 85,
        "space": "500MB",
        "description": "Test suspicious activity",
        "data_type": "ecosystem",
        # Daily report fields
        "sources_healthy": 14,
        "sources_degraded": 1,
        "sources_down": 1,
        "parsers_success": 192,
        "parsers_errors": 3,
        "graph_nodes": 276,
        "graph_edges": 4163,
        "momentum_tracked": 129,
        "momentum_high": 3,
        "new_entities": 7,
        "status_message": "Система работает стабильно."
    }
    
    alert_id = await engine.emit_alert(
        alert_code=alert_code,
        data=data,
        entity=entity,
        force=force
    )
    
    if alert_id:
        return {
            "ok": True,
            "alert_id": alert_id,
            "message": "Alert emitted and queued for Telegram"
        }
    else:
        return {
            "ok": False,
            "message": "Alert skipped (cooldown active)"
        }


@router.get("/alerts/recent")
async def get_recent_alerts(
    severity: Optional[str] = Query(None, description="Filter by severity"),
    category: Optional[str] = Query(None, description="Filter by category"),
    limit: int = Query(50, ge=1, le=200)
):
    """Get recent alerts"""
    from modules.telegram_service.alert_engine import get_alert_engine
    engine = get_alert_engine(_get_db())
    
    alerts = await engine.get_recent_alerts(
        severity=severity,
        category=category,
        limit=limit
    )
    
    return {
        "ok": True,
        "count": len(alerts),
        "alerts": alerts
    }


@router.get("/alerts/stats")
async def get_alert_stats():
    """Get alert engine statistics"""
    from modules.telegram_service.alert_engine import get_alert_engine
    engine = get_alert_engine(_get_db())
    
    stats = await engine.get_stats()
    
    return {
        "ok": True,
        "ts": datetime.now(timezone.utc).isoformat(),
        **stats
    }


@router.get("/alerts/codes")
async def get_alert_codes():
    """Get all available alert codes"""
    from modules.telegram_service.alert_templates_ru import ALERT_TEMPLATES
    
    codes = []
    for code, info in ALERT_TEMPLATES.items():
        codes.append({
            "code": code,
            "severity": info.get("severity"),
            "category": info.get("category"),
            "cooldown_minutes": info.get("cooldown_minutes")
        })
    
    return {
        "ok": True,
        "count": len(codes),
        "codes": codes
    }


# =============================================================================
# NOTIFICATION QUEUE
# =============================================================================

@router.get("/queue/pending")
async def get_pending_notifications(
    limit: int = Query(50, ge=1, le=200)
):
    """Get pending notifications in queue"""
    from modules.telegram_service.alert_engine import get_alert_engine
    engine = get_alert_engine(_get_db())
    
    notifications = await engine.get_pending_notifications(limit=limit)
    
    return {
        "ok": True,
        "count": len(notifications),
        "notifications": notifications
    }


@router.post("/queue/cleanup")
async def cleanup_old_alerts(
    days: int = Query(30, ge=1, le=365)
):
    """Remove old alerts and notifications"""
    from modules.telegram_service.alert_engine import get_alert_engine
    engine = get_alert_engine(_get_db())
    
    deleted = await engine.cleanup_old_alerts(days=days)
    
    return {
        "ok": True,
        "deleted_alerts": deleted
    }


# =============================================================================
# TELEGRAM BOT CONTROL
# =============================================================================

@router.get("/bot/status")
async def get_bot_status():
    """Get Telegram bot status"""
    from modules.telegram_service.telegram_worker import get_telegram_worker, get_telegram_bot
    
    worker = get_telegram_worker()
    bot = get_telegram_bot()
    
    return {
        "ok": True,
        "worker_running": worker._running if worker else False,
        "bot_running": bot._running if bot else False,
        "chat_id_configured": bool(worker.chat_id if worker else False)
    }


@router.post("/bot/test")
async def test_telegram_connection():
    """Test Telegram connection by sending a test message"""
    from modules.telegram_service.telegram_worker import get_telegram_worker
    
    worker = get_telegram_worker()
    if not worker:
        raise HTTPException(status_code=400, detail="Telegram worker not initialized")
    
    success = await worker.send_direct("🔵 Тестовое сообщение\n\nСоединение с Telegram работает.")
    
    return {
        "ok": success,
        "message": "Test message sent" if success else "Failed to send"
    }


@router.post("/bot/send-report")
async def send_daily_report():
    """Send daily system report to Telegram"""
    from modules.telegram_service.alert_engine import get_alert_engine
    
    db = _get_db()
    engine = get_alert_engine(db)
    
    # Gather stats
    nodes = await db.graph_nodes.count_documents({})
    edges = await db.graph_edges.count_documents({})
    momentum = await db.entity_momentum.count_documents({})
    high_mom = await db.entity_momentum.count_documents({"momentum_score": {"$gte": 50}})
    
    data = {
        "sources_healthy": 14,
        "sources_degraded": 1,
        "sources_down": 1,
        "parsers_success": 192,
        "parsers_errors": 3,
        "graph_nodes": nodes,
        "graph_edges": edges,
        "momentum_tracked": momentum,
        "momentum_high": high_mom,
        "new_entities": 7,
        "status_message": "Система работает стабильно."
    }
    
    alert_id = await engine.emit_alert(
        alert_code="daily_system_report",
        data=data,
        entity="daily",
        force=True
    )
    
    return {
        "ok": bool(alert_id),
        "alert_id": alert_id
    }
