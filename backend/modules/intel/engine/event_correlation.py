"""
Event Correlation Engine

Connects events into chains to understand project lifecycles:
- Funding -> Token Sale -> Exchange Listing -> Unlock
- Identifies causal, temporal, and sequence relationships

Architecture:
Event Engine -> Correlation Engine -> Event Relations -> Project Timeline
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class RelationType(Enum):
    """Types of event relationships"""
    CAUSAL = "causal"       # A directly causes B (funding -> token_sale)
    TEMPORAL = "temporal"   # A happens before B in time (listing -> unlock)
    SEQUENCE = "sequence"   # A is part of sequence with B (unlock #1 -> unlock #2)
    RELATED = "related"     # A and B are connected (funding -> investor_entry)
    DUPLICATE = "duplicate" # A and B are same event from different sources


@dataclass
class EventRelation:
    """Represents a relationship between two events"""
    from_event_id: str
    to_event_id: str
    relation_type: RelationType
    confidence: float
    entity_id: str
    metadata: Dict[str, Any] = None


# Correlation rules: (from_type, to_type) -> relation_type
CORRELATION_RULES = {
    ("funding", "token_sale"): RelationType.CAUSAL,
    ("funding", "exchange_listing"): RelationType.SEQUENCE,
    ("token_sale", "exchange_listing"): RelationType.SEQUENCE,
    ("exchange_listing", "unlock"): RelationType.TEMPORAL,
    ("funding", "investor_entry"): RelationType.RELATED,
    ("seed", "series_a"): RelationType.SEQUENCE,
    ("series_a", "series_b"): RelationType.SEQUENCE,
    ("series_b", "series_c"): RelationType.SEQUENCE,
    ("private_sale", "public_sale"): RelationType.SEQUENCE,
    ("unlock", "unlock"): RelationType.SEQUENCE,
}

# Time windows for correlation (days)
CORRELATION_WINDOWS = {
    ("funding", "token_sale"): 365,      # Funding usually precedes sale by up to 1 year
    ("funding", "exchange_listing"): 180, # Listing often 6 months after funding
    ("token_sale", "exchange_listing"): 90, # Listing within 3 months of sale
    ("exchange_listing", "unlock"): 365,  # Unlocks happen over long periods
}


class EventCorrelationEngine:
    """
    Engine for correlating events and building relationship graphs.
    
    Creates intel_event_relations collection with connections between events.
    """
    
    def __init__(self, db=None):
        self.db = db
        self.relations_created = 0
        self.entities_processed = 0
    
    async def correlate_entity_events(self, entity_id: str) -> List[Dict]:
        """
        Correlate all events for a specific entity.
        
        Returns list of created relations.
        """
        if self.db is None:
            return []
        
        # Get all events for entity, sorted by date
        cursor = self.db.intel_events.find(
            {"entity_id": entity_id},
            {"_id": 0}
        ).sort("date", 1)
        
        events = await cursor.to_list(500)
        
        if len(events) < 2:
            return []
        
        relations = []
        
        # Compare each pair of events
        for i, event_a in enumerate(events):
            for event_b in events[i+1:]:
                relation = self._detect_relation(event_a, event_b)
                
                if relation:
                    relations.append(relation)
        
        # Store relations
        if relations:
            await self._store_relations(relations)
        
        self.entities_processed += 1
        self.relations_created += len(relations)
        
        logger.info(f"[Correlation] Entity {entity_id}: {len(relations)} relations found")
        
        return [self._relation_to_dict(r) for r in relations]
    
    def _detect_relation(self, event_a: Dict, event_b: Dict) -> Optional[EventRelation]:
        """
        Detect if there's a meaningful relationship between two events.
        """
        type_a = event_a.get("event_type", "").lower()
        type_b = event_b.get("event_type", "").lower()
        
        # Check if this pair has a defined correlation rule
        rule_key = (type_a, type_b)
        relation_type = CORRELATION_RULES.get(rule_key)
        
        if not relation_type:
            return None
        
        # Check time window
        date_a = event_a.get("date")
        date_b = event_b.get("date")
        
        if date_a and date_b:
            # Parse dates if strings
            if isinstance(date_a, str):
                try:
                    date_a = datetime.fromisoformat(date_a.replace("Z", "+00:00"))
                except:
                    date_a = None
            if isinstance(date_b, str):
                try:
                    date_b = datetime.fromisoformat(date_b.replace("Z", "+00:00"))
                except:
                    date_b = None
            
            if date_a and date_b:
                # Handle timestamps
                if isinstance(date_a, (int, float)):
                    date_a = datetime.fromtimestamp(date_a if date_a < 1e12 else date_a/1000, tz=timezone.utc)
                if isinstance(date_b, (int, float)):
                    date_b = datetime.fromtimestamp(date_b if date_b < 1e12 else date_b/1000, tz=timezone.utc)
                
                days_diff = abs((date_b - date_a).days) if hasattr(date_a, 'days') or hasattr(date_b, 'days') else 0
                
                # Get max window for this pair
                max_window = CORRELATION_WINDOWS.get(rule_key, 365)
                
                if days_diff > max_window:
                    return None
        
        # Calculate confidence based on time proximity and source overlap
        confidence = self._calculate_relation_confidence(event_a, event_b, relation_type)
        
        return EventRelation(
            from_event_id=event_a.get("id", event_a.get("event_id", "")),
            to_event_id=event_b.get("id", event_b.get("event_id", "")),
            relation_type=relation_type,
            confidence=confidence,
            entity_id=event_a.get("entity_id", ""),
            metadata={
                "from_type": type_a,
                "to_type": type_b,
                "from_date": str(event_a.get("date", "")),
                "to_date": str(event_b.get("date", ""))
            }
        )
    
    def _calculate_relation_confidence(
        self, 
        event_a: Dict, 
        event_b: Dict, 
        relation_type: RelationType
    ) -> float:
        """Calculate confidence score for a relation."""
        confidence = 0.7  # Base confidence
        
        # Boost for same entity
        if event_a.get("entity_id") == event_b.get("entity_id"):
            confidence += 0.1
        
        # Boost for overlapping sources
        sources_a = set(event_a.get("sources", []))
        sources_b = set(event_b.get("sources", []))
        if sources_a & sources_b:
            confidence += 0.1
        
        # Boost for causal relations (strongest type)
        if relation_type == RelationType.CAUSAL:
            confidence += 0.05
        
        return min(1.0, confidence)
    
    async def _store_relations(self, relations: List[EventRelation]):
        """Store relations in database."""
        if not self.db or not relations:
            return
        
        docs = [self._relation_to_dict(r) for r in relations]
        
        # Use bulk upsert
        from pymongo import UpdateOne
        
        operations = [
            UpdateOne(
                {
                    "from_event_id": doc["from_event_id"],
                    "to_event_id": doc["to_event_id"]
                },
                {"$set": doc},
                upsert=True
            )
            for doc in docs
        ]
        
        if operations:
            await self.db.intel_event_relations.bulk_write(operations)
    
    def _relation_to_dict(self, relation: EventRelation) -> Dict:
        """Convert relation to dictionary."""
        return {
            "from_event_id": relation.from_event_id,
            "to_event_id": relation.to_event_id,
            "relation_type": relation.relation_type.value,
            "confidence": relation.confidence,
            "entity_id": relation.entity_id,
            "metadata": relation.metadata or {},
            "created_at": datetime.now(timezone.utc).isoformat()
        }
    
    async def correlate_all_entities(self, limit: int = 1000) -> Dict[str, Any]:
        """
        Run correlation for all entities with events.
        """
        if self.db is None:
            return {"error": "No database connection"}
        
        start_time = datetime.now(timezone.utc)
        
        # Get unique entities with events
        pipeline = [
            {"$group": {"_id": "$entity_id"}},
            {"$limit": limit}
        ]
        
        cursor = self.db.intel_events.aggregate(pipeline)
        entities = [doc["_id"] async for doc in cursor if doc["_id"]]
        
        total_relations = 0
        processed = 0
        errors = []
        
        for entity_id in entities:
            try:
                relations = await self.correlate_entity_events(entity_id)
                total_relations += len(relations)
                processed += 1
            except Exception as e:
                errors.append(f"{entity_id}: {str(e)}")
                logger.error(f"[Correlation] Error for {entity_id}: {e}")
        
        elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
        
        return {
            "entities_processed": processed,
            "relations_created": total_relations,
            "elapsed_sec": round(elapsed, 2),
            "errors": errors[:10]  # Limit error list
        }
    
    async def get_entity_timeline(self, entity_id: str) -> Dict[str, Any]:
        """
        Get full timeline with relations for an entity.
        
        Returns events connected by their relationships.
        """
        if self.db is None:
            return {"error": "No database connection"}
        
        # Get events
        events_cursor = self.db.intel_events.find(
            {"entity_id": entity_id},
            {"_id": 0}
        ).sort("date", 1)
        events = await events_cursor.to_list(100)
        
        # Get relations
        relations_cursor = self.db.intel_event_relations.find(
            {"entity_id": entity_id},
            {"_id": 0}
        )
        relations = await relations_cursor.to_list(500)
        
        return {
            "entity_id": entity_id,
            "event_count": len(events),
            "relation_count": len(relations),
            "events": events,
            "relations": relations,
            "lifecycle": self._build_lifecycle(events, relations)
        }
    
    def _build_lifecycle(self, events: List[Dict], relations: List[Dict]) -> List[Dict]:
        """Build simplified lifecycle from events and relations."""
        if not events:
            return []
        
        lifecycle = []
        seen_types = set()
        
        for event in events:
            event_type = event.get("event_type", "unknown")
            if event_type not in seen_types:
                lifecycle.append({
                    "stage": event_type,
                    "date": event.get("date"),
                    "event_id": event.get("id", event.get("event_id"))
                })
                seen_types.add(event_type)
        
        return lifecycle
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get correlation engine statistics."""
        if self.db is None:
            return {"error": "No database connection"}
        
        total_relations = await self.db.intel_event_relations.count_documents({})
        
        # Relations by type
        pipeline = [
            {"$group": {"_id": "$relation_type", "count": {"$sum": 1}}}
        ]
        cursor = self.db.intel_event_relations.aggregate(pipeline)
        by_type = {doc["_id"]: doc["count"] async for doc in cursor}
        
        # Entities with relations
        pipeline = [
            {"$group": {"_id": "$entity_id"}},
            {"$count": "total"}
        ]
        cursor = self.db.intel_event_relations.aggregate(pipeline)
        entities_result = await cursor.to_list(1)
        entities_with_relations = entities_result[0]["total"] if entities_result else 0
        
        return {
            "total_relations": total_relations,
            "by_type": by_type,
            "entities_with_relations": entities_with_relations,
            "session_stats": {
                "entities_processed": self.entities_processed,
                "relations_created": self.relations_created
            }
        }


# Singleton instance
correlation_engine: Optional[EventCorrelationEngine] = None


def init_correlation_engine(db):
    """Initialize correlation engine."""
    global correlation_engine
    correlation_engine = EventCorrelationEngine(db)
    return correlation_engine


def get_correlation_engine():
    """Get correlation engine instance."""
    return correlation_engine
