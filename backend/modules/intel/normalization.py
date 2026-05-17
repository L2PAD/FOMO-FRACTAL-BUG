"""
Data Normalization & Deduplication Engine

Pipeline:
RAW JSON → Parser → Normalized Tables → Dedup → Curated Intel Tables

This module handles:
1. Storing parsed data to normalized collections
2. Merging duplicates from multiple sources
3. Building the Event Index for fast queries
4. Creating curated final tables for API
"""

import logging
from typing import List, Dict, Any, Optional, Type
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorDatabase

from .models import (
    IntelUnlock,
    IntelFunding,
    IntelInvestor,
    IntelSale,
    IntelEvent
)

logger = logging.getLogger(__name__)

# Source weights for confidence calculation
SOURCE_WEIGHTS = {
    "cryptorank": 0.9,
    "dropstab": 0.85,
    "coingecko": 0.8,
    "manual": 1.0
}


class NormalizationEngine:
    """
    Handles data normalization and deduplication.
    
    Collections:
    - normalized_unlocks / normalized_funding / etc - parsed data
    - intel_unlocks / intel_funding / etc - deduplicated curated data
    - intel_events - unified event index
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
    
    # ═══════════════════════════════════════════════════════════════
    # STORE NORMALIZED DATA
    # ═══════════════════════════════════════════════════════════════
    
    async def store_unlocks(self, unlocks: List[IntelUnlock]) -> Dict[str, Any]:
        """Store parsed unlocks to normalized collection"""
        if not unlocks:
            return {"stored": 0, "updated": 0}
        
        stored = 0
        updated = 0
        
        for unlock in unlocks:
            doc = unlock.to_mongo()
            
            # Upsert by unique ID
            result = await self.db.normalized_unlocks.update_one(
                {"id": unlock.id},
                {"$set": doc},
                upsert=True
            )
            
            if result.upserted_id:
                stored += 1
            elif result.modified_count > 0:
                updated += 1
        
        logger.info(f"[Normalize] Stored {stored} new, updated {updated} unlocks")
        return {"stored": stored, "updated": updated}
    
    async def store_funding(self, rounds: List[IntelFunding]) -> Dict[str, Any]:
        """Store parsed funding rounds to normalized collection"""
        if not rounds:
            return {"stored": 0, "updated": 0}
        
        stored = 0
        updated = 0
        
        for funding in rounds:
            doc = funding.to_mongo()
            
            result = await self.db.normalized_funding.update_one(
                {"id": funding.id},
                {"$set": doc},
                upsert=True
            )
            
            if result.upserted_id:
                stored += 1
            elif result.modified_count > 0:
                updated += 1
        
        logger.info(f"[Normalize] Stored {stored} new, updated {updated} funding rounds")
        return {"stored": stored, "updated": updated}
    
    async def store_investors(self, investors: List[IntelInvestor]) -> Dict[str, Any]:
        """Store parsed investors to normalized collection"""
        if not investors:
            return {"stored": 0, "updated": 0}
        
        stored = 0
        updated = 0
        
        for investor in investors:
            doc = investor.to_mongo()
            
            result = await self.db.normalized_investors.update_one(
                {"id": investor.id},
                {"$set": doc},
                upsert=True
            )
            
            if result.upserted_id:
                stored += 1
            elif result.modified_count > 0:
                updated += 1
        
        logger.info(f"[Normalize] Stored {stored} new, updated {updated} investors")
        return {"stored": stored, "updated": updated}
    
    async def store_sales(self, sales: List[IntelSale]) -> Dict[str, Any]:
        """Store parsed sales to normalized collection"""
        if not sales:
            return {"stored": 0, "updated": 0}
        
        stored = 0
        updated = 0
        
        for sale in sales:
            doc = sale.to_mongo()
            
            result = await self.db.normalized_sales.update_one(
                {"id": sale.id},
                {"$set": doc},
                upsert=True
            )
            
            if result.upserted_id:
                stored += 1
            elif result.modified_count > 0:
                updated += 1
        
        logger.info(f"[Normalize] Stored {stored} new, updated {updated} sales")
        return {"stored": stored, "updated": updated}
    
    # ═══════════════════════════════════════════════════════════════
    # DEDUPLICATION
    # ═══════════════════════════════════════════════════════════════
    
    async def dedupe_unlocks(self) -> Dict[str, Any]:
        """
        Deduplicate unlocks from normalized to curated table.
        Uses MongoDB aggregation for grouping, processes in batches.
        """
        total_sources = await self.db.normalized_unlocks.count_documents({})
        if total_sources == 0:
            return {"deduped": 0, "total_sources": 0}
        
        # Use MongoDB aggregation to group by symbol + day
        pipeline = [
            {"$match": {"symbol": {"$exists": True, "$ne": ""}}},
            {"$addFields": {
                "day_key": {"$floor": {"$divide": [{"$ifNull": ["$unlock_date", 0]}, 86400]}}
            }},
            {"$group": {
                "_id": {"symbol": {"$toUpper": "$symbol"}, "day": "$day_key"},
                "records": {"$push": "$$ROOT"},
                "count": {"$sum": 1}
            }},
        ]
        
        merged = 0
        batch_ops = []
        BATCH_SIZE = 200
        
        async for group in self.db.normalized_unlocks.aggregate(pipeline):
            records = group["records"]
            if not records:
                continue
            
            primary = records[0]
            sources = list(set(u.get("source") for u in records if u.get("source")))
            confidence = min(1.0, sum(SOURCE_WEIGHTS.get(s, 0.5) for s in sources))
            
            amount_usd = max((u.get("amount_usd") or 0) for u in records) or None
            amount_tokens = max((u.get("amount_tokens") or 0) for u in records) or None
            percent_supply = max((u.get("percent_supply") or 0) for u in records) or None
            
            curated = {
                "id": primary.get("id"),
                "symbol": primary.get("symbol"),
                "project": primary.get("project"),
                "project_key": primary.get("project_key"),
                "unlock_date": primary.get("unlock_date"),
                "unlock_type": primary.get("unlock_type"),
                "amount_usd": amount_usd,
                "amount_tokens": amount_tokens,
                "percent_supply": percent_supply,
                "sources": sources,
                "confidence": confidence,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            
            from pymongo import UpdateOne
            batch_ops.append(UpdateOne(
                {"id": curated["id"]},
                {"$set": curated},
                upsert=True
            ))
            merged += 1
            
            if len(batch_ops) >= BATCH_SIZE:
                await self.db.intel_unlocks.bulk_write(batch_ops, ordered=False)
                batch_ops = []
        
        if batch_ops:
            await self.db.intel_unlocks.bulk_write(batch_ops, ordered=False)
        
        logger.info(f"[Dedup] Merged {merged} unlock events from {total_sources} sources")
        return {"deduped": merged, "total_sources": total_sources}
    
    async def dedupe_funding(self) -> Dict[str, Any]:
        """Deduplicate funding rounds using MongoDB aggregation + batch writes"""
        total_sources = await self.db.normalized_funding.count_documents({})
        if total_sources == 0:
            return {"deduped": 0, "total_sources": 0}
        
        # Group by project/symbol + round_type + week
        pipeline = [
            {"$addFields": {
                "group_key": {
                    "$toLower": {
                        "$ifNull": [
                            "$symbol",
                            {"$ifNull": ["$project", "unknown"]}
                        ]
                    }
                },
                "week_key": {"$floor": {"$divide": [{"$ifNull": ["$round_date", 0]}, 604800]}}
            }},
            {"$match": {"group_key": {"$ne": "unknown"}}},
            {"$group": {
                "_id": {
                    "group_key": "$group_key",
                    "round_type": {"$ifNull": ["$round_type", "other"]},
                    "week": "$week_key"
                },
                "records": {"$push": "$$ROOT"},
                "count": {"$sum": 1}
            }},
        ]
        
        merged = 0
        batch_ops = []
        BATCH_SIZE = 200
        
        async for group in self.db.normalized_funding.aggregate(pipeline):
            records = group["records"]
            if not records:
                continue
            
            primary = records[0]
            sources = list(set(f.get("source") for f in records if f.get("source")))
            confidence = min(1.0, sum(SOURCE_WEIGHTS.get(s, 0.5) for s in sources))
            
            all_investors = set()
            all_leads = set()
            for f in records:
                inv = f.get("investors", [])
                if isinstance(inv, list):
                    all_investors.update(inv)
                lead = f.get("lead_investor") or f.get("lead_investors", [])
                if isinstance(lead, list):
                    all_leads.update(lead)
                elif isinstance(lead, str) and lead:
                    all_leads.add(lead)
            
            raised_usd = max((f.get("raised_usd") or 0) for f in records) or None
            
            dedup_id = f"{group['_id']['group_key']}:{group['_id']['round_type']}:{group['_id']['week']}"
            
            curated = {
                "id": dedup_id,
                "symbol": primary.get("symbol"),
                "project": primary.get("project"),
                "round_type": primary.get("round_type"),
                "round_date": primary.get("round_date"),
                "raised_usd": raised_usd,
                "valuation_usd": max((f.get("valuation_usd") or 0) for f in records) or None,
                "investors": list(all_investors),
                "lead_investors": list(all_leads),
                "investor_count": len(all_investors),
                "sources": sources,
                "source_count": len(records),
                "confidence": confidence,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            
            from pymongo import UpdateOne
            batch_ops.append(UpdateOne(
                {"id": dedup_id},
                {"$set": curated},
                upsert=True
            ))
            merged += 1
            
            if len(batch_ops) >= BATCH_SIZE:
                await self.db.intel_funding.bulk_write(batch_ops, ordered=False)
                batch_ops = []
        
        if batch_ops:
            await self.db.intel_funding.bulk_write(batch_ops, ordered=False)
        
        logger.info(f"[Dedup] Merged {merged} funding rounds from {total_sources} sources")
        return {"deduped": merged, "total_sources": total_sources}
    
    async def dedupe_investors(self) -> Dict[str, Any]:
        """Deduplicate investors using MongoDB aggregation + batch writes"""
        total_sources = await self.db.normalized_investors.count_documents({})
        if total_sources == 0:
            return {"deduped": 0, "total_sources": 0}
        
        pipeline = [
            {"$match": {"slug": {"$exists": True, "$ne": ""}}},
            {"$group": {
                "_id": {"$toLower": "$slug"},
                "records": {"$push": "$$ROOT"},
                "count": {"$sum": 1}
            }},
        ]
        
        merged = 0
        batch_ops = []
        BATCH_SIZE = 200
        
        async for group in self.db.normalized_investors.aggregate(pipeline):
            records = group["records"]
            slug = group["_id"]
            if not records or not slug:
                continue
            
            primary = records[0]
            sources = list(set(i.get("source") for i in records if i.get("source")))
            
            investments_count = max(i.get("investments_count", 0) for i in records)
            
            all_portfolio = set()
            for i in records:
                all_portfolio.update(i.get("portfolio", []))
            
            curated = {
                "id": primary.get("id"),
                "name": primary.get("name"),
                "slug": slug,
                "tier": primary.get("tier"),
                "category": primary.get("category"),
                "investments_count": investments_count,
                "portfolio": list(all_portfolio),
                "logo_url": primary.get("logo_url"),
                "sources": sources,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            
            from pymongo import UpdateOne
            batch_ops.append(UpdateOne(
                {"slug": slug},
                {"$set": curated},
                upsert=True
            ))
            merged += 1
            
            if len(batch_ops) >= BATCH_SIZE:
                await self.db.intel_investors.bulk_write(batch_ops, ordered=False)
                batch_ops = []
        
        if batch_ops:
            await self.db.intel_investors.bulk_write(batch_ops, ordered=False)
        
        logger.info(f"[Dedup] Merged {merged} investors from {total_sources} sources")
        return {"deduped": merged, "total_sources": total_sources}
    
    # ═══════════════════════════════════════════════════════════════
    # EVENT INDEX
    # ═══════════════════════════════════════════════════════════════
    
    async def build_event_index(self) -> Dict[str, Any]:
        """
        Build unified event index from curated tables.
        
        Enables fast queries:
        - GET /events?symbol=SOL
        - GET /events?type=unlock&date_range=next_30_days
        """
        events_created = 0
        
        # Index unlocks
        cursor = self.db.intel_unlocks.find({}, {"_id": 0})
        unlocks = await cursor.to_list(None)
        
        for unlock in unlocks:
            event = {
                "id": f"unlock:{unlock.get('id')}",
                "event_type": "unlock",
                "symbol": unlock.get("symbol"),
                "project": unlock.get("project"),
                "project_key": unlock.get("project_key"),
                "event_date": unlock.get("unlock_date"),
                "amount_usd": unlock.get("amount_usd"),
                "sources": unlock.get("sources", []),
                "confidence": unlock.get("confidence", 0.5),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            
            await self.db.intel_events.update_one(
                {"id": event["id"]},
                {"$set": event},
                upsert=True
            )
            events_created += 1
        
        # Index funding
        cursor = self.db.intel_funding.find({}, {"_id": 0})
        funding = await cursor.to_list(None)
        
        for f in funding:
            event = {
                "id": f"funding:{f.get('id')}",
                "event_type": "funding",
                "symbol": f.get("symbol"),
                "project": f.get("project"),
                "project_key": f.get("project_key"),
                "event_date": f.get("round_date"),
                "amount_usd": f.get("raised_usd"),
                "sources": f.get("sources", []),
                "confidence": f.get("confidence", 0.5),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            
            await self.db.intel_events.update_one(
                {"id": event["id"]},
                {"$set": event},
                upsert=True
            )
            events_created += 1
        
        # Create indexes for fast queries
        await self.db.intel_events.create_index([("symbol", 1), ("event_date", 1)])
        await self.db.intel_events.create_index([("event_type", 1), ("event_date", 1)])
        await self.db.intel_events.create_index([("event_date", 1)])
        
        logger.info(f"[EventIndex] Built index with {events_created} events")
        return {"events_indexed": events_created}
    
    # ═══════════════════════════════════════════════════════════════
    # FULL PIPELINE
    # ═══════════════════════════════════════════════════════════════
    
    async def run_full_pipeline(self) -> Dict[str, Any]:
        """Run full normalization → dedup → index pipeline"""
        results = {
            "dedupe_unlocks": await self.dedupe_unlocks(),
            "dedupe_funding": await self.dedupe_funding(),
            "dedupe_investors": await self.dedupe_investors(),
            "event_index": await self.build_event_index()
        }
        
        logger.info(f"[Pipeline] Full normalization complete: {results}")
        return results
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get pipeline statistics"""
        return {
            "normalized": {
                "unlocks": await self.db.normalized_unlocks.count_documents({}),
                "funding": await self.db.normalized_funding.count_documents({}),
                "investors": await self.db.normalized_investors.count_documents({}),
                "sales": await self.db.normalized_sales.count_documents({})
            },
            "curated": {
                "unlocks": await self.db.intel_unlocks.count_documents({}),
                "funding": await self.db.intel_funding.count_documents({}),
                "investors": await self.db.intel_investors.count_documents({}),
                "sales": await self.db.intel_sales.count_documents({})
            },
            "events": await self.db.intel_events.count_documents({})
        }


def create_normalization_engine(db: AsyncIOMotorDatabase) -> NormalizationEngine:
    """Factory function"""
    return NormalizationEngine(db)
