"""
DappRadar Parser
================

Parser for DappRadar.com - DApp analytics and rankings.
Data types: dapps, usage_stats, rankings

API: https://api.dappradar.com (requires API key for full access)
"""

import httpx
import logging
from typing import Dict, List, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

DAPPRADAR_API_BASE = "https://api.dappradar.com"
# Free public endpoints
DAPPRADAR_PUBLIC_URL = "https://dappradar.com/api"


async def fetch_dappradar_top_dapps(chain: str = None, limit: int = 50) -> List[Dict]:
    """Fetch top dApps from DappRadar"""
    dapps = []
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Use public rankings endpoint
            url = f"{DAPPRADAR_PUBLIC_URL}/rankings"
            params = {"results_per_page": limit}
            
            if chain:
                params["chain"] = chain
            
            response = await client.get(
                url,
                params=params,
                headers={"User-Agent": "Mozilla/5.0"}
            )
            
            if response.status_code == 200:
                data = response.json()
                dapps = data.get("dapps", []) or data.get("data", [])
            else:
                logger.warning(f"DappRadar returned {response.status_code}")
    except Exception as e:
        logger.error(f"DappRadar fetch error: {e}")
    
    return dapps


async def fetch_dappradar_defi(limit: int = 50) -> List[Dict]:
    """Fetch DeFi dApps from DappRadar"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{DAPPRADAR_PUBLIC_URL}/rankings",
                params={"category": "defi", "results_per_page": limit},
                headers={"User-Agent": "Mozilla/5.0"}
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("dapps", []) or data.get("data", [])
    except Exception as e:
        logger.error(f"DappRadar DeFi fetch error: {e}")
    
    return []


async def sync_dappradar_data(db, limit: int = 50) -> Dict[str, Any]:
    """
    Sync DappRadar data to MongoDB.
    """
    now = datetime.now(timezone.utc).isoformat()
    results = {
        "ok": True,
        "source": "dappradar",
        "dapps": 0,
        "defi": 0,
        "errors": []
    }
    
    # Sync top dApps
    try:
        dapps = await fetch_dappradar_top_dapps(limit=limit)
        for item in dapps:
            doc = {
                "id": f"dappradar_{item.get('slug', item.get('name', '').lower().replace(' ', '_'))}",
                "source": "dappradar",
                "name": item.get("name", ""),
                "slug": item.get("slug", ""),
                "category": item.get("category", ""),
                "chain": item.get("chain", ""),
                "chains": item.get("chains", []),
                "description": item.get("description", ""),
                "website": item.get("website", ""),
                "logo": item.get("logo", ""),
                "balance": item.get("balance"),
                "users_24h": item.get("users_24h") or item.get("daily_users"),
                "transactions_24h": item.get("transactions_24h") or item.get("daily_transactions"),
                "volume_24h": item.get("volume_24h") or item.get("daily_volume"),
                "rank": item.get("rank"),
                "created_at": now,
                "updated_at": now
            }
            
            await db.defi_protocols.update_one(
                {"id": doc["id"]},
                {"$set": doc},
                upsert=True
            )
            results["dapps"] += 1
    except Exception as e:
        results["errors"].append(f"DApps sync error: {e}")
    
    # Sync DeFi specifically
    try:
        defi_dapps = await fetch_dappradar_defi(limit=limit)
        for item in defi_dapps:
            doc = {
                "id": f"dappradar_defi_{item.get('slug', '')}",
                "source": "dappradar",
                "name": item.get("name", ""),
                "category": "defi",
                "tvl": item.get("tvl") or item.get("balance"),
                "users_24h": item.get("users_24h"),
                "chains": item.get("chains", []),
                "updated_at": now
            }
            
            await db.defi_protocols.update_one(
                {"id": doc["id"]},
                {"$set": doc},
                upsert=True
            )
            results["defi"] += 1
    except Exception as e:
        results["errors"].append(f"DeFi sync error: {e}")
    
    # Update data source status
    await db.data_sources.update_one(
        {"id": "dappradar"},
        {
            "$set": {
                "last_sync": now,
                "status": "active",
                "updated_at": now
            },
            "$inc": {"sync_count": 1}
        }
    )
    
    logger.info(f"[DappRadar] Synced: {results['dapps']} dApps, {results['defi']} DeFi")
    return results
