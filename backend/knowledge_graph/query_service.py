"""
Graph Query Service - Query and traverse the knowledge graph

Responsibilities:
- Get node neighbors
- Get edges by node
- Path finding
- Graph statistics
- Network subgraph extraction
"""

import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
from motor.motor_asyncio import AsyncIOMotorDatabase

from .models import (
    GraphNetworkResponse, 
    GraphStatsResponse,
    NODE_TYPES,
    RELATION_SCOPE
)

# Redis cache for canonical resolution
from modules.cache.redis_client import cache_get, cache_set, is_redis_available

logger = logging.getLogger(__name__)

# Redis cache config
CANONICAL_CACHE_PREFIX = "canonical:"
CANONICAL_CACHE_TTL = 3600  # 1 hour

# ============================================
# CANONICAL IDENTITY RESOLUTION (DB-first + Redis cache)
# Priority: 1) Redis cache → 2) entity_aliases DB → 3) fallback map → 4) passthrough
# ============================================

# Small fallback map for core assets (used only if DB has no alias)
SYMBOL_FALLBACK = {
    "btc": "bitcoin",
    "xbt": "bitcoin",
    "eth": "ethereum",
    "ether": "ethereum",
    "sol": "solana",
    "bnb": "binance-coin",
    "arb": "arbitrum",
    "op": "optimism",
    "matic": "polygon",
}

# ============================================
# RELATION PRIORITY LAYER
# Higher priority = more important relations shown first
# ============================================

RELATION_PRIORITY = {
    "founded_by": 10,
    "founder": 10,
    "founded": 10,
    "co_founded_by": 10,
    "co_founder": 10,
    "invested_in": 9,
    "investor": 9,
    "investment": 9,
    "coinvested_with": 8,
    "coinvested": 8,
    "built_on": 7,
    "built_by": 7,
    "builds": 7,
    "ecosystem": 6,
    "partner": 5,
    "partnership": 5,
    "listed_on": 4,
    "listing": 4,
    "acquisition": 4,
    "acquired": 4,
    "transfer": 3,
    "transaction": 3,
    "event_linked": 2,
    "event": 2,
    "mention": 1,
    "mentioned": 1,
    "related": 1,
}

# Hub suppression: max edges per node in BFS
MAX_EDGES_PER_NODE = 25


def resolve_canonical_identity_sync(entity_id: str) -> str:
    """
    Synchronous fallback resolver (uses only SYMBOL_FALLBACK).
    Used when DB is not available.
    """
    if not entity_id:
        return entity_id
    
    normalized = entity_id.lower().strip()
    return SYMBOL_FALLBACK.get(normalized, normalized)


class GraphQueryService:
    """
    Query service for the knowledge graph.
    Provides API-ready responses for graph visualization.
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.nodes_collection = db.graph_nodes
        self.edges_collection = db.graph_relations
        # Alias collection is in fomo_intel database
        self._alias_db = None
        self._canonical_cache = {}  # In-memory cache for session
    
    @staticmethod
    def _node_entity_type(node: dict) -> str:
        """Get entity_type from node, compatible with both old and new data formats"""
        return node.get("entity_type") or node.get("type") or "unknown"
    
    @staticmethod
    def _node_entity_id(node: dict) -> str:
        """Get entity_id from node, compatible with both old and new data formats"""
        return node.get("entity_id") or node.get("entity") or node.get("cluster_id") or node.get("id", "")

    
    async def _get_alias_collection(self):
        """Get entity_aliases collection from fomo_intel database"""
        if self._alias_db is None:
            # Get client from current db and switch to fomo_intel
            client = self.db.client
            self._alias_db = client['fomo_intel']
        return self._alias_db.entity_aliases
    
    async def resolve_canonical_identity(self, entity_id: str) -> str:
        """
        Redis-cached DB-first canonical identity resolution.
        
        Priority:
        1. Redis cache (fastest)
        2. In-memory cache (fast)
        3. entity_aliases collection (source of truth)
        4. SYMBOL_FALLBACK map (for core assets)
        5. passthrough (return as-is)
        
        Examples:
            eth → ethereum (from DB or fallback)
            ETH → ethereum
            random-token → random-token (passthrough)
        """
        if not entity_id:
            return entity_id
        
        normalized = entity_id.lower().strip()
        
        # 1. Check Redis cache first (fastest)
        if is_redis_available():
            cache_key = f"{CANONICAL_CACHE_PREFIX}{normalized}"
            cached = await cache_get(cache_key)
            if cached:
                return cached
        
        # 2. Check in-memory cache
        if normalized in self._canonical_cache:
            return self._canonical_cache[normalized]
        
        canonical = normalized
        
        try:
            # 3. DB lookup (source of truth)
            alias_collection = await self._get_alias_collection()
            
            # Find any document where this value is in aliases array
            alias_doc = await alias_collection.find_one({"aliases": normalized})
            
            if alias_doc:
                # Extract canonical from entity_id (e.g., "asset:ethereum" → "ethereum")
                db_entity_id = alias_doc.get("entity_id", "")
                if ":" in db_entity_id:
                    canonical = db_entity_id.split(":", 1)[1]
                else:
                    canonical = db_entity_id
        except Exception as e:
            logger.debug(f"DB alias lookup failed: {e}")
        
        # 4. Fallback to symbol map if DB didn't resolve
        if canonical == normalized and normalized in SYMBOL_FALLBACK:
            canonical = SYMBOL_FALLBACK[normalized]
        
        # Cache the result in both caches
        self._canonical_cache[normalized] = canonical
        
        # Store in Redis (async, don't wait)
        if is_redis_available():
            cache_key = f"{CANONICAL_CACHE_PREFIX}{normalized}"
            await cache_set(cache_key, canonical, CANONICAL_CACHE_TTL)
        
        return canonical
    
    async def get_node(self, entity_type: str, entity_id: str) -> Optional[Dict[str, Any]]:
        """Get node by entity type and id, with canonical resolution"""
        # Direct lookup first - try both old and new field names
        node = await self.nodes_collection.find_one({
            "$or": [
                {"entity_type": entity_type, "entity_id": entity_id},
                {"type": entity_type, "entity": entity_id},
                {"type": entity_type, "cluster_id": entity_id},
            ]
        })
        
        # Try by id pattern
        if not node:
            node = await self.nodes_collection.find_one({"id": {"$regex": f"^{entity_type}:.*{entity_id}", "$options": "i"}})
        
        # Try canonical resolution if direct lookup fails
        if not node:
            try:
                from modules.knowledge_graph.canonical_resolver import get_canonical_resolver
                resolver = get_canonical_resolver(self.db)
                
                canonical_id, entity_data = await resolver.resolve(entity_id, entity_type)
                if canonical_id:
                    node = await self.nodes_collection.find_one({"id": canonical_id})
            except Exception as e:
                logger.debug(f"Canonical resolution failed: {e}")
        
        if node:
            # Add neighbor count
            edge_count = await self.edges_collection.count_documents({
                "$or": [
                    {"source_id": node["id"]},
                    {"target_id": node["id"]}
                ]
            })
            node["edge_count"] = edge_count
        
        return node
    
    async def get_node_by_id(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Get node by internal id"""
        return await self.nodes_collection.find_one({"id": node_id})
    
    async def get_edges(
        self,
        entity_type: str,
        entity_id: str,
        relation_type: Optional[str] = None,
        direction: str = "both",  # both, outgoing, incoming
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get edges for a node"""
        node = await self.get_node(entity_type, entity_id)
        if not node:
            return []
        
        node_id = node["id"]
        
        filter_dict = {}
        if direction == "outgoing":
            filter_dict["source_id"] = node_id
        elif direction == "incoming":
            filter_dict["target_id"] = node_id
        else:
            filter_dict["$or"] = [
                {"source_id": node_id},
                {"target_id": node_id}
            ]
        
        if relation_type:
            filter_dict["relation_type"] = relation_type
        
        cursor = self.edges_collection.find(filter_dict).limit(limit)
        return await cursor.to_list(length=limit)
    
    async def get_neighbors(
        self,
        entity_type: str,
        entity_id: str,
        neighbor_type: Optional[str] = None,
        relation_type: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get neighbor nodes for a node"""
        edges = await self.get_edges(entity_type, entity_id, relation_type, limit=limit * 2)
        
        node = await self.get_node(entity_type, entity_id)
        if not node:
            return []
        
        node_id = node["id"]
        neighbor_ids = set()
        
        for edge in edges:
            if edge["source_id"] == node_id:
                neighbor_ids.add(edge["target_id"])
            else:
                neighbor_ids.add(edge["source_id"])
        
        # Fetch neighbor nodes
        filter_dict = {"id": {"$in": list(neighbor_ids)}}
        if neighbor_type:
            filter_dict["$or"] = [{"entity_type": neighbor_type}, {"type": neighbor_type}]
        
        cursor = self.nodes_collection.find(filter_dict).limit(limit)
        return await cursor.to_list(length=limit)
    
    async def get_network(
        self,
        center_type: Optional[str] = None,
        center_id: Optional[str] = None,
        depth: int = 1,
        limit_nodes: int = 200,
        limit_edges: int = 500,
        node_types: Optional[List[str]] = None,
        relation_types: Optional[List[str]] = None
    ) -> GraphNetworkResponse:
        """
        Get graph network for visualization.
        
        If center_type/center_id provided, returns ego-network around that node.
        Otherwise returns full network sample.
        
        Features:
        - Canonical identity resolution (ETH/Ethereum/eth → single node)
        - Relation priority (founders > investors > ecosystem > mentions)
        - Hub suppression (max 25 edges per node)
        
        Returns format compatible with react-force-graph-2d:
        {
            "nodes": [{"id": "type:id", "label": "...", "type": "...", ...}],
            "edges": [{"source": "type:id", "target": "type:id", "relation": "...", ...}]
        }
        """
        # CANONICAL DEDUP: Track visited by canonical_id, not raw node_id
        visited_entities = set()  # canonical entity_id
        visited_node_ids = set()  # raw node_id for edge lookup
        canonical_to_node = {}    # canonical_id -> node data (first seen wins)
        edges_list = []
        
        if center_type and center_id:
            # Ego-network mode: start from center node
            center_node = await self.get_node(center_type, center_id)
            if not center_node:
                return GraphNetworkResponse(nodes=[], edges=[], stats={"error": "Center node not found"})
            
            # Resolve canonical identity for center node (DB-first)
            center_canonical = await self.resolve_canonical_identity(self._node_entity_id(center_node))
            
            # Add center node
            node_key = f"{self._node_entity_type(center_node)}:{center_canonical}"
            center_data = {
                "id": node_key,
                "label": center_node.get("label", center_node.get("entity", center_node.get("id", ""))),
                "type": self._node_entity_type(center_node),
                "entity_id": center_canonical,
                "size": 20,  # Larger for center
                "metadata": center_node.get("metadata", {})
            }
            
            visited_entities.add(center_canonical)
            visited_node_ids.add(center_node["id"])
            canonical_to_node[center_canonical] = center_data
            
            # Collect ALL node IDs belonging to this entity's cluster
            # This handles type prefix mismatch (cex:0x... vs wallet:0x...)
            cluster_id = center_node.get("cluster_id") or center_node.get("entity") or center_canonical
            all_cluster_nodes = []
            if cluster_id:
                cursor = self.nodes_collection.find(
                    {"$or": [{"cluster_id": cluster_id}, {"entity": cluster_id}]},
                    {"_id": 0, "id": 1}
                )
                async for doc in cursor:
                    all_cluster_nodes.append(doc["id"])
                    visited_node_ids.add(doc["id"])
            
            # Also create alternate IDs with different type prefixes for edge matching
            def get_address_variants(node_id):
                """Generate all possible ID variants for edge matching"""
                parts = node_id.split(":")
                if len(parts) >= 3:
                    # e.g., cex:0x28c6...:ethereum -> also check wallet:0x28c6...:ethereum
                    addr_chain = ":".join(parts[1:])
                    prefixes = ["wallet", "cex", "dex", "exchange", "protocol", "contract", "cluster", "bridge"]
                    return [f"{p}:{addr_chain}" for p in prefixes]
                return [node_id]
            
            # Build initial search set with all variants
            initial_ids = list(visited_node_ids)
            for nid in list(visited_node_ids):
                initial_ids.extend(get_address_variants(nid))
            initial_ids = list(set(initial_ids))
            
            # BFS to collect neighbors up to depth
            current_level = initial_ids
            
            for d in range(depth):
                next_level = []
                
                if not current_level:
                    break
                
                # Batch edge query for entire level
                edge_filter = {
                    "$or": [
                        {"source_id": {"$in": current_level}},
                        {"target_id": {"$in": current_level}}
                    ]
                }
                if relation_types:
                    edge_filter["relation_type"] = {"$in": relation_types}
                
                cursor = self.edges_collection.find(edge_filter)
                all_level_edges = await cursor.to_list(length=limit_edges * 2)
                
                # RELATION PRIORITY: Sort edges by importance
                all_level_edges = sorted(
                    all_level_edges,
                    key=lambda e: RELATION_PRIORITY.get(e.get("relation_type", ""), 0),
                    reverse=True
                )[:limit_edges]
                
                for edge in all_level_edges:
                    # Determine which endpoint(s) are new neighbors
                    src = edge.get("source_id", "")
                    tgt = edge.get("target_id", "")
                    
                    # Check both endpoints - one is in our set, the other is neighbor
                    src_known = src in visited_node_ids or src in current_level
                    tgt_known = tgt in visited_node_ids or tgt in current_level
                    
                    neighbor_ids_to_check = []
                    if src_known and not tgt_known:
                        neighbor_ids_to_check.append(tgt)
                    if tgt_known and not src_known:
                        neighbor_ids_to_check.append(src)
                    
                    for neighbor_id in neighbor_ids_to_check:
                        # Fetch neighbor if not visited
                        if neighbor_id not in visited_node_ids and len(canonical_to_node) < limit_nodes:
                            neighbor = await self.nodes_collection.find_one({"id": neighbor_id})
                            if neighbor:
                                if node_types and self._node_entity_type(neighbor) not in node_types:
                                    continue
                                
                                neighbor_canonical = await self.resolve_canonical_identity(self._node_entity_id(neighbor))
                                
                                if neighbor_canonical in visited_entities:
                                    visited_node_ids.add(neighbor_id)
                                    continue
                                
                                visited_entities.add(neighbor_canonical)
                                visited_node_ids.add(neighbor_id)
                                next_level.append(neighbor_id)
                                # Also add address variants for next BFS level
                                next_level.extend(get_address_variants(neighbor_id))
                                
                                neighbor_key = f"{self._node_entity_type(neighbor)}:{neighbor_canonical}"
                                canonical_to_node[neighbor_canonical] = {
                                    "id": neighbor_key,
                                    "label": neighbor.get("label", neighbor.get("entity", "")),
                                    "type": self._node_entity_type(neighbor),
                                    "entity_id": neighbor_canonical,
                                    "size": 10,
                                    "metadata": neighbor.get("metadata", {})
                                }
                    
                    # Track raw node IDs for edge resolution
                    visited_node_ids.add(src)
                    visited_node_ids.add(tgt)
                
                current_level = list(set(next_level))
                if not current_level:
                    break
            
            # After BFS: resolve edges between all discovered nodes
            # Re-fetch all edges connecting visited nodes
            all_node_ids = list(visited_node_ids)
            if all_node_ids:
                edge_cursor = self.edges_collection.find({
                    "$or": [
                        {"source_id": {"$in": all_node_ids}},
                        {"target_id": {"$in": all_node_ids}}
                    ]
                })
                all_edges = await edge_cursor.to_list(length=limit_edges)
                
                seen_edge_keys = set()
                for edge in all_edges:
                    src_id = edge.get("source_id", "")
                    tgt_id = edge.get("target_id", "")
                    
                    # Both endpoints must be in visited set
                    if src_id not in visited_node_ids or tgt_id not in visited_node_ids:
                        continue
                    
                    from_raw = await self.nodes_collection.find_one({"id": src_id})
                    to_raw = await self.nodes_collection.find_one({"id": tgt_id})
                    
                    if from_raw and to_raw:
                        from_canonical = await self.resolve_canonical_identity(self._node_entity_id(from_raw))
                        to_canonical = await self.resolve_canonical_identity(self._node_entity_id(to_raw))
                        
                        from_node = canonical_to_node.get(from_canonical)
                        to_node = canonical_to_node.get(to_canonical)
                        
                        if from_node and to_node and from_canonical != to_canonical:
                            edge_key = f"{from_node['id']}-{edge.get('relation_type','')}-{to_node['id']}"
                            if edge_key in seen_edge_keys:
                                continue
                            seen_edge_keys.add(edge_key)
                            
                            relation_type = edge.get("relation_type", "")
                            edges_list.append({
                                "source": from_node["id"],
                                "target": to_node["id"],
                                "relation": relation_type,
                                "weight": edge.get("weight", 1.0),
                                "value": edge.get("weight", 1.0) * 100 - 50,
                                "scope": RELATION_SCOPE.get(relation_type, "other"),
                                "confidence": edge.get("confidence", 0.8),
                                "context": edge.get("context"),
                                "data_source": edge.get("data_source", edge.get("source_type", "direct")),
                                "priority": RELATION_PRIORITY.get(relation_type, 0),
                                "metadata": edge.get("metadata", {})
                            })
        
        else:
            # Full network sample mode - also apply canonical dedup
            node_filter = {}
            if node_types:
                node_filter["$or"] = [{"entity_type": {"$in": node_types}}, {"type": {"$in": node_types}}]
            
            # Get sample of nodes with canonical dedup
            cursor = self.nodes_collection.find(node_filter).limit(limit_nodes * 2)  # Fetch extra to account for dedup
            async for node in cursor:
                if len(canonical_to_node) >= limit_nodes:
                    break
                    
                # Resolve canonical identity (DB-first)
                node_canonical = await self.resolve_canonical_identity(self._node_entity_id(node))
                
                # Skip if canonical already seen
                if node_canonical in visited_entities:
                    visited_node_ids.add(node["id"])
                    continue
                
                visited_entities.add(node_canonical)
                visited_node_ids.add(node["id"])
                
                node_key = f"{self._node_entity_type(node)}:{node_canonical}"
                canonical_to_node[node_canonical] = {
                    "id": node_key,
                    "label": node.get("label", node.get("entity", node.get("id", ""))),
                    "type": self._node_entity_type(node),
                    "entity_id": node_canonical,
                    "size": 15 if self._node_entity_type(node) in ["exchange", "fund", "cex"] else 10,
                    "metadata": node.get("metadata", {})
                }
            
            # Get edges between these nodes
            node_ids = list(visited_node_ids)
            edge_filter = {
                "source_id": {"$in": node_ids},
                "target_id": {"$in": node_ids}
            }
            if relation_types:
                edge_filter["relation_type"] = {"$in": relation_types}
            
            # Fetch and sort edges by priority
            cursor = self.edges_collection.find(edge_filter)
            all_edges = await cursor.to_list(length=limit_edges * 2)
            
            # RELATION PRIORITY: Sort by importance
            all_edges = sorted(
                all_edges,
                key=lambda e: RELATION_PRIORITY.get(e.get("relation_type", ""), 0),
                reverse=True
            )[:limit_edges]
            
            for edge in all_edges:
                # Resolve canonical for edge endpoints
                from_raw = await self.nodes_collection.find_one({"id": edge["source_id"]})
                to_raw = await self.nodes_collection.find_one({"id": edge["target_id"]})
                
                if from_raw and to_raw:
                    from_canonical = await self.resolve_canonical_identity(self._node_entity_id(from_raw))
                    to_canonical = await self.resolve_canonical_identity(self._node_entity_id(to_raw))
                    
                    from_node = canonical_to_node.get(from_canonical)
                    to_node = canonical_to_node.get(to_canonical)
                    
                    if from_node and to_node and from_canonical != to_canonical:
                        relation_type = edge.get("relation_type", "")
                        edges_list.append({
                            "source": from_node["id"],
                            "target": to_node["id"],
                            "relation": relation_type,
                            "weight": edge.get("weight", 1.0),
                            "value": edge.get("weight", 1.0) * 100 - 50,
                            # G3: Graph Context Layer
                            "scope": RELATION_SCOPE.get(relation_type, "other"),
                            "confidence": edge.get("confidence", 0.8),
                            "context": edge.get("context"),
                            "data_source": edge.get("data_source", edge.get("source_type", "direct")),
                            "priority": RELATION_PRIORITY.get(relation_type, 0),
                            "metadata": edge.get("metadata", {})
                        })
        
        # Keep ALL edges - multiple edges between same nodes represent multiple investments/relations
        # We DON'T deduplicate to show real investment count
        # Previously we deduped by source|target|relation which lost multi-round investments
        
        return GraphNetworkResponse(
            nodes=list(canonical_to_node.values()),
            edges=edges_list,  # Return ALL edges (not deduplicated)
            stats={
                "node_count": len(canonical_to_node),
                "edge_count": len(edges_list),
                "center": f"{center_type}:{center_id}" if center_type else None,
                "depth": depth
            }
        )
    
    async def get_stats(self) -> GraphStatsResponse:
        """Get graph statistics"""
        # Count nodes by type
        nodes_pipeline = [
            {"$group": {"_id": "$entity_type", "count": {"$sum": 1}}}
        ]
        nodes_by_type = {}
        async for doc in self.nodes_collection.aggregate(nodes_pipeline):
            key = doc["_id"] if doc["_id"] is not None else "unknown"
            nodes_by_type[str(key)] = doc["count"]
        
        # Count edges by type
        edges_pipeline = [
            {"$group": {"_id": "$relation_type", "count": {"$sum": 1}}}
        ]
        edges_by_type = {}
        async for doc in self.edges_collection.aggregate(edges_pipeline):
            key = doc["_id"] if doc["_id"] is not None else "unknown"
            edges_by_type[str(key)] = doc["count"]
        
        # Get last rebuild
        last_snapshot = await self.db.graph_snapshots.find_one(
            sort=[("created_at", -1)]
        )
        
        return GraphStatsResponse(
            total_nodes=sum(nodes_by_type.values()),
            total_edges=sum(edges_by_type.values()),
            nodes_by_type=nodes_by_type,
            edges_by_type=edges_by_type,
            last_rebuild=last_snapshot["created_at"] if last_snapshot else None
        )
    
    async def search(
        self,
        query: str,
        entity_type: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Search nodes by label/slug - deduplicated by entity"""
        filter_dict = {
            "$or": [
                {"label": {"$regex": query, "$options": "i"}},
                {"slug": {"$regex": query, "$options": "i"}},
                {"entity_id": {"$regex": query, "$options": "i"}},
                {"entity": {"$regex": query, "$options": "i"}},
                {"cluster_id": {"$regex": query, "$options": "i"}},
                {"id": {"$regex": query, "$options": "i"}},
            ]
        }
        if entity_type:
            filter_dict["$or"] = [
                *filter_dict["$or"],
            ]
            filter_dict = {"$and": [filter_dict, {"$or": [{"entity_type": entity_type}, {"type": entity_type}]}]}
        
        cursor = self.nodes_collection.find(filter_dict).limit(limit * 5)
        results = []
        seen_entities = set()
        async for node in cursor:
            et = self._node_entity_type(node)
            eid = self._node_entity_id(node)
            dedup_key = f"{et}:{eid}".lower()
            if dedup_key in seen_entities:
                continue
            seen_entities.add(dedup_key)
            # Clean label: remove suffixes like "hot_wallet", "cold_wallet"
            raw_label = node.get("label", node.get("entity", node.get("id", "")))
            clean_label = raw_label
            for suffix in (" hot_wallet", " cold_wallet", " deposit", " withdrawal"):
                if clean_label.lower().endswith(suffix):
                    clean_label = clean_label[:len(clean_label)-len(suffix)]
            results.append({
                "id": dedup_key,
                "label": clean_label or eid,
                "type": et,
                "entity_id": eid,
                "slug": node.get("slug")
            })
            if len(results) >= limit:
                break
        return results
    
    async def get_related(
        self,
        entity_type: str,
        entity_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get related entities based on shared connections"""
        node = await self.get_node(entity_type, entity_id)
        if not node:
            return []
        
        # Find entities that share connections
        # For projects: shared investors, shared founders
        # For funds: shared portfolio companies
        # For persons: shared organizations
        
        neighbors = await self.get_neighbors(entity_type, entity_id, limit=50)
        neighbor_ids = [n["id"] for n in neighbors]
        
        # Find other nodes connected to same neighbors
        related_pipeline = [
            {"$match": {
                "$or": [
                    {"source_id": {"$in": neighbor_ids}},
                    {"target_id": {"$in": neighbor_ids}}
                ]
            }},
            {"$project": {
                "other_node": {
                    "$cond": [
                        {"$in": ["$source_id", neighbor_ids]},
                        "$target_id",
                        "$source_id"
                    ]
                }
            }},
            {"$match": {"other_node": {"$ne": node["id"]}}},
            {"$group": {"_id": "$other_node", "shared_count": {"$sum": 1}}},
            {"$sort": {"shared_count": -1}},
            {"$limit": limit}
        ]
        
        related = []
        async for doc in self.edges_collection.aggregate(related_pipeline):
            related_node = await self.nodes_collection.find_one({"id": doc["_id"]})
            if related_node and self._node_entity_type(related_node) == entity_type:
                related.append({
                    "id": f"{self._node_entity_type(related_node)}:{self._node_entity_id(related_node)}",
                    "label": related_node.get("label", related_node.get("entity", "")),
                    "type": self._node_entity_type(related_node),
                    "shared_connections": doc["shared_count"]
                })
        
        return related
