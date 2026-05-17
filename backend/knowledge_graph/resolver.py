"""
Graph Resolver - Resolves entities to graph nodes

Responsibilities:
- Find or create nodes for entities
- Normalize business keys
- Maintain node uniqueness (entity_type, entity_id)
"""

import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from motor.motor_asyncio import AsyncIOMotorDatabase

from .models import GraphNode, NODE_TYPES

logger = logging.getLogger(__name__)


class GraphResolver:
    """
    Resolves entities to graph nodes.
    Ensures unique nodes per (entity_type, entity_id) pair.
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.nodes_collection = db.graph_nodes
        self._cache: Dict[str, str] = {}  # node_key -> node_id cache
    
    async def ensure_indexes(self):
        """Create required indexes for graph_nodes"""
        await self.nodes_collection.create_index(
            [("entity_type", 1), ("entity_id", 1)],
            unique=True,
            name="unique_entity"
        )
        await self.nodes_collection.create_index("entity_type", name="idx_entity_type")
        await self.nodes_collection.create_index("entity_id", name="idx_entity_id")
        await self.nodes_collection.create_index("slug", name="idx_slug")
        await self.nodes_collection.create_index(
            [("label", "text")],
            name="text_label"
        )
        logger.info("[GraphResolver] Indexes created for graph_nodes")
    
    def make_node_key(self, entity_type: str, entity_id: str) -> str:
        """Create canonical node key"""
        return f"{entity_type}:{entity_id}"
    
    async def resolve(
        self,
        entity_type: str,
        entity_id: str,
        label: str,
        slug: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        status: str = "active"
    ) -> str:
        """
        Resolve entity to graph node.
        Returns node_id (creates if not exists).
        """
        if entity_type not in NODE_TYPES:
            logger.warning(f"[GraphResolver] Unknown entity type: {entity_type}")
        
        node_key = self.make_node_key(entity_type, entity_id)
        
        # Check cache first
        if node_key in self._cache:
            return self._cache[node_key]
        
        # Try to find existing node
        existing = await self.nodes_collection.find_one({
            "entity_type": entity_type,
            "entity_id": entity_id
        })
        
        if existing:
            node_id = existing["id"]
            self._cache[node_key] = node_id
            
            # Update if label changed
            if existing.get("label") != label:
                await self.nodes_collection.update_one(
                    {"id": node_id},
                    {"$set": {
                        "label": label,
                        "updated_at": datetime.now(timezone.utc)
                    }}
                )
            return node_id
        
        # Create new node
        node = GraphNode(
            entity_type=entity_type,
            entity_id=entity_id,
            label=label,
            slug=slug or entity_id,
            status=status,
            metadata=metadata or {}
        )
        
        try:
            await self.nodes_collection.insert_one(node.model_dump())
            self._cache[node_key] = node.id
            logger.debug(f"[GraphResolver] Created node: {node_key} -> {node.id}")
            return node.id
        except Exception as e:
            # Handle race condition - another process might have created it
            logger.warning(f"[GraphResolver] Insert failed, retrying lookup: {e}")
            existing = await self.nodes_collection.find_one({
                "entity_type": entity_type,
                "entity_id": entity_id
            })
            if existing:
                node_id = existing["id"]
                self._cache[node_key] = node_id
                return node_id
            raise
    
    async def resolve_batch(
        self,
        entities: List[Dict[str, Any]]
    ) -> Dict[str, str]:
        """
        Resolve multiple entities to nodes.
        Returns dict of node_key -> node_id.
        """
        results = {}
        for entity in entities:
            try:
                node_id = await self.resolve(
                    entity_type=entity["entity_type"],
                    entity_id=entity["entity_id"],
                    label=entity["label"],
                    slug=entity.get("slug"),
                    metadata=entity.get("metadata"),
                    status=entity.get("status", "active")
                )
                node_key = self.make_node_key(entity["entity_type"], entity["entity_id"])
                results[node_key] = node_id
            except Exception as e:
                logger.error(f"[GraphResolver] Failed to resolve entity: {entity}, error: {e}")
        return results
    
    async def get_node_by_key(self, entity_type: str, entity_id: str) -> Optional[Dict[str, Any]]:
        """Get node by entity type and id"""
        return await self.nodes_collection.find_one({
            "entity_type": entity_type,
            "entity_id": entity_id
        })
    
    async def get_node_by_id(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Get node by node id"""
        return await self.nodes_collection.find_one({"id": node_id})
    
    async def search_nodes(
        self,
        query: str,
        entity_type: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Search nodes by label"""
        filter_dict = {}
        if entity_type:
            filter_dict["entity_type"] = entity_type
        
        if query:
            filter_dict["$or"] = [
                {"label": {"$regex": query, "$options": "i"}},
                {"slug": {"$regex": query, "$options": "i"}},
                {"entity_id": {"$regex": query, "$options": "i"}}
            ]
        
        cursor = self.nodes_collection.find(filter_dict).limit(limit)
        return await cursor.to_list(length=limit)
    
    def clear_cache(self):
        """Clear node cache"""
        self._cache.clear()
