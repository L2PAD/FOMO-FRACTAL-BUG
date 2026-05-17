"""
Feed Projection Worker

Automated worker for creating and maintaining feed_cards from source events.

Architecture:
- Listens to event changes (new events, updates, score changes)
- Projects events into feed_cards_hot collection
- Archives old cards to feed_cards_archive
- Uses cursor pagination for all queries
- Incremental updates, not full rebuilds

Collections:
- feed_cards_hot: Active cards (0-90 days)
- feed_cards_archive: Historical cards (90+ days)
- feed_projection_state: Worker state and checkpoints

Jobs:
- project_new_events: Process newly created events
- update_changed_events: Update cards for modified events
- archive_old_cards: Move old cards to archive
- rebuild_partial: Rebuild subset of cards
- rebuild_full: Full rebuild (rare, scheduled)
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, AsyncGenerator
from pydantic import BaseModel, Field
from enum import Enum
import hashlib

logger = logging.getLogger(__name__)


class ProjectionJobType(str, Enum):
    """Types of projection jobs"""
    PROJECT_NEW = "project_new"
    UPDATE_CHANGED = "update_changed"
    ARCHIVE_OLD = "archive_old"
    REBUILD_PARTIAL = "rebuild_partial"
    REBUILD_FULL = "rebuild_full"
    SCORE_RECALC = "score_recalc"


class FeedCardPriority(str, Enum):
    """Display priority"""
    BREAKING = "breaking"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


class ProjectionState(BaseModel):
    """Worker state checkpoint"""
    worker_id: str = "feed_projection_worker"
    last_processed_event_id: Optional[str] = None
    last_processed_time: Optional[datetime] = None
    last_archive_run: Optional[datetime] = None
    last_full_rebuild: Optional[datetime] = None
    events_processed_24h: int = 0
    cards_created_24h: int = 0
    cards_archived_24h: int = 0
    errors_24h: int = 0


class FeedProjectionWorker:
    """
    Main worker for feed projection
    
    Design principles:
    1. Never do full table scans
    2. Always use cursor pagination
    3. Incremental updates over full rebuilds
    4. Hot/archive split for query performance
    """
    
    # Configuration
    HOT_DAYS = 90  # Cards younger than this stay in hot
    ARCHIVE_DAYS = 90  # Cards older than this go to archive
    BATCH_SIZE = 100  # Process events in batches
    
    # Priority thresholds
    BREAKING_THRESHOLD = 90
    HIGH_THRESHOLD = 70
    LOW_THRESHOLD = 30
    
    def __init__(self, db):
        self.db = db
        
        # Hot collection (fast queries)
        self.cards_hot = db.feed_cards_hot
        
        # Archive collection (historical)
        self.cards_archive = db.feed_cards_archive
        
        # State tracking
        self.state_collection = db.feed_projection_state
        
        # Source collections
        self.root_events = db.root_events
        self.event_updates = db.event_updates
        self.narratives = db.narratives
        self.articles = db.normalized_articles
        
        # Worker state
        self._running = False
        self._state: Optional[ProjectionState] = None
    
    async def initialize(self):
        """Initialize worker - create indexes and load state"""
        logger.info("[FeedProjectionWorker] Initializing...")
        
        # Create indexes for hot collection
        await self._create_hot_indexes()
        
        # Create indexes for archive collection
        await self._create_archive_indexes()
        
        # Load or create state
        self._state = await self._load_state()
        
        logger.info("[FeedProjectionWorker] Initialized")
    
    async def _create_hot_indexes(self):
        """Create optimized indexes for hot feed queries"""
        try:
            # Primary query index: active cards sorted by priority and time
            await self.cards_hot.create_index([
                ("priority", -1),
                ("event_time", -1)
            ], name="feed_query_primary")
            
            # Entity lookup
            await self.cards_hot.create_index(
                [("entities.symbol", 1), ("event_time", -1)],
                name="entity_feed"
            )
            
            # Narrative lookup
            await self.cards_hot.create_index(
                [("narrative_id", 1), ("event_time", -1)],
                name="narrative_feed"
            )
            
            # FOMO score filtering
            await self.cards_hot.create_index(
                [("fomo_score", -1), ("event_time", -1)],
                name="fomo_feed"
            )
            
            # Card type filtering
            await self.cards_hot.create_index(
                [("card_type", 1), ("event_time", -1)],
                name="type_feed"
            )
            
            # Source event lookup (for updates)
            await self.cards_hot.create_index("root_event_id", name="event_lookup")
            
            # Unique ID
            await self.cards_hot.create_index("id", unique=True, name="id_unique")
            
            # Cursor pagination support
            await self.cards_hot.create_index(
                [("event_time", -1), ("id", -1)],
                name="cursor_pagination"
            )
            
            logger.info("  → Hot collection indexes created")
            
        except Exception as e:
            logger.error(f"  → Hot index error: {e}")
    
    async def _create_archive_indexes(self):
        """Create minimal indexes for archive (rarely queried)"""
        try:
            await self.cards_archive.create_index("id", unique=True)
            await self.cards_archive.create_index("root_event_id")
            await self.cards_archive.create_index("event_time")
            
            logger.info("  → Archive collection indexes created")
            
        except Exception as e:
            logger.error(f"  → Archive index error: {e}")
    
    async def _load_state(self) -> ProjectionState:
        """Load worker state from DB"""
        doc = await self.state_collection.find_one({"worker_id": "feed_projection_worker"})
        if doc:
            return ProjectionState(**doc)
        
        state = ProjectionState()
        await self.state_collection.insert_one(state.dict())
        return state
    
    async def _save_state(self):
        """Save worker state"""
        if self._state:
            await self.state_collection.update_one(
                {"worker_id": "feed_projection_worker"},
                {"$set": self._state.dict()},
                upsert=True
            )
    
    # =========================================================================
    # MAIN PROJECTION JOBS
    # =========================================================================
    
    async def project_new_events(self, limit: int = None) -> Dict:
        """
        Project newly created events into feed cards
        
        Uses cursor pagination to avoid large scans
        """
        stats = {"processed": 0, "created": 0, "errors": 0}
        limit = limit or self.BATCH_SIZE
        
        # Find events newer than last processed
        query = {}
        if self._state and self._state.last_processed_time:
            query["first_seen"] = {"$gt": self._state.last_processed_time}
        
        # Cursor pagination with batch processing
        async for event in self._paginate_events(query, limit):
            try:
                card = await self._project_event_to_card(event)
                if card:
                    await self._upsert_card_hot(card)
                    stats["created"] += 1
                
                stats["processed"] += 1
                
                # Update state checkpoint
                self._state.last_processed_event_id = event.get("id")
                self._state.last_processed_time = event.get("first_seen")
                
            except Exception as e:
                logger.error(f"Error projecting event {event.get('id')}: {e}")
                stats["errors"] += 1
        
        # Save state
        self._state.events_processed_24h += stats["processed"]
        self._state.cards_created_24h += stats["created"]
        self._state.errors_24h += stats["errors"]
        await self._save_state()
        
        return stats
    
    async def update_changed_events(self, since: datetime = None) -> Dict:
        """
        Update cards for events that have been modified
        
        Triggered by:
        - New event_updates
        - Score changes
        - Narrative assignments
        """
        stats = {"processed": 0, "updated": 0, "errors": 0}
        
        since = since or (datetime.now(timezone.utc) - timedelta(hours=1))
        
        # Find recently updated events
        query = {"last_updated": {"$gt": since}}
        
        async for event in self._paginate_events(query, self.BATCH_SIZE):
            try:
                # Check if card exists
                existing = await self.cards_hot.find_one(
                    {"root_event_id": event.get("id")}
                )
                
                if existing:
                    # Update existing card
                    card = await self._project_event_to_card(event)
                    if card:
                        await self._upsert_card_hot(card)
                        stats["updated"] += 1
                else:
                    # Create new card
                    card = await self._project_event_to_card(event)
                    if card:
                        await self._upsert_card_hot(card)
                        stats["updated"] += 1
                
                stats["processed"] += 1
                
            except Exception as e:
                logger.error(f"Error updating event {event.get('id')}: {e}")
                stats["errors"] += 1
        
        return stats
    
    async def archive_old_cards(self) -> Dict:
        """
        Move old cards from hot to archive
        
        Should run daily or hourly
        """
        stats = {"archived": 0, "kept": 0, "errors": 0}
        
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.ARCHIVE_DAYS)
        
        # Find cards to archive (but never archive breaking)
        query = {
            "event_time": {"$lt": cutoff},
            "priority": {"$ne": FeedCardPriority.BREAKING.value}
        }
        
        # Use cursor to avoid memory issues
        cursor = self.cards_hot.find(query).batch_size(100)
        
        async for card in cursor:
            try:
                # Move to archive
                await self.cards_archive.update_one(
                    {"id": card["id"]},
                    {"$set": {**card, "archived_at": datetime.now(timezone.utc)}},
                    upsert=True
                )
                
                # Remove from hot
                await self.cards_hot.delete_one({"id": card["id"]})
                
                stats["archived"] += 1
                
            except Exception as e:
                logger.error(f"Error archiving card {card.get('id')}: {e}")
                stats["errors"] += 1
        
        # Update state
        self._state.last_archive_run = datetime.now(timezone.utc)
        self._state.cards_archived_24h += stats["archived"]
        await self._save_state()
        
        return stats
    
    async def rebuild_partial(
        self,
        entity_symbol: str = None,
        narrative_id: str = None,
        event_ids: List[str] = None
    ) -> Dict:
        """
        Rebuild subset of cards
        
        Use cases:
        - Entity data changed
        - Narrative reassigned
        - Score algorithm updated
        """
        stats = {"processed": 0, "updated": 0, "errors": 0}
        
        # Build query
        if event_ids:
            query = {"id": {"$in": event_ids}}
        elif entity_symbol:
            query = {"entities": entity_symbol.lower()}
        elif narrative_id:
            query = {"narrative_ids": narrative_id}
        else:
            return {"error": "No filter specified"}
        
        async for event in self._paginate_events(query, self.BATCH_SIZE * 10):
            try:
                card = await self._project_event_to_card(event)
                if card:
                    await self._upsert_card_hot(card)
                    stats["updated"] += 1
                
                stats["processed"] += 1
                
            except Exception as e:
                logger.error(f"Error rebuilding event {event.get('id')}: {e}")
                stats["errors"] += 1
        
        return stats
    
    async def rebuild_full(self) -> Dict:
        """
        Full rebuild of all feed cards
        
        WARNING: Expensive operation, run rarely (weekly maintenance)
        """
        stats = {"processed": 0, "created": 0, "errors": 0, "duration_seconds": 0}
        
        start_time = datetime.now(timezone.utc)
        logger.info("[FeedProjectionWorker] Starting FULL REBUILD...")
        
        # Clear hot collection (keep archive)
        # await self.cards_hot.delete_many({})  # Uncomment for true rebuild
        
        # Process all events
        async for event in self._paginate_events({}, limit=None):
            try:
                card = await self._project_event_to_card(event)
                if card:
                    # Determine if hot or archive
                    age_days = (datetime.now(timezone.utc) - card.get("event_time", datetime.now(timezone.utc))).days
                    
                    if age_days <= self.HOT_DAYS or card.get("priority") == FeedCardPriority.BREAKING.value:
                        await self._upsert_card_hot(card)
                    else:
                        await self.cards_archive.update_one(
                            {"id": card["id"]},
                            {"$set": card},
                            upsert=True
                        )
                    
                    stats["created"] += 1
                
                stats["processed"] += 1
                
                # Log progress
                if stats["processed"] % 1000 == 0:
                    logger.info(f"  → Processed {stats['processed']} events...")
                
            except Exception as e:
                logger.error(f"Error in full rebuild for event {event.get('id')}: {e}")
                stats["errors"] += 1
        
        # Update state
        self._state.last_full_rebuild = datetime.now(timezone.utc)
        await self._save_state()
        
        stats["duration_seconds"] = (datetime.now(timezone.utc) - start_time).total_seconds()
        logger.info(f"[FeedProjectionWorker] FULL REBUILD complete: {stats}")
        
        return stats
    
    # =========================================================================
    # PROJECTION LOGIC
    # =========================================================================
    
    async def _project_event_to_card(self, event: Dict) -> Optional[Dict]:
        """
        Project a root event into a feed card
        
        This is the core projection logic
        """
        if not event:
            return None
        
        event_id = event.get("id")
        if not event_id:
            return None
        
        # Get narrative if linked
        narrative = None
        narrative_ids = event.get("narrative_ids", [])
        if narrative_ids:
            narrative = await self.narratives.find_one({"id": narrative_ids[0]})
        
        # Calculate priority
        fomo_score = event.get("fomo_score", 0) or event.get("importance_score", 0)
        priority = self._calculate_priority(fomo_score)
        
        # Map event type to card type
        card_type = self._map_event_type(event.get("event_type", "news"))
        
        # Extract entities preview (max 5 for card display)
        entities_preview = []
        event_entities = event.get("event_entities", [])
        for ee in event_entities[:5]:
            entities_preview.append({
                "id": ee.get("entity_id"),
                "name": ee.get("entity_name"),
                "symbol": ee.get("entity_symbol"),
                "type": ee.get("entity_type"),
                "role": ee.get("role")
            })
        
        # Get primary symbol
        primary_symbol = None
        for ee in event_entities:
            if ee.get("entity_type") == "asset" and ee.get("entity_symbol"):
                primary_symbol = ee.get("entity_symbol")
                break
        
        # Sentiment label
        sentiment_score = event.get("sentiment_score", 0)
        sentiment = "neutral"
        if sentiment_score > 0.2:
            sentiment = "positive"
        elif sentiment_score < -0.2:
            sentiment = "negative"
        
        # Visual styling
        color = None
        if priority == FeedCardPriority.BREAKING.value:
            color = "#ef4444" if sentiment == "negative" else "#22c55e"
        
        # Build card
        card = {
            "id": f"fc_{event_id}",
            "root_event_id": event_id,
            "source_type": "event",
            
            # Content
            "title": event.get("title", ""),
            "summary": event.get("summary"),
            
            # Classification
            "card_type": card_type,
            "priority": priority,
            
            # Entities
            "entities": entities_preview,
            "primary_symbol": primary_symbol,
            
            # Narrative
            "narrative": narrative.get("name") if narrative else None,
            "narrative_id": narrative.get("id") if narrative else None,
            "narrative_momentum": narrative.get("momentum_score") if narrative else None,
            
            # Scores
            "sentiment": sentiment,
            "sentiment_score": sentiment_score,
            "importance": event.get("importance_score", 0),
            "impact": event.get("impact_score", 0),
            "confidence": event.get("confidence_score", 0),
            "fomo_score": fomo_score,
            
            # Visual
            "color": color,
            
            # Stats
            "source_count": event.get("source_count", 0),
            "update_count": event.get("update_count", 0),
            "view_count": 0,
            
            # Timeline
            "event_time": event.get("first_seen", datetime.now(timezone.utc)),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            
            # Tags for filtering
            "tags": event.get("entities", []),
            "topics": event.get("topics", [])
        }
        
        return card
    
    def _calculate_priority(self, fomo_score: float) -> str:
        """Calculate card priority from FOMO score"""
        if fomo_score >= self.BREAKING_THRESHOLD:
            return FeedCardPriority.BREAKING.value
        elif fomo_score >= self.HIGH_THRESHOLD:
            return FeedCardPriority.HIGH.value
        elif fomo_score <= self.LOW_THRESHOLD:
            return FeedCardPriority.LOW.value
        return FeedCardPriority.NORMAL.value
    
    def _map_event_type(self, event_type: str) -> str:
        """Map event type to card type"""
        mapping = {
            "funding": "funding",
            "unlock": "unlock",
            "listing": "listing",
            "delisting": "listing",
            "hack": "alert",
            "exploit": "alert",
            "regulation": "alert",
        }
        return mapping.get(event_type, "event")
    
    async def _upsert_card_hot(self, card: Dict):
        """Upsert card to hot collection"""
        await self.cards_hot.update_one(
            {"id": card["id"]},
            {"$set": card},
            upsert=True
        )
    
    # =========================================================================
    # CURSOR PAGINATION
    # =========================================================================
    
    async def _paginate_events(
        self,
        query: Dict,
        limit: int = None
    ) -> AsyncGenerator[Dict, None]:
        """
        Paginate through events using cursor
        
        Never loads entire collection into memory
        """
        batch_size = min(limit or self.BATCH_SIZE, 1000)
        total_yielded = 0
        last_id = None
        
        while True:
            # Build paginated query
            page_query = dict(query)
            if last_id:
                page_query["_id"] = {"$gt": last_id}
            
            # Fetch batch
            cursor = self.root_events.find(
                page_query,
                {"_id": 1}  # Get _id for pagination
            ).sort("_id", 1).limit(batch_size)
            
            batch = await cursor.to_list(length=batch_size)
            
            if not batch:
                break
            
            # Fetch full documents
            ids = [doc["_id"] for doc in batch]
            full_cursor = self.root_events.find({"_id": {"$in": ids}})
            full_docs = await full_cursor.to_list(length=batch_size)
            
            for doc in full_docs:
                # Remove _id for clean output
                doc.pop("_id", None)
                yield doc
                total_yielded += 1
                
                if limit and total_yielded >= limit:
                    return
            
            # Update cursor position
            last_id = batch[-1]["_id"]
            
            # Check if we've hit limit
            if limit and total_yielded >= limit:
                break
    
    # =========================================================================
    # FEED QUERIES (Hot collection only)
    # =========================================================================
    
    async def get_feed(
        self,
        limit: int = 50,
        cursor: str = None,
        card_type: str = None,
        min_fomo: float = 0,
        entity_symbol: str = None,
        narrative_id: str = None
    ) -> Dict:
        """
        Get feed with cursor pagination
        
        Returns:
        {
            "cards": [...],
            "next_cursor": "...",
            "has_more": bool
        }
        """
        query = {}
        
        # Decode cursor (format: timestamp_id)
        if cursor:
            try:
                parts = cursor.split("_", 1)
                cursor_time = datetime.fromisoformat(parts[0])
                cursor_id = parts[1] if len(parts) > 1 else None
                
                query["$or"] = [
                    {"event_time": {"$lt": cursor_time}},
                    {
                        "event_time": cursor_time,
                        "id": {"$lt": cursor_id} if cursor_id else {"$exists": True}
                    }
                ]
            except:
                pass
        
        # Filters
        if card_type:
            query["card_type"] = card_type
        
        if min_fomo > 0:
            query["fomo_score"] = {"$gte": min_fomo}
        
        if entity_symbol:
            query["entities.symbol"] = entity_symbol.upper()
        
        if narrative_id:
            query["narrative_id"] = narrative_id
        
        # Query with limit + 1 to check has_more
        cursor_result = self.cards_hot.find(query).sort([
            ("priority", -1),
            ("event_time", -1),
            ("id", -1)
        ]).limit(limit + 1)
        
        cards = await cursor_result.to_list(length=limit + 1)
        
        # Check if more results
        has_more = len(cards) > limit
        if has_more:
            cards = cards[:limit]
        
        # Build next cursor
        next_cursor = None
        if cards and has_more:
            last_card = cards[-1]
            event_time = last_card.get("event_time")
            if isinstance(event_time, datetime):
                next_cursor = f"{event_time.isoformat()}_{last_card.get('id', '')}"
        
        # Clean output
        for card in cards:
            card.pop("_id", None)
        
        return {
            "cards": cards,
            "next_cursor": next_cursor,
            "has_more": has_more,
            "count": len(cards)
        }
    
    async def get_breaking(self, limit: int = 10) -> List[Dict]:
        """Get breaking news cards"""
        cursor = self.cards_hot.find({
            "priority": FeedCardPriority.BREAKING.value
        }).sort("event_time", -1).limit(limit)
        
        cards = await cursor.to_list(length=limit)
        for card in cards:
            card.pop("_id", None)
        
        return cards
    
    async def get_entity_feed(self, symbol: str, limit: int = 30) -> List[Dict]:
        """Get feed for specific entity"""
        cursor = self.cards_hot.find({
            "entities.symbol": symbol.upper()
        }).sort([
            ("priority", -1),
            ("event_time", -1)
        ]).limit(limit)
        
        cards = await cursor.to_list(length=limit)
        for card in cards:
            card.pop("_id", None)
        
        return cards
    
    # =========================================================================
    # STATS
    # =========================================================================
    
    async def get_stats(self) -> Dict:
        """Get worker statistics"""
        hot_count = await self.cards_hot.count_documents({})
        archive_count = await self.cards_archive.count_documents({})
        
        # Count by priority
        priority_counts = {}
        for priority in FeedCardPriority:
            count = await self.cards_hot.count_documents({"priority": priority.value})
            priority_counts[priority.value] = count
        
        return {
            "hot_cards": hot_count,
            "archive_cards": archive_count,
            "total_cards": hot_count + archive_count,
            "priority_distribution": priority_counts,
            "state": self._state.dict() if self._state else None
        }


# =============================================================================
# SCHEDULER INTEGRATION
# =============================================================================

async def run_projection_jobs(db):
    """
    Run projection jobs (called by scheduler)
    """
    worker = FeedProjectionWorker(db)
    await worker.initialize()
    
    # Run incremental jobs
    stats = {
        "new_events": await worker.project_new_events(),
        "updates": await worker.update_changed_events(),
        "archive": await worker.archive_old_cards()
    }
    
    return stats
