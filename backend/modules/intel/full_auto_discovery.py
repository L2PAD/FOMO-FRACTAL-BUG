"""
Full Auto-Discovery System
==========================
Automatically discovers missing data and creates new sources/endpoints.

Flow:
1. Audit endpoints -> find missing
2. For each missing, search in known providers
3. If found, generate adapter and register
4. If not found in known, search web for new providers
5. Add new providers with is_new=True
6. Update Discovery UI automatically
"""

from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple
import asyncio
import httpx
import logging
import re
import json

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# KNOWN DATA PROVIDERS BY CATEGORY
# ═══════════════════════════════════════════════════════════════

CATEGORY_PROVIDERS = {
    "onchain": [
        {
            "id": "defillama",
            "name": "DefiLlama",
            "base_url": "https://api.llama.fi",
            "endpoints": {
                "tvl": "/protocols",
                "protocol_tvl": "/protocol/{protocol}",
                "chains": "/chains",
                "yields": "/yields",
                "stablecoins": "https://stablecoins.llama.fi/stablecoins"
            },
            "free": True,
            "categories": ["defi", "tvl", "yields"]
        },
        {
            "id": "coinglass",
            "name": "CoinGlass",
            "base_url": "https://open-api.coinglass.com",
            "endpoints": {
                "liquidations": "/public/v2/liquidation_chart",
                "funding": "/public/v2/funding",
                "oi": "/public/v2/open_interest"
            },
            "free": True,
            "categories": ["derivatives", "liquidations", "funding"]
        }
    ],
    "tokenomics": [
        {
            "id": "coingecko",
            "name": "CoinGecko",
            "base_url": "https://api.coingecko.com/api/v3",
            "endpoints": {
                "coin": "/coins/{coin_id}",
                "markets": "/coins/markets",
                "global": "/global"
            },
            "free": True,
            "categories": ["market", "tokenomics", "prices"]
        },
        {
            "id": "defillama_unlocks",
            "name": "DefiLlama Unlocks",
            "base_url": "https://api.llama.fi",
            "endpoints": {
                "unlocks": "/protocol/{protocol}"
            },
            "free": True,
            "categories": ["unlocks", "vesting"]
        }
    ],
    "market": [
        {
            "id": "coingecko",
            "name": "CoinGecko",
            "base_url": "https://api.coingecko.com/api/v3",
            "endpoints": {
                "price": "/simple/price",
                "markets": "/coins/markets",
                "ohlc": "/coins/{coin_id}/ohlc"
            },
            "free": True,
            "categories": ["prices", "market", "volume"]
        },
        {
            "id": "dexscreener",
            "name": "DexScreener",
            "base_url": "https://api.dexscreener.com",
            "endpoints": {
                "search": "/latest/dex/search",
                "pairs": "/latest/dex/pairs/{chain}/{pair}"
            },
            "free": True,
            "categories": ["dex", "prices", "liquidity"]
        }
    ],
    "funds": [
        {
            "id": "cryptorank",
            "name": "CryptoRank",
            "base_url": "https://api.cryptorank.io/v1",
            "endpoints": {
                "funds": "/funds",
                "fund": "/funds/{fund_id}"
            },
            "free": False,
            "categories": ["funds", "vc", "investments"]
        },
        {
            "id": "rootdata",
            "name": "RootData",
            "base_url": "https://api.rootdata.com",
            "endpoints": {
                "funding": "/funding",
                "investors": "/investors"
            },
            "free": False,
            "categories": ["funding", "investors"]
        }
    ],
    "persons": [
        {
            "id": "cryptorank_people",
            "name": "CryptoRank People",
            "base_url": "https://api.cryptorank.io/v1",
            "endpoints": {
                "people": "/people",
                "person": "/people/{person_id}"
            },
            "free": False,
            "categories": ["people", "founders", "executives"]
        }
    ],
    "derivatives": [
        {
            "id": "coinglass",
            "name": "CoinGlass",
            "base_url": "https://open-api.coinglass.com",
            "endpoints": {
                "funding": "/public/v2/funding",
                "oi": "/public/v2/open_interest",
                "liquidations": "/public/v2/liquidation_chart"
            },
            "free": True,
            "categories": ["funding", "open_interest", "liquidations"]
        }
    ]
}


class FullAutoDiscovery:
    """Full automatic discovery and integration system"""
    
    def __init__(self, db):
        self.db = db
        self._running = False
        self._discovered_providers = []
        
    async def run_full_audit(self, api_base_url: str) -> Dict[str, Any]:
        """
        Run complete audit of all endpoints.
        Returns detailed status of each endpoint.
        """
        # Get documented endpoints from API registry
        try:
            from modules.intel.api.documentation_registry import API_DOCUMENTATION
            docs = []
            for endpoint in API_DOCUMENTATION:
                docs.append({
                    "path": endpoint.path,
                    "method": endpoint.method.value if hasattr(endpoint.method, 'value') else endpoint.method,
                    "category": endpoint.category,
                    "title": endpoint.title_en
                })
        except ImportError:
            # Fallback to database
            docs = await self.db.docs_endpoints.find({}, {'_id': 0}).to_list(500)
        
        if not docs:
            return {
                "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
                "error": "No endpoint documentation found",
                "total_endpoints": 0
            }
        
        results = {
            "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
            "total_endpoints": len(docs),
            "working": [],
            "working_no_data": [],
            "not_found": [],
            "errors": [],
            "by_category": {}
        }
        
        # Sample data for path params
        samples = {
            "symbol": "BTC",
            "query": "bitcoin",
            "project": "ethereum",
            "projectId": "ethereum",
            "project_id": "ethereum",
            "fund": "a16z",
            "fundId": "a16z",
            "person": "vitalik-buterin",
            "personId": "vitalik-buterin",
            "exchange": "binance",
            "source_id": "coingecko",
            "entity_id": "btc",
            "activity_id": "1",
            "coin_id": "bitcoin"
        }
        
        async with httpx.AsyncClient(timeout=8) as client:
            for doc in docs:
                path = doc.get("path", "")
                category = doc.get("category", "other")
                method = doc.get("method", "GET").upper()
                
                # Initialize category
                if category not in results["by_category"]:
                    results["by_category"][category] = {
                        "total": 0, "working": 0, "missing": 0
                    }
                results["by_category"][category]["total"] += 1
                
                # Replace path params
                test_path = path
                for key, value in samples.items():
                    test_path = test_path.replace(f"{{{key}}}", value)
                
                try:
                    url = f"{api_base_url}{test_path}"
                    
                    if method == "GET":
                        resp = await client.get(url)
                    elif method == "POST":
                        resp = await client.post(url, json={})
                    else:
                        continue
                    
                    if resp.status_code == 200:
                        try:
                            data = resp.json()
                            has_data = bool(data) and len(str(data)) > 50
                            
                            if has_data:
                                results["working"].append({
                                    "path": path,
                                    "category": category
                                })
                                results["by_category"][category]["working"] += 1
                            else:
                                results["working_no_data"].append({
                                    "path": path,
                                    "category": category
                                })
                                results["by_category"][category]["working"] += 1
                        except:
                            results["working_no_data"].append({
                                "path": path,
                                "category": category
                            })
                    elif resp.status_code == 404:
                        results["not_found"].append({
                            "path": path,
                            "category": category
                        })
                        results["by_category"][category]["missing"] += 1
                    else:
                        results["errors"].append({
                            "path": path,
                            "category": category,
                            "code": resp.status_code
                        })
                except Exception as e:
                    results["errors"].append({
                        "path": path,
                        "category": category,
                        "error": str(e)[:100]
                    })
        
        # Calculate summary
        total_working = len(results["working"]) + len(results["working_no_data"])
        results["summary"] = {
            "working_pct": round(total_working / len(docs) * 100, 1) if docs else 0,
            "total_working": total_working,
            "total_missing": len(results["not_found"]),
            "total_errors": len(results["errors"]),
            "missing_categories": list(set(e["category"] for e in results["not_found"]))
        }
        
        return results
    
    async def find_provider_for_category(self, category: str) -> List[Dict]:
        """
        Find providers that can fulfill a missing category.
        """
        providers = CATEGORY_PROVIDERS.get(category, [])
        available = []
        
        for provider in providers:
            # Check if provider is accessible
            try:
                async with httpx.AsyncClient(timeout=5) as client:
                    resp = await client.get(provider["base_url"])
                    if resp.status_code < 500:
                        available.append({
                            **provider,
                            "available": True,
                            "response_code": resp.status_code
                        })
            except Exception as e:
                available.append({
                    **provider,
                    "available": False,
                    "error": str(e)[:50]
                })
        
        return available
    
    async def discover_and_register_provider(self, provider_data: Dict) -> str:
        """
        Register a newly discovered provider in the database.
        Creates both data_sources and providers entries.
        """
        provider_id = provider_data.get("id")
        
        # Check if already exists
        existing = await self.db.providers.find_one({"id": provider_id})
        if existing:
            # Update is_new to False since we're re-discovering
            return "exists"
        
        now = datetime.now(timezone.utc).isoformat()
        
        # Create data source entry
        data_source = {
            "id": provider_id,
            "name": provider_data.get("name"),
            "website": provider_data.get("base_url"),
            "categories": provider_data.get("categories", []),
            "data_types": list(provider_data.get("endpoints", {}).keys()),
            "priority": "high" if provider_data.get("free") else "medium",
            "status": "active",
            "has_api": True,
            "api_key_required": not provider_data.get("free", True),
            "rate_limit": provider_data.get("rate_limit", "60/min"),
            "parser_module": f"auto_{provider_id}",
            "is_new": True,
            "discovered_at": now,
            "description": f"Auto-discovered provider for {', '.join(provider_data.get('categories', []))}"
        }
        
        await self.db.data_sources.update_one(
            {"id": provider_id},
            {"$set": data_source},
            upsert=True
        )
        
        # Create provider entry
        provider_doc = {
            "id": provider_id,
            "name": provider_data.get("name"),
            "status": "active",
            "is_new": True,
            "discovered_at": now,
            "category": provider_data.get("categories", ["other"])[0],
            "requires_api_key": not provider_data.get("free", True),
            "capabilities": provider_data.get("categories", []),
            "base_url": provider_data.get("base_url"),
            "endpoints": provider_data.get("endpoints", {}),
            "rate_limit": 60,
            "description": data_source["description"]
        }
        
        await self.db.providers.update_one(
            {"id": provider_id},
            {"$set": provider_doc},
            upsert=True
        )
        
        self._discovered_providers.append(provider_id)
        logger.info(f"Registered new provider: {provider_id}")
        
        return "registered"
    
    async def auto_fill_missing_categories(self, missing_categories: List[str]) -> Dict:
        """
        Automatically find and register providers for missing categories.
        """
        results = {
            "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
            "categories_processed": [],
            "providers_registered": [],
            "providers_unavailable": []
        }
        
        for category in missing_categories:
            providers = await self.find_provider_for_category(category)
            results["categories_processed"].append(category)
            
            for provider in providers:
                if provider.get("available"):
                    status = await self.discover_and_register_provider(provider)
                    if status == "registered":
                        results["providers_registered"].append({
                            "id": provider["id"],
                            "name": provider["name"],
                            "category": category
                        })
                else:
                    results["providers_unavailable"].append({
                        "id": provider["id"],
                        "name": provider["name"],
                        "error": provider.get("error")
                    })
        
        return results
    
    async def run_full_discovery_cycle(self, api_base_url: str) -> Dict:
        """
        Run complete discovery cycle:
        1. Audit all endpoints
        2. Find missing categories
        3. Discover and register providers
        4. Return comprehensive report
        """
        if self._running:
            return {"error": "Discovery already running"}
        
        self._running = True
        self._discovered_providers = []
        
        try:
            # Step 1: Audit
            audit = await self.run_full_audit(api_base_url)
            
            # Step 2: Find providers for missing categories
            missing_cats = audit["summary"]["missing_categories"]
            fill_result = await self.auto_fill_missing_categories(missing_cats)
            
            # Step 3: Count new sources
            new_sources = await self.db.data_sources.count_documents({"is_new": True})
            new_providers = await self.db.providers.count_documents({"is_new": True})
            
            return {
                "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
                "audit_summary": audit["summary"],
                "discovery_result": fill_result,
                "new_sources_total": new_sources,
                "new_providers_total": new_providers,
                "discovered_this_run": self._discovered_providers
            }
        finally:
            self._running = False
    
    async def get_status(self) -> Dict:
        """Get current discovery status"""
        new_sources = await self.db.data_sources.count_documents({"is_new": True})
        new_providers = await self.db.providers.count_documents({"is_new": True})
        total_sources = await self.db.data_sources.count_documents({})
        total_providers = await self.db.providers.count_documents({})
        
        # Get list of new items
        new_source_list = await self.db.data_sources.find(
            {"is_new": True},
            {"_id": 0, "id": 1, "name": 1, "discovered_at": 1}
        ).to_list(20)
        
        return {
            "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
            "new_sources": new_sources,
            "new_providers": new_providers,
            "total_sources": total_sources,
            "total_providers": total_providers,
            "is_running": self._running,
            "recently_discovered": new_source_list
        }
    
    async def mark_all_seen(self) -> int:
        """Mark all new sources as seen (remove is_new flag)"""
        result1 = await self.db.data_sources.update_many(
            {"is_new": True},
            {"$set": {"is_new": False}}
        )
        result2 = await self.db.providers.update_many(
            {"is_new": True},
            {"$set": {"is_new": False}}
        )
        return result1.modified_count + result2.modified_count


# Global instance
_full_discovery = None

def get_full_discovery(db):
    global _full_discovery
    if _full_discovery is None:
        _full_discovery = FullAutoDiscovery(db)
    return _full_discovery
