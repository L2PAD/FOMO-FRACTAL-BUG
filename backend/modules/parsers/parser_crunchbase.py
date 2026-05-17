"""
Crunchbase Parser
=================

Parser for Crunchbase - General startup and VC database.
Note: Requires API key for full access.
"""

import httpx
import logging
import os
from typing import Dict, List, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

CRUNCHBASE_API_BASE = "https://api.crunchbase.com/api/v4"
CRUNCHBASE_API_KEY = os.environ.get("CRUNCHBASE_API_KEY", "")


async def fetch_crunchbase_funding_rounds(limit: int = 50) -> List[Dict]:
    """Fetch funding rounds from Crunchbase"""
    if not CRUNCHBASE_API_KEY:
        logger.warning("Crunchbase API key not configured")
        return []
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{CRUNCHBASE_API_BASE}/searches/funding_rounds",
                params={
                    "user_key": CRUNCHBASE_API_KEY,
                    "limit": limit
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("entities", [])
            else:
                logger.warning(f"Crunchbase returned {response.status_code}")
    except Exception as e:
        logger.error(f"Crunchbase fetch error: {e}")
    
    return []


async def fetch_crunchbase_organizations(query: str = "crypto", limit: int = 50) -> List[Dict]:
    """Fetch organizations from Crunchbase"""
    if not CRUNCHBASE_API_KEY:
        return []
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{CRUNCHBASE_API_BASE}/searches/organizations",
                params={
                    "user_key": CRUNCHBASE_API_KEY,
                    "query": query,
                    "limit": limit
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("entities", [])
    except Exception as e:
        logger.error(f"Crunchbase orgs fetch error: {e}")
    
    return []


async def sync_crunchbase_data(db, limit: int = 50) -> Dict[str, Any]:
    """Sync Crunchbase data to MongoDB"""
    now = datetime.now(timezone.utc).isoformat()
    results = {
        "ok": True,
        "source": "crunchbase",
        "funding_rounds": 0,
        "organizations": 0,
        "errors": []
    }
    
    if not CRUNCHBASE_API_KEY:
        results["errors"].append("CRUNCHBASE_API_KEY not configured")
        logger.warning("[Crunchbase] API key not configured, skipping sync")
        return results
    
    # Sync funding rounds
    try:
        rounds = await fetch_crunchbase_funding_rounds(limit)
        
        for item in rounds:
            props = item.get("properties", {})
            
            doc = {
                "id": f"crunchbase_{props.get('uuid', '')}",
                "source": "crunchbase",
                "project": props.get("organization_name", ""),
                "round_type": props.get("investment_type", ""),
                "raised_usd": props.get("money_raised", {}).get("value_usd"),
                "announced_on": props.get("announced_on"),
                "num_investors": props.get("num_investors"),
                "lead_investors": props.get("lead_investor_names", []),
                "created_at": now,
                "updated_at": now
            }
            
            await db.intel_funding.update_one(
                {"id": doc["id"]},
                {"$set": doc},
                upsert=True
            )
            results["funding_rounds"] += 1
    except Exception as e:
        results["errors"].append(f"Funding sync error: {e}")
    
    # Sync crypto organizations
    try:
        orgs = await fetch_crunchbase_organizations("crypto blockchain", limit)
        
        for item in orgs:
            props = item.get("properties", {})
            
            doc = {
                "id": f"crunchbase_{props.get('uuid', '')}",
                "source": "crunchbase",
                "name": props.get("name", ""),
                "short_description": props.get("short_description", ""),
                "category_groups": props.get("category_groups", []),
                "founded_on": props.get("founded_on"),
                "num_employees": props.get("num_employees_enum"),
                "total_funding_usd": props.get("total_funding_usd"),
                "website": props.get("homepage_url"),
                "created_at": now,
                "updated_at": now
            }
            
            await db.intel_projects.update_one(
                {"id": doc["id"]},
                {"$set": doc},
                upsert=True
            )
            results["organizations"] += 1
    except Exception as e:
        results["errors"].append(f"Organizations sync error: {e}")
    
    # Update data source status
    status = "active" if results["funding_rounds"] > 0 or results["organizations"] > 0 else "partial"
    await db.data_sources.update_one(
        {"id": "crunchbase"},
        {
            "$set": {
                "last_sync": now,
                "status": status,
                "updated_at": now
            },
            "$inc": {"sync_count": 1}
        }
    )
    
    logger.info(f"[Crunchbase] Synced: {results['funding_rounds']} rounds, {results['organizations']} orgs")
    return results
