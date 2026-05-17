"""
Sentiment Analysis Scheduler
==============================
Auto-analyze incoming news with multi-provider sentiment engine.
Cache results in MongoDB for fast retrieval.

Schedule:
- Sentiment Analysis: Every 2 minutes (new unanalyzed events)
- Cache Cleanup: Daily at 3:00 UTC (remove old cache entries)
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR

logger = logging.getLogger(__name__)

# Cache collection name
SENTIMENT_CACHE_COLLECTION = "sentiment_cache"


class SentimentScheduler:
    """
    Scheduler for automated sentiment analysis.
    Auto-analyzes new news events and caches results in MongoDB.
    """
    
    def __init__(self, db):
        self.db = db
        self.scheduler = AsyncIOScheduler(timezone="UTC")
        self._running = False
        self._stats: Dict[str, Dict] = {}
        self._engine = None
        
        # Register event listeners
        self.scheduler.add_listener(self._on_job_executed, EVENT_JOB_EXECUTED)
        self.scheduler.add_listener(self._on_job_error, EVENT_JOB_ERROR)
        
    def _get_engine(self):
        """Lazy load sentiment engine"""
        if self._engine is None:
            from modules.sentiment_engine.engine import SentimentEngine
            self._engine = SentimentEngine(self.db)
        return self._engine
    
    def _on_job_executed(self, event):
        """Track successful job execution"""
        job_id = event.job_id
        self._stats[job_id] = {
            "last_run": datetime.now(timezone.utc).isoformat(),
            "status": "success",
            "run_count": self._stats.get(job_id, {}).get("run_count", 0) + 1
        }
        logger.info(f"[SentimentScheduler] Job {job_id} completed successfully")
    
    def _on_job_error(self, event):
        """Track failed job execution"""
        job_id = event.job_id
        self._stats[job_id] = {
            "last_run": datetime.now(timezone.utc).isoformat(),
            "status": "error",
            "error": str(event.exception)[:200],
            "error_count": self._stats.get(job_id, {}).get("error_count", 0) + 1
        }
        logger.error(f"[SentimentScheduler] Job {job_id} failed: {event.exception}")
    
    async def _ensure_indexes(self):
        """Ensure MongoDB indexes for sentiment cache"""
        try:
            cache_col = self.db[SENTIMENT_CACHE_COLLECTION]
            
            # Create indexes
            await cache_col.create_index("event_id", unique=True)
            await cache_col.create_index("analyzed_at")
            await cache_col.create_index([("consensus_label", 1), ("analyzed_at", -1)])
            await cache_col.create_index("ttl_expire", expireAfterSeconds=0)  # TTL index
            
            logger.info("[SentimentScheduler] MongoDB indexes created")
        except Exception as e:
            logger.error(f"[SentimentScheduler] Index creation failed: {e}")
    
    async def _run_sentiment_analysis(self):
        """
        Main job: Analyze unprocessed news events with multi-provider sentiment.
        Stores results in MongoDB cache.
        """
        engine = self._get_engine()
        cache_col = self.db[SENTIMENT_CACHE_COLLECTION]
        events_col = self.db["news_events"]
        
        try:
            # Get already analyzed text hashes
            analyzed_cursor = cache_col.find({}, {"event_id": 1, "text_hash": 1})
            analyzed_ids = set()
            analyzed_hashes = set()
            async for doc in analyzed_cursor:
                if doc.get("event_id"):
                    analyzed_ids.add(doc.get("event_id"))
                if doc.get("text_hash"):
                    analyzed_hashes.add(doc.get("text_hash"))
            
            # Find unanalyzed events from last 7 days
            cutoff = datetime.now(timezone.utc) - timedelta(days=7)
            
            query = {}  # Get all events, filter by text hash
            
            unanalyzed = []
            cursor = events_col.find(query, {"_id": 0}).sort("created_at", -1).limit(200)
            
            async for event in cursor:
                event_id = event.get("event_id") or event.get("id") or str(hash(str(event)[:100]))
                # Use correct field names from news_events
                text = (event.get("headline") or event.get("title_en") or 
                        event.get("title_seed") or event.get("summary_en") or 
                        event.get("summary") or event.get("title") or "")
                text_hash = hash(text[:500])
                
                # Skip if already analyzed (by ID or text hash)
                if event_id in analyzed_ids or text_hash in analyzed_hashes:
                    continue
                    
                # Set event_id if missing
                event["_computed_event_id"] = event_id
                event["_text_hash"] = text_hash
                unanalyzed.append(event)
            
            if not unanalyzed:
                logger.debug("[SentimentScheduler] No new events to analyze")
                return {"analyzed": 0, "cached": 0}
            
            logger.info(f"[SentimentScheduler] Analyzing {len(unanalyzed)} new events...")
            
            analyzed_count = 0
            cached_count = 0
            
            # Process in batches of 10
            batch_size = 10
            for i in range(0, len(unanalyzed), batch_size):
                batch = unanalyzed[i:i + batch_size]
                
                for event in batch:
                    try:
                        event_id = event.get("_computed_event_id") or event.get("event_id") or event.get("id")
                        text_hash = event.get("_text_hash") or hash(str(event)[:100])
                        # Use correct field names
                        text = (event.get("headline") or event.get("title_en") or 
                                event.get("title_seed") or event.get("summary_en") or 
                                event.get("summary") or event.get("title") or "")
                        
                        if len(text) < 10:
                            continue
                        
                        # Analyze with multi-provider engine
                        result = await engine.analyze(text, context={"event_id": event_id})
                        analyzed_count += 1
                        
                        # Prepare cache document
                        cache_doc = {
                            "event_id": event_id,
                            "text_hash": text_hash,
                            "consensus": {
                                "score": result.consensus_score,
                                "confidence": result.consensus_confidence,
                                "label": result.consensus_label,
                                "providers_used": result.providers_used
                            },
                            "fomo": {
                                "score": result.fomo_score,
                                "confidence": result.fomo_confidence,
                                "available": result.fomo_available
                            },
                            "providers": [
                                {
                                    "provider": p.provider,
                                    "model": p.model,
                                    "score": p.score,
                                    "confidence": p.confidence,
                                    "label": p.label,
                                    "factors": p.factors,
                                    "latency_ms": p.latency_ms,
                                    "error": p.error
                                }
                                for p in result.providers
                            ],
                            "analyzed_at": datetime.now(timezone.utc).isoformat(),
                            "ttl_expire": datetime.now(timezone.utc) + timedelta(days=7),  # 7 day TTL
                            "text_preview": text[:200]
                        }
                        
                        # Upsert to cache
                        await cache_col.update_one(
                            {"event_id": event_id},
                            {"$set": cache_doc},
                            upsert=True
                        )
                        cached_count += 1
                        
                        # Also update the news_events collection with sentiment
                        await events_col.update_one(
                            {"$or": [{"event_id": event_id}, {"id": event_id}]},
                            {"$set": {
                                "multi_sentiment": {
                                    "consensus_score": result.consensus_score,
                                    "consensus_label": result.consensus_label,
                                    "fomo_score": result.fomo_score,
                                    "providers_used": result.providers_used,
                                    "analyzed_at": datetime.now(timezone.utc).isoformat()
                                }
                            }}
                        )
                        
                    except Exception as e:
                        logger.error(f"[SentimentScheduler] Failed to analyze event {event_id}: {e}")
                
                # Small delay between batches to avoid rate limits
                await asyncio.sleep(0.5)
            
            logger.info(f"[SentimentScheduler] Completed: {analyzed_count} analyzed, {cached_count} cached")
            
            return {
                "analyzed": analyzed_count,
                "cached": cached_count,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"[SentimentScheduler] Sentiment analysis job failed: {e}")
            raise
    
    async def _run_cache_cleanup(self):
        """
        Cleanup job: Remove expired cache entries and compact collection.
        """
        cache_col = self.db[SENTIMENT_CACHE_COLLECTION]
        
        try:
            # Remove entries older than 7 days (backup to TTL index)
            cutoff = datetime.now(timezone.utc) - timedelta(days=7)
            
            result = await cache_col.delete_many({
                "analyzed_at": {"$lt": cutoff.isoformat()}
            })
            
            deleted = result.deleted_count
            
            # Get collection stats
            stats = await cache_col.count_documents({})
            
            logger.info(f"[SentimentScheduler] Cache cleanup: {deleted} removed, {stats} remaining")
            
            return {
                "deleted": deleted,
                "remaining": stats,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"[SentimentScheduler] Cache cleanup failed: {e}")
            raise
    
    async def get_cached_sentiment(self, event_id: str) -> Optional[Dict]:
        """Get cached sentiment for an event"""
        cache_col = self.db[SENTIMENT_CACHE_COLLECTION]
        
        doc = await cache_col.find_one(
            {"event_id": event_id},
            {"_id": 0, "ttl_expire": 0}
        )
        
        return doc
    
    async def get_cached_sentiments_batch(self, event_ids: List[str]) -> Dict[str, Dict]:
        """Get cached sentiments for multiple events"""
        cache_col = self.db[SENTIMENT_CACHE_COLLECTION]
        
        results = {}
        cursor = cache_col.find(
            {"event_id": {"$in": event_ids}},
            {"_id": 0, "ttl_expire": 0}
        )
        
        async for doc in cursor:
            results[doc["event_id"]] = doc
        
        return results
    
    async def get_cache_stats(self) -> Dict:
        """Get sentiment cache statistics"""
        cache_col = self.db[SENTIMENT_CACHE_COLLECTION]
        
        total = await cache_col.count_documents({})
        
        # Count by label
        pipeline = [
            {"$group": {
                "_id": "$consensus.label",
                "count": {"$sum": 1},
                "avg_score": {"$avg": "$consensus.score"},
                "avg_confidence": {"$avg": "$consensus.confidence"}
            }}
        ]
        
        by_label = {}
        async for doc in cache_col.aggregate(pipeline):
            by_label[doc["_id"]] = {
                "count": doc["count"],
                "avg_score": round(doc["avg_score"], 3),
                "avg_confidence": round(doc["avg_confidence"], 3)
            }
        
        # Recent analysis stats
        last_hour = datetime.now(timezone.utc) - timedelta(hours=1)
        recent = await cache_col.count_documents({
            "analyzed_at": {"$gte": last_hour.isoformat()}
        })
        
        return {
            "total_cached": total,
            "analyzed_last_hour": recent,
            "by_label": by_label,
            "job_stats": self._stats,
            "scheduler_running": self._running
        }
    
    async def _monitor_sentiment_shifts(self):
        """
        Monitor for significant sentiment shifts and send WebSocket alerts.
        Triggers alert when sentiment changes >20% for an asset within 1 hour.
        """
        try:
            from modules.websocket import broadcast_sentiment_alert
            
            cache_col = self.db[SENTIMENT_CACHE_COLLECTION]
            shifts_col = self.db["sentiment_shifts"]
            
            # Get events from last hour
            one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
            two_hours_ago = datetime.now(timezone.utc) - timedelta(hours=2)
            
            # Get recent sentiment scores by asset
            pipeline = [
                {
                    "$match": {
                        "analyzed_at": {"$gte": one_hour_ago.isoformat()}
                    }
                },
                {
                    "$unwind": {"path": "$assets", "preserveNullAndEmptyArrays": True}
                },
                {
                    "$group": {
                        "_id": "$assets",
                        "current_avg": {"$avg": "$consensus.score"},
                        "count": {"$sum": 1},
                        "latest": {"$max": "$analyzed_at"}
                    }
                },
                {
                    "$match": {"_id": {"$ne": None}, "count": {"$gte": 2}}
                }
            ]
            
            current_sentiments = {}
            async for doc in cache_col.aggregate(pipeline):
                asset = doc["_id"]
                if asset:
                    current_sentiments[asset] = {
                        "score": doc["current_avg"],
                        "count": doc["count"]
                    }
            
            # Get previous hour sentiment for comparison
            pipeline_prev = [
                {
                    "$match": {
                        "analyzed_at": {
                            "$gte": two_hours_ago.isoformat(),
                            "$lt": one_hour_ago.isoformat()
                        }
                    }
                },
                {
                    "$unwind": {"path": "$assets", "preserveNullAndEmptyArrays": True}
                },
                {
                    "$group": {
                        "_id": "$assets",
                        "prev_avg": {"$avg": "$consensus.score"},
                        "count": {"$sum": 1}
                    }
                }
            ]
            
            previous_sentiments = {}
            async for doc in cache_col.aggregate(pipeline_prev):
                asset = doc["_id"]
                if asset:
                    previous_sentiments[asset] = doc["prev_avg"]
            
            # Detect shifts > 20%
            alerts_sent = 0
            for asset, current in current_sentiments.items():
                if asset in previous_sentiments:
                    prev_score = previous_sentiments[asset]
                    curr_score = current["score"]
                    
                    # Calculate percentage change
                    if abs(prev_score) > 0.01:  # Avoid division by near-zero
                        change_percent = ((curr_score - prev_score) / abs(prev_score)) * 100
                    else:
                        change_percent = (curr_score - prev_score) * 100
                    
                    # Alert if change > 20%
                    if abs(change_percent) >= 20:
                        alert = {
                            "asset": asset,
                            "asset_name": asset.upper(),
                            "previous": round(prev_score, 3),
                            "current": round(curr_score, 3),
                            "change_percent": round(change_percent, 1),
                            "time_window": "1h",
                            "confidence": "high" if current["count"] >= 5 else "medium",
                            "sources": [],
                            "detected_at": datetime.now(timezone.utc).isoformat()
                        }
                        
                        # Store shift in database
                        await shifts_col.insert_one({
                            **alert,
                            "sent": True
                        })
                        
                        # Send WebSocket alert
                        await broadcast_sentiment_alert(alert)
                        alerts_sent += 1
                        
                        logger.info(f"[SentimentScheduler] Shift alert: {asset} {change_percent:.1f}%")
            
            logger.info(f"[SentimentScheduler] Sentiment monitoring: {alerts_sent} alerts sent")
            
            return {
                "assets_monitored": len(current_sentiments),
                "alerts_sent": alerts_sent,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"[SentimentScheduler] Sentiment monitoring failed: {e}")
            raise
    
    def start(self):
        """Start the sentiment scheduler"""
        if self._running:
            logger.warning("[SentimentScheduler] Already running")
            return
        
        # Add jobs
        self.scheduler.add_job(
            self._run_sentiment_analysis,
            IntervalTrigger(minutes=2),
            id="sentiment_auto_analyze",
            name="Auto-Analyze New Events",
            replace_existing=True
        )
        
        self.scheduler.add_job(
            self._run_cache_cleanup,
            CronTrigger(hour=3, minute=0),  # Daily at 3:00 UTC
            id="sentiment_cache_cleanup",
            name="Sentiment Cache Cleanup",
            replace_existing=True
        )
        
        # Add sentiment shift monitoring job
        self.scheduler.add_job(
            self._monitor_sentiment_shifts,
            IntervalTrigger(minutes=5),
            id="sentiment_shift_monitor",
            name="Monitor Sentiment Shifts",
            replace_existing=True
        )
        
        # Ensure indexes on startup
        asyncio.create_task(self._ensure_indexes())
        
        # Run initial analysis
        asyncio.create_task(self._run_sentiment_analysis())
        
        self.scheduler.start()
        self._running = True
        
        logger.info("[SentimentScheduler] Started with 2 jobs")
    
    def stop(self):
        """Stop the sentiment scheduler"""
        if not self._running:
            return
        
        self.scheduler.shutdown(wait=False)
        self._running = False
        
        logger.info("[SentimentScheduler] Stopped")
    
    def get_status(self) -> Dict:
        """Get scheduler status"""
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                "stats": self._stats.get(job.id, {})
            })
        
        return {
            "running": self._running,
            "jobs": jobs,
            "engine_status": self._get_engine().get_status() if self._engine else None
        }


# Global scheduler instance
_sentiment_scheduler: Optional[SentimentScheduler] = None


def get_sentiment_scheduler(db=None) -> SentimentScheduler:
    """Get or create sentiment scheduler instance"""
    global _sentiment_scheduler
    
    if _sentiment_scheduler is None and db is not None:
        _sentiment_scheduler = SentimentScheduler(db)
    
    return _sentiment_scheduler


def start_sentiment_scheduler(db):
    """Start sentiment scheduler"""
    scheduler = get_sentiment_scheduler(db)
    scheduler.start()
    return scheduler
