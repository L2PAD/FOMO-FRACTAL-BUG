"""
News Ranker
===========

Ranks news articles by relevance and recency.
"""

import logging
from typing import List, Dict
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)


# High-value keywords
HOT_KEYWORDS = [
    "bitcoin", "btc", "ethereum", "eth", "sec", "etf", "ai",
    "breaking", "exclusive", "hack", "exploit", "airdrop",
    "bull", "bear", "rally", "crash", "ath"
]

# Source weights
SOURCE_WEIGHTS = {
    "cointelegraph": 1.0,
    "theblock": 1.0,
    "coindesk": 0.95,
    "decrypt": 0.9,
    "blockworks": 0.85,
    "incrypted": 0.8
}


class NewsRanker:
    """
    News article ranking system.
    
    Score formula:
    score = recency_score * 0.4 + relevance_score * 0.3 + source_weight * 0.2 + engagement * 0.1
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.articles = db.news_articles
    
    async def rank_article(self, article: dict) -> dict:
        """
        Calculate ranking score for article.
        
        Args:
            article: Article document
            
        Returns:
            Updated article with scores
        """
        # 1. Recency score (0-1)
        recency = self._calculate_recency(article.get("published_at"))
        
        # 2. Relevance score (0-1)
        relevance = self._calculate_relevance(article)
        
        # 3. Source weight (0-1)
        source_weight = SOURCE_WEIGHTS.get(article.get("source", ""), 0.5)
        
        # 4. Calculate final score
        score = (
            recency * 0.4 +
            relevance * 0.3 +
            source_weight * 0.3
        )
        
        article["recency_score"] = recency
        article["relevance_score"] = relevance
        article["score"] = round(score, 4)
        
        return article
    
    def _calculate_recency(self, published_at) -> float:
        """
        Calculate recency score.
        1.0 = just published
        0.0 = older than 7 days
        """
        if not published_at:
            return 0.5
        
        if isinstance(published_at, str):
            try:
                published_at = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
            except:
                return 0.5
        
        now = datetime.now(timezone.utc)
        if published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=timezone.utc)
        
        age = now - published_at
        age_hours = age.total_seconds() / 3600
        
        # Decay function: score = 1.0 at 0 hours, ~0 at 168 hours (7 days)
        if age_hours < 0:
            return 1.0
        elif age_hours > 168:
            return 0.0
        else:
            return max(0, 1.0 - (age_hours / 168))
    
    def _calculate_relevance(self, article: dict) -> float:
        """
        Calculate relevance score based on content.
        """
        score = 0.0
        text = (article.get("title", "") + " " + article.get("content", "")).lower()
        
        # Hot keywords
        keyword_matches = sum(1 for kw in HOT_KEYWORDS if kw in text)
        score += min(keyword_matches * 0.1, 0.5)
        
        # Mentioned tokens boost
        tokens = article.get("mentioned_tokens", [])
        if tokens:
            score += min(len(tokens) * 0.05, 0.25)
        
        # Mentioned projects boost
        projects = article.get("mentioned_projects", [])
        if projects:
            score += min(len(projects) * 0.05, 0.25)
        
        # Category boost
        category = article.get("category", "")
        if category in ["breaking", "market"]:
            score += 0.1
        
        return min(score, 1.0)
    
    async def rank_all_articles(self) -> dict:
        """Recalculate scores for all articles"""
        updated = 0
        
        cursor = self.articles.find({}, {"_id": 0})
        async for article in cursor:
            ranked = await self.rank_article(article)
            
            await self.articles.update_one(
                {"id": article["id"]},
                {"$set": {
                    "score": ranked["score"],
                    "recency_score": ranked["recency_score"],
                    "relevance_score": ranked["relevance_score"]
                }}
            )
            updated += 1
        
        return {"ok": True, "updated": updated}
    
    async def get_top_news(self, limit: int = 20) -> List[dict]:
        """Get top ranked news articles"""
        articles = []
        cursor = self.articles.find(
            {},
            {"_id": 0, "content": 0}  # Exclude full content for feed
        ).sort("score", -1).limit(limit)
        
        async for article in cursor:
            articles.append(article)
        
        return articles
    
    async def get_trending_topics(self, limit: int = 10) -> List[dict]:
        """Get trending topics from recent news"""
        # Aggregate mentioned tokens from last 24h
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        
        pipeline = [
            {"$match": {"published_at": {"$gte": yesterday.isoformat()}}},
            {"$unwind": "$mentioned_tokens"},
            {"$group": {"_id": "$mentioned_tokens", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": limit}
        ]
        
        topics = []
        async for doc in self.articles.aggregate(pipeline):
            topics.append({
                "topic": doc["_id"],
                "mentions": doc["count"]
            })
        
        return topics
