"""
Provider Validation Service
============================

Validates entity candidates against external providers:
- CryptoRank
- RootData  
- CoinGecko

Provides:
- Provider match confirmation
- Entity type correction
- Confidence boost from external sources
"""

import logging
import re
import asyncio
import aiohttp
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)


# Provider configurations
PROVIDER_CONFIG = {
    "cryptorank": {
        "base_url": "https://api.cryptorank.io/v1",
        "search_endpoint": "/global/search",
        "project_endpoint": "/currencies",
        "fund_endpoint": "/funds",
        "priority": 1,
        "weight": 0.95,
        "timeout": 10
    },
    "rootdata": {
        "base_url": "https://api.rootdata.com/open",
        "search_endpoint": "/search",
        "priority": 2,
        "weight": 0.90,
        "timeout": 10
    },
    "coingecko": {
        "base_url": "https://api.coingecko.com/api/v3",
        "search_endpoint": "/search",
        "priority": 3,
        "weight": 0.85,
        "timeout": 10
    }
}

# Entity type mappings from providers
TYPE_MAPPINGS = {
    "cryptorank": {
        "currency": "project",
        "token": "project",
        "fund": "fund",
        "investor": "fund",
        "vc": "fund",
        "person": "person",
        "exchange": "exchange"
    },
    "rootdata": {
        "project": "project",
        "organization": "fund",
        "investor": "fund",
        "fund": "fund",
        "people": "person"
    },
    "coingecko": {
        "coin": "project",
        "exchange": "exchange",
        "category": None  # Skip
    }
}


class ProviderValidationService:
    """
    Validates entity candidates against external providers.
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.candidates = db.entity_candidates
        self.validation_logs = db.provider_validation_logs
        self._session: Optional[aiohttp.ClientSession] = None
        
        # Cache for recent validations
        self._cache: Dict[str, Dict] = {}
        self._cache_ttl = 3600  # 1 hour
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session"""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=15)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session
    
    async def close(self):
        """Close HTTP session"""
        if self._session and not self._session.closed:
            await self._session.close()
    
    @staticmethod
    def normalize_name(name: str) -> str:
        """Normalize name for matching"""
        if not name:
            return ""
        normalized = name.lower().strip()
        normalized = re.sub(r'[^\w\s]', '', normalized)
        normalized = re.sub(r'\s+', ' ', normalized)
        return normalized
    
    def _match_score(self, query: str, result_name: str) -> float:
        """Calculate match score between query and result"""
        query_norm = self.normalize_name(query)
        result_norm = self.normalize_name(result_name)
        
        # Exact match
        if query_norm == result_norm:
            return 1.0
        
        # Starts with
        if result_norm.startswith(query_norm) or query_norm.startswith(result_norm):
            return 0.9
        
        # Contains
        if query_norm in result_norm or result_norm in query_norm:
            return 0.75
        
        # Word match
        query_words = set(query_norm.split())
        result_words = set(result_norm.split())
        common = query_words & result_words
        if common:
            return 0.6 * len(common) / max(len(query_words), len(result_words))
        
        return 0.0
    
    async def validate_with_cryptorank(self, name: str, entity_type: str = None) -> Optional[Dict]:
        """Validate against CryptoRank"""
        try:
            config = PROVIDER_CONFIG["cryptorank"]
            
            # Use internal data instead of external API
            # CryptoRank data is already in our database
            cryptorank_projects = self.db.cryptorank_projects
            cryptorank_funds = self.db.cryptorank_funds
            
            normalized = self.normalize_name(name)
            
            # Search projects
            project = await cryptorank_projects.find_one({
                "$or": [
                    {"name": {"$regex": f"^{re.escape(name)}$", "$options": "i"}},
                    {"symbol": {"$regex": f"^{re.escape(name)}$", "$options": "i"}},
                    {"slug": normalized.replace(' ', '-')}
                ]
            })
            
            if project:
                return {
                    "provider": "cryptorank",
                    "match": True,
                    "entity_type": "project",
                    "matched_name": project.get("name"),
                    "matched_id": project.get("slug") or project.get("key"),
                    "confidence": config["weight"],
                    "metadata": {
                        "symbol": project.get("symbol"),
                        "category": project.get("category")
                    }
                }
            
            # Search funds
            fund = await cryptorank_funds.find_one({
                "$or": [
                    {"name": {"$regex": f"^{re.escape(name)}$", "$options": "i"}},
                    {"name": {"$regex": f".*{re.escape(name)}.*", "$options": "i"}}
                ]
            })
            
            if fund:
                return {
                    "provider": "cryptorank",
                    "match": True,
                    "entity_type": "fund",
                    "matched_name": fund.get("name"),
                    "matched_id": fund.get("slug") or fund.get("key"),
                    "confidence": config["weight"],
                    "metadata": {
                        "type": fund.get("type"),
                        "portfolio_size": fund.get("portfolio_count")
                    }
                }
            
            return None
            
        except Exception as e:
            logger.warning(f"[ProviderValidation] CryptoRank error for '{name}': {e}")
            return None
    
    async def validate_with_rootdata(self, name: str, entity_type: str = None) -> Optional[Dict]:
        """Validate against RootData"""
        try:
            config = PROVIDER_CONFIG["rootdata"]
            
            # Use internal RootData collections
            rootdata_projects = self.db.rootdata_projects
            rootdata_organizations = self.db.rootdata_organizations
            
            normalized = self.normalize_name(name)
            
            # Search projects
            project = await rootdata_projects.find_one({
                "$or": [
                    {"name": {"$regex": f"^{re.escape(name)}$", "$options": "i"}},
                    {"name": {"$regex": f".*{re.escape(name)}.*", "$options": "i"}}
                ]
            })
            
            if project:
                return {
                    "provider": "rootdata",
                    "match": True,
                    "entity_type": "project",
                    "matched_name": project.get("name"),
                    "matched_id": project.get("id") or project.get("slug"),
                    "confidence": config["weight"],
                    "metadata": {
                        "category": project.get("category"),
                        "tags": project.get("tags", [])
                    }
                }
            
            # Search organizations (funds)
            org = await rootdata_organizations.find_one({
                "$or": [
                    {"name": {"$regex": f"^{re.escape(name)}$", "$options": "i"}},
                    {"name": {"$regex": f".*{re.escape(name)}.*", "$options": "i"}}
                ]
            })
            
            if org:
                return {
                    "provider": "rootdata",
                    "match": True,
                    "entity_type": "fund",
                    "matched_name": org.get("name"),
                    "matched_id": org.get("id") or org.get("slug"),
                    "confidence": config["weight"],
                    "metadata": {
                        "type": org.get("type")
                    }
                }
            
            return None
            
        except Exception as e:
            logger.warning(f"[ProviderValidation] RootData error for '{name}': {e}")
            return None
    
    async def validate_with_coingecko(self, name: str, entity_type: str = None) -> Optional[Dict]:
        """Validate against CoinGecko"""
        try:
            config = PROVIDER_CONFIG["coingecko"]
            
            # Use internal CoinGecko data
            coingecko_coins = self.db.coingecko_coins
            
            # Search coins
            coin = await coingecko_coins.find_one({
                "$or": [
                    {"name": {"$regex": f"^{re.escape(name)}$", "$options": "i"}},
                    {"symbol": {"$regex": f"^{re.escape(name)}$", "$options": "i"}},
                    {"id": normalized.replace(' ', '-')}
                ]
            })
            
            if coin:
                return {
                    "provider": "coingecko",
                    "match": True,
                    "entity_type": "project",
                    "matched_name": coin.get("name"),
                    "matched_id": coin.get("id"),
                    "confidence": config["weight"],
                    "metadata": {
                        "symbol": coin.get("symbol"),
                        "market_cap_rank": coin.get("market_cap_rank")
                    }
                }
            
            return None
            
        except Exception as e:
            logger.warning(f"[ProviderValidation] CoinGecko error for '{name}': {e}")
            return None
    
    async def validate_entity(
        self, 
        name: str, 
        entity_type_guess: str = None
    ) -> Dict[str, Any]:
        """
        Validate entity against all providers.
        
        Returns:
        {
            "validated": bool,
            "provider_matches": [...],
            "best_match": {...},
            "confirmed_type": str,
            "provider_confidence": float,
            "multi_source": bool
        }
        """
        # Check cache first
        cache_key = f"{self.normalize_name(name)}:{entity_type_guess or 'any'}"
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            if (datetime.now(timezone.utc).timestamp() - cached.get("ts", 0)) < self._cache_ttl:
                return cached["result"]
        
        # Run all validations in parallel
        results = await asyncio.gather(
            self.validate_with_cryptorank(name, entity_type_guess),
            self.validate_with_rootdata(name, entity_type_guess),
            self.validate_with_coingecko(name, entity_type_guess),
            return_exceptions=True
        )
        
        # Collect matches
        matches = []
        for result in results:
            if isinstance(result, dict) and result.get("match"):
                matches.append(result)
        
        if not matches:
            result = {
                "validated": False,
                "provider_matches": [],
                "best_match": None,
                "confirmed_type": entity_type_guess,
                "provider_confidence": 0.0,
                "multi_source": False
            }
        else:
            # Sort by confidence
            matches.sort(key=lambda x: x.get("confidence", 0), reverse=True)
            best_match = matches[0]
            
            # Calculate combined confidence
            if len(matches) >= 3:
                provider_confidence = 0.98  # Very high - confirmed by 3 providers
            elif len(matches) >= 2:
                provider_confidence = 0.92  # High - confirmed by 2 providers
            else:
                provider_confidence = best_match.get("confidence", 0.85)
            
            result = {
                "validated": True,
                "provider_matches": [m["provider"] for m in matches],
                "best_match": best_match,
                "confirmed_type": best_match.get("entity_type", entity_type_guess),
                "provider_confidence": provider_confidence,
                "multi_source": len(matches) >= 2
            }
        
        # Cache result
        self._cache[cache_key] = {
            "ts": datetime.now(timezone.utc).timestamp(),
            "result": result
        }
        
        # Log validation
        await self._log_validation(name, entity_type_guess, result)
        
        return result
    
    async def _log_validation(self, name: str, entity_type: str, result: Dict):
        """Log validation result"""
        try:
            log = {
                "name": name,
                "entity_type_guess": entity_type,
                "validated": result.get("validated", False),
                "provider_matches": result.get("provider_matches", []),
                "provider_confidence": result.get("provider_confidence", 0),
                "validated_at": datetime.now(timezone.utc)
            }
            await self.validation_logs.insert_one(log)
        except Exception as e:
            logger.debug(f"[ProviderValidation] Failed to log: {e}")
    
    async def validate_batch(
        self, 
        candidates: List[Dict],
        concurrency: int = 5
    ) -> List[Dict]:
        """Validate multiple candidates"""
        results = []
        
        # Process in batches to avoid overwhelming providers
        for i in range(0, len(candidates), concurrency):
            batch = candidates[i:i + concurrency]
            
            tasks = [
                self.validate_entity(
                    c.get("name"),
                    c.get("entity_type_guess")
                )
                for c in batch
            ]
            
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for candidate, result in zip(batch, batch_results):
                if isinstance(result, Exception):
                    result = {"validated": False, "error": str(result)}
                
                results.append({
                    "candidate": candidate.get("name"),
                    "validation": result
                })
            
            # Small delay between batches
            if i + concurrency < len(candidates):
                await asyncio.sleep(0.5)
        
        return results
    
    async def get_validation_stats(self) -> Dict[str, Any]:
        """Get validation statistics"""
        # Total validations
        total = await self.validation_logs.count_documents({})
        
        # Validated vs not validated
        validated_count = await self.validation_logs.count_documents({"validated": True})
        
        # By provider
        provider_pipeline = [
            {"$unwind": "$provider_matches"},
            {"$group": {"_id": "$provider_matches", "count": {"$sum": 1}}}
        ]
        provider_counts = await self.validation_logs.aggregate(provider_pipeline).to_list(10)
        
        return {
            "total_validations": total,
            "validated_count": validated_count,
            "validation_rate": validated_count / total if total > 0 else 0,
            "by_provider": {p["_id"]: p["count"] for p in provider_counts}
        }


# Singleton
_provider_service: Optional[ProviderValidationService] = None


def get_provider_validation_service(db: AsyncIOMotorDatabase = None) -> ProviderValidationService:
    """Get or create provider validation service"""
    global _provider_service
    if db is not None:
        _provider_service = ProviderValidationService(db)
    return _provider_service
