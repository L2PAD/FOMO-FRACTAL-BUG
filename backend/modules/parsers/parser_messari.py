"""
Messari Parser
==============
Parser for crypto research and metrics from Messari.
Free tier has limited endpoints.

Endpoints:
- /assets - List of assets with metrics
- /assets/{slug}/metrics - Asset metrics
- /assets/{slug}/profile - Asset profile
"""

import httpx
import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

BASE_URL = "https://data.messari.io/api/v1"
BASE_URL_V2 = "https://data.messari.io/api/v2"


class MessariParser:
    """Parser for Messari crypto data"""
    
    def __init__(self, db, api_key: Optional[str] = None):
        self.db = db
        self.api_key = api_key
        headers = {"Accept": "application/json"}
        if api_key:
            headers["x-messari-api-key"] = api_key
        self.client = httpx.AsyncClient(timeout=30, headers=headers)
    
    async def close(self):
        await self.client.aclose()
    
    async def fetch_assets(self, limit: int = 50) -> List[Dict]:
        """Fetch top assets with metrics"""
        try:
            resp = await self.client.get(
                f"{BASE_URL_V2}/assets",
                params={"limit": limit, "fields": "id,slug,symbol,name,metrics"}
            )
            if resp.status_code == 200:
                data = resp.json()
                assets = data.get("data", [])
                logger.info(f"Messari: Fetched {len(assets)} assets")
                return assets
            else:
                logger.warning(f"Messari assets failed: {resp.status_code}")
                return []
        except Exception as e:
            logger.error(f"Messari assets error: {e}")
            return []
    
    async def fetch_asset_profile(self, slug: str) -> Optional[Dict]:
        """Fetch detailed asset profile"""
        try:
            resp = await self.client.get(f"{BASE_URL_V2}/assets/{slug}/profile")
            if resp.status_code == 200:
                data = resp.json()
                return data.get("data")
            return None
        except Exception as e:
            logger.error(f"Messari profile {slug} error: {e}")
            return None
    
    async def fetch_asset_metrics(self, slug: str) -> Optional[Dict]:
        """Fetch asset metrics"""
        try:
            resp = await self.client.get(f"{BASE_URL}/assets/{slug}/metrics")
            if resp.status_code == 200:
                data = resp.json()
                return data.get("data")
            return None
        except Exception as e:
            logger.error(f"Messari metrics {slug} error: {e}")
            return None
    
    async def sync_assets(self, limit: int = 50) -> Dict[str, Any]:
        """Sync assets to database"""
        assets = await self.fetch_assets(limit)
        now = datetime.now(timezone.utc).isoformat()
        
        synced = 0
        for a in assets:
            metrics = a.get("metrics", {}) or {}
            market_data = metrics.get("market_data", {}) or {}
            
            doc = {
                "id": f"messari:{a.get('slug', '')}",
                "source": "messari",
                "messari_id": a.get("id"),
                "name": a.get("name"),
                "slug": a.get("slug"),
                "symbol": a.get("symbol"),
                # Market metrics
                "price_usd": market_data.get("price_usd"),
                "market_cap": market_data.get("real_volume_last_24_hours"),
                "volume_24h": market_data.get("volume_last_24_hours"),
                "price_change_24h": market_data.get("percent_change_usd_last_24_hours"),
                # On-chain metrics
                "active_addresses": metrics.get("on_chain_data", {}).get("active_addresses") if metrics.get("on_chain_data") else None,
                "transaction_volume": metrics.get("on_chain_data", {}).get("transaction_volume") if metrics.get("on_chain_data") else None,
                # ROI metrics
                "roi_data": metrics.get("roi_data"),
                # Developer activity
                "developer_activity": metrics.get("developer_activity"),
                "updated_at": now
            }
            
            await self.db.messari_assets.update_one(
                {"id": doc["id"]},
                {"$set": doc},
                upsert=True
            )
            synced += 1
        
        # Update data source status
        await self._update_source_status("messari", True, synced)
        
        return {"synced": synced, "source": "messari"}
    
    async def sync_profiles(self, slugs: List[str]) -> Dict[str, Any]:
        """Sync detailed profiles for specific assets"""
        now = datetime.now(timezone.utc).isoformat()
        synced = 0
        
        for slug in slugs[:20]:  # Limit to avoid rate limits
            profile = await self.fetch_asset_profile(slug)
            if profile:
                general = profile.get("profile", {}).get("general", {}) or {}
                contributors = profile.get("profile", {}).get("contributors", {}) or {}
                
                doc = {
                    "id": f"messari:profile:{slug}",
                    "source": "messari",
                    "slug": slug,
                    "tagline": general.get("overview", {}).get("tagline") if general.get("overview") else None,
                    "category": general.get("overview", {}).get("category") if general.get("overview") else None,
                    "sector": general.get("overview", {}).get("sector") if general.get("overview") else None,
                    "description": general.get("overview", {}).get("project_details") if general.get("overview") else None,
                    # Team info
                    "individuals": contributors.get("individuals", []),
                    "organizations": contributors.get("organizations", []),
                    "updated_at": now
                }
                
                await self.db.messari_profiles.update_one(
                    {"id": doc["id"]},
                    {"$set": doc},
                    upsert=True
                )
                synced += 1
        
        return {"synced": synced, "type": "profiles"}
    
    async def _update_source_status(self, source_id: str, success: bool, count: int):
        """Update data source sync status"""
        now = datetime.now(timezone.utc).isoformat()
        update = {
            "updated_at": now,
            "status": "active" if success else "error"
        }
        if success:
            update["last_sync"] = now
        
        await self.db.data_sources.update_one(
            {"id": source_id},
            {"$set": update, "$inc": {"sync_count": 1}}
        )


async def sync_messari_data(db, limit: int = 50):
    """Main sync function for Messari"""
    parser = MessariParser(db)
    try:
        result = await parser.sync_assets(limit)
        logger.info(f"Messari sync complete: {result['synced']} assets")
        return result
    finally:
        await parser.close()
