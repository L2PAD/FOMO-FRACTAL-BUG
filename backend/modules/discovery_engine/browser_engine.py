"""
Browser Discovery Engine
========================

Real Playwright-based network interception for API discovery.
Captures XHR, Fetch, and GraphQL requests from websites.

Architecture:
    UI Parse Button
    ↓
    POST /api/discovery/browser
    ↓
    Browser Discovery Engine (Playwright)
    ↓
    Capture XHR / Fetch / GraphQL
    ↓
    Save endpoint blueprint
    ↓
    Register endpoint
    ↓
    Return result to UI
"""

import asyncio
import logging
import hashlib
import json
from typing import List, Dict, Optional, Set
from datetime import datetime, timezone
from urllib.parse import urlparse, parse_qs
from dataclasses import dataclass, field, asdict

from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)


@dataclass
class CapturedRequest:
    """Captured network request"""
    url: str
    method: str
    headers: Dict[str, str] = field(default_factory=dict)
    post_data: Optional[str] = None
    resource_type: str = "unknown"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class CapturedResponse:
    """Captured network response"""
    url: str
    status: int
    headers: Dict[str, str] = field(default_factory=dict)
    body: Optional[str] = None
    body_size: int = 0
    is_json: bool = False
    latency_ms: float = 0


@dataclass
class EndpointBlueprint:
    """Complete endpoint blueprint for replay"""
    id: str
    domain: str
    url: str
    path: str
    method: str
    query_params: Dict[str, str] = field(default_factory=dict)
    headers: Dict[str, str] = field(default_factory=dict)
    cookies: Dict[str, str] = field(default_factory=dict)
    body: Optional[str] = None
    response_schema: Optional[Dict] = None
    response_sample: Optional[Dict] = None
    status: str = "discovered"
    capabilities: List[str] = field(default_factory=list)
    data_type: str = "unknown"
    requires_auth: bool = False
    auth_type: Optional[str] = None
    latency_ms: float = 0
    discovered_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_verified: Optional[str] = None
    replay_success: bool = False
    scraper_ready: bool = False


class BrowserDiscoveryEngine:
    """
    Playwright-based browser discovery engine.
    
    Capabilities:
    - Network interception (XHR, Fetch, GraphQL)
    - Human-like behavior simulation
    - Cookie/header capture
    - Response schema detection
    - Endpoint validation & replay
    """
    
    # API URL patterns to capture
    API_PATTERNS = [
        '/api/', '/v1/', '/v2/', '/v3/', 
        '/graphql', '/rest/', '/public/',
        '/data/', '/query/', '/rpc/',
        '.json', '/feed/', '/export/'
    ]
    
    # Skip these resource types
    SKIP_RESOURCES = {'image', 'stylesheet', 'font', 'media', 'manifest', 'other'}
    
    # Skip these domains (tracking, analytics)
    SKIP_DOMAINS = {
        'google-analytics.com', 'googletagmanager.com',
        'facebook.com', 'twitter.com', 'ads.',
        'cloudflare.com', 'sentry.io', 'segment.com',
        'hotjar.com', 'intercom.io', 'amplitude.com'
    }
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.endpoints_collection = db.endpoint_registry
        self.discovery_logs = db.discovery_logs
        
    async def discover(
        self,
        url: str,
        headless: bool = True,
        scroll: bool = True,
        wait_time: int = 8000,
        human_simulation: bool = True
    ) -> Dict:
        """
        Run full browser discovery on a URL.
        
        Args:
            url: Target URL (e.g., "https://defillama.com")
            headless: Run browser in headless mode
            scroll: Scroll page to trigger lazy-loaded content
            wait_time: Time to wait for network requests (ms)
            human_simulation: Simulate human behavior (mouse, scroll)
            
        Returns:
            {
                "status": "success",
                "endpoints_found": 6,
                "endpoints": [...],
                "registered": true,
                "scraper_ready": true
            }
        """
        from playwright.async_api import async_playwright
        
        # Parse domain
        parsed = urlparse(url)
        if not parsed.scheme:
            url = f"https://{url}"
            parsed = urlparse(url)
        domain = parsed.netloc.replace('www.', '')
        
        logger.info(f"[BrowserDiscovery] Starting discovery for {domain}")
        
        captured_requests: List[CapturedRequest] = []
        captured_responses: List[CapturedResponse] = []
        
        try:
            async with async_playwright() as p:
                # Launch browser
                browser = await p.chromium.launch(
                    headless=headless,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--no-sandbox',
                        '--disable-dev-shm-usage'
                    ]
                )
                
                # Create context with realistic settings
                context = await browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    locale='en-US',
                    timezone_id='America/New_York'
                )
                
                page = await context.new_page()
                
                # ═══════════════════════════════════════════════════════════════
                # NETWORK INTERCEPTION
                # ═══════════════════════════════════════════════════════════════
                
                async def handle_request(request):
                    """Capture outgoing requests"""
                    try:
                        req_url = request.url
                        resource_type = request.resource_type
                        
                        # Skip non-API resources
                        if resource_type in self.SKIP_RESOURCES:
                            return
                        
                        # Skip tracking/analytics
                        req_domain = urlparse(req_url).netloc
                        if any(skip in req_domain for skip in self.SKIP_DOMAINS):
                            return
                        
                        # Check if looks like API
                        if self._is_api_request(req_url, resource_type):
                            captured = CapturedRequest(
                                url=req_url,
                                method=request.method,
                                headers=dict(request.headers),
                                post_data=request.post_data,
                                resource_type=resource_type
                            )
                            captured_requests.append(captured)
                            logger.debug(f"[Capture] {request.method} {req_url}")
                    except Exception as e:
                        logger.debug(f"Request capture error: {e}")
                
                async def handle_response(response):
                    """Capture API responses"""
                    try:
                        resp_url = response.url
                        
                        # Only capture API responses
                        if not self._is_api_request(resp_url, response.request.resource_type):
                            return
                        
                        content_type = response.headers.get('content-type', '')
                        is_json = 'json' in content_type
                        
                        body = None
                        body_size = 0
                        
                        if is_json and response.status == 200:
                            try:
                                body_bytes = await response.body()
                                body_size = len(body_bytes)
                                if body_size < 1_000_000:  # Max 1MB
                                    body = body_bytes.decode('utf-8')
                            except:
                                pass
                        
                        captured = CapturedResponse(
                            url=resp_url,
                            status=response.status,
                            headers=dict(response.headers),
                            body=body,
                            body_size=body_size,
                            is_json=is_json
                        )
                        captured_responses.append(captured)
                        
                    except Exception as e:
                        logger.debug(f"Response capture error: {e}")
                
                page.on('request', handle_request)
                page.on('response', handle_response)
                
                # ═══════════════════════════════════════════════════════════════
                # NAVIGATE & INTERACT
                # ═══════════════════════════════════════════════════════════════
                
                try:
                    await page.goto(url, wait_until='networkidle', timeout=30000)
                except Exception as e:
                    logger.warning(f"Navigation timeout, continuing: {e}")
                
                # Wait for initial requests
                await page.wait_for_timeout(2000)
                
                # Human simulation
                if human_simulation:
                    await self._simulate_human(page)
                
                # Scroll to trigger lazy loading
                if scroll:
                    await self._scroll_page(page)
                
                # Wait for all network requests
                await page.wait_for_timeout(wait_time)
                
                # Get cookies
                cookies = await context.cookies()
                cookie_dict = {c['name']: c['value'] for c in cookies}
                
                await browser.close()
                
        except Exception as e:
            logger.error(f"[BrowserDiscovery] Error: {e}")
            return {
                "status": "error",
                "error": str(e),
                "endpoints_found": 0,
                "endpoints": [],
                "registered": False,
                "scraper_ready": False
            }
        
        # ═══════════════════════════════════════════════════════════════
        # PROCESS CAPTURED DATA
        # ═══════════════════════════════════════════════════════════════
        
        endpoints = await self._process_captured_data(
            domain, captured_requests, captured_responses, cookie_dict
        )
        
        # Save to registry
        for endpoint in endpoints:
            await self._save_endpoint(endpoint)
        
        # Determine overall status
        active_count = sum(1 for ep in endpoints if ep.status == 'active')
        
        result = {
            "status": "success",
            "domain": domain,
            "endpoints_found": len(endpoints),
            "active_endpoints": active_count,
            "endpoints": [asdict(ep) for ep in endpoints],
            "registered": len(endpoints) > 0,
            "scraper_ready": active_count > 0
        }
        
        # Log discovery
        await self._log_discovery(domain, result)
        
        logger.info(f"[BrowserDiscovery] {domain}: Found {len(endpoints)} endpoints ({active_count} active)")
        
        return result
    
    def _is_api_request(self, url: str, resource_type: str) -> bool:
        """Check if URL is likely an API request"""
        # XHR/Fetch are APIs
        if resource_type in ('xhr', 'fetch'):
            return True
        
        # Check URL patterns
        url_lower = url.lower()
        for pattern in self.API_PATTERNS:
            if pattern in url_lower:
                return True
        
        return False
    
    async def _simulate_human(self, page):
        """Simulate human-like behavior"""
        try:
            # Random mouse movement
            await page.mouse.move(500, 300)
            await page.wait_for_timeout(200)
            await page.mouse.move(700, 400)
            
            # Try to click something interactive
            try:
                # Look for common interactive elements
                selectors = [
                    'button:visible',
                    '[role="button"]:visible',
                    'a[href]:visible',
                    '[class*="tab"]:visible'
                ]
                for selector in selectors:
                    elements = await page.query_selector_all(selector)
                    if elements and len(elements) > 0:
                        # Click first non-navigation element
                        await elements[0].hover()
                        await page.wait_for_timeout(500)
                        break
            except:
                pass
                
        except Exception as e:
            logger.debug(f"Human simulation error: {e}")
    
    async def _scroll_page(self, page, steps: int = 5):
        """Scroll page to trigger lazy-loaded content"""
        try:
            for i in range(steps):
                await page.evaluate(f'window.scrollTo(0, document.body.scrollHeight * {(i+1)/steps})')
                await page.wait_for_timeout(800)
            
            # Scroll back to top
            await page.evaluate('window.scrollTo(0, 0)')
            await page.wait_for_timeout(500)
            
        except Exception as e:
            logger.debug(f"Scroll error: {e}")
    
    async def _process_captured_data(
        self,
        domain: str,
        requests: List[CapturedRequest],
        responses: List[CapturedResponse],
        cookies: Dict[str, str]
    ) -> List[EndpointBlueprint]:
        """Process captured network data into endpoint blueprints"""
        
        # Match requests to responses
        response_map = {r.url: r for r in responses}
        
        endpoints: List[EndpointBlueprint] = []
        seen_paths: Set[str] = set()
        
        for req in requests:
            parsed = urlparse(req.url)
            path = parsed.path or '/'
            
            # Deduplicate by path (ignore query params for dedup)
            if path in seen_paths:
                continue
            seen_paths.add(path)
            
            # Get matching response
            resp = response_map.get(req.url)
            
            # Parse query params
            query_params = {}
            if parsed.query:
                query_params = {k: v[0] if len(v) == 1 else v 
                              for k, v in parse_qs(parsed.query).items()}
            
            # Generate endpoint ID
            endpoint_id = hashlib.md5(f"{domain}:{path}:{req.method}".encode()).hexdigest()[:16]
            
            # Detect capabilities from path
            capabilities = self._detect_capabilities(path, req.url)
            
            # Determine status
            status = 'discovered'
            replay_success = False
            scraper_ready = False
            
            if resp:
                if resp.status == 200 and resp.is_json:
                    status = 'active'
                    replay_success = True
                    scraper_ready = True
                elif resp.status in (401, 403):
                    status = 'blocked'
                elif resp.status >= 400:
                    status = 'error'
            
            # Parse response schema
            response_schema = None
            response_sample = None
            data_type = 'unknown'
            
            if resp and resp.body:
                try:
                    data = json.loads(resp.body)
                    response_schema = self._detect_schema(data)
                    response_sample = self._get_sample(data)
                    data_type = self._detect_data_type(data, path)
                except:
                    pass
            
            # Detect auth requirement
            requires_auth = False
            auth_type = None
            
            headers = req.headers.copy()
            if 'authorization' in {k.lower() for k in headers}:
                requires_auth = True
                auth_header = headers.get('authorization', headers.get('Authorization', ''))
                if auth_header.lower().startswith('bearer'):
                    auth_type = 'bearer'
                elif auth_header.lower().startswith('basic'):
                    auth_type = 'basic'
                else:
                    auth_type = 'api_key'
            
            # Clean headers (remove sensitive ones for storage)
            safe_headers = {k: v for k, v in headers.items() 
                          if k.lower() not in ('cookie', 'authorization')}
            
            endpoint = EndpointBlueprint(
                id=endpoint_id,
                domain=domain,
                url=req.url,
                path=path,
                method=req.method,
                query_params=query_params,
                headers=safe_headers,
                cookies=cookies,
                body=req.post_data,
                response_schema=response_schema,
                response_sample=response_sample,
                status=status,
                capabilities=capabilities,
                data_type=data_type,
                requires_auth=requires_auth,
                auth_type=auth_type,
                latency_ms=resp.latency_ms if resp else 0,
                replay_success=replay_success,
                scraper_ready=scraper_ready
            )
            
            endpoints.append(endpoint)
        
        return endpoints
    
    def _detect_capabilities(self, path: str, url: str) -> List[str]:
        """Detect endpoint capabilities from path"""
        path_lower = path.lower()
        url_lower = url.lower()
        combined = path_lower + url_lower
        
        capabilities = []
        
        # Market data
        if any(x in combined for x in ['price', 'market', 'ticker', 'quote', 'ohlc']):
            capabilities.append('market_data')
        
        # DeFi
        if any(x in combined for x in ['tvl', 'protocol', 'pool', 'yield', 'defi', 'llama']):
            capabilities.append('defi_data')
        
        # DEX
        if any(x in combined for x in ['dex', 'pair', 'swap', 'liquidity', 'screener']):
            capabilities.append('dex_data')
        
        # Derivatives
        if any(x in combined for x in ['funding', 'openinterest', 'liquidation', 'futures', 'perp']):
            capabilities.append('derivatives')
        
        # Funding/VC
        if any(x in combined for x in ['fund', 'investor', 'round', 'raise', 'venture']):
            capabilities.append('funding')
        
        # News
        if any(x in combined for x in ['news', 'article', 'feed', 'rss']):
            capabilities.append('news')
        
        # Token data
        if any(x in combined for x in ['token', 'coin', 'asset', 'currency']):
            capabilities.append('token_data')
        
        # On-chain
        if any(x in combined for x in ['chain', 'address', 'transaction', 'block', 'wallet']):
            capabilities.append('onchain')
        
        if not capabilities:
            capabilities.append('unknown')
        
        return capabilities
    
    def _detect_schema(self, data) -> Dict:
        """Detect JSON schema from response data"""
        schema = {"type": "unknown", "fields": {}}
        
        if isinstance(data, list):
            schema["type"] = "array"
            if data:
                first = data[0]
                if isinstance(first, dict):
                    schema["fields"] = {k: type(v).__name__ for k, v in first.items()}
                    schema["array_length"] = len(data)
        elif isinstance(data, dict):
            schema["type"] = "object"
            schema["fields"] = {k: type(v).__name__ for k, v in data.items()}
            
            # Check for common data wrapper patterns
            for key in ['data', 'result', 'results', 'items', 'records']:
                if key in data and isinstance(data[key], list):
                    schema["data_key"] = key
                    schema["array_length"] = len(data[key])
                    if data[key]:
                        schema["item_fields"] = {k: type(v).__name__ 
                                                 for k, v in data[key][0].items() 
                                                 if isinstance(data[key][0], dict)}
                    break
        
        return schema
    
    def _get_sample(self, data, max_items: int = 3) -> Dict:
        """Get sample data for preview"""
        if isinstance(data, list):
            return {"items": data[:max_items], "total": len(data)}
        elif isinstance(data, dict):
            # Check for data wrapper
            for key in ['data', 'result', 'results', 'items', 'records']:
                if key in data and isinstance(data[key], list):
                    return {key: data[key][:max_items], "total": len(data[key])}
            return data
        return {"value": data}
    
    def _detect_data_type(self, data, path: str) -> str:
        """Detect data type from response structure"""
        path_lower = path.lower()
        
        # Check path hints
        type_hints = {
            'protocols': 'defi_protocols',
            'tokens': 'tokens',
            'coins': 'coins', 
            'pairs': 'pairs',
            'pools': 'pools',
            'funds': 'funds',
            'prices': 'prices',
            'news': 'news',
            'events': 'events'
        }
        
        for hint, data_type in type_hints.items():
            if hint in path_lower:
                return data_type
        
        # Check data structure
        if isinstance(data, list) and data:
            first = data[0] if isinstance(data[0], dict) else {}
            if 'tvl' in first or 'protocol' in first:
                return 'defi_protocols'
            if 'price' in first or 'market_cap' in first:
                return 'market_data'
            if 'pair' in first or 'dex' in first:
                return 'pairs'
        
        return 'unknown'
    
    async def _save_endpoint(self, endpoint: EndpointBlueprint):
        """Save endpoint to registry"""
        doc = asdict(endpoint)
        
        await self.endpoints_collection.update_one(
            {"id": endpoint.id},
            {"$set": doc},
            upsert=True
        )
    
    async def _log_discovery(self, domain: str, result: Dict):
        """Log discovery result"""
        log = {
            "domain": domain,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "endpoints_found": result.get("endpoints_found", 0),
            "active_endpoints": result.get("active_endpoints", 0),
            "status": result.get("status")
        }
        
        await self.discovery_logs.insert_one(log)
    
    # ═══════════════════════════════════════════════════════════════
    # API REPLAY
    # ═══════════════════════════════════════════════════════════════
    
    async def replay_endpoint(self, endpoint_id: str) -> Dict:
        """
        Replay a discovered endpoint to verify it works.
        
        This allows fetching data without browser after initial discovery.
        """
        import httpx
        
        endpoint = await self.endpoints_collection.find_one({"id": endpoint_id}, {"_id": 0})
        if not endpoint:
            return {"ok": False, "error": "Endpoint not found"}
        
        try:
            headers = endpoint.get("headers", {})
            cookies = endpoint.get("cookies", {})
            
            # Add cookies to headers
            if cookies:
                cookie_str = "; ".join(f"{k}={v}" for k, v in cookies.items())
                headers["Cookie"] = cookie_str
            
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                if endpoint["method"] == "GET":
                    response = await client.get(endpoint["url"], headers=headers)
                else:
                    response = await client.post(
                        endpoint["url"], 
                        headers=headers,
                        content=endpoint.get("body")
                    )
                
                is_json = 'json' in response.headers.get('content-type', '')
                data = None
                
                if response.status_code == 200 and is_json:
                    data = response.json()
                
                # Update endpoint status
                new_status = "active" if response.status_code == 200 else "error"
                await self.endpoints_collection.update_one(
                    {"id": endpoint_id},
                    {"$set": {
                        "status": new_status,
                        "replay_success": response.status_code == 200,
                        "last_verified": datetime.now(timezone.utc).isoformat(),
                        "latency_ms": response.elapsed.total_seconds() * 1000 if response.elapsed else 0
                    }}
                )
                
                return {
                    "ok": True,
                    "status_code": response.status_code,
                    "is_json": is_json,
                    "data": data,
                    "latency_ms": response.elapsed.total_seconds() * 1000 if response.elapsed else 0
                }
                
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    # ═══════════════════════════════════════════════════════════════
    # REGISTRY METHODS
    # ═══════════════════════════════════════════════════════════════
    
    async def get_endpoints(
        self,
        domain: str = None,
        status: str = None,
        capability: str = None,
        limit: int = 100
    ) -> List[Dict]:
        """Get endpoints from registry"""
        query = {}
        if domain:
            query["domain"] = domain
        if status:
            query["status"] = status
        if capability:
            query["capabilities"] = capability
        
        endpoints = []
        cursor = self.endpoints_collection.find(query, {"_id": 0}).limit(limit)
        async for ep in cursor:
            endpoints.append(ep)
        
        return endpoints
    
    async def get_discovery_status(self, domain: str) -> Dict:
        """Get discovery status for domain"""
        endpoints = await self.get_endpoints(domain=domain)
        
        if not endpoints:
            return {
                "domain": domain,
                "status": "NOT_DISCOVERED",
                "discovered_endpoints": 0,
                "replay_success": False,
                "parser_ready": False
            }
        
        active = sum(1 for ep in endpoints if ep.get("status") == "active")
        replay_ok = sum(1 for ep in endpoints if ep.get("replay_success"))
        
        status = "BLOCKED"
        if active > 0 and replay_ok > 0:
            status = "ACTIVE"
        elif active > 0:
            status = "PARTIAL"
        elif endpoints:
            status = "DISCOVERED"
        
        return {
            "domain": domain,
            "status": status,
            "discovered_endpoints": len(endpoints),
            "active_endpoints": active,
            "replay_success": replay_ok > 0,
            "parser_ready": active > 0,
            "endpoints": endpoints
        }
    
    async def rediscover(self, domain: str) -> Dict:
        """Force re-discovery for domain"""
        # Delete old endpoints
        await self.endpoints_collection.delete_many({"domain": domain})
        
        # Run new discovery
        url = f"https://{domain}"
        return await self.discover(url)
    
    async def get_stats(self) -> Dict:
        """Get registry statistics"""
        total = await self.endpoints_collection.count_documents({})
        active = await self.endpoints_collection.count_documents({"status": "active"})
        blocked = await self.endpoints_collection.count_documents({"status": "blocked"})
        
        # By domain
        domains_pipeline = [
            {"$group": {"_id": "$domain", "count": {"$sum": 1}, 
                       "active": {"$sum": {"$cond": [{"$eq": ["$status", "active"]}, 1, 0]}}}},
            {"$sort": {"count": -1}},
            {"$limit": 20}
        ]
        
        domains = []
        async for doc in self.endpoints_collection.aggregate(domains_pipeline):
            domains.append({
                "domain": doc["_id"],
                "total": doc["count"],
                "active": doc["active"]
            })
        
        return {
            "total_endpoints": total,
            "active_endpoints": active,
            "blocked_endpoints": blocked,
            "domains": domains
        }
