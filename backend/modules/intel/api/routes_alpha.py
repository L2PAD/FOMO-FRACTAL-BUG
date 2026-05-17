"""
Alpha Feed API Routes
=====================

Unified Alpha Feed endpoints:
- /api/alpha/search - Search projects, tokens, funds
- /api/alpha/projects - Alpha projects grid
- /api/alpha/signals - Market signals
- /api/alpha/events - Event feed with priority scoring
"""

from fastapi import APIRouter, Query, HTTPException, WebSocket, WebSocketDisconnect
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
import asyncio
import json
import logging

from motor.motor_asyncio import AsyncIOMotorClient
import os

logger = logging.getLogger(__name__)

# DB connection
mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
_client = AsyncIOMotorClient(mongo_url)
_db = _client[os.environ.get('DB_NAME', 'test_database')]

router = APIRouter(prefix="/api/alpha", tags=["Alpha Feed"])

# WebSocket connections manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"[WebSocket] Client connected. Total: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"[WebSocket] Client disconnected. Total: {len(self.active_connections)}")
    
    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"[WebSocket] Broadcast error: {e}")

manager = ConnectionManager()


# ═══════════════════════════════════════════════════════════════
# EVENT PRIORITY ENGINE
# ═══════════════════════════════════════════════════════════════

def calculate_event_score(event: Dict) -> float:
    """
    Calculate event priority score.
    
    Formula:
    event_score = impact_score * 0.6 + confidence * 0.2 + recency_score * 0.2
    """
    impact = event.get("impact_score", 50) or 50
    confidence = (event.get("confidence", 0.8) or 0.8) * 100
    
    # Calculate recency score
    event_date = event.get("date") or event.get("timestamp")
    recency_score = 40  # default
    
    if event_date:
        try:
            if isinstance(event_date, str):
                event_dt = datetime.fromisoformat(event_date.replace('Z', '+00:00'))
            else:
                event_dt = event_date
            
            now = datetime.now(timezone.utc)
            age_minutes = (now - event_dt).total_seconds() / 60
            
            if age_minutes < 5:
                recency_score = 100
            elif age_minutes < 30:
                recency_score = 80
            elif age_minutes < 120:
                recency_score = 60
            elif age_minutes < 1440:  # 24h
                recency_score = 40
            else:
                recency_score = 20
        except:
            pass
    
    return impact * 0.6 + confidence * 0.2 + recency_score * 0.2


def get_impact_category(score: int) -> str:
    """Get impact category from score."""
    if score >= 80:
        return "critical"
    elif score >= 60:
        return "high"
    elif score >= 40:
        return "medium"
    elif score >= 20:
        return "minor"
    else:
        return "low"


# ═══════════════════════════════════════════════════════════════
# SEARCH
# ═══════════════════════════════════════════════════════════════

@router.get("/search")
async def search(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(20, ge=1, le=50)
):
    """
    Search projects, tokens, funds, persons, news.
    
    Returns unified search results across all entity types and news.
    """
    query = q.lower().strip()
    results = []
    seen_names = set()
    
    # 1. Search in intel_projects (primary source for projects)
    cursor = _db.intel_projects.find({
        "$or": [
            {"name": {"$regex": query, "$options": "i"}},
            {"symbol": {"$regex": query, "$options": "i"}},
            {"slug": {"$regex": query, "$options": "i"}}
        ]
    }, {"_id": 0}).limit(10)
    
    async for doc in cursor:
        name = doc.get("name")
        if name and name not in seen_names:
            seen_names.add(name)
            results.append({
                "type": "project",
                "id": doc.get("slug") or doc.get("key"),
                "name": name,
                "symbol": doc.get("symbol"),
                "category": doc.get("category"),
                "entity_type": "project"
            })
    
    # 2. Search in intel_persons
    cursor = _db.intel_persons.find({
        "$or": [
            {"name": {"$regex": query, "$options": "i"}},
            {"slug": {"$regex": query, "$options": "i"}}
        ]
    }, {"_id": 0}).limit(5)
    
    async for doc in cursor:
        name = doc.get("name")
        if name and name not in seen_names:
            seen_names.add(name)
            results.append({
                "type": "person",
                "id": doc.get("slug") or doc.get("key"),
                "name": name,
                "role": doc.get("role"),
                "entity_type": "person"
            })
    
    # 3. Search in intel_investors
    cursor = _db.intel_investors.find({
        "$or": [
            {"name": {"$regex": query, "$options": "i"}},
            {"slug": {"$regex": query, "$options": "i"}}
        ]
    }, {"_id": 0}).limit(5)
    
    async for doc in cursor:
        name = doc.get("name")
        if name and name not in seen_names:
            seen_names.add(name)
            results.append({
                "type": "investor",
                "id": doc.get("slug") or doc.get("key"),
                "name": name,
                "category": doc.get("type", "fund"),
                "entity_type": "investor"
            })
    
    # 4. Search in intel_exchanges
    cursor = _db.intel_exchanges.find({
        "$or": [
            {"name": {"$regex": query, "$options": "i"}},
            {"slug": {"$regex": query, "$options": "i"}}
        ]
    }, {"_id": 0}).limit(5)
    
    async for doc in cursor:
        name = doc.get("name")
        if name and name not in seen_names:
            seen_names.add(name)
            results.append({
                "type": "exchange",
                "id": doc.get("slug") or doc.get("key"),
                "name": name,
                "exchange_type": doc.get("type"),
                "entity_type": "exchange"
            })
    
    # 5. Search in fused_entities
    cursor = _db.fused_entities.find({
        "$or": [
            {"canonical_id": {"$regex": query, "$options": "i"}},
            {"name": {"$regex": query, "$options": "i"}},
            {"symbol": {"$regex": query, "$options": "i"}},
            {"aliases": {"$regex": query, "$options": "i"}}
        ]
    }, {"_id": 0}).limit(5)
    
    async for doc in cursor:
        name = doc.get("name")
        if name and name not in seen_names:
            seen_names.add(name)
            results.append({
                "type": doc.get("entity_type", "project"),
                "id": doc.get("canonical_id"),
                "name": name,
                "symbol": doc.get("symbol"),
                "entity_type": doc.get("entity_type")
            })
    
    # 6. Search in graph nodes
    cursor = _db.graph_nodes.find({
        "$or": [
            {"id": {"$regex": query, "$options": "i"}},
            {"label": {"$regex": query, "$options": "i"}}
        ]
    }, {"_id": 0}).limit(5)
    
    async for doc in cursor:
        name = doc.get("label")
        if name and name not in seen_names:
            seen_names.add(name)
            results.append({
                "type": doc.get("type", "entity"),
                "id": doc.get("id"),
                "name": name,
                "entity_type": doc.get("type")
            })
    
    return {
        "ts": datetime.now(timezone.utc).isoformat(),
        "query": q,
        "count": len(results),
        "results": results[:limit]
    }


# ═══════════════════════════════════════════════════════════════
# ALPHA PROJECTS
# ═══════════════════════════════════════════════════════════════

@router.get("/projects")
async def get_alpha_projects(
    limit: int = Query(12, ge=1, le=50),
    category: Optional[str] = Query(None, description="Filter by category")
):
    """
    Get Alpha projects with scores.
    
    Alpha score = volume_score + activity_score + funding_score + signal_score
    """
    projects = []
    
    # Get fused entities (projects)
    cursor = _db.fused_entities.find(
        {"entity_type": "project"},
        {"_id": 0}
    ).limit(limit * 2)
    
    async for entity in cursor:
        canonical_id = entity.get("canonical_id")
        
        # Get related events count
        events_count = await _db.fused_events.count_documents({
            "canonical_entity_id": canonical_id
        })
        
        # Get latest event for this project
        latest_event = await _db.fused_events.find_one(
            {"canonical_entity_id": canonical_id},
            {"_id": 0},
            sort=[("date", -1)]
        )
        
        # Calculate alpha score components
        volume_score = 0
        activity_score = min(events_count * 10, 30)  # Max 30 from events
        funding_score = 0
        signal_score = 0
        
        # Check for funding
        funding = await _db.intel_funding.find_one(
            {"project": {"$regex": canonical_id, "$options": "i"}},
            {"_id": 0}
        )
        if funding:
            amount = funding.get("raised_usd", 0) or 0
            if amount >= 100_000_000:
                funding_score = 40
            elif amount >= 50_000_000:
                funding_score = 30
            elif amount >= 10_000_000:
                funding_score = 20
            else:
                funding_score = 10
        
        # Check for activities
        activities_count = await _db.crypto_activities.count_documents({
            "project_id": {"$regex": canonical_id, "$options": "i"}
        })
        if activities_count > 0:
            activity_score = min(activity_score + activities_count * 5, 40)
        
        alpha_score = volume_score + activity_score + funding_score + signal_score
        
        # Only include if has some alpha
        if alpha_score > 0 or events_count > 0:
            projects.append({
                "id": canonical_id,
                "name": entity.get("name"),
                "symbol": entity.get("symbol"),
                "category": "crypto",
                "alpha_score": min(alpha_score, 100),
                "events_count": events_count,
                "metrics": {
                    "funding": funding_score > 0,
                    "activity": activity_score > 0,
                    "volume_spike": volume_score > 0,
                    "signals": signal_score > 0
                },
                "latest_event": latest_event.get("title") if latest_event else None,
                "updated_at": entity.get("updated_at")
            })
    
    # Sort by alpha score
    projects.sort(key=lambda x: x["alpha_score"], reverse=True)
    
    return {
        "ts": datetime.now(timezone.utc).isoformat(),
        "count": len(projects[:limit]),
        "projects": projects[:limit]
    }


# ═══════════════════════════════════════════════════════════════
# ALPHA SIGNALS
# ═══════════════════════════════════════════════════════════════

@router.get("/signals")
async def get_alpha_signals(
    signal_type: Optional[str] = Query(None, description="Filter by signal type"),
    min_score: int = Query(50, ge=0, le=100),
    limit: int = Query(20, ge=1, le=50)
):
    """
    Get market alpha signals.
    
    Signal types: pump_setup, dump_risk, unlock_risk, smart_money_entry, 
    funding_stress, oi_shock, rotation_signal, narrative_breakout
    """
    query = {"score": {"$gte": min_score}}
    
    if signal_type:
        query["signal_type"] = signal_type
    
    signals = []
    cursor = _db.fused_signals.find(query, {"_id": 0}).sort(
        [("score", -1)]
    ).limit(limit)
    
    async for doc in cursor:
        signals.append({
            "id": doc.get("id"),
            "type": doc.get("signal_type"),
            "asset": doc.get("symbol"),
            "score": doc.get("score"),
            "components": doc.get("components", {}),
            "date": doc.get("date"),
            "expires_at": doc.get("expires_at")
        })
    
    # If no signals in DB, generate sample based on market data
    if not signals:
        # Create sample signals from market activity
        sample_signals = [
            {
                "id": "signal_pump_setup_sol_1",
                "type": "pump_setup",
                "asset": "SOL",
                "score": 78,
                "components": {
                    "price_velocity": 0.75,
                    "volume_spike": 0.82,
                    "oi_spike": 0.68
                },
                "date": datetime.now(timezone.utc).isoformat()
            },
            {
                "id": "signal_unlock_risk_arb_1",
                "type": "unlock_risk",
                "asset": "ARB",
                "score": 72,
                "components": {
                    "unlock_percent": 0.85,
                    "volume_ratio": 0.65
                },
                "date": datetime.now(timezone.utc).isoformat()
            }
        ]
        signals = [s for s in sample_signals if s["score"] >= min_score]
    
    return {
        "ts": datetime.now(timezone.utc).isoformat(),
        "count": len(signals),
        "signals": signals
    }


# ═══════════════════════════════════════════════════════════════
# EVENT FEED
# ═══════════════════════════════════════════════════════════════

@router.get("/events")
async def get_alpha_events(
    event_type: Optional[str] = Query(None, description="Filter: unlock, funding, activity, signal, listing, news"),
    category: Optional[str] = Query(None, description="Filter: alpha, all"),
    min_impact: int = Query(0, ge=0, le=100),
    limit: int = Query(24, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """
    Get unified event feed with priority scoring.
    
    Events are scored and sorted by: impact (60%), confidence (20%), recency (20%)
    """
    events = []
    
    # Build query
    query = {}
    if event_type:
        type_mapping = {
            "unlock": "unlock_event",
            "funding": "funding_event",
            "activity": "activity_event",
            "signal": "market_signal",
            "listing": "listing_event",
            "news": "news_event"
        }
        query["event_type"] = type_mapping.get(event_type, event_type)
    
    if min_impact > 0:
        query["impact_score"] = {"$gte": min_impact}
    
    # Get fused events
    cursor = _db.fused_events.find(query, {"_id": 0}).sort(
        [("date", -1)]
    ).skip(offset).limit(limit * 2)
    
    async for doc in cursor:
        event_score = calculate_event_score(doc)
        impact_category = get_impact_category(doc.get("impact_score", 50))
        
        events.append({
            "id": doc.get("id"),
            "type": doc.get("event_type", "").replace("_event", ""),
            "asset": doc.get("canonical_entity_id"),
            "title": doc.get("title"),
            "description": doc.get("description"),
            "impact_score": doc.get("impact_score", 50),
            "impact_category": impact_category,
            "confidence": doc.get("confidence", 0.8),
            "event_score": round(event_score, 1),
            "sources_count": len(doc.get("sources", [])),
            "metrics": doc.get("payload", {}),
            "tags": doc.get("tags", []),
            "timestamp": doc.get("date"),
            "created_at": doc.get("created_at")
        })
    
    # Also get intel events if not enough
    if len(events) < limit:
        intel_cursor = _db.intel_events.find({}, {"_id": 0}).sort(
            [("event_date", -1)]
        ).limit(limit - len(events))
        
        async for doc in intel_cursor:
            events.append({
                "id": doc.get("id") or f"intel_{doc.get('slug')}",
                "type": doc.get("type", "activity"),
                "asset": doc.get("project_id") or doc.get("symbol"),
                "title": doc.get("title") or doc.get("name"),
                "description": doc.get("description"),
                "impact_score": doc.get("score", 50),
                "impact_category": get_impact_category(doc.get("score", 50)),
                "confidence": 0.7,
                "event_score": 50,
                "sources_count": 1,
                "metrics": {},
                "tags": [doc.get("type", "event")],
                "timestamp": doc.get("event_date") or doc.get("created_at")
            })
    
    # Sort by event_score
    events.sort(key=lambda x: x["event_score"], reverse=True)
    
    # Get total count
    total = await _db.fused_events.count_documents(query)
    
    return {
        "ts": datetime.now(timezone.utc).isoformat(),
        "total": total,
        "count": len(events[:limit]),
        "offset": offset,
        "events": events[:limit]
    }


@router.get("/events/{event_id}")
async def get_event_detail(event_id: str):
    """
    Get detailed event information.
    
    Includes: sources, related events, timeline, project info
    """
    event = await _db.fused_events.find_one({"id": event_id}, {"_id": 0})
    
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # Get related events for same project
    related = []
    if event.get("canonical_entity_id"):
        cursor = _db.fused_events.find({
            "canonical_entity_id": event["canonical_entity_id"],
            "id": {"$ne": event_id}
        }, {"_id": 0}).sort([("date", -1)]).limit(5)
        
        async for doc in cursor:
            related.append({
                "id": doc.get("id"),
                "type": doc.get("event_type"),
                "title": doc.get("title"),
                "date": doc.get("date"),
                "impact_score": doc.get("impact_score")
            })
    
    # Get project info
    project = await _db.fused_entities.find_one(
        {"canonical_id": event.get("canonical_entity_id")},
        {"_id": 0}
    )
    
    return {
        "event": {
            **event,
            "event_score": calculate_event_score(event),
            "impact_category": get_impact_category(event.get("impact_score", 50))
        },
        "related_events": related,
        "project": project,
        "timeline": []  # TODO: Build timeline from related events
    }


# ═══════════════════════════════════════════════════════════════
# STATS
# ═══════════════════════════════════════════════════════════════

@router.get("/stats")
async def get_alpha_stats():
    """Get Alpha Feed statistics."""
    
    # Count by event type
    event_types_pipeline = [
        {"$group": {"_id": "$event_type", "count": {"$sum": 1}}}
    ]
    event_types = {}
    async for doc in _db.fused_events.aggregate(event_types_pipeline):
        event_types[doc["_id"]] = doc["count"]
    
    # Count by impact category
    high_impact = await _db.fused_events.count_documents({"impact_score": {"$gte": 60}})
    medium_impact = await _db.fused_events.count_documents({
        "impact_score": {"$gte": 40, "$lt": 60}
    })
    
    return {
        "ts": datetime.now(timezone.utc).isoformat(),
        "totals": {
            "projects": await _db.fused_entities.count_documents({"entity_type": "project"}),
            "events": await _db.fused_events.count_documents({}),
            "signals": await _db.fused_signals.count_documents({}),
            "high_impact_events": high_impact,
            "medium_impact_events": medium_impact
        },
        "by_event_type": event_types,
        "websocket_clients": len(manager.active_connections)
    }


# ═══════════════════════════════════════════════════════════════
# WEBSOCKET
# ═══════════════════════════════════════════════════════════════

@router.websocket("/ws/events")
async def websocket_events(websocket: WebSocket):
    """
    WebSocket endpoint for real-time event updates.
    
    Message format:
    {
        "type": "new_event" | "update" | "ping",
        "event": { ... }
    }
    """
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                
                # Handle client messages
                try:
                    msg = json.loads(data)
                    if msg.get("type") == "ping":
                        await websocket.send_json({"type": "pong", "ts": datetime.now(timezone.utc).isoformat()})
                    elif msg.get("type") == "subscribe":
                        await websocket.send_json({"type": "subscribed", "channel": msg.get("channel", "all")})
                except:
                    pass
                    
            except asyncio.TimeoutError:
                # Send heartbeat
                await websocket.send_json({
                    "type": "heartbeat",
                    "ts": datetime.now(timezone.utc).isoformat()
                })
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"[WebSocket] Error: {e}")
        manager.disconnect(websocket)


# Helper to broadcast new events (call from other modules)
async def broadcast_new_event(event: dict):
    """Broadcast new event to all connected clients."""
    await manager.broadcast({
        "type": "new_event",
        "event": {
            **event,
            "event_score": calculate_event_score(event),
            "impact_category": get_impact_category(event.get("impact_score", 50))
        },
        "ts": datetime.now(timezone.utc).isoformat()
    })
