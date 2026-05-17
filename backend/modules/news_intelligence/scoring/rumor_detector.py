"""
Rumor Detection Layer
======================
Detects rumors, speculation, and unconfirmed news using keyword analysis.

Even if news is reported by sources, it may be:
- rumor
- speculation
- fake
- unconfirmed

This layer analyzes text for rumor indicators and adjusts confidence.

Rumor Keywords:
- "may", "might", "could", "reportedly", "allegedly"
- "sources say", "unconfirmed", "rumored", "speculation"

Classes:
- 0-30: CONFIRMED
- 30-60: SPECULATION
- 60-100: RUMOR

Usage:
    detector = RumorDetector(db)
    result = await detector.analyze(event)
"""

import logging
import re
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# RUMOR KEYWORDS AND WEIGHTS
# ═══════════════════════════════════════════════════════════════

# Keywords that indicate speculation/rumor with their penalty weight
RUMOR_KEYWORDS = {
    # High indicators (20+ points)
    "rumor": 25,
    "rumored": 25,
    "rumoured": 25,
    "allegedly": 20,
    "unconfirmed": 20,
    "unverified": 20,
    "speculation": 20,
    "speculated": 20,
    
    # Medium indicators (10-15 points)
    "reportedly": 15,
    "sources say": 15,
    "sources claim": 15,
    "insiders say": 15,
    "insider says": 15,
    "according to sources": 15,
    "anonymous sources": 18,
    "unnamed sources": 18,
    "people familiar": 12,
    
    # Low indicators (5-10 points)
    "may": 8,
    "might": 8,
    "could": 8,
    "possibly": 10,
    "potential": 5,
    "potentially": 5,
    "expected to": 5,
    "likely to": 5,
    "appears to": 7,
    "seems to": 7,
    "believed to": 10,
    "thought to": 10,
    "considered": 5,
    
    # Very low (3-5 points)
    "plans to": 3,
    "planning to": 3,
    "exploring": 4,
    "considering": 4,
    "looking to": 3,
    "in talks": 5,
    "discussions": 4,
    "negotiations": 4,
}

# Keywords that CONFIRM news (reduce rumor score)
CONFIRMATION_KEYWORDS = {
    "confirmed": -25,
    "officially": -20,
    "official": -15,
    "announced": -15,
    "announcement": -15,
    "press release": -20,
    "statement": -10,
    "verified": -20,
    "disclosed": -15,
    "filed": -15,  # SEC filing, etc.
    "approved": -20,
    "signed": -15,
    "launched": -15,
    "completed": -15,
}


# ═══════════════════════════════════════════════════════════════
# RUMOR LEVELS
# ═══════════════════════════════════════════════════════════════

RUMOR_LEVELS = {
    "CONFIRMED": (0, 30),
    "SPECULATION": (30, 60),
    "RUMOR": (60, 100)
}


def get_rumor_level(score: float) -> str:
    """Get rumor level from score."""
    for level, (low, high) in RUMOR_LEVELS.items():
        if low <= score < high:
            return level
    return "RUMOR" if score >= 60 else "CONFIRMED"


# ═══════════════════════════════════════════════════════════════
# RUMOR DETECTOR
# ═══════════════════════════════════════════════════════════════

class RumorDetector:
    """
    Analyzes news text for rumor/speculation indicators.
    
    Returns:
    - rumor_score: 0-100 (higher = more likely rumor)
    - rumor_level: CONFIRMED/SPECULATION/RUMOR
    - keywords_detected: list of detected rumor keywords
    - confidence_adjustment: how much to adjust confidence_score
    """
    
    def __init__(self, db):
        self.db = db
    
    def analyze_text(self, text: str) -> Dict[str, Any]:
        """
        Analyze text for rumor indicators.
        """
        if not text:
            return {
                "rumor_score": 50,
                "rumor_level": "SPECULATION",
                "keywords_detected": [],
                "confirmation_keywords": [],
                "confidence_adjustment": 0
            }
        
        text_lower = text.lower()
        
        # Detect rumor keywords
        detected_rumors: List[Tuple[str, int]] = []
        total_rumor_weight = 0
        
        for keyword, weight in RUMOR_KEYWORDS.items():
            # Use word boundary matching for short words
            if len(keyword) <= 4:
                pattern = r'\b' + re.escape(keyword) + r'\b'
                if re.search(pattern, text_lower):
                    detected_rumors.append((keyword, weight))
                    total_rumor_weight += weight
            else:
                if keyword in text_lower:
                    detected_rumors.append((keyword, weight))
                    total_rumor_weight += weight
        
        # Detect confirmation keywords
        detected_confirmations: List[Tuple[str, int]] = []
        total_confirm_weight = 0
        
        for keyword, weight in CONFIRMATION_KEYWORDS.items():
            if keyword in text_lower:
                detected_confirmations.append((keyword, weight))
                total_confirm_weight += weight  # weight is negative
        
        # Calculate base score
        # Start at 30 (neutral-low), add rumor weight, subtract confirmation weight
        base_score = 30
        raw_score = base_score + total_rumor_weight + total_confirm_weight
        
        # Clamp to 0-100
        rumor_score = max(0, min(100, raw_score))
        rumor_level = get_rumor_level(rumor_score)
        
        # Calculate confidence adjustment
        # High rumor score = negative adjustment
        if rumor_score >= 70:
            confidence_adjustment = -30
        elif rumor_score >= 50:
            confidence_adjustment = -15
        elif rumor_score >= 30:
            confidence_adjustment = 0
        else:
            confidence_adjustment = 10  # Confirmed news boosts confidence
        
        return {
            "rumor_score": round(rumor_score, 1),
            "rumor_level": rumor_level,
            "keywords_detected": [k for k, w in detected_rumors],
            "confirmation_keywords": [k for k, w in detected_confirmations],
            "rumor_weight": total_rumor_weight,
            "confirmation_weight": abs(total_confirm_weight),
            "confidence_adjustment": confidence_adjustment
        }
    
    async def analyze_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze an event for rumor indicators.
        Combines title + summary for analysis.
        """
        title = event.get("title_en") or event.get("title_seed") or ""
        summary = event.get("summary_en") or event.get("ai_summary") or ""
        
        # Combine text for analysis (title weighted more heavily)
        combined_text = f"{title} {title} {summary}"  # Title appears twice for weighting
        
        result = self.analyze_text(combined_text)
        
        # Additional factors
        source_count = event.get("source_count", 1)
        
        # Multiple sources reduce rumor score
        if source_count >= 5:
            result["rumor_score"] = max(0, result["rumor_score"] - 15)
        elif source_count >= 3:
            result["rumor_score"] = max(0, result["rumor_score"] - 10)
        elif source_count >= 2:
            result["rumor_score"] = max(0, result["rumor_score"] - 5)
        elif source_count == 1:
            result["rumor_score"] = min(100, result["rumor_score"] + 10)
        
        # Recalculate level after adjustments
        result["rumor_level"] = get_rumor_level(result["rumor_score"])
        
        # Recalculate confidence adjustment
        if result["rumor_score"] >= 70:
            result["confidence_adjustment"] = -30
        elif result["rumor_score"] >= 50:
            result["confidence_adjustment"] = -15
        elif result["rumor_score"] >= 30:
            result["confidence_adjustment"] = 0
        else:
            result["confidence_adjustment"] = 10
        
        result["source_count_factor"] = source_count
        
        return result
    
    async def update_event_rumor_status(self, event_id: str) -> Dict[str, Any]:
        """Update rumor status for a specific event."""
        event = await self.db.news_events.find_one({"id": event_id})
        if not event:
            return {"ok": False, "error": "Event not found"}
        
        result = await self.analyze_event(event)
        
        # Update event
        await self.db.news_events.update_one(
            {"id": event_id},
            {"$set": {
                "rumor_score": result["rumor_score"],
                "rumor_level": result["rumor_level"],
                "rumor_keywords": result["keywords_detected"],
                "confirmation_keywords": result["confirmation_keywords"],
                "rumor_analyzed_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        
        return {
            "ok": True,
            "event_id": event_id,
            **result
        }
    
    async def batch_analyze_rumors(self, limit: int = 50) -> Dict[str, Any]:
        """Batch analyze events for rumor detection."""
        results = {
            "processed": 0,
            "rumors_detected": 0,
            "confirmed": 0,
            "speculation": 0,
            "errors": []
        }
        
        # Find events without rumor analysis
        cursor = self.db.news_events.find({
            "$or": [
                {"rumor_level": {"$exists": False}},
                {"rumor_level": None}
            ]
        }).limit(limit)
        
        events = await cursor.to_list(limit)
        results["found"] = len(events)
        
        for event in events:
            try:
                r = await self.update_event_rumor_status(event["id"])
                if r.get("ok"):
                    level = r.get("rumor_level")
                    if level == "RUMOR":
                        results["rumors_detected"] += 1
                    elif level == "CONFIRMED":
                        results["confirmed"] += 1
                    else:
                        results["speculation"] += 1
            except Exception as e:
                results["errors"].append(f"{event['id']}: {str(e)}")
            results["processed"] += 1
        
        return results


# ═══════════════════════════════════════════════════════════════
# SINGLETON ACCESS
# ═══════════════════════════════════════════════════════════════

_rumor_detector: Optional[RumorDetector] = None


def get_rumor_detector(db) -> RumorDetector:
    """Get or create RumorDetector singleton."""
    global _rumor_detector
    if _rumor_detector is None:
        _rumor_detector = RumorDetector(db)
    return _rumor_detector
