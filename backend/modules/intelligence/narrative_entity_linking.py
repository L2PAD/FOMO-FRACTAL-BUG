"""
Narrative Entity Linking
========================

Links narratives to entities bidirectionally:
- narrative → top entities (which projects/funds are most relevant)
- entity → narratives (which narratives is this entity part of)

This bridges:
- narrative_layer.py (narratives, topics)
- graph_layers.py (entity relationships)
- entity_momentum.py (momentum scoring)

Key methods:
- link_entity_to_narrative: Create entity-narrative link
- get_top_narratives_for_entity: Which narratives feature this entity
- get_top_entities_for_narrative: Top momentum entities in narrative
- detect_entity_narrative_relevance: Auto-detect narrative fit

Collections:
    narrative_entities - Links between narratives and entities
    narrative_exposure - Aggregated narrative exposure per entity
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)


class NarrativeEntityLinker:
    """
    Service for linking narratives to graph entities.
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.narrative_entities = db.narrative_entities
        self.narrative_exposure = db.narrative_exposure
        
        # Related collections
        self.narratives = db.narratives
        self.graph_nodes = db.graph_nodes
        self.entity_momentum = db.entity_momentum
        self.intelligence_edges = db.graph_intelligence_edges
    
    async def ensure_indexes(self):
        """Create indexes for linking collections"""
        await self.narrative_entities.create_index(
            [("narrative_id", 1), ("entity_key", 1)],
            unique=True
        )
        await self.narrative_entities.create_index("narrative_id")
        await self.narrative_entities.create_index("entity_key")
        await self.narrative_entities.create_index("entity_type")
        await self.narrative_entities.create_index("relevance_score")
        await self.narrative_entities.create_index("is_key_player")
        
        await self.narrative_exposure.create_index("entity_key", unique=True)
        await self.narrative_exposure.create_index("total_exposure")
        
        logger.info("[NarrativeLinker] Indexes created")
    
    async def link_entity_to_narrative(
        self,
        narrative_id: str,
        entity_type: str,
        entity_id: str,
        relevance_score: float = 0.5,
        is_key_player: bool = False,
        source: str = "manual"
    ) -> Dict[str, Any]:
        """
        Create or update link between entity and narrative.
        """
        entity_key = f"{entity_type}:{entity_id}"
        now = datetime.now(timezone.utc)
        
        link = {
            "narrative_id": narrative_id,
            "entity_key": entity_key,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "relevance_score": relevance_score,
            "is_key_player": is_key_player,
            "source": source,
            "updated_at": now
        }
        
        await self.narrative_entities.update_one(
            {"narrative_id": narrative_id, "entity_key": entity_key},
            {
                "$set": link,
                "$setOnInsert": {"created_at": now}
            },
            upsert=True
        )
        
        # Update entity's narrative exposure
        await self._update_entity_exposure(entity_key)
        
        # Create intelligence edge
        await self._create_narrative_edge(narrative_id, entity_key, relevance_score)
        
        logger.debug(f"[NarrativeLinker] Linked {entity_key} to {narrative_id}")
        
        return link
    
    async def get_top_narratives_for_entity(
        self,
        entity_type: str,
        entity_id: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Get top narratives for an entity.
        Returns narratives sorted by relevance.
        """
        entity_key = f"{entity_type}:{entity_id}"
        
        # Get narrative links
        cursor = self.narrative_entities.find(
            {"entity_key": entity_key},
            {"_id": 0}
        ).sort("relevance_score", -1).limit(limit)
        
        links = await cursor.to_list(length=limit)
        
        # Enrich with narrative details
        results = []
        for link in links:
            narrative = await self.narratives.find_one(
                {"id": link["narrative_id"]},
                {"_id": 0, "id": 1, "name": 1, "canonical_name": 1, 
                 "momentum_score": 1, "lifecycle": 1}
            )
            
            if narrative:
                results.append({
                    **link,
                    "narrative": narrative
                })
        
        return results
    
    async def get_top_entities_for_narrative(
        self,
        narrative_id: str,
        entity_type: str = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Get top entities for a narrative.
        Returns entities sorted by momentum score.
        """
        query = {"narrative_id": narrative_id}
        if entity_type:
            query["entity_type"] = entity_type
        
        # Get entity links
        cursor = self.narrative_entities.find(
            query,
            {"_id": 0}
        ).sort("relevance_score", -1).limit(limit * 2)  # Get more to sort by momentum
        
        links = await cursor.to_list(length=limit * 2)
        
        # Enrich with momentum data
        results = []
        for link in links:
            momentum = await self.entity_momentum.find_one(
                {"entity_key": link["entity_key"]},
                {"_id": 0, "momentum_score": 1, "momentum_velocity": 1}
            )
            
            # Get entity label from graph
            parts = link["entity_key"].split(":")
            node = await self.graph_nodes.find_one(
                {"entity_type": parts[0], "entity_id": parts[1]},
                {"_id": 0, "label": 1}
            )
            
            results.append({
                **link,
                "label": node.get("label") if node else parts[1],
                "momentum_score": momentum.get("momentum_score", 0) if momentum else 0,
                "momentum_velocity": momentum.get("momentum_velocity", 0) if momentum else 0
            })
        
        # Sort by momentum
        results.sort(key=lambda x: x.get("momentum_score", 0), reverse=True)
        
        return results[:limit]
    
    async def detect_entity_narrative_relevance(
        self,
        entity_type: str,
        entity_id: str
    ) -> List[Dict[str, Any]]:
        """
        Auto-detect which narratives an entity is relevant to.
        Uses keyword/topic matching.
        """
        entity_key = f"{entity_type}:{entity_id}"
        matched = []
        
        # Get entity info
        node = await self.graph_nodes.find_one({
            "entity_type": entity_type,
            "entity_id": entity_id
        })
        
        if not node:
            return []
        
        entity_label = node.get("label", entity_id)
        entity_slug = node.get("slug", entity_id)
        
        # Get all active narratives
        cursor = self.narratives.find({"lifecycle": {"$ne": "dormant"}})
        
        async for narrative in cursor:
            score = 0.0
            
            # Check if entity appears in narrative keywords
            keywords = narrative.get("keywords", [])
            for keyword in keywords:
                if entity_label.lower() in keyword.lower():
                    score += 0.3
                elif entity_slug.lower() in keyword.lower():
                    score += 0.2
            
            # Check topics
            topics = narrative.get("topics", [])
            for topic in topics:
                if entity_id.lower() in topic.lower():
                    score += 0.2
            
            # If entity is a project, check category match
            if entity_type == "project":
                project = await self.db.intel_projects.find_one({"slug": entity_id})
                if project:
                    project_category = project.get("category", "").lower()
                    narrative_name = narrative.get("canonical_name", "").lower()
                    
                    if project_category in narrative_name or narrative_name in project_category:
                        score += 0.3
            
            if score > 0.2:
                matched.append({
                    "narrative_id": narrative.get("id"),
                    "narrative_name": narrative.get("name"),
                    "relevance_score": min(score, 1.0),
                    "is_key_player": score > 0.6
                })
        
        # Sort by relevance
        matched.sort(key=lambda x: x["relevance_score"], reverse=True)
        
        return matched[:10]  # Top 10 matches
    
    async def auto_link_entity(
        self,
        entity_type: str,
        entity_id: str
    ) -> int:
        """
        Automatically link entity to relevant narratives.
        Returns number of links created.
        """
        matches = await self.detect_entity_narrative_relevance(entity_type, entity_id)
        
        links_created = 0
        for match in matches:
            if match["relevance_score"] > 0.3:  # Threshold
                await self.link_entity_to_narrative(
                    narrative_id=match["narrative_id"],
                    entity_type=entity_type,
                    entity_id=entity_id,
                    relevance_score=match["relevance_score"],
                    is_key_player=match["is_key_player"],
                    source="auto_detection"
                )
                links_created += 1
        
        return links_created
    
    async def batch_link_entities(
        self,
        entity_type: str = None,
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        Batch auto-link entities to narratives.
        Called by scheduler job.
        """
        start = datetime.now(timezone.utc)
        
        query = {}
        if entity_type:
            query["entity_type"] = entity_type
        
        cursor = self.graph_nodes.find(query).limit(limit)
        
        results = {
            "processed": 0,
            "links_created": 0,
            "by_type": {}
        }
        
        async for node in cursor:
            etype = node.get("entity_type")
            eid = node.get("entity_id")
            
            links = await self.auto_link_entity(etype, eid)
            
            results["processed"] += 1
            results["links_created"] += links
            
            if etype not in results["by_type"]:
                results["by_type"][etype] = 0
            results["by_type"][etype] += links
        
        elapsed = (datetime.now(timezone.utc) - start).total_seconds()
        results["elapsed_seconds"] = round(elapsed, 2)
        
        logger.info(f"[NarrativeLinker] Batch linked {results['links_created']} entities in {elapsed:.1f}s")
        
        return results
    
    async def _update_entity_exposure(self, entity_key: str):
        """Update aggregated narrative exposure for entity"""
        now = datetime.now(timezone.utc)
        
        # Count narratives and sum relevance
        pipeline = [
            {"$match": {"entity_key": entity_key}},
            {"$group": {
                "_id": "$entity_key",
                "narrative_count": {"$sum": 1},
                "total_relevance": {"$sum": "$relevance_score"},
                "key_player_count": {
                    "$sum": {"$cond": ["$is_key_player", 1, 0]}
                }
            }}
        ]
        
        result = await self.narrative_entities.aggregate(pipeline).to_list(1)
        
        if result:
            stats = result[0]
            exposure = {
                "entity_key": entity_key,
                "narrative_count": stats["narrative_count"],
                "total_relevance": round(stats["total_relevance"], 2),
                "key_player_count": stats["key_player_count"],
                "total_exposure": round(
                    stats["narrative_count"] * 0.5 + 
                    stats["total_relevance"] * 0.3 +
                    stats["key_player_count"] * 0.2,
                    2
                ),
                "updated_at": now
            }
            
            await self.narrative_exposure.update_one(
                {"entity_key": entity_key},
                {"$set": exposure},
                upsert=True
            )
    
    async def _create_narrative_edge(
        self,
        narrative_id: str,
        entity_key: str,
        relevance_score: float
    ):
        """Create intelligence edge for narrative link"""
        now = datetime.now(timezone.utc)
        
        # Find entity node
        parts = entity_key.split(":")
        node = await self.graph_nodes.find_one({
            "entity_type": parts[0],
            "entity_id": parts[1]
        })
        
        if not node:
            return
        
        # Create narrative_linked edge
        edge = {
            "from_node_id": node["id"],
            "to_entity_key": entity_key,
            "relation_type": "narrative_linked",
            "layer": "intelligence",
            "narrative_id": narrative_id,
            "confidence": relevance_score,
            "source": "narrative_linking",
            "created_at": now,
            "updated_at": now
        }
        
        await self.intelligence_edges.update_one(
            {
                "from_node_id": node["id"],
                "narrative_id": narrative_id,
                "relation_type": "narrative_linked"
            },
            {"$set": edge},
            upsert=True
        )
    
    async def get_entity_exposure(
        self,
        entity_type: str,
        entity_id: str
    ) -> Dict[str, Any]:
        """Get narrative exposure metrics for entity"""
        entity_key = f"{entity_type}:{entity_id}"
        
        exposure = await self.narrative_exposure.find_one(
            {"entity_key": entity_key},
            {"_id": 0}
        )
        
        if not exposure:
            return {
                "entity_key": entity_key,
                "narrative_count": 0,
                "total_exposure": 0
            }
        
        return exposure
    
    async def get_top_exposed_entities(
        self,
        entity_type: str = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Get entities with highest narrative exposure"""
        query = {}
        if entity_type:
            query["entity_key"] = {"$regex": f"^{entity_type}:"}
        
        cursor = self.narrative_exposure.find(
            query,
            {"_id": 0}
        ).sort("total_exposure", -1).limit(limit)
        
        return await cursor.to_list(length=limit)
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get linking statistics"""
        total_links = await self.narrative_entities.count_documents({})
        
        # Links by entity type
        pipeline = [
            {"$group": {
                "_id": "$entity_type",
                "count": {"$sum": 1}
            }}
        ]
        
        type_stats = await self.narrative_entities.aggregate(pipeline).to_list(10)
        
        # Key players count
        key_players = await self.narrative_entities.count_documents({"is_key_player": True})
        
        # Narratives with entities
        narratives_with_links = len(
            await self.narrative_entities.distinct("narrative_id")
        )
        
        # Entities with narratives
        entities_with_links = len(
            await self.narrative_entities.distinct("entity_key")
        )
        
        return {
            "total_links": total_links,
            "key_players": key_players,
            "narratives_with_entities": narratives_with_links,
            "entities_with_narratives": entities_with_links,
            "by_entity_type": {
                stat["_id"]: stat["count"]
                for stat in type_stats
            }
        }


# Singleton
_linker: Optional[NarrativeEntityLinker] = None


def get_narrative_entity_linker(db: AsyncIOMotorDatabase = None) -> NarrativeEntityLinker:
    """Get or create linker instance"""
    global _linker
    if db is not None:
        _linker = NarrativeEntityLinker(db)
    return _linker
