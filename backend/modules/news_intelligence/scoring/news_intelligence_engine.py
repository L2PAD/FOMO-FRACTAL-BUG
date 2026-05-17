"""
News Intelligence Engine
=========================
Sentiment Analysis + Importance Score for News Articles.

Components:
1. SentimentAnalyzer - Analyzes sentiment of news articles
2. ImportanceScorer - Calculates importance score based on multiple factors
3. NewsIntelligenceEngine - Combines both for complete analysis

Importance Score Formula:
score = (0.35 * source_weight) + (0.25 * source_count) + (0.20 * entity_importance) + (0.10 * sentiment_strength) + (0.10 * novelty)
"""

import logging
import asyncio
import time
import os
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import math

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# SOURCE WEIGHT CONFIGURATION
# ═══════════════════════════════════════════════════════════════

SOURCE_WEIGHTS = {
    # Tier A - Primary (1.0)
    "coindesk": 1.0,
    "the_block": 1.0,
    "bloomberg_crypto": 1.0,
    "reuters_crypto": 1.0,
    "cointelegraph": 0.95,
    
    # Tier B - Secondary (0.8-0.9)
    "decrypt": 0.9,
    "blockworks": 0.9,
    "defiant": 0.85,
    "unchained": 0.85,
    "bankless": 0.85,
    
    # Tier C - Research (0.6-0.8)
    "messari": 0.8,
    "delphi_digital": 0.8,
    "glassnode": 0.75,
    "nansen": 0.75,
    "chainalysis": 0.75,
    
    # Tier D - Aggregators (0.4-0.6)
    "cryptopanic": 0.5,
    "cryptoslate": 0.5,
    "crypto_news": 0.45,
    "newsbtc": 0.4,
    
    # Default
    "default": 0.5
}


# Entity importance weights
ENTITY_IMPORTANCE = {
    # Tier 1 - Major assets
    "BTC": 1.0, "ETH": 1.0, "SOL": 0.9,
    
    # Tier 2 - Major institutions
    "BlackRock": 1.0, "SEC": 1.0, "Binance": 0.95, "Coinbase": 0.95,
    "Grayscale": 0.9, "Fidelity": 0.9,
    
    # Tier 3 - Major protocols
    "Ethereum": 0.9, "Bitcoin": 1.0, "Solana": 0.85, "Arbitrum": 0.8,
    "Optimism": 0.8, "Base": 0.8,
    
    # Tier 4 - DeFi
    "Uniswap": 0.75, "Aave": 0.75, "MakerDAO": 0.75, "Lido": 0.75,
    
    # Default
    "default": 0.3
}


# ═══════════════════════════════════════════════════════════════
# SENTIMENT ANALYZER
# ═══════════════════════════════════════════════════════════════

class SentimentAnalyzer:
    """
    Analyzes sentiment of news articles using configured providers.
    Returns: sentiment (positive/negative/neutral), score (-1 to 1), summary, topics.
    """
    
    SENTIMENT_PROMPT = """Analyze the following news article and provide:
1. Sentiment: "positive", "negative", or "neutral"
2. Sentiment score: -1.0 (very negative) to 1.0 (very positive)
3. Brief summary (1-2 sentences)
4. Key topics (up to 5)
5. Confidence: 0.0 to 1.0

Article:
{text}

Respond in JSON format:
{
  "sentiment": "positive/negative/neutral",
  "sentiment_score": 0.0,
  "summary": "...",
  "topics": ["topic1", "topic2"],
  "confidence": 0.0
}"""
    
    def __init__(self, db):
        self.db = db
    
    async def analyze(self, text: str, use_cache: bool = True) -> Dict[str, Any]:
        """
        Analyze sentiment of text.
        Returns sentiment data or cached result.
        """
        import hashlib
        
        # Check cache first
        if use_cache:
            text_hash = hashlib.md5(text[:500].encode()).hexdigest()
            cached = await self.db.sentiment_cache.find_one({"text_hash": text_hash})
            if cached:
                logger.debug(f"[Sentiment] Cache hit for {text_hash[:8]}")
                return {
                    "sentiment": cached.get("sentiment"),
                    "sentiment_score": cached.get("sentiment_score"),
                    "summary": cached.get("summary"),
                    "topics": cached.get("topics", []),
                    "confidence": cached.get("confidence"),
                    "cached": True
                }
        
        # Get sentiment key
        from modules.intel.api.routes_sentiment_keys import get_sentiment_keys_manager
        manager = get_sentiment_keys_manager(self.db)
        key_info = await manager.get_default_key()
        
        if not key_info:
            logger.warning("[Sentiment] No sentiment key configured, using fallback")
            return await self._fallback_analysis(text)
        
        start_time = time.time()
        
        try:
            if key_info["provider"] == "internal":
                # Use LLM keys
                result = await self._analyze_with_llm(text)
            elif key_info["provider"] == "openai":
                result = await self._analyze_with_openai(text, key_info["api_key"], key_info.get("model", "gpt-4o-mini"))
            elif key_info["provider"] == "custom":
                result = await self._analyze_with_custom(text, key_info["endpoint_url"], key_info.get("api_key"))
            else:
                result = await self._analyze_with_llm(text)
            
            latency_ms = int((time.time() - start_time) * 1000)
            await manager.record_usage(key_info["id"], latency_ms)
            
            # Cache result
            if use_cache and result.get("sentiment"):
                await self.db.sentiment_cache.update_one(
                    {"text_hash": hashlib.md5(text[:500].encode()).hexdigest()},
                    {"$set": {
                        **result,
                        "text_hash": hashlib.md5(text[:500].encode()).hexdigest(),
                        "created_at": datetime.now(timezone.utc).isoformat()
                    }},
                    upsert=True
                )
            
            return result
            
        except Exception as e:
            logger.error(f"[Sentiment] Analysis failed: {e}")
            return await self._fallback_analysis(text)
    
    async def _analyze_with_llm(self, text: str) -> Dict[str, Any]:
        """Analyze using internal LLM keys."""
        from modules.intel.api.routes_llm_keys import get_llm_keys_manager
        
        llm_manager = get_llm_keys_manager(self.db)
        key_info = await llm_manager.get_key_for_capability("text")
        
        if not key_info:
            return await self._fallback_analysis(text)
        
        try:
            return await self._analyze_with_openai(
                text=text,
                api_key=key_info["api_key"],
                model="gpt-4o-mini"
            )
        except Exception as e:
            logger.error(f"[Sentiment] LLM analysis failed: {e}")
            return await self._fallback_analysis(text)
    
    async def _analyze_with_openai(self, text: str, api_key: str, model: str) -> Dict[str, Any]:
        """Analyze using OpenAI API directly."""
        import httpx
        import json
        
        prompt = self.SENTIMENT_PROMPT.format(text=text[:2000])
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": "You are a financial news sentiment analyzer. Always respond in valid JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.3
                },
                timeout=30
            )
            
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            return json.loads(content)
    
    async def _analyze_with_custom(self, text: str, endpoint_url: str, api_key: str = None) -> Dict[str, Any]:
        """Analyze using custom Sentiment SDK endpoint."""
        import httpx
        
        # If no endpoint_url, try to use sentiment_sdk with the key
        if not endpoint_url and api_key and api_key.startswith("sk-sent-"):
            # Use internal sentiment SDK
            return await self._analyze_with_sentiment_sdk(text, api_key)
        
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["X-API-Key"] = api_key
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                endpoint_url,
                headers=headers,
                json={"text": text[:2000], "source": "news"},
                timeout=30
            )
            data = response.json()
            
            # Handle SDK response format
            if data.get("ok") and data.get("data"):
                result_data = data["data"]
                label = result_data.get("label", "NEUTRAL").upper()
                score = result_data.get("score", 0.5)
                
                # Convert score (0-1) to sentiment_score (-1 to 1)
                sentiment_score = (score - 0.5) * 2
                
                return {
                    "sentiment": label.lower(),
                    "sentiment_score": sentiment_score,
                    "summary": text[:200],
                    "topics": [],
                    "confidence": result_data.get("meta", {}).get("confidenceScore", 0.5)
                }
            
            return data
    
    async def _analyze_with_sentiment_sdk(self, text: str, api_key: str) -> Dict[str, Any]:
        """Analyze using Sentiment SDK with api_key (no URL needed - gets from DB)."""
        import httpx
        
        # Get sentiment URL from database or environment
        sentiment_url = await self._get_sentiment_url()
        
        if not sentiment_url:
            logger.warning("[Sentiment] No sentiment URL configured, using fallback")
            return await self._fallback_analysis(text)
        
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": api_key
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{sentiment_url}/api/v1/sentiment/analyze",
                    headers=headers,
                    json={"text": text[:2000], "source": "news"},
                    timeout=15
                )
                data = response.json()
                
                if data.get("ok") and data.get("data"):
                    result_data = data["data"]
                    label = result_data.get("label", "NEUTRAL").upper()
                    score = result_data.get("score", 0.5)
                    
                    # Convert score (0-1) to sentiment_score (-1 to 1)
                    sentiment_score = (score - 0.5) * 2
                    
                    return {
                        "sentiment": label.lower(),
                        "sentiment_score": sentiment_score,
                        "summary": text[:200],
                        "topics": [],
                        "confidence": result_data.get("meta", {}).get("confidenceScore", 0.5)
                    }
                else:
                    logger.warning(f"[Sentiment] SDK error: {data}")
                    return await self._fallback_analysis(text)
                    
        except Exception as e:
            logger.error(f"[Sentiment] SDK request failed: {e}")
            return await self._fallback_analysis(text)
    
    async def _get_sentiment_url(self) -> str:
        """Get sentiment API URL from database settings."""
        import os
        
        # First try environment variable
        url = os.environ.get("SENTIMENT_API_URL")
        if url:
            return url
        
        # Try database settings
        settings = await self.db.settings.find_one({"key": "sentiment_api_url"})
        if settings:
            return settings.get("value")
        
        return None
    
    async def _fallback_analysis(self, text: str) -> Dict[str, Any]:
        """Simple keyword-based fallback analysis."""
        text_lower = text.lower()
        
        # Positive keywords
        positive = ["surge", "rally", "gains", "bullish", "approved", "adoption", "growth", "breakthrough", "record", "soar"]
        # Negative keywords
        negative = ["crash", "plunge", "bearish", "hack", "fraud", "ban", "investigation", "lawsuit", "decline", "collapse"]
        
        pos_count = sum(1 for word in positive if word in text_lower)
        neg_count = sum(1 for word in negative if word in text_lower)
        
        if pos_count > neg_count:
            sentiment = "positive"
            score = min(0.8, 0.3 + (pos_count * 0.1))
        elif neg_count > pos_count:
            sentiment = "negative"
            score = max(-0.8, -0.3 - (neg_count * 0.1))
        else:
            sentiment = "neutral"
            score = 0.0
        
        return {
            "sentiment": sentiment,
            "sentiment_score": score,
            "summary": text[:200] + "..." if len(text) > 200 else text,
            "topics": [],
            "confidence": 0.5,
            "fallback": True
        }


# ═══════════════════════════════════════════════════════════════
# IMPORTANCE SCORER
# ═══════════════════════════════════════════════════════════════

class ImportanceScorer:
    """
    Calculates importance score for news events.
    
    Formula:
    score = (0.35 * source_weight) + (0.25 * source_count) + (0.20 * entity_importance) + (0.10 * sentiment_strength) + (0.10 * novelty)
    
    All components normalized to 0-100 scale.
    """
    
    WEIGHTS = {
        "source_weight": 0.35,
        "source_count": 0.25,
        "entity_importance": 0.20,
        "sentiment_strength": 0.10,
        "novelty": 0.10
    }
    
    def __init__(self, db):
        self.db = db
        self._reliability_manager = None
    
    async def _get_reliability_manager(self):
        """Get SourceReliabilityManager instance."""
        if self._reliability_manager is None:
            from .source_reliability import get_source_reliability_manager
            self._reliability_manager = get_source_reliability_manager(self.db)
        return self._reliability_manager
    
    async def calculate_source_weight(self, sources: List[str]) -> float:
        """Calculate weighted average of source weights using SourceReliabilityManager."""
        if not sources:
            return 0.5
        
        manager = await self._get_reliability_manager()
        
        weights = []
        for source in sources:
            weight = await manager.get_weight(source)
            weights.append(weight)
        
        # Return max weight (best source defines reliability)
        return max(weights) if weights else 0.5
    
    def calculate_source_count_score(self, count: int) -> float:
        """Calculate score based on number of sources (logarithmic)."""
        if count <= 0:
            return 0
        # log2(count) normalized: 1 source = 0, 8 sources = 1
        return min(1.0, math.log2(count + 1) / 3)
    
    def calculate_entity_importance(self, entities: List[str]) -> float:
        """Calculate max entity importance score."""
        if not entities:
            return ENTITY_IMPORTANCE["default"]
        
        max_importance = 0
        for entity in entities:
            importance = ENTITY_IMPORTANCE.get(entity, ENTITY_IMPORTANCE["default"])
            max_importance = max(max_importance, importance)
        
        return max_importance
    
    def calculate_sentiment_strength(self, sentiment_score: float) -> float:
        """Calculate sentiment strength (absolute value)."""
        return abs(sentiment_score or 0)
    
    async def calculate_novelty(self, event_id: str, first_seen_at: str = None) -> float:
        """Calculate novelty score based on how many similar events exist."""
        # Count similar events in last 24h
        from datetime import timedelta
        
        now = datetime.now(timezone.utc)
        day_ago = now - timedelta(hours=24)
        
        similar_count = await self.db.news_events.count_documents({
            "id": {"$ne": event_id},
            "first_seen_at": {"$gte": day_ago.isoformat()}
        })
        
        # If first source: high novelty, if many: low novelty
        if similar_count == 0:
            return 1.0
        elif similar_count < 3:
            return 0.8
        elif similar_count < 10:
            return 0.5
        else:
            return 0.2
    
    async def calculate_score(
        self,
        sources: List[str] = None,
        source_count: int = 1,
        entities: List[str] = None,
        sentiment_score: float = 0,
        event_id: str = None,
        first_seen_at: str = None
    ) -> Dict[str, Any]:
        """
        Calculate total importance score.
        Returns score (0-100) and breakdown.
        """
        # Calculate components
        source_weight = await self.calculate_source_weight(sources or [])
        source_count_norm = self.calculate_source_count_score(source_count)
        entity_importance = self.calculate_entity_importance(entities or [])
        sentiment_strength = self.calculate_sentiment_strength(sentiment_score)
        novelty = await self.calculate_novelty(event_id, first_seen_at) if event_id else 0.8
        
        # Calculate weighted score
        raw_score = (
            self.WEIGHTS["source_weight"] * source_weight +
            self.WEIGHTS["source_count"] * source_count_norm +
            self.WEIGHTS["entity_importance"] * entity_importance +
            self.WEIGHTS["sentiment_strength"] * sentiment_strength +
            self.WEIGHTS["novelty"] * novelty
        )
        
        # Convert to 0-100 scale and clamp
        final_score = max(0, min(100, round(raw_score * 100, 1)))
        
        return {
            "importance_score": final_score,
            "breakdown": {
                "source_weight": round(source_weight * 100, 1),
                "source_count": round(source_count_norm * 100, 1),
                "entity_importance": round(entity_importance * 100, 1),
                "sentiment_strength": round(sentiment_strength * 100, 1),
                "novelty": round(novelty * 100, 1)
            },
            "weights": self.WEIGHTS
        }


# ═══════════════════════════════════════════════════════════════
# NEWS INTELLIGENCE ENGINE
# ═══════════════════════════════════════════════════════════════

class NewsIntelligenceEngine:
    """
    Combined engine for sentiment + importance scoring.
    
    Usage:
    engine = NewsIntelligenceEngine(db)
    result = await engine.analyze_article(article_text, metadata)
    """
    
    def __init__(self, db):
        self.db = db
        self.sentiment_analyzer = SentimentAnalyzer(db)
        self.importance_scorer = ImportanceScorer(db)
    
    async def analyze_article(
        self,
        text: str,
        sources: List[str] = None,
        source_count: int = 1,
        entities: List[str] = None,
        event_id: str = None,
        first_seen_at: str = None
    ) -> Dict[str, Any]:
        """
        Full analysis: sentiment + importance score.
        """
        start_time = time.time()
        
        # Run sentiment analysis
        sentiment_result = await self.sentiment_analyzer.analyze(text)
        
        # Calculate importance score
        importance_result = await self.importance_scorer.calculate_score(
            sources=sources,
            source_count=source_count,
            entities=entities,
            sentiment_score=sentiment_result.get("sentiment_score", 0),
            event_id=event_id,
            first_seen_at=first_seen_at
        )
        
        processing_time = round((time.time() - start_time) * 1000)
        
        return {
            "sentiment": sentiment_result.get("sentiment"),
            "sentiment_score": sentiment_result.get("sentiment_score"),
            "summary": sentiment_result.get("summary"),
            "topics": sentiment_result.get("topics", []),
            "confidence": sentiment_result.get("confidence"),
            "importance_score": importance_result["importance_score"],
            "importance_breakdown": importance_result["breakdown"],
            "processing_time_ms": processing_time
        }
    
    async def analyze_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze a news event document."""
        text = event.get("summary_en") or event.get("title_seed") or event.get("headline") or ""
        
        return await self.analyze_article(
            text=text,
            sources=event.get("sources", []),
            source_count=event.get("source_count", 1),
            entities=event.get("primary_entities", []) + event.get("primary_assets", []),
            event_id=event.get("id"),
            first_seen_at=event.get("first_seen_at")
        )
    
    async def update_event_scores(self, event_id: str) -> Dict[str, Any]:
        """Update sentiment and importance scores for an event."""
        event = await self.db.news_events.find_one({"id": event_id})
        if not event:
            return {"ok": False, "error": "Event not found"}
        
        analysis = await self.analyze_event(event)
        
        # Update event
        await self.db.news_events.update_one(
            {"id": event_id},
            {"$set": {
                "sentiment": analysis["sentiment"],
                "sentiment_score": analysis["sentiment_score"],
                "ai_summary": analysis["summary"],
                "topics": analysis["topics"],
                "sentiment_confidence": analysis["confidence"],
                "importance_score": analysis["importance_score"],
                "importance_breakdown": analysis["importance_breakdown"],
                "scores_updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        
        return {
            "ok": True,
            "event_id": event_id,
            **analysis
        }


# ═══════════════════════════════════════════════════════════════
# SINGLETON ACCESS
# ═══════════════════════════════════════════════════════════════

_news_intelligence_engine: Optional[NewsIntelligenceEngine] = None


def get_news_intelligence_engine(db) -> NewsIntelligenceEngine:
    """Get or create NewsIntelligenceEngine singleton."""
    global _news_intelligence_engine
    if _news_intelligence_engine is None:
        _news_intelligence_engine = NewsIntelligenceEngine(db)
    return _news_intelligence_engine
