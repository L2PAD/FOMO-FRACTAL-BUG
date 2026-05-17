"""
Source Discovery Engine

Автоматически находит новые аналитические источники:
1. Сканирует seed-источники
2. Определяет capabilities (funding, unlocks, investors...)
3. Находит API endpoints
4. Регистрирует в системе

Seed Sources → Domain Scanner → Capability Detector → Endpoint Discovery → Registry
"""

import re
import asyncio
import hashlib
import logging
from typing import Dict, Any, List, Optional, Set
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from urllib.parse import urlparse

import aiohttp

logger = logging.getLogger(__name__)


# Seed queries for finding crypto analytics sites
SEED_QUERIES = [
    "crypto unlock calendar",
    "crypto funding tracker", 
    "crypto venture database",
    "token unlock schedule",
    "crypto analytics platform",
    "defi analytics",
    "crypto investor database"
]

# Known seed domains to start with
SEED_DOMAINS = [
    "dropstab.com",
    "cryptorank.io",
    "coingecko.com",
    "defillama.com",
    "messari.io",
    "rootdata.com",
    "tokenterminal.com",
    "icodrops.com",
    "icobench.com",
    "dune.com",
    "nansen.ai",
    "santiment.net",
    "tokenunlocks.app"
]

# Capability detection patterns
CAPABILITY_PATTERNS = {
    "unlocks": [
        "unlock", "vesting", "token unlock", "cliff", "release schedule"
    ],
    "funding": [
        "funding", "venture", "investment", "fundrais", "raise", "series"
    ],
    "investors": [
        "investor", "vc", "venture capital", "fund", "portfolio"
    ],
    "sales": [
        "ico", "ido", "ieo", "launchpad", "token sale", "public sale"
    ],
    "tvl": [
        "tvl", "total value locked", "defi", "protocol"
    ],
    "markets": [
        "price", "market cap", "volume", "trading"
    ],
    "airdrops": [
        "airdrop", "claim", "distribution"
    ]
}


@dataclass
class DiscoveredSource:
    """Discovered source metadata"""
    domain: str
    name: str
    capabilities: List[str]
    endpoints: List[Dict[str, Any]]
    confidence: float
    discovered_at: str
    status: str  # active, pending, blocked
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DiscoveredEndpoint:
    """Discovered API endpoint"""
    url: str
    method: str
    capability: str
    sample_keys: List[str]
    response_type: str  # json, html, unknown
    confidence: float
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SourceDiscoveryEngine:
    """
    Automatic source discovery engine.
    
    Usage:
        engine = SourceDiscoveryEngine(db)
        
        # Discover from seed domains
        await engine.discover_seeds()
        
        # Scan specific domain
        source = await engine.scan_domain("defillama.com")
    """
    
    def __init__(self, db=None):
        self.db = db
        self.session: Optional[aiohttp.ClientSession] = None
        self.discovered_domains: Set[str] = set()
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
            )
        return self.session
    
    async def close(self):
        """Close session"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    # ═══════════════════════════════════════════════════════════════
    # Domain Scanning
    # ═══════════════════════════════════════════════════════════════
    
    async def fetch_page(self, url: str) -> Optional[str]:
        """Fetch page content"""
        try:
            session = await self._get_session()
            async with session.get(url) as response:
                if response.status == 200:
                    return await response.text()
        except Exception as e:
            logger.debug(f"Failed to fetch {url}: {e}")
        return None
    
    async def detect_capabilities(self, domain: str) -> List[str]:
        """Detect what data types a domain provides"""
        url = f"https://{domain}"
        html = await self.fetch_page(url)
        
        if not html:
            return []
        
        html_lower = html.lower()
        capabilities = []
        
        for cap, keywords in CAPABILITY_PATTERNS.items():
            for keyword in keywords:
                if keyword in html_lower:
                    if cap not in capabilities:
                        capabilities.append(cap)
                    break
        
        return capabilities
    
    async def find_api_endpoints(self, domain: str) -> List[DiscoveredEndpoint]:
        """Find API endpoints from page source"""
        url = f"https://{domain}"
        html = await self.fetch_page(url)
        
        if not html:
            return []
        
        endpoints = []
        
        # Find API URLs in JavaScript
        api_patterns = [
            r'["\']https?://[^"\']*api[^"\']*["\']',
            r'["\']https?://[^"\']*\.json["\']',
            r'["\']\/api\/[^"\']*["\']',
            r'fetch\(["\']([^"\']+)["\']',
            r'axios\.[a-z]+\(["\']([^"\']+)["\']'
        ]
        
        found_urls = set()
        for pattern in api_patterns:
            matches = re.findall(pattern, html, re.IGNORECASE)
            for match in matches:
                # Clean up the URL
                clean_url = match.strip('"\'')
                if clean_url.startswith('/'):
                    clean_url = f"https://{domain}{clean_url}"
                if 'api' in clean_url.lower() or '.json' in clean_url.lower():
                    found_urls.add(clean_url)
        
        # Test each endpoint
        for ep_url in list(found_urls)[:20]:  # Limit to 20
            endpoint = await self._test_endpoint(ep_url, domain)
            if endpoint:
                endpoints.append(endpoint)
        
        return endpoints
    
    async def _test_endpoint(self, url: str, domain: str) -> Optional[DiscoveredEndpoint]:
        """Test if endpoint returns valid data"""
        try:
            session = await self._get_session()
            async with session.get(url) as response:
                if response.status != 200:
                    return None
                
                content_type = response.headers.get('content-type', '')
                
                if 'json' in content_type:
                    data = await response.json()
                    
                    # Analyze response
                    sample_keys = []
                    if isinstance(data, dict):
                        sample_keys = list(data.keys())[:10]
                    elif isinstance(data, list) and data and isinstance(data[0], dict):
                        sample_keys = list(data[0].keys())[:10]
                    
                    # Detect capability from keys
                    capability = self._detect_capability_from_keys(sample_keys)
                    
                    return DiscoveredEndpoint(
                        url=url,
                        method="GET",
                        capability=capability,
                        sample_keys=sample_keys,
                        response_type="json",
                        confidence=0.8 if capability != "unknown" else 0.5
                    )
        except Exception as e:
            logger.debug(f"Endpoint test failed for {url}: {e}")
        
        return None
    
    def _detect_capability_from_keys(self, keys: List[str]) -> str:
        """Detect capability from JSON keys"""
        keys_lower = [k.lower() for k in keys]
        keys_str = " ".join(keys_lower)
        
        if any(k in keys_str for k in ["unlock", "vesting", "cliff"]):
            return "unlocks"
        if any(k in keys_str for k in ["funding", "raise", "investor", "round"]):
            return "funding"
        if any(k in keys_str for k in ["tvl", "protocol", "chain"]):
            return "tvl"
        if any(k in keys_str for k in ["price", "market", "volume"]):
            return "markets"
        if any(k in keys_str for k in ["ico", "ido", "sale"]):
            return "sales"
        
        return "unknown"
    
    # ═══════════════════════════════════════════════════════════════
    # Full Source Scan
    # ═══════════════════════════════════════════════════════════════
    
    async def scan_domain(self, domain: str) -> Optional[DiscoveredSource]:
        """
        Full scan of a domain.
        Returns DiscoveredSource with capabilities and endpoints.
        """
        logger.info(f"[Discovery] Scanning domain: {domain}")
        
        # Detect capabilities
        capabilities = await self.detect_capabilities(domain)
        
        if not capabilities:
            logger.info(f"[Discovery] No capabilities found for {domain}")
            return None
        
        # Find endpoints
        endpoints = await self.find_api_endpoints(domain)
        
        # Calculate confidence
        confidence = min(0.95, 0.5 + len(capabilities) * 0.1 + len(endpoints) * 0.05)
        
        source = DiscoveredSource(
            domain=domain,
            name=domain.split('.')[0].capitalize(),
            capabilities=capabilities,
            endpoints=[ep.to_dict() for ep in endpoints],
            confidence=confidence,
            discovered_at=datetime.now(timezone.utc).isoformat(),
            status="pending"
        )
        
        # Save to database
        if self.db is not None:
            await self._save_source(source)
        
        self.discovered_domains.add(domain)
        
        logger.info(f"[Discovery] Found {domain}: caps={capabilities}, endpoints={len(endpoints)}")
        
        return source
    
    async def _save_source(self, source: DiscoveredSource):
        """Save discovered source to database"""
        if self.db is None:
            return
        try:
            await self.db.intel_discovered_sources.update_one(
                {"domain": source.domain},
                {"$set": source.to_dict()},
                upsert=True
            )
        except Exception as e:
            logger.error(f"Failed to save source: {e}")
    
    # ═══════════════════════════════════════════════════════════════
    # Batch Discovery
    # ═══════════════════════════════════════════════════════════════
    
    async def discover_seeds(self) -> Dict[str, Any]:
        """Discover all seed domains"""
        results = {
            "scanned": 0,
            "discovered": 0,
            "sources": [],
            "errors": []
        }
        
        for domain in SEED_DOMAINS:
            try:
                results["scanned"] += 1
                source = await self.scan_domain(domain)
                
                if source:
                    results["discovered"] += 1
                    results["sources"].append({
                        "domain": source.domain,
                        "capabilities": source.capabilities,
                        "endpoints": len(source.endpoints)
                    })
                
                # Rate limit
                await asyncio.sleep(2)
                
            except Exception as e:
                results["errors"].append(f"{domain}: {str(e)}")
        
        return results
    
    async def get_sources_with_capability(self, capability: str) -> List[Dict[str, Any]]:
        """Get all sources that have a specific capability"""
        if self.db is None:
            return []
        
        cursor = self.db.intel_discovered_sources.find({
            "capabilities": capability,
            "status": {"$in": ["active", "pending"]}
        })
        
        return await cursor.to_list(100)
    
    async def get_all_sources(self) -> List[Dict[str, Any]]:
        """Get all discovered sources"""
        if self.db is None:
            return []
        
        cursor = self.db.intel_discovered_sources.find({})
        sources = await cursor.to_list(200)
        
        # Remove MongoDB _id
        for s in sources:
            s.pop("_id", None)
        
        return sources
    
    async def activate_source(self, domain: str) -> Dict[str, Any]:
        """Activate a discovered source for regular scraping"""
        if self.db is None:
            return {"error": "No database"}
        
        result = await self.db.intel_discovered_sources.update_one(
            {"domain": domain},
            {"$set": {"status": "active"}}
        )
        
        return {
            "domain": domain,
            "activated": result.modified_count > 0
        }
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get discovery statistics"""
        if self.db is None:
            return {"discovered": len(self.discovered_domains)}
        
        total = await self.db.intel_discovered_sources.count_documents({})
        active = await self.db.intel_discovered_sources.count_documents({"status": "active"})
        
        # Count by capability
        pipeline = [
            {"$unwind": "$capabilities"},
            {"$group": {"_id": "$capabilities", "count": {"$sum": 1}}}
        ]
        cursor = self.db.intel_discovered_sources.aggregate(pipeline)
        by_capability = {doc["_id"]: doc["count"] async for doc in cursor}
        
        return {
            "total_sources": total,
            "active_sources": active,
            "by_capability": by_capability,
            "seed_domains": len(SEED_DOMAINS)
        }


# Singleton
discovery_engine: Optional[SourceDiscoveryEngine] = None


def init_discovery_engine(db) -> SourceDiscoveryEngine:
    """Initialize discovery engine"""
    global discovery_engine
    discovery_engine = SourceDiscoveryEngine(db)
    return discovery_engine
