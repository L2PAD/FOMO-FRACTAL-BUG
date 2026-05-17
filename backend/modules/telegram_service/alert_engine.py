"""
Alert Engine
============

Центральный движок алертов:
- Принимает события из системы
- Проверяет cooldown (deduplication)
- Записывает в alert_events
- Отправляет в notification_queue

Архитектура:
System Event → Alert Engine → Alert Events → Notification Queue → Telegram Worker
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List
from motor.motor_asyncio import AsyncIOMotorDatabase
import hashlib

from .alert_templates_ru import (
    ALERT_TEMPLATES, 
    get_alert_severity, 
    get_alert_cooldown,
    get_alert_category,
    AlertSeverity
)

logger = logging.getLogger(__name__)


class AlertEngine:
    """
    Central alert processing engine.
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.alert_events = db.alert_events
        self.notification_queue = db.notification_queue
        self.alert_cooldowns = db.alert_cooldowns
        self.alert_settings = db.alert_settings
    
    async def ensure_indexes(self):
        """Create indexes for alert collections"""
        await self.alert_events.create_index("alert_id", unique=True)
        await self.alert_events.create_index("alert_code")
        await self.alert_events.create_index("severity")
        await self.alert_events.create_index("status")
        await self.alert_events.create_index("created_at")
        
        await self.notification_queue.create_index("notification_id", unique=True)
        await self.notification_queue.create_index("status")
        await self.notification_queue.create_index("next_retry")
        await self.notification_queue.create_index("created_at")
        
        await self.alert_cooldowns.create_index("alert_key", unique=True)
        await self.alert_cooldowns.create_index("expires_at")
        
        logger.info("[AlertEngine] Indexes created")
    
    async def emit_alert(
        self,
        alert_code: str,
        data: Dict[str, Any],
        entity: str = None,
        force: bool = False
    ) -> Optional[str]:
        """
        Emit a new alert event.
        
        Args:
            alert_code: Alert type code (e.g., "source_down")
            data: Template data (e.g., {"source": "CryptoRank"})
            entity: Entity identifier for dedup (e.g., "cryptorank")
            force: Skip cooldown check
        
        Returns:
            alert_id if created, None if skipped (cooldown)
        """
        now = datetime.now(timezone.utc)
        
        # Get template info
        if alert_code not in ALERT_TEMPLATES:
            logger.warning(f"[AlertEngine] Unknown alert_code: {alert_code}")
            return None
        
        severity = get_alert_severity(alert_code)
        cooldown_minutes = get_alert_cooldown(alert_code)
        category = get_alert_category(alert_code)
        
        # Build alert key for dedup
        alert_key = f"{alert_code}:{entity or 'global'}"
        
        # Check cooldown
        if not force:
            is_in_cooldown = await self._check_cooldown(alert_key)
            if is_in_cooldown:
                logger.debug(f"[AlertEngine] Alert {alert_key} in cooldown, skipping")
                return None
        
        # Generate alert ID
        alert_id = f"alert_{alert_code}_{now.strftime('%Y%m%d%H%M%S%f')}"
        
        # Create alert event
        alert_event = {
            "alert_id": alert_id,
            "alert_code": alert_code,
            "alert_key": alert_key,
            "severity": severity,
            "category": category,
            "entity": entity,
            "data": data,
            "status": "new",
            "created_at": now
        }
        
        await self.alert_events.insert_one(alert_event)
        
        # Set cooldown
        await self._set_cooldown(alert_key, cooldown_minutes)
        
        # Add to notification queue
        await self._enqueue_notification(alert_id, alert_code, severity)
        
        logger.info(f"[AlertEngine] Alert emitted: {alert_code} ({entity or 'global'})")
        
        return alert_id
    
    async def _check_cooldown(self, alert_key: str) -> bool:
        """Check if alert is in cooldown period"""
        now = datetime.now(timezone.utc)
        
        cooldown = await self.alert_cooldowns.find_one({
            "alert_key": alert_key,
            "expires_at": {"$gt": now}
        })
        
        return cooldown is not None
    
    async def _set_cooldown(self, alert_key: str, minutes: int):
        """Set cooldown for alert key"""
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=minutes)
        
        await self.alert_cooldowns.update_one(
            {"alert_key": alert_key},
            {
                "$set": {
                    "alert_key": alert_key,
                    "expires_at": expires_at,
                    "updated_at": now
                }
            },
            upsert=True
        )
    
    async def _enqueue_notification(
        self,
        alert_id: str,
        alert_code: str,
        severity: str
    ):
        """Add alert to notification queue"""
        now = datetime.now(timezone.utc)
        notification_id = f"notif_{alert_id}"
        
        notification = {
            "notification_id": notification_id,
            "alert_id": alert_id,
            "alert_code": alert_code,
            "severity": severity,
            "channel": "telegram",
            "status": "pending",
            "attempts": 0,
            "max_attempts": 5,
            "next_retry": now,
            "created_at": now
        }
        
        await self.notification_queue.insert_one(notification)
    
    async def get_pending_notifications(
        self,
        limit: int = 50
    ) -> List[Dict]:
        """Get pending notifications for processing"""
        now = datetime.now(timezone.utc)
        
        cursor = self.notification_queue.find(
            {
                "status": {"$in": ["pending", "retry"]},
                "next_retry": {"$lte": now}
            },
            {"_id": 0}
        ).sort("created_at", 1).limit(limit)
        
        return await cursor.to_list(length=limit)
    
    async def mark_notification_sent(self, notification_id: str):
        """Mark notification as sent"""
        now = datetime.now(timezone.utc)
        
        await self.notification_queue.update_one(
            {"notification_id": notification_id},
            {
                "$set": {
                    "status": "sent",
                    "sent_at": now
                }
            }
        )
    
    async def mark_notification_failed(
        self,
        notification_id: str,
        error: str
    ):
        """Mark notification as failed, schedule retry"""
        now = datetime.now(timezone.utc)
        
        notification = await self.notification_queue.find_one({
            "notification_id": notification_id
        })
        
        if not notification:
            return
        
        attempts = notification.get("attempts", 0) + 1
        max_attempts = notification.get("max_attempts", 5)
        
        if attempts >= max_attempts:
            # Max retries reached
            await self.notification_queue.update_one(
                {"notification_id": notification_id},
                {
                    "$set": {
                        "status": "failed",
                        "last_error": error,
                        "failed_at": now
                    },
                    "$inc": {"attempts": 1}
                }
            )
        else:
            # Schedule retry (exponential backoff)
            retry_delay = min(30 * (2 ** attempts), 600)  # Max 10 min
            next_retry = now + timedelta(seconds=retry_delay)
            
            await self.notification_queue.update_one(
                {"notification_id": notification_id},
                {
                    "$set": {
                        "status": "retry",
                        "next_retry": next_retry,
                        "last_error": error
                    },
                    "$inc": {"attempts": 1}
                }
            )
    
    async def get_alert_event(self, alert_id: str) -> Optional[Dict]:
        """Get alert event by ID"""
        return await self.alert_events.find_one(
            {"alert_id": alert_id},
            {"_id": 0}
        )
    
    async def get_recent_alerts(
        self,
        severity: str = None,
        category: str = None,
        limit: int = 50
    ) -> List[Dict]:
        """Get recent alerts"""
        query = {}
        if severity:
            query["severity"] = severity
        if category:
            query["category"] = category
        
        cursor = self.alert_events.find(
            query,
            {"_id": 0}
        ).sort("created_at", -1).limit(limit)
        
        return await cursor.to_list(length=limit)
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get alert engine statistics"""
        now = datetime.now(timezone.utc)
        day_ago = now - timedelta(days=1)
        
        total = await self.alert_events.count_documents({})
        today = await self.alert_events.count_documents({
            "created_at": {"$gte": day_ago}
        })
        
        # By severity
        pipeline = [
            {"$match": {"created_at": {"$gte": day_ago}}},
            {"$group": {
                "_id": "$severity",
                "count": {"$sum": 1}
            }}
        ]
        severity_stats = await self.alert_events.aggregate(pipeline).to_list(10)
        
        # Queue stats
        queue_pending = await self.notification_queue.count_documents({
            "status": {"$in": ["pending", "retry"]}
        })
        queue_sent = await self.notification_queue.count_documents({
            "status": "sent"
        })
        queue_failed = await self.notification_queue.count_documents({
            "status": "failed"
        })
        
        return {
            "total_alerts": total,
            "alerts_24h": today,
            "by_severity_24h": {s["_id"]: s["count"] for s in severity_stats},
            "queue": {
                "pending": queue_pending,
                "sent": queue_sent,
                "failed": queue_failed
            }
        }
    
    async def cleanup_old_alerts(self, days: int = 30) -> int:
        """Remove old alerts"""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        
        result = await self.alert_events.delete_many({
            "created_at": {"$lt": cutoff}
        })
        
        # Also clean notification queue
        await self.notification_queue.delete_many({
            "status": {"$in": ["sent", "failed"]},
            "created_at": {"$lt": cutoff}
        })
        
        return result.deleted_count


# Singleton
_alert_engine: Optional[AlertEngine] = None


def get_alert_engine(db: AsyncIOMotorDatabase = None) -> AlertEngine:
    """Get or create alert engine instance"""
    global _alert_engine
    if db is not None:
        _alert_engine = AlertEngine(db)
    return _alert_engine
