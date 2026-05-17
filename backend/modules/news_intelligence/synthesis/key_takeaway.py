"""
Key Takeaway Generator
=======================
Generates concise "KEY TAKEAWAY" summaries for news events.

Provides a one-liner insight that makes the news actionable.

Examples:
- "BlackRock updated its ETF filing after SEC feedback. Approval probability increased."
- "SEC delays decision - expect volatility until new deadline in March."
- "Exchange hack confirmed - withdraw funds from affected platform immediately."

Usage:
    generator = KeyTakeawayGenerator(db)
    takeaway = await generator.generate(event)
"""

import logging
import re
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# KEY TAKEAWAY TEMPLATES
# ═══════════════════════════════════════════════════════════════

# Event type to template mapping
TAKEAWAY_TEMPLATES = {
    # Regulatory
    "etf_filing": "{entity} {action} ETF filing. {implication}",
    "sec_decision": "SEC {action} - {implication}",
    "regulatory": "Regulatory {action} by {entity}. {implication}",
    
    # Market
    "price_move": "{asset} {direction} {magnitude}. {implication}",
    "whale_move": "Large {asset} {action} detected. {implication}",
    "exchange": "{entity} {action}. {implication}",
    
    # Security
    "hack": "Security incident at {entity}. {implication}",
    "exploit": "{asset} {action} exploited. {implication}",
    
    # Corporate
    "partnership": "{entity1} partners with {entity2}. {implication}",
    "funding": "{entity} raises {amount}. {implication}",
    "launch": "{entity} launches {product}. {implication}",
    
    # Default
    "default": "{summary}. {implication}"
}

# Sentiment-based implications
IMPLICATIONS = {
    "positive": [
        "Bullish signal.",
        "Positive for market sentiment.",
        "Consider accumulation.",
        "Watch for follow-through.",
        "Institutional interest increasing."
    ],
    "negative": [
        "Exercise caution.",
        "Risk-off sentiment.",
        "Consider reducing exposure.",
        "Monitor for further developments.",
        "Volatility expected."
    ],
    "neutral": [
        "Monitor developments.",
        "No immediate action required.",
        "Wait for confirmation.",
        "Situation developing."
    ]
}


# ═══════════════════════════════════════════════════════════════
# KEY TAKEAWAY GENERATOR
# ═══════════════════════════════════════════════════════════════

class KeyTakeawayGenerator:
    """
    Generates concise, actionable takeaways from news events.
    
    Output format:
    - First sentence: What happened (factual)
    - Second sentence: What it means (implication)
    
    Max length: ~150 characters
    """
    
    def __init__(self, db):
        self.db = db
    
    def generate_from_event(self, event: Dict[str, Any]) -> str:
        """
        Generate key takeaway from event data.
        """
        title = event.get("title_en") or event.get("title_seed") or ""
        summary = event.get("summary_en") or event.get("ai_summary") or ""
        sentiment = event.get("sentiment", "neutral")
        event_type = event.get("event_type", "news")
        assets = event.get("primary_assets", [])
        entities = event.get("primary_entities", [])
        importance = event.get("importance_score", 50)
        
        # Extract key information
        main_asset = assets[0] if assets else ""
        main_entity = entities[0] if entities else ""
        
        # Detect event type from content
        detected_type = self._detect_event_type(title, summary)
        
        # Generate factual part
        factual = self._generate_factual(title, summary, detected_type, main_asset, main_entity)
        
        # Generate implication
        implication = self._generate_implication(sentiment, detected_type, importance)
        
        # Combine
        takeaway = f"{factual} {implication}"
        
        # Truncate if too long
        if len(takeaway) > 200:
            takeaway = takeaway[:197] + "..."
        
        return takeaway
    
    def _detect_event_type(self, title: str, summary: str) -> str:
        """Detect event type from content."""
        text = (title + " " + summary).lower()
        
        if any(word in text for word in ["etf", "filing", "sec approval"]):
            return "etf_filing"
        elif any(word in text for word in ["sec", "cftc", "regulator", "regulation"]):
            return "regulatory"
        elif any(word in text for word in ["hack", "stolen", "breach", "attack"]):
            return "hack"
        elif any(word in text for word in ["exploit", "vulnerability", "drained"]):
            return "exploit"
        elif any(word in text for word in ["partner", "partnership", "collaboration"]):
            return "partnership"
        elif any(word in text for word in ["raises", "funding", "investment", "million", "billion"]):
            return "funding"
        elif any(word in text for word in ["launch", "releases", "introduces", "announces"]):
            return "launch"
        elif any(word in text for word in ["whale", "large transfer", "moved"]):
            return "whale_move"
        elif any(word in text for word in ["price", "rally", "dump", "crash", "surge"]):
            return "price_move"
        elif any(word in text for word in ["exchange", "binance", "coinbase", "kraken"]):
            return "exchange"
        else:
            return "default"
    
    def _generate_factual(
        self, 
        title: str, 
        summary: str, 
        event_type: str,
        main_asset: str,
        main_entity: str
    ) -> str:
        """Generate factual sentence."""
        # Clean and truncate summary
        clean_summary = summary.replace("\n", " ").strip()
        
        # Use first sentence of summary if available
        first_sentence = clean_summary.split(".")[0] if clean_summary else title
        
        # Limit length
        if len(first_sentence) > 100:
            # Find last space before 100 chars
            truncate_at = first_sentence[:100].rfind(" ")
            if truncate_at > 50:
                first_sentence = first_sentence[:truncate_at] + "..."
            else:
                first_sentence = first_sentence[:97] + "..."
        
        # Ensure ends with period
        if first_sentence and not first_sentence.endswith((".","!","?")):
            first_sentence += "."
        
        return first_sentence
    
    def _generate_implication(
        self, 
        sentiment: str, 
        event_type: str, 
        importance: float
    ) -> str:
        """Generate implication sentence."""
        import random
        
        # Get implications list based on sentiment
        implications_list = IMPLICATIONS.get(sentiment, IMPLICATIONS["neutral"])
        
        # Select based on importance
        if importance >= 80:
            # High importance - use stronger implications
            if sentiment == "positive":
                return "Major bullish catalyst."
            elif sentiment == "negative":
                return "Significant risk event - monitor closely."
            else:
                return "Major development - watch for market reaction."
        elif importance >= 60:
            return random.choice(implications_list)
        else:
            # Lower importance - more neutral
            return "Monitor for further updates."
    
    async def generate(self, event_id: str) -> Dict[str, Any]:
        """
        Generate and save key takeaway for an event.
        """
        event = await self.db.news_events.find_one({"id": event_id})
        if not event:
            return {"ok": False, "error": "Event not found"}
        
        takeaway = self.generate_from_event(event)
        
        # Update event
        await self.db.news_events.update_one(
            {"id": event_id},
            {"$set": {
                "key_takeaway": takeaway,
                "takeaway_generated_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        
        return {
            "ok": True,
            "event_id": event_id,
            "key_takeaway": takeaway
        }
    
    async def batch_generate(self, limit: int = 50) -> Dict[str, Any]:
        """Batch generate takeaways for events without them."""
        results = {
            "processed": 0,
            "generated": 0,
            "errors": []
        }
        
        # Find events without takeaway
        cursor = self.db.news_events.find({
            "$or": [
                {"key_takeaway": {"$exists": False}},
                {"key_takeaway": None},
                {"key_takeaway": ""}
            ]
        }).limit(limit)
        
        events = await cursor.to_list(limit)
        results["found"] = len(events)
        
        for event in events:
            try:
                takeaway = self.generate_from_event(event)
                await self.db.news_events.update_one(
                    {"id": event["id"]},
                    {"$set": {
                        "key_takeaway": takeaway,
                        "takeaway_generated_at": datetime.now(timezone.utc).isoformat()
                    }}
                )
                results["generated"] += 1
            except Exception as e:
                results["errors"].append(f"{event['id']}: {str(e)}")
            results["processed"] += 1
        
        return results


# ═══════════════════════════════════════════════════════════════
# SINGLETON ACCESS
# ═══════════════════════════════════════════════════════════════

_takeaway_generator: Optional[KeyTakeawayGenerator] = None


def get_takeaway_generator(db) -> KeyTakeawayGenerator:
    """Get or create KeyTakeawayGenerator singleton."""
    global _takeaway_generator
    if _takeaway_generator is None:
        _takeaway_generator = KeyTakeawayGenerator(db)
    return _takeaway_generator
