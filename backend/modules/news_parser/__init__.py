"""
News Parser Module
==================

Parses news articles from crypto media sources.
Uses readability algorithm for content extraction.

Sources:
- Incrypted
- Cointelegraph  
- Decrypt
- The Block
- Blockworks
- CoinDesk

Pipeline:
    News Source → Crawler → Article Extractor → Content Cleaner → News Database
"""

from .models import NewsArticle, NewsSource, NewsCategory
from .parser import NewsParser
from .ranker import NewsRanker

__all__ = [
    'NewsArticle',
    'NewsSource', 
    'NewsCategory',
    'NewsParser',
    'NewsRanker'
]
