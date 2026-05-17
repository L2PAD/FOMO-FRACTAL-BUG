"""
RootData Parser
===============

Parser for RootData.com - Crypto investment and fund data.
TIER 1 source - Core Data

Owner fields: fund_profile, fund_portfolio, founders, team_members, advisors
Data types: funding_rounds, investor_profiles, team_members

API: https://api.rootdata.com (free tier available)
"""

import httpx
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone

from modules.intel.parser_validation import ParserValidator

logger = logging.getLogger(__name__)

ROOTDATA_API_BASE = "https://api.rootdata.com/open"

# Parser validator
_validator = ParserValidator("rootdata")


async def fetch_rootdata_funding(limit: int = 50) -> List[Dict]:
    """Fetch funding rounds from RootData"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # RootData API endpoint for funding rounds
            response = await client.get(
                f"{ROOTDATA_API_BASE}/ser_inv",
                params={"limit": limit, "page": 1}
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("data", {}).get("list", [])
            else:
                logger.warning(f"RootData API returned {response.status_code}")
                return []
    except Exception as e:
        logger.error(f"RootData funding fetch error: {e}")
        return []


async def fetch_rootdata_investors(limit: int = 50) -> List[Dict]:
    """Fetch investor profiles from RootData"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{ROOTDATA_API_BASE}/org",
                params={"limit": limit, "page": 1, "type": "vc"}
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("data", {}).get("list", [])
            else:
                return []
    except Exception as e:
        logger.error(f"RootData investors fetch error: {e}")
        return []


async def fetch_rootdata_projects(limit: int = 50) -> List[Dict]:
    """Fetch project profiles from RootData"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{ROOTDATA_API_BASE}/item",
                params={"limit": limit, "page": 1}
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("data", {}).get("list", [])
            else:
                return []
    except Exception as e:
        logger.error(f"RootData projects fetch error: {e}")
        return []


async def sync_rootdata_data(db, limit: int = 50) -> Dict[str, Any]:
    """
    Sync RootData data to MongoDB.
    """
    now = datetime.now(timezone.utc).isoformat()
    results = {
        "ok": True,
        "source": "rootdata",
        "funding": 0,
        "investors": 0,
        "projects": 0,
        "errors": []
    }
    
    # Sync funding rounds
    try:
        funding_data = await fetch_rootdata_funding(limit)
        for item in funding_data:
            doc = {
                "id": f"rootdata_funding_{item.get('id', '')}",
                "source": "rootdata",
                "project": item.get("project_name", ""),
                "project_id": item.get("project_id", ""),
                "round_type": item.get("round", ""),
                "raised_usd": item.get("amount", 0),
                "valuation_usd": item.get("valuation"),
                "funding_rounds": item.get("project_name", ""),  # Field we can provide
                "investor_list": item.get("investors", []),      # Field we can provide
                "investors": item.get("investors", []),
                "round_date": item.get("date"),
                "announcement_url": item.get("link"),
                "created_at": now,
                "updated_at": now
            }
            
            # Validate data
            validated_doc = _validator.filter_data(doc)
            
            # Check if this is a new funding round
            existing = await db.intel_funding.find_one({"id": validated_doc["id"]})
            is_new = existing is None
            
            await db.intel_funding.update_one(
                {"id": validated_doc["id"]},
                {"$set": validated_doc},
                upsert=True
            )
            results["funding"] += 1
            
            # Emit webhook for new funding rounds
            if is_new:
                try:
                    from modules.webhooks import emit_on_funding_insert
                    await emit_on_funding_insert(db, validated_doc)
                except Exception as e:
                    logger.warning(f"[RootData] Webhook emit error: {e}")
    except Exception as e:
        results["errors"].append(f"Funding sync error: {e}")
    
    # Sync investors
    try:
        investors_data = await fetch_rootdata_investors(limit)
        for item in investors_data:
            doc = {
                "id": f"rootdata_investor_{item.get('id', '')}",
                "source": "rootdata",
                "name": item.get("name", ""),
                "slug": item.get("slug", ""),
                "category": item.get("type", "vc"),
                "website": item.get("website"),
                "twitter": item.get("twitter"),
                "portfolio_count": item.get("portfolio_count", 0),
                "aum_usd": item.get("aum"),
                "description": item.get("description"),
                "logo": item.get("logo"),
                "created_at": now,
                "updated_at": now
            }
            
            await db.intel_investors.update_one(
                {"id": doc["id"]},
                {"$set": doc},
                upsert=True
            )
            results["investors"] += 1
    except Exception as e:
        results["errors"].append(f"Investors sync error: {e}")
    
    # Sync projects
    try:
        projects_data = await fetch_rootdata_projects(limit)
        for item in projects_data:
            doc = {
                "id": f"rootdata_project_{item.get('id', '')}",
                "source": "rootdata",
                "name": item.get("name", ""),
                "symbol": item.get("symbol"),
                "slug": item.get("slug", ""),
                "category": item.get("category"),
                "description": item.get("description"),
                "website": item.get("website"),
                "twitter": item.get("twitter"),
                "total_funding": item.get("total_funding"),
                "team_size": item.get("team_size"),
                "logo": item.get("logo"),
                "created_at": now,
                "updated_at": now
            }
            
            await db.intel_projects.update_one(
                {"id": doc["id"]},
                {"$set": doc},
                upsert=True
            )
            results["projects"] += 1
    except Exception as e:
        results["errors"].append(f"Projects sync error: {e}")
    
    # Update data source status
    await db.data_sources.update_one(
        {"id": "rootdata"},
        {
            "$set": {
                "last_sync": now,
                "status": "active",
                "updated_at": now
            },
            "$inc": {"sync_count": 1}
        }
    )
    
    logger.info(f"[RootData] Synced: {results['funding']} funding, {results['investors']} investors, {results['projects']} projects")
    return results
