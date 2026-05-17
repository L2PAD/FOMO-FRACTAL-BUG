"""
Intel Parser - SMART Data Type Detection

Parser is the SMART component:
- Analyzes raw JSON structure
- Detects entity type (unlock, funding, investor, etc)
- Transforms to unified schema
- Routes to correct normalized table

Architecture:
RAW JSON → PARSER (detects type) → UNIFIED MODEL → NORMALIZED TABLE
"""

import json
import gzip
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ParsedEntity:
    """Result of parsing a raw record"""
    entity_type: str  # unlock, funding, investor, sale, project, category
    confidence: float  # 0.0 - 1.0
    data: Dict[str, Any]
    source: str
    raw_keys: List[str]


class EntityDetector:
    """
    Detects entity type from raw JSON structure.
    Uses key patterns and heuristics.
    """
    
    # Key patterns that indicate entity types
    UNLOCK_KEYS = {
        "must_have_any": ["unlock", "vesting", "cliff", "tge"],
        "strong_signals": ["unlockUsd", "unlock_usd", "unlockPercent", "unlock_percent", 
                          "vestingSchedule", "vesting_schedule", "unlockDate", "unlock_date"],
        "weak_signals": ["percent", "release", "schedule"]
    }
    
    FUNDING_KEYS = {
        "must_have_any": ["funding", "raise", "round", "investment"],
        "strong_signals": ["raised", "raisedUsd", "raised_usd", "fundingRound", "funding_round",
                          "investmentStage", "investment_stage", "roundType", "round_type",
                          "leadInvestor", "lead_investor"],
        "weak_signals": ["investors", "funds", "valuation", "pre_money", "post_money"]
    }
    
    INVESTOR_KEYS = {
        "must_have_any": ["investor", "fund", "vc", "venture"],
        "strong_signals": ["aum", "assetsUnderManagement", "assets_under_management",
                          "portfolio", "investments", "fundType", "fund_type", "tier"],
        "weak_signals": ["website", "twitter", "founded", "team"]
    }
    
    SALE_KEYS = {
        "must_have_any": ["ico", "ido", "ieo", "sale", "launchpad"],
        "strong_signals": ["saleType", "sale_type", "launchpad", "tokenPrice", "token_price",
                          "hardCap", "hard_cap", "softCap", "soft_cap", "startDate", "endDate"],
        "weak_signals": ["allocation", "participants", "platform"]
    }
    
    PROJECT_KEYS = {
        "must_have_any": ["project", "token", "coin", "asset"],
        "strong_signals": ["marketCap", "market_cap", "price", "volume", "circulating",
                          "totalSupply", "total_supply", "chain", "category"],
        "weak_signals": ["symbol", "name", "logo", "website"]
    }
    
    CATEGORY_KEYS = {
        "must_have_any": ["category", "sector", "tag"],
        "strong_signals": ["categoryId", "category_id", "coinsCount", "coins_count",
                          "marketCapChange", "volumeChange"],
        "weak_signals": ["description", "top_coins"]
    }
    
    @classmethod
    def detect(cls, data: Dict[str, Any]) -> Tuple[str, float]:
        """
        Detect entity type from data structure.
        Returns (entity_type, confidence)
        """
        if not isinstance(data, dict):
            return "unknown", 0.0
        
        # Check for _data_key hint (from CryptoRank-style extraction)
        data_key = data.get("_data_key", "")
        if data_key:
            # Direct mapping from data key
            key_map = {
                "funds": ("investor", 0.9),
                "funding": ("funding", 0.9),
                "fundraising": ("funding", 0.9),
                "investors": ("investor", 0.9),
                "coins": ("project", 0.9),
                "unlocks": ("unlock", 0.9),
                "sales": ("sale", 0.9),
                "idoPlatforms": ("sale", 0.8),
                "exchanges": ("project", 0.7),
                "categories": ("category", 0.9),
                "tags": ("category", 0.8),
            }
            if data_key in key_map:
                return key_map[data_key]
        
        keys = set(k.lower() for k in data.keys())
        keys_str = " ".join(keys)
        
        scores = {
            "unlock": cls._score_entity(keys, keys_str, cls.UNLOCK_KEYS),
            "funding": cls._score_entity(keys, keys_str, cls.FUNDING_KEYS),
            "investor": cls._score_entity(keys, keys_str, cls.INVESTOR_KEYS),
            "sale": cls._score_entity(keys, keys_str, cls.SALE_KEYS),
            "project": cls._score_entity(keys, keys_str, cls.PROJECT_KEYS),
            "category": cls._score_entity(keys, keys_str, cls.CATEGORY_KEYS),
        }
        
        # Get highest scoring type
        best_type = max(scores, key=scores.get)
        best_score = scores[best_type]
        
        # Require minimum confidence
        if best_score < 0.3:
            return "unknown", best_score
        
        return best_type, best_score
    
    @classmethod
    def _score_entity(cls, keys: set, keys_str: str, patterns: Dict) -> float:
        """Calculate score for entity type"""
        score = 0.0
        
        # Check must_have_any (required)
        must_have = patterns.get("must_have_any", [])
        has_must_have = any(m in keys_str for m in must_have)
        if not has_must_have:
            return 0.0
        
        score += 0.3  # Base score for having required keys
        
        # Check strong signals
        strong = patterns.get("strong_signals", [])
        strong_matches = sum(1 for s in strong if s.lower() in keys_str)
        score += min(0.5, strong_matches * 0.15)
        
        # Check weak signals
        weak = patterns.get("weak_signals", [])
        weak_matches = sum(1 for w in weak if w.lower() in keys_str)
        score += min(0.2, weak_matches * 0.05)
        
        return min(1.0, score)


class IntelParser:
    """
    Main parser class.
    Transforms raw data to unified schema based on detected type.
    """
    
    RAW_DIR = Path("/app/data/raw")
    
    def __init__(self, db=None):
        self.db = db
        self.detector = EntityDetector()
    
    async def parse_source(self, source: str) -> Dict[str, Any]:
        """
        Parse ALL raw data from a source.
        Automatically detects entity types.
        """
        source_dir = self.RAW_DIR / source
        if not source_dir.exists():
            return {"error": f"No raw data for source: {source}"}
        
        results = {
            "source": source,
            "files_processed": 0,
            "records_parsed": 0,
            "by_type": {},
            "errors": []
        }
        
        # Find all raw files
        raw_files = list(source_dir.rglob("*.json.gz")) + list(source_dir.rglob("*.json"))
        
        for raw_file in raw_files:
            # Skip discovery files
            if "discovery" in str(raw_file):
                continue
                
            try:
                # Load raw data
                if raw_file.suffix == ".gz":
                    with gzip.open(raw_file, 'rt') as f:
                        raw_data = json.load(f)
                else:
                    with open(raw_file, 'r') as f:
                        raw_data = json.load(f)
                
                # Extract payload if wrapped in raw_store format
                if isinstance(raw_data, dict) and "payload" in raw_data:
                    raw_data = raw_data["payload"]
                
                # Parse records
                records = self._extract_records(raw_data)
                
                for record in records:
                    entity_type, confidence = self.detector.detect(record)
                    
                    if entity_type != "unknown" and confidence >= 0.3:
                        # Transform to unified schema
                        unified = self._transform_to_unified(record, entity_type, source)
                        
                        # Save to normalized table
                        await self._save_normalized(entity_type, unified)
                        
                        # Track stats
                        if entity_type not in results["by_type"]:
                            results["by_type"][entity_type] = 0
                        results["by_type"][entity_type] += 1
                        results["records_parsed"] += 1
                
                results["files_processed"] += 1
                
            except Exception as e:
                results["errors"].append(f"{raw_file.name}: {str(e)}")
        
        return results
    
    def _extract_records(self, raw_data: Any) -> List[Dict]:
        """Extract individual records from raw data"""
        all_records = []
        
        if isinstance(raw_data, list):
            return [r for r in raw_data if isinstance(r, dict)]
        
        if isinstance(raw_data, dict):
            # Check common wrapper keys (priority)
            for key in ["data", "items", "results", "records", "list"]:
                if key in raw_data and isinstance(raw_data[key], list):
                    return [r for r in raw_data[key] if isinstance(r, dict)]
            
            # CryptoRank-style: multiple lists under different keys
            # Extract all lists that look like entity data
            entity_keys = ["coins", "funds", "funding", "fundraising", "investors", 
                          "exchanges", "idoPlatforms", "unlocks", "sales", "categories",
                          "tags", "activities"]
            
            for key in entity_keys:
                if key in raw_data and isinstance(raw_data[key], list):
                    for item in raw_data[key]:
                        if isinstance(item, dict):
                            # Tag the item with its source key for parser hints
                            item["_data_key"] = key
                            all_records.append(item)
            
            if all_records:
                return all_records
            
            # Single record fallback
            return [raw_data]
        
        return []
    
    def _transform_to_unified(self, record: Dict, entity_type: str, source: str) -> Dict:
        """Transform raw record to unified schema"""
        now = datetime.now(timezone.utc)
        
        # Base fields for all entities
        unified = {
            "source": source,
            "_source_id": record.get("id") or record.get("key") or record.get("slug"),
            "_scraped_at": int(now.timestamp() * 1000),
            "_parser_version": "1.0"
        }
        
        if entity_type == "unlock":
            unified.update(self._transform_unlock(record))
        elif entity_type == "funding":
            unified.update(self._transform_funding(record))
        elif entity_type == "investor":
            unified.update(self._transform_investor(record))
        elif entity_type == "sale":
            unified.update(self._transform_sale(record))
        elif entity_type == "project":
            unified.update(self._transform_project(record))
        elif entity_type == "category":
            unified.update(self._transform_category(record))
        
        return unified
    
    def _transform_unlock(self, record: Dict) -> Dict:
        """Transform to IntelUnlock schema"""
        return {
            "symbol": record.get("symbol") or record.get("ticker") or record.get("coinSymbol"),
            "project": record.get("project") or record.get("projectName") or record.get("name"),
            "unlock_date": self._parse_date(record.get("unlockDate") or record.get("unlock_date") or record.get("date")),
            "unlock_type": record.get("unlockType") or record.get("unlock_type") or record.get("type") or "other",
            "amount_usd": self._parse_number(record.get("unlockUsd") or record.get("unlock_usd") or record.get("valueUsd")),
            "percent_supply": self._parse_number(record.get("unlockPercent") or record.get("unlock_percent") or record.get("percent")),
            "tokens_amount": self._parse_number(record.get("tokensAmount") or record.get("tokens_amount") or record.get("amount")),
        }
    
    def _transform_funding(self, record: Dict) -> Dict:
        """Transform to IntelFunding schema"""
        return {
            "symbol": record.get("symbol") or record.get("ticker"),
            "project": record.get("project") or record.get("projectName") or record.get("name"),
            "round_date": self._parse_date(record.get("date") or record.get("fundingDate") or record.get("announcedDate")),
            "round_type": record.get("stage") or record.get("roundType") or record.get("round_type") or "other",
            "raised_usd": self._parse_number(record.get("raised") or record.get("raisedUsd") or record.get("amount")),
            "valuation_usd": self._parse_number(record.get("valuation") or record.get("postMoney")),
            "investors": record.get("investors") or record.get("funds") or [],
            "lead_investor": record.get("leadInvestor") or record.get("lead_investor"),
        }
    
    def _transform_investor(self, record: Dict) -> Dict:
        """Transform to IntelInvestor schema"""
        return {
            "name": record.get("name") or record.get("fundName") or record.get("investorName"),
            "slug": record.get("slug") or record.get("key") or record.get("id"),
            "tier": record.get("tier") or self._detect_tier(record),
            "investor_type": record.get("type") or record.get("fundType") or record.get("category"),
            "aum_usd": self._parse_number(record.get("aum") or record.get("assetsUnderManagement")),
            "portfolio": record.get("portfolio") or record.get("investments") or [],
            "portfolio_count": record.get("portfolioCount") or record.get("investmentsCount") or len(record.get("portfolio", [])),
        }
    
    def _transform_sale(self, record: Dict) -> Dict:
        """Transform to IntelSale schema"""
        return {
            "symbol": record.get("symbol") or record.get("ticker"),
            "project": record.get("project") or record.get("projectName") or record.get("name"),
            "sale_type": record.get("saleType") or record.get("sale_type") or record.get("type") or "other",
            "platform": record.get("launchpad") or record.get("platform"),
            "start_date": self._parse_date(record.get("startDate") or record.get("start_date")),
            "end_date": self._parse_date(record.get("endDate") or record.get("end_date")),
            "token_price": self._parse_number(record.get("tokenPrice") or record.get("price")),
            "hard_cap_usd": self._parse_number(record.get("hardCap") or record.get("hard_cap")),
        }
    
    def _transform_project(self, record: Dict) -> Dict:
        """Transform to project schema"""
        return {
            "symbol": record.get("symbol") or record.get("ticker"),
            "name": record.get("name") or record.get("projectName"),
            "slug": record.get("slug") or record.get("id") or record.get("key"),
            "price_usd": self._parse_number(record.get("price") or record.get("current_price")),
            "market_cap": self._parse_number(record.get("marketCap") or record.get("market_cap")),
            "volume_24h": self._parse_number(record.get("volume") or record.get("total_volume")),
            "category": record.get("category") or record.get("categories"),
            "chain": record.get("chain") or record.get("platform"),
        }
    
    def _transform_category(self, record: Dict) -> Dict:
        """Transform to category schema"""
        return {
            "category_id": record.get("id") or record.get("categoryId") or record.get("category_id"),
            "name": record.get("name") or record.get("categoryName"),
            "coins_count": record.get("coinsCount") or record.get("coins_count") or 0,
            "market_cap": self._parse_number(record.get("marketCap") or record.get("market_cap")),
            "volume_24h": self._parse_number(record.get("volume") or record.get("volume_24h")),
        }
    
    def _parse_date(self, value: Any) -> Optional[int]:
        """Parse date to timestamp"""
        if value is None:
            return None
        if isinstance(value, (int, float)):
            # Already timestamp
            return int(value) if value > 1e12 else int(value * 1000)
        if isinstance(value, str):
            try:
                dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
                return int(dt.timestamp() * 1000)
            except:
                pass
        return None
    
    def _parse_number(self, value: Any) -> Optional[float]:
        """Parse number"""
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                # Remove common formatting
                clean = value.replace(",", "").replace("$", "").replace("%", "").strip()
                return float(clean)
            except:
                pass
        return None
    
    def _detect_tier(self, record: Dict) -> str:
        """Detect investor tier from data"""
        aum = self._parse_number(record.get("aum") or record.get("assetsUnderManagement"))
        portfolio_count = record.get("portfolioCount") or len(record.get("portfolio", []))
        
        if aum and aum > 1e9:
            return "tier_1"
        if aum and aum > 100e6:
            return "tier_2"
        if portfolio_count and portfolio_count > 50:
            return "tier_2"
        if portfolio_count and portfolio_count > 10:
            return "tier_3"
        return "other"
    
    async def _save_normalized(self, entity_type: str, data: Dict):
        """Save to normalized collection"""
        if self.db is None:
            return
        
        collection_map = {
            "unlock": "normalized_unlocks",
            "funding": "normalized_funding",
            "investor": "normalized_investors",
            "sale": "normalized_sales",
            "project": "intel_projects",
            "category": "intel_categories",
        }
        
        collection_name = collection_map.get(entity_type)
        if not collection_name:
            return
        
        # Upsert by source + source_id
        filter_key = {
            "source": data.get("source"),
            "_source_id": data.get("_source_id")
        }
        
        try:
            await self.db[collection_name].update_one(
                filter_key,
                {"$set": data},
                upsert=True
            )
        except Exception as e:
            logger.error(f"Failed to save {entity_type}: {e}")


# Singleton instance
intel_parser: Optional[IntelParser] = None


def init_parser(db):
    """Initialize parser with database"""
    global intel_parser
    intel_parser = IntelParser(db)
    return intel_parser
