"""
Intelligence Scoring Pipeline

Every article/update/event gets 4 independent scores:

1. sentiment_score:    -1 to 1, market sentiment
2. importance_score:   0-100, how significant
3. confidence_score:   0-1, how reliable the info
4. rumor_score:        0-1, likelihood of being rumor/speculation

These scores are calculated independently and stored on every intelligence object.
"""

from typing import Optional, List, Dict, Tuple
from pydantic import BaseModel, Field
from enum import Enum
import re


class IntelligenceScores(BaseModel):
    """Complete scoring for an intelligence object"""
    sentiment_score: float = Field(0.0, ge=-1, le=1)
    sentiment_label: str = Field("neutral")  # positive/negative/neutral
    importance_score: float = Field(0.0, ge=0, le=100)
    confidence_score: float = Field(0.0, ge=0, le=1)
    rumor_score: float = Field(0.0, ge=0, le=1)


# =============================================================================
# IMPORTANCE KEYWORDS
# =============================================================================

HIGH_IMPORTANCE_KEYWORDS = {
    # Major events
    "hack": 90, "hacked": 90, "exploit": 85, "exploited": 85,
    "stolen": 80, "theft": 80, "breach": 75,
    "sec": 75, "lawsuit": 70, "regulation": 65,
    "etf": 80, "approved": 70, "rejected": 70,
    "bankrupt": 85, "bankruptcy": 85, "insolvent": 80,
    
    # Funding
    "raises": 60, "funding round": 65, "series a": 65, "series b": 70,
    "series c": 75, "ipo": 80, "acquisition": 75, "acquired": 75,
    
    # Launches
    "mainnet": 70, "testnet": 50, "launch": 55, "airdrop": 60,
    "token launch": 65, "tge": 70,
    
    # Partnerships
    "partnership": 55, "integration": 50, "collaboration": 50,
    "partners with": 55,
    
    # Market events
    "listing": 60, "delisting": 70, "halving": 75,
    "unlock": 55, "vesting": 50,
}

MEDIUM_IMPORTANCE_KEYWORDS = {
    "update": 30, "upgrade": 40, "release": 35,
    "milestone": 40, "achievement": 35,
    "growth": 35, "increase": 30, "decrease": 30,
    "report": 30, "analysis": 25,
    "announcement": 40, "announced": 40,
}

LOW_IMPORTANCE_KEYWORDS = {
    "opinion": 15, "prediction": 20, "forecast": 20,
    "rumor": 10, "speculation": 10, "might": 10,
    "could": 10, "may": 10, "possibly": 10,
}


# =============================================================================
# SENTIMENT KEYWORDS
# =============================================================================

POSITIVE_KEYWORDS = {
    "bullish": 0.7, "surge": 0.6, "soar": 0.7, "rally": 0.6,
    "growth": 0.4, "gain": 0.4, "profit": 0.5, "profitable": 0.5,
    "success": 0.5, "successful": 0.5, "breakthrough": 0.6,
    "adoption": 0.4, "partnership": 0.3, "integration": 0.3,
    "approval": 0.5, "approved": 0.5, "launch": 0.3, "launched": 0.3,
    "milestone": 0.4, "record": 0.4, "ath": 0.7, "all-time high": 0.7,
    "moon": 0.6, "pump": 0.5, "green": 0.3,
    "upgrade": 0.3, "improved": 0.3, "recovery": 0.4,
}

NEGATIVE_KEYWORDS = {
    "bearish": -0.7, "crash": -0.8, "plunge": -0.7, "dump": -0.6,
    "decline": -0.4, "loss": -0.5, "losses": -0.5, "down": -0.3,
    "hack": -0.8, "hacked": -0.8, "exploit": -0.7, "exploited": -0.7,
    "stolen": -0.7, "scam": -0.8, "fraud": -0.8, "rug": -0.9,
    "bankruptcy": -0.9, "bankrupt": -0.9, "insolvent": -0.8,
    "lawsuit": -0.5, "sued": -0.5, "investigation": -0.4,
    "delisting": -0.5, "delisted": -0.5, "ban": -0.6, "banned": -0.6,
    "warning": -0.4, "risk": -0.3, "concern": -0.3, "fear": -0.4,
    "sell-off": -0.5, "liquidation": -0.5, "liquidated": -0.5,
    "red": -0.3, "blood": -0.4, "rekt": -0.6,
}


# =============================================================================
# RUMOR INDICATORS
# =============================================================================

RUMOR_INDICATORS = {
    "rumor": 0.8, "rumored": 0.8, "reportedly": 0.5, "allegedly": 0.6,
    "speculation": 0.7, "speculated": 0.7, "unconfirmed": 0.7,
    "sources say": 0.5, "insider": 0.4, "leak": 0.5, "leaked": 0.5,
    "might": 0.3, "may": 0.2, "could": 0.2, "possibly": 0.3,
    "potential": 0.2, "considering": 0.3, "exploring": 0.3,
    "expected": 0.2, "anticipate": 0.2, "predicted": 0.3,
}

CONFIRMATION_INDICATORS = {
    "confirmed": -0.5, "official": -0.4, "announced": -0.3,
    "statement": -0.3, "press release": -0.4, "verified": -0.5,
    "on-chain": -0.4, "blockchain data": -0.4, "transaction": -0.3,
}


# =============================================================================
# SOURCE CREDIBILITY
# =============================================================================

SOURCE_CREDIBILITY = {
    # Tier A (high credibility)
    "bloomberg": 0.95, "reuters": 0.95, "wsj": 0.90,
    "coindesk": 0.85, "theblock": 0.85, "cointelegraph": 0.80,
    "decrypt": 0.80, "dlnews": 0.80,
    
    # Tier B (medium-high)
    "forbes": 0.75, "cnbc": 0.75, "techcrunch": 0.75,
    "messari": 0.80, "delphi": 0.80, "blockworks": 0.80,
    
    # Tier C (medium)
    "cryptoslate": 0.65, "bitcoinist": 0.60, "ambcrypto": 0.60,
    "newsbtc": 0.60, "beincrypto": 0.60,
    
    # Tier D (lower)
    "twitter": 0.50, "reddit": 0.45, "telegram": 0.40,
    "discord": 0.40, "medium": 0.55,
    
    # Official sources
    "company_blog": 0.85, "github": 0.90, "official": 0.85,
}


class ScoringPipeline:
    """
    Scoring pipeline for intelligence objects
    """
    
    def __init__(self, llm_client=None):
        """
        Args:
            llm_client: Optional LLM client for advanced analysis
        """
        self.llm_client = llm_client
    
    def score_article(
        self,
        title: str,
        content: str = "",
        source: str = "",
        entities: List[str] = None,
        source_count: int = 1
    ) -> IntelligenceScores:
        """
        Score an article/event with all 4 metrics
        """
        text = f"{title} {content}".lower()
        
        # Calculate each score
        sentiment_score = self._calculate_sentiment(text)
        importance_score = self._calculate_importance(text, entities or [], source_count)
        confidence_score = self._calculate_confidence(text, source, source_count)
        rumor_score = self._calculate_rumor_score(text)
        
        # Derive sentiment label
        sentiment_label = "neutral"
        if sentiment_score > 0.2:
            sentiment_label = "positive"
        elif sentiment_score < -0.2:
            sentiment_label = "negative"
        
        return IntelligenceScores(
            sentiment_score=round(sentiment_score, 3),
            sentiment_label=sentiment_label,
            importance_score=round(importance_score, 1),
            confidence_score=round(confidence_score, 3),
            rumor_score=round(rumor_score, 3)
        )
    
    def _calculate_sentiment(self, text: str) -> float:
        """Calculate sentiment score from -1 to 1"""
        score = 0.0
        word_count = 0
        
        # Check positive keywords
        for keyword, weight in POSITIVE_KEYWORDS.items():
            if keyword in text:
                score += weight
                word_count += 1
        
        # Check negative keywords
        for keyword, weight in NEGATIVE_KEYWORDS.items():
            if keyword in text:
                score += weight  # weight is already negative
                word_count += 1
        
        if word_count == 0:
            return 0.0
        
        # Normalize
        score = score / max(word_count, 1)
        return max(-1.0, min(1.0, score))
    
    def _calculate_importance(
        self,
        text: str,
        entities: List[str],
        source_count: int
    ) -> float:
        """Calculate importance score from 0 to 100"""
        score = 20  # Base score
        
        # Check high importance keywords
        for keyword, weight in HIGH_IMPORTANCE_KEYWORDS.items():
            if keyword in text:
                score = max(score, weight)
        
        # Check medium importance keywords
        for keyword, weight in MEDIUM_IMPORTANCE_KEYWORDS.items():
            if keyword in text:
                score = max(score, weight)
        
        # Boost for multiple sources
        source_boost = min(source_count * 3, 20)
        score += source_boost
        
        # Boost for major entities (would need entity importance map)
        entity_boost = min(len(entities) * 2, 10)
        score += entity_boost
        
        # Cap for low importance content
        for keyword, weight in LOW_IMPORTANCE_KEYWORDS.items():
            if keyword in text:
                score = min(score, 50)  # Cap at 50 if rumor-like
                break
        
        return min(100, max(0, score))
    
    def _calculate_confidence(
        self,
        text: str,
        source: str,
        source_count: int
    ) -> float:
        """Calculate confidence score from 0 to 1"""
        # Base confidence from source credibility
        source_lower = source.lower()
        base_confidence = 0.5
        
        for src, credibility in SOURCE_CREDIBILITY.items():
            if src in source_lower:
                base_confidence = credibility
                break
        
        # Boost from multiple sources
        if source_count >= 5:
            base_confidence = min(base_confidence + 0.2, 0.95)
        elif source_count >= 3:
            base_confidence = min(base_confidence + 0.1, 0.90)
        
        # Check for confirmation indicators
        for indicator, adjustment in CONFIRMATION_INDICATORS.items():
            if indicator in text:
                base_confidence = min(base_confidence - adjustment, 0.95)
        
        # Reduce for rumor indicators
        for indicator, weight in RUMOR_INDICATORS.items():
            if indicator in text:
                base_confidence *= (1 - weight * 0.3)
        
        return max(0.1, min(0.95, base_confidence))
    
    def _calculate_rumor_score(self, text: str) -> float:
        """Calculate rumor/speculation score from 0 to 1"""
        score = 0.0
        
        # Check rumor indicators
        for indicator, weight in RUMOR_INDICATORS.items():
            if indicator in text:
                score = max(score, weight)
        
        # Reduce for confirmation indicators
        for indicator, reduction in CONFIRMATION_INDICATORS.items():
            if indicator in text:
                score = max(0, score + reduction)  # reduction is negative
        
        return max(0, min(1, score))
    
    async def score_with_llm(
        self,
        title: str,
        content: str,
        source: str
    ) -> IntelligenceScores:
        """
        Advanced scoring using LLM (when available)
        Falls back to rule-based if no LLM
        """
        if not self.llm_client:
            return self.score_article(title, content, source)
        
        # LLM prompt for scoring
        prompt = f"""Analyze this crypto news article and provide scores:

Title: {title}
Content: {content[:500]}
Source: {source}

Provide JSON with:
- sentiment_score: -1 to 1 (market sentiment)
- importance_score: 0 to 100 (significance)
- confidence_score: 0 to 1 (reliability)
- rumor_score: 0 to 1 (speculation likelihood)
"""
        
        try:
            response = await self.llm_client.generate(prompt)
            # Parse LLM response and create scores
            # (Implementation depends on LLM client)
            pass
        except Exception as e:
            # Fallback to rule-based
            return self.score_article(title, content, source)
    
    def combine_scores(
        self,
        scores_list: List[IntelligenceScores]
    ) -> IntelligenceScores:
        """
        Combine scores from multiple sources for an event
        """
        if not scores_list:
            return IntelligenceScores()
        
        n = len(scores_list)
        
        # Average sentiment
        avg_sentiment = sum(s.sentiment_score for s in scores_list) / n
        
        # Max importance (most important view wins)
        max_importance = max(s.importance_score for s in scores_list)
        
        # Average confidence, boosted by agreement
        avg_confidence = sum(s.confidence_score for s in scores_list) / n
        if n >= 3:
            avg_confidence = min(avg_confidence + 0.1, 0.95)
        
        # Min rumor score (if any source confirms, reduce rumor)
        min_rumor = min(s.rumor_score for s in scores_list)
        
        sentiment_label = "neutral"
        if avg_sentiment > 0.2:
            sentiment_label = "positive"
        elif avg_sentiment < -0.2:
            sentiment_label = "negative"
        
        return IntelligenceScores(
            sentiment_score=round(avg_sentiment, 3),
            sentiment_label=sentiment_label,
            importance_score=round(max_importance, 1),
            confidence_score=round(avg_confidence, 3),
            rumor_score=round(min_rumor, 3)
        )


# Singleton instance
scoring_pipeline = ScoringPipeline()
