"""
Enhanced Intelligence Scoring Pipeline

Extends base scoring with:
- impact_score: Market impact assessment (independent from importance)
- Enhanced confidence modeling

Architecture:
sentiment = market mood
importance = news significance  
confidence = data reliability
rumor = speculation likelihood
impact = MARKET EFFECT (new!)

Key insight:
- High importance + Low impact: "ETF paperwork filed"
- Low importance + High impact: "Flash loan exploit on DEX"
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime, timezone


class EnhancedIntelligenceScores(BaseModel):
    """
    Complete 5-axis scoring for intelligence objects
    
    This is the canonical scoring model going forward.
    """
    # Original 4 scores
    sentiment_score: float = Field(0.0, ge=-1, le=1)
    sentiment_label: str = Field("neutral")  # positive/negative/neutral
    importance_score: float = Field(0.0, ge=0, le=100)
    confidence_score: float = Field(0.0, ge=0, le=1)
    rumor_score: float = Field(0.0, ge=0, le=1)
    
    # NEW: Impact score (P0 requirement)
    impact_score: float = Field(0.0, ge=0, le=100, description="Market impact potential")
    impact_label: str = Field("low", description="low/medium/high/critical")
    
    # Calculated composite
    fomo_score: float = Field(0.0, ge=0, le=100, description="Composite FOMO score")
    
    # Metadata
    scored_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    scoring_version: str = Field("2.0", description="Scoring pipeline version")


# =============================================================================
# IMPACT KEYWORDS
# Different from importance - these indicate market-moving potential
# =============================================================================

HIGH_IMPACT_KEYWORDS = {
    # Price-moving events
    "liquidation": 90, "liquidated": 90, "cascade": 85,
    "whale": 70, "dump": 75, "pump": 70,
    "flash crash": 95, "circuit breaker": 85,
    "depegged": 90, "depeg": 90,
    
    # Supply shocks
    "burn": 60, "burned": 60, "mint": 55, "minted": 55,
    "unlock": 65, "vesting cliff": 70,
    "airdrop claim": 60,
    
    # Exchange events
    "listing": 70, "delisting": 80, "trading halt": 85,
    "withdrawal suspended": 75, "deposits disabled": 70,
    
    # DeFi impact
    "exploit": 90, "drained": 85, "rug": 95, "rugged": 95,
    "flash loan": 80, "oracle attack": 85,
    "tvl drop": 70, "bank run": 85,
    
    # Regulatory action
    "ban": 80, "banned": 80, "seized": 85, "frozen": 80,
    "enforcement action": 75, "indictment": 80,
}

MEDIUM_IMPACT_KEYWORDS = {
    "selloff": 55, "sell-off": 55, "capitulation": 60,
    "accumulation": 50, "distribution": 50,
    "breakout": 45, "breakdown": 45,
    "support": 35, "resistance": 35,
    "volume spike": 50, "unusual activity": 45,
    "migration": 40, "upgrade": 35,
}

LOW_IMPACT_KEYWORDS = {
    "roadmap": 20, "proposal": 25, "governance": 25,
    "vote": 20, "snapshot": 20,
    "testnet": 30, "beta": 25,
    "interview": 15, "podcast": 15,
    "opinion": 10, "analysis": 15,
}


# =============================================================================
# ENTITY IMPACT MULTIPLIERS
# Some entities have higher market impact
# =============================================================================

ENTITY_IMPACT_MULTIPLIERS = {
    # Major projects
    "bitcoin": 1.5, "btc": 1.5,
    "ethereum": 1.4, "eth": 1.4,
    "solana": 1.3, "sol": 1.3,
    "bnb": 1.2, "binance": 1.3,
    
    # High-impact entities
    "tether": 1.5, "usdt": 1.5, "usdc": 1.4,
    "blackrock": 1.4, "grayscale": 1.3,
    "sec": 1.3, "cftc": 1.2,
    
    # DeFi majors
    "uniswap": 1.2, "aave": 1.2, "lido": 1.2,
    "makerdao": 1.2, "curve": 1.2,
}


class EnhancedScoringPipeline:
    """
    Enhanced scoring pipeline with impact analysis
    """
    
    def __init__(self, base_pipeline=None):
        """
        Args:
            base_pipeline: Original ScoringPipeline for base scores
        """
        from modules.intelligence.scoring_pipeline import ScoringPipeline
        self.base_pipeline = base_pipeline or ScoringPipeline()
    
    def score_article(
        self,
        title: str,
        content: str = "",
        source: str = "",
        entities: List[str] = None,
        source_count: int = 1
    ) -> EnhancedIntelligenceScores:
        """
        Score with enhanced 5-axis model
        """
        entities = entities or []
        text = f"{title} {content}".lower()
        
        # Get base scores
        base_scores = self.base_pipeline.score_article(
            title, content, source, entities, source_count
        )
        
        # Calculate impact score
        impact_score = self._calculate_impact(text, entities)
        
        # Derive impact label
        impact_label = "low"
        if impact_score >= 80:
            impact_label = "critical"
        elif impact_score >= 60:
            impact_label = "high"
        elif impact_score >= 40:
            impact_label = "medium"
        
        # Calculate composite FOMO score
        fomo_score = self._calculate_fomo_score(
            base_scores.sentiment_score,
            base_scores.importance_score,
            base_scores.confidence_score,
            base_scores.rumor_score,
            impact_score
        )
        
        return EnhancedIntelligenceScores(
            sentiment_score=base_scores.sentiment_score,
            sentiment_label=base_scores.sentiment_label,
            importance_score=base_scores.importance_score,
            confidence_score=base_scores.confidence_score,
            rumor_score=base_scores.rumor_score,
            impact_score=round(impact_score, 1),
            impact_label=impact_label,
            fomo_score=round(fomo_score, 1)
        )
    
    def _calculate_impact(
        self,
        text: str,
        entities: List[str]
    ) -> float:
        """
        Calculate market impact potential (0-100)
        
        Different from importance:
        - Importance = news significance
        - Impact = market effect potential
        """
        score = 15  # Base score
        
        # Check high impact keywords
        for keyword, weight in HIGH_IMPACT_KEYWORDS.items():
            if keyword in text:
                score = max(score, weight)
        
        # Check medium impact keywords
        for keyword, weight in MEDIUM_IMPACT_KEYWORDS.items():
            if keyword in text:
                score = max(score, weight)
        
        # Apply entity multipliers
        multiplier = 1.0
        for entity in entities:
            entity_lower = entity.lower()
            if entity_lower in ENTITY_IMPACT_MULTIPLIERS:
                multiplier = max(multiplier, ENTITY_IMPACT_MULTIPLIERS[entity_lower])
        
        score *= multiplier
        
        # Cap for low impact indicators
        for keyword, weight in LOW_IMPACT_KEYWORDS.items():
            if keyword in text:
                score = min(score, 50)
                break
        
        return min(100, max(0, score))
    
    def _calculate_fomo_score(
        self,
        sentiment: float,
        importance: float,
        confidence: float,
        rumor: float,
        impact: float
    ) -> float:
        """
        Calculate composite FOMO score
        
        Formula considers all 5 dimensions:
        - Higher impact = higher FOMO
        - Higher importance = higher FOMO
        - Higher confidence = higher FOMO
        - Lower rumor = higher FOMO (inverted)
        - Sentiment affects direction, not magnitude
        """
        # Base from impact and importance
        base = (impact * 0.4 + importance * 0.3)
        
        # Confidence boost
        confidence_factor = 0.7 + (confidence * 0.3)
        
        # Rumor penalty
        rumor_penalty = 1 - (rumor * 0.3)
        
        # Sentiment boost (stronger sentiment = more FOMO-worthy)
        sentiment_factor = 1 + abs(sentiment) * 0.2
        
        fomo = base * confidence_factor * rumor_penalty * sentiment_factor
        
        return min(100, max(0, fomo))
    
    def combine_scores(
        self,
        scores_list: List[EnhancedIntelligenceScores]
    ) -> EnhancedIntelligenceScores:
        """
        Combine scores from multiple sources
        """
        if not scores_list:
            return EnhancedIntelligenceScores()
        
        n = len(scores_list)
        
        # Average sentiment
        avg_sentiment = sum(s.sentiment_score for s in scores_list) / n
        
        # Max importance and impact (most significant view wins)
        max_importance = max(s.importance_score for s in scores_list)
        max_impact = max(s.impact_score for s in scores_list)
        
        # Average confidence, boosted by agreement
        avg_confidence = sum(s.confidence_score for s in scores_list) / n
        if n >= 3:
            avg_confidence = min(avg_confidence + 0.1, 0.95)
        
        # Min rumor score
        min_rumor = min(s.rumor_score for s in scores_list)
        
        # Recalculate FOMO with combined values
        fomo = self._calculate_fomo_score(
            avg_sentiment, max_importance, avg_confidence, min_rumor, max_impact
        )
        
        sentiment_label = "neutral"
        if avg_sentiment > 0.2:
            sentiment_label = "positive"
        elif avg_sentiment < -0.2:
            sentiment_label = "negative"
        
        impact_label = "low"
        if max_impact >= 80:
            impact_label = "critical"
        elif max_impact >= 60:
            impact_label = "high"
        elif max_impact >= 40:
            impact_label = "medium"
        
        return EnhancedIntelligenceScores(
            sentiment_score=round(avg_sentiment, 3),
            sentiment_label=sentiment_label,
            importance_score=round(max_importance, 1),
            confidence_score=round(avg_confidence, 3),
            rumor_score=round(min_rumor, 3),
            impact_score=round(max_impact, 1),
            impact_label=impact_label,
            fomo_score=round(fomo, 1)
        )


# Singleton instance
enhanced_scoring_pipeline = EnhancedScoringPipeline()
