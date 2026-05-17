"""
Lead Source Detection Module
=============================

Detects which news sources are fastest at breaking news.
Adjusts source priority based on historical lead times.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class SourceLeadMetrics:
    """Lead detection metrics for a source."""
    source_id: str
    source_name: str = ""
    total_events: int = 0
    first_detections: int = 0
    avg_detection_delay_min: float = 0.0
    lead_score: float = 0.0  # 0-1, higher = faster
    tier: str = "B"  # A=fastest, B=medium, C=slow
    last_updated: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "source_name": self.source_name,
            "total_events": self.total_events,
            "first_detections": self.first_detections,
            "avg_detection_delay_min": round(self.avg_detection_delay_min, 2),
            "lead_score": round(self.lead_score, 3),
            "tier": self.tier,
            "last_updated": self.last_updated
        }


class LeadSourceDetector:
    """
    Detects and ranks news sources by speed.
    
    Features:
    - Tracks which sources break news first
    - Calculates average detection delay
    - Assigns dynamic tiers based on performance
    - Updates scheduler priorities
    """
    
    def __init__(self, db=None):
        self.db = db
        self.metrics: Dict[str, SourceLeadMetrics] = {}
        
        # Tier thresholds
        self.tier_a_threshold = 0.3  # Top 30% lead score → Tier A
        self.tier_b_threshold = 0.1  # 10-30% → Tier B
        # Below 10% → Tier C
        
        # Refresh intervals by tier (minutes)
        self.tier_intervals = {
            "A": 3,   # Fastest sources - check every 3 min
            "B": 10,  # Medium sources - check every 10 min
            "C": 30   # Slow sources - check every 30 min
        }
    
    async def analyze_event_sources(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze which source detected this event first.
        Updates lead metrics for all sources in the event.
        """
        articles = event.get("source_articles", [])
        
        if not articles:
            return {"status": "no_articles"}
        
        # Sort by published time to find first
        sorted_articles = sorted(
            articles,
            key=lambda a: a.get("published_at", "") or a.get("fetched_at", "")
        )
        
        if not sorted_articles:
            return {"status": "no_articles"}
        
        # First article is the lead
        lead_article = sorted_articles[0]
        lead_source = lead_article.get("source_id")
        lead_time = lead_article.get("published_at") or lead_article.get("fetched_at")
        
        if not lead_source or not lead_time:
            return {"status": "missing_data"}
        
        # Parse lead time
        try:
            if isinstance(lead_time, str):
                lead_dt = datetime.fromisoformat(lead_time.replace("Z", "+00:00"))
            else:
                lead_dt = lead_time
        except Exception as e:
            logger.warning(f"Failed to parse lead time: {e}")
            return {"status": "parse_error"}
        
        # Update metrics for all sources in this event
        for article in sorted_articles:
            source_id = article.get("source_id")
            if not source_id:
                continue
            
            # Get or create metrics
            if source_id not in self.metrics:
                self.metrics[source_id] = SourceLeadMetrics(
                    source_id=source_id,
                    source_name=article.get("source_name", source_id)
                )
            
            metrics = self.metrics[source_id]
            metrics.total_events += 1
            
            # Check if this was the lead
            is_lead = source_id == lead_source
            if is_lead:
                metrics.first_detections += 1
            
            # Calculate delay from lead
            article_time = article.get("published_at") or article.get("fetched_at")
            if article_time:
                try:
                    if isinstance(article_time, str):
                        article_dt = datetime.fromisoformat(article_time.replace("Z", "+00:00"))
                    else:
                        article_dt = article_time
                    
                    delay_minutes = (article_dt - lead_dt).total_seconds() / 60
                    
                    # Update rolling average
                    n = metrics.total_events
                    metrics.avg_detection_delay_min = (
                        (metrics.avg_detection_delay_min * (n - 1) + delay_minutes) / n
                    )
                except Exception:
                    pass
            
            # Recalculate lead score
            if metrics.total_events > 0:
                metrics.lead_score = metrics.first_detections / metrics.total_events
            
            metrics.last_updated = datetime.now(timezone.utc).isoformat()
        
        return {
            "status": "success",
            "lead_source": lead_source,
            "sources_updated": len(sorted_articles)
        }
    
    def recalculate_tiers(self) -> Dict[str, List[str]]:
        """
        Recalculate source tiers based on lead scores.
        Returns dict of tier -> source_ids.
        """
        if not self.metrics:
            return {"A": [], "B": [], "C": []}
        
        # Sort by lead score
        sorted_sources = sorted(
            self.metrics.values(),
            key=lambda m: m.lead_score,
            reverse=True
        )
        
        tiers = {"A": [], "B": [], "C": []}
        
        for metrics in sorted_sources:
            if metrics.lead_score >= self.tier_a_threshold:
                metrics.tier = "A"
                tiers["A"].append(metrics.source_id)
            elif metrics.lead_score >= self.tier_b_threshold:
                metrics.tier = "B"
                tiers["B"].append(metrics.source_id)
            else:
                metrics.tier = "C"
                tiers["C"].append(metrics.source_id)
        
        logger.info(f"[LeadDetection] Tiers: A={len(tiers['A'])}, B={len(tiers['B'])}, C={len(tiers['C'])}")
        
        return tiers
    
    def get_source_tier(self, source_id: str) -> str:
        """Get tier for a source."""
        if source_id in self.metrics:
            return self.metrics[source_id].tier
        return "B"  # Default tier
    
    def get_refresh_interval(self, source_id: str) -> int:
        """Get recommended refresh interval in minutes."""
        tier = self.get_source_tier(source_id)
        return self.tier_intervals.get(tier, 10)
    
    def get_all_metrics(self) -> List[Dict[str, Any]]:
        """Get all source lead metrics."""
        return [m.to_dict() for m in sorted(
            self.metrics.values(),
            key=lambda m: m.lead_score,
            reverse=True
        )]
    
    def get_lead_ranking(self, top_n: int = 10) -> List[Dict[str, Any]]:
        """Get top lead sources."""
        return self.get_all_metrics()[:top_n]
    
    async def save_to_db(self) -> int:
        """Save metrics to database."""
        if self.db is None:
            return 0
        
        saved = 0
        for source_id, metrics in self.metrics.items():
            await self.db.source_lead_metrics.update_one(
                {"source_id": source_id},
                {"$set": metrics.to_dict()},
                upsert=True
            )
            saved += 1
        
        return saved
    
    async def load_from_db(self) -> int:
        """Load metrics from database."""
        if self.db is None:
            return 0
        
        cursor = self.db.source_lead_metrics.find({})
        loaded = 0
        
        async for doc in cursor:
            source_id = doc.get("source_id")
            if source_id:
                self.metrics[source_id] = SourceLeadMetrics(
                    source_id=source_id,
                    source_name=doc.get("source_name", ""),
                    total_events=doc.get("total_events", 0),
                    first_detections=doc.get("first_detections", 0),
                    avg_detection_delay_min=doc.get("avg_detection_delay_min", 0.0),
                    lead_score=doc.get("lead_score", 0.0),
                    tier=doc.get("tier", "B"),
                    last_updated=doc.get("last_updated")
                )
                loaded += 1
        
        if loaded > 0:
            self.recalculate_tiers()
        
        return loaded
    
    async def analyze_all_events(self) -> Dict[str, Any]:
        """Analyze all events in database to build lead metrics."""
        if self.db is None:
            return {"error": "No database"}
        
        # Reset metrics
        self.metrics = {}
        
        # Get all events with multiple sources
        cursor = self.db.news_events.find({
            "source_count": {"$gte": 2}
        })
        
        analyzed = 0
        async for event in cursor:
            await self.analyze_event_sources(event)
            analyzed += 1
        
        # Recalculate tiers
        tiers = self.recalculate_tiers()
        
        # Save to DB
        await self.save_to_db()
        
        return {
            "events_analyzed": analyzed,
            "sources_tracked": len(self.metrics),
            "tiers": {k: len(v) for k, v in tiers.items()}
        }


# Global instance
_lead_detector: Optional[LeadSourceDetector] = None


def get_lead_detector() -> LeadSourceDetector:
    """Get global lead detector instance."""
    global _lead_detector
    if _lead_detector is None:
        _lead_detector = LeadSourceDetector()
    return _lead_detector


def set_lead_detector_db(db):
    """Set database for lead detector."""
    global _lead_detector
    if _lead_detector is None:
        _lead_detector = LeadSourceDetector(db)
    else:
        _lead_detector.db = db
