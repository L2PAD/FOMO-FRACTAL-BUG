"""
Story Engine - Duplicate Collapse & Story Grouping
====================================================
Groups similar news articles into unified stories.
Prevents duplicate cards in the feed.

Features:
- Clusters articles about the same event
- Combines sources into a single story
- Updates story when new articles arrive
- Provides "Sources: N" count

Usage:
    engine = StoryEngine(db)
    story = await engine.create_or_update_story(article)
"""

import logging
import hashlib
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# STORY ENGINE
# ═══════════════════════════════════════════════════════════════

class StoryEngine:
    """
    Groups similar articles into unified stories.
    
    Story Structure:
    - story_id: unique identifier
    - title: main headline
    - summary: AI-generated combined summary
    - articles: list of article IDs
    - sources: list of unique source names
    - source_count: number of sources
    - confidence_score: based on source diversity
    - first_seen_at: earliest article time
    - updated_at: latest article time
    """
    
    # Similarity threshold for grouping
    SIMILARITY_THRESHOLD = 0.75
    
    # Max time difference for story grouping (hours)
    MAX_TIME_WINDOW_HOURS = 48
    
    def __init__(self, db):
        self.db = db
    
    async def create_or_update_story(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new story or update existing one with this event.
        Returns the story document.
        """
        event_id = event.get("id")
        title = event.get("title_en") or event.get("title_seed") or ""
        
        # Find similar existing story
        similar_story = await self._find_similar_story(event)
        
        if similar_story:
            # Update existing story
            return await self._update_story(similar_story, event)
        else:
            # Create new story
            return await self._create_story(event)
    
    async def _find_similar_story(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Find an existing story that matches this event."""
        title = event.get("title_en") or event.get("title_seed") or ""
        assets = event.get("primary_assets", [])
        entities = event.get("primary_entities", [])
        
        # Time window
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(hours=self.MAX_TIME_WINDOW_HOURS)
        
        # Query for potential matches
        query = {
            "is_story": True,
            "updated_at": {"$gte": window_start.isoformat()}
        }
        
        # Add asset filter if available
        if assets:
            query["primary_assets"] = {"$in": assets}
        
        cursor = self.db.news_stories.find(query).sort("updated_at", -1).limit(20)
        stories = await cursor.to_list(20)
        
        # Check similarity
        for story in stories:
            similarity = self._calculate_similarity(event, story)
            if similarity >= self.SIMILARITY_THRESHOLD:
                return story
        
        return None
    
    def _calculate_similarity(self, event: Dict[str, Any], story: Dict[str, Any]) -> float:
        """
        Calculate similarity between event and story.
        Returns 0.0 to 1.0.
        """
        score = 0.0
        
        # Title similarity (Jaccard on words)
        title1 = (event.get("title_en") or event.get("title_seed") or "").lower()
        title2 = (story.get("title") or story.get("title_seed") or "").lower()
        
        words1 = set(title1.split())
        words2 = set(title2.split())
        
        if words1 and words2:
            intersection = len(words1 & words2)
            union = len(words1 | words2)
            title_sim = intersection / union if union > 0 else 0
            score += title_sim * 0.4
        
        # Asset overlap
        assets1 = set(event.get("primary_assets", []))
        assets2 = set(story.get("primary_assets", []))
        
        if assets1 and assets2:
            intersection = len(assets1 & assets2)
            union = len(assets1 | assets2)
            asset_sim = intersection / union if union > 0 else 0
            score += asset_sim * 0.3
        
        # Entity overlap
        entities1 = set(event.get("primary_entities", []))
        entities2 = set(story.get("primary_entities", []))
        
        if entities1 and entities2:
            intersection = len(entities1 & entities2)
            union = len(entities1 | entities2)
            entity_sim = intersection / union if union > 0 else 0
            score += entity_sim * 0.2
        
        # Event type match
        if event.get("event_type") == story.get("event_type"):
            score += 0.1
        
        return score
    
    async def _create_story(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new story from event."""
        now = datetime.now(timezone.utc)
        
        story_id = f"story_{hashlib.md5(str(now.timestamp()).encode()).hexdigest()[:12]}"
        
        story = {
            "id": story_id,
            "is_story": True,
            "title": event.get("title_en") or event.get("title_seed"),
            "title_seed": event.get("title_seed"),
            "summary": event.get("summary_en") or event.get("ai_summary"),
            "event_type": event.get("event_type", "news"),
            "status": event.get("status", "candidate"),
            "primary_assets": event.get("primary_assets", []),
            "primary_entities": event.get("primary_entities", []),
            
            # Source tracking
            "article_ids": [event.get("id")],
            "source_ids": [event.get("primary_source_id")] if event.get("primary_source_id") else [],
            "source_names": [],
            "source_count": 1,
            "article_count": 1,
            
            # Scores
            "confidence_score": event.get("confidence_score", 0.5),
            "importance_score": event.get("importance_score"),
            "sentiment": event.get("sentiment"),
            "sentiment_score": event.get("sentiment_score"),
            "fomo_score": event.get("fomo_score"),
            "feed_score": event.get("feed_score"),
            
            # Timestamps
            "first_seen_at": event.get("first_seen_at") or now.isoformat(),
            "updated_at": now.isoformat(),
            "created_at": now.isoformat()
        }
        
        await self.db.news_stories.insert_one(story)
        
        # Link event to story
        await self.db.news_events.update_one(
            {"id": event.get("id")},
            {"$set": {"story_id": story_id}}
        )
        
        logger.info(f"[StoryEngine] Created story {story_id} for event {event.get('id')}")
        
        return story
    
    async def _update_story(self, story: Dict[str, Any], event: Dict[str, Any]) -> Dict[str, Any]:
        """Update existing story with new event."""
        story_id = story.get("id")
        event_id = event.get("id")
        now = datetime.now(timezone.utc)
        
        # Add event to story
        article_ids = story.get("article_ids", [])
        if event_id not in article_ids:
            article_ids.append(event_id)
        
        # Update source tracking
        source_ids = story.get("source_ids", [])
        if event.get("primary_source_id") and event.get("primary_source_id") not in source_ids:
            source_ids.append(event.get("primary_source_id"))
        
        # Calculate new source count
        source_count = len(set(source_ids))
        
        # Update confidence based on source diversity
        confidence = min(1.0, 0.5 + (source_count * 0.1))
        
        # Merge assets and entities
        assets = list(set(story.get("primary_assets", []) + event.get("primary_assets", [])))
        entities = list(set(story.get("primary_entities", []) + event.get("primary_entities", [])))
        
        # Update importance (take max)
        importance = max(
            story.get("importance_score") or 0,
            event.get("importance_score") or 0
        )
        
        # Update sentiment (weighted average towards latest)
        old_sentiment = story.get("sentiment_score") or 0
        new_sentiment = event.get("sentiment_score") or 0
        merged_sentiment = (old_sentiment * 0.6) + (new_sentiment * 0.4)
        
        update = {
            "article_ids": article_ids,
            "source_ids": source_ids,
            "source_count": source_count,
            "article_count": len(article_ids),
            "confidence_score": confidence,
            "importance_score": importance,
            "sentiment_score": merged_sentiment,
            "primary_assets": assets,
            "primary_entities": entities,
            "updated_at": now.isoformat()
        }
        
        await self.db.news_stories.update_one(
            {"id": story_id},
            {"$set": update}
        )
        
        # Link event to story
        await self.db.news_events.update_one(
            {"id": event_id},
            {"$set": {"story_id": story_id, "is_duplicate": True}}
        )
        
        logger.info(f"[StoryEngine] Updated story {story_id}: +1 event, {source_count} sources")
        
        return {**story, **update}
    
    async def get_story_feed(
        self,
        limit: int = 20,
        min_sources: int = 1,
        sentiment: str = None,
        min_importance: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get stories for feed (collapsed duplicates).
        Returns only unique stories, not individual articles.
        """
        query = {
            "is_story": True,
            "source_count": {"$gte": min_sources}
        }
        
        if sentiment:
            query["sentiment"] = sentiment
        
        if min_importance > 0:
            query["importance_score"] = {"$gte": min_importance}
        
        cursor = self.db.news_stories.find(
            query,
            {"_id": 0}
        ).sort([
            ("importance_score", -1),
            ("source_count", -1),
            ("updated_at", -1)
        ]).limit(limit)
        
        stories = await cursor.to_list(limit)
        
        return stories
    
    async def collapse_existing_events(self, limit: int = 100) -> Dict[str, Any]:
        """
        Batch process existing events to group into stories.
        Run this to collapse duplicates in existing data.
        """
        results = {
            "processed": 0,
            "stories_created": 0,
            "stories_updated": 0,
            "errors": []
        }
        
        # Get events not yet linked to stories
        cursor = self.db.news_events.find({
            "story_id": {"$exists": False},
            "status": {"$in": ["candidate", "developing", "confirmed"]}
        }).sort("first_seen_at", 1).limit(limit)
        
        events = await cursor.to_list(limit)
        
        for event in events:
            try:
                result = await self.create_or_update_story(event)
                results["processed"] += 1
                
                if result.get("article_count", 0) == 1:
                    results["stories_created"] += 1
                else:
                    results["stories_updated"] += 1
                    
            except Exception as e:
                results["errors"].append(f"{event.get('id')}: {str(e)}")
        
        return results
    
    async def get_story_detail(self, story_id: str) -> Optional[Dict[str, Any]]:
        """Get full story detail with all linked articles."""
        story = await self.db.news_stories.find_one({"id": story_id}, {"_id": 0})
        
        if not story:
            return None
        
        # Get linked articles
        article_ids = story.get("article_ids", [])
        if article_ids:
            cursor = self.db.news_events.find(
                {"id": {"$in": article_ids}},
                {"_id": 0, "id": 1, "title_en": 1, "title_seed": 1, "primary_source_id": 1, "first_seen_at": 1}
            )
            articles = await cursor.to_list(len(article_ids))
            story["linked_articles"] = articles
        
        return story


# ═══════════════════════════════════════════════════════════════
# SINGLETON ACCESS
# ═══════════════════════════════════════════════════════════════

_story_engine: Optional[StoryEngine] = None


def get_story_engine(db) -> StoryEngine:
    """Get or create StoryEngine singleton."""
    global _story_engine
    if _story_engine is None:
        _story_engine = StoryEngine(db)
    return _story_engine
