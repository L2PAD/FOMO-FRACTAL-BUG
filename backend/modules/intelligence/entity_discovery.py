"""
Entity-Driven Crawling
======================

Instead of source-centric approach (source → parser → data),
this uses entity-centric approach (entity → discover sources → data).

When a new entity is detected, the system automatically:
1. Searches for entity across known platforms
2. Discovers new sources (docs, repos, socials)
3. Extracts relationships
4. Builds graph edges

This allows the system to scale by entities, not parsers.

Collections:
    entity_discovery_queue - Entities pending discovery
    entity_discovery_results - Discovered sources per entity
    source_state - Incremental extraction state
"""

import logging
import re
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
import hashlib

logger = logging.getLogger(__name__)

# Discovery sources configuration
DISCOVERY_SOURCES = {
    "github": {
        "url_pattern": "https://github.com/{entity_id}",
        "search_pattern": "https://github.com/search?q={entity_name}",
        "priority": 1
    },
    "twitter": {
        "url_pattern": "https://twitter.com/{entity_id}",
        "priority": 2
    },
    "defillama": {
        "search_pattern": "https://defillama.com/protocol/{entity_id}",
        "priority": 1
    },
    "coingecko": {
        "search_pattern": "https://www.coingecko.com/en/coins/{entity_id}",
        "priority": 2
    },
    "cryptorank": {
        "search_pattern": "https://cryptorank.io/ico/{entity_id}",
        "priority": 1
    }
}


class EntityDiscoveryEngine:
    """
    Entity-driven crawling engine.
    Discovers sources and data based on entities, not parsers.
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.queue = db.entity_discovery_queue
        self.results = db.entity_discovery_results
        self.source_state = db.source_state
        
        # Entity collections
        self.graph_nodes = db.graph_nodes
        self.graph_edges = db.graph_edges
    
    async def ensure_indexes(self):
        """Create indexes for discovery collections"""
        await self.queue.create_index("entity_key", unique=True)
        await self.queue.create_index("status")
        await self.queue.create_index("priority")
        await self.queue.create_index("created_at")
        
        await self.results.create_index("entity_key")
        await self.results.create_index("source_type")
        await self.results.create_index("discovered_at")
        
        await self.source_state.create_index("source_id", unique=True)
        await self.source_state.create_index("source_type")
        
        logger.info("[EntityDiscovery] Indexes created")
    
    async def enqueue_entity(
        self,
        entity_type: str,
        entity_id: str,
        entity_name: str = None,
        priority: int = 2
    ) -> str:
        """
        Add entity to discovery queue.
        Priority: 1=high, 2=normal, 3=low
        """
        entity_key = f"{entity_type}:{entity_id}"
        now = datetime.now(timezone.utc)
        
        # Check if already exists
        existing = await self.queue.find_one({"entity_key": entity_key})
        if existing:
            return existing.get("entity_key")
        
        item = {
            "entity_key": entity_key,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "entity_name": entity_name or entity_id,
            "priority": priority,
            "status": "pending",
            "created_at": now,
            "attempts": 0
        }
        
        await self.queue.insert_one(item)
        
        logger.info(f"[EntityDiscovery] Enqueued: {entity_key}")
        
        return entity_key
    
    async def discover_entity(
        self,
        entity_key: str
    ) -> Dict[str, Any]:
        """
        Run discovery for a single entity.
        Searches across configured sources.
        """
        now = datetime.now(timezone.utc)
        
        # Get from queue
        item = await self.queue.find_one({"entity_key": entity_key})
        if not item:
            return {"error": "Entity not in queue"}
        
        entity_type = item.get("entity_type")
        entity_id = item.get("entity_id")
        entity_name = item.get("entity_name", entity_id)
        
        # Update status
        await self.queue.update_one(
            {"entity_key": entity_key},
            {
                "$set": {"status": "processing"},
                "$inc": {"attempts": 1}
            }
        )
        
        discovered = []
        
        # Try each discovery source
        for source_type, config in DISCOVERY_SOURCES.items():
            try:
                result = await self._discover_from_source(
                    source_type, config,
                    entity_type, entity_id, entity_name
                )
                
                if result:
                    discovered.append(result)
                    
                    # Save discovery result
                    await self.results.update_one(
                        {
                            "entity_key": entity_key,
                            "source_type": source_type
                        },
                        {
                            "$set": {
                                **result,
                                "entity_key": entity_key,
                                "source_type": source_type,
                                "discovered_at": now
                            }
                        },
                        upsert=True
                    )
            except Exception as e:
                logger.error(f"[EntityDiscovery] Error discovering {entity_key} from {source_type}: {e}")
        
        # Update queue status
        await self.queue.update_one(
            {"entity_key": entity_key},
            {
                "$set": {
                    "status": "completed",
                    "completed_at": now,
                    "sources_found": len(discovered)
                }
            }
        )
        
        logger.info(f"[EntityDiscovery] {entity_key}: found {len(discovered)} sources")
        
        return {
            "entity_key": entity_key,
            "sources_discovered": len(discovered),
            "results": discovered
        }
    
    async def _discover_from_source(
        self,
        source_type: str,
        config: Dict,
        entity_type: str,
        entity_id: str,
        entity_name: str
    ) -> Optional[Dict]:
        """
        Try to discover entity data from a specific source.
        This is a placeholder - actual implementation would make HTTP requests.
        """
        # Build potential URLs
        urls = []
        
        if "url_pattern" in config:
            urls.append(config["url_pattern"].format(
                entity_id=entity_id,
                entity_name=entity_name.replace(" ", "-").lower()
            ))
        
        if "search_pattern" in config:
            urls.append(config["search_pattern"].format(
                entity_id=entity_id,
                entity_name=entity_name.replace(" ", "+")
            ))
        
        # In real implementation, would check if URLs are valid
        # For now, return discovery metadata
        return {
            "source_type": source_type,
            "potential_urls": urls,
            "priority": config.get("priority", 2),
            "status": "discovered"  # or "verified" after HTTP check
        }
    
    async def process_queue(self, limit: int = 10) -> Dict[str, Any]:
        """
        Process pending entities in queue.
        Called by scheduler job.
        """
        now = datetime.now(timezone.utc)
        processed = 0
        errors = 0
        
        # Get pending items sorted by priority
        cursor = self.queue.find(
            {"status": "pending"}
        ).sort([("priority", 1), ("created_at", 1)]).limit(limit)
        
        async for item in cursor:
            try:
                await self.discover_entity(item["entity_key"])
                processed += 1
            except Exception as e:
                logger.error(f"[EntityDiscovery] Error processing {item['entity_key']}: {e}")
                errors += 1
                
                # Mark as failed
                await self.queue.update_one(
                    {"entity_key": item["entity_key"]},
                    {"$set": {"status": "failed", "error": str(e)}}
                )
        
        return {
            "processed": processed,
            "errors": errors,
            "processed_at": now.isoformat()
        }
    
    async def get_queue_stats(self) -> Dict[str, Any]:
        """Get discovery queue statistics"""
        pipeline = [
            {"$group": {
                "_id": "$status",
                "count": {"$sum": 1}
            }}
        ]
        
        status_counts = await self.queue.aggregate(pipeline).to_list(10)
        
        total_results = await self.results.count_documents({})
        
        return {
            "queue_by_status": {s["_id"]: s["count"] for s in status_counts},
            "total_discoveries": total_results
        }
    
    async def get_entity_discoveries(
        self,
        entity_key: str
    ) -> List[Dict]:
        """Get all discoveries for an entity"""
        cursor = self.results.find(
            {"entity_key": entity_key},
            {"_id": 0}
        )
        
        return await cursor.to_list(length=50)


class IncrementalExtractor:
    """
    Incremental extraction for parsers.
    Tracks state so parsers only fetch new data.
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.source_state = db.source_state
    
    async def get_state(self, source_id: str) -> Optional[Dict]:
        """Get extraction state for a source"""
        state = await self.source_state.find_one(
            {"source_id": source_id},
            {"_id": 0}
        )
        return state
    
    async def update_state(
        self,
        source_id: str,
        cursor: str = None,
        last_item_id: str = None,
        last_item_hash: str = None,
        items_fetched: int = 0
    ) -> Dict:
        """Update extraction state after successful fetch"""
        now = datetime.now(timezone.utc)
        
        update = {
            "source_id": source_id,
            "last_run": now,
            "last_success": now
        }
        
        if cursor:
            update["cursor"] = cursor
        if last_item_id:
            update["last_item_id"] = last_item_id
        if last_item_hash:
            update["last_item_hash"] = last_item_hash
        
        result = await self.source_state.update_one(
            {"source_id": source_id},
            {
                "$set": update,
                "$inc": {
                    "runs_count": 1,
                    "total_items_fetched": items_fetched
                }
            },
            upsert=True
        )
        
        return update
    
    async def mark_failed(self, source_id: str, error: str):
        """Mark source extraction as failed"""
        now = datetime.now(timezone.utc)
        
        await self.source_state.update_one(
            {"source_id": source_id},
            {
                "$set": {
                    "last_run": now,
                    "last_error": error,
                    "last_error_at": now
                },
                "$inc": {"error_count": 1}
            },
            upsert=True
        )
    
    async def should_fetch(
        self,
        source_id: str,
        min_interval_minutes: int = 5
    ) -> bool:
        """Check if enough time has passed since last fetch"""
        state = await self.get_state(source_id)
        
        if not state:
            return True
        
        last_run = state.get("last_run")
        if not last_run:
            return True
        
        min_interval = timedelta(minutes=min_interval_minutes)
        return datetime.now(timezone.utc) - last_run >= min_interval
    
    async def compute_hash(self, content: str) -> str:
        """Compute content hash for change detection"""
        return hashlib.md5(content.encode()).hexdigest()
    
    async def is_content_changed(
        self,
        source_id: str,
        new_hash: str
    ) -> bool:
        """Check if content has changed since last fetch"""
        state = await self.get_state(source_id)
        
        if not state:
            return True
        
        return state.get("last_item_hash") != new_hash
    
    async def get_all_states(self) -> List[Dict]:
        """Get all source states"""
        cursor = self.source_state.find({}, {"_id": 0})
        return await cursor.to_list(length=500)


# Singletons
_discovery_engine: Optional[EntityDiscoveryEngine] = None
_incremental_extractor: Optional[IncrementalExtractor] = None


def get_entity_discovery_engine(db: AsyncIOMotorDatabase = None) -> EntityDiscoveryEngine:
    """Get or create discovery engine"""
    global _discovery_engine
    if db is not None:
        _discovery_engine = EntityDiscoveryEngine(db)
    return _discovery_engine


def get_incremental_extractor(db: AsyncIOMotorDatabase = None) -> IncrementalExtractor:
    """Get or create incremental extractor"""
    global _incremental_extractor
    if db is not None:
        _incremental_extractor = IncrementalExtractor(db)
    return _incremental_extractor
