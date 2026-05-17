"""
Web Scraping for Provider Discovery
====================================
Searches the web for new crypto data providers and APIs.
"""

import asyncio
import httpx
import re
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


# Sources to search for new APIs
WEB_SOURCES = [
    {
        "id": "github_public_apis",
        "url": "https://api.github.com/repos/public-apis/public-apis/contents/README.md",
        "type": "github_readme",
        "category": "cryptocurrency"
    },
    {
        "id": "rapidapi",
        "url": "https://rapidapi.com/category/Finance",
        "type": "marketplace",
        "category": "finance"
    }
]

# Keywords to identify crypto-related APIs
CRYPTO_KEYWORDS = [
    "cryptocurrency", "crypto", "bitcoin", "ethereum", "blockchain",
    "defi", "nft", "exchange", "trading", "market data", "price",
    "coingecko", "coinmarketcap", "binance", "coinbase", "bybit"
]

# Known providers to avoid duplicates
KNOWN_PROVIDERS = [
    "coingecko", "coinmarketcap", "defillama", "dexscreener",
    "coinglass", "messari", "cryptorank", "binance", "coinbase",
    "bybit", "hyperliquid", "okx", "kraken", "geckoterminal"
]


class WebProviderDiscovery:
    """Discovers new crypto data providers from the web"""
    
    def __init__(self, db):
        self.db = db
        self._discovered = []
        
    async def _fetch_github_apis(self) -> List[Dict]:
        """Fetch APIs from public-apis GitHub repo"""
        discovered = []
        
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                # Get the cryptocurrency section
                resp = await client.get(
                    "https://raw.githubusercontent.com/public-apis/public-apis/master/README.md"
                )
                
                if resp.status_code == 200:
                    content = resp.text
                    
                    # Find cryptocurrency section
                    crypto_match = re.search(
                        r'### Cryptocurrency(.*?)### ',
                        content,
                        re.DOTALL | re.IGNORECASE
                    )
                    
                    if crypto_match:
                        crypto_section = crypto_match.group(1)
                        
                        # Parse table rows
                        # Format: | API | Description | Auth | HTTPS | CORS |
                        rows = re.findall(
                            r'\|\s*\[([^\]]+)\]\(([^\)]+)\)\s*\|\s*([^\|]+)\s*\|\s*([^\|]+)\s*\|\s*([^\|]+)\s*\|\s*([^\|]+)\s*\|',
                            crypto_section
                        )
                        
                        for row in rows:
                            name, url, description, auth, https, cors = row
                            name_lower = name.lower().replace(" ", "")
                            
                            # Skip known providers
                            if any(known in name_lower for known in KNOWN_PROVIDERS):
                                continue
                            
                            discovered.append({
                                "id": f"web_{name_lower}",
                                "name": name.strip(),
                                "website": url.strip(),
                                "description": description.strip(),
                                "api_key_required": "apikey" in auth.lower() or "key" in auth.lower(),
                                "has_https": "yes" in https.lower(),
                                "categories": ["cryptocurrency"],
                                "source": "github_public_apis",
                                "discovered_at": datetime.now(timezone.utc).isoformat()
                            })
                            
        except Exception as e:
            logger.error(f"GitHub API fetch failed: {e}")
        
        return discovered
    
    async def _search_web_for_apis(self, query: str) -> List[Dict]:
        """Search the web for crypto APIs (using DuckDuckGo-like approach)"""
        discovered = []
        
        # For now, return predefined list of potential providers
        # In production, would use web search API
        potential_providers = [
            {
                "id": "alternative_me",
                "name": "Alternative.me",
                "website": "https://alternative.me/crypto/api/",
                "description": "Fear & Greed Index, crypto prices",
                "api_key_required": False,
                "categories": ["sentiment", "market"],
                "endpoints": {
                    "fear_greed": "https://api.alternative.me/fng/"
                }
            },
            {
                "id": "blockchain_info",
                "name": "Blockchain.info",
                "website": "https://www.blockchain.com/api",
                "description": "Bitcoin blockchain data",
                "api_key_required": False,
                "categories": ["blockchain", "bitcoin"],
                "endpoints": {
                    "stats": "https://api.blockchain.info/stats"
                }
            },
            {
                "id": "etherscan",
                "name": "Etherscan",
                "website": "https://etherscan.io/apis",
                "description": "Ethereum blockchain explorer API",
                "api_key_required": True,
                "categories": ["blockchain", "ethereum"],
                "endpoints": {
                    "gas": "https://api.etherscan.io/api"
                }
            },
            {
                "id": "solscan",
                "name": "Solscan",
                "website": "https://docs.solscan.io/",
                "description": "Solana blockchain explorer API",
                "api_key_required": False,
                "categories": ["blockchain", "solana"],
                "endpoints": {}
            },
            {
                "id": "whale_alert",
                "name": "Whale Alert",
                "website": "https://whale-alert.io/",
                "description": "Large crypto transaction tracking",
                "api_key_required": True,
                "categories": ["whale", "transactions"],
                "endpoints": {}
            },
            {
                "id": "santiment",
                "name": "Santiment",
                "website": "https://santiment.net/",
                "description": "Crypto social and on-chain analytics",
                "api_key_required": True,
                "categories": ["sentiment", "onchain"],
                "endpoints": {}
            },
            {
                "id": "lunarcrush",
                "name": "LunarCrush",
                "website": "https://lunarcrush.com/",
                "description": "Social listening and analytics",
                "api_key_required": True,
                "categories": ["sentiment", "social"],
                "endpoints": {}
            },
            {
                "id": "nansen",
                "name": "Nansen",
                "website": "https://nansen.ai/",
                "description": "On-chain analytics and wallet labeling",
                "api_key_required": True,
                "categories": ["onchain", "wallets"],
                "endpoints": {}
            }
        ]
        
        for provider in potential_providers:
            provider["discovered_at"] = datetime.now(timezone.utc).isoformat()
            provider["source"] = "web_search"
        
        return potential_providers
    
    async def _verify_provider(self, provider: Dict) -> Dict:
        """Verify if a discovered provider is accessible"""
        website = provider.get("website", "")
        
        try:
            async with httpx.AsyncClient(timeout=5, follow_redirects=True) as client:
                resp = await client.get(website)
                provider["verified"] = resp.status_code < 400
                provider["status_code"] = resp.status_code
        except Exception as e:
            provider["verified"] = False
            provider["error"] = str(e)[:50]
        
        return provider
    
    async def discover_new_providers(self, verify: bool = True) -> Dict:
        """
        Run full web discovery process.
        1. Fetch from GitHub public-apis
        2. Search web for crypto APIs
        3. Optionally verify each provider
        4. Return discovered providers
        """
        all_discovered = []
        
        # Step 1: GitHub
        github_providers = await self._fetch_github_apis()
        all_discovered.extend(github_providers)
        
        # Step 2: Web search
        web_providers = await self._search_web_for_apis("crypto api")
        all_discovered.extend(web_providers)
        
        # Remove duplicates by ID
        seen_ids = set()
        unique_providers = []
        for p in all_discovered:
            if p["id"] not in seen_ids:
                seen_ids.add(p["id"])
                unique_providers.append(p)
        
        # Step 3: Verify (optional)
        if verify:
            verified_providers = []
            for provider in unique_providers[:10]:  # Limit to first 10 to avoid timeout
                verified = await self._verify_provider(provider)
                verified_providers.append(verified)
            unique_providers = verified_providers + unique_providers[10:]
        
        self._discovered = unique_providers
        
        return {
            "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
            "total_discovered": len(unique_providers),
            "from_github": len(github_providers),
            "from_web_search": len(web_providers),
            "verified_count": len([p for p in unique_providers if p.get("verified")]),
            "providers": unique_providers
        }
    
    async def add_discovered_to_registry(self, provider_ids: List[str] = None) -> Dict:
        """
        Add discovered providers to the data sources registry.
        If provider_ids is None, adds all verified providers.
        """
        if not self._discovered:
            return {"error": "No discovered providers. Run discover_new_providers first."}
        
        added = []
        skipped = []
        
        for provider in self._discovered:
            pid = provider["id"]
            
            # Filter by IDs if specified
            if provider_ids and pid not in provider_ids:
                continue
            
            # Skip unverified
            if not provider.get("verified", False):
                skipped.append({"id": pid, "reason": "not_verified"})
                continue
            
            # Check if already exists
            existing = await self.db.data_sources.find_one({"id": pid})
            if existing:
                skipped.append({"id": pid, "reason": "already_exists"})
                continue
            
            # Add to data_sources
            source_doc = {
                "id": pid,
                "name": provider["name"],
                "website": provider["website"],
                "categories": provider.get("categories", ["cryptocurrency"]),
                "data_types": list(provider.get("endpoints", {}).keys()) or ["general"],
                "priority": "medium",
                "status": "planned" if provider.get("api_key_required") else "active",
                "has_api": True,
                "api_key_required": provider.get("api_key_required", False),
                "is_new": True,
                "discovered_at": provider["discovered_at"],
                "description": provider.get("description", "")
            }
            
            await self.db.data_sources.insert_one(source_doc)
            
            # Add to providers
            provider_doc = {
                "id": pid,
                "name": provider["name"],
                "status": source_doc["status"],
                "is_new": True,
                "discovered_at": provider["discovered_at"],
                "category": provider.get("categories", ["other"])[0],
                "requires_api_key": provider.get("api_key_required", False),
                "capabilities": provider.get("categories", []),
                "base_url": provider["website"],
                "endpoints": provider.get("endpoints", {}),
                "rate_limit": 60,
                "description": provider.get("description", "")
            }
            
            await self.db.providers.insert_one(provider_doc)
            added.append(pid)
        
        return {
            "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
            "added_count": len(added),
            "added": added,
            "skipped_count": len(skipped),
            "skipped": skipped
        }


# Global instance
_web_discovery = None

def get_web_discovery(db):
    global _web_discovery
    if _web_discovery is None:
        _web_discovery = WebProviderDiscovery(db)
    return _web_discovery
