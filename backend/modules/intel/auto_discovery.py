"""
Auto-Discovery Engine
======================
Automatically discovers missing data and new data sources.

Flow:
1. Audit current endpoints - check which ones return 404 or no data
2. For missing endpoints, search in known sources (16 cards in Discovery)
3. If not found in known sources, search web for new providers
4. Add discovered sources with is_new=True flag
"""

from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import asyncio
import httpx
import logging

logger = logging.getLogger(__name__)


# Known providers to search for missing data
KNOWN_PROVIDERS = [
    {"id": "coingecko", "url": "https://api.coingecko.com/api/v3", "type": "market"},
    {"id": "defillama", "url": "https://api.llama.fi", "type": "defi"},
    {"id": "cryptorank", "url": "https://api.cryptorank.io/v1", "type": "funding"},
    {"id": "dexscreener", "url": "https://api.dexscreener.com", "type": "dex"},
    {"id": "coinglass", "url": "https://open-api.coinglass.com", "type": "derivatives"},
    {"id": "tokenterminal", "url": "https://api.tokenterminal.com", "type": "analytics"},
]

# Web sources for discovering new providers
WEB_DISCOVERY_SOURCES = [
    "https://github.com/public-apis/public-apis",
    "https://rapidapi.com/category/Finance",
    "https://www.coingecko.com/en/api",
]


class AutoDiscoveryEngine:
    """Engine for automatic data discovery and source management"""
    
    def __init__(self, db):
        self.db = db
        self._discovery_running = False
        
    async def audit_endpoints(self, base_url: str) -> Dict[str, Any]:
        """
        Audit all documented endpoints.
        Returns status of each endpoint category.
        """
        # Get documented endpoints
        docs = await self.db.api_documentation.find({}, {'_id': 0}).to_list(500)
        
        results = {
            "total": len(docs),
            "working": 0,
            "missing_data": 0,
            "not_found": 0,
            "errors": 0,
            "categories": {},
            "missing_endpoints": []
        }
        
        async with httpx.AsyncClient(timeout=10) as client:
            for doc in docs:
                path = doc.get("path", "")
                category = doc.get("category", "other")
                
                if category not in results["categories"]:
                    results["categories"][category] = {
                        "total": 0, "working": 0, "missing": 0
                    }
                
                results["categories"][category]["total"] += 1
                
                # Skip endpoints with dynamic params for now
                if "{" in path:
                    # Test with sample params
                    test_path = path.replace("{query}", "bitcoin")\
                                    .replace("{symbol}", "BTC")\
                                    .replace("{project}", "ethereum")\
                                    .replace("{fund}", "a16z")\
                                    .replace("{exchange}", "binance")\
                                    .replace("{fundId}", "a16z")\
                                    .replace("{personId}", "vitalik")\
                                    .replace("{projectId}", "ethereum")\
                                    .replace("{project_id}", "ethereum")\
                                    .replace("{activity_id}", "1")\
                                    .replace("{source_id}", "coingecko")\
                                    .replace("{entity_id}", "btc")
                else:
                    test_path = path
                
                try:
                    url = f"{base_url}{test_path}"
                    resp = await client.get(url)
                    
                    if resp.status_code == 200:
                        results["working"] += 1
                        results["categories"][category]["working"] += 1
                    elif resp.status_code == 404:
                        results["not_found"] += 1
                        results["categories"][category]["missing"] += 1
                        results["missing_endpoints"].append({
                            "path": path,
                            "category": category,
                            "status": "not_found"
                        })
                    else:
                        results["errors"] += 1
                except Exception as e:
                    results["errors"] += 1
                    logger.debug(f"Endpoint check failed: {path} - {e}")
        
        return results
    
    async def discover_missing_data(self, endpoint_category: str) -> List[Dict]:
        """
        Try to find data for missing endpoints from known sources.
        """
        discovered = []
        
        # Map category to provider type
        category_providers = {
            "onchain": ["defillama", "dune", "glassnode"],
            "tokenomics": ["cryptorank", "messari", "tokenterminal"],
            "market": ["coingecko", "coinmarketcap", "defillama"],
            "derivatives": ["coinglass", "bybit", "binance"],
            "funds": ["cryptorank", "rootdata", "crunchbase"],
            "persons": ["cryptorank", "linkedin"],
        }
        
        relevant_providers = category_providers.get(endpoint_category, [])
        
        for provider_id in relevant_providers:
            provider = next((p for p in KNOWN_PROVIDERS if p["id"] == provider_id), None)
            if provider:
                # Check if provider can fulfill the category
                try:
                    async with httpx.AsyncClient(timeout=5) as client:
                        resp = await client.get(f"{provider['url']}/")
                        if resp.status_code < 500:
                            discovered.append({
                                "provider_id": provider_id,
                                "can_fulfill": True,
                                "category": endpoint_category
                            })
                except:
                    pass
        
        return discovered
    
    async def add_discovered_source(self, source_data: Dict) -> str:
        """
        Add a newly discovered data source with is_new=True flag.
        """
        source_id = source_data.get("id")
        
        # Check if already exists
        existing = await self.db.data_sources.find_one({"id": source_id})
        if existing:
            return "exists"
        
        # Add with is_new flag
        source_data["is_new"] = True
        source_data["discovered_at"] = datetime.now(timezone.utc).isoformat()
        source_data["status"] = "planned"
        
        await self.db.data_sources.insert_one(source_data)
        
        # Also add to providers collection
        provider_doc = {
            "id": source_id,
            "name": source_data.get("name"),
            "status": "active",
            "is_new": True,
            "discovered_at": source_data["discovered_at"],
            "category": source_data.get("categories", ["other"])[0],
            "requires_api_key": source_data.get("api_key_required", False),
            "capabilities": source_data.get("data_types", []),
            "rate_limit": source_data.get("rate_limit", "60"),
            "description": source_data.get("description", "Auto-discovered provider")
        }
        
        await self.db.providers.update_one(
            {"id": source_id},
            {"$set": provider_doc},
            upsert=True
        )
        
        logger.info(f"Added new data source: {source_id}")
        return "added"
    
    async def mark_source_as_seen(self, source_id: str) -> bool:
        """
        Remove is_new flag from source after user has seen it.
        """
        result = await self.db.data_sources.update_one(
            {"id": source_id},
            {"$set": {"is_new": False}}
        )
        
        await self.db.providers.update_one(
            {"id": source_id},
            {"$set": {"is_new": False}}
        )
        
        return result.modified_count > 0
    
    async def get_discovery_status(self) -> Dict:
        """
        Get current discovery status and new sources count.
        """
        new_sources = await self.db.data_sources.count_documents({"is_new": True})
        new_providers = await self.db.providers.count_documents({"is_new": True})
        total_sources = await self.db.data_sources.count_documents({})
        
        return {
            "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
            "new_sources": new_sources,
            "new_providers": new_providers,
            "total_sources": total_sources,
            "discovery_running": self._discovery_running
        }
    
    async def run_full_discovery(self, base_url: str) -> Dict:
        """
        Run full discovery process:
        1. Audit endpoints
        2. Find missing data in known sources
        3. Add new sources if found
        """
        if self._discovery_running:
            return {"error": "Discovery already running"}
        
        self._discovery_running = True
        results = {
            "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
            "audit": None,
            "discoveries": [],
            "new_sources_added": 0
        }
        
        try:
            # Step 1: Audit
            audit = await self.audit_endpoints(base_url)
            results["audit"] = {
                "total": audit["total"],
                "working": audit["working"],
                "missing": audit["not_found"]
            }
            
            # Step 2: Find missing data categories
            missing_categories = set()
            for ep in audit.get("missing_endpoints", []):
                missing_categories.add(ep.get("category", "other"))
            
            # Step 3: Discover sources for missing categories
            for category in missing_categories:
                discoveries = await self.discover_missing_data(category)
                results["discoveries"].extend(discoveries)
            
            # Count how many new could be added
            results["potential_new_sources"] = len(set(d["provider_id"] for d in results["discoveries"]))
            
        finally:
            self._discovery_running = False
        
        return results


# Global instance
_discovery_engine = None

def get_discovery_engine(db):
    global _discovery_engine
    if _discovery_engine is None:
        _discovery_engine = AutoDiscoveryEngine(db)
    return _discovery_engine
