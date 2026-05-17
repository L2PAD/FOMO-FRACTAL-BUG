"""
Event Clustering Engine
=======================

Groups articles into events based on semantic similarity and entity overlap.
Multi-factor matching: embedding similarity + entity overlap + event type + time proximity
"""

import logging
import hashlib
from typing import List, Optional, Dict, Any, Set
from datetime import datetime, timezone, timedelta

from ..models import NewsEvent, NormalizedArticle, EventStatus, EventType
from ..embeddings import EmbeddingGenerator

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
# CLUSTERING CONFIGURATION - TUNED FOR REAL EVENT DETECTION
# ═══════════════════════════════════════════════════════════════

# Main threshold for final match score
MATCH_THRESHOLD = 0.55  # Lowered from 0.75 for better clustering

# Individual component thresholds
MIN_SEMANTIC_SIMILARITY = 0.40  # Minimum embedding similarity
MIN_ENTITY_OVERLAP = 0.15  # At least some entity overlap required

# Weights for multi-factor scoring
WEIGHTS = {
    "semantic": 0.50,      # Embedding cosine similarity
    "entity": 0.25,        # Entity/asset overlap
    "event_type": 0.15,    # Same event type
    "time": 0.10           # Time proximity
}

# Time windows
TIME_WINDOW_HOURS = 24  # Search for matches within this window
DEVELOPING_TIME_HOURS = 48  # Extended window for developing stories

# Status thresholds
SOURCE_THRESHOLD_DEVELOPING = 2
SOURCE_THRESHOLD_CONFIRMED = 3


class EventClusteringEngine:
    """Clusters articles into events."""
    
    def __init__(self, db):
        self.db = db
        self.embedder = EmbeddingGenerator()
    
    def _generate_event_id(self, seed: str) -> str:
        """Generate unique event ID."""
        ts = datetime.now(timezone.utc).timestamp()
        hash_input = f"{seed}:{ts}"
        return f"evt_{hashlib.md5(hash_input.encode()).hexdigest()[:12]}"
    
    def _generate_cluster_key(self, assets: List[str], orgs: List[str], 
                              event_type: str) -> str:
        """Generate cluster key for matching."""
        parts = sorted(assets[:3]) + sorted(orgs[:2]) + [event_type]
        return hashlib.md5(":".join(parts).encode()).hexdigest()[:16]
    
    def _calculate_entity_overlap(self, article: Dict, event: Dict) -> float:
        """Calculate entity overlap score."""
        article_entities = set(article.get("entities", []) + article.get("assets", []))
        event_entities = set(event.get("primary_entities", []) + event.get("primary_assets", []))
        
        if not article_entities or not event_entities:
            return 0.0
        
        intersection = len(article_entities & event_entities)
        union = len(article_entities | event_entities)
        
        if union == 0:
            return 0.0
        
        return intersection / union
    
    def _calculate_event_type_match(self, article_hints: List[str], 
                                    event_type: str) -> float:
        """Calculate event type match score."""
        type_keywords = {
            EventType.REGULATION: ["regulate", "approve", "reject", "ban", "legalize", "sec", "cftc"],
            EventType.LISTING: ["list", "listing"],
            EventType.DELISTING: ["delist"],
            EventType.FUNDING: ["raise", "invest", "funding", "round", "series"],
            EventType.PARTNERSHIP: ["partner", "integrate", "collaboration"],
            EventType.HACK: ["hack", "exploit", "breach", "attack"],
            EventType.LAUNCH: ["launch", "release", "announce"],
            EventType.AIRDROP: ["airdrop", "drop"],
            EventType.UNLOCK: ["unlock", "vesting"],
        }
        
        keywords = type_keywords.get(event_type, [])
        if not keywords or not article_hints:
            return 0.0
        
        matches = sum(1 for hint in article_hints if any(kw in hint for kw in keywords))
        return min(1.0, matches / len(keywords))
    
    def _calculate_time_proximity(self, article_time: datetime, 
                                  event_time: datetime) -> float:
        """Calculate time proximity score (0-1)."""
        if not article_time or not event_time:
            return 0.5
        
        diff = abs((article_time - event_time).total_seconds())
        hours = diff / 3600
        
        if hours < 1:
            return 1.0
        elif hours < 6:
            return 0.9
        elif hours < 12:
            return 0.7
        elif hours < 24:
            return 0.5
        else:
            return max(0.0, 1.0 - (hours / 72))
    
    def _detect_event_type(self, hints: List[str], title: str) -> EventType:
        """Detect event type from hints and title."""
        text = " ".join(hints) + " " + title.lower()
        
        if any(w in text for w in ["hack", "exploit", "breach", "attack", "steal"]):
            return EventType.HACK
        if any(w in text for w in ["sec", "cftc", "regul", "approve", "reject", "ban", "legal"]):
            return EventType.REGULATION
        if any(w in text for w in ["rais", "invest", "funding", "million", "billion", "series"]):
            return EventType.FUNDING
        if any(w in text for w in ["list", "trading"]) and "delist" not in text:
            return EventType.LISTING
        if "delist" in text:
            return EventType.DELISTING
        if any(w in text for w in ["partner", "integrat", "collaborat"]):
            return EventType.PARTNERSHIP
        if any(w in text for w in ["launch", "releas", "announc"]):
            return EventType.LAUNCH
        if "airdrop" in text:
            return EventType.AIRDROP
        if "unlock" in text:
            return EventType.UNLOCK
        
        return EventType.NEWS
    
    def calculate_match_score(self, article: Dict, event: Dict) -> Dict[str, float]:
        """
        Calculate multi-factor match score between article and event.
        Returns dict with individual scores and final score.
        """
        scores = {
            "semantic": 0.0,
            "entity": 0.0,
            "event_type": 0.0,
            "time": 0.0,
            "final": 0.0,
            "can_merge": False
        }
        
        # 1. Semantic similarity (embedding cosine)
        article_emb = article.get("embedding")
        event_emb = event.get("centroid_embedding")
        
        if article_emb and event_emb:
            scores["semantic"] = self.embedder.cosine_similarity(article_emb, event_emb)
        
        # 2. Entity overlap (assets + organizations)
        scores["entity"] = self._calculate_entity_overlap(article, event)
        
        # 3. Event type match
        scores["event_type"] = self._calculate_event_type_match(
            article.get("event_hints", []),
            event.get("event_type", "news")
        )
        
        # 4. Time proximity
        article_time = article.get("published_at")
        event_time = event.get("last_seen_at")
        
        if isinstance(article_time, str):
            try:
                article_time = datetime.fromisoformat(article_time.replace('Z', '+00:00'))
            except:
                article_time = None
        if isinstance(event_time, str):
            try:
                event_time = datetime.fromisoformat(event_time.replace('Z', '+00:00'))
            except:
                event_time = None
        
        scores["time"] = self._calculate_time_proximity(article_time, event_time)
        
        # Calculate weighted final score
        scores["final"] = (
            scores["semantic"] * WEIGHTS["semantic"] +
            scores["entity"] * WEIGHTS["entity"] +
            scores["event_type"] * WEIGHTS["event_type"] +
            scores["time"] * WEIGHTS["time"]
        )
        
        # Determine if can merge based on multiple criteria
        # Must have minimum semantic similarity AND some entity overlap
        scores["can_merge"] = (
            scores["final"] >= MATCH_THRESHOLD and
            scores["semantic"] >= MIN_SEMANTIC_SIMILARITY and
            (scores["entity"] >= MIN_ENTITY_OVERLAP or scores["semantic"] >= 0.70)
        )
        
        return scores
    
    def _quick_entity_filter(self, article: Dict, event: Dict) -> bool:
        """
        Quick filter: check if there's any entity overlap before expensive embedding comparison.
        """
        article_assets = set(a.upper() for a in article.get("assets", []))
        event_assets = set(a.upper() for a in event.get("primary_assets", []))
        
        article_orgs = set(o.lower() for o in article.get("organizations", []))
        event_orgs = set(o.lower() for o in event.get("organizations", []))
        
        # At least one shared asset OR one shared organization
        has_shared_asset = bool(article_assets & event_assets)
        has_shared_org = bool(article_orgs & event_orgs)
        
        return has_shared_asset or has_shared_org
    
    async def find_matching_event(self, article: Dict) -> Optional[Dict]:
        """
        Find existing event that matches the article using multi-factor scoring.
        Uses quick entity filter first, then full scoring.
        """
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=TIME_WINDOW_HOURS)
        
        # Get recent active events
        cursor = self.db.news_events.find({
            "status": {"$in": ["candidate", "developing", "confirmed"]},
            "last_seen_at": {"$gte": cutoff.isoformat()}
        })
        
        best_match = None
        best_score = 0.0
        match_details = None
        
        candidates_checked = 0
        quick_filtered = 0
        
        async for event in cursor:
            candidates_checked += 1
            
            # Quick filter: skip if no entity overlap at all
            if not self._quick_entity_filter(article, event):
                quick_filtered += 1
                continue
            
            # Full scoring
            scores = self.calculate_match_score(article, event)
            
            if scores["can_merge"] and scores["final"] > best_score:
                best_score = scores["final"]
                best_match = event
                match_details = scores
        
        if best_match:
            logger.info(f"[Clustering] Match found: score={best_score:.3f}, "
                       f"semantic={match_details['semantic']:.3f}, "
                       f"entity={match_details['entity']:.3f}")
        else:
            logger.debug(f"[Clustering] No match (checked {candidates_checked}, "
                        f"quick-filtered {quick_filtered})")
        
        return best_match
    
    async def create_event_from_article(self, article: Dict) -> NewsEvent:
        """Create new event from article."""
        now = datetime.now(timezone.utc)
        
        # Detect event type
        event_type = self._detect_event_type(
            article.get("event_hints", []),
            article.get("title", "")
        )
        
        # Generate cluster key
        cluster_key = self._generate_cluster_key(
            article.get("assets", []),
            article.get("organizations", []),
            event_type.value
        )
        
        event = NewsEvent(
            id=self._generate_event_id(article.get("title", "")),
            cluster_key=cluster_key,
            status=EventStatus.CANDIDATE,
            event_type=event_type,
            title_seed=article.get("title", ""),
            primary_assets=article.get("assets", [])[:5],
            primary_entities=article.get("entities", [])[:10],
            organizations=article.get("organizations", [])[:5],
            persons=article.get("persons", [])[:5],
            regions=article.get("regions", [])[:3],
            source_count=1,
            article_count=1,
            article_ids=[article.get("id")],
            primary_source_id=article.get("source_id"),
            confidence_score=0.3,
            importance_score=0.5,
            freshness_score=1.0,
            feed_score=0.5,
            first_seen_at=now,
            last_seen_at=now,
            centroid_embedding=article.get("embedding")
        )
        
        return event
    
    async def add_article_to_event(self, article: Dict, event: Dict) -> Dict:
        """Add article to existing event and update it."""
        now = datetime.now(timezone.utc)
        
        # Update article list
        article_ids = event.get("article_ids", [])
        if article["id"] not in article_ids:
            article_ids.append(article["id"])
        
        # Track unique sources
        existing_sources = set()
        for aid in article_ids:
            a = await self.db.normalized_articles.find_one({"id": aid})
            if a:
                existing_sources.add(a.get("source_id"))
        source_count = len(existing_sources)
        
        # Update centroid embedding
        embeddings = []
        if event.get("centroid_embedding"):
            embeddings.append(event["centroid_embedding"])
        if article.get("embedding"):
            embeddings.append(article["embedding"])
        
        new_centroid = None
        if embeddings:
            new_centroid = self.embedder.calculate_centroid(embeddings)
        
        # Merge entities
        primary_assets = list(set(event.get("primary_assets", []) + article.get("assets", [])))[:8]
        primary_entities = list(set(event.get("primary_entities", []) + article.get("entities", [])))[:15]
        organizations = list(set(event.get("organizations", []) + article.get("organizations", [])))[:8]
        regions = list(set(event.get("regions", []) + article.get("regions", [])))[:5]
        
        # Update status based on source count
        status = event.get("status", "candidate")
        if source_count >= 3:
            status = "confirmed"
        elif source_count >= 2:
            status = "developing"
        
        # Calculate confidence
        confidence = min(0.95, 0.3 + (source_count * 0.2))
        
        # Update event
        update_data = {
            "article_ids": article_ids,
            "article_count": len(article_ids),
            "source_count": source_count,
            "status": status,
            "confidence_score": confidence,
            "primary_assets": primary_assets,
            "primary_entities": primary_entities,
            "organizations": organizations,
            "regions": regions,
            "last_seen_at": now.isoformat(),
            "centroid_embedding": new_centroid
        }
        
        await self.db.news_events.update_one(
            {"id": event["id"]},
            {"$set": update_data}
        )
        
        return {**event, **update_data}
    
    async def process_article(self, article_id: str) -> Dict[str, Any]:
        """Process a single article for clustering."""
        article = await self.db.normalized_articles.find_one({"id": article_id})
        if not article:
            return {"ok": False, "error": "Article not found"}
        
        if article.get("is_duplicate"):
            return {"ok": False, "error": "Article is duplicate"}
        
        # Find matching event
        matching_event = await self.find_matching_event(article)
        
        if matching_event:
            # Add to existing event
            updated_event = await self.add_article_to_event(article, matching_event)
            return {
                "ok": True,
                "action": "merged",
                "event_id": updated_event["id"],
                "source_count": updated_event.get("source_count", 1)
            }
        else:
            # Create new event
            new_event = await self.create_event_from_article(article)
            event_data = new_event.model_dump()
            await self.db.news_events.insert_one(event_data)
            
            # Emit webhook for important news
            if event_data.get("importance_score", 0) >= 0.7:
                try:
                    from modules.webhooks import emit_on_news_insert
                    await emit_on_news_insert(self.db, event_data)
                except Exception as e:
                    logger.warning(f"[Clustering] Webhook emit error: {e}")
            
            return {
                "ok": True,
                "action": "created",
                "event_id": new_event.id,
                "source_count": 1
            }
    
    async def process_pending_articles(self, limit: int = 50) -> Dict[str, Any]:
        """Process pending articles for clustering."""
        results = {
            "processed": 0,
            "events_created": 0,
            "events_merged": 0,
            "errors": 0
        }
        
        # Find articles with embeddings but not yet in events
        cursor = self.db.normalized_articles.find({
            "embedding": {"$ne": None},
            "is_duplicate": False
        }).sort("created_at", -1).limit(limit)
        
        processed_ids = set()
        async for event in self.db.news_events.find({}):
            for aid in event.get("article_ids", []):
                processed_ids.add(aid)
        
        async for article in cursor:
            if article["id"] in processed_ids:
                continue
            
            results["processed"] += 1
            
            try:
                result = await self.process_article(article["id"])
                
                if result.get("ok"):
                    if result.get("action") == "created":
                        results["events_created"] += 1
                    else:
                        results["events_merged"] += 1
                else:
                    results["errors"] += 1
                    
            except Exception as e:
                results["errors"] += 1
                logger.error(f"[Clustering] Error processing {article['id']}: {e}")
        
        # Phase 2: Merge similar events together
        if results["events_created"] > 0:
            merge_result = await self.merge_similar_events()
            results["events_merged"] += merge_result.get("merged", 0)
            logger.info(f"[Clustering] Post-merge: {merge_result}")
        
        return results
    
    async def merge_similar_events(self) -> Dict[str, Any]:
        """
        Post-processing: merge similar events that were created separately.
        This handles cases where articles arrived at the same time.
        """
        results = {"merged": 0, "checked": 0}
        
        # Common/generic assets to exclude from overlap check
        COMMON_ASSETS = {"BTC", "ETH", "SOL", "BNB", "OP", "W", "USDT", "USDC", "ARB", "MATIC"}
        
        # Get all recent candidate events (single-source events are merge candidates)
        # Don't filter by time - just get all candidates
        events = []
        cursor = self.db.news_events.find({
            "status": "candidate",
            "source_count": 1
        })
        async for event in cursor:
            if event.get("centroid_embedding"):
                events.append(event)
        
        if len(events) < 2:
            logger.info(f"[Clustering] Only {len(events)} candidate events, skipping merge")
            return results
        
        logger.info(f"[Clustering] Checking {len(events)} candidate events for merging")
        
        merged_ids = set()
        
        for i, event1 in enumerate(events):
            if event1["id"] in merged_ids:
                continue
            
            for event2 in events[i+1:]:
                if event2["id"] in merged_ids:
                    continue
                
                results["checked"] += 1
                
                # Calculate semantic similarity first
                emb1 = event1.get("centroid_embedding")
                emb2 = event2.get("centroid_embedding")
                
                if not emb1 or not emb2:
                    continue
                
                similarity = self.embedder.cosine_similarity(emb1, emb2)
                
                # Skip if too dissimilar
                if similarity < 0.50:
                    continue
                
                # Entity overlap (excluding common tokens)
                assets1 = set(a.upper() for a in event1.get("primary_assets", [])) - COMMON_ASSETS
                assets2 = set(a.upper() for a in event2.get("primary_assets", [])) - COMMON_ASSETS
                orgs1 = set(o.lower() for o in event1.get("organizations", []))
                orgs2 = set(o.lower() for o in event2.get("organizations", []))
                
                shared_assets = assets1 & assets2
                shared_orgs = orgs1 & orgs2
                
                # Merge conditions:
                # 1. High similarity (>=0.70) OR
                # 2. Medium similarity (>=0.55) with entity overlap
                should_merge = (
                    similarity >= 0.70 or
                    (similarity >= 0.55 and (shared_assets or shared_orgs))
                )
                
                if should_merge:
                    logger.info(f"[Clustering] Merging events: sim={similarity:.3f}, "
                               f"shared_assets={shared_assets}, shared_orgs={shared_orgs}")
                    logger.info(f"  Event1: {event1['title_seed'][:50]}...")
                    logger.info(f"  Event2: {event2['title_seed'][:50]}...")
                    
                    await self._merge_two_events(event1, event2)
                    merged_ids.add(event2["id"])
                    results["merged"] += 1
        
        return results
    
    async def _merge_two_events(self, event1: Dict, event2: Dict):
        """Merge event2 into event1."""
        now = datetime.now(timezone.utc)
        
        # Combine article IDs
        article_ids = list(set(event1.get("article_ids", []) + event2.get("article_ids", [])))
        
        # Count unique sources
        sources = set()
        for aid in article_ids:
            article = await self.db.normalized_articles.find_one({"id": aid})
            if article:
                sources.add(article.get("source_id"))
        source_count = len(sources)
        
        # Update status
        status = "candidate"
        if source_count >= SOURCE_THRESHOLD_CONFIRMED:
            status = "confirmed"
        elif source_count >= SOURCE_THRESHOLD_DEVELOPING:
            status = "developing"
        
        # Merge entities
        primary_assets = list(set(event1.get("primary_assets", []) + event2.get("primary_assets", [])))[:10]
        primary_entities = list(set(event1.get("primary_entities", []) + event2.get("primary_entities", [])))[:15]
        organizations = list(set(event1.get("organizations", []) + event2.get("organizations", [])))[:10]
        regions = list(set(event1.get("regions", []) + event2.get("regions", [])))[:5]
        
        # Update centroid
        emb1 = event1.get("centroid_embedding")
        emb2 = event2.get("centroid_embedding")
        new_centroid = self.embedder.calculate_centroid([emb1, emb2]) if emb1 and emb2 else emb1
        
        # Calculate confidence
        confidence = min(0.95, 0.3 + (source_count * 0.2))
        
        # Update event1
        await self.db.news_events.update_one(
            {"id": event1["id"]},
            {"$set": {
                "article_ids": article_ids,
                "article_count": len(article_ids),
                "source_count": source_count,
                "status": status,
                "confidence_score": confidence,
                "primary_assets": primary_assets,
                "primary_entities": primary_entities,
                "organizations": organizations,
                "regions": regions,
                "centroid_embedding": new_centroid,
                "last_seen_at": now.isoformat()
            }}
        )
        
        # Delete event2
        await self.db.news_events.delete_one({"id": event2["id"]})
