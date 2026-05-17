"""
Discovery Engine
================

Core engine for automatic API discovery.
Uses network capture and pattern detection.
"""

import re
import asyncio
import logging
import hashlib
from typing import List, Dict, Optional, Set
from datetime import datetime, timezone
from urllib.parse import urlparse, urljoin

from motor.motor_asyncio import AsyncIOMotorDatabase

from .models import (
    DiscoveredEndpoint, DiscoveryJob, DiscoveryJobCreate,
    EndpointStatus, CapabilityType, SEED_DOMAINS
)
from .validator import EndpointValidator
from .schema_detector import SchemaDetector

logger = logging.getLogger(__name__)


# API endpoint patterns to detect
API_PATTERNS = [
    r'/api/',
    r'/v[0-9]+/',
    r'/graphql',
    r'/rest/',
    r'/public/',
    r'/data/',
    r'\.json$',
]

# Subdomains to check
API_SUBDOMAINS = ["api", "data", "public", "developer", "docs"]

# Known API domain mappings (domain -> actual API endpoints)
KNOWN_API_MAPPINGS = {
    "defillama.com": {
        "api_domain": "api.llama.fi",
        "endpoints": [
            {"path": "/protocols", "capability": "defi_data", "description": "All DeFi protocols with TVL"},
            {"path": "/tvl/{protocol}", "capability": "defi_data", "description": "Historical TVL for protocol"},
            {"path": "/charts", "capability": "defi_data", "description": "Historical DeFi TVL"},
            {"path": "/yields/pools", "capability": "defi_data", "description": "Yield farming pools"},
            {"path": "/stablecoins", "capability": "defi_data", "description": "Stablecoin data"},
        ]
    },
    "coingecko.com": {
        "api_domain": "api.coingecko.com",
        "endpoints": [
            {"path": "/api/v3/coins/list", "capability": "market_data", "description": "All coins list"},
            {"path": "/api/v3/coins/markets", "capability": "market_data", "description": "Market data for coins"},
            {"path": "/api/v3/simple/price", "capability": "market_data", "description": "Simple price for coins"},
        ]
    },
    "coinmarketcap.com": {
        "api_domain": "pro-api.coinmarketcap.com",
        "endpoints": [
            {"path": "/v1/cryptocurrency/listings/latest", "capability": "market_data", "description": "Latest listings"},
            {"path": "/v1/cryptocurrency/quotes/latest", "capability": "market_data", "description": "Price quotes"},
        ],
        "requires_key": True
    },
    "dexscreener.com": {
        "api_domain": "api.dexscreener.com",
        "endpoints": [
            {"path": "/latest/dex/tokens/{address}", "capability": "dex_data", "description": "Token data"},
            {"path": "/latest/dex/pairs/{chain}/{address}", "capability": "dex_data", "description": "Pair data"},
            {"path": "/latest/dex/search", "capability": "dex_data", "description": "Search pairs"},
        ]
    },
    "cryptorank.io": {
        "api_domain": "api.cryptorank.io",
        "endpoints": [
            {"path": "/v1/currencies", "capability": "market_data", "description": "Currencies list"},
            {"path": "/v1/funds", "capability": "funding", "description": "VC funds list"},
        ],
        "requires_key": True
    },
    "coinglass.com": {
        "api_domain": "open-api.coinglass.com",
        "endpoints": [
            {"path": "/public/v2/funding", "capability": "derivatives", "description": "Funding rates"},
            {"path": "/public/v2/open_interest", "capability": "derivatives", "description": "Open interest"},
            {"path": "/public/v2/liquidation", "capability": "derivatives", "description": "Liquidations"},
        ]
    },
    "messari.io": {
        "api_domain": "data.messari.io",
        "endpoints": [
            {"path": "/api/v2/assets", "capability": "market_data", "description": "All assets"},
            {"path": "/api/v1/news", "capability": "news", "description": "News articles"},
        ]
    },
    "tokenterminal.com": {
        "api_domain": "api.tokenterminal.com",
        "endpoints": [
            {"path": "/v2/projects", "capability": "defi_data", "description": "Protocol metrics"},
        ],
        "requires_key": True
    },
    "geckoterminal.com": {
        "api_domain": "api.geckoterminal.com",
        "endpoints": [
            {"path": "/api/v2/networks", "capability": "dex_data", "description": "Supported networks"},
            {"path": "/api/v2/simple/networks/{network}/token_price/{address}", "capability": "dex_data", "description": "Token price"},
        ]
    },
}


class DiscoveryEngine:
    """
    API Discovery Engine.
    Automatically finds and registers API endpoints.
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.endpoints = db.discovered_endpoints
        self.jobs = db.discovery_jobs
        self.validator = EndpointValidator()
        self.schema_detector = SchemaDetector()
        
        # Patterns
        self.api_patterns = [re.compile(p, re.IGNORECASE) for p in API_PATTERNS]
    
    # ═══════════════════════════════════════════════════════════════
    # DISCOVERY JOBS
    # ═══════════════════════════════════════════════════════════════
    
    async def create_job(self, data: DiscoveryJobCreate) -> dict:
        """Create discovery job for domain"""
        now = datetime.now(timezone.utc)
        
        job_id = hashlib.md5(f"{data.domain}:{now.timestamp()}".encode()).hexdigest()[:12]
        
        doc = {
            "id": job_id,
            "domain": data.domain.lower().strip(),
            "scan_depth": data.scan_depth,
            "network_capture": data.network_capture,
            "check_subdomains": data.check_subdomains,
            "status": "pending",
            "progress": 0.0,
            "endpoints_found": 0,
            "apis_detected": 0,
            "errors": [],
            "created_at": now.isoformat(),
            "started_at": None,
            "completed_at": None
        }
        
        await self.jobs.insert_one(doc)
        doc.pop("_id", None)
        
        return {"ok": True, "job_id": job_id, "job": doc}
    
    async def get_job(self, job_id: str) -> Optional[dict]:
        """Get job by ID"""
        job = await self.jobs.find_one({"id": job_id})
        if job:
            job.pop("_id", None)
        return job
    
    async def run_job(self, job_id: str) -> dict:
        """Execute discovery job"""
        job = await self.get_job(job_id)
        if not job:
            return {"ok": False, "error": "Job not found"}
        
        # Update status
        await self.jobs.update_one(
            {"id": job_id},
            {"$set": {
                "status": "running",
                "started_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        
        try:
            domain = job["domain"]
            results = await self.discover_domain(domain, job.get("check_subdomains", []))
            
            # Update job with results
            await self.jobs.update_one(
                {"id": job_id},
                {"$set": {
                    "status": "completed",
                    "progress": 100.0,
                    "endpoints_found": len(results["endpoints"]),
                    "apis_detected": len(results["apis"]),
                    "completed_at": datetime.now(timezone.utc).isoformat()
                }}
            )
            
            return {"ok": True, "job_id": job_id, "results": results}
            
        except Exception as e:
            await self.jobs.update_one(
                {"id": job_id},
                {"$set": {
                    "status": "failed",
                    "errors": [str(e)],
                    "completed_at": datetime.now(timezone.utc).isoformat()
                }}
            )
            return {"ok": False, "error": str(e)}
    
    # ═══════════════════════════════════════════════════════════════
    # DOMAIN DISCOVERY
    # ═══════════════════════════════════════════════════════════════
    
    async def discover_domain(
        self, 
        domain: str,
        check_subdomains: List[str] = None
    ) -> dict:
        """
        Discover API endpoints for a domain.
        
        Args:
            domain: Target domain (e.g., "defillama.com")
            check_subdomains: Subdomains to check (e.g., ["api", "docs"])
            
        Returns:
            {
                "domain": str,
                "endpoints": List[dict],
                "apis": List[str],
                "status": str
            }
        """
        if check_subdomains is None:
            check_subdomains = API_SUBDOMAINS
        
        # Parse domain
        if not domain.startswith("http"):
            domain = domain.lower().strip()
        else:
            parsed = urlparse(domain)
            domain = parsed.netloc
        
        # Remove www. prefix if present
        if domain.startswith("www."):
            domain = domain[4:]
        
        endpoints_found = []
        apis_detected = set()
        
        # ═══════════════════════════════════════════════════════════════
        # CHECK KNOWN API MAPPINGS FIRST
        # ═══════════════════════════════════════════════════════════════
        if domain in KNOWN_API_MAPPINGS:
            mapping = KNOWN_API_MAPPINGS[domain]
            api_domain = mapping["api_domain"]
            requires_key = mapping.get("requires_key", False)
            
            logger.info(f"Using known API mapping for {domain} -> {api_domain}")
            
            for ep_info in mapping["endpoints"]:
                path = ep_info["path"]
                # Skip templated paths for now, use base path
                if "{" in path:
                    base_path = path.split("{")[0].rstrip("/")
                    if not base_path:
                        base_path = "/"
                else:
                    base_path = path
                
                url = f"https://{api_domain}{base_path}"
                endpoint = await self._probe_endpoint(url, domain)
                
                if endpoint:
                    # Override with known info
                    endpoint.capabilities = [CapabilityType(ep_info.get("capability", "unknown"))]
                    endpoint.requires_auth = requires_key
                    if requires_key:
                        endpoint.auth_type = "api_key"
                    
                    # If blocked due to auth but known to work, mark as discovered
                    if endpoint.status == EndpointStatus.BLOCKED and requires_key:
                        endpoint.status = EndpointStatus.DISCOVERED
                    
                    endpoints_found.append(endpoint)
                    apis_detected.add(f"https://{api_domain}")
            
            # Also probe the API domain root
            root_endpoint = await self._probe_endpoint(f"https://{api_domain}", domain)
            if root_endpoint and root_endpoint.status != EndpointStatus.DEAD:
                if root_endpoint not in endpoints_found:
                    endpoints_found.append(root_endpoint)
        
        # ═══════════════════════════════════════════════════════════════
        # GENERIC DISCOVERY FOR UNKNOWN DOMAINS
        # ═══════════════════════════════════════════════════════════════
        if not endpoints_found:
            # 1. Try common API subdomains
            for subdomain in check_subdomains:
                api_base = f"https://{subdomain}.{domain}"
                
                # Common endpoints to probe
                probe_paths = [
                    "/",
                    "/v1",
                    "/v2",
                    "/api",
                    "/health",
                    "/status",
                    "/info",
                ]
                
                for path in probe_paths:
                    url = f"{api_base}{path}"
                    endpoint = await self._probe_endpoint(url, domain)
                    if endpoint and endpoint.status != EndpointStatus.DEAD:
                        endpoints_found.append(endpoint)
                        apis_detected.add(api_base)
            
            # 2. Try main domain with API paths
            main_probes = [
                f"https://{domain}/api",
                f"https://{domain}/api/v1",
                f"https://{domain}/v1",
                f"https://www.{domain}/api",
            ]
            
            for url in main_probes:
                endpoint = await self._probe_endpoint(url, domain)
                if endpoint and endpoint.status != EndpointStatus.DEAD:
                    endpoints_found.append(endpoint)
                    apis_detected.add(urlparse(url).scheme + "://" + urlparse(url).netloc)
        
        # 3. Save discovered endpoints
        for endpoint in endpoints_found:
            await self._save_endpoint(endpoint)
        
        return {
            "domain": domain,
            "endpoints": [self._endpoint_to_dict(ep) for ep in endpoints_found],
            "apis": list(apis_detected),
            "status": "completed"
        }
    
    async def _probe_endpoint(self, url: str, domain: str) -> Optional[DiscoveredEndpoint]:
        """Probe a URL to check if it's a valid API endpoint"""
        import httpx
        
        try:
            async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                response = await client.get(url)
                
                # Check if JSON response
                content_type = response.headers.get("content-type", "")
                is_json = "json" in content_type
                
                if response.status_code < 400 or response.status_code in [401, 403]:
                    parsed = urlparse(url)
                    
                    endpoint = DiscoveredEndpoint(
                        id=hashlib.md5(url.encode()).hexdigest()[:16],
                        domain=domain,
                        url=url,
                        path=parsed.path or "/",
                        method="GET",
                        discovery_method="subdomain_probe",
                        detected_patterns=self._find_patterns(url),
                        status=EndpointStatus.DISCOVERED if response.status_code < 400 else EndpointStatus.BLOCKED,
                        latency_ms=response.elapsed.total_seconds() * 1000 if response.elapsed else None,
                        requires_auth=response.status_code in [401, 403]
                    )
                    
                    # Try to detect schema if JSON
                    if is_json and response.status_code == 200:
                        try:
                            data = response.json()
                            schema = self.schema_detector.detect_from_response(data)
                            endpoint.response_schema = schema.fields
                            endpoint.capabilities = [schema.detected_capability]
                            endpoint.data_quality_score = schema.confidence
                            endpoint.status = EndpointStatus.ACTIVE
                        except:
                            pass
                    
                    return endpoint
                    
        except Exception as e:
            logger.debug(f"Probe failed for {url}: {e}")
        
        return None
    
    def _find_patterns(self, url: str) -> List[str]:
        """Find API patterns in URL"""
        patterns = []
        for pattern in self.api_patterns:
            if pattern.search(url):
                patterns.append(pattern.pattern)
        return patterns
    
    async def _save_endpoint(self, endpoint: DiscoveredEndpoint) -> None:
        """Save endpoint to database"""
        doc = self._endpoint_to_dict(endpoint)
        
        # Upsert
        await self.endpoints.update_one(
            {"id": endpoint.id},
            {"$set": doc},
            upsert=True
        )
    
    def _endpoint_to_dict(self, endpoint: DiscoveredEndpoint) -> dict:
        """Convert endpoint to dict for storage"""
        return {
            "id": endpoint.id,
            "domain": endpoint.domain,
            "url": endpoint.url,
            "path": endpoint.path,
            "method": endpoint.method,
            "discovery_method": endpoint.discovery_method,
            "detected_patterns": endpoint.detected_patterns,
            "response_schema": endpoint.response_schema,
            "capabilities": [c.value if isinstance(c, CapabilityType) else c for c in endpoint.capabilities],
            "status": endpoint.status.value if isinstance(endpoint.status, EndpointStatus) else endpoint.status,
            "latency_ms": endpoint.latency_ms,
            "success_rate": endpoint.success_rate,
            "stability_score": endpoint.stability_score,
            "data_quality_score": endpoint.data_quality_score,
            "overall_score": endpoint.overall_score,
            "requires_auth": endpoint.requires_auth,
            "auth_type": endpoint.auth_type,
            "provider_id": endpoint.provider_id,
            "discovered_at": endpoint.discovered_at.isoformat() if endpoint.discovered_at else None,
            "last_checked": endpoint.last_checked.isoformat() if endpoint.last_checked else None,
            "last_success": endpoint.last_success.isoformat() if endpoint.last_success else None
        }
    
    # ═══════════════════════════════════════════════════════════════
    # ENDPOINT MANAGEMENT
    # ═══════════════════════════════════════════════════════════════
    
    async def get_endpoints(
        self,
        domain: Optional[str] = None,
        status: Optional[str] = None,
        capability: Optional[str] = None,
        limit: int = 100
    ) -> List[dict]:
        """Get discovered endpoints with filters"""
        query = {}
        if domain:
            query["domain"] = domain
        if status:
            query["status"] = status
        if capability:
            query["capabilities"] = capability
        
        endpoints = []
        cursor = self.endpoints.find(query, {"_id": 0}).sort("overall_score", -1).limit(limit)
        async for ep in cursor:
            endpoints.append(ep)
        
        return endpoints
    
    async def get_endpoint(self, endpoint_id: str) -> Optional[dict]:
        """Get single endpoint by ID"""
        ep = await self.endpoints.find_one({"id": endpoint_id}, {"_id": 0})
        return ep
    
    async def validate_endpoints(self, domain: Optional[str] = None) -> dict:
        """Validate all endpoints for a domain"""
        query = {"status": {"$nin": ["dead", "blocked"]}}
        if domain:
            query["domain"] = domain
        
        endpoints = []
        cursor = self.endpoints.find(query, {"_id": 0})
        async for ep in cursor:
            # Convert to model
            endpoint = DiscoveredEndpoint(**ep)
            endpoints.append(endpoint)
        
        # Validate
        validated = await self.validator.batch_validate(endpoints)
        
        # Save results
        for endpoint in validated:
            await self._save_endpoint(endpoint)
        
        active = sum(1 for ep in validated if ep.status == EndpointStatus.ACTIVE)
        
        return {
            "total": len(validated),
            "active": active,
            "degraded": sum(1 for ep in validated if ep.status == EndpointStatus.DEGRADED),
            "dead": sum(1 for ep in validated if ep.status == EndpointStatus.DEAD)
        }
    
    # ═══════════════════════════════════════════════════════════════
    # AUTO PROVIDER REGISTRATION
    # ═══════════════════════════════════════════════════════════════
    
    async def register_discovered_provider(
        self, 
        endpoint_id: str,
        provider_name: str
    ) -> dict:
        """
        Register a discovered endpoint as a provider.
        """
        endpoint = await self.get_endpoint(endpoint_id)
        if not endpoint:
            return {"ok": False, "error": "Endpoint not found"}
        
        # Build provider config
        provider_id = provider_name.lower().replace(" ", "_")
        
        parsed = urlparse(endpoint["url"])
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        
        # Determine auth type
        auth_type = "none"
        if endpoint.get("requires_auth"):
            auth_type = endpoint.get("auth_type", "api_key")
        
        # Determine category from capability
        capability = endpoint.get("capabilities", ["unknown"])[0]
        category_map = {
            "market_data": "market_data",
            "defi_data": "defi",
            "dex_data": "dex",
            "derivatives": "derivatives",
            "news": "news",
            "onchain": "onchain"
        }
        category = category_map.get(capability, "market_data")
        
        # Create provider
        from modules.provider_gateway.registry import ProviderRegistry
        registry = ProviderRegistry(self.db)
        
        from modules.provider_gateway.models import ProviderCreate, AuthType, ProviderCategory
        
        provider_data = ProviderCreate(
            id=provider_id,
            name=provider_name,
            endpoint=base_url,
            auth_type=AuthType(auth_type),
            requires_api_key=(auth_type != "none"),
            category=ProviderCategory(category),
            capabilities=[capability],
            rate_limit=60,
            description=f"Auto-discovered from {endpoint['domain']}"
        )
        
        result = await registry.create_provider(provider_data)
        
        if result["ok"]:
            # Update endpoint with provider link
            await self.endpoints.update_one(
                {"id": endpoint_id},
                {"$set": {"provider_id": provider_id}}
            )
        
        return result
    
    # ═══════════════════════════════════════════════════════════════
    # SEED DOMAINS
    # ═══════════════════════════════════════════════════════════════
    
    async def get_seed_domains(self) -> dict:
        """Get seed domains list"""
        return SEED_DOMAINS
    
    async def discover_seed_domain(self, category: str, domain: str) -> dict:
        """Discover single seed domain"""
        if category not in SEED_DOMAINS:
            return {"ok": False, "error": f"Unknown category: {category}"}
        
        if domain not in SEED_DOMAINS[category]:
            return {"ok": False, "error": f"Domain {domain} not in {category} seeds"}
        
        results = await self.discover_domain(domain)
        return {"ok": True, "domain": domain, "category": category, "results": results}
    
    async def discover_all_seeds(self) -> dict:
        """Discover all seed domains"""
        results = {}
        
        for category, domains in SEED_DOMAINS.items():
            results[category] = []
            for domain in domains:
                try:
                    discovery = await self.discover_domain(domain)
                    results[category].append({
                        "domain": domain,
                        "endpoints_found": len(discovery["endpoints"]),
                        "apis_detected": len(discovery["apis"])
                    })
                except Exception as e:
                    results[category].append({
                        "domain": domain,
                        "error": str(e)
                    })
        
        return results
    
    # ═══════════════════════════════════════════════════════════════
    # STATISTICS
    # ═══════════════════════════════════════════════════════════════
    
    async def get_stats(self) -> dict:
        """Get discovery statistics"""
        total = await self.endpoints.count_documents({})
        active = await self.endpoints.count_documents({"status": "active"})
        discovered = await self.endpoints.count_documents({"status": "discovered"})
        
        # By domain
        domains_pipeline = [
            {"$group": {"_id": "$domain", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10}
        ]
        domains = {}
        async for doc in self.endpoints.aggregate(domains_pipeline):
            domains[doc["_id"]] = doc["count"]
        
        # By capability
        capabilities_pipeline = [
            {"$unwind": "$capabilities"},
            {"$group": {"_id": "$capabilities", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        capabilities = {}
        async for doc in self.endpoints.aggregate(capabilities_pipeline):
            capabilities[doc["_id"]] = doc["count"]
        
        return {
            "total_endpoints": total,
            "active_endpoints": active,
            "discovered_endpoints": discovered,
            "endpoints_by_domain": domains,
            "endpoints_by_capability": capabilities
        }
