"""
CoinGecko Multi-Proxy Key Manager
=================================
Manages CoinGecko API access with:
- Multiple API keys per proxy
- Automatic failover when key hits rate limit
- Parallel requests through different proxies
- Key rotation within same proxy

Rate limits:
- Demo API with key: 30 req/min per key
- Demo API without key: 10-30 req/min per IP
- Pro API: 500 req/min per key

Strategy:
1. Each proxy can have multiple keys bound to it
2. When one key hits 429, switch to next key on same proxy
3. If all keys on proxy exhausted, mark proxy as rate-limited
4. Auto-switch to next proxy
5. Parallel work: proxy1 + proxy2 can work simultaneously
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
import httpx

logger = logging.getLogger(__name__)


@dataclass
class KeyStatus:
    """Status tracking for a single API key"""
    key_id: str
    api_key: str
    proxy_id: Optional[str]
    is_pro: bool = False
    requests_this_minute: int = 0
    minute_window_start: Optional[datetime] = None
    is_rate_limited: bool = False
    rate_limit_until: Optional[datetime] = None
    consecutive_errors: int = 0
    last_error: Optional[str] = None
    last_success: Optional[datetime] = None
    total_requests: int = 0
    
    @property
    def rate_limit(self) -> int:
        return 500 if self.is_pro else 30
    
    def reset_minute_window(self):
        self.requests_this_minute = 0
        self.minute_window_start = datetime.now(timezone.utc)
    
    def is_available(self) -> bool:
        """Check if key is available for use"""
        now = datetime.now(timezone.utc)
        
        # Check cooldown expired
        if self.rate_limit_until and now > self.rate_limit_until:
            self.is_rate_limited = False
            self.rate_limit_until = None
            logger.info(f"[CoinGeckoManager] Key {self.key_id[:8]} cooldown expired, available again")
        
        if self.is_rate_limited:
            return False
        
        # Check minute window
        if not self.minute_window_start or (now - self.minute_window_start).total_seconds() >= 60:
            self.reset_minute_window()
        
        return self.requests_this_minute < self.rate_limit
    
    def record_request(self):
        self.requests_this_minute += 1
        self.total_requests += 1
    
    def record_rate_limit(self, cooldown_seconds: int = 60):
        """Mark key as rate limited"""
        self.is_rate_limited = True
        self.rate_limit_until = datetime.now(timezone.utc) + timedelta(seconds=cooldown_seconds)
        logger.warning(f"[CoinGeckoManager] Key {self.key_id[:8]} rate limited until {self.rate_limit_until}")
    
    def record_success(self):
        self.consecutive_errors = 0
        self.last_error = None
        self.last_success = datetime.now(timezone.utc)
    
    def record_error(self, error: str):
        self.consecutive_errors += 1
        self.last_error = error


@dataclass 
class ProxySlot:
    """Proxy with its assigned keys"""
    proxy_id: str
    server: str
    proxy_url: Optional[str]  # Full URL with auth
    priority: int
    keys: List[KeyStatus] = field(default_factory=list)
    current_key_idx: int = 0
    # Keyless mode stats
    keyless_requests: int = 0
    keyless_rate_limited: bool = False
    keyless_rate_limit_until: Optional[datetime] = None
    
    def get_available_key(self) -> Optional[KeyStatus]:
        """Get next available key for this proxy"""
        if not self.keys:
            return None
        
        # Try each key starting from current
        for i in range(len(self.keys)):
            idx = (self.current_key_idx + i) % len(self.keys)
            key = self.keys[idx]
            if key.is_available():
                self.current_key_idx = idx
                return key
        
        return None
    
    def is_keyless_available(self) -> bool:
        """Check if can use without key (IP-based limit)"""
        now = datetime.now(timezone.utc)
        if self.keyless_rate_limit_until and now > self.keyless_rate_limit_until:
            self.keyless_rate_limited = False
            self.keyless_rate_limit_until = None
        return not self.keyless_rate_limited
    
    def record_keyless_rate_limit(self):
        self.keyless_rate_limited = True
        self.keyless_rate_limit_until = datetime.now(timezone.utc) + timedelta(seconds=60)


class CoinGeckoKeyManager:
    """
    Manages CoinGecko API access with multiple proxies and keys.
    
    Architecture:
    - Proxy 1 → [Key A, Key B] → if all exhausted → keyless mode
    - Proxy 2 → [Key C, Key D] → if all exhausted → keyless mode
    
    When proxy+keys exhausted → switch to next proxy
    Both proxies can work in parallel for different requests
    """
    
    BASE_URL = "https://api.coingecko.com/api/v3"
    PRO_URL = "https://pro-api.coingecko.com/api/v3"
    
    def __init__(self, db):
        self.db = db
        self._proxy_slots: Dict[str, ProxySlot] = {}
        self._direct_slot: Optional[ProxySlot] = None  # For direct connection
        self._lock = asyncio.Lock()
        self._initialized = False
    
    async def initialize(self):
        """Load proxies and keys from database"""
        if self._initialized:
            return
        
        try:
            # Load proxies
            from modules.intel.common.proxy_manager import proxy_manager
            await proxy_manager.load_from_db()
            status = proxy_manager.get_status()
            
            for proxy in sorted(status.get('proxies', []), key=lambda p: p.get('priority', 99)):
                if not proxy.get('enabled'):
                    continue
                
                proxy_id = str(proxy['id'])
                
                # Get full proxy URL with auth
                proxy_url = None
                for p in proxy_manager._proxies:
                    if p.id == proxy['id']:
                        proxy_url = p.url
                        break
                
                self._proxy_slots[proxy_id] = ProxySlot(
                    proxy_id=proxy_id,
                    server=proxy.get('server', ''),
                    proxy_url=proxy_url,
                    priority=proxy.get('priority', 99)
                )
            
            # Load CoinGecko API keys from database
            keys_cursor = self.db.api_keys.find({"service": "coingecko", "enabled": True})
            keys = await keys_cursor.to_list(100)
            
            for key_doc in keys:
                key_status = KeyStatus(
                    key_id=key_doc.get('id', ''),
                    api_key=key_doc.get('api_key', ''),
                    proxy_id=key_doc.get('proxy_id'),
                    is_pro=key_doc.get('is_pro', False)
                )
                
                # Assign key to proxy
                proxy_id = key_doc.get('proxy_id')
                if proxy_id and proxy_id in self._proxy_slots:
                    self._proxy_slots[proxy_id].keys.append(key_status)
                    logger.info(f"[CoinGeckoManager] Key {key_status.key_id[:8]} assigned to proxy {proxy_id}")
                else:
                    # Key without proxy - assign to first available or direct
                    if self._proxy_slots:
                        first_proxy = list(self._proxy_slots.values())[0]
                        first_proxy.keys.append(key_status)
                        logger.info(f"[CoinGeckoManager] Key {key_status.key_id[:8]} assigned to proxy {first_proxy.proxy_id} (default)")
                    else:
                        # Direct connection slot
                        if not self._direct_slot:
                            self._direct_slot = ProxySlot(
                                proxy_id='direct',
                                server='direct',
                                proxy_url=None,
                                priority=999
                            )
                        self._direct_slot.keys.append(key_status)
                        logger.info(f"[CoinGeckoManager] Key {key_status.key_id[:8]} assigned to direct connection")
            
            # Create direct slot if no proxies
            if not self._proxy_slots and not self._direct_slot:
                self._direct_slot = ProxySlot(
                    proxy_id='direct',
                    server='direct',
                    proxy_url=None,
                    priority=999
                )
            
            self._initialized = True
            
            total_keys = sum(len(s.keys) for s in self._proxy_slots.values())
            if self._direct_slot:
                total_keys += len(self._direct_slot.keys)
            
            logger.info(f"[CoinGeckoManager] Initialized: {len(self._proxy_slots)} proxies, {total_keys} keys")
            
        except Exception as e:
            logger.error(f"[CoinGeckoManager] Init failed: {e}")
            self._initialized = True  # Prevent retry loop
    
    def _get_all_slots(self) -> List[ProxySlot]:
        """Get all slots sorted by priority"""
        slots = list(self._proxy_slots.values())
        if self._direct_slot:
            slots.append(self._direct_slot)
        return sorted(slots, key=lambda s: s.priority)
    
    async def _get_best_slot_and_key(self) -> Tuple[Optional[ProxySlot], Optional[KeyStatus], bool]:
        """
        Find best available proxy slot and key.
        Returns: (slot, key, use_keyless)
        """
        await self.initialize()
        
        slots = self._get_all_slots()
        
        for slot in slots:
            # Try to get available key
            key = slot.get_available_key()
            if key:
                return (slot, key, False)
            
            # No key available, try keyless mode
            if slot.is_keyless_available():
                return (slot, None, True)
        
        # All exhausted - wait and retry with first slot
        if slots:
            logger.warning("[CoinGeckoManager] All slots exhausted, waiting 5s...")
            await asyncio.sleep(5)
            return (slots[0], None, True)
        
        return (None, None, False)
    
    async def request(
        self,
        endpoint: str,
        params: Dict = None,
        timeout: int = 30,
        _retry_count: int = 0
    ) -> Dict[str, Any]:
        """
        Make CoinGecko API request with automatic proxy/key rotation.
        """
        if _retry_count > 5:
            raise Exception("Max retries exceeded for CoinGecko request")
        
        async with self._lock:
            slot, key, use_keyless = await self._get_best_slot_and_key()
        
        if not slot:
            raise Exception("No available proxy/connection for CoinGecko")
        
        # Build URL
        if key and key.is_pro:
            base_url = self.PRO_URL
        else:
            base_url = self.BASE_URL
        
        url = f"{base_url}{endpoint}"
        
        # Build params with key if available
        request_params = dict(params) if params else {}
        if key:
            if key.is_pro:
                request_params['x_cg_pro_api_key'] = key.api_key
            else:
                request_params['x_cg_demo_api_key'] = key.api_key
        
        try:
            async with httpx.AsyncClient(
                proxy=slot.proxy_url,
                timeout=timeout
            ) as client:
                response = await client.get(url, params=request_params)
                
                # Record request
                if key:
                    key.record_request()
                else:
                    slot.keyless_requests += 1
                
                # Handle rate limit
                if response.status_code == 429:
                    if key:
                        key.record_rate_limit(60)
                        logger.warning(f"[CoinGeckoManager] Key {key.key_id[:8]} hit rate limit on proxy {slot.proxy_id}")
                    else:
                        slot.record_keyless_rate_limit()
                        logger.warning(f"[CoinGeckoManager] Keyless mode hit rate limit on proxy {slot.proxy_id}")
                    
                    # Retry with different slot/key
                    return await self.request(endpoint, params, timeout, _retry_count + 1)
                
                response.raise_for_status()
                
                if key:
                    key.record_success()
                
                return response.json()
                
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                if key:
                    key.record_rate_limit(60)
                else:
                    slot.record_keyless_rate_limit()
                return await self.request(endpoint, params, timeout, _retry_count + 1)
            
            if key:
                key.record_error(str(e))
            raise
            
        except Exception as e:
            if key:
                key.record_error(str(e))
            raise
    
    async def request_parallel(
        self,
        endpoints: List[str],
        params_list: List[Dict] = None
    ) -> List[Dict[str, Any]]:
        """
        Make multiple CoinGecko requests in parallel using different proxies.
        """
        if params_list is None:
            params_list = [{}] * len(endpoints)
        
        tasks = [
            self.request(endpoint, params)
            for endpoint, params in zip(endpoints, params_list)
        ]
        
        return await asyncio.gather(*tasks, return_exceptions=True)
    
    def get_status(self) -> Dict[str, Any]:
        """Get manager status"""
        slots_status = {}
        
        for slot in self._get_all_slots():
            slots_status[slot.proxy_id] = {
                "server": slot.server,
                "priority": slot.priority,
                "keys_count": len(slot.keys),
                "keys": [
                    {
                        "key_id": k.key_id[:8] + "...",
                        "is_pro": k.is_pro,
                        "is_available": k.is_available(),
                        "requests_this_minute": k.requests_this_minute,
                        "is_rate_limited": k.is_rate_limited,
                        "rate_limit_until": k.rate_limit_until.isoformat() if k.rate_limit_until else None,
                        "total_requests": k.total_requests
                    }
                    for k in slot.keys
                ],
                "keyless_available": slot.is_keyless_available(),
                "keyless_requests": slot.keyless_requests
            }
        
        return {
            "initialized": self._initialized,
            "total_proxies": len(self._proxy_slots),
            "has_direct": self._direct_slot is not None,
            "slots": slots_status
        }


# Singleton
_manager: Optional[CoinGeckoKeyManager] = None


def get_coingecko_manager(db) -> CoinGeckoKeyManager:
    """Get or create CoinGecko key manager"""
    global _manager
    if _manager is None:
        _manager = CoinGeckoKeyManager(db)
    return _manager


async def reset_coingecko_manager():
    """Reset manager (for testing)"""
    global _manager
    _manager = None
