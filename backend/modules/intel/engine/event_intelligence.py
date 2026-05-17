"""
Event Intelligence Engine

Превращает разрозненные данные (funding, unlock, listing, sale)
в унифицированный поток событий проекта.

Event Types:
- funding: раунды финансирования
- unlock: token unlocks
- token_sale: ICO/IDO/IEO
- exchange_listing: листинги на биржах
- governance: governance events
- airdrop: airdrops
"""

import hashlib
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    FUNDING = "funding"
    UNLOCK = "unlock"
    TOKEN_SALE = "token_sale"
    EXCHANGE_LISTING = "exchange_listing"
    GOVERNANCE = "governance"
    AIRDROP = "airdrop"
    INVESTOR_ENTRY = "investor_entry"
    OTHER = "other"


@dataclass
class IntelEvent:
    """Unified event model"""
    event_id: str
    entity_id: str
    event_type: EventType
    date: str  # ISO date
    payload: Dict[str, Any]
    sources: List[str]
    confidence: float
    created_at: str
    
    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["event_type"] = self.event_type.value
        return d


def generate_event_id(entity_id: str, event_type: str, date: str, payload_hash: str = "") -> str:
    """Generate unique event ID"""
    raw = f"{entity_id}:{event_type}:{date}:{payload_hash}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def payload_hash(payload: Dict[str, Any]) -> str:
    """Generate hash of payload for dedup"""
    # Use key fields for hashing
    key_fields = ["amount_usd", "stage", "exchange", "sale_type", "percent"]
    values = []
    for f in key_fields:
        if f in payload:
            values.append(str(payload[f]))
    return hashlib.md5(":".join(values).encode()).hexdigest()[:8]


class EventIntelligenceEngine:
    """
    Unified event processing engine.
    
    Converts:
    - Funding records → funding events
    - Unlock records → unlock events
    - Sale records → token_sale events
    - Listing records → exchange_listing events
    
    Provides:
    - Event deduplication
    - Event timeline per entity
    - Event search and filtering
    """
    
    def __init__(self, db):
        self.db = db
    
    async def _init_collections(self):
        """Ensure indexes"""
        try:
            await self.db.intel_events.create_index("event_id", unique=True)
            await self.db.intel_events.create_index("entity_id")
            await self.db.intel_events.create_index("event_type")
            await self.db.intel_events.create_index("date")
            await self.db.intel_events.create_index([("entity_id", 1), ("date", -1)])
        except Exception as e:
            logger.debug(f"Index creation skipped: {e}")
    
    # ═══════════════════════════════════════════════════════════════
    # Event Builders
    # ═══════════════════════════════════════════════════════════════
    
    async def funding_to_event(self, funding: Dict[str, Any]) -> IntelEvent:
        """Convert funding record to event"""
        entity_id = funding.get("entity_id") or (funding.get("symbol") or "unknown").lower()
        date = self._normalize_date(funding.get("round_date") or funding.get("date"))
        
        payload = {
            "amount_usd": funding.get("raised_usd") or funding.get("amount_usd"),
            "stage": funding.get("round_type") or funding.get("stage"),
            "investors": funding.get("investors", []),
            "lead_investor": funding.get("lead_investor"),
            "valuation_usd": funding.get("valuation_usd")
        }
        # Remove None values
        payload = {k: v for k, v in payload.items() if v is not None}
        
        event_id = generate_event_id(entity_id, "funding", date, payload_hash(payload))
        
        return IntelEvent(
            event_id=event_id,
            entity_id=entity_id,
            event_type=EventType.FUNDING,
            date=date,
            payload=payload,
            sources=[funding.get("source", "unknown")],
            confidence=funding.get("confidence", 0.8),
            created_at=datetime.now(timezone.utc).isoformat()
        )
    
    async def unlock_to_event(self, unlock: Dict[str, Any]) -> IntelEvent:
        """Convert unlock record to event"""
        entity_id = unlock.get("entity_id") or (unlock.get("symbol") or "unknown").lower()
        date = self._normalize_date(unlock.get("unlock_date") or unlock.get("date"))
        
        payload = {
            "amount_usd": unlock.get("amount_usd"),
            "percent": unlock.get("percent_supply") or unlock.get("percent"),
            "tokens_amount": unlock.get("tokens_amount"),
            "unlock_type": unlock.get("unlock_type")
        }
        payload = {k: v for k, v in payload.items() if v is not None}
        
        event_id = generate_event_id(entity_id, "unlock", date, payload_hash(payload))
        
        return IntelEvent(
            event_id=event_id,
            entity_id=entity_id,
            event_type=EventType.UNLOCK,
            date=date,
            payload=payload,
            sources=[unlock.get("source", "unknown")],
            confidence=unlock.get("confidence", 0.8),
            created_at=datetime.now(timezone.utc).isoformat()
        )
    
    async def sale_to_event(self, sale: Dict[str, Any]) -> IntelEvent:
        """Convert token sale record to event"""
        entity_id = sale.get("entity_id") or (sale.get("symbol") or "unknown").lower()
        date = self._normalize_date(sale.get("start_date") or sale.get("date"))
        
        payload = {
            "sale_type": sale.get("sale_type") or sale.get("type"),
            "platform": sale.get("platform") or sale.get("launchpad"),
            "token_price": sale.get("token_price"),
            "hard_cap_usd": sale.get("hard_cap_usd"),
            "end_date": self._normalize_date(sale.get("end_date"))
        }
        payload = {k: v for k, v in payload.items() if v is not None}
        
        event_id = generate_event_id(entity_id, "token_sale", date, payload_hash(payload))
        
        return IntelEvent(
            event_id=event_id,
            entity_id=entity_id,
            event_type=EventType.TOKEN_SALE,
            date=date,
            payload=payload,
            sources=[sale.get("source", "unknown")],
            confidence=sale.get("confidence", 0.8),
            created_at=datetime.now(timezone.utc).isoformat()
        )
    
    async def listing_to_event(self, listing: Dict[str, Any]) -> IntelEvent:
        """Convert exchange listing to event"""
        entity_id = listing.get("entity_id") or (listing.get("symbol") or "unknown").lower()
        date = self._normalize_date(listing.get("listing_date") or listing.get("date"))
        
        payload = {
            "exchange": listing.get("exchange"),
            "pairs": listing.get("pairs", [])
        }
        payload = {k: v for k, v in payload.items() if v is not None}
        
        event_id = generate_event_id(entity_id, "exchange_listing", date, payload_hash(payload))
        
        return IntelEvent(
            event_id=event_id,
            entity_id=entity_id,
            event_type=EventType.EXCHANGE_LISTING,
            date=date,
            payload=payload,
            sources=[listing.get("source", "unknown")],
            confidence=listing.get("confidence", 0.8),
            created_at=datetime.now(timezone.utc).isoformat()
        )
    
    # ═══════════════════════════════════════════════════════════════
    # Event Storage
    # ═══════════════════════════════════════════════════════════════
    
    async def save_event(self, event: IntelEvent) -> Dict[str, Any]:
        """Save event with dedup"""
        event_dict = event.to_dict()
        
        # Check if exists
        existing = await self.db.intel_events.find_one({"event_id": event.event_id})
        
        if existing:
            # Merge sources
            existing_sources = existing.get("sources", [])
            new_sources = list(set(existing_sources + event.sources))
            
            await self.db.intel_events.update_one(
                {"event_id": event.event_id},
                {"$set": {
                    "sources": new_sources,
                    "confidence": max(existing.get("confidence", 0), event.confidence)
                }}
            )
            return {"action": "merged", "event_id": event.event_id}
        
        await self.db.intel_events.insert_one(event_dict)
        return {"action": "created", "event_id": event.event_id}
    
    # ═══════════════════════════════════════════════════════════════
    # Batch Processing
    # ═══════════════════════════════════════════════════════════════
    
    async def process_all_events(self) -> Dict[str, Any]:
        """Process all normalized data into events"""
        results = {
            "funding": 0,
            "unlock": 0,
            "sale": 0,
            "errors": []
        }
        
        # Process funding
        cursor = self.db.normalized_funding.find({})
        async for record in cursor:
            try:
                event = await self.funding_to_event(record)
                await self.save_event(event)
                results["funding"] += 1
            except Exception as e:
                results["errors"].append(f"funding: {str(e)}")
        
        # Process unlocks
        cursor = self.db.normalized_unlocks.find({})
        async for record in cursor:
            try:
                event = await self.unlock_to_event(record)
                await self.save_event(event)
                results["unlock"] += 1
            except Exception as e:
                results["errors"].append(f"unlock: {str(e)}")
        
        # Process sales
        cursor = self.db.normalized_sales.find({})
        async for record in cursor:
            try:
                event = await self.sale_to_event(record)
                await self.save_event(event)
                results["sale"] += 1
            except Exception as e:
                results["errors"].append(f"sale: {str(e)}")
        
        logger.info(f"[EventEngine] Processed events: {results}")
        return results
    
    # ═══════════════════════════════════════════════════════════════
    # Queries
    # ═══════════════════════════════════════════════════════════════
    
    async def get_timeline(self, entity_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get chronological timeline for entity"""
        cursor = self.db.intel_events.find(
            {"entity_id": entity_id}
        ).sort("date", -1).limit(limit)
        
        events = await cursor.to_list(limit)
        
        # Sort by date ascending for timeline
        events.sort(key=lambda x: x.get("date", ""))
        
        return events
    
    async def get_events_by_type(
        self, 
        event_type: str, 
        limit: int = 100,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get events by type with optional date filter"""
        query = {"event_type": event_type}
        
        if start_date or end_date:
            query["date"] = {}
            if start_date:
                query["date"]["$gte"] = start_date
            if end_date:
                query["date"]["$lte"] = end_date
        
        cursor = self.db.intel_events.find(query).sort("date", -1).limit(limit)
        return await cursor.to_list(limit)
    
    async def get_upcoming_events(self, days: int = 30, limit: int = 100) -> List[Dict[str, Any]]:
        """Get upcoming events (unlocks, sales, etc.)"""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
        cursor = self.db.intel_events.find({
            "event_type": {"$in": ["unlock", "token_sale"]},
            "date": {"$gte": today}
        }).sort("date", 1).limit(limit)
        
        return await cursor.to_list(limit)
    
    async def search_events(
        self, 
        query: Optional[str] = None,
        event_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Search events with filters"""
        filter_query = {}
        
        if event_type:
            filter_query["event_type"] = event_type
        if entity_id:
            filter_query["entity_id"] = entity_id
        
        cursor = self.db.intel_events.find(filter_query).sort("date", -1).limit(limit)
        return await cursor.to_list(limit)
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get event statistics"""
        total = await self.db.intel_events.count_documents({})
        
        # Count by type
        pipeline = [
            {"$group": {"_id": "$event_type", "count": {"$sum": 1}}}
        ]
        cursor = self.db.intel_events.aggregate(pipeline)
        by_type = {doc["_id"]: doc["count"] async for doc in cursor}
        
        return {
            "total": total,
            "by_type": by_type
        }
    
    def _normalize_date(self, value: Any) -> str:
        """Normalize date to ISO format"""
        if value is None:
            return datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
        if isinstance(value, (int, float)):
            # Timestamp
            ts = value if value > 1e12 else value * 1000
            dt = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
            return dt.strftime("%Y-%m-%d")
        
        if isinstance(value, str):
            # Already string, normalize
            return value[:10]  # Take YYYY-MM-DD part
        
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")


# Singleton
event_engine: Optional[EventIntelligenceEngine] = None


def init_event_engine(db) -> EventIntelligenceEngine:
    """Initialize event engine"""
    global event_engine
    event_engine = EventIntelligenceEngine(db)
    return event_engine
