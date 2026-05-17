"""
FOMO Projects Extended Profile API
===================================
Extended project profile endpoints:
- GET /api/projects/{id}/about - Project description, technology, whitepaper
- GET /api/projects/{id}/links - Official links (twitter, discord, github, etc.)
- GET /api/projects/{id}/explorers - Blockchain explorers
- GET /api/projects/{id}/bridges - Cross-chain bridges
- GET /api/projects/{id}/activities - Project activities

Collections:
- project_profiles (about, technology, whitepaper)
- project_links (official links)
- project_explorers (blockchain explorers)
- project_bridges (cross-chain bridges)
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

router = APIRouter(prefix="/api/projects", tags=["Projects Extended"])


def ts_now():
    return int(datetime.now(timezone.utc).timestamp() * 1000)


async def get_project_by_id(db, project_id: str) -> dict:
    """Find project by ID, slug, or symbol."""
    project = await db.intel_projects.find_one({
        "$or": [
            {"key": project_id},
            {"slug": project_id},
            {"symbol": project_id.upper()}
        ]
    })
    return project


# ═══════════════════════════════════════════════════════════════
# PROJECT ABOUT
# ═══════════════════════════════════════════════════════════════

@router.get("/{project_id}/about")
async def get_project_about(project_id: str):
    """
    Get project about information:
    - Description
    - Technology
    - Consensus mechanism
    - Token utility
    - Launch year
    - Whitepaper
    """
    from server import db
    
    project = await get_project_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    project_key = project.get("key", project_id)
    
    # Try to get extended profile
    profile = await db.project_profiles.find_one({"project_id": project_key})
    
    # Build about section (with safe access to profile)
    about = {
        "project_id": project_key,
        "name": project.get("name"),
        "symbol": project.get("symbol"),
        "logo": project.get("logo_url"),
        "description": profile.get("about") if profile and isinstance(profile, dict) else project.get("description"),
        "short_description": project.get("description", "")[:200] if project.get("description") else None,
        "technology": profile.get("technology") if profile and isinstance(profile, dict) else None,
        "consensus": profile.get("consensus") if profile and isinstance(profile, dict) else None,
        "token_utility": profile.get("token_utility") if profile and isinstance(profile, dict) else None,
        "launch_year": (profile.get("launch_year") if profile and isinstance(profile, dict) else None) or project.get("founded_year"),
        "whitepaper": profile.get("whitepaper") if profile and isinstance(profile, dict) else project.get("whitepaper"),
        "category": project.get("category"),
        "chain": project.get("chain"),
        "tags": project.get("tags", [])
    }
    
    return {
        "ts": ts_now(),
        "about": about,
        "_meta": {"cache_sec": 3600}
    }


# ═══════════════════════════════════════════════════════════════
# PROJECT LINKS
# ═══════════════════════════════════════════════════════════════

@router.get("/{project_id}/links")
async def get_project_links(project_id: str):
    """
    Get project official links:
    - Website
    - Twitter
    - Telegram
    - Discord
    - Reddit
    - GitHub
    - LinkedIn
    - Medium
    - YouTube
    - Facebook
    """
    from server import db
    
    project = await get_project_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    project_key = project.get("key", project_id)
    
    # Try to get from dedicated links collection
    links_doc = await db.project_links.find_one({"project_id": project_key})
    
    # Build links from project or links collection
    links = {
        "project_id": project_key,
        "name": project.get("name"),
        "website": (links_doc or project).get("website"),
        "twitter": (links_doc or project).get("twitter"),
        "telegram": (links_doc or project).get("telegram"),
        "discord": (links_doc or project).get("discord"),
        "reddit": (links_doc or project).get("reddit"),
        "github": (links_doc or project).get("github"),
        "linkedin": (links_doc or project).get("linkedin"),
        "medium": (links_doc or project).get("medium"),
        "youtube": (links_doc or project).get("youtube"),
        "facebook": (links_doc or project).get("facebook"),
        "blog": (links_doc or project).get("blog"),
        "documentation": (links_doc or project).get("documentation"),
        "forum": (links_doc or project).get("forum")
    }
    
    # Filter out None values and build list
    official_links = []
    for platform, url in links.items():
        if url and platform not in ["project_id", "name"]:
            official_links.append({
                "platform": platform,
                "url": url,
                "icon": f"fa-{platform}" if platform in ["twitter", "telegram", "discord", "reddit", "github", "linkedin", "medium", "youtube", "facebook"] else "fa-link"
            })
    
    return {
        "ts": ts_now(),
        "project_id": project_key,
        "project_name": project.get("name"),
        "links": links,
        "official_links": official_links,
        "_meta": {"cache_sec": 3600}
    }


# ═══════════════════════════════════════════════════════════════
# PROJECT EXPLORERS
# ═══════════════════════════════════════════════════════════════

@router.get("/{project_id}/explorers")
async def get_project_explorers(project_id: str):
    """
    Get blockchain explorers for project:
    - Explorer name
    - Chain
    - URL
    """
    from server import db
    
    project = await get_project_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    project_key = project.get("key", project_id)
    symbol = project.get("symbol", "")
    chain = project.get("chain", "")
    
    # Get explorers from collection
    cursor = db.project_explorers.find({"project_id": project_key})
    explorers = await cursor.to_list(20)
    
    # If no explorers in DB, generate defaults based on chain
    if not explorers:
        default_explorers = []
        
        chain_lower = chain.lower() if chain else ""
        symbol_lower = symbol.lower() if symbol else ""
        
        # Bitcoin
        if symbol_lower == "btc" or chain_lower == "bitcoin":
            default_explorers = [
                {"name": "Blockchain.info", "chain": "Bitcoin", "url": "https://www.blockchain.com/explorer"},
                {"name": "Blockchair", "chain": "Bitcoin", "url": "https://blockchair.com/bitcoin"},
                {"name": "Blockcypher", "chain": "Bitcoin", "url": "https://live.blockcypher.com/btc/"},
                {"name": "OKLink", "chain": "Bitcoin", "url": "https://www.oklink.com/btc"}
            ]
        # Ethereum
        elif symbol_lower == "eth" or chain_lower == "ethereum":
            default_explorers = [
                {"name": "Etherscan", "chain": "Ethereum", "url": "https://etherscan.io"},
                {"name": "Blockchair", "chain": "Ethereum", "url": "https://blockchair.com/ethereum"},
                {"name": "Ethplorer", "chain": "Ethereum", "url": "https://ethplorer.io"},
                {"name": "OKLink", "chain": "Ethereum", "url": "https://www.oklink.com/eth"}
            ]
        # Solana
        elif symbol_lower == "sol" or chain_lower == "solana":
            default_explorers = [
                {"name": "Solscan", "chain": "Solana", "url": "https://solscan.io"},
                {"name": "Solana Explorer", "chain": "Solana", "url": "https://explorer.solana.com"},
                {"name": "SolanaFM", "chain": "Solana", "url": "https://solana.fm"}
            ]
        # Arbitrum
        elif chain_lower == "arbitrum":
            default_explorers = [
                {"name": "Arbiscan", "chain": "Arbitrum", "url": "https://arbiscan.io"},
                {"name": "Arbitrum Explorer", "chain": "Arbitrum", "url": "https://explorer.arbitrum.io"}
            ]
        # Optimism
        elif chain_lower == "optimism":
            default_explorers = [
                {"name": "Optimistic Etherscan", "chain": "Optimism", "url": "https://optimistic.etherscan.io"}
            ]
        # Polygon
        elif chain_lower == "polygon":
            default_explorers = [
                {"name": "Polygonscan", "chain": "Polygon", "url": "https://polygonscan.com"}
            ]
        # BSC
        elif chain_lower == "bsc" or chain_lower == "binance":
            default_explorers = [
                {"name": "BscScan", "chain": "BSC", "url": "https://bscscan.com"}
            ]
        # Avalanche
        elif chain_lower == "avalanche":
            default_explorers = [
                {"name": "SnowTrace", "chain": "Avalanche", "url": "https://snowtrace.io"},
                {"name": "Avascan", "chain": "Avalanche", "url": "https://avascan.info"}
            ]
        
        explorers = default_explorers
    else:
        # Format from DB
        explorers = [
            {
                "name": e.get("name"),
                "chain": e.get("chain"),
                "url": e.get("url")
            }
            for e in explorers
        ]
    
    return {
        "ts": ts_now(),
        "project_id": project_key,
        "project_name": project.get("name"),
        "chain": chain,
        "explorers_count": len(explorers),
        "explorers": explorers,
        "_meta": {"cache_sec": 3600}
    }


# ═══════════════════════════════════════════════════════════════
# PROJECT BRIDGES
# ═══════════════════════════════════════════════════════════════

@router.get("/{project_id}/bridges")
async def get_project_bridges(project_id: str):
    """
    Get cross-chain bridges for project token:
    - Bridge name
    - From chain
    - To chain
    - URL
    """
    from server import db
    
    project = await get_project_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    project_key = project.get("key", project_id)
    symbol = project.get("symbol", "")
    chain = project.get("chain", "")
    
    # Get bridges from collection
    cursor = db.project_bridges.find({"project_id": project_key})
    bridges = await cursor.to_list(20)
    
    # If no bridges in DB, provide defaults for major tokens
    if not bridges:
        default_bridges = []
        symbol_lower = symbol.lower() if symbol else ""
        
        # Common bridges for major chains
        if symbol_lower in ["eth", "weth", "usdc", "usdt", "dai"]:
            default_bridges = [
                {"bridge_name": "Arbitrum Bridge", "from_chain": "Ethereum", "to_chain": "Arbitrum", "url": "https://bridge.arbitrum.io"},
                {"bridge_name": "Optimism Bridge", "from_chain": "Ethereum", "to_chain": "Optimism", "url": "https://app.optimism.io/bridge"},
                {"bridge_name": "Polygon Bridge", "from_chain": "Ethereum", "to_chain": "Polygon", "url": "https://wallet.polygon.technology/bridge"},
                {"bridge_name": "Stargate", "from_chain": "Multi-chain", "to_chain": "Multi-chain", "url": "https://stargate.finance/transfer"},
                {"bridge_name": "Hop Protocol", "from_chain": "Multi-chain", "to_chain": "Multi-chain", "url": "https://hop.exchange"}
            ]
        elif chain and chain.lower() == "solana":
            default_bridges = [
                {"bridge_name": "Wormhole", "from_chain": "Solana", "to_chain": "Multi-chain", "url": "https://wormhole.com"},
                {"bridge_name": "Portal Bridge", "from_chain": "Solana", "to_chain": "Multi-chain", "url": "https://portalbridge.com"}
            ]
        
        bridges = default_bridges
    else:
        bridges = [
            {
                "bridge_name": b.get("bridge_name"),
                "from_chain": b.get("from_chain"),
                "to_chain": b.get("to_chain"),
                "url": b.get("url")
            }
            for b in bridges
        ]
    
    return {
        "ts": ts_now(),
        "project_id": project_key,
        "project_name": project.get("name"),
        "symbol": symbol,
        "bridges_count": len(bridges),
        "bridges": bridges,
        "_meta": {"cache_sec": 3600}
    }


# ═══════════════════════════════════════════════════════════════
# PROJECT ACTIVITIES
# ═══════════════════════════════════════════════════════════════

@router.get("/{project_id}/activities")
async def get_project_activities(
    project_id: str,
    status: Optional[str] = Query(None, description="Filter: active, upcoming, ended"),
    type: Optional[str] = Query(None, description="Filter by activity type"),
    limit: int = Query(20, ge=1, le=100)
):
    """
    Get all activities for a specific project.
    """
    from server import db
    
    project = await get_project_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    project_key = project.get("key", project_id)
    
    query = {
        "$or": [
            {"project_id": project_key},
            {"project_id": project_id},
            {"project_name": {"$regex": project.get("name", ""), "$options": "i"}}
        ]
    }
    
    now = datetime.now(timezone.utc)
    if status == "active":
        query["$and"] = [
            {"$or": [{"start_date": {"$lte": now.isoformat()}}, {"start_date": {"$exists": False}}]},
            {"$or": [{"end_date": {"$gte": now.isoformat()}}, {"end_date": {"$exists": False}}, {"end_date": None}]}
        ]
    elif status == "upcoming":
        query["start_date"] = {"$gt": now.isoformat()}
    elif status == "ended":
        query["end_date"] = {"$lt": now.isoformat()}
    
    if type:
        query["type"] = type
    
    cursor = db.crypto_activities.find(query).sort("start_date", -1).limit(limit)
    activities = await cursor.to_list(limit)
    
    items = []
    for act in activities:
        items.append({
            "id": act.get("id", str(act.get("_id", ""))),
            "title": act.get("title"),
            "description": act.get("description", "")[:200],
            "type": act.get("type"),
            "category": act.get("category"),
            "status": act.get("status", "active"),
            "reward": act.get("reward"),
            "difficulty": act.get("difficulty"),
            "start_date": act.get("start_date"),
            "end_date": act.get("end_date"),
            "source": act.get("source"),
            "source_url": act.get("source_url"),
            "score": act.get("score", 50)
        })
    
    return {
        "ts": ts_now(),
        "project_id": project_key,
        "project_name": project.get("name"),
        "count": len(items),
        "activities": items,
        "_meta": {"cache_sec": 300}
    }


# ═══════════════════════════════════════════════════════════════
# PROJECT UNLOCKS
# ═══════════════════════════════════════════════════════════════

@router.get("/{project_id}/unlocks")
async def get_project_unlocks(
    project_id: str,
    include_past: bool = Query(False, description="Include past unlocks"),
    limit: int = Query(50, ge=1, le=200)
):
    """
    Get all token unlocks for a specific project.
    """
    from server import db
    
    project = await get_project_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    project_key = project.get("key", project_id)
    symbol = project.get("symbol", "")
    
    now = datetime.now(timezone.utc)
    
    query = {
        "$or": [
            {"project_id": project_key},
            {"project_id": project_id},
            {"symbol": symbol.upper() if symbol else ""}
        ]
    }
    
    if not include_past:
        query["date"] = {"$gte": now.isoformat()}
    
    cursor = db.token_unlocks.find(query).sort("date", 1).limit(limit)
    unlocks = await cursor.to_list(limit)
    
    # Also check unlock_events collection
    if not unlocks:
        cursor = db.unlock_events.find(query).sort("unlock_date", 1).limit(limit)
        unlocks = await cursor.to_list(limit)
    
    items = []
    for u in unlocks:
        items.append({
            "id": u.get("id", str(u.get("_id", ""))),
            "date": u.get("date") or u.get("unlock_date"),
            "category": u.get("category"),
            "amount_tokens": u.get("amount_tokens") or u.get("unlock_amount"),
            "amount_usd": u.get("amount_usd") or u.get("value_usd"),
            "percent_supply": u.get("percent_supply") or u.get("percent_of_supply"),
            "is_future": u.get("is_future", True)
        })
    
    # Calculate summary
    total_tokens = sum(u.get("amount_tokens", 0) or 0 for u in items)
    total_usd = sum(u.get("amount_usd", 0) or 0 for u in items)
    total_percent = sum(u.get("percent_supply", 0) or 0 for u in items)
    
    return {
        "ts": ts_now(),
        "project_id": project_key,
        "project_name": project.get("name"),
        "symbol": symbol,
        "summary": {
            "upcoming_unlocks": len(items),
            "total_tokens": total_tokens,
            "total_usd": total_usd,
            "total_percent_supply": round(total_percent, 4)
        },
        "unlocks": items,
        "_meta": {"cache_sec": 600}
    }
