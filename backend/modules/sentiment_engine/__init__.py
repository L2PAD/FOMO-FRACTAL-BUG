"""
FOMO Multi-Provider Sentiment Engine
=====================================

Multi-provider sentiment analysis with consensus mechanism.

Providers:
- FOMO: Custom internal sentiment (primary)
- OpenAI: GPT-based analysis
- Anthropic: Claude-based analysis
- Gemini: Google AI analysis

Output:
- Consensus (weighted average from all active providers)
- Individual provider scores
- FOMO score (custom, 0 if not configured)
"""

from .engine import SentimentEngine, SentimentResult
from .providers import SentimentProvider, ProviderType
from .api import router as sentiment_router

__all__ = [
    'SentimentEngine',
    'SentimentResult', 
    'SentimentProvider',
    'ProviderType',
    'sentiment_router'
]
