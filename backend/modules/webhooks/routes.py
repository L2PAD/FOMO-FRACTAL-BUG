"""
Webhook Service Module
======================

Manages webhook subscriptions and event delivery.
"""

import logging
import asyncio
import httpx
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, HttpUrl
from fastapi import APIRouter, HTTPException
from enum import Enum

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhooks", tags=["Webhooks"])

# Database reference
_db = None

def set_database(db):
    global _db
    _db = db

def get_db():
    return _db


# ═══════════════════════════════════════════════════════════════
# MODELS
# ═══════════════════════════════════════════════════════════════

class WebhookEventType(str, Enum):
    FUNDING_ROUND = "funding.round"           # New funding round announced
    TOKEN_UNLOCK = "token.unlock"             # Token unlock event
    NEWS_BREAKING = "news.breaking"           # Breaking news event
    NEWS_IMPORTANT = "news.important"         # Important news (high score)
    PRICE_ALERT = "price.alert"               # Price threshold crossed
    SENTIMENT_SHIFT = "sentiment.shift"       # Major sentiment change
    PROJECT_NEW = "project.new"               # New project discovered
    INVESTOR_MOVE = "investor.move"           # Notable investor activity
    # New event types
    MARKET_PUMP = "market.pump"               # Rapid price increase (>5% in 1h)
    MARKET_DUMP = "market.dump"               # Rapid price decrease (>5% in 1h)
    WHALE_ALERT = "whale.alert"               # Large whale transaction detected
    LISTING_NEW = "listing.new"               # New token listing on exchange
    AIRDROP_ANNOUNCED = "airdrop.announced"   # Airdrop announcement
    HACK_DETECTED = "hack.detected"           # Security breach or exploit detected
    REGULATION_UPDATE = "regulation.update"   # Regulatory news or updates


class WebhookSubscription(BaseModel):
    url: HttpUrl
    events: List[WebhookEventType]
    name: Optional[str] = None
    secret: Optional[str] = None  # For HMAC signature verification
    enabled: bool = True
    # Filters for asset/project specific webhooks
    filters: Optional[Dict[str, Any]] = None  # e.g., {"assets": ["BTC", "ETH"], "projects": ["uniswap"]}


class WebhookEvent(BaseModel):
    event_type: WebhookEventType
    timestamp: str
    data: Dict[str, Any]


class DeliveryLog(BaseModel):
    """Detailed log of a webhook delivery attempt."""
    id: str
    subscription_id: str
    subscription_url: str
    event_type: str
    event_data: Dict[str, Any]
    attempt: int
    status: str  # "success", "failed", "pending"
    status_code: Optional[int] = None
    error: Optional[str] = None
    response_time_ms: Optional[int] = None
    created_at: str


# ═══════════════════════════════════════════════════════════════
# WEBHOOK MANAGER
# ═══════════════════════════════════════════════════════════════

class WebhookManager:
    """Manages webhook subscriptions and event delivery."""
    
    def __init__(self, db):
        self.db = db
        self.client = httpx.AsyncClient(timeout=10.0)
    
    async def create_subscription(self, sub: WebhookSubscription) -> Dict:
        """Create a new webhook subscription."""
        import uuid
        
        doc = {
            "id": f"wh_{uuid.uuid4().hex[:12]}",
            "url": str(sub.url),
            "events": [e.value for e in sub.events],
            "name": sub.name,
            "secret": sub.secret,
            "enabled": sub.enabled,
            "filters": sub.filters,  # Asset/project filters
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_triggered": None,
            "success_count": 0,
            "error_count": 0
        }
        
        await self.db.webhook_subscriptions.insert_one(doc)
        logger.info(f"[Webhooks] Created subscription: {doc['id']} -> {sub.url} (filters: {sub.filters})")
        
        return {"id": doc["id"], "url": str(sub.url), "events": doc["events"], "filters": doc["filters"]}
    
    async def list_subscriptions(self) -> List[Dict]:
        """List all webhook subscriptions."""
        subs = []
        async for doc in self.db.webhook_subscriptions.find({}, {"_id": 0}):
            subs.append(doc)
        return subs
    
    async def get_subscription(self, webhook_id: str) -> Optional[Dict]:
        """Get a single webhook subscription by ID."""
        doc = await self.db.webhook_subscriptions.find_one({"id": webhook_id}, {"_id": 0})
        return doc
    
    async def update_subscription(self, webhook_id: str, updates: Dict) -> bool:
        """Update a webhook subscription."""
        # Only allow updating specific fields
        allowed_fields = {"url", "events", "name", "secret", "enabled", "filters"}
        filtered_updates = {k: v for k, v in updates.items() if k in allowed_fields}
        
        if not filtered_updates:
            return False
        
        # Convert events to string values if they are enums
        if "events" in filtered_updates:
            filtered_updates["events"] = [
                e.value if hasattr(e, 'value') else e 
                for e in filtered_updates["events"]
            ]
        
        result = await self.db.webhook_subscriptions.update_one(
            {"id": webhook_id},
            {"$set": filtered_updates}
        )
        
        if result.modified_count > 0:
            logger.info(f"[Webhooks] Updated subscription: {webhook_id}")
            return True
        return False
    
    async def delete_subscription(self, webhook_id: str) -> bool:
        """Delete a webhook subscription."""
        result = await self.db.webhook_subscriptions.delete_one({"id": webhook_id})
        return result.deleted_count > 0
    
    async def trigger_event(self, event: WebhookEvent) -> Dict:
        """Trigger webhook event to all subscribed endpoints with retry support."""
        results = {"sent": 0, "failed": 0, "skipped": 0, "queued_for_retry": 0}
        
        # Find all subscriptions for this event type
        cursor = self.db.webhook_subscriptions.find({
            "enabled": True,
            "events": event.event_type.value
        })
        
        async for sub in cursor:
            # Check if subscription filters match the event
            if not self._matches_filters(sub, event):
                results["skipped"] += 1
                continue
                
            delivery_result = await self._deliver_webhook(sub, event)
            
            if delivery_result["success"]:
                results["sent"] += 1
            elif delivery_result.get("queued_for_retry"):
                results["queued_for_retry"] += 1
            else:
                results["failed"] += 1
        
        # Log event
        await self.db.webhook_events.insert_one({
            "event_type": event.event_type.value,
            "timestamp": event.timestamp,
            "data": event.data,
            "results": results,
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        
        return results
    
    def _matches_filters(self, subscription: Dict, event: WebhookEvent) -> bool:
        """Check if event matches subscription filters."""
        filters = subscription.get("filters")
        if not filters:
            return True  # No filters means accept all events
        
        event_data = event.data
        
        # Check if event matches any of the content filters (assets OR projects)
        content_filter_passed = True
        has_content_filters = "assets" in filters or "projects" in filters
        
        if has_content_filters:
            content_filter_passed = False  # Must be proven True
            
            # Check asset filters
            if "assets" in filters:
                allowed_assets = [asset.upper() for asset in filters["assets"]]
                
                # Look for asset references in event data
                event_assets = []
                asset_fields = ["asset", "token", "primary_assets", "assets"]
                for field in asset_fields:
                    if field in event_data:
                        value = event_data[field]
                        if isinstance(value, str):
                            event_assets.append(value.upper())
                        elif isinstance(value, list):
                            event_assets.extend([str(v).upper() for v in value])
                
                # If event has matching assets, pass the filter
                if event_assets and any(asset in allowed_assets for asset in event_assets):
                    content_filter_passed = True
            
            # Check project filters (OR with asset filters)
            if "projects" in filters and not content_filter_passed:
                allowed_projects = [proj.lower() for proj in filters["projects"]]
                
                # Look for project references in event data
                event_projects = []
                project_fields = ["project", "project_slug", "project_name"]
                for field in project_fields:
                    if field in event_data:
                        value = event_data[field]
                        if isinstance(value, str):
                            event_projects.append(value.lower())
                        elif isinstance(value, list):
                            event_projects.extend([str(v).lower() for v in value])
                
                # If event has matching projects, pass the filter
                if event_projects and any(proj in allowed_projects for proj in event_projects):
                    content_filter_passed = True
            
            # If no assets or projects found but it's a general event type, allow it
            if not content_filter_passed:
                event_assets = []
                event_projects = []
                
                # Check for assets
                asset_fields = ["asset", "token", "primary_assets", "assets"]
                for field in asset_fields:
                    if field in event_data:
                        value = event_data[field]
                        if isinstance(value, str):
                            event_assets.append(value.upper())
                        elif isinstance(value, list):
                            event_assets.extend([str(v).upper() for v in value])
                
                # Check for projects
                project_fields = ["project", "project_slug", "project_name"]
                for field in project_fields:
                    if field in event_data:
                        value = event_data[field]
                        if isinstance(value, str):
                            event_projects.append(value.lower())
                        elif isinstance(value, list):
                            event_projects.extend([str(v).lower() for v in value])
                
                # If no specific assets/projects and it's a general event, allow it
                if not event_assets and not event_projects:
                    if event.event_type.value in ["news.breaking", "news.important", "project.new", "investor.move", "market.pump", "market.dump"]:
                        content_filter_passed = True
        
        # Check minimum importance score for news events
        importance_filter_passed = True
        if "min_importance" in filters:
            min_score = filters["min_importance"]
            if event.event_type.value in ["news.breaking", "news.important"]:
                importance_score = event_data.get("importance_score", 0)
                importance_filter_passed = importance_score >= min_score
        
        # Check price thresholds for price alerts
        price_filter_passed = True
        if "price_thresholds" in filters:
            if event.event_type.value == "price.alert":
                asset = event_data.get("asset", "").upper()
                price = event_data.get("price", 0)
                
                if asset in filters["price_thresholds"]:
                    threshold_config = filters["price_thresholds"][asset]
                    min_price = threshold_config.get("min_price")
                    max_price = threshold_config.get("max_price")
                    
                    if min_price is not None and price < min_price:
                        price_filter_passed = False
                    if max_price is not None and price > max_price:
                        price_filter_passed = False
        
        # All filters must pass
        return content_filter_passed and importance_filter_passed and price_filter_passed
    
    async def _deliver_webhook(self, sub: Dict, event: WebhookEvent, attempt: int = 1) -> Dict:
        """
        Deliver webhook to a single subscription.
        Returns: {"success": bool, "status_code": int, "error": str, "queued_for_retry": bool}
        """
        import json
        import hmac
        import hashlib
        import uuid
        import time
        
        log_id = f"log_{uuid.uuid4().hex[:12]}"
        start_time = time.time()
        
        try:
            # Prepare payload
            payload = {
                "event": event.event_type.value,
                "timestamp": event.timestamp,
                "data": event.data,
                "webhook_id": sub["id"],
                "attempt": attempt
            }
            
            # Add signature if secret exists
            headers = {"Content-Type": "application/json"}
            if sub.get("secret"):
                signature = hmac.new(
                    sub["secret"].encode(),
                    json.dumps(payload).encode(),
                    hashlib.sha256
                ).hexdigest()
                headers["X-Webhook-Signature"] = f"sha256={signature}"
            
            # Send webhook
            response = await self.client.post(
                sub["url"],
                json=payload,
                headers=headers
            )
            
            response_time_ms = int((time.time() - start_time) * 1000)
            
            if response.status_code < 400:
                # Success - log delivery
                await self._save_delivery_log(
                    log_id=log_id,
                    sub=sub,
                    event=event,
                    attempt=attempt,
                    status="success",
                    status_code=response.status_code,
                    response_time_ms=response_time_ms
                )
                
                await self.db.webhook_subscriptions.update_one(
                    {"id": sub["id"]},
                    {
                        "$set": {"last_triggered": datetime.now(timezone.utc).isoformat()},
                        "$inc": {"success_count": 1}
                    }
                )
                return {"success": True, "status_code": response.status_code, "log_id": log_id}
            else:
                # Failed - log and queue for retry if first attempt
                error_msg = f"HTTP {response.status_code}"
                
                await self._save_delivery_log(
                    log_id=log_id,
                    sub=sub,
                    event=event,
                    attempt=attempt,
                    status="failed",
                    status_code=response.status_code,
                    error=error_msg,
                    response_time_ms=response_time_ms
                )
                
                if attempt == 1:
                    await self._queue_for_retry(sub, event, error_msg)
                    return {"success": False, "status_code": response.status_code, "error": error_msg, "queued_for_retry": True, "log_id": log_id}
                
                await self.db.webhook_subscriptions.update_one(
                    {"id": sub["id"]},
                    {"$inc": {"error_count": 1}}
                )
                logger.warning(f"[Webhooks] Failed to deliver to {sub['url']}: {response.status_code}")
                return {"success": False, "status_code": response.status_code, "error": error_msg, "log_id": log_id}
                
        except Exception as e:
            error_msg = str(e)
            response_time_ms = int((time.time() - start_time) * 1000)
            
            await self._save_delivery_log(
                log_id=log_id,
                sub=sub,
                event=event,
                attempt=attempt,
                status="failed",
                error=error_msg,
                response_time_ms=response_time_ms
            )
            
            if attempt == 1:
                await self._queue_for_retry(sub, event, error_msg)
                return {"success": False, "error": error_msg, "queued_for_retry": True, "log_id": log_id}
            
            logger.error(f"[Webhooks] Error delivering to {sub.get('url')}: {e}")
            return {"success": False, "error": error_msg, "log_id": log_id}
    
    async def _save_delivery_log(self, log_id: str, sub: Dict, event: WebhookEvent, 
                                  attempt: int, status: str, status_code: int = None,
                                  error: str = None, response_time_ms: int = None):
        """Save a delivery attempt to the logs collection."""
        log_doc = {
            "id": log_id,
            "subscription_id": sub["id"],
            "subscription_name": sub.get("name", sub["id"]),
            "subscription_url": sub["url"],
            "event_type": event.event_type.value,
            "event_data": event.data,
            "attempt": attempt,
            "status": status,
            "status_code": status_code,
            "error": error,
            "response_time_ms": response_time_ms,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        await self.db.webhook_delivery_logs.insert_one(log_doc)
    
    async def get_delivery_logs(self, subscription_id: str = None, event_type: str = None,
                                 status: str = None, limit: int = 50) -> List[Dict]:
        """Get delivery logs with optional filters."""
        query = {}
        
        if subscription_id:
            query["subscription_id"] = subscription_id
        if event_type:
            query["event_type"] = event_type
        if status:
            query["status"] = status
        
        logs = []
        cursor = self.db.webhook_delivery_logs.find(
            query,
            {"_id": 0}
        ).sort("created_at", -1).limit(limit)
        
        async for doc in cursor:
            logs.append(doc)
        
        return logs
    
    async def get_delivery_log(self, log_id: str) -> Optional[Dict]:
        """Get a single delivery log by ID."""
        log = await self.db.webhook_delivery_logs.find_one({"id": log_id}, {"_id": 0})
        return log
    
    async def get_delivery_stats(self, subscription_id: str = None) -> Dict:
        """Get delivery statistics."""
        match_stage = {}
        if subscription_id:
            match_stage["subscription_id"] = subscription_id
        
        pipeline = [
            {"$match": match_stage} if match_stage else {"$match": {}},
            {"$group": {
                "_id": "$status",
                "count": {"$sum": 1},
                "avg_response_time": {"$avg": "$response_time_ms"}
            }}
        ]
        
        stats = {"success": 0, "failed": 0, "total": 0, "avg_response_time_ms": 0}
        total_response_time = 0
        total_with_time = 0
        
        async for doc in self.db.webhook_delivery_logs.aggregate(pipeline):
            stats[doc["_id"]] = doc["count"]
            stats["total"] += doc["count"]
            if doc.get("avg_response_time"):
                total_response_time += doc["avg_response_time"] * doc["count"]
                total_with_time += doc["count"]
        
        if total_with_time > 0:
            stats["avg_response_time_ms"] = round(total_response_time / total_with_time, 1)
        
        stats["success_rate"] = round((stats["success"] / stats["total"] * 100) if stats["total"] > 0 else 100, 1)
        
        return stats
    
    async def _queue_for_retry(self, sub: Dict, event: WebhookEvent, error: str):
        """Queue a failed webhook delivery for retry."""
        import uuid
        
        # Retry delays: 1min, 5min, 15min, 1hour (exponential backoff)
        retry_delays = [60, 300, 900, 3600]  # seconds
        
        retry_doc = {
            "id": f"retry_{uuid.uuid4().hex[:12]}",
            "subscription_id": sub["id"],
            "subscription_url": sub["url"],
            "subscription_secret": sub.get("secret"),
            "event_type": event.event_type.value,
            "event_timestamp": event.timestamp,
            "event_data": event.data,
            "attempt": 1,
            "max_attempts": 4,
            "last_error": error,
            "status": "pending",  # pending, retrying, success, failed
            "created_at": datetime.now(timezone.utc).isoformat(),
            "next_retry_at": (datetime.now(timezone.utc) + timedelta(seconds=retry_delays[0])).isoformat(),
            "retry_history": [{
                "attempt": 1,
                "error": error,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }]
        }
        
        await self.db.webhook_retries.insert_one(retry_doc)
        logger.info(f"[Webhooks] Queued retry for {sub['url']}: {retry_doc['id']}")
    
    async def process_pending_retries(self) -> Dict:
        """Process all pending webhook retries that are due."""
        import json
        import hmac
        import hashlib
        
        results = {"processed": 0, "succeeded": 0, "failed": 0, "requeued": 0}
        retry_delays = [60, 300, 900, 3600]
        
        now = datetime.now(timezone.utc).isoformat()
        
        # Find pending retries that are due
        cursor = self.db.webhook_retries.find({
            "status": "pending",
            "next_retry_at": {"$lte": now}
        })
        
        async for retry in cursor:
            results["processed"] += 1
            attempt = retry["attempt"] + 1
            
            try:
                # Mark as retrying
                await self.db.webhook_retries.update_one(
                    {"id": retry["id"]},
                    {"$set": {"status": "retrying"}}
                )
                
                # Prepare payload
                payload = {
                    "event": retry["event_type"],
                    "timestamp": retry["event_timestamp"],
                    "data": retry["event_data"],
                    "webhook_id": retry["subscription_id"],
                    "attempt": attempt,
                    "retry_id": retry["id"]
                }
                
                headers = {"Content-Type": "application/json"}
                if retry.get("subscription_secret"):
                    signature = hmac.new(
                        retry["subscription_secret"].encode(),
                        json.dumps(payload).encode(),
                        hashlib.sha256
                    ).hexdigest()
                    headers["X-Webhook-Signature"] = f"sha256={signature}"
                
                # Attempt delivery
                response = await self.client.post(
                    retry["subscription_url"],
                    json=payload,
                    headers=headers
                )
                
                if response.status_code < 400:
                    # Success!
                    results["succeeded"] += 1
                    await self.db.webhook_retries.update_one(
                        {"id": retry["id"]},
                        {
                            "$set": {
                                "status": "success",
                                "completed_at": datetime.now(timezone.utc).isoformat()
                            },
                            "$push": {
                                "retry_history": {
                                    "attempt": attempt,
                                    "status_code": response.status_code,
                                    "timestamp": datetime.now(timezone.utc).isoformat()
                                }
                            }
                        }
                    )
                    # Update subscription success count
                    await self.db.webhook_subscriptions.update_one(
                        {"id": retry["subscription_id"]},
                        {
                            "$set": {"last_triggered": datetime.now(timezone.utc).isoformat()},
                            "$inc": {"success_count": 1}
                        }
                    )
                    logger.info(f"[Webhooks] Retry successful: {retry['id']} on attempt {attempt}")
                else:
                    raise Exception(f"HTTP {response.status_code}")
                    
            except Exception as e:
                error_msg = str(e)
                
                if attempt >= retry["max_attempts"]:
                    # Max attempts reached - mark as failed
                    results["failed"] += 1
                    await self.db.webhook_retries.update_one(
                        {"id": retry["id"]},
                        {
                            "$set": {
                                "status": "failed",
                                "last_error": error_msg,
                                "completed_at": datetime.now(timezone.utc).isoformat()
                            },
                            "$push": {
                                "retry_history": {
                                    "attempt": attempt,
                                    "error": error_msg,
                                    "timestamp": datetime.now(timezone.utc).isoformat()
                                }
                            }
                        }
                    )
                    # Update subscription error count
                    await self.db.webhook_subscriptions.update_one(
                        {"id": retry["subscription_id"]},
                        {"$inc": {"error_count": 1}}
                    )
                    logger.warning(f"[Webhooks] Retry failed permanently: {retry['id']} after {attempt} attempts")
                else:
                    # Schedule next retry
                    results["requeued"] += 1
                    next_delay = retry_delays[min(attempt - 1, len(retry_delays) - 1)]
                    next_retry = (datetime.now(timezone.utc) + timedelta(seconds=next_delay)).isoformat()
                    
                    await self.db.webhook_retries.update_one(
                        {"id": retry["id"]},
                        {
                            "$set": {
                                "status": "pending",
                                "attempt": attempt,
                                "last_error": error_msg,
                                "next_retry_at": next_retry
                            },
                            "$push": {
                                "retry_history": {
                                    "attempt": attempt,
                                    "error": error_msg,
                                    "timestamp": datetime.now(timezone.utc).isoformat()
                                }
                            }
                        }
                    )
                    logger.info(f"[Webhooks] Retry {retry['id']} requeued for attempt {attempt + 1} at {next_retry}")
        
        return results
    
    async def get_pending_retries(self, limit: int = 50) -> List[Dict]:
        """Get pending webhook retries."""
        retries = []
        cursor = self.db.webhook_retries.find(
            {"status": {"$in": ["pending", "retrying"]}},
            {"_id": 0}
        ).sort("next_retry_at", 1).limit(limit)
        
        async for doc in cursor:
            retries.append(doc)
        return retries
    
    async def get_failed_deliveries(self, limit: int = 50) -> List[Dict]:
        """Get permanently failed webhook deliveries."""
        failed = []
        cursor = self.db.webhook_retries.find(
            {"status": "failed"},
            {"_id": 0}
        ).sort("completed_at", -1).limit(limit)
        
        async for doc in cursor:
            failed.append(doc)
        return failed
    
    async def retry_failed_delivery(self, retry_id: str) -> bool:
        """Manually retry a failed delivery."""
        retry = await self.db.webhook_retries.find_one({"id": retry_id})
        if not retry or retry["status"] != "failed":
            return False
        
        # Reset for retry
        await self.db.webhook_retries.update_one(
            {"id": retry_id},
            {
                "$set": {
                    "status": "pending",
                    "attempt": retry["attempt"],  # Keep same attempt count
                    "next_retry_at": datetime.now(timezone.utc).isoformat()
                }
            }
        )
        return True
    
    async def get_retry_stats(self) -> Dict:
        """Get retry statistics."""
        pipeline = [
            {
                "$group": {
                    "_id": "$status",
                    "count": {"$sum": 1}
                }
            }
        ]
        
        stats = {"pending": 0, "retrying": 0, "success": 0, "failed": 0, "total": 0}
        async for doc in self.db.webhook_retries.aggregate(pipeline):
            stats[doc["_id"]] = doc["count"]
            stats["total"] += doc["count"]
        
        return stats
    
    async def get_event_history(self, limit: int = 50) -> List[Dict]:
        """Get recent webhook events."""
        events = []
        cursor = self.db.webhook_events.find(
            {},
            {"_id": 0}
        ).sort("created_at", -1).limit(limit)
        
        async for doc in cursor:
            events.append(doc)
        return events
    
    async def get_analytics(self, period: str = "24h") -> Dict:
        """
        Get webhook analytics for a given period.
        period: "24h", "7d", "30d"
        """
        # Calculate time range
        now = datetime.now(timezone.utc)
        if period == "24h":
            start_time = now - timedelta(hours=24)
            interval_hours = 1
        elif period == "7d":
            start_time = now - timedelta(days=7)
            interval_hours = 6
        else:  # 30d
            start_time = now - timedelta(days=30)
            interval_hours = 24
        
        start_iso = start_time.isoformat()
        
        # Get total events in period
        total_events = await self.db.webhook_events.count_documents({
            "created_at": {"$gte": start_iso}
        })
        
        # Get success/failed counts from events
        pipeline_results = [
            {"$match": {"created_at": {"$gte": start_iso}}},
            {"$group": {
                "_id": None,
                "total_sent": {"$sum": "$results.sent"},
                "total_failed": {"$sum": "$results.failed"},
                "total_queued": {"$sum": {"$ifNull": ["$results.queued_for_retry", 0]}}
            }}
        ]
        
        totals = {"total_sent": 0, "total_failed": 0, "total_queued": 0}
        async for doc in self.db.webhook_events.aggregate(pipeline_results):
            totals = {
                "total_sent": doc.get("total_sent", 0),
                "total_failed": doc.get("total_failed", 0),
                "total_queued": doc.get("total_queued", 0)
            }
        
        # Calculate success rate
        total_deliveries = totals["total_sent"] + totals["total_failed"]
        success_rate = (totals["total_sent"] / total_deliveries * 100) if total_deliveries > 0 else 100
        
        # Get events by type
        pipeline_by_type = [
            {"$match": {"created_at": {"$gte": start_iso}}},
            {"$group": {
                "_id": "$event_type",
                "count": {"$sum": 1},
                "sent": {"$sum": "$results.sent"},
                "failed": {"$sum": "$results.failed"}
            }},
            {"$sort": {"count": -1}}
        ]
        
        events_by_type = []
        async for doc in self.db.webhook_events.aggregate(pipeline_by_type):
            events_by_type.append({
                "event_type": doc["_id"],
                "count": doc["count"],
                "sent": doc.get("sent", 0),
                "failed": doc.get("failed", 0)
            })
        
        # Get timeline data (events per interval)
        timeline = await self._get_timeline_data(start_time, now, interval_hours)
        
        # Get retry statistics for period
        retry_stats = await self._get_retry_analytics(start_iso)
        
        # Get top subscriptions by activity
        top_subscriptions = await self._get_top_subscriptions(start_iso)
        
        # Get recent errors
        recent_errors = await self._get_recent_errors(limit=5)
        
        return {
            "period": period,
            "start_time": start_iso,
            "end_time": now.isoformat(),
            "summary": {
                "total_events": total_events,
                "total_sent": totals["total_sent"],
                "total_failed": totals["total_failed"],
                "success_rate": round(success_rate, 1),
                "avg_events_per_hour": round(total_events / (24 if period == "24h" else (168 if period == "7d" else 720)), 1)
            },
            "events_by_type": events_by_type,
            "timeline": timeline,
            "retry_stats": retry_stats,
            "top_subscriptions": top_subscriptions,
            "recent_errors": recent_errors
        }
    
    async def _get_timeline_data(self, start: datetime, end: datetime, interval_hours: int) -> List[Dict]:
        """Generate timeline data for chart."""
        timeline = []
        current = start
        
        while current < end:
            next_time = current + timedelta(hours=interval_hours)
            
            # Count events in this interval
            count = await self.db.webhook_events.count_documents({
                "created_at": {
                    "$gte": current.isoformat(),
                    "$lt": next_time.isoformat()
                }
            })
            
            # Get sent/failed for this interval
            pipeline = [
                {"$match": {
                    "created_at": {
                        "$gte": current.isoformat(),
                        "$lt": next_time.isoformat()
                    }
                }},
                {"$group": {
                    "_id": None,
                    "sent": {"$sum": "$results.sent"},
                    "failed": {"$sum": "$results.failed"}
                }}
            ]
            
            sent, failed = 0, 0
            async for doc in self.db.webhook_events.aggregate(pipeline):
                sent = doc.get("sent", 0)
                failed = doc.get("failed", 0)
            
            timeline.append({
                "timestamp": current.isoformat(),
                "label": current.strftime("%H:%M" if interval_hours <= 6 else "%m/%d"),
                "events": count,
                "sent": sent,
                "failed": failed
            })
            
            current = next_time
        
        return timeline
    
    async def _get_retry_analytics(self, start_iso: str) -> Dict:
        """Get retry analytics for period."""
        pipeline = [
            {"$match": {"created_at": {"$gte": start_iso}}},
            {"$group": {
                "_id": "$status",
                "count": {"$sum": 1}
            }}
        ]
        
        stats = {"pending": 0, "success": 0, "failed": 0, "total": 0}
        async for doc in self.db.webhook_retries.aggregate(pipeline):
            stats[doc["_id"]] = doc["count"]
            stats["total"] += doc["count"]
        
        # Calculate retry success rate
        completed = stats["success"] + stats["failed"]
        stats["retry_success_rate"] = round((stats["success"] / completed * 100) if completed > 0 else 0, 1)
        
        return stats
    
    async def _get_top_subscriptions(self, start_iso: str, limit: int = 5) -> List[Dict]:
        """Get most active webhook subscriptions."""
        # Get all subscriptions
        subs = {}
        async for doc in self.db.webhook_subscriptions.find({}, {"_id": 0}):
            subs[doc["id"]] = {
                "id": doc["id"],
                "name": doc.get("name", doc["id"]),
                "url": doc["url"],
                "success_count": doc.get("success_count", 0),
                "error_count": doc.get("error_count", 0),
                "enabled": doc.get("enabled", True)
            }
        
        # Sort by total activity
        sorted_subs = sorted(
            subs.values(), 
            key=lambda x: x["success_count"] + x["error_count"], 
            reverse=True
        )
        
        return sorted_subs[:limit]
    
    async def _get_recent_errors(self, limit: int = 5) -> List[Dict]:
        """Get recent webhook delivery errors."""
        errors = []
        
        # From failed retries
        cursor = self.db.webhook_retries.find(
            {"status": "failed"},
            {"_id": 0}
        ).sort("completed_at", -1).limit(limit)
        
        async for doc in cursor:
            errors.append({
                "type": "retry_failed",
                "url": doc.get("subscription_url"),
                "event_type": doc.get("event_type"),
                "error": doc.get("last_error"),
                "attempts": doc.get("attempt"),
                "timestamp": doc.get("completed_at") or doc.get("created_at")
            })
        
        return errors


# Global manager instance
_manager: Optional[WebhookManager] = None

def get_manager() -> WebhookManager:
    global _manager
    if _manager is None:
        _manager = WebhookManager(get_db())
    return _manager


# ═══════════════════════════════════════════════════════════════
# API ROUTES
# ═══════════════════════════════════════════════════════════════

@router.get("/subscriptions")
async def list_subscriptions():
    """
    Список всех webhook подписок.
    
    Returns all active webhook subscriptions.
    """
    manager = get_manager()
    subs = await manager.list_subscriptions()
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "total": len(subs),
        "subscriptions": subs
    }


@router.post("/subscriptions")
async def create_subscription(sub: WebhookSubscription):
    """
    Создать новую webhook подписку.
    
    **Event Types:**
    - `funding.round` - Новый раунд финансирования
    - `token.unlock` - Разблокировка токенов
    - `news.breaking` - Срочные новости
    - `news.important` - Важные новости (высокий score)
    - `price.alert` - Пересечение ценового порога
    - `sentiment.shift` - Значительное изменение sentiment
    - `project.new` - Обнаружен новый проект
    - `investor.move` - Активность крупного инвестора
    
    **Filters (optional):**
    - `assets`: Array of asset symbols (e.g., ["BTC", "ETH"]) - only events for these assets
    - `projects`: Array of project slugs (e.g., ["uniswap", "compound"]) - only events for these projects
    - `min_importance`: Minimum importance score for news events (0.0-1.0)
    - `price_thresholds`: Asset-specific price filters for price alerts
    
    **Example Request:**
    ```json
    {
        "url": "https://your-server.com/webhook",
        "events": ["funding.round", "token.unlock", "news.important"],
        "name": "My Integration",
        "secret": "your-secret-key",
        "filters": {
            "assets": ["BTC", "ETH"],
            "projects": ["uniswap"],
            "min_importance": 0.8
        }
    }
    ```
    
    **Example with Price Thresholds:**
    ```json
    {
        "url": "https://your-server.com/webhook",
        "events": ["price.alert"],
        "filters": {
            "price_thresholds": {
                "BTC": {"min_price": 50000, "max_price": 100000},
                "ETH": {"min_price": 3000}
            }
        }
    }
    ```
    """
    manager = get_manager()
    result = await manager.create_subscription(sub)
    return {"ok": True, **result}


@router.delete("/subscriptions/{webhook_id}")
async def delete_subscription(webhook_id: str):
    """
    Удалить webhook подписку.
    """
    manager = get_manager()
    deleted = await manager.delete_subscription(webhook_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return {"ok": True, "deleted": webhook_id}


@router.get("/subscriptions/{webhook_id}")
async def get_subscription(webhook_id: str):
    """
    Получить webhook подписку по ID.
    """
    manager = get_manager()
    sub = await manager.get_subscription(webhook_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return sub


class WebhookUpdate(BaseModel):
    url: Optional[HttpUrl] = None
    events: Optional[List[WebhookEventType]] = None
    name: Optional[str] = None
    secret: Optional[str] = None
    enabled: Optional[bool] = None
    filters: Optional[Dict[str, Any]] = None


@router.put("/subscriptions/{webhook_id}")
async def update_subscription(webhook_id: str, update: WebhookUpdate):
    """
    Обновить webhook подписку.
    
    Можно обновить:
    - url: новый URL для webhook
    - events: список событий
    - name: название интеграции
    - secret: секретный ключ для HMAC
    - enabled: включить/выключить подписку
    - filters: фильтры для событий (assets, projects, min_importance, price_thresholds)
    """
    manager = get_manager()
    
    # Check if subscription exists
    existing = await manager.get_subscription(webhook_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Webhook not found")
    
    # Build updates dict from non-None values
    updates = {}
    if update.url is not None:
        updates["url"] = str(update.url)
    if update.events is not None:
        updates["events"] = update.events
    if update.name is not None:
        updates["name"] = update.name
    if update.secret is not None:
        updates["secret"] = update.secret
    if update.enabled is not None:
        updates["enabled"] = update.enabled
    if update.filters is not None:
        updates["filters"] = update.filters
    
    if not updates:
        return {"ok": True, "message": "No changes"}
    
    success = await manager.update_subscription(webhook_id, updates)
    if success:
        return {"ok": True, "updated": webhook_id}
    return {"ok": False, "message": "Update failed"}


@router.post("/test")
async def test_webhook(url: str, event_type: WebhookEventType = WebhookEventType.NEWS_IMPORTANT):
    """
    Отправить тестовый webhook.
    
    Sends a test webhook event to the specified URL.
    """
    manager = get_manager()
    
    test_event = WebhookEvent(
        event_type=event_type,
        timestamp=datetime.now(timezone.utc).isoformat(),
        data={
            "test": True,
            "message": "This is a test webhook from FOMO",
            "example_data": {
                "project": "test-project",
                "amount": 1000000,
                "currency": "USD"
            }
        }
    )
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                url,
                json={
                    "event": test_event.event_type.value,
                    "timestamp": test_event.timestamp,
                    "data": test_event.data
                }
            )
            return {
                "ok": response.status_code < 400,
                "status_code": response.status_code,
                "response": response.text[:500] if response.text else None
            }
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.get("/events")
async def get_event_history(limit: int = 50):
    """
    История отправленных webhook событий.
    
    Returns recent webhook events with delivery results.
    """
    manager = get_manager()
    events = await manager.get_event_history(limit)
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "total": len(events),
        "events": events
    }


@router.get("/event-types")
async def list_event_types():
    """
    Список доступных типов событий.
    
    Returns all available webhook event types with descriptions.
    """
    return {
        "event_types": [
            {
                "type": "funding.round",
                "description": "Новый раунд финансирования",
                "example_data": {
                    "project_slug": "example-project",
                    "project_name": "Example Project",
                    "stage": "series_a",
                    "amount": 25000000,
                    "currency": "USD",
                    "lead_investors": ["a16z", "paradigm"]
                }
            },
            {
                "type": "token.unlock",
                "description": "Разблокировка токенов",
                "example_data": {
                    "project": "solana",
                    "token": "SOL",
                    "unlock_date": "2026-03-15",
                    "amount": 1500000,
                    "value_usd": 225000000,
                    "percent_of_supply": 2.5
                }
            },
            {
                "type": "news.breaking",
                "description": "Срочные новости",
                "example_data": {
                    "event_id": "evt_123",
                    "headline": "Breaking: SEC approves Bitcoin ETF",
                    "importance_score": 0.95,
                    "primary_assets": ["BTC"],
                    "source": "CoinDesk"
                }
            },
            {
                "type": "news.important",
                "description": "Важные новости (score > 0.7)",
                "example_data": {
                    "event_id": "evt_456",
                    "headline": "Major funding round announced",
                    "importance_score": 0.82,
                    "primary_assets": ["ETH"],
                    "sources_count": 5
                }
            },
            {
                "type": "price.alert",
                "description": "Пересечение ценового порога",
                "example_data": {
                    "asset": "BTC",
                    "price": 70000,
                    "threshold": 70000,
                    "direction": "above",
                    "change_24h": 5.2
                }
            },
            {
                "type": "sentiment.shift",
                "description": "Значительное изменение sentiment",
                "example_data": {
                    "asset": "ETH",
                    "old_sentiment": 0.3,
                    "new_sentiment": 0.8,
                    "shift": 0.5,
                    "reason": "Major partnership announcement"
                }
            },
            {
                "type": "project.new",
                "description": "Обнаружен новый проект",
                "example_data": {
                    "slug": "new-project",
                    "name": "New Project",
                    "categories": ["defi", "layer2"],
                    "discovered_from": "cryptorank"
                }
            },
            {
                "type": "investor.move",
                "description": "Активность крупного инвестора",
                "example_data": {
                    "investor_id": "a16z",
                    "investor_name": "Andreessen Horowitz",
                    "action": "investment",
                    "project": "example-project",
                    "amount": 50000000
                }
            },
            {
                "type": "market.pump",
                "description": "Резкий рост цены (>5% за час)",
                "example_data": {
                    "asset": "SOL",
                    "price": 185.50,
                    "change_1h": 7.2,
                    "change_24h": 12.5,
                    "volume_24h": 2500000000
                }
            },
            {
                "type": "market.dump",
                "description": "Резкое падение цены (>5% за час)",
                "example_data": {
                    "asset": "DOGE",
                    "price": 0.08,
                    "change_1h": -8.5,
                    "change_24h": -15.2,
                    "volume_24h": 1200000000
                }
            },
            {
                "type": "whale.alert",
                "description": "Крупная транзакция кита",
                "example_data": {
                    "asset": "BTC",
                    "amount": 1500,
                    "value_usd": 105000000,
                    "from_address": "bc1q...",
                    "to_address": "bc1p...",
                    "tx_hash": "abc123..."
                }
            },
            {
                "type": "listing.new",
                "description": "Новый листинг на бирже",
                "example_data": {
                    "asset": "NEWTOKEN",
                    "exchange": "binance",
                    "pair": "NEWTOKEN/USDT",
                    "listing_date": "2026-03-15",
                    "trading_starts": "2026-03-15T10:00:00Z"
                }
            },
            {
                "type": "airdrop.announced",
                "description": "Анонс аирдропа",
                "example_data": {
                    "project": "LayerZero",
                    "token": "ZRO",
                    "snapshot_date": "2026-04-01",
                    "claim_date": "2026-04-15",
                    "eligibility": "Bridge users with >$1000 volume"
                }
            },
            {
                "type": "hack.detected",
                "description": "Обнаружен взлом/эксплойт",
                "example_data": {
                    "project": "Example Protocol",
                    "type": "flash_loan_attack",
                    "estimated_loss_usd": 5000000,
                    "affected_chains": ["ethereum", "bsc"],
                    "status": "investigating"
                }
            },
            {
                "type": "regulation.update",
                "description": "Регуляторные новости",
                "example_data": {
                    "region": "USA",
                    "regulator": "SEC",
                    "action": "approval",
                    "subject": "Spot Ethereum ETF",
                    "impact": "positive"
                }
            }
        ]
    }


# ═══════════════════════════════════════════════════════════════
# HELPER FUNCTIONS (for other modules to trigger webhooks)
# ═══════════════════════════════════════════════════════════════

async def emit_funding_event(funding_data: Dict):
    """Emit funding.round webhook event."""
    manager = get_manager()
    await manager.trigger_event(WebhookEvent(
        event_type=WebhookEventType.FUNDING_ROUND,
        timestamp=datetime.now(timezone.utc).isoformat(),
        data=funding_data
    ))


async def emit_unlock_event(unlock_data: Dict):
    """Emit token.unlock webhook event."""
    manager = get_manager()
    await manager.trigger_event(WebhookEvent(
        event_type=WebhookEventType.TOKEN_UNLOCK,
        timestamp=datetime.now(timezone.utc).isoformat(),
        data=unlock_data
    ))


async def emit_news_event(news_data: Dict, breaking: bool = False):
    """Emit news webhook event."""
    manager = get_manager()
    await manager.trigger_event(WebhookEvent(
        event_type=WebhookEventType.NEWS_BREAKING if breaking else WebhookEventType.NEWS_IMPORTANT,
        timestamp=datetime.now(timezone.utc).isoformat(),
        data=news_data
    ))


async def emit_price_alert(alert_data: Dict):
    """Emit price.alert webhook event."""
    manager = get_manager()
    await manager.trigger_event(WebhookEvent(
        event_type=WebhookEventType.PRICE_ALERT,
        timestamp=datetime.now(timezone.utc).isoformat(),
        data=alert_data
    ))



@router.post("/check-all")
async def check_all_events():
    """
    Проверить все новые события и отправить webhooks.
    
    Manually triggers webhook checks for:
    - New funding rounds (last 30 minutes)
    - Upcoming token unlocks (next 7 days)
    - Important news (score >= 0.7, last 30 minutes)
    """
    from .emitter import get_emitter
    
    db = get_db()
    emitter = get_emitter(db)
    results = await emitter.run_all_checks()
    
    return {
        "ok": True,
        **results
    }


@router.post("/check-funding")
async def check_funding_events(since_minutes: int = 30):
    """Check for new funding rounds and emit webhooks."""
    from .emitter import get_emitter
    
    db = get_db()
    emitter = get_emitter(db)
    results = await emitter.check_new_funding(since_minutes)
    
    return {"ok": True, **results}


@router.post("/check-unlocks")
async def check_unlock_events(days_ahead: int = 7):
    """Check for upcoming token unlocks and emit webhooks."""
    from .emitter import get_emitter
    
    db = get_db()
    emitter = get_emitter(db)
    results = await emitter.check_new_unlocks(days_ahead)
    
    return {"ok": True, **results}


@router.post("/check-news")
async def check_news_events(since_minutes: int = 30):
    """Check for important news and emit webhooks."""
    from .emitter import get_emitter
    
    db = get_db()
    emitter = get_emitter(db)
    results = await emitter.check_new_news(since_minutes)
    
    return {"ok": True, **results}



# ═══════════════════════════════════════════════════════════════
# RETRY MANAGEMENT ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@router.get("/retries/pending")
async def get_pending_retries(limit: int = 50):
    """
    Получить список ожидающих повторных попыток доставки.
    
    Returns pending webhook deliveries queued for retry.
    """
    manager = get_manager()
    retries = await manager.get_pending_retries(limit)
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "total": len(retries),
        "retries": retries
    }


@router.get("/retries/failed")
async def get_failed_deliveries(limit: int = 50):
    """
    Получить список неудачных доставок (исчерпаны все попытки).
    
    Returns permanently failed webhook deliveries.
    """
    manager = get_manager()
    failed = await manager.get_failed_deliveries(limit)
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "total": len(failed),
        "failed": failed
    }


@router.get("/retries/stats")
async def get_retry_stats():
    """
    Статистика по повторным попыткам доставки.
    
    Returns retry statistics by status.
    """
    manager = get_manager()
    stats = await manager.get_retry_stats()
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        **stats
    }


@router.post("/retries/process")
async def process_retries():
    """
    Обработать все ожидающие повторные попытки.
    
    Manually triggers processing of pending retries.
    """
    manager = get_manager()
    results = await manager.process_pending_retries()
    return {
        "ok": True,
        **results
    }


@router.post("/retries/{retry_id}/retry")
async def retry_failed_delivery(retry_id: str):
    """
    Повторить неудачную доставку вручную.
    
    Manually retry a failed delivery.
    """
    manager = get_manager()
    success = await manager.retry_failed_delivery(retry_id)
    if not success:
        raise HTTPException(status_code=404, detail="Retry not found or not in failed state")
    return {"ok": True, "retry_id": retry_id, "message": "Queued for retry"}



# ═══════════════════════════════════════════════════════════════
# ANALYTICS ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@router.get("/analytics")
async def get_analytics(period: str = "24h"):
    """
    Получить аналитику по webhook доставкам.
    
    Параметры:
    - period: "24h" (последние 24 часа), "7d" (7 дней), "30d" (30 дней)
    
    Возвращает:
    - summary: общая статистика (события, доставки, success rate)
    - events_by_type: распределение по типам событий
    - timeline: данные для графика по времени
    - retry_stats: статистика повторных попыток
    - top_subscriptions: самые активные подписки
    - recent_errors: последние ошибки доставки
    """
    if period not in ["24h", "7d", "30d"]:
        raise HTTPException(status_code=400, detail="Invalid period. Use: 24h, 7d, 30d")
    
    manager = get_manager()
    analytics = await manager.get_analytics(period)
    
    return {
        "ok": True,
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        **analytics
    }



# ═══════════════════════════════════════════════════════════════
# DELIVERY LOGS ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@router.get("/delivery-logs")
async def get_delivery_logs(
    subscription_id: str = None,
    event_type: str = None,
    status: str = None,
    limit: int = 50
):
    """
    Получить логи доставки webhook.
    
    Параметры:
    - subscription_id: фильтр по подписке
    - event_type: фильтр по типу события
    - status: фильтр по статусу (success, failed)
    - limit: максимальное количество записей
    
    Возвращает детальную информацию о каждой попытке доставки.
    """
    manager = get_manager()
    logs = await manager.get_delivery_logs(
        subscription_id=subscription_id,
        event_type=event_type,
        status=status,
        limit=limit
    )
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "total": len(logs),
        "logs": logs
    }


@router.get("/delivery-logs/{log_id}")
async def get_delivery_log(log_id: str):
    """
    Получить детали конкретной попытки доставки.
    """
    manager = get_manager()
    log = await manager.get_delivery_log(log_id)
    
    if not log:
        raise HTTPException(status_code=404, detail="Delivery log not found")
    
    return log


@router.get("/delivery-stats")
async def get_delivery_stats(subscription_id: str = None):
    """
    Получить статистику доставки webhook.
    
    Параметры:
    - subscription_id: фильтр по подписке (опционально)
    
    Возвращает:
    - success: количество успешных доставок
    - failed: количество неудачных
    - total: всего попыток
    - success_rate: процент успешных
    - avg_response_time_ms: среднее время ответа
    """
    manager = get_manager()
    stats = await manager.get_delivery_stats(subscription_id)
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        **stats
    }
