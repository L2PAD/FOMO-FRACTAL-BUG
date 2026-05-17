"""
Graph Builder - Builds graph from normalized data

Responsibilities:
- Build direct edges from source collections
- Build derived edges (coinvested_with, worked_together, etc.)
- Manage edge upserts and deduplication
"""

import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
from motor.motor_asyncio import AsyncIOMotorDatabase

from .models import GraphEdge, GraphSnapshot, EDGE_TYPES
from .resolver import GraphResolver

logger = logging.getLogger(__name__)


class GraphBuilder:
    """
    Builds graph nodes and edges from normalized data.
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.resolver = GraphResolver(db)
        self.edges_collection = db.graph_edges
        self.edge_types_collection = db.graph_edge_types
        self.snapshots_collection = db.graph_snapshots
    
    async def ensure_indexes(self):
        """Create required indexes for graph collections"""
        # Resolver indexes
        await self.resolver.ensure_indexes()
        
        # Edge indexes
        await self.edges_collection.create_index("from_node_id", name="idx_from_node")
        await self.edges_collection.create_index("to_node_id", name="idx_to_node")
        await self.edges_collection.create_index("relation_type", name="idx_relation")
        await self.edges_collection.create_index(
            [("from_node_id", 1), ("relation_type", 1)],
            name="idx_from_relation"
        )
        await self.edges_collection.create_index(
            [("to_node_id", 1), ("relation_type", 1)],
            name="idx_to_relation"
        )
        await self.edges_collection.create_index("source_type", name="idx_source_type")
        await self.edges_collection.create_index("source_ref", name="idx_source_ref")
        await self.edges_collection.create_index(
            [("from_node_id", 1), ("to_node_id", 1), ("relation_type", 1)],
            unique=False,  # Allow multiple edges with different source_ref
            name="idx_edge_lookup"
        )
        
        # Edge types indexes
        await self.edge_types_collection.create_index(
            [("relation_type", 1), ("from_entity_type", 1), ("to_entity_type", 1)],
            unique=True,
            name="unique_edge_type"
        )
        
        logger.info("[GraphBuilder] Indexes created for graph collections")
    
    async def init_edge_types(self):
        """Initialize edge types dictionary from EDGE_TYPES"""
        for relation_type, config in EDGE_TYPES.items():
            try:
                await self.edge_types_collection.update_one(
                    {"relation_type": relation_type},
                    {"$set": {
                        "relation_type": relation_type,
                        "from_entity_type": config["from"],
                        "to_entity_type": config["to"],
                        "directed": config["directed"],
                        "derived": config["derived"],
                        "updated_at": datetime.now(timezone.utc)
                    }},
                    upsert=True
                )
            except Exception as e:
                logger.warning(f"[GraphBuilder] Failed to init edge type {relation_type}: {e}")
        
        logger.info(f"[GraphBuilder] Initialized {len(EDGE_TYPES)} edge types")
    
    async def add_edge(
        self,
        from_node_id: str,
        to_node_id: str,
        relation_type: str,
        weight: float = 1.0,
        source_type: str = "direct",
        source_ref: Optional[str] = None,
        confidence: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
        directionality: str = "directed"
    ) -> str:
        """
        Add or update an edge.
        Uses upsert based on (from_node_id, to_node_id, relation_type, source_ref).
        """
        now = datetime.now(timezone.utc)
        
        # Find existing edge
        filter_dict = {
            "from_node_id": from_node_id,
            "to_node_id": to_node_id,
            "relation_type": relation_type
        }
        if source_ref:
            filter_dict["source_ref"] = source_ref
        
        existing = await self.edges_collection.find_one(filter_dict)
        
        if existing:
            # Update existing edge
            update_data = {
                "weight": weight,
                "updated_at": now
            }
            if metadata:
                update_data["metadata"] = {**existing.get("metadata", {}), **metadata}
            if confidence is not None:
                update_data["confidence"] = confidence
            
            await self.edges_collection.update_one(
                {"id": existing["id"]},
                {"$set": update_data}
            )
            return existing["id"]
        
        # Create new edge
        edge = GraphEdge(
            from_node_id=from_node_id,
            to_node_id=to_node_id,
            relation_type=relation_type,
            weight=weight,
            directionality=directionality,
            source_type=source_type,
            source_ref=source_ref,
            confidence=confidence,
            metadata=metadata or {}
        )
        
        await self.edges_collection.insert_one(edge.model_dump())
        logger.debug(f"[GraphBuilder] Created edge: {from_node_id} --[{relation_type}]--> {to_node_id}")
        return edge.id
    
    async def add_edge_by_entity(
        self,
        from_type: str,
        from_id: str,
        from_label: str,
        to_type: str,
        to_id: str,
        to_label: str,
        relation_type: str,
        **kwargs
    ) -> Tuple[str, str, str]:
        """
        Add edge by resolving entities first.
        Returns (from_node_id, to_node_id, edge_id).
        """
        # Resolve nodes
        from_node_id = await self.resolver.resolve(
            entity_type=from_type,
            entity_id=from_id,
            label=from_label
        )
        to_node_id = await self.resolver.resolve(
            entity_type=to_type,
            entity_id=to_id,
            label=to_label
        )
        
        # Add edge
        edge_id = await self.add_edge(
            from_node_id=from_node_id,
            to_node_id=to_node_id,
            relation_type=relation_type,
            **kwargs
        )
        
        return from_node_id, to_node_id, edge_id
    
    # =========================================================================
    # Build from source collections
    # =========================================================================
    
    async def build_projects_graph(self) -> int:
        """Build graph nodes and edges from projects collection"""
        count = 0
        cursor = self.db.intel_projects.find({})
        
        async for project in cursor:
            try:
                # Create project node
                project_id = project.get("slug") or project.get("key", "").split(":")[-1]
                await self.resolver.resolve(
                    entity_type="project",
                    entity_id=project_id,
                    label=project.get("name", project_id),
                    slug=project.get("slug"),
                    metadata={
                        "category": project.get("category"),
                        "symbol": project.get("symbol"),
                        "source": project.get("source")
                    }
                )
                count += 1
                
                # If project has token symbol, create token node and edge
                if project.get("symbol"):
                    token_id = project["symbol"].lower()
                    await self.add_edge_by_entity(
                        from_type="project",
                        from_id=project_id,
                        from_label=project.get("name", project_id),
                        to_type="token",
                        to_id=token_id,
                        to_label=project["symbol"],
                        relation_type="has_token",
                        source_type="direct",
                        source_ref=f"project:{project_id}",
                        metadata={"symbol": project["symbol"]}
                    )
                    count += 1
                    
            except Exception as e:
                logger.error(f"[GraphBuilder] Failed to process project {project}: {e}")
        
        logger.info(f"[GraphBuilder] Built {count} nodes/edges from projects")
        return count
    
    async def build_exchanges_graph(self) -> int:
        """Build graph nodes for exchanges"""
        count = 0
        
        # Default exchanges to bootstrap
        exchanges = [
            {"id": "binance", "name": "Binance", "type": "cex"},
            {"id": "coinbase", "name": "Coinbase", "type": "cex"},
            {"id": "kraken", "name": "Kraken", "type": "cex"},
            {"id": "okx", "name": "OKX", "type": "cex"},
            {"id": "bybit", "name": "Bybit", "type": "cex"},
            {"id": "gate", "name": "Gate.io", "type": "cex"},
            {"id": "kucoin", "name": "KuCoin", "type": "cex"},
            {"id": "htx", "name": "HTX", "type": "cex"},
            {"id": "uniswap", "name": "Uniswap", "type": "dex"},
            {"id": "sushiswap", "name": "SushiSwap", "type": "dex"},
        ]
        
        for exchange in exchanges:
            await self.resolver.resolve(
                entity_type="exchange",
                entity_id=exchange["id"],
                label=exchange["name"],
                slug=exchange["id"],
                metadata={"exchange_type": exchange["type"]}
            )
            count += 1
        
        # Also check exchanges collection if exists
        try:
            cursor = self.db.exchanges.find({})
            async for ex in cursor:
                await self.resolver.resolve(
                    entity_type="exchange",
                    entity_id=ex.get("slug") or ex.get("id"),
                    label=ex.get("name"),
                    slug=ex.get("slug"),
                    metadata=ex.get("metadata", {})
                )
                count += 1
        except Exception:
            pass
        
        logger.info(f"[GraphBuilder] Built {count} exchange nodes")
        return count
    
    async def build_traded_on_edges(self) -> int:
        """Build traded_on edges from asset market symbols"""
        count = 0
        
        # Check asset_market_symbols collection
        try:
            cursor = self.db.asset_market_symbols.find({})
            async for symbol in cursor:
                asset_id = symbol.get("asset_id") or symbol.get("base_asset")
                exchange_id = symbol.get("exchange_id") or symbol.get("exchange")
                
                if asset_id and exchange_id:
                    # Get or create asset node
                    asset_label = symbol.get("base_asset_name") or asset_id.upper()
                    
                    await self.add_edge_by_entity(
                        from_type="asset",
                        from_id=asset_id,
                        from_label=asset_label,
                        to_type="exchange",
                        to_id=exchange_id,
                        to_label=exchange_id.title(),
                        relation_type="traded_on",
                        source_type="direct",
                        source_ref=f"market:{symbol.get('symbol', asset_id)}",
                        metadata={
                            "symbol": symbol.get("symbol"),
                            "market_type": symbol.get("market_type", "spot")
                        }
                    )
                    count += 1
        except Exception as e:
            logger.warning(f"[GraphBuilder] No asset_market_symbols: {e}")
        
        logger.info(f"[GraphBuilder] Built {count} traded_on edges")
        return count
    
    async def build_real_investments_network(self) -> int:
        """
        Build REAL investment network from actual VC portfolio data.
        Uses verified investment data from public sources.
        """
        count = 0
        
        try:
            from .real_investments import (
                ALL_INVESTMENTS_EXTENDED as ALL_INVESTMENTS, 
                PROJECT_TEAM_MEMBERS, 
                FUND_TEAM_MEMBERS_EXTENDED as FUND_TEAM_MEMBERS
            )
        except ImportError:
            logger.warning("[GraphBuilder] Real investments data not found, using sample")
            return await self._build_sample_network_fallback()
        
        # Create fund nodes with metadata
        fund_names = {
            "a16z": "a16z Crypto",
            "paradigm": "Paradigm",
            "coinbase-ventures": "Coinbase Ventures",
            "binance-labs": "Binance Labs",
            "polychain": "Polychain Capital",
            "pantera": "Pantera Capital",
            "dragonfly": "Dragonfly Capital",
            "multicoin": "Multicoin Capital",
            # Tier 2 & 3 funds
            "sequoia": "Sequoia Capital",
            "galaxy": "Galaxy Digital",
            "jump-crypto": "Jump Crypto",
            "framework": "Framework Ventures",
            "hack-vc": "Hack VC",
            "animoca": "Animoca Brands",
            "spartan": "Spartan Group",
            "delphi": "Delphi Ventures",
            "dcg": "Digital Currency Group",
            "placeholder": "Placeholder VC",
            "robot-ventures": "Robot Ventures",
        }
        
        for fund_slug, fund_name in fund_names.items():
            await self.resolver.resolve(
                entity_type="fund",
                entity_id=fund_slug,
                label=fund_name,
                slug=fund_slug,
                metadata={"type": "vc", "tier": 1}
            )
            count += 1
        
        # Build investment edges from REAL data
        # Each investment round creates a separate edge (multiple lines = multiple rounds)
        for fund_slug, investments in ALL_INVESTMENTS.items():
            fund_name = fund_names.get(fund_slug, fund_slug)
            
            for inv in investments:
                project_id = inv["project"]
                project_name = inv["name"]
                amount = inv["amount"]
                round_type = inv.get("round", "Private")
                year = inv.get("year", 2023)
                
                # Create project node if not exists
                await self.resolver.resolve(
                    entity_type="project",
                    entity_id=project_id,
                    label=project_name,
                    slug=project_id
                )
                
                # Create investment edge with UNIQUE source_ref per round
                # This allows multiple edges for multiple investments
                source_ref = f"investment:{fund_slug}_{project_id}_{round_type}_{year}"
                
                await self.add_edge_by_entity(
                    from_type="fund",
                    from_id=fund_slug,
                    from_label=fund_name,
                    to_type="project",
                    to_id=project_id,
                    to_label=project_name,
                    relation_type="invested_in",
                    weight=min(1.0, (amount / 100000000) if amount > 0 else 0.5),
                    source_type="direct",
                    source_ref=source_ref,
                    metadata={
                        "amount_usd": amount,
                        "round": round_type,
                        "year": year
                    }
                )
                count += 1
        
        # Build fund team members (partners -> fund)
        for fund_slug, members in FUND_TEAM_MEMBERS.items():
            fund_name = fund_names.get(fund_slug, fund_slug)
            
            for member in members:
                person_id = member["id"]
                person_name = member["name"]
                role = member.get("role", "Partner")
                
                # Create person node
                await self.resolver.resolve(
                    entity_type="person",
                    entity_id=person_id,
                    label=person_name,
                    slug=person_id,
                    metadata={"role": role}
                )
                count += 1
                
                # Create works_at edge
                await self.add_edge_by_entity(
                    from_type="person",
                    from_id=person_id,
                    from_label=person_name,
                    to_type="fund",
                    to_id=fund_slug,
                    to_label=fund_name,
                    relation_type="works_at",
                    source_type="direct",
                    source_ref=f"team:{person_id}_{fund_slug}",
                    metadata={"role": role}
                )
                count += 1
        
        # Build project team members (founders/team -> project)
        for project_id, members in PROJECT_TEAM_MEMBERS.items():
            # Get project name from existing node or use ID
            project_node = await self.resolver.get_node_by_key("project", project_id)
            project_name = project_node.get("label", project_id.title()) if project_node else project_id.title()
            
            for member in members:
                person_id = member["id"]
                person_name = member["name"]
                role = member.get("role", "Team Member")
                
                # Determine relation type based on role
                relation_type = "founded" if "founder" in role.lower() else "works_at"
                
                # Create person node
                await self.resolver.resolve(
                    entity_type="person",
                    entity_id=person_id,
                    label=person_name,
                    slug=person_id,
                    metadata={"role": role}
                )
                count += 1
                
                # Create relation edge
                await self.add_edge_by_entity(
                    from_type="person",
                    from_id=person_id,
                    from_label=person_name,
                    to_type="project",
                    to_id=project_id,
                    to_label=project_name,
                    relation_type=relation_type,
                    source_type="direct",
                    source_ref=f"team:{person_id}_{project_id}",
                    metadata={"role": role}
                )
                count += 1
        
        # Build token mappings for major projects
        token_mappings = [
            ("arbitrum", "arb", "ARB"),
            ("optimism", "op", "OP"),
            ("polygon", "matic", "MATIC"),
            ("uniswap", "uni", "UNI"),
            ("ethereum", "eth", "ETH"),
            ("solana", "sol", "SOL"),
            ("cosmos", "atom", "ATOM"),
            ("aptos", "apt", "APT"),
            ("sui", "sui", "SUI"),
            ("near", "near", "NEAR"),
            ("avalanche", "avax", "AVAX"),
            ("lido", "ldo", "LDO"),
            ("aave", "aave", "AAVE"),
            ("compound", "comp", "COMP"),
            ("dydx", "dydx", "DYDX"),
            ("chainlink", "link", "LINK"),
            ("polkadot", "dot", "DOT"),
            ("filecoin", "fil", "FIL"),
            ("render", "rndr", "RNDR"),
            ("injective", "inj", "INJ"),
            ("worldcoin", "wld", "WLD"),
            ("eigenlayer", "eigen", "EIGEN"),
            ("layerzero", "zro", "ZRO"),
        ]
        
        for project_id, token_id, symbol in token_mappings:
            # Project -> token (has_token)
            project_node = await self.resolver.get_node_by_key("project", project_id)
            if project_node:
                await self.add_edge_by_entity(
                    from_type="project",
                    from_id=project_id,
                    from_label=project_node.get("label", project_id.title()),
                    to_type="token",
                    to_id=token_id,
                    to_label=symbol,
                    relation_type="has_token",
                    source_type="direct",
                    source_ref=f"token:{project_id}_{token_id}"
                )
                count += 1
            
            # Token -> asset mapping
            await self.add_edge_by_entity(
                from_type="token",
                from_id=token_id,
                from_label=symbol,
                to_type="asset",
                to_id=token_id,
                to_label=symbol,
                relation_type="mapped_to_asset",
                source_type="direct",
                source_ref=f"token_asset:{token_id}"
            )
            count += 1
            
            # Asset -> exchanges (traded_on) - major exchanges
            for exchange_id in ["binance", "coinbase", "kraken"]:
                await self.add_edge_by_entity(
                    from_type="asset",
                    from_id=token_id,
                    from_label=symbol,
                    to_type="exchange",
                    to_id=exchange_id,
                    to_label=exchange_id.title(),
                    relation_type="traded_on",
                    source_type="direct",
                    source_ref=f"listing:{token_id}_{exchange_id}",
                    metadata={"symbol": f"{symbol}/USDT"}
                )
                count += 1
        
        logger.info(f"[GraphBuilder] Built {count} REAL investment network nodes/edges")
        return count
    
    async def _build_sample_network_fallback(self) -> int:
        """Fallback sample network if real data not available."""
        count = 0
        # Minimal sample data
        logger.info("[GraphBuilder] Using minimal fallback data")
        return count
    
    # =========================================================================
    # Derived edges
    # =========================================================================
    
    async def build_coinvested_edges(self) -> int:
        """
        Build coinvested_with edges between funds that invested in same projects.
        """
        count = 0
        
        # Get all invested_in edges grouped by project
        pipeline = [
            {"$match": {"relation_type": "invested_in"}},
            {"$group": {
                "_id": "$to_node_id",  # project node
                "investors": {"$addToSet": "$from_node_id"}
            }},
            {"$match": {"investors.1": {"$exists": True}}}  # At least 2 investors
        ]
        
        async for group in self.edges_collection.aggregate(pipeline):
            investors = group["investors"]
            project_node_id = group["_id"]
            
            # Create pairwise coinvested_with edges
            for i in range(len(investors)):
                for j in range(i + 1, len(investors)):
                    # Check if edge already exists or create/update
                    existing = await self.edges_collection.find_one({
                        "$or": [
                            {"from_node_id": investors[i], "to_node_id": investors[j], "relation_type": "coinvested_with"},
                            {"from_node_id": investors[j], "to_node_id": investors[i], "relation_type": "coinvested_with"}
                        ]
                    })
                    
                    if existing:
                        # Update metadata with new shared project
                        shared_projects = existing.get("metadata", {}).get("shared_projects", [])
                        if project_node_id not in shared_projects:
                            shared_projects.append(project_node_id)
                            await self.edges_collection.update_one(
                                {"id": existing["id"]},
                                {"$set": {
                                    "metadata.shared_projects": shared_projects,
                                    "metadata.shared_count": len(shared_projects),
                                    "weight": min(1.0, len(shared_projects) * 0.2),
                                    "updated_at": datetime.now(timezone.utc)
                                }}
                            )
                    else:
                        # Create new coinvested edge
                        await self.add_edge(
                            from_node_id=investors[i],
                            to_node_id=investors[j],
                            relation_type="coinvested_with",
                            directionality="undirected",
                            source_type="derived",
                            weight=0.2,
                            metadata={
                                "shared_projects": [project_node_id],
                                "shared_count": 1
                            }
                        )
                        count += 1
        
        logger.info(f"[GraphBuilder] Built {count} coinvested_with edges")
        return count
    
    # =========================================================================
    # Full rebuild
    # =========================================================================
    
    async def full_rebuild(self) -> GraphSnapshot:
        """
        Full graph rebuild from all source collections.
        """
        logger.info("[GraphBuilder] Starting full graph rebuild...")
        
        # Ensure indexes
        await self.ensure_indexes()
        await self.init_edge_types()
        
        # Clear cache
        self.resolver.clear_cache()
        
        total_count = 0
        
        # Build nodes and direct edges
        total_count += await self.build_exchanges_graph()
        total_count += await self.build_projects_graph()
        total_count += await self.build_traded_on_edges()
        total_count += await self.build_real_investments_network()
        
        # Build derived edges
        total_count += await self.build_coinvested_edges()
        
        # Get final counts
        node_count = await self.db.graph_nodes.count_documents({})
        edge_count = await self.db.graph_edges.count_documents({})
        
        # Create snapshot record
        snapshot = GraphSnapshot(
            snapshot_type="full_rebuild",
            node_count=node_count,
            edge_count=edge_count,
            metadata={
                "total_operations": total_count,
                "rebuild_time": datetime.now(timezone.utc).isoformat()
            }
        )
        
        await self.snapshots_collection.insert_one(snapshot.model_dump())
        
        logger.info(f"[GraphBuilder] Full rebuild complete: {node_count} nodes, {edge_count} edges")
        return snapshot
