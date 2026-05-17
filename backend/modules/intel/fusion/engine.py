"""
Data Fusion Engine
==================

Главный движок для объединения данных из разных источников.

Логика:
1. Entity Fusion - объединение разных названий в одну сущность
2. Event Fusion - объединение событий из разных источников
3. Signal Fusion - объединение market signals
"""

import logging
import hashlib
from typing import Optional, Dict, List, Any, Tuple
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorDatabase

from .models import (
    FusedEntity, FusedEvent, FusedSignal,
    EventType, SignalType, FusionCandidate
)

logger = logging.getLogger(__name__)

# Similarity weights for different event types
FUSION_WEIGHTS = {
    "funding": {
        "same_project": 0.35,
        "same_date": 0.20,
        "same_amount": 0.20,
        "same_investors": 0.15,
        "title_similarity": 0.10
    },
    "unlock": {
        "same_project": 0.40,
        "same_date": 0.25,
        "same_percent": 0.20,
        "same_category": 0.15
    },
    "activity": {
        "same_project": 0.40,
        "same_type": 0.25,
        "same_date_window": 0.20,
        "title_similarity": 0.15
    },
    "news": {
        "same_project": 0.30,
        "same_date": 0.20,
        "title_similarity": 0.35,
        "content_similarity": 0.15
    }
}

MERGE_THRESHOLD = 0.75
PROBABLE_THRESHOLD = 0.50


class DataFusionEngine:
    """
    Data Fusion Engine - объединяет данные из разных источников.
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.fused_entities = db.fused_entities
        self.fused_events = db.fused_events
        self.fused_signals = db.fused_signals
        self.fusion_candidates = db.fusion_candidates
        self.fusion_rules = db.fusion_rules
        
    async def init_indexes(self):
        """Create necessary indexes"""
        try:
            await self.fused_entities.create_index("canonical_id", unique=True)
            await self.fused_entities.create_index("entity_type")
            await self.fused_entities.create_index("sources")
            
            await self.fused_events.create_index("canonical_entity_id")
            await self.fused_events.create_index("event_type")
            await self.fused_events.create_index([("date", -1)])
            await self.fused_events.create_index("confidence")
            
            await self.fused_signals.create_index("asset_id")
            await self.fused_signals.create_index("signal_type")
            await self.fused_signals.create_index([("date", -1)])
        except Exception as e:
            logger.debug(f"Index creation skipped: {e}")
    
    # ═══════════════════════════════════════════════════════════════
    # ENTITY FUSION
    # ═══════════════════════════════════════════════════════════════
    
    async def fuse_entity(
        self,
        name: str,
        entity_type: str,
        symbol: Optional[str] = None,
        source: str = "unknown",
        source_id: Optional[str] = None,
        metadata: Dict = None
    ) -> FusedEntity:
        """
        Fuse entity from different sources into canonical entity.
        """
        canonical_id = self._generate_canonical_id(name, symbol)
        
        # Try to find existing
        existing = await self.fused_entities.find_one({"canonical_id": canonical_id})
        
        if existing:
            # Update existing entity - correctly format the update query
            update_ops = {"$set": {"updated_at": datetime.now(timezone.utc).isoformat()}}
            
            if source not in existing.get("sources", []):
                update_ops["$addToSet"] = {
                    "sources": source,
                    "source_ids": source_id or canonical_id
                }
            
            if name.lower() not in [a.lower() for a in existing.get("aliases", [])]:
                if "$addToSet" not in update_ops:
                    update_ops["$addToSet"] = {}
                update_ops["$addToSet"]["aliases"] = name
            
            await self.fused_entities.update_one(
                {"canonical_id": canonical_id},
                update_ops
            )
            
            existing["_id"] = str(existing["_id"])
            return FusedEntity(**existing)
        
        # Create new fused entity
        entity_data = {
            "id": f"fused_{entity_type}_{canonical_id}",
            "entity_type": entity_type,
            "canonical_id": canonical_id,
            "name": name,
            "symbol": symbol.upper() if symbol else None,
            "source_ids": [source_id or canonical_id],
            "sources": [source],
            "aliases": [name],
            "confidence": 1.0,
            "metadata": metadata or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        await self.fused_entities.insert_one(entity_data)
        logger.info(f"[Fusion] Created entity: {canonical_id}")
        
        return FusedEntity(**entity_data)
    
    async def find_entity(
        self,
        query: str,
        entity_type: Optional[str] = None
    ) -> Optional[FusedEntity]:
        """Find fused entity by any identifier"""
        filter_query = {
            "$or": [
                {"canonical_id": query.lower()},
                {"symbol": query.upper()},
                {"name": {"$regex": f"^{query}$", "$options": "i"}},
                {"aliases": {"$regex": f"^{query}$", "$options": "i"}}
            ]
        }
        
        if entity_type:
            filter_query["entity_type"] = entity_type
        
        doc = await self.fused_entities.find_one(filter_query)
        if doc:
            doc["_id"] = str(doc["_id"])
            return FusedEntity(**doc)
        return None
    
    # ═══════════════════════════════════════════════════════════════
    # EVENT FUSION
    # ═══════════════════════════════════════════════════════════════
    
    async def fuse_funding_events(self) -> Dict[str, Any]:
        """Fuse funding events from different sources"""
        results = {"fused": 0, "candidates": 0}
        
        # Get all funding events from different collections
        funding_sources = [
            ("intel_funding", "cryptorank"),
            ("funding_rounds", "seed"),
        ]
        
        all_events = []
        for collection, source in funding_sources:
            cursor = self.db[collection].find({})
            async for doc in cursor:
                doc["_source"] = source
                doc["_collection"] = collection
                all_events.append(doc)
        
        # Group by project
        by_project = {}
        for event in all_events:
            project_key = (
                event.get("project", "").lower() or 
                event.get("project_name", "").lower() or
                event.get("symbol", "").lower()
            )
            if project_key:
                if project_key not in by_project:
                    by_project[project_key] = []
                by_project[project_key].append(event)
        
        # Fuse events within each project
        for project_key, events in by_project.items():
            if len(events) < 2:
                continue
            
            # Find fusion candidates
            candidates = await self._find_funding_candidates(events)
            results["candidates"] += len(candidates)
            
            # Fuse high-confidence matches
            for candidate in candidates:
                if candidate["score"] >= MERGE_THRESHOLD:
                    await self._create_fused_funding_event(candidate)
                    results["fused"] += 1
        
        logger.info(f"[Fusion] Fused {results['fused']} funding events")
        return results
    
    async def _find_funding_candidates(
        self,
        events: List[Dict]
    ) -> List[Dict]:
        """Find funding event fusion candidates"""
        candidates = []
        weights = FUSION_WEIGHTS["funding"]
        
        for i, event_a in enumerate(events):
            for event_b in events[i+1:]:
                # Skip if from same source
                if event_a.get("_source") == event_b.get("_source"):
                    continue
                
                score = 0.0
                reasons = []
                
                # Same project (already grouped, so always 1.0)
                score += weights["same_project"]
                reasons.append("same_project")
                
                # Same date (within 7 days)
                date_a = self._parse_date(event_a.get("round_date") or event_a.get("date"))
                date_b = self._parse_date(event_b.get("round_date") or event_b.get("date"))
                
                if date_a and date_b:
                    days_diff = abs((date_a - date_b).days)
                    if days_diff <= 7:
                        score += weights["same_date"]
                        reasons.append(f"same_date ({days_diff}d)")
                
                # Same amount (within 20%)
                amount_a = event_a.get("raised_usd") or event_a.get("amount_usd") or 0
                amount_b = event_b.get("raised_usd") or event_b.get("amount_usd") or 0
                
                if amount_a > 0 and amount_b > 0:
                    ratio = min(amount_a, amount_b) / max(amount_a, amount_b)
                    if ratio >= 0.8:
                        score += weights["same_amount"]
                        reasons.append(f"same_amount ({ratio:.0%})")
                
                # Same investors
                investors_a = set(event_a.get("investors", []))
                investors_b = set(event_b.get("investors", []))
                
                if investors_a and investors_b:
                    overlap = len(investors_a & investors_b) / len(investors_a | investors_b)
                    if overlap > 0:
                        score += weights["same_investors"] * overlap
                        reasons.append(f"investor_overlap ({overlap:.0%})")
                
                if score >= PROBABLE_THRESHOLD:
                    candidates.append({
                        "source_a": event_a,
                        "source_b": event_b,
                        "score": score,
                        "reasons": reasons,
                        "action": "merge" if score >= MERGE_THRESHOLD else "review"
                    })
        
        return candidates
    
    async def _create_fused_funding_event(self, candidate: Dict) -> str:
        """Create fused funding event from candidate"""
        event_a = candidate["source_a"]
        event_b = candidate["source_b"]
        
        # Merge data, preferring most complete
        project_name = event_a.get("project") or event_b.get("project")
        symbol = event_a.get("symbol") or event_b.get("symbol")
        
        # Find/create fused entity
        entity = await self.fuse_entity(
            name=project_name,
            entity_type="project",
            symbol=symbol,
            source="fusion"
        )
        
        # Calculate impact score based on amount
        amount = max(
            event_a.get("raised_usd", 0) or 0,
            event_b.get("raised_usd", 0) or 0
        )
        impact = self._calculate_funding_impact(amount)
        
        # Merge investors
        all_investors = list(set(
            event_a.get("investors", []) + 
            event_b.get("investors", [])
        ))
        
        fused_event = {
            "id": f"fused_funding_{entity.canonical_id}_{int(datetime.now().timestamp())}",
            "event_type": EventType.FUNDING.value,
            "canonical_entity_id": entity.canonical_id,
            "title": f"{project_name} raises ${amount/1e6:.1f}M",
            "description": f"Funding round confirmed from multiple sources",
            "date": self._parse_date(
                event_a.get("round_date") or event_b.get("round_date")
            ).isoformat() if self._parse_date(event_a.get("round_date") or event_b.get("round_date")) else datetime.now(timezone.utc).isoformat(),
            "sources": [
                {"source": event_a.get("_source"), "id": str(event_a.get("_id", ""))},
                {"source": event_b.get("_source"), "id": str(event_b.get("_id", ""))}
            ],
            "confidence": candidate["score"],
            "impact_score": impact,
            "payload": {
                "amount_usd": amount,
                "round_type": event_a.get("round_type") or event_b.get("round_type"),
                "investors": all_investors,
                "lead_investors": event_a.get("lead_investors", []) or event_b.get("lead_investors", []),
                "valuation_usd": event_a.get("valuation_usd") or event_b.get("valuation_usd")
            },
            "tags": ["funding", symbol.upper() if symbol else project_name.lower()],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        await self.fused_events.update_one(
            {"canonical_entity_id": entity.canonical_id, "event_type": EventType.FUNDING.value},
            {"$set": fused_event},
            upsert=True
        )
        
        return fused_event["id"]
    
    async def fuse_unlock_events(self) -> Dict[str, Any]:
        """Fuse unlock events from different sources"""
        results = {"fused": 0}
        
        # Get unlocks
        cursor = self.db.token_unlocks.find({})
        by_project = {}
        
        async for doc in cursor:
            project_key = (doc.get("project_id", "") or doc.get("symbol", "")).lower()
            if project_key:
                if project_key not in by_project:
                    by_project[project_key] = []
                by_project[project_key].append(doc)
        
        for project_key, events in by_project.items():
            # Create fused unlock events
            for event in events:
                entity = await self.fuse_entity(
                    name=event.get("project_name", project_key),
                    entity_type="project",
                    symbol=event.get("symbol"),
                    source="fusion"
                )
                
                amount_usd = event.get("amount_usd", 0) or 0
                percent = event.get("percent_supply", 0) or 0
                impact = self._calculate_unlock_impact(percent, amount_usd)
                
                fused_event = {
                    "id": f"fused_unlock_{entity.canonical_id}_{event.get('id', '')}",
                    "event_type": EventType.UNLOCK.value,
                    "canonical_entity_id": entity.canonical_id,
                    "title": f"{event.get('symbol', '')} Unlock: {percent:.1f}% supply",
                    "description": f"Token unlock of {percent:.1f}% supply (${amount_usd/1e6:.1f}M)",
                    "date": event.get("date", datetime.now(timezone.utc).isoformat()),
                    "sources": [{"source": event.get("source", "unknown"), "id": str(event.get("_id", ""))}],
                    "confidence": 0.9,
                    "impact_score": impact,
                    "payload": {
                        "amount_tokens": event.get("amount_tokens", 0),
                        "amount_usd": amount_usd,
                        "percent_supply": percent,
                        "category": event.get("category", "unknown"),
                        "days_until": event.get("days_until", 0)
                    },
                    "tags": ["unlock", event.get("symbol", "").upper(), event.get("category", "")],
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }
                
                await self.fused_events.update_one(
                    {"id": fused_event["id"]},
                    {"$set": fused_event},
                    upsert=True
                )
                results["fused"] += 1
        
        logger.info(f"[Fusion] Fused {results['fused']} unlock events")
        return results
    
    async def fuse_activity_events(self) -> Dict[str, Any]:
        """Fuse activity events (airdrops, testnets, etc)"""
        results = {"fused": 0}
        
        cursor = self.db.crypto_activities.find({})
        
        async for activity in cursor:
            project_name = activity.get("project_name", "") or activity.get("project_id", "")
            if not project_name:
                continue
            
            entity = await self.fuse_entity(
                name=project_name,
                entity_type="project",
                source="fusion"
            )
            
            # Calculate impact based on score
            score = activity.get("score", 50) or 50
            impact = min(100, int(score * 1.2))
            
            fused_event = {
                "id": f"fused_activity_{entity.canonical_id}_{activity.get('id', '')}",
                "event_type": EventType.ACTIVITY.value,
                "canonical_entity_id": entity.canonical_id,
                "title": activity.get("title", f"{project_name} Activity"),
                "description": activity.get("description", ""),
                "date": activity.get("start_date", datetime.now(timezone.utc).isoformat()),
                "sources": [{"source": activity.get("source", "unknown"), "id": str(activity.get("_id", ""))}],
                "confidence": 0.85,
                "impact_score": impact,
                "payload": {
                    "activity_type": activity.get("type", "unknown"),
                    "category": activity.get("category", "unknown"),
                    "status": activity.get("status", "active"),
                    "reward": activity.get("reward"),
                    "difficulty": activity.get("difficulty"),
                    "chain": activity.get("chain")
                },
                "tags": [
                    "activity",
                    activity.get("type", ""),
                    activity.get("category", ""),
                    entity.canonical_id
                ],
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            
            await self.fused_events.update_one(
                {"id": fused_event["id"]},
                {"$set": fused_event},
                upsert=True
            )
            results["fused"] += 1
        
        logger.info(f"[Fusion] Fused {results['fused']} activity events")
        return results
    
    # ═══════════════════════════════════════════════════════════════
    # SIGNAL FUSION
    # ═══════════════════════════════════════════════════════════════
    
    async def create_market_signal(
        self,
        asset_id: str,
        symbol: str,
        signal_type: SignalType,
        components: Dict[str, float],
        metadata: Dict = None
    ) -> FusedSignal:
        """Create fused market signal from components"""
        # Calculate overall score
        score = self._calculate_signal_score(components)
        
        signal = {
            "id": f"signal_{signal_type.value}_{symbol}_{int(datetime.now().timestamp())}",
            "signal_type": signal_type.value,
            "asset_id": asset_id,
            "symbol": symbol.upper(),
            "score": score,
            "components": components,
            "date": datetime.now(timezone.utc).isoformat(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat(),
            "metadata": metadata or {}
        }
        
        await self.fused_signals.insert_one(signal)
        logger.info(f"[Fusion] Created signal: {signal_type.value} for {symbol} (score: {score})")
        
        return FusedSignal(**signal)
    
    def _calculate_signal_score(self, components: Dict[str, float]) -> int:
        """Calculate overall signal score from components"""
        if not components:
            return 0
        
        # Weighted average of components
        weights = {
            "price_velocity": 0.25,
            "volume_spike": 0.25,
            "oi_spike": 0.20,
            "liq_burst": 0.15,
            "funding_shift": 0.15
        }
        
        total_weight = 0
        weighted_sum = 0
        
        for key, value in components.items():
            weight = weights.get(key, 0.1)
            weighted_sum += value * weight * 100
            total_weight += weight
        
        if total_weight > 0:
            return min(100, int(weighted_sum / total_weight))
        return 50
    
    # ═══════════════════════════════════════════════════════════════
    # UNIFIED FEED API
    # ═══════════════════════════════════════════════════════════════
    
    async def get_unified_feed(
        self,
        event_types: List[str] = None,
        entity_id: Optional[str] = None,
        min_impact: int = 0,
        min_confidence: float = 0,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """Get unified event feed"""
        query = {}
        
        if event_types:
            query["event_type"] = {"$in": event_types}
        
        if entity_id:
            query["canonical_entity_id"] = entity_id
        
        if min_impact > 0:
            query["impact_score"] = {"$gte": min_impact}
        
        if min_confidence > 0:
            query["confidence"] = {"$gte": min_confidence}
        
        total = await self.fused_events.count_documents(query)
        
        cursor = self.fused_events.find(query, {"_id": 0}).sort(
            [("date", -1)]
        ).skip(offset).limit(limit)
        
        events = []
        async for doc in cursor:
            events.append(doc)
        
        return {
            "ts": datetime.now(timezone.utc).isoformat(),
            "total": total,
            "limit": limit,
            "offset": offset,
            "events": events
        }
    
    async def get_entity_timeline(
        self,
        entity_id: str,
        limit: int = 50
    ) -> Dict[str, Any]:
        """Get event timeline for entity"""
        entity = await self.fused_entities.find_one(
            {"canonical_id": entity_id},
            {"_id": 0}
        )
        
        if not entity:
            return {"error": "Entity not found"}
        
        cursor = self.fused_events.find(
            {"canonical_entity_id": entity_id},
            {"_id": 0}
        ).sort([("date", -1)]).limit(limit)
        
        events = []
        async for doc in cursor:
            events.append(doc)
        
        return {
            "entity": entity,
            "events": events,
            "total_events": len(events)
        }
    
    async def get_top_signals(
        self,
        signal_type: Optional[str] = None,
        min_score: int = 50,
        limit: int = 20
    ) -> List[Dict]:
        """Get top active signals"""
        query = {
            "score": {"$gte": min_score},
            "expires_at": {"$gte": datetime.now(timezone.utc).isoformat()}
        }
        
        if signal_type:
            query["signal_type"] = signal_type
        
        cursor = self.fused_signals.find(query, {"_id": 0}).sort(
            [("score", -1)]
        ).limit(limit)
        
        signals = []
        async for doc in cursor:
            signals.append(doc)
        
        return signals
    
    # ═══════════════════════════════════════════════════════════════
    # FULL FUSION RUN
    # ═══════════════════════════════════════════════════════════════
    
    async def fuse_news_events(self) -> Dict[str, Any]:
        """
        Fuse news events from intel_events collection.
        Converts news articles into fused events for unified feed.
        """
        results = {"fused": 0, "candidates": 0}
        now = datetime.now(timezone.utc)
        
        try:
            # Get all news from intel_events
            cursor = self.db.intel_events.find(
                {"type": "news"},
                {"_id": 0}
            )
            
            async for event in cursor:
                results["candidates"] += 1
                
                # Generate fused event
                event_id = f"news_{event.get('id', '')}"
                
                # Parse date
                event_date = self._parse_date(event.get("date"))
                if not event_date:
                    event_date = now
                
                # Build fused event
                fused_doc = {
                    "id": event_id,
                    "event_type": "news_event",
                    "canonical_entity_id": event.get("entities", [None])[0] if event.get("entities") else None,
                    "title": event.get("title", ""),
                    "description": event.get("description", ""),
                    "date": event_date.isoformat(),
                    "sources": [{"source": event.get("source", "unknown"), "id": event.get("id")}],
                    "confidence": event.get("confidence", 0.8),
                    "impact_score": int(event.get("impact_score", 0.5) * 100),
                    "payload": {
                        "url": event.get("url", ""),
                        "category": event.get("category", "news"),
                        "entities": event.get("entities", []),
                        "raw_data": event.get("raw_data", {})
                    },
                    "created_at": now.isoformat(),
                    "updated_at": now.isoformat()
                }
                
                # Upsert
                await self.fused_events.update_one(
                    {"id": event_id},
                    {"$set": fused_doc},
                    upsert=True
                )
                results["fused"] += 1
            
            logger.info(f"[Fusion] News: fused {results['fused']} events")
            
        except Exception as e:
            logger.error(f"[Fusion] News fusion error: {e}")
            results["error"] = str(e)
        
        return results
    
    async def run_full_fusion(self) -> Dict[str, Any]:
        """Run full data fusion pipeline"""
        await self.init_indexes()
        
        results = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "funding": await self.fuse_funding_events(),
            "unlocks": await self.fuse_unlock_events(),
            "activities": await self.fuse_activity_events(),
            "news": await self.fuse_news_events()
        }
        
        # Count totals
        results["totals"] = {
            "fused_entities": await self.fused_entities.count_documents({}),
            "fused_events": await self.fused_events.count_documents({}),
            "fused_signals": await self.fused_signals.count_documents({})
        }
        
        logger.info(f"[Fusion] Full fusion complete: {results['totals']}")
        return results
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get fusion engine statistics"""
        return {
            "fused_entities": await self.fused_entities.count_documents({}),
            "fused_events": await self.fused_events.count_documents({}),
            "fused_signals": await self.fused_signals.count_documents({}),
            "events_by_type": await self._count_by_field(self.fused_events, "event_type"),
            "entities_by_type": await self._count_by_field(self.fused_entities, "entity_type")
        }
    
    async def _count_by_field(self, collection, field: str) -> Dict[str, int]:
        """Count documents grouped by field"""
        pipeline = [
            {"$group": {"_id": f"${field}", "count": {"$sum": 1}}}
        ]
        result = {}
        async for doc in collection.aggregate(pipeline):
            result[doc["_id"]] = doc["count"]
        return result
    
    # ═══════════════════════════════════════════════════════════════
    # HELPERS
    # ═══════════════════════════════════════════════════════════════
    
    def _generate_canonical_id(self, name: str, symbol: Optional[str] = None) -> str:
        """Generate canonical ID from name/symbol"""
        base = (symbol or name).lower().strip()
        # Remove common suffixes
        for suffix in [" protocol", " labs", " network", " finance", " dao", " token"]:
            if base.endswith(suffix):
                base = base[:-len(suffix)]
        # Keep only alphanumeric
        import re
        return re.sub(r'[^a-z0-9]', '', base)
    
    def _parse_date(self, date_value) -> Optional[datetime]:
        """Parse date from various formats"""
        if not date_value:
            return None
        
        if isinstance(date_value, datetime):
            return date_value
        
        if isinstance(date_value, (int, float)):
            # Assume milliseconds if > 1e12
            if date_value > 1e12:
                date_value = date_value / 1000
            return datetime.fromtimestamp(date_value, tz=timezone.utc)
        
        if isinstance(date_value, str):
            try:
                return datetime.fromisoformat(date_value.replace('Z', '+00:00'))
            except:
                pass
        
        return None
    
    def _calculate_funding_impact(self, amount_usd: float) -> int:
        """Calculate impact score for funding amount"""
        if amount_usd >= 500_000_000:
            return 95
        elif amount_usd >= 100_000_000:
            return 85
        elif amount_usd >= 50_000_000:
            return 75
        elif amount_usd >= 20_000_000:
            return 65
        elif amount_usd >= 10_000_000:
            return 55
        elif amount_usd >= 5_000_000:
            return 45
        else:
            return 35
    
    def _calculate_unlock_impact(self, percent: float, amount_usd: float) -> int:
        """Calculate impact score for unlock"""
        # Based on % of supply and USD value
        percent_score = min(50, int(percent * 5))  # 20% unlock = 100 points (capped at 50)
        value_score = self._calculate_funding_impact(amount_usd) // 2  # Half weight for value
        
        return min(100, percent_score + value_score)


# Singleton
_fusion_engine: Optional[DataFusionEngine] = None


def get_fusion_engine(db: AsyncIOMotorDatabase = None) -> DataFusionEngine:
    """Get or create fusion engine instance"""
    global _fusion_engine
    if db is not None:
        _fusion_engine = DataFusionEngine(db)
    return _fusion_engine
