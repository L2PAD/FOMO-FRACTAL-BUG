"""
News Intelligence Scheduler
===========================

Background scheduler for automatic pipeline execution.
Uses APScheduler with AsyncIOScheduler for proper async handling.
"""

import logging
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

# Scheduler state
_scheduler: Optional[AsyncIOScheduler] = None
_db = None
_last_run_time: Optional[datetime] = None
_last_run_result: Optional[Dict] = None
_job_count = 0

# Generation progress tracking
_generation_progress: Dict[str, Dict[str, Any]] = {}


def get_generation_progress(event_id: str) -> Dict[str, Any]:
    """Get generation progress for event."""
    return _generation_progress.get(event_id, {
        "stage": "unknown",
        "progress": 0,
        "message": "Not found"
    })


def set_generation_progress(event_id: str, stage: str, progress: int, message: str = ""):
    """Set generation progress for event."""
    _generation_progress[event_id] = {
        "stage": stage,
        "progress": progress,
        "message": message,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }


def clear_generation_progress(event_id: str):
    """Clear generation progress after completion."""
    if event_id in _generation_progress:
        del _generation_progress[event_id]


class NewsScheduler:
    """
    Background scheduler for News Intelligence pipeline.
    Uses AsyncIOScheduler to avoid event loop issues.
    
    Schedule:
    - Full pipeline: every 10 minutes
    - Top events generation: every 6 hours
    - Breaking news: instant (score > 90)
    """
    
    def __init__(self, db):
        global _db
        self.db = db
        _db = db
        
    async def run_pipeline_cycle(self) -> Dict[str, Any]:
        """Run one full pipeline cycle."""
        global _last_run_time, _last_run_result
        
        from .pipeline import NewsIntelligencePipeline
        from ..clustering import EventClusteringEngine
        from ..ranking import EventRanker
        
        start_time = datetime.now(timezone.utc)
        results = {
            "started_at": start_time.isoformat(),
            "stages": {}
        }
        
        try:
            pipeline = NewsIntelligencePipeline(self.db)
            
            # 1. Fetch
            logger.info("[Scheduler] Running fetch pipeline...")
            fetch_result = await pipeline.run_fetch_only()
            results["stages"]["fetch"] = fetch_result
            
            # 2. Process (normalize + embed + cluster)
            logger.info("[Scheduler] Running process pipeline...")
            process_result = await pipeline.run_process_only()
            results["stages"]["process"] = process_result
            
            # 3. Merge similar events
            logger.info("[Scheduler] Merging events...")
            clustering = EventClusteringEngine(self.db)
            merge_result = await clustering.merge_similar_events()
            results["stages"]["merge"] = merge_result
            
            # 4. Update rankings
            logger.info("[Scheduler] Updating rankings...")
            ranker = EventRanker(self.db)
            rank_result = await ranker.update_all_scores()
            results["stages"]["rank"] = rank_result
            
            # 5. Run synthesis for confirmed events
            logger.info("[Scheduler] Running synthesis for confirmed events...")
            synthesis_result = await pipeline.run_synthesis_only(limit=3)
            results["stages"]["synthesis"] = synthesis_result
            
            results["ok"] = True
            
        except Exception as e:
            results["ok"] = False
            results["error"] = str(e)
            logger.error(f"[Scheduler] Pipeline error: {e}", exc_info=True)
        
        end_time = datetime.now(timezone.utc)
        results["completed_at"] = end_time.isoformat()
        results["duration_sec"] = (end_time - start_time).total_seconds()
        
        _last_run_time = end_time
        _last_run_result = results
        
        logger.info(f"[Scheduler] Pipeline complete in {results['duration_sec']:.2f}s")
        
        return results
    
    async def run_top_events_generation(self) -> Dict[str, Any]:
        """
        Generate AI articles for top events (every 6 hours).
        Only generates for events with score > 70 and >= 3 sources.
        """
        from ..synthesis.story_builder import StorySynthesizer
        from ..synthesis.image_generator import CoverImageGenerator
        
        logger.info("[Scheduler] Running top events generation...")
        
        results = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "events_processed": 0,
            "events_generated": 0,
            "errors": []
        }
        
        try:
            # Get top events without full stories
            cursor = self.db.news_events.find({
                "status": {"$in": ["confirmed", "developing"]},
                "source_count": {"$gte": 3},
                "$or": [
                    {"fomo_score": {"$gte": 70}},
                    {"confidence_score": {"$gte": 0.7}}
                ],
                "$or": [
                    {"story_en": {"$exists": False}},
                    {"story_en": None},
                    {"story_en": ""}
                ]
            }).sort("fomo_score", -1).limit(3)
            
            events = await cursor.to_list(3)
            results["events_found"] = len(events)
            
            synthesizer = StorySynthesizer(self.db)
            generator = CoverImageGenerator(self.db)
            
            for event in events:
                event_id = event.get("id")
                results["events_processed"] += 1
                
                try:
                    # Set progress
                    set_generation_progress(event_id, "AI_WRITING", 30, "Generating story...")
                    
                    # Generate story in parallel
                    story_data = await synthesizer.generate_full_story_parallel(event)
                    
                    set_generation_progress(event_id, "IMAGE_GENERATION", 70, "Generating image...")
                    
                    # Update event with story
                    await self.db.news_events.update_one(
                        {"id": event_id},
                        {"$set": {
                            **story_data,
                            "story_generated_at": datetime.now(timezone.utc).isoformat()
                        }}
                    )
                    
                    # Generate image
                    await generator.generate_for_event(event)
                    
                    set_generation_progress(event_id, "READY", 100, "Complete")
                    results["events_generated"] += 1
                    
                    # Clear progress after short delay
                    await asyncio.sleep(5)
                    clear_generation_progress(event_id)
                    
                except Exception as e:
                    logger.error(f"[Scheduler] Error generating for {event_id}: {e}")
                    results["errors"].append(f"{event_id}: {str(e)}")
                    set_generation_progress(event_id, "ERROR", 0, str(e))
            
        except Exception as e:
            results["error"] = str(e)
            logger.error(f"[Scheduler] Top events generation error: {e}", exc_info=True)
        
        results["completed_at"] = datetime.now(timezone.utc).isoformat()
        logger.info(f"[Scheduler] Top events generation complete: {results['events_generated']}/{results['events_processed']}")
        
        return results
    
    async def batch_sentiment_backfill(self) -> Dict[str, Any]:
        """
        Batch analyze events without sentiment/importance scores.
        Runs every 5 minutes, processes 50 events at a time.
        """
        from ..scoring.news_intelligence_engine import get_news_intelligence_engine
        
        logger.info("[Scheduler] Running batch sentiment backfill...")
        
        results = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "analyzed": 0,
            "errors": []
        }
        
        try:
            engine = get_news_intelligence_engine(self.db)
            
            # Find events without sentiment
            events = await self.db.news_events.find({
                "$or": [
                    {"sentiment": {"$exists": False}},
                    {"sentiment": None},
                    {"importance_score": {"$exists": False}},
                    {"importance_score": None}
                ]
            }).sort("first_seen_at", -1).limit(50).to_list(50)
            
            results["found"] = len(events)
            
            for event in events:
                try:
                    await engine.update_event_scores(event["id"])
                    results["analyzed"] += 1
                except Exception as e:
                    results["errors"].append(f"{event['id']}: {str(e)}")
            
            logger.info(f"[Scheduler] Batch sentiment: analyzed {results['analyzed']}/{len(events)}")
            
        except Exception as e:
            results["error"] = str(e)
            logger.error(f"[Scheduler] Batch sentiment error: {e}")
        
        results["completed_at"] = datetime.now(timezone.utc).isoformat()
        return results
    
    async def collapse_duplicate_stories(self) -> Dict[str, Any]:
        """
        Run Story Engine to collapse duplicate events into stories.
        Runs every 15 minutes.
        """
        from ..clustering.story_engine import get_story_engine
        
        logger.info("[Scheduler] Running duplicate collapse...")
        
        try:
            story_engine = get_story_engine(self.db)
            result = await story_engine.collapse_existing_events(limit=100)
            logger.info(f"[Scheduler] Story collapse: {result['stories_created']} created, {result['stories_updated']} updated")
            return result
        except Exception as e:
            logger.error(f"[Scheduler] Story collapse error: {e}")
            return {"error": str(e)}
    
    async def check_breaking_news(self) -> Dict[str, Any]:
        """
        Check for breaking news (score > 90) and generate instantly.
        Runs every 3 minutes. Broadcasts via WebSocket.
        """
        from ..synthesis.story_builder import StorySynthesizer
        from ..synthesis.image_generator import CoverImageGenerator
        
        results = {"checked": 0, "generated": 0}
        
        try:
            # Find breaking events without stories
            cursor = self.db.news_events.find({
                "status": "confirmed",
                "fomo_score": {"$gte": 90},
                "$or": [
                    {"story_en": {"$exists": False}},
                    {"story_en": None},
                    {"story_en": ""}
                ]
            }).limit(1)
            
            events = await cursor.to_list(1)
            results["checked"] = 1
            
            if events:
                event = events[0]
                event_id = event.get("id")
                
                logger.info(f"[Scheduler] 🚨 BREAKING NEWS detected: {event_id} (FOMO: {event.get('fomo_score')})")
                
                # Broadcast breaking news alert via WebSocket
                try:
                    from ...websocket import broadcast_breaking_news, broadcast_generation_progress
                    await broadcast_breaking_news(event)
                    await broadcast_generation_progress(event_id, "AI_WRITING", 30, "Breaking news - urgent generation")
                except Exception as ws_err:
                    logger.warning(f"[Scheduler] WebSocket broadcast failed: {ws_err}")
                
                set_generation_progress(event_id, "AI_WRITING", 30, "Breaking news - urgent generation")
                
                synthesizer = StorySynthesizer(self.db)
                story_data = await synthesizer.generate_full_story_parallel(event)
                
                set_generation_progress(event_id, "IMAGE_GENERATION", 70, "Generating image...")
                try:
                    from ...websocket import broadcast_generation_progress
                    await broadcast_generation_progress(event_id, "IMAGE_GENERATION", 70, "Generating cover image...")
                except:
                    pass
                
                await self.db.news_events.update_one(
                    {"id": event_id},
                    {"$set": {
                        **story_data,
                        "is_breaking": True,
                        "story_generated_at": datetime.now(timezone.utc).isoformat()
                    }}
                )
                
                generator = CoverImageGenerator(self.db)
                await generator.generate_for_event(event)
                
                set_generation_progress(event_id, "PUBLISHED", 100, "Breaking news published!")
                results["generated"] = 1
                
                # Broadcast published event
                try:
                    from ...websocket import broadcast_event_published, broadcast_generation_progress
                    updated_event = await self.db.news_events.find_one({"id": event_id})
                    if updated_event:
                        await broadcast_event_published(updated_event)
                    await broadcast_generation_progress(event_id, "PUBLISHED", 100, "Breaking news published!")
                except:
                    pass
                
                await asyncio.sleep(10)
                clear_generation_progress(event_id)
                
        except Exception as e:
            logger.error(f"[Scheduler] Breaking news check error: {e}")
        
        return results
    
    def start(self, interval_seconds: int = 600):
        """Start the background scheduler using AsyncIOScheduler."""
        global _scheduler, _job_count
        
        if _scheduler and _scheduler.running:
            logger.warning("[Scheduler] Already running")
            return False
        
        _scheduler = AsyncIOScheduler()
        
        # Job 1: Main pipeline every 10 minutes
        _scheduler.add_job(
            self.run_pipeline_cycle,
            IntervalTrigger(seconds=interval_seconds),
            id='news_pipeline',
            name='News Pipeline',
            replace_existing=True
        )
        _job_count += 1
        
        # Job 2: Top events generation every 6 hours
        _scheduler.add_job(
            self.run_top_events_generation,
            CronTrigger(hour='*/6'),
            id='top_events_generation',
            name='Top Events AI Generation',
            replace_existing=True
        )
        _job_count += 1
        
        # Job 3: Breaking news check every 3 minutes
        _scheduler.add_job(
            self.check_breaking_news,
            IntervalTrigger(minutes=3),
            id='breaking_news_check',
            name='Breaking News Check',
            replace_existing=True
        )
        _job_count += 1
        
        # Job 4: Batch sentiment backfill every 5 minutes
        _scheduler.add_job(
            self.batch_sentiment_backfill,
            IntervalTrigger(minutes=5),
            id='batch_sentiment_backfill',
            name='Batch Sentiment Backfill',
            replace_existing=True
        )
        _job_count += 1
        
        # Job 5: Duplicate collapse every 15 minutes
        _scheduler.add_job(
            self.collapse_duplicate_stories,
            IntervalTrigger(minutes=15),
            id='duplicate_collapse',
            name='Duplicate Story Collapse',
            replace_existing=True
        )
        _job_count += 1
        
        _scheduler.start()
        
        logger.info(f"[Scheduler] Started with {_job_count} jobs")
        return True
    
    def stop(self):
        """Stop the background scheduler."""
        global _scheduler
        
        if not _scheduler or not _scheduler.running:
            logger.warning("[Scheduler] Not running")
            return False
        
        _scheduler.shutdown(wait=False)
        _scheduler = None
        
        logger.info("[Scheduler] Stopped")
        return True
    
    @staticmethod
    def is_running() -> bool:
        """Check if scheduler is running."""
        return _scheduler is not None and _scheduler.running
    
    @staticmethod
    def get_status() -> Dict[str, Any]:
        """Get scheduler status."""
        global _scheduler, _job_count
        
        jobs = []
        if _scheduler and _scheduler.running:
            for job in _scheduler.get_jobs():
                jobs.append({
                    "id": job.id,
                    "name": job.name,
                    "next_run": str(job.next_run_time) if job.next_run_time else None
                })
        
        return {
            "running": _scheduler is not None and _scheduler.running,
            "job_count": len(jobs),
            "jobs": jobs,
            "last_run_time": _last_run_time.isoformat() if _last_run_time else None,
            "last_run_result": _last_run_result,
            "active_generations": len(_generation_progress),
            "generation_progress": _generation_progress
        }
