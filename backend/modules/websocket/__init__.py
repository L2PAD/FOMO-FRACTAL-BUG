"""
WebSocket Manager for Real-Time Updates
========================================

Provides real-time updates for:
- News Intelligence events
- Breaking news alerts
- Generation progress
- Market signals
"""

import logging
import asyncio
import json
from typing import Dict, Set, Any
from datetime import datetime, timezone
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSocket"])

# Connection manager
class ConnectionManager:
    """Manages WebSocket connections and broadcasts."""
    
    def __init__(self):
        # Channel -> Set of WebSocket connections
        self.active_connections: Dict[str, Set[WebSocket]] = {
            "news": set(),
            "breaking": set(),
            "progress": set(),
            "signals": set(),
            "all": set()  # Receives all updates
        }
        self._lock = asyncio.Lock()
    
    async def connect(self, websocket: WebSocket, channel: str = "all"):
        """Accept and register a new connection."""
        await websocket.accept()
        async with self._lock:
            if channel not in self.active_connections:
                self.active_connections[channel] = set()
            self.active_connections[channel].add(websocket)
            self.active_connections["all"].add(websocket)
        logger.info(f"[WS] New connection on channel: {channel}. Total: {self.total_connections}")
    
    async def disconnect(self, websocket: WebSocket, channel: str = "all"):
        """Remove a connection."""
        async with self._lock:
            for ch in self.active_connections.values():
                ch.discard(websocket)
        logger.info(f"[WS] Connection closed. Total: {self.total_connections}")
    
    @property
    def total_connections(self) -> int:
        """Get total unique connections."""
        return len(self.active_connections.get("all", set()))
    
    async def broadcast(self, channel: str, message: Dict[str, Any]):
        """Broadcast message to all connections on a channel."""
        if channel not in self.active_connections:
            return
        
        dead_connections = set()
        message_json = json.dumps(message)
        
        for connection in self.active_connections[channel]:
            try:
                await connection.send_text(message_json)
            except Exception as e:
                logger.warning(f"[WS] Failed to send to connection: {e}")
                dead_connections.add(connection)
        
        # Clean up dead connections
        if dead_connections:
            async with self._lock:
                for conn in dead_connections:
                    for ch in self.active_connections.values():
                        ch.discard(conn)
    
    async def send_to_all(self, message: Dict[str, Any]):
        """Send to all connected clients."""
        await self.broadcast("all", message)


# Global connection manager
manager = ConnectionManager()


# ═══════════════════════════════════════════════════════════════
# WebSocket Endpoints
# ═══════════════════════════════════════════════════════════════

@router.websocket("/ws/news")
async def websocket_news(websocket: WebSocket):
    """
    WebSocket for news intelligence updates.
    
    Receives:
    - new_event: New event detected
    - event_update: Event status/content update
    - breaking: Breaking news alert
    """
    await manager.connect(websocket, "news")
    try:
        while True:
            # Keep connection alive, handle incoming messages
            data = await websocket.receive_text()
            # Echo back or handle commands
            await websocket.send_json({
                "type": "ack",
                "received": data,
                "ts": datetime.now(timezone.utc).isoformat()
            })
    except WebSocketDisconnect:
        await manager.disconnect(websocket, "news")


@router.websocket("/ws/breaking")
async def websocket_breaking(websocket: WebSocket):
    """
    WebSocket for breaking news alerts only.
    High-priority channel for score > 90 events.
    """
    await manager.connect(websocket, "breaking")
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_json({"type": "ack", "channel": "breaking"})
    except WebSocketDisconnect:
        await manager.disconnect(websocket, "breaking")


@router.websocket("/ws/progress")
async def websocket_progress(websocket: WebSocket):
    """
    WebSocket for generation progress updates.
    Real-time progress: DETECTED → AI_WRITING → IMAGE_GENERATION → PUBLISHED
    """
    await manager.connect(websocket, "progress")
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_json({"type": "ack", "channel": "progress"})
    except WebSocketDisconnect:
        await manager.disconnect(websocket, "progress")


@router.websocket("/ws/signals")
async def websocket_signals(websocket: WebSocket):
    """
    WebSocket for market signals.
    Pump/dump alerts, unlock risks, etc.
    """
    await manager.connect(websocket, "signals")
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_json({"type": "ack", "channel": "signals"})
    except WebSocketDisconnect:
        await manager.disconnect(websocket, "signals")


@router.websocket("/ws/all")
async def websocket_all(websocket: WebSocket):
    """
    WebSocket for all updates.
    Receives every message from all channels.
    """
    await manager.connect(websocket, "all")
    try:
        while True:
            data = await websocket.receive_text()
            # Handle subscription requests
            try:
                msg = json.loads(data)
                if msg.get("action") == "ping":
                    await websocket.send_json({
                        "type": "pong",
                        "ts": datetime.now(timezone.utc).isoformat(),
                        "connections": manager.total_connections
                    })
            except:
                pass
    except WebSocketDisconnect:
        await manager.disconnect(websocket, "all")


# ═══════════════════════════════════════════════════════════════
# Broadcast Functions (called from scheduler/pipeline)
# ═══════════════════════════════════════════════════════════════

async def broadcast_new_event(event: Dict[str, Any]):
    """Broadcast new event to news channel."""
    await manager.broadcast("news", {
        "type": "new_event",
        "event": event,
        "ts": datetime.now(timezone.utc).isoformat()
    })


async def broadcast_breaking_news(event: Dict[str, Any]):
    """Broadcast breaking news to breaking channel."""
    message = {
        "type": "breaking",
        "event": {
            "id": event.get("id"),
            "headline": event.get("title_en") or event.get("headline"),
            "summary": event.get("summary_en"),
            "fomo_score": event.get("fomo_score"),
            "assets": event.get("primary_assets", []),
            "event_type": event.get("event_type")
        },
        "ts": datetime.now(timezone.utc).isoformat(),
        "priority": "urgent"
    }
    await manager.broadcast("breaking", message)
    await manager.send_to_all(message)
    logger.info(f"[WS] Breaking news broadcast: {event.get('id')}")


async def broadcast_generation_progress(event_id: str, stage: str, progress: int, message: str = ""):
    """Broadcast generation progress update."""
    await manager.broadcast("progress", {
        "type": "progress",
        "event_id": event_id,
        "stage": stage,
        "progress": progress,
        "message": message,
        "ts": datetime.now(timezone.utc).isoformat()
    })


async def broadcast_event_published(event: Dict[str, Any]):
    """Broadcast when event story is published."""
    message = {
        "type": "published",
        "event": {
            "id": event.get("id"),
            "headline": event.get("title_en"),
            "summary": event.get("summary_en"),
            "has_image": bool(event.get("cover_image_base64")),
            "fomo_score": event.get("fomo_score")
        },
        "ts": datetime.now(timezone.utc).isoformat()
    }
    await manager.broadcast("news", message)
    await manager.send_to_all(message)


async def broadcast_signal(signal: Dict[str, Any]):
    """Broadcast market signal."""
    await manager.broadcast("signals", {
        "type": "signal",
        "signal": signal,
        "ts": datetime.now(timezone.utc).isoformat()
    })


async def broadcast_sentiment_alert(alert: Dict[str, Any]):
    """
    Broadcast sentiment shift alert.
    Triggered when sentiment changes significantly (>20% in short period).
    """
    message = {
        "type": "sentiment_alert",
        "alert": {
            "asset": alert.get("asset"),
            "asset_name": alert.get("asset_name"),
            "previous_sentiment": alert.get("previous"),
            "current_sentiment": alert.get("current"),
            "change_percent": alert.get("change_percent"),
            "direction": "bullish" if alert.get("change_percent", 0) > 0 else "bearish",
            "time_window": alert.get("time_window", "1h"),
            "confidence": alert.get("confidence", "medium"),
            "trigger_sources": alert.get("sources", []),
        },
        "ts": datetime.now(timezone.utc).isoformat(),
        "priority": "high" if abs(alert.get("change_percent", 0)) > 30 else "medium"
    }
    await manager.broadcast("signals", message)
    await manager.send_to_all(message)
    logger.info(f"[WS] Sentiment alert broadcast: {alert.get('asset')} {alert.get('change_percent')}%")


async def broadcast_investment_alert(investment: Dict[str, Any]):
    """
    Broadcast new investment detection alert.
    Triggered when parser detects new VC investment.
    """
    message = {
        "type": "investment_alert",
        "investment": {
            "fund": investment.get("fund"),
            "fund_name": investment.get("fund_name"),
            "project": investment.get("project"),
            "project_name": investment.get("project_name"),
            "amount_usd": investment.get("amount"),
            "round": investment.get("round"),
            "source": investment.get("source"),
        },
        "ts": datetime.now(timezone.utc).isoformat(),
        "priority": "high"
    }
    await manager.broadcast("signals", message)
    await manager.send_to_all(message)
    logger.info(f"[WS] Investment alert: {investment.get('fund_name')} -> {investment.get('project_name')}")


# ═══════════════════════════════════════════════════════════════
# REST API for WebSocket Status
# ═══════════════════════════════════════════════════════════════

@router.get("/api/ws/status")
async def get_websocket_status():
    """Get WebSocket connection status."""
    return {
        "ok": True,
        "total_connections": manager.total_connections,
        "channels": {
            channel: len(connections)
            for channel, connections in manager.active_connections.items()
        }
    }


@router.post("/api/ws/test-broadcast")
async def test_broadcast(channel: str = "all", message: str = "Test message"):
    """Test broadcast (admin only)."""
    await manager.broadcast(channel, {
        "type": "test",
        "message": message,
        "ts": datetime.now(timezone.utc).isoformat()
    })
    return {"ok": True, "sent_to": channel}
