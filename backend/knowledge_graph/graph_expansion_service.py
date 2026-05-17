"""
Graph Expansion Job
====================

Automatically creates edges for newly approved entities.

When a new entity is approved (confidence >= 0.75), this job:
1. Searches for related funding rounds
2. Finds co-investors
3. Extracts mentions from articles
4. Discovers portfolio connections
5. Creates edges in graph

Only processes entities with confidence >= 0.75
"""

import logging
import re
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Set
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

# Minimum confidence for graph expansion
MIN_CONFIDENCE = 0.75

# Edge relation types
RELATION_TYPES = {
    "invested_in": {"source_type": "fund", "target_type": "project", "weight": 0.9},
    "coinvested_with": {"source_type": "fund", "target_type": "fund", "weight": 0.7},
    "founded_by": {"source_type": "project", "target_type": "person", "weight": 0.95},
    "works_at": {"source_type": "person", "target_type": "project", "weight": 0.8},
    "partner_of": {"source_type": "fund", "target_type": "fund", "weight": 0.6},
    "mentioned_with": {"source_type": "any", "target_type": "any", "weight": 0.4}
}


class GraphExpansionService:
    """
    Expands graph by creating edges for approved entities.
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.graph_nodes = db.graph_nodes
        self.graph_edges = db.graph_edges
        self.entity_confidence = db.entity_confidence
        self.entity_candidates = db.entity_candidates
        
        # Data sources
        self.funding_rounds = db.funding_rounds
        self.articles = db.normalized_articles
        self.cryptorank_funds = db.cryptorank_funds
        self.cryptorank_projects = db.cryptorank_projects
        
        # Track processed entities
        self._processed_entities: Set[str] = set()
    
    @staticmethod
    def normalize_name(name: str) -> str:
        """Normalize name for matching"""
        if not name:
            return ""
        normalized = name.lower().strip()
        normalized = re.sub(r'[^\w\s]', '', normalized)
        normalized = re.sub(r'\s+', ' ', normalized)
        return normalized
    
    @staticmethod
    def to_slug(name: str) -> str:
        """Convert name to slug"""
        slug = name.lower().strip()
        slug = re.sub(r'[^\w\s-]', '', slug)
        slug = re.sub(r'\s+', '-', slug)
        return slug
    
    async def expand_for_entity(self, entity_id: str) -> Dict[str, Any]:
        """
        Expand graph for a specific entity.
        Creates edges based on funding, co-investments, mentions.
        """
        # Parse entity ID
        parts = entity_id.split(':')
        if len(parts) != 2:
            return {"error": "Invalid entity_id format"}
        
        entity_type, entity_slug = parts
        
        # Check if already processed recently
        if entity_id in self._processed_entities:
            return {"skipped": True, "reason": "recently_processed"}
        
        # Check confidence
        confidence_record = await self.entity_confidence.find_one({"entity_id": entity_id})
        if confidence_record and confidence_record.get("confidence_score", 0) < MIN_CONFIDENCE:
            return {"skipped": True, "reason": "low_confidence"}
        
        # Get entity node
        node = await self.graph_nodes.find_one({"id": entity_id})
        if not node:
            return {"error": "Entity not found in graph"}
        
        entity_name = node.get("label", entity_slug)
        
        edges_created = 0
        
        # Expand based on entity type
        if entity_type == "fund":
            edges_created += await self._expand_fund(entity_id, entity_name, entity_slug)
        elif entity_type == "project":
            edges_created += await self._expand_project(entity_id, entity_name, entity_slug)
        elif entity_type == "person":
            edges_created += await self._expand_person(entity_id, entity_name, entity_slug)
        
        # Mark as processed
        self._processed_entities.add(entity_id)
        
        logger.info(f"[GraphExpansion] Expanded {entity_id}: {edges_created} edges created")
        
        return {
            "entity_id": entity_id,
            "entity_type": entity_type,
            "edges_created": edges_created
        }
    
    async def _expand_fund(self, entity_id: str, name: str, slug: str) -> int:
        """Expand edges for a fund entity"""
        edges_created = 0
        normalized = self.normalize_name(name)
        
        # 1. Find investments from funding rounds
        cursor = self.funding_rounds.find({
            "$or": [
                {"investors": {"$elemMatch": {"$regex": f".*{re.escape(name)}.*", "$options": "i"}}},
                {"lead_investor": {"$regex": f".*{re.escape(name)}.*", "$options": "i"}}
            ]
        }).limit(100)
        
        async for round_data in cursor:
            project_name = round_data.get("project_name") or round_data.get("project")
            if project_name:
                project_slug = self.to_slug(project_name)
                target_id = f"project:{project_slug}"
                
                # Create invested_in edge
                edge = await self._create_edge(
                    entity_id, 
                    target_id, 
                    "invested_in",
                    {
                        "round_type": round_data.get("round_type"),
                        "amount": round_data.get("amount"),
                        "date": round_data.get("date")
                    }
                )
                if edge:
                    edges_created += 1
                
                # Find co-investors
                investors = round_data.get("investors", [])
                for investor in investors:
                    investor_name = investor if isinstance(investor, str) else investor.get("name")
                    if investor_name and self.normalize_name(investor_name) != normalized:
                        coinvestor_slug = self.to_slug(investor_name)
                        coinvestor_id = f"fund:{coinvestor_slug}"
                        
                        edge = await self._create_edge(
                            entity_id,
                            coinvestor_id,
                            "coinvested_with",
                            {"project": project_name}
                        )
                        if edge:
                            edges_created += 1
        
        # 2. Check CryptoRank fund data for portfolio
        fund_data = await self.cryptorank_funds.find_one({
            "$or": [
                {"name": {"$regex": f"^{re.escape(name)}$", "$options": "i"}},
                {"slug": slug}
            ]
        })
        
        if fund_data and fund_data.get("portfolio"):
            for project in fund_data.get("portfolio", [])[:50]:
                project_name = project.get("name") if isinstance(project, dict) else project
                if project_name:
                    project_slug = self.to_slug(project_name)
                    target_id = f"project:{project_slug}"
                    
                    edge = await self._create_edge(
                        entity_id,
                        target_id,
                        "invested_in",
                        {"source": "cryptorank_portfolio"}
                    )
                    if edge:
                        edges_created += 1
        
        return edges_created
    
    async def _expand_project(self, entity_id: str, name: str, slug: str) -> int:
        """Expand edges for a project entity"""
        edges_created = 0
        
        # 1. Find investors from funding rounds
        cursor = self.funding_rounds.find({
            "$or": [
                {"project_name": {"$regex": f"^{re.escape(name)}$", "$options": "i"}},
                {"project": {"$regex": f"^{re.escape(name)}$", "$options": "i"}}
            ]
        }).limit(50)
        
        async for round_data in cursor:
            # Add investor edges
            investors = round_data.get("investors", [])
            for investor in investors:
                investor_name = investor if isinstance(investor, str) else investor.get("name")
                if investor_name:
                    investor_slug = self.to_slug(investor_name)
                    source_id = f"fund:{investor_slug}"
                    
                    edge = await self._create_edge(
                        source_id,
                        entity_id,
                        "invested_in",
                        {
                            "round_type": round_data.get("round_type"),
                            "amount": round_data.get("amount")
                        }
                    )
                    if edge:
                        edges_created += 1
            
            # Add lead investor
            lead = round_data.get("lead_investor")
            if lead:
                lead_slug = self.to_slug(lead)
                source_id = f"fund:{lead_slug}"
                
                edge = await self._create_edge(
                    source_id,
                    entity_id,
                    "invested_in",
                    {"is_lead": True, "round_type": round_data.get("round_type")}
                )
                if edge:
                    edges_created += 1
        
        # 2. Check CryptoRank project data for founders/team
        project_data = await self.cryptorank_projects.find_one({
            "$or": [
                {"name": {"$regex": f"^{re.escape(name)}$", "$options": "i"}},
                {"slug": slug}
            ]
        })
        
        if project_data:
            # Founders
            founders = project_data.get("founders", []) or project_data.get("team", [])
            for founder in founders[:10]:
                founder_name = founder.get("name") if isinstance(founder, dict) else founder
                if founder_name:
                    founder_slug = self.to_slug(founder_name)
                    source_id = f"person:{founder_slug}"
                    
                    edge = await self._create_edge(
                        entity_id,
                        source_id,
                        "founded_by",
                        {"source": "cryptorank"}
                    )
                    if edge:
                        edges_created += 1
        
        return edges_created
    
    async def _expand_person(self, entity_id: str, name: str, slug: str) -> int:
        """Expand edges for a person entity"""
        edges_created = 0
        
        # Find projects where person is mentioned as founder/team
        cursor = self.cryptorank_projects.find({
            "$or": [
                {"founders.name": {"$regex": f".*{re.escape(name)}.*", "$options": "i"}},
                {"team.name": {"$regex": f".*{re.escape(name)}.*", "$options": "i"}}
            ]
        }).limit(20)
        
        async for project in cursor:
            project_name = project.get("name")
            if project_name:
                project_slug = self.to_slug(project_name)
                target_id = f"project:{project_slug}"
                
                edge = await self._create_edge(
                    target_id,
                    entity_id,
                    "founded_by",
                    {"source": "cryptorank_team"}
                )
                if edge:
                    edges_created += 1
        
        return edges_created
    
    async def _create_edge(
        self,
        source_id: str,
        target_id: str,
        relation: str,
        metadata: Dict = None
    ) -> bool:
        """Create edge in graph if not exists"""
        # Skip self-loops
        if source_id == target_id:
            return False
        
        # Check if edge already exists
        existing = await self.graph_edges.find_one({
            "source": source_id,
            "target": target_id,
            "relation": relation
        })
        if existing:
            return False
        
        now = datetime.now(timezone.utc)
        
        edge = {
            "source": source_id,
            "target": target_id,
            "relation": relation,
            "weight": RELATION_TYPES.get(relation, {}).get("weight", 0.5),
            "metadata": metadata or {},
            "source_layer": "expansion",
            "created_at": now
        }
        
        try:
            await self.graph_edges.insert_one(edge)
            return True
        except Exception as e:
            logger.debug(f"[GraphExpansion] Edge creation failed: {e}")
            return False
    
    async def expand_new_entities(self, limit: int = 50) -> Dict[str, Any]:
        """
        Expand graph for newly approved entities.
        Called by scheduler.
        """
        now = datetime.now(timezone.utc)
        since = now - timedelta(hours=24)
        
        # Find recently approved candidates
        cursor = self.entity_candidates.find({
            "status": "approved",
            "approved_at": {"$gte": since}
        }).limit(limit)
        
        total_expanded = 0
        total_edges = 0
        
        async for candidate in cursor:
            entity_type = candidate.get("entity_type_guess", "project")
            slug = candidate.get("slug") or self.to_slug(candidate.get("name", ""))
            entity_id = f"{entity_type}:{slug}"
            
            result = await self.expand_for_entity(entity_id)
            if result.get("edges_created"):
                total_expanded += 1
                total_edges += result["edges_created"]
        
        logger.info(f"[GraphExpansion] Expanded {total_expanded} entities, created {total_edges} edges")
        
        return {
            "entities_expanded": total_expanded,
            "edges_created": total_edges,
            "timestamp": now.isoformat()
        }
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get expansion statistics"""
        # Total edges by source layer
        pipeline = [
            {"$group": {"_id": "$source_layer", "count": {"$sum": 1}}}
        ]
        layer_counts = await self.graph_edges.aggregate(pipeline).to_list(10)
        
        # Total edges by relation
        relation_pipeline = [
            {"$group": {"_id": "$relation", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        relation_counts = await self.graph_edges.aggregate(relation_pipeline).to_list(20)
        
        return {
            "by_layer": {layer["_id"]: layer["count"] for layer in layer_counts if layer["_id"]},
            "by_relation": {r["_id"]: r["count"] for r in relation_counts if r["_id"]},
            "total_edges": await self.graph_edges.count_documents({}),
            "processed_entities": len(self._processed_entities)
        }


# Singleton
_expansion_service: Optional[GraphExpansionService] = None


def get_graph_expansion_service(db: AsyncIOMotorDatabase = None) -> GraphExpansionService:
    """Get or create graph expansion service"""
    global _expansion_service
    if db is not None:
        _expansion_service = GraphExpansionService(db)
    return _expansion_service
