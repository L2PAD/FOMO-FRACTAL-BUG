"""
Seed Entity Graph from Discovery Data (real_investments.py)
============================================================
Creates:
  1. graph_nodes for funds, projects, persons
  2. graph_relations for invested_in, founded_by, works_at, coinvested_with

Schema-compatible with query_service.py BFS (source_id/target_id/relation_type)
"""
import asyncio
import os
from datetime import datetime, timezone
from collections import defaultdict
from motor.motor_asyncio import AsyncIOMotorClient

# Import real investment data
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from knowledge_graph.real_investments import (
    ALL_INVESTMENTS_EXTENDED, 
    PROJECT_TEAM_MEMBERS, 
    FUND_TEAM_MEMBERS_EXTENDED
)

MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME", "intelligence_engine")


async def seed_discovery_graph():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    now = datetime.now(timezone.utc)
    
    nodes_created = 0
    edges_created = 0
    
    # Track all entities for coinvestment edges
    project_investors = defaultdict(list)  # project_slug -> [fund_slug, ...]
    
    # =====================================================
    # 1. Create FUND nodes
    # =====================================================
    fund_labels = {
        "a16z": "a16z Crypto",
        "paradigm": "Paradigm",
        "coinbase-ventures": "Coinbase Ventures",
        "binance-labs": "Binance Labs",
        "polychain": "Polychain Capital",
        "pantera": "Pantera Capital",
        "dragonfly": "Dragonfly",
        "multicoin": "Multicoin Capital",
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
    
    for fund_slug, label in fund_labels.items():
        fund_id = f"fund:{fund_slug}"
        await db.graph_nodes.update_one(
            {"id": fund_id},
            {"$set": {
                "id": fund_id,
                "type": "fund",
                "entity": fund_slug,
                "cluster_id": fund_slug,
                "label": label,
                "metadata": {"source": "discovery", "category": "VC"},
                "created_at": now
            }},
            upsert=True
        )
        nodes_created += 1
    
    # =====================================================
    # 2. Create PROJECT nodes + invested_in edges
    # =====================================================
    seen_projects = set()
    
    for fund_slug, investments in ALL_INVESTMENTS_EXTENDED.items():
        fund_id = f"fund:{fund_slug}"
        
        for inv in investments:
            project_slug = inv["project"]
            project_name = inv["name"]
            project_id = f"project:{project_slug}"
            
            # Track for coinvestment
            project_investors[project_slug].append(fund_slug)
            
            # Create project node (once)
            if project_slug not in seen_projects:
                seen_projects.add(project_slug)
                await db.graph_nodes.update_one(
                    {"id": project_id},
                    {"$set": {
                        "id": project_id,
                        "type": "project",
                        "entity": project_slug,
                        "cluster_id": project_slug,
                        "label": project_name,
                        "metadata": {"source": "discovery"},
                        "created_at": now
                    }},
                    upsert=True
                )
                nodes_created += 1
            
            # Create invested_in edge: fund -> project
            amount = inv.get("amount", 0)
            round_type = inv.get("round", "Unknown")
            year = inv.get("year", 0)
            
            edge_id = f"{fund_id}|{project_id}|invested_in"
            await db.graph_relations.update_one(
                {"source_id": fund_id, "target_id": project_id, "relation_type": "invested_in"},
                {"$set": {
                    "source_id": fund_id,
                    "target_id": project_id,
                    "relation_type": "invested_in",
                    "direction": "out",
                    "weight": min(10, 1 + (amount / 50_000_000)) if amount else 1,
                    "metadata": {
                        "amount_usd": amount,
                        "round": round_type,
                        "year": year,
                        "source": "discovery"
                    },
                    "tags": ["investment", "discovery"],
                    "first_seen": int(now.timestamp()),
                    "last_seen": int(now.timestamp()),
                }},
                upsert=True
            )
            edges_created += 1
    
    # =====================================================
    # 3. Create PERSON nodes + founder/works_at edges
    # =====================================================
    
    # Project founders
    for project_slug, team in PROJECT_TEAM_MEMBERS.items():
        project_id = f"project:{project_slug}"
        
        for member in team:
            person_id = f"person:{member['id']}"
            person_name = member["name"]
            role = member.get("role", "Team")
            
            # Create person node
            await db.graph_nodes.update_one(
                {"id": person_id},
                {"$set": {
                    "id": person_id,
                    "type": "person",
                    "entity": member["id"],
                    "cluster_id": member["id"],
                    "label": person_name,
                    "metadata": {"source": "discovery", "primary_role": role},
                    "created_at": now
                }},
                upsert=True
            )
            nodes_created += 1
            
            # Determine relation type based on role
            rel_type = "founded" if "founder" in role.lower() else "works_at"
            
            # Create founder/team edge: person -> project
            await db.graph_relations.update_one(
                {"source_id": person_id, "target_id": project_id, "relation_type": rel_type},
                {"$set": {
                    "source_id": person_id,
                    "target_id": project_id,
                    "relation_type": rel_type,
                    "direction": "out",
                    "weight": 5 if "founder" in role.lower() else 3,
                    "metadata": {"role": role, "source": "discovery"},
                    "tags": ["team", "discovery"],
                    "first_seen": int(now.timestamp()),
                    "last_seen": int(now.timestamp()),
                }},
                upsert=True
            )
            edges_created += 1
    
    # Fund team members
    for fund_slug, team in FUND_TEAM_MEMBERS_EXTENDED.items():
        fund_id = f"fund:{fund_slug}"
        
        for member in team:
            person_id = f"person:{member['id']}"
            person_name = member["name"]
            role = member.get("role", "Team")
            
            # Create person node
            await db.graph_nodes.update_one(
                {"id": person_id},
                {"$set": {
                    "id": person_id,
                    "type": "person",
                    "entity": member["id"],
                    "cluster_id": member["id"],
                    "label": person_name,
                    "metadata": {"source": "discovery", "primary_role": role},
                    "created_at": now
                }},
                upsert=True
            )
            nodes_created += 1
            
            # Create works_at edge: person -> fund
            await db.graph_relations.update_one(
                {"source_id": person_id, "target_id": fund_id, "relation_type": "works_at"},
                {"$set": {
                    "source_id": person_id,
                    "target_id": fund_id,
                    "relation_type": "works_at",
                    "direction": "out",
                    "weight": 5 if "founder" in role.lower() or "co-founder" in role.lower() else 3,
                    "metadata": {"role": role, "source": "discovery"},
                    "tags": ["team", "discovery"],
                    "first_seen": int(now.timestamp()),
                    "last_seen": int(now.timestamp()),
                }},
                upsert=True
            )
            edges_created += 1
    
    # =====================================================
    # 4. Create coinvested_with edges (fund <-> fund)
    # =====================================================
    coinvest_pairs = set()
    
    for project_slug, investors in project_investors.items():
        if len(investors) < 2:
            continue
        
        for i in range(len(investors)):
            for j in range(i + 1, len(investors)):
                a, b = sorted([investors[i], investors[j]])
                pair = (a, b)
                if pair in coinvest_pairs:
                    continue
                coinvest_pairs.add(pair)
                
                fund_a = f"fund:{a}"
                fund_b = f"fund:{b}"
                
                await db.graph_relations.update_one(
                    {"source_id": fund_a, "target_id": fund_b, "relation_type": "coinvested_with"},
                    {"$set": {
                        "source_id": fund_a,
                        "target_id": fund_b,
                        "relation_type": "coinvested_with",
                        "direction": "bidirectional",
                        "weight": 2,
                        "metadata": {"shared_project": project_slug, "source": "discovery"},
                        "tags": ["coinvestment", "discovery"],
                        "first_seen": int(now.timestamp()),
                        "last_seen": int(now.timestamp()),
                    }},
                    upsert=True
                )
                edges_created += 1
    
    # =====================================================
    # 5. Create entity_aliases for search
    # =====================================================
    alias_mappings = {
        # Fund aliases
        "a16z": ("fund", "a16z", ["a16z", "andreessen horowitz", "a16z crypto"]),
        "paradigm": ("fund", "paradigm", ["paradigm"]),
        "coinbase-ventures": ("fund", "coinbase-ventures", ["coinbase ventures"]),
        "binance-labs": ("fund", "binance-labs", ["binance labs"]),
        "polychain": ("fund", "polychain", ["polychain", "polychain capital"]),
        "pantera": ("fund", "pantera", ["pantera", "pantera capital"]),
        "dragonfly": ("fund", "dragonfly", ["dragonfly", "dragonfly capital"]),
        "multicoin": ("fund", "multicoin", ["multicoin", "multicoin capital"]),
        "sequoia": ("fund", "sequoia", ["sequoia", "sequoia capital"]),
        "galaxy": ("fund", "galaxy", ["galaxy", "galaxy digital"]),
        "jump-crypto": ("fund", "jump-crypto", ["jump", "jump crypto", "jump trading"]),
        "framework": ("fund", "framework", ["framework", "framework ventures"]),
        "hack-vc": ("fund", "hack-vc", ["hack vc", "hack"]),
        "animoca": ("fund", "animoca", ["animoca", "animoca brands"]),
        "spartan": ("fund", "spartan", ["spartan", "spartan group"]),
        "delphi": ("fund", "delphi", ["delphi", "delphi ventures"]),
        "dcg": ("fund", "dcg", ["dcg", "digital currency group"]),
        "placeholder": ("fund", "placeholder", ["placeholder", "placeholder vc"]),
        "robot-ventures": ("fund", "robot-ventures", ["robot ventures", "robot"]),
        # Project aliases
        "solana": ("project", "solana", ["solana", "sol", "SOL"]),
        "bitcoin": ("project", "bitcoin", ["bitcoin", "btc", "BTC"]),
        "ethereum": ("project", "ethereum", ["ethereum", "eth", "ETH"]),
        "polygon": ("project", "polygon", ["polygon", "matic", "MATIC"]),
        "arbitrum": ("project", "arbitrum", ["arbitrum", "arb", "ARB"]),
        "optimism": ("project", "optimism", ["optimism", "op", "OP"]),
        "avalanche": ("project", "avalanche", ["avalanche", "avax", "AVAX"]),
        "cosmos": ("project", "cosmos", ["cosmos", "atom", "ATOM"]),
        "near": ("project", "near", ["near", "near protocol", "NEAR"]),
        "aptos": ("project", "aptos", ["aptos", "apt", "APT"]),
        "sui": ("project", "sui", ["sui", "SUI"]),
        "sei": ("project", "sei", ["sei", "SEI"]),
        "polkadot": ("project", "polkadot", ["polkadot", "dot", "DOT"]),
        "celestia": ("project", "celestia", ["celestia", "tia", "TIA"]),
        "eigenlayer": ("project", "eigenlayer", ["eigenlayer", "eigen"]),
        "monad": ("project", "monad", ["monad"]),
        "berachain": ("project", "berachain", ["berachain", "bera"]),
        "uniswap": ("project", "uniswap", ["uniswap", "uni", "UNI"]),
        "aave": ("project", "aave", ["aave", "AAVE"]),
        "lido": ("project", "lido", ["lido", "lido finance", "LDO"]),
        "compound": ("project", "compound", ["compound", "comp", "COMP"]),
        "maker": ("project", "maker", ["maker", "makerdao", "MKR"]),
        "dydx": ("project", "dydx", ["dydx", "DYDX"]),
        "chainlink": ("project", "chainlink", ["chainlink", "link", "LINK"]),
        "ripple": ("project", "ripple", ["ripple", "xrp", "XRP"]),
        "opensea": ("project", "opensea", ["opensea"]),
        "wormhole": ("project", "wormhole", ["wormhole"]),
        "layerzero": ("project", "layerzero", ["layerzero"]),
        "starkware": ("project", "starkware", ["starkware", "starknet", "STRK"]),
        "matter-labs": ("project", "matter-labs", ["zksync", "matter labs", "ZK"]),
    }
    
    aliases_created = 0
    for key, (etype, eid, aliases) in alias_mappings.items():
        for alias in aliases:
            normalized = alias.lower().strip()
            await db.entity_aliases.update_one(
                {"normalized_alias": normalized, "entity_type": etype},
                {"$set": {
                    "entity_type": etype,
                    "entity_id": eid,
                    "alias": alias,
                    "normalized_alias": normalized,
                    "full_entity_id": f"{etype}:{eid}",
                    "source": "discovery",
                    "confidence": 1.0,
                    "created_at": now
                }},
                upsert=True
            )
            aliases_created += 1
    
    # =====================================================
    # 6. Create indexes
    # =====================================================
    await db.graph_relations.create_index("source_id")
    await db.graph_relations.create_index("target_id")
    await db.graph_relations.create_index("relation_type")
    await db.graph_relations.create_index([("source_id", 1), ("target_id", 1), ("relation_type", 1)])
    await db.entity_aliases.create_index("normalized_alias")
    await db.entity_aliases.create_index("entity_id")
    
    # =====================================================
    # Summary
    # =====================================================
    total_nodes = await db.graph_nodes.count_documents({})
    total_edges = await db.graph_relations.count_documents({})
    total_aliases = await db.entity_aliases.count_documents({})
    
    discovery_nodes = await db.graph_nodes.count_documents({"metadata.source": "discovery"})
    discovery_edges = await db.graph_relations.count_documents({"tags": "discovery"})
    
    print(f"\n=== Discovery Graph Seeded ===")
    print(f"  Nodes created/updated: {nodes_created}")
    print(f"  Edges created/updated: {edges_created}")
    print(f"  Aliases created: {aliases_created}")
    print(f"  Coinvestment pairs: {len(coinvest_pairs)}")
    print(f"\n  Discovery nodes: {discovery_nodes}")
    print(f"  Discovery edges: {discovery_edges}")
    print(f"  Total graph_nodes: {total_nodes}")
    print(f"  Total graph_relations: {total_edges}")
    print(f"  Total aliases: {total_aliases}")


if __name__ == "__main__":
    asyncio.run(seed_discovery_graph())
