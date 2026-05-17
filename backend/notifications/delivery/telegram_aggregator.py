"""
Telegram Aggregation Buffer.

Buffers telegram events per asset and flushes them as aggregated messages.

Rules:
  - Events buffered per asset
  - Flush when: buffer age >= 5 min OR buffer size >= 3
  - Single event after 5 min → send as-is
  - Multiple events → aggregate into 1 message with decision header
  - Never mix different assets
"""
import asyncio
import time
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)

WINDOW_SECONDS = 300  # 5 minutes
MAX_BATCH = 3  # Flush if >= 3 events accumulated

# Buffer: {asset: [{"notification": ..., "event": ..., "buffered_at": float}]}
_buffer: dict[str, list] = defaultdict(list)
_lock = asyncio.Lock()


async def buffer_telegram_event(notification: dict, event: dict):
    """Add an event to the aggregation buffer instead of sending immediately."""
    asset = event.get("asset", "UNKNOWN")
    async with _lock:
        _buffer[asset].append({
            "notification": notification,
            "event": event,
            "buffered_at": time.time(),
        })
        count = len(_buffer[asset])
    logger.info(f"[TG-Agg] Buffered {event.get('type')} for {asset} (buffer: {count})")

    # Immediate flush if batch threshold hit
    if count >= MAX_BATCH:
        await _flush_asset(asset)


async def flush_loop():
    """Background loop: check buffers every 60s and flush mature ones."""
    logger.info("[TG-Agg] Flush loop started (60s interval)")
    while True:
        await asyncio.sleep(60)
        await flush_all()


async def flush_all():
    """Flush all mature buffers."""
    now = time.time()
    to_flush = {}

    async with _lock:
        for asset, items in list(_buffer.items()):
            if not items:
                continue
            oldest = min(i["buffered_at"] for i in items)
            age = now - oldest
            if len(items) >= 2 or age >= WINDOW_SECONDS:
                to_flush[asset] = items[:]
                del _buffer[asset]

    for asset, items in to_flush.items():
        await _send_batch(asset, items)


async def _flush_asset(asset: str):
    """Flush a specific asset's buffer."""
    async with _lock:
        items = _buffer.pop(asset, [])
    if items:
        await _send_batch(asset, items)


async def _send_batch(asset: str, items: list):
    """Send aggregated or single message for an asset."""
    if len(items) == 1:
        # Single event: send as-is (no aggregation needed)
        await _send_single(items[0])
    else:
        # Multiple events: aggregate
        await _send_aggregated(asset, items)


async def _send_single(item: dict):
    """Send a single event through normal telegram delivery."""
    from notifications.delivery.telegram_user import send_telegram_user
    notification = item["notification"]
    event = item["event"]
    result = await send_telegram_user(notification, event)
    await _update_status(notification, result)


async def _send_aggregated(asset: str, items: list):
    """Build and send an aggregated message for multiple events."""
    from notifications.delivery.telegram_user import _send_tg, TG_BOT_TOKEN, TG_USER_CHAT_ID

    if not TG_BOT_TOKEN or not TG_USER_CHAT_ID:
        logger.warning("[TG-Agg] Telegram not configured, skipping aggregated send")
        return

    text = _format_aggregated(asset, items)
    result = await _send_tg(TG_BOT_TOKEN, TG_USER_CHAT_ID, text)

    # Update all notification statuses
    for item in items:
        await _update_status(item["notification"], result)

    sent_ok = result.get("ok", False)
    event_types = [i["event"].get("type", "?") for i in items]
    logger.info(f"[TG-Agg] Sent aggregated {asset}: {len(items)} events ({event_types}), ok={sent_ok}")


def _format_aggregated(asset: str, items: list) -> str:
    """Build a clean aggregated Telegram message."""
    events = [i["event"] for i in items]
    signals = []

    for event in events:
        etype = event.get("type", "")
        payload = event.get("payload", {})

        if etype == "exchange.prediction.updated":
            direction = str(payload.get("direction", "")).upper()
            move = float(payload.get("expectedMovePct", 0))
            horizon = payload.get("horizon", "")
            sign = "+" if move > 0 else ""
            signals.append({
                "source": "Exchange",
                "text": f"Exchange {horizon} → {direction.lower()} ({sign}{move:.1f}%)",
                "direction": "bearish" if direction in ("BEARISH", "SHORT") else "bullish" if direction in ("BULLISH", "LONG") else "neutral",
                "priority": 1,
            })
        elif etype in ("onchain.whale.transfer", "onchain.smart_money.entry"):
            direction = payload.get("direction", "")
            value_usd = payload.get("valueUsd", 0)
            label = "Whale" if etype == "onchain.whale.transfer" else "Smart Money"
            amount_str = f"${value_usd / 1e6:.1f}M " if value_usd else ""
            signals.append({
                "source": "OnChain",
                "text": f"{label} → {amount_str}{direction}",
                "direction": "bearish" if direction == "inflow" else "bullish" if direction == "outflow" else "neutral",
                "priority": 2,
            })
        elif etype == "sentiment.spike":
            delta = float(payload.get("delta", 0))
            window = payload.get("window", "4h")
            direction = "bullish" if delta > 0 else "bearish"
            signals.append({
                "source": "Sentiment",
                "text": f"Sentiment → {direction} spike ({delta:+.1%}, {window})",
                "direction": direction,
                "priority": 3,
            })
        elif etype == "exchange.divergence.detected":
            d7 = payload.get("7D", "?")
            d30 = payload.get("30D", "?")
            signals.append({
                "source": "Divergence",
                "text": f"Divergence → 7D {d7} vs 30D {d30}",
                "direction": "mixed",
                "priority": 4,
            })
        else:
            signals.append({
                "source": "Signal",
                "text": event.get("title", etype),
                "direction": "neutral",
                "priority": 5,
            })

    # Sort by priority
    signals.sort(key=lambda s: s["priority"])

    # Compute alignment
    bullish = sum(1 for s in signals if s["direction"] == "bullish")
    bearish = sum(1 for s in signals if s["direction"] == "bearish")

    if bullish > bearish:
        alignment = "bullish"
        alignment_label = "Bullish alignment"
    elif bearish > bullish:
        alignment = "bearish"
        alignment_label = "Bearish alignment"
    else:
        alignment = "mixed"
        alignment_label = "Mixed signals"

    strength = "Strong" if max(bullish, bearish) >= 3 else "Moderate" if max(bullish, bearish) >= 2 else "Weak"

    # Try to get a quick decision for this asset
    decision_header = None
    try:
        from notifications.decision_engine import compute_decision
        dec = compute_decision(asset, "7D")
        dtype = dec.get("decisionType", "NORMAL")
        decision = dec.get("decision", "WAIT")
        confidence = dec.get("confidence", 0)
        if decision != "WAIT":
            if dtype == "EXTREME":
                decision_header = f"<b>{asset} EXTREME {decision} SIGNAL</b>"
            elif dtype == "HIGH_CONVICTION":
                decision_header = f"<b>{asset} HIGH CONVICTION {decision}</b>"
            else:
                decision_header = f"<b>{asset} DECISION: {decision}</b>"
            decision_header += f"\nConfidence: {confidence}%"
    except Exception:
        pass

    # Build message
    lines = []
    if decision_header:
        lines.append(decision_header)
    else:
        lines.append(f"<b>{asset} Market Update</b>")

    lines.append("")
    lines.append("Signals:")
    for s in signals:
        lines.append(f"  • {s['text']}")

    lines.append("")
    lines.append(f"→ {strength} {alignment_label.lower()}")

    return "\n".join(lines)


async def _update_status(notification: dict, result: dict):
    """Update notification status after delivery."""
    from notifications.storage.notification_repo import _col
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    ntf_id = notification.get("id")
    if not ntf_id:
        return
    if result.get("ok") and not result.get("skipped"):
        await _col().update_one(
            {"id": ntf_id},
            {"$set": {"status": "sent", "sentAt": now, "deliveryResult": {"aggregated": True}}}
        )
    elif result.get("skipped"):
        await _col().update_one(
            {"id": ntf_id},
            {"$set": {"status": "filtered", "deliveryResult": result}}
        )


def get_buffer_status() -> dict:
    """Get current buffer state (for debugging)."""
    status = {}
    for asset, items in _buffer.items():
        status[asset] = {
            "count": len(items),
            "oldest": min(i["buffered_at"] for i in items) if items else None,
            "types": [i["event"].get("type", "?") for i in items],
        }
    return status
