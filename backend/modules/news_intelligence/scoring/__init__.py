"""
News Intelligence Scoring Module
=================================
Sentiment analysis, importance scoring, confidence and rumor detection.
"""

from .news_intelligence_engine import (
    NewsIntelligenceEngine,
    SentimentAnalyzer,
    ImportanceScorer,
    get_news_intelligence_engine
)

from .source_reliability import (
    SourceReliabilityManager,
    get_source_reliability_manager,
    get_source_weight,
    DEFAULT_SOURCE_WEIGHTS
)

from .confidence_engine import (
    ConfidenceEngine,
    get_confidence_engine,
    get_confidence_level,
    CONFIDENCE_LEVELS
)

from .rumor_detector import (
    RumorDetector,
    get_rumor_detector,
    get_rumor_level,
    RUMOR_KEYWORDS,
    RUMOR_LEVELS
)

__all__ = [
    # Intelligence engine
    "NewsIntelligenceEngine",
    "SentimentAnalyzer", 
    "ImportanceScorer",
    "get_news_intelligence_engine",
    # Source reliability
    "SourceReliabilityManager",
    "get_source_reliability_manager",
    "get_source_weight",
    "DEFAULT_SOURCE_WEIGHTS",
    # Confidence
    "ConfidenceEngine",
    "get_confidence_engine",
    "get_confidence_level",
    "CONFIDENCE_LEVELS",
    # Rumor detection
    "RumorDetector",
    "get_rumor_detector",
    "get_rumor_level",
    "RUMOR_KEYWORDS",
    "RUMOR_LEVELS"
]
