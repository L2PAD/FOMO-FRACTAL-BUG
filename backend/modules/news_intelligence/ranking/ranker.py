"""
Event Ranking Engine
====================

Calculates feed scores and ranks events for display.
"""

import logging
from typing import Dict, Any, List
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# SCORING WEIGHTS
# ═══════════════════════════════════════════════════════════════

WEIGHTS = {
    "freshness": 0.35,
    "importance": 0.20,
    "confidence": 0.20,
    "source_quality": 0.15,
    "market_relevance": 0.10
}

# High importance event types
HIGH_IMPORTANCE_TYPES = [
    "regulation", "hack", "exploit", "funding", "listing", "legal"
]

# High importance assets
HIGH_IMPORTANCE_ASSETS = [
    "BTC", "ETH", "SOL", "BNB", "XRP", "USDT", "USDC"
]

# High importance orgs
HIGH_IMPORTANCE_ORGS = [
    "SEC", "CFTC", "Fed", "BlackRock", "Fidelity", "Grayscale",
    "Binance", "Coinbase", "a16z", "Paradigm"
]


class EventRanker:
    """Calculates event scores and rankings."""
    
    def __init__(self, db):
        self.db = db
    
    def _calculate_freshness(self, first_seen: datetime, last_seen: datetime) -> float:
        """Calculate freshness score (0-1)."""
        now = datetime.now(timezone.utc)
        
        # Use last_seen for freshness
        if isinstance(last_seen, str):
            try:
                last_seen = datetime.fromisoformat(last_seen.replace('Z', '+00:00'))
            except:
                last_seen = now
        
        # Ensure timezone aware
        if last_seen and last_seen.tzinfo is None:
            last_seen = last_seen.replace(tzinfo=timezone.utc)
        
        if not last_seen:
            return 0.5
        
        diff = (now - last_seen).total_seconds()
        hours = diff / 3600
        
        if hours < 1:
            return 1.0
        elif hours < 3:
            return 0.95
        elif hours < 6:
            return 0.85
        elif hours < 12:
            return 0.70
        elif hours < 24:
            return 0.50
        elif hours < 48:
            return 0.30
        else:
            return max(0.1, 1.0 - (hours / 168))  # Decay over 1 week
    
    def _calculate_importance(self, event: Dict) -> float:
        """Calculate importance score (0-1)."""
        score = 0.3  # Base score
        
        # Event type importance
        event_type = event.get("event_type", "news")
        if event_type in HIGH_IMPORTANCE_TYPES:
            score += 0.3
        
        # Asset importance
        assets = event.get("primary_assets", [])
        high_assets = sum(1 for a in assets if a in HIGH_IMPORTANCE_ASSETS)
        score += min(0.2, high_assets * 0.05)
        
        # Organization importance
        orgs = event.get("organizations", [])
        high_orgs = sum(1 for o in orgs if o in HIGH_IMPORTANCE_ORGS)
        score += min(0.2, high_orgs * 0.1)
        
        return min(1.0, score)
    
    def _calculate_confidence(self, event: Dict) -> float:
        """Calculate confidence score (0-1)."""
        source_count = event.get("source_count", 1)
        status = event.get("status", "candidate")
        
        # Base confidence from status
        status_scores = {
            "candidate": 0.3,
            "developing": 0.5,
            "confirmed": 0.8,
            "official": 0.95
        }
        base = status_scores.get(status, 0.3)
        
        # Boost for more sources
        source_boost = min(0.2, source_count * 0.05)
        
        # Use extracted confidence if available
        facts = event.get("extracted_facts", [])
        if facts:
            avg_confidence = sum(f.get("confidence", 0.5) for f in facts) / len(facts)
            base = (base + avg_confidence) / 2
        
        return min(1.0, base + source_boost)
    
    def _calculate_source_quality(self, event: Dict) -> float:
        """Calculate source quality score (0-1)."""
        from ..ingestion import get_source_weight
        
        # Get weights for all sources
        article_ids = event.get("article_ids", [])
        if not article_ids:
            return 0.5
        
        # Simple heuristic: more sources = higher quality
        source_count = event.get("source_count", 1)
        
        # Boost for official sources
        if event.get("status") == "official":
            return 0.95
        
        # Base on source count
        if source_count >= 5:
            return 0.9
        elif source_count >= 3:
            return 0.75
        elif source_count >= 2:
            return 0.6
        else:
            return 0.4
    
    def _calculate_market_relevance(self, event: Dict) -> float:
        """Calculate market relevance score (0-1)."""
        score = 0.3  # Base
        
        # Has major assets
        assets = event.get("primary_assets", [])
        if any(a in HIGH_IMPORTANCE_ASSETS for a in assets):
            score += 0.3
        
        # Is market-moving event type
        event_type = event.get("event_type", "news")
        market_moving = ["listing", "delisting", "hack", "regulation", "funding"]
        if event_type in market_moving:
            score += 0.3
        
        # Has amounts (concrete numbers)
        facts = event.get("extracted_facts", [])
        for f in facts:
            if f.get("amounts"):
                score += 0.1
                break
        
        return min(1.0, score)
    
    def calculate_feed_score(self, event: Dict) -> float:
        """Calculate final feed score."""
        scores = {
            "freshness": self._calculate_freshness(
                event.get("first_seen_at"),
                event.get("last_seen_at")
            ),
            "importance": self._calculate_importance(event),
            "confidence": self._calculate_confidence(event),
            "source_quality": self._calculate_source_quality(event),
            "market_relevance": self._calculate_market_relevance(event)
        }
        
        final_score = sum(scores[k] * WEIGHTS[k] for k in WEIGHTS)
        
        return round(final_score, 4)
    
    def calculate_fomo_score(self, event: Dict) -> float:
        """Calculate FOMO score (hype/urgency indicator)."""
        score = 30  # Base
        
        # Freshness boost
        freshness = self._calculate_freshness(
            event.get("first_seen_at"),
            event.get("last_seen_at")
        )
        score += freshness * 20
        
        # Viral potential
        event_type = event.get("event_type", "news")
        viral_types = ["hack", "airdrop", "listing", "regulation"]
        if event_type in viral_types:
            score += 20
        
        # Asset popularity
        assets = event.get("primary_assets", [])
        popular = ["BTC", "ETH", "SOL", "DOGE", "PEPE", "SHIB"]
        if any(a in popular for a in assets):
            score += 15
        
        # Source confirmation
        if event.get("source_count", 1) >= 3:
            score += 15
        
        return min(99, int(score))
    
    async def update_event_scores(self, event_id: str) -> Dict[str, Any]:
        """Update scores for an event."""
        event = await self.db.news_events.find_one({"id": event_id})
        if not event:
            return {"ok": False, "error": "Event not found"}
        
        feed_score = self.calculate_feed_score(event)
        fomo_score = self.calculate_fomo_score(event)
        importance_score = self._calculate_importance(event)
        freshness_score = self._calculate_freshness(
            event.get("first_seen_at"),
            event.get("last_seen_at")
        )
        
        await self.db.news_events.update_one(
            {"id": event_id},
            {"$set": {
                "feed_score": feed_score,
                "fomo_score": fomo_score,
                "importance_score": importance_score,
                "freshness_score": freshness_score
            }}
        )
        
        return {
            "ok": True,
            "event_id": event_id,
            "feed_score": feed_score,
            "fomo_score": fomo_score
        }
    
    async def update_all_scores(self) -> Dict[str, Any]:
        """Update scores for all active events."""
        results = {
            "updated": 0,
            "errors": 0
        }
        
        cursor = self.db.news_events.find({
            "status": {"$in": ["candidate", "developing", "confirmed", "official"]}
        })
        
        async for event in cursor:
            try:
                await self.update_event_scores(event["id"])
                results["updated"] += 1
            except Exception as e:
                results["errors"] += 1
                logger.error(f"[Ranker] Error updating {event['id']}: {e}")
        
        return results
    
    async def get_ranked_events(self, limit: int = 50, 
                                event_type: str = None,
                                asset: str = None,
                                min_confidence: float = 0.0) -> List[Dict]:
        """Get ranked events for feed."""
        query = {
            "status": {"$in": ["developing", "confirmed", "official"]},
            "confidence_score": {"$gte": min_confidence}
        }
        
        if event_type:
            query["event_type"] = event_type
        
        if asset:
            query["primary_assets"] = asset
        
        cursor = self.db.news_events.find(query).sort(
            "feed_score", -1
        ).limit(limit)
        
        events = []
        async for event in cursor:
            events.append(event)
        
        return events
