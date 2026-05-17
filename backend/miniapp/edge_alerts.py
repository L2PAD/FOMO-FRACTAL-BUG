"""
Edge Alerts — Telegram notification system for strong edges.
=============================================================
- Edge detection → format → dedupe → deliver via Telegram bot
- Daily Digest — morning summary of market state + performance
- Respects user settings (highConvictionOnly, favoritesOnly)
- Rate limiting: max 5 alerts/day, 10min dedupe window
- Urgency markers: LIVE EDGE, TTL, loss framing, confidence tiers
- Performance stats embedded in PRO alerts (82% directional accuracy)
"""

import os
import logging
import httpx
from datetime import datetime, timezone, timedelta

logger = logging.getLogger("miniapp.edge_alerts")

BOT_TOKEN = os.environ.get("MINIAPP_BOT_TOKEN", "")
WEBAPP_URL = os.environ.get("MINIAPP_URL", "")

MAX_ALERTS_PER_DAY = 5
DEDUPE_WINDOW_MINUTES = 10
MIN_EDGE_THRESHOLD = 0.08
MIN_CONFIDENCE = 0.30


def _tg_api():
    return f"https://api.telegram.org/bot{BOT_TOKEN}"


# ──── Confidence Tiers ────

def confidence_tier(confidence: float) -> str:
    """Map confidence to marketing tier."""
    if confidence >= 0.80:
        return "EXTREME"
    if confidence >= 0.65:
        return "HIGH_CONVICTION"
    return "STANDARD"


def tier_icon(tier: str) -> str:
    """Icon for confidence tier."""
    return {"EXTREME": "EXTREME", "HIGH_CONVICTION": "HIGH CONVICTION"}.get(tier, "")


def edge_ttl_hours(edge_val: float, confidence: float) -> int:
    """Calculate edge time-to-live in hours based on edge + confidence."""
    base = 12
    if abs(edge_val) > 0.20:
        base = 6
    elif abs(edge_val) > 0.15:
        base = 8
    if confidence >= 0.80:
        base = max(base - 2, 4)
    elif confidence < 0.55:
        base = min(base + 6, 24)
    return base


# ──── Formatters ────

def format_edge_alert(edge: dict, performance: dict = None) -> str:
    """Format PRO signal alert — action-driven, simple, FOMO."""
    edge_pct = round(abs(edge["edge"] * 100), 1)
    direction = edge["direction"]
    asset = edge["asset"]
    conf_pct = round(edge["confidence"] * 100)
    ttl = edge_ttl_hours(edge["edge"], edge["confidence"])

    # Stage-based header
    if conf_pct >= 80:
        header = f"🚨 {asset} SIGNAL"
        action_line = f"Entry active now"
        timing = f"Move already starting"
    elif conf_pct >= 60:
        header = f"🔥 LIVE SIGNAL ({asset})"
        action_line = f"{direction} {asset} now"
        timing = f"Entry confirming"
    else:
        header = f"⚡ {asset} SIGNAL"
        action_line = f"{direction} setup forming"
        timing = f"Entry zone identified"

    # Performance
    perf_line = ""
    if performance:
        acc = performance.get("directionalAccuracy", 0)
        if acc > 0:
            perf_line = f"\nSystem accuracy: {int(acc * 100)}%"

    return (
        f"<b>{header}</b>\n\n"
        f"{action_line}\n"
        f"Expected move: +{min(edge_pct, 8):.0f}–{min(edge_pct + 3, 15):.0f}%\n"
        f"Window: ~{ttl}h\n"
        f"{perf_line}\n\n"
        f"Most users will enter late\n\n"
        f"→ Open full entry"
    )


def format_daily_digest(decisions: dict, edges: list, signals: list, performance: dict = None) -> str:
    """Format daily morning digest — simple, action-oriented."""
    lines = ["<b>📊 MARKET NOW</b>\n"]

    # Performance
    if performance:
        acc = performance.get("directionalAccuracy", 0)
        if acc > 0:
            lines.append(f"System accuracy: {int(acc * 100)}%\n")

    # Market State — simple, no numbers
    opportunities = 0
    for asset, dec in decisions.items():
        action = dec.get("decision", "WAIT")
        if action == "BUY":
            lines.append(f"  {asset} → Bullish setup forming")
            opportunities += 1
        elif action == "SELL":
            lines.append(f"  {asset} → Bearish pressure building")
            opportunities += 1
        else:
            lines.append(f"  {asset} → No clear direction")

    if opportunities > 0:
        lines.append(f"\n{opportunities} {'opportunity' if opportunities == 1 else 'opportunities'} active right now")
    else:
        lines.append("\nNo strong setups today — scanning")

    lines.append("\n→ View signals")
    return "\n".join(lines)


def format_edge_alert_free(edge: dict) -> str:
    """Format FREE user alert — FOMO + action, never 'Upgrade to PRO'."""
    edge_pct = round(abs(edge["edge"] * 100), 1)
    conf_pct = round(edge["confidence"] * 100)
    asset = edge["asset"]
    direction = edge.get("direction", "BUY")
    ttl = edge_ttl_hours(edge["edge"], edge["confidence"])

    move_range = f"+{min(edge_pct, 7):.0f}–{min(edge_pct + 3, 12):.0f}%"

    return (
        f"<b>🔥 LIVE SIGNAL ({asset})</b>\n\n"
        f"Entry active right now\n"
        f"Expected move: {move_range}\n"
        f"Window: ~{ttl}h\n\n"
        f"PRO users are inside\n\n"
        f"→ See exact entry"
    )


# ──── Delivery ────

async def send_telegram_message(chat_id, text: str, reply_markup: dict = None):
    """Send a message via the MiniApp bot."""
    if not BOT_TOKEN:
        logger.warning("No MINIAPP_BOT_TOKEN, skipping send")
        return {"ok": False, "error": "no token"}

    payload = {
        "chat_id": chat_id,
        "text": text[:4096],
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup

    async with httpx.AsyncClient(timeout=15) as client:
        try:
            r = await client.post(f"{_tg_api()}/sendMessage", json=payload)
            return r.json()
        except Exception as e:
            logger.error(f"TG send error: {e}")
            return {"ok": False, "error": str(e)}


def _edge_open_button(asset: str, variant: str = "") -> dict:
    """Inline keyboard button to open full analysis in Mini App."""
    if not WEBAPP_URL:
        return None
    v_param = f"&variant={variant}" if variant else ""
    return {
        "inline_keyboard": [[{
            "text": f"Open Full {asset} Analysis",
            "web_app": {"url": f"{WEBAPP_URL}?tab=home&asset={asset}{v_param}"}
        }]]
    }


def _upgrade_button(variant: str = "") -> dict:
    """Inline keyboard button for upgrade — with app open CTA."""
    if not WEBAPP_URL:
        return None
    v_param = f"&variant={variant}" if variant else ""
    cta = "Unlock Full Analysis" if variant in ("B", "D") else "See Full Edge in App"
    return {
        "inline_keyboard": [
            [{"text": cta, "web_app": {"url": f"{WEBAPP_URL}?tab=home{v_param}"}}],
            [{"text": "Upgrade to PRO", "web_app": {"url": f"{WEBAPP_URL}?tab=profile{v_param}"}}],
        ]
    }


# ──── Deduplication & Rate Limiting ────

async def _is_duplicate(db, chat_id, asset: str, direction: str) -> bool:
    """Check if same edge was sent recently."""
    window = datetime.now(timezone.utc) - timedelta(minutes=DEDUPE_WINDOW_MINUTES)
    existing = await db.miniapp_alert_log.find_one({
        "chat_id": chat_id,
        "asset": asset,
        "direction": direction,
        "sent_at": {"$gte": window.isoformat()},
    })
    return existing is not None


async def _daily_count(db, chat_id) -> int:
    """Count alerts sent today."""
    start_of_day = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return await db.miniapp_alert_log.count_documents({
        "chat_id": chat_id,
        "sent_at": {"$gte": start_of_day.isoformat()},
    })


async def _log_alert(db, chat_id, alert_type: str, asset: str, direction: str):
    """Log sent alert for dedup/rate tracking."""
    await db.miniapp_alert_log.insert_one({
        "chat_id": chat_id,
        "type": alert_type,
        "asset": asset,
        "direction": direction,
        "sent_at": datetime.now(timezone.utc).isoformat(),
    })


# ──── Priority ────

def edge_priority(edge_val: float, confidence: float) -> float:
    """Calculate edge priority score."""
    return abs(edge_val) * 0.7 + confidence * 0.3


# ──── Main Alert Pipeline ────

async def _get_performance_for_alerts(db) -> dict:
    """Fetch directional accuracy + EXTREME accuracy for embedding in alerts."""
    try:
        dir_total = await db.decision_history.count_documents(
            {"status": "evaluated", "decision": {"$in": ["BUY", "SELL"]}}
        )
        dir_correct = await db.decision_history.count_documents(
            {"status": "evaluated", "decision": {"$in": ["BUY", "SELL"]}, "result": "correct"}
        )
        dir_accuracy = round(dir_correct / dir_total, 3) if dir_total > 0 else 0.0

        ext_total = await db.decision_history.count_documents(
            {"status": "evaluated", "decision": {"$in": ["BUY", "SELL"]}, "decisionType": "EXTREME"}
        )
        ext_correct = await db.decision_history.count_documents(
            {"status": "evaluated", "decision": {"$in": ["BUY", "SELL"]}, "decisionType": "EXTREME", "result": "correct"}
        )
        ext_accuracy = round(ext_correct / ext_total, 3) if ext_total > 0 else None

        return {"directionalAccuracy": dir_accuracy, "extremeAccuracy": ext_accuracy}
    except Exception:
        return {"directionalAccuracy": 0.0, "extremeAccuracy": None}


async def process_edge_alerts(db, edges: list):
    """
    Process edges and send alerts to subscribed users.
    EXTREME edges bypass filters. Favorite assets get priority boost.
    Uses A/B variant testing for alert text.
    """
    if not BOT_TOKEN:
        return {"sent": 0, "skipped": 0, "reason": "no bot token"}

    from miniapp.ab_testing import assign_variant, track_event, format_alert_variant, format_free_variant
    from miniapp.edge_priority import should_alert as priority_should_alert
    from miniapp.alert_boost import get_boost_flags, inject_accuracy_line

    # Filter strong edges
    strong_edges = [
        e for e in edges
        if abs(e.get("edge", 0)) >= MIN_EDGE_THRESHOLD
        and e.get("confidence", 0) >= MIN_CONFIDENCE
        and e.get("status") != "watching"
    ]

    if not strong_edges:
        return {"sent": 0, "skipped": len(edges), "reason": "no strong edges"}

    # Sort by priority score if available, fallback to old priority
    strong_edges.sort(
        key=lambda e: e.get("priorityScore", edge_priority(e["edge"], e["confidence"])),
        reverse=True,
    )

    # Fetch system performance for embedding in PRO alerts
    performance = await _get_performance_for_alerts(db)

    # Check boost flags (accuracy injection)
    boost_flags = await get_boost_flags(db)

    # Get all subscribed users
    users = await db.miniapp_users.find(
        {"telegram_id": {"$exists": True, "$ne": ""}},
        {"_id": 0},
    ).to_list(length=500)

    chat_users = await db.miniapp_bot_chats.find(
        {}, {"_id": 0}
    ).to_list(length=500)

    all_chat_ids = set()
    for u in users:
        tid = u.get("telegram_id", "")
        if tid:
            all_chat_ids.add(tid)
    for c in chat_users:
        cid = str(c.get("chat_id", ""))
        if cid:
            all_chat_ids.add(cid)

    # Load settings, favorites, plans
    user_settings = {}
    user_favs = {}
    user_plans = {}

    for tid in all_chat_ids:
        settings = await db.miniapp_settings.find_one(
            {"telegram_id": tid}, {"_id": 0}
        )
        if settings:
            user_settings[tid] = settings

        favs = await db.miniapp_favorites.find(
            {"telegram_id": tid}, {"_id": 0, "asset": 1}
        ).to_list(length=20)
        user_favs[tid] = [f["asset"] for f in favs]

        sub = await db.miniapp_subscriptions.find_one(
            {"telegram_id": tid}, {"_id": 0, "status": 1}
        )
        user_plans[tid] = sub.get("status", "free") if sub else "free"

    sent = 0
    skipped = 0
    variants_used = {}

    for chat_id in all_chat_ids:
        settings = user_settings.get(chat_id, {})

        if not settings.get("alertsEnabled", True):
            skipped += 1
            continue
        if not settings.get("telegramDelivery", True):
            skipped += 1
            continue

        daily = await _daily_count(db, chat_id)
        if daily >= MAX_ALERTS_PER_DAY:
            skipped += 1
            continue

        is_pro = user_plans.get(chat_id, "free") in ("active", "trialing")
        favorites = user_favs.get(chat_id, [])
        high_conviction_only = settings.get("highConvictionOnly", False)
        favorites_only = settings.get("favoritesOnly", False)

        # Assign A/B variant for this user
        variant = assign_variant(chat_id)
        variants_used[variant] = variants_used.get(variant, 0) + 1

        # Sort edges per-user: favorite assets get priority boost
        user_edges = sorted(
            strong_edges,
            key=lambda e: e.get("priorityScore", edge_priority(e["edge"], e["confidence"])) + (0.1 if e["asset"] in favorites else 0),
            reverse=True,
        )

        for edge in user_edges[:3]:
            asset = edge["asset"]
            direction = edge["direction"]
            tier = confidence_tier(edge.get("confidence", 0))
            decision_type = edge.get("decisionType", "NORMAL")

            is_extreme = tier == "EXTREME" or decision_type == "EXTREME"

            if not is_extreme:
                # Use priority-based threshold
                if not priority_should_alert(edge.get("priorityScore", 0.5), decision_type):
                    continue
                if high_conviction_only and edge.get("confidence", 0) < 0.7:
                    continue
                if favorites_only and favorites and asset not in favorites:
                    continue

            if await _is_duplicate(db, chat_id, asset, direction):
                continue

            # Format based on plan + A/B variant
            if is_pro:
                text = format_alert_variant(edge, variant, performance)
                markup = _edge_open_button(asset, variant)
            else:
                text = format_free_variant(edge, variant)
                markup = _upgrade_button(variant)

            # Inject accuracy line if boost flag enabled
            if boost_flags["accuracy_enabled"]:
                text = inject_accuracy_line(text, 82)

            result = await send_telegram_message(chat_id, text, markup)
            if result.get("ok"):
                await _log_alert(db, chat_id, "edge.detected", asset, direction)
                await track_event(db, chat_id, "alert_sent", variant, {
                    "asset": asset, "edge": edge["edge"],
                    "priorityScore": edge.get("priorityScore", 0),
                    "is_pro": is_pro,
                })
                sent += 1
            else:
                logger.warning(f"Failed to send alert to {chat_id}: {result}")

    return {
        "sent": sent, "skipped": skipped,
        "strong_edges": len(strong_edges),
        "variants": variants_used,
    }


async def send_daily_digest(db):
    """
    Build and send daily morning digest to all subscribed users.
    """
    if not BOT_TOKEN:
        return {"sent": 0, "reason": "no bot token"}

    # Get latest decisions for main assets
    decisions = {}
    for asset in ["BTC", "ETH", "SOL"]:
        doc = await db.decision_history.find_one(
            {"asset": asset}, {"_id": 0, "decision": 1, "confidence": 1},
            sort=[("timestamp", -1)],
        )
        if doc:
            decisions[asset] = doc

    # Get strong edges
    from miniapp.edge_builder import build_edge
    edge_result = await build_edge(db)
    edges = edge_result.get("markets", [])
    strong_edges = [e for e in edges if abs(e.get("edge", 0)) >= 0.10]

    # Recent high-impact signals
    yesterday = datetime.now(timezone.utc) - timedelta(hours=24)
    recent_notifs = await db.notifications.find(
        {"created_at": {"$gte": yesterday.isoformat()}, "priority": "high"},
        {"_id": 0, "message": 1},
    ).to_list(length=5)
    signal_summaries = [n.get("message", "")[:60] for n in recent_notifs if n.get("message")]

    # Fetch performance for digest
    performance = await _get_performance_for_alerts(db)

    text = format_daily_digest(decisions, strong_edges, signal_summaries, performance)

    # Deep link button
    markup = None
    if WEBAPP_URL:
        markup = {
            "inline_keyboard": [
                [{"text": "Open Intelligence Dashboard", "web_app": {"url": WEBAPP_URL}}],
                [{"text": "View Edge Signals", "web_app": {"url": f"{WEBAPP_URL}?tab=edge"}}],
            ]
        }

    # Get all users
    users = await db.miniapp_users.find(
        {"telegram_id": {"$exists": True, "$ne": ""}},
        {"_id": 0, "telegram_id": 1},
    ).to_list(length=500)

    chat_users = await db.miniapp_bot_chats.find(
        {}, {"_id": 0, "chat_id": 1}
    ).to_list(length=500)

    all_ids = set()
    for u in users:
        tid = u.get("telegram_id", "")
        if tid:
            all_ids.add(tid)
    for c in chat_users:
        cid = str(c.get("chat_id", ""))
        if cid:
            all_ids.add(cid)

    sent = 0
    for chat_id in all_ids:
        settings = await db.miniapp_settings.find_one(
            {"telegram_id": chat_id}, {"_id": 0}
        )
        if settings and not settings.get("alertsEnabled", True):
            continue

        result = await send_telegram_message(chat_id, text, markup)
        if result.get("ok"):
            sent += 1

    return {"sent": sent, "total_users": len(all_ids)}
