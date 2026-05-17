"""
Event Confidence Engine
========================
Calculates confidence score for news events based on multiple factors.

Confidence is different from importance:
- importance_score → how interesting/impactful the news is
- confidence_score → how trustworthy/verified the news is

Formula:
confidence_score = 0.40 * source_quality + 0.30 * source_count + 0.20 * source_diversity + 0.10 * time_confirmation

Levels:
- 0-40: LOW (unconfirmed)
- 40-70: MEDIUM
- 70-90: HIGH
- 90+: CONFIRMED

Usage:
    engine = ConfidenceEngine(db)
    result = await engine.calculate_confidence(event)
"""

import logging
import math
from typing import Dict, Any, Optional, List, Set
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# CONFIDENCE LEVELS
# ═══════════════════════════════════════════════════════════════

CONFIDENCE_LEVELS = {
    "LOW": (0, 40),
    "MEDIUM": (40, 70),
    "HIGH": (70, 90),
    "CONFIRMED": (90, 100)
}


def get_confidence_level(score: float) -> str:
    """Get confidence level from score."""
    for level, (low, high) in CONFIDENCE_LEVELS.items():
        if low <= score < high:
            return level
    return "CONFIRMED" if score >= 90 else "LOW"


# ═══════════════════════════════════════════════════════════════
# CONFIDENCE ENGINE
# ═══════════════════════════════════════════════════════════════

class ConfidenceEngine:
    """
    Calculates event confidence based on source reliability.
    
    Factors:
    1. Source Quality (40%) - Average weight of sources
    2. Source Count (30%) - Number of sources reporting
    3. Source Diversity (20%) - Unique domains/categories
    4. Time Confirmation (10%) - How long event has been confirmed
    """
    
    WEIGHTS = {
        "source_quality": 0.40,
        "source_count": 0.30,
        "source_diversity": 0.20,
        "time_confirmation": 0.10
    }
    
    def __init__(self, db):
        self.db = db
        self._reliability_manager = None
    
    async def _get_reliability_manager(self):
        """Get SourceReliabilityManager."""
        if self._reliability_manager is None:
            from .source_reliability import get_source_reliability_manager
            self._reliability_manager = get_source_reliability_manager(self.db)
        return self._reliability_manager
    
    async def calculate_source_quality(self, sources: List[str]) -> float:
        """
        Calculate average source quality.
        Returns 0.0-1.0.
        """
        if not sources:
            return 0.3  # Low default for unknown sources
        
        manager = await self._get_reliability_manager()
        
        weights = []
        for source in sources:
            weight = await manager.get_weight(source)
            weights.append(weight)
        
        # Average of all source weights
        return sum(weights) / len(weights) if weights else 0.3
    
    def calculate_source_count_score(self, count: int) -> float:
        """
        Calculate score based on number of sources.
        Formula: min(log(count + 1) / log(6), 1)
        
        1 source → 0.39
        2 sources → 0.61
        3 sources → 0.77
        5 sources → 0.96
        6+ sources → 1.0
        """
        if count <= 0:
            return 0
        return min(1.0, math.log(count + 1) / math.log(6))
    
    def calculate_source_diversity(self, sources: List[str], source_ids: List[str] = None) -> float:
        """
        Calculate source diversity score.
        Higher if sources are from different domains/categories.
        """
        if not sources:
            return 0
        
        # Extract unique domains
        unique_domains: Set[str] = set()
        for source in sources:
            # Normalize and extract domain-like identifier
            domain = source.lower().replace("_", ".").split(".")[0]
            unique_domains.add(domain)
        
        # Diversity = unique_domains / total_sources
        diversity = len(unique_domains) / len(sources) if sources else 0
        
        return diversity
    
    def calculate_time_confirmation(self, first_seen_at: str, source_count: int) -> float:
        """
        Calculate time-based confirmation score.
        Higher if event has been confirmed over time with multiple sources.
        
        Formula: min(hours_since_first / 3, 1)
        """
        if not first_seen_at:
            return 0.5
        
        try:
            first_seen = datetime.fromisoformat(first_seen_at.replace('Z', '+00:00'))
            now = datetime.now(timezone.utc)
            hours_elapsed = (now - first_seen).total_seconds() / 3600
            
            # More sources over time = higher confirmation
            if source_count >= 3:
                return min(1.0, hours_elapsed / 2)  # Faster confirmation with multiple sources
            else:
                return min(1.0, hours_elapsed / 6)  # Slower confirmation with single source
                
        except Exception:
            return 0.5
    
    async def calculate_confidence(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate full confidence score for an event.
        
        Returns:
        - confidence_score: 0-100
        - confidence_level: LOW/MEDIUM/HIGH/CONFIRMED
        - breakdown: individual factor scores
        """
        sources = event.get("sources", [])
        source_ids = event.get("source_ids", [])
        source_count = event.get("source_count", len(sources) or 1)
        first_seen_at = event.get("first_seen_at")
        
        # If no explicit sources, try to extract from source_ids
        if not sources and source_ids:
            sources = source_ids
        
        # Calculate components
        source_quality = await self.calculate_source_quality(sources)
        source_count_score = self.calculate_source_count_score(source_count)
        source_diversity = self.calculate_source_diversity(sources, source_ids)
        time_confirmation = self.calculate_time_confirmation(first_seen_at, source_count)
        
        # Calculate weighted score
        raw_score = (
            self.WEIGHTS["source_quality"] * source_quality +
            self.WEIGHTS["source_count"] * source_count_score +
            self.WEIGHTS["source_diversity"] * source_diversity +
            self.WEIGHTS["time_confirmation"] * time_confirmation
        )
        
        # Convert to 0-100 and clamp
        confidence_score = max(0, min(100, round(raw_score * 100, 1)))
        confidence_level = get_confidence_level(confidence_score)
        
        return {
            "confidence_score": confidence_score,
            "confidence_level": confidence_level,
            "breakdown": {
                "source_quality": round(source_quality * 100, 1),
                "source_count": round(source_count_score * 100, 1),
                "source_diversity": round(source_diversity * 100, 1),
                "time_confirmation": round(time_confirmation * 100, 1)
            },
            "factors": {
                "sources_analyzed": len(sources),
                "source_count": source_count,
                "unique_domains": len(set(s.lower().split("_")[0] for s in sources)) if sources else 0
            }
        }
    
    async def update_event_confidence(self, event_id: str) -> Dict[str, Any]:
        """Update confidence score for a specific event."""
        event = await self.db.news_events.find_one({"id": event_id})
        if not event:
            return {"ok": False, "error": "Event not found"}
        
        result = await self.calculate_confidence(event)
        
        # Update event
        await self.db.news_events.update_one(
            {"id": event_id},
            {"$set": {
                "confidence_score": result["confidence_score"],
                "confidence_level": result["confidence_level"],
                "confidence_breakdown": result["breakdown"],
                "confidence_updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        
        return {
            "ok": True,
            "event_id": event_id,
            **result
        }
    
    async def batch_update_confidence(self, limit: int = 50) -> Dict[str, Any]:
        """Batch update confidence for events without scores."""
        results = {
            "processed": 0,
            "updated": 0,
            "errors": []
        }
        
        # Find events without confidence_level
        cursor = self.db.news_events.find({
            "$or": [
                {"confidence_level": {"$exists": False}},
                {"confidence_level": None}
            ]
        }).limit(limit)
        
        events = await cursor.to_list(limit)
        results["found"] = len(events)
        
        for event in events:
            try:
                await self.update_event_confidence(event["id"])
                results["updated"] += 1
            except Exception as e:
                results["errors"].append(f"{event['id']}: {str(e)}")
            results["processed"] += 1
        
        return results


# ═══════════════════════════════════════════════════════════════
# SINGLETON ACCESS
# ═══════════════════════════════════════════════════════════════

_confidence_engine: Optional[ConfidenceEngine] = None


def get_confidence_engine(db) -> ConfidenceEngine:
    """Get or create ConfidenceEngine singleton."""
    global _confidence_engine
    if _confidence_engine is None:
        _confidence_engine = ConfidenceEngine(db)
    return _confidence_engine
