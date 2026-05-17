"""
Intel Entities & Events
=======================
Core intelligence layer for tracking entities (projects, investors, persons)
and correlating events across the crypto ecosystem.

Entities: Unified view of all tracked crypto entities
Events: Significant occurrences (funding, unlocks, launches, etc.)
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional
from enum import Enum
import logging
import hashlib

logger = logging.getLogger(__name__)


class EntityType(str, Enum):
    PROJECT = "project"
    INVESTOR = "investor"
    FUND = "fund"
    PERSON = "person"
    EXCHANGE = "exchange"
    PROTOCOL = "protocol"


class EventType(str, Enum):
    FUNDING_ROUND = "funding_round"
    TOKEN_UNLOCK = "token_unlock"
    TOKEN_LAUNCH = "token_launch"
    LISTING = "listing"
    AIRDROP = "airdrop"
    PARTNERSHIP = "partnership"
    PROTOCOL_UPDATE = "protocol_update"
    GOVERNANCE = "governance"
    MARKET_MOVE = "market_move"
    TEAM_CHANGE = "team_change"


class EventSeverity(str, Enum):
    CRITICAL = "critical"  # Major market impact
    HIGH = "high"          # Significant event
    MEDIUM = "medium"      # Notable
    LOW = "low"            # Minor


class IntelEntitiesService:
    """Service for managing intel entities"""
    
    def __init__(self, db):
        self.db = db
    
    async def create_entity(self, entity: Dict) -> str:
        """Create or update an entity"""
        now = datetime.now(timezone.utc).isoformat()
        
        entity_id = entity.get("id") or self._generate_id(
            entity.get("type", "unknown"),
            entity.get("name", "")
        )
        
        doc = {
            "id": entity_id,
            "type": entity.get("type"),
            "name": entity.get("name"),
            "slug": entity.get("slug") or entity.get("name", "").lower().replace(" ", "-"),
            "symbol": entity.get("symbol"),
            "description": entity.get("description"),
            "logo": entity.get("logo"),
            "website": entity.get("website"),
            "twitter": entity.get("twitter"),
            "category": entity.get("category"),
            "tags": entity.get("tags", []),
            "metadata": entity.get("metadata", {}),
            "sources": entity.get("sources", []),
            "trust_score": entity.get("trust_score", 0.5),
            "created_at": entity.get("created_at") or now,
            "updated_at": now
        }
        
        await self.db.intel_entities.update_one(
            {"id": entity_id},
            {"$set": doc},
            upsert=True
        )
        
        return entity_id
    
    async def get_entity(self, entity_id: str) -> Optional[Dict]:
        """Get entity by ID"""
        return await self.db.intel_entities.find_one(
            {"id": entity_id},
            {"_id": 0}
        )
    
    async def search_entities(
        self,
        query: str,
        entity_type: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict]:
        """Search entities"""
        regex = {"$regex": query, "$options": "i"}
        filter_query = {
            "$or": [
                {"name": regex},
                {"symbol": regex},
                {"slug": regex}
            ]
        }
        
        if entity_type:
            filter_query["type"] = entity_type
        
        entities = await self.db.intel_entities.find(
            filter_query,
            {"_id": 0}
        ).limit(limit).to_list(limit)
        
        return entities
    
    async def list_entities(
        self,
        entity_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """List entities with pagination"""
        query = {}
        if entity_type:
            query["type"] = entity_type
        
        total = await self.db.intel_entities.count_documents(query)
        entities = await self.db.intel_entities.find(
            query,
            {"_id": 0}
        ).skip(offset).limit(limit).to_list(limit)
        
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "entities": entities
        }
    
    async def sync_entities_from_sources(self) -> Dict[str, int]:
        """Sync entities from all source collections"""
        synced = {"projects": 0, "investors": 0, "persons": 0, "protocols": 0}
        
        # Sync from intel_projects
        async for project in self.db.intel_projects.find({}, {"_id": 0}):
            await self.create_entity({
                "id": f"project:{project.get('key', project.get('slug', ''))}",
                "type": EntityType.PROJECT,
                "name": project.get("name"),
                "slug": project.get("slug"),
                "symbol": project.get("symbol"),
                "category": project.get("category"),
                "sources": ["intel_projects"]
            })
            synced["projects"] += 1
        
        # Sync from intel_investors
        async for investor in self.db.intel_investors.find({}, {"_id": 0}):
            await self.create_entity({
                "id": f"investor:{investor.get('id', investor.get('slug', ''))}",
                "type": EntityType.INVESTOR,
                "name": investor.get("name"),
                "slug": investor.get("slug"),
                "logo": investor.get("logo"),
                "category": investor.get("type"),
                "metadata": {
                    "portfolio_count": investor.get("portfolio_count"),
                    "investments_count": investor.get("investments_count")
                },
                "sources": ["intel_investors"]
            })
            synced["investors"] += 1
        
        # Sync from intel_persons
        async for person in self.db.intel_persons.find({}, {"_id": 0}):
            await self.create_entity({
                "id": f"person:{person.get('id', person.get('slug', ''))}",
                "type": EntityType.PERSON,
                "name": person.get("name"),
                "slug": person.get("slug"),
                "logo": person.get("avatar"),
                "twitter": person.get("twitter"),
                "metadata": {
                    "title": person.get("title"),
                    "bio": person.get("bio")
                },
                "sources": ["intel_persons"]
            })
            synced["persons"] += 1
        
        # Sync from defi_protocols (if exists)
        if await self.db.list_collection_names() and "defi_protocols" in await self.db.list_collection_names():
            async for protocol in self.db.defi_protocols.find({}, {"_id": 0}):
                await self.create_entity({
                    "id": f"protocol:{protocol.get('slug', '')}",
                    "type": EntityType.PROTOCOL,
                    "name": protocol.get("name"),
                    "slug": protocol.get("slug"),
                    "symbol": protocol.get("symbol"),
                    "logo": protocol.get("logo"),
                    "category": protocol.get("category"),
                    "metadata": {
                        "tvl": protocol.get("tvl"),
                        "chains": protocol.get("chains")
                    },
                    "sources": ["defi_protocols"]
                })
                synced["protocols"] += 1
        
        return synced
    
    def _generate_id(self, entity_type: str, name: str) -> str:
        """Generate unique entity ID"""
        hash_input = f"{entity_type}:{name}".lower()
        short_hash = hashlib.md5(hash_input.encode()).hexdigest()[:8]
        return f"{entity_type}:{short_hash}"


class IntelEventsService:
    """Service for managing intel events"""
    
    def __init__(self, db):
        self.db = db
    
    async def create_event(self, event: Dict) -> str:
        """Create a new event"""
        now = datetime.now(timezone.utc).isoformat()
        
        event_id = event.get("id") or self._generate_id(
            event.get("type", "unknown"),
            event.get("title", ""),
            event.get("date", now)
        )
        
        doc = {
            "id": event_id,
            "type": event.get("type"),
            "title": event.get("title"),
            "description": event.get("description"),
            "severity": event.get("severity", EventSeverity.MEDIUM),
            "date": event.get("date", now),
            # Related entities
            "entities": event.get("entities", []),  # List of entity IDs
            "primary_entity": event.get("primary_entity"),
            # Event data
            "data": event.get("data", {}),
            "impact_score": event.get("impact_score", 0.5),
            # Source tracking
            "source": event.get("source"),
            "source_url": event.get("source_url"),
            "verified": event.get("verified", False),
            # Timestamps
            "created_at": now,
            "updated_at": now
        }
        
        await self.db.intel_events.update_one(
            {"id": event_id},
            {"$set": doc},
            upsert=True
        )
        
        return event_id
    
    async def get_event(self, event_id: str) -> Optional[Dict]:
        """Get event by ID"""
        return await self.db.intel_events.find_one(
            {"id": event_id},
            {"_id": 0}
        )
    
    async def list_events(
        self,
        event_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        severity: Optional[str] = None,
        days: int = 30,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """List events with filters"""
        query = {}
        
        if event_type:
            query["type"] = event_type
        if entity_id:
            query["$or"] = [
                {"entities": entity_id},
                {"primary_entity": entity_id}
            ]
        if severity:
            query["severity"] = severity
        
        # Date filter
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        query["date"] = {"$gte": cutoff}
        
        total = await self.db.intel_events.count_documents(query)
        events = await self.db.intel_events.find(
            query,
            {"_id": 0}
        ).sort("date", -1).skip(offset).limit(limit).to_list(limit)
        
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "events": events
        }
    
    async def get_upcoming_events(self, days: int = 30, limit: int = 20) -> List[Dict]:
        """Get upcoming events"""
        now = datetime.now(timezone.utc).isoformat()
        future = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()
        
        events = await self.db.intel_events.find(
            {"date": {"$gte": now, "$lte": future}},
            {"_id": 0}
        ).sort("date", 1).limit(limit).to_list(limit)
        
        return events
    
    async def sync_events_from_sources(self) -> Dict[str, int]:
        """Generate events from existing data sources"""
        synced = {"funding": 0, "unlocks": 0, "activities": 0}
        now = datetime.now(timezone.utc)
        
        # Generate events from funding rounds
        async for funding in self.db.intel_funding.find({}, {"_id": 0}):
            await self.create_event({
                "id": f"event:funding:{funding.get('id', '')}",
                "type": EventType.FUNDING_ROUND,
                "title": f"{funding.get('project', 'Unknown')} raises ${funding.get('raised_usd', 0)/1e6:.1f}M in {funding.get('round_type', 'funding')}",
                "description": f"Investors: {', '.join(funding.get('investors', [])[:3])}",
                "severity": self._calc_funding_severity(funding.get("raised_usd", 0)),
                "date": funding.get("round_date") or funding.get("created_at"),
                "primary_entity": f"project:{funding.get('project', '').lower().replace(' ', '-')}",
                "entities": [f"investor:{inv.lower().replace(' ', '-')}" for inv in funding.get("investors", [])[:5]],
                "data": {
                    "raised_usd": funding.get("raised_usd"),
                    "round_type": funding.get("round_type"),
                    "valuation": funding.get("valuation")
                },
                "source": funding.get("source"),
                "verified": True
            })
            synced["funding"] += 1
        
        # Generate events from token unlocks
        async for unlock in self.db.token_unlocks.find({}, {"_id": 0}):
            unlock_date = unlock.get("date") or unlock.get("unlock_date")
            if not unlock_date:
                continue
            
            await self.create_event({
                "id": f"event:unlock:{unlock.get('id', '')}",
                "type": EventType.TOKEN_UNLOCK,
                "title": f"{unlock.get('symbol', '?')} token unlock: {unlock.get('percent_supply', 0):.1f}% of supply",
                "description": f"Category: {unlock.get('category', 'Unknown')}",
                "severity": self._calc_unlock_severity(unlock.get("percent_supply", 0)),
                "date": unlock_date,
                "primary_entity": f"project:{unlock.get('project_id', unlock.get('symbol', '').lower())}",
                "data": {
                    "percent_supply": unlock.get("percent_supply"),
                    "amount_usd": unlock.get("amount_usd"),
                    "category": unlock.get("category")
                },
                "source": unlock.get("source"),
                "verified": True
            })
            synced["unlocks"] += 1
        
        # Generate events from crypto activities (airdrops, launches)
        async for activity in self.db.crypto_activities.find({}, {"_id": 0}):
            event_type = EventType.AIRDROP if activity.get("activity_type") == "airdrop" else EventType.TOKEN_LAUNCH
            
            await self.create_event({
                "id": f"event:activity:{activity.get('id', '')}",
                "type": event_type,
                "title": f"{activity.get('project_name', 'Unknown')}: {activity.get('title', activity.get('activity_type', ''))}",
                "description": activity.get("description", "")[:200],
                "severity": EventSeverity.MEDIUM,
                "date": activity.get("created_at") or now.isoformat(),
                "primary_entity": f"project:{activity.get('project_id', activity.get('project_name', '').lower().replace(' ', '-'))}",
                "data": {
                    "activity_type": activity.get("activity_type"),
                    "status": activity.get("status"),
                    "estimated_value": activity.get("estimated_value")
                },
                "source": activity.get("source"),
                "verified": activity.get("verified", False)
            })
            synced["activities"] += 1
        
        return synced
    
    def _calc_funding_severity(self, amount_usd: float) -> str:
        """Calculate funding event severity"""
        if amount_usd >= 100_000_000:
            return EventSeverity.CRITICAL
        elif amount_usd >= 50_000_000:
            return EventSeverity.HIGH
        elif amount_usd >= 10_000_000:
            return EventSeverity.MEDIUM
        else:
            return EventSeverity.LOW
    
    def _calc_unlock_severity(self, percent: float) -> str:
        """Calculate unlock event severity"""
        if percent >= 10:
            return EventSeverity.CRITICAL
        elif percent >= 5:
            return EventSeverity.HIGH
        elif percent >= 2:
            return EventSeverity.MEDIUM
        else:
            return EventSeverity.LOW
    
    def _generate_id(self, event_type: str, title: str, date: str) -> str:
        """Generate unique event ID"""
        hash_input = f"{event_type}:{title}:{date}"
        short_hash = hashlib.md5(hash_input.encode()).hexdigest()[:12]
        return f"event:{short_hash}"
