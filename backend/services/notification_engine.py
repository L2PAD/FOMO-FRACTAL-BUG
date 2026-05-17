"""
FOMO In-App Notification Engine (bilingual: EN / RU).
Notifications are stored with both languages.
Frontend sends ?lang=en|ru, backend returns the correct version.
Two types: SYSTEM (admin broadcast) and SIGNAL (auto-generated from market data).
"""
import os
import logging
from datetime import datetime, timezone
from pymongo import MongoClient, DESCENDING
from dotenv import load_dotenv
from pathlib import Path
import uuid

load_dotenv(Path(__file__).parent.parent / '.env')
logger = logging.getLogger(__name__)

MONGO_URL = os.getenv('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.getenv('DB_NAME', 'test_database')

client = MongoClient(MONGO_URL)
db = client[DB_NAME]

notifications_col = db['notifications']
user_notifications_col = db['user_notifications']

# Ensure indexes
notifications_col.create_index([('createdAt', DESCENDING)])
notifications_col.create_index('type')
user_notifications_col.create_index([('userId', 1), ('notificationId', 1)], unique=True)
user_notifications_col.create_index('userId')

# Signal state tracking (in-memory)
_last_signals: dict[str, dict] = {}

PLAN_RANK = {'FREE': 0, 'TRIAL': 1, 'PRO': 2, 'INSTITUTIONAL': 3}

# ═══════════════════════════════════════════════════
#  CREATE / STORE
# ═══════════════════════════════════════════════════

def create_notification(
    ntype: str,
    title_en: str,
    title_ru: str,
    body_en: str,
    body_ru: str,
    data: dict = None,
    priority: str = "MEDIUM",
    icon: str = None,
) -> str:
    """Create a bilingual notification. Returns notification ID."""
    nid = f"n_{uuid.uuid4().hex[:12]}"
    doc = {
        '_id': nid,
        'type': ntype,
        'title_en': title_en,
        'title_ru': title_ru,
        'body_en': body_en,
        'body_ru': body_ru,
        'data': data or {},
        'priority': priority,
        'icon': icon or ('megaphone' if ntype == 'SYSTEM' else 'trending-up'),
        'createdAt': datetime.now(timezone.utc),
    }
    notifications_col.insert_one(doc)
    logger.info(f"Notification created: [{ntype}] {title_en}")
    return nid


def broadcast_system_notification(
    title_en: str, title_ru: str,
    body_en: str, body_ru: str,
    data: dict = None, priority: str = "MEDIUM",
) -> str:
    """Admin broadcasts a system notification to all users."""
    return create_notification("SYSTEM", title_en, title_ru, body_en, body_ru, data, priority, icon="megaphone")


def create_signal_notification(
    asset: str,
    title_en: str, title_ru: str,
    body_en: str, body_ru: str,
    action: str = None,
    confidence: float = None,
    screen: str = "home",
    priority: str = "MEDIUM",
) -> str:
    """Create a bilingual signal-type notification."""
    data = {"asset": asset, "screen": screen}
    if action:
        data["action"] = action
    if confidence is not None:
        data["confidence"] = confidence

    icon = "trending-up"
    if action == "SELL":
        icon = "trending-down"
    elif action == "WAIT":
        icon = "pause-circle"

    return create_notification("SIGNAL", title_en, title_ru, body_en, body_ru, data, priority, icon=icon)


# ═══════════════════════════════════════════════════
#  READ / QUERY
# ═══════════════════════════════════════════════════

def get_user_notifications(user_id: str, lang: str = "en", ntype: str = None, limit: int = 50, offset: int = 0) -> dict:
    """Get notifications for a user, localized to requested language."""
    query = {}
    if ntype and ntype in ('SYSTEM', 'SIGNAL'):
        query['type'] = ntype

    total = notifications_col.count_documents(query)
    notifs = list(
        notifications_col.find(query)
        .sort('createdAt', DESCENDING)
        .skip(offset)
        .limit(limit)
    )

    nids = [n['_id'] for n in notifs]
    read_docs = list(user_notifications_col.find({
        'userId': user_id,
        'notificationId': {'$in': nids},
    }))
    read_map = {r['notificationId']: r.get('readAt') for r in read_docs}

    suffix = f"_{lang}" if lang in ("en", "ru") else "_en"

    items = []
    for n in notifs:
        read_at = read_map.get(n['_id'])

        # Resolve title / body for requested language
        title = n.get(f'title{suffix}') or n.get('title_en') or n.get('title', '')
        body = n.get(f'body{suffix}') or n.get('body_en') or n.get('body', '')

        items.append({
            'id': n['_id'],
            'type': n['type'],
            'title': title,
            'body': body,
            'data': n.get('data', {}),
            'priority': n.get('priority', 'MEDIUM'),
            'icon': n.get('icon', 'notifications'),
            'read': read_at is not None,
            'readAt': read_at.isoformat() if read_at else None,
            'createdAt': n['createdAt'].isoformat() if n.get('createdAt') else None,
        })

    return {
        'items': items,
        'total': total,
        'limit': limit,
        'offset': offset,
    }


def get_unread_count(user_id: str) -> dict:
    """Get unread notification count."""
    total_notifs = notifications_col.count_documents({})
    read_count = user_notifications_col.count_documents({'userId': user_id})
    unread = max(0, total_notifs - read_count)

    signal_total = notifications_col.count_documents({'type': 'SIGNAL'})
    system_total = notifications_col.count_documents({'type': 'SYSTEM'})

    signal_nids = [n['_id'] for n in notifications_col.find({'type': 'SIGNAL'}, {'_id': 1})]
    system_nids = [n['_id'] for n in notifications_col.find({'type': 'SYSTEM'}, {'_id': 1})]

    signal_read = user_notifications_col.count_documents({
        'userId': user_id,
        'notificationId': {'$in': signal_nids},
    }) if signal_nids else 0

    system_read = user_notifications_col.count_documents({
        'userId': user_id,
        'notificationId': {'$in': system_nids},
    }) if system_nids else 0

    return {
        'total': unread,
        'signal': max(0, signal_total - signal_read),
        'system': max(0, system_total - system_read),
    }


def mark_read(user_id: str, notification_id: str) -> bool:
    try:
        user_notifications_col.update_one(
            {'userId': user_id, 'notificationId': notification_id},
            {'$set': {'readAt': datetime.now(timezone.utc)},
             '$setOnInsert': {'userId': user_id, 'notificationId': notification_id}},
            upsert=True,
        )
        return True
    except Exception as e:
        logger.error(f"mark_read error: {e}")
        return False


def mark_all_read(user_id: str) -> int:
    all_nids = [n['_id'] for n in notifications_col.find({}, {'_id': 1})]
    now = datetime.now(timezone.utc)
    count = 0
    for nid in all_nids:
        result = user_notifications_col.update_one(
            {'userId': user_id, 'notificationId': nid},
            {'$set': {'readAt': now},
             '$setOnInsert': {'userId': user_id, 'notificationId': nid}},
            upsert=True,
        )
        if result.upserted_id or result.modified_count:
            count += 1
    return count


# ═══════════════════════════════════════════════════
#  SIGNAL AUTO-GENERATOR
# ═══════════════════════════════════════════════════

def check_and_generate_signal_notifications(asset: str, obs: dict):
    """Called after each data refresh. Checks for significant events."""
    global _last_signals

    if not obs:
        return

    price = obs.get('price', 0)
    change24h = obs.get('change24h', 0)
    change7d = obs.get('change7d', 0)
    sentiment_up = obs.get('sentimentUp', 50)

    # Signal computation
    score = 0.5
    if change24h > 0:
        score += min(change24h * 2, 0.15)
    else:
        score += max(change24h * 2, -0.15)
    if sentiment_up > 60:
        score += 0.1
    elif sentiment_up < 40:
        score -= 0.1
    if change7d > 0:
        score += min(change7d * 0.5, 0.1)
    else:
        score += max(change7d * 0.5, -0.1)
    score = max(0.15, min(0.95, score))

    if score >= 0.55:
        decision = "BUY"
    elif score <= 0.45:
        decision = "SELL"
    else:
        decision = "WAIT"

    prev = _last_signals.get(asset)
    price_str = f"${price:,.2f}" if price >= 1 else f"${price:.4f}"
    conf_pct = int(score * 100)

    # Decision change
    if prev and prev.get('decision') and prev['decision'] != decision:
        old = prev['decision']
        create_signal_notification(
            asset=asset,
            title_en=f"{asset}: {old} → {decision}",
            title_ru=f"{asset}: {old} → {decision}",
            body_en=f"Decision changed. {price_str}, confidence {conf_pct}%.",
            body_ru=f"Решение изменилось. {price_str}, уверенность {conf_pct}%.",
            action=decision, confidence=score, screen="home", priority="HIGH",
        )

    # High confidence
    if score >= 0.85 and (not prev or prev.get('confidence', 0) < 0.85):
        create_signal_notification(
            asset=asset,
            title_en=f"{asset}: High confidence {conf_pct}%",
            title_ru=f"{asset}: Высокая уверенность {conf_pct}%",
            body_en=f"Strong {decision} signal. {price_str}.",
            body_ru=f"Сильный сигнал {decision}. {price_str}.",
            action=decision, confidence=score, screen="home", priority="HIGH",
        )

    # Big 24h move (>5%)
    if abs(change24h) >= 5.0 and (not prev or abs(prev.get('change24h', 0)) < 5.0):
        direction_en = "up" if change24h > 0 else "down"
        direction_ru = "вырос" if change24h > 0 else "упал"
        create_signal_notification(
            asset=asset,
            title_en=f"{asset}: {direction_en} {abs(change24h):.1f}% in 24h",
            title_ru=f"{asset}: {direction_ru} на {abs(change24h):.1f}% за 24ч",
            body_en=f"Price: {price_str}. Significant market movement.",
            body_ru=f"Цена: {price_str}. Значительное движение рынка.",
            action=decision, confidence=score, screen="feed", priority="HIGH",
        )

    # Extreme sentiment
    if sentiment_up >= 85 and (not prev or prev.get('sentiment_up', 50) < 85):
        create_signal_notification(
            asset=asset,
            title_en=f"{asset}: Market euphoria ({int(sentiment_up)}% bullish)",
            title_ru=f"{asset}: Эйфория рынка ({int(sentiment_up)}% bullish)",
            body_en=f"Extreme bullish sentiment. Possible correction.",
            body_ru=f"Экстремальный бычий сентимент. Возможна коррекция.",
            action="WAIT", confidence=score, screen="feed", priority="MEDIUM",
        )
    elif sentiment_up <= 15 and (not prev or prev.get('sentiment_up', 50) > 15):
        create_signal_notification(
            asset=asset,
            title_en=f"{asset}: Market fear ({int(sentiment_up)}% bullish)",
            title_ru=f"{asset}: Страх на рынке ({int(sentiment_up)}% bullish)",
            body_en=f"Extreme bearish sentiment. Possible reversal.",
            body_ru=f"Экстремальный медвежий сентимент. Возможен разворот.",
            action="BUY", confidence=score, screen="feed", priority="MEDIUM",
        )

    _last_signals[asset] = {
        'decision': decision, 'confidence': score, 'price': price,
        'change24h': change24h, 'sentiment_up': sentiment_up,
        'ts': datetime.now(timezone.utc),
    }


# ═══════════════════════════════════════════════════
#  SEED
# ═══════════════════════════════════════════════════

def seed_initial_notifications():
    """Seed bilingual initial notifications if collection is empty."""
    if notifications_col.count_documents({}) > 0:
        return

    logger.info("Seeding initial bilingual notifications...")

    # System
    broadcast_system_notification(
        "Welcome to FOMO!", "Добро пожаловать в FOMO!",
        "Your Decision Layer for crypto markets. Set up notifications in profile.",
        "Ваш Decision Layer для крипторынка. Настройте уведомления в профиле.",
        {"screen": "profile"}, "MEDIUM",
    )
    broadcast_system_notification(
        "FOMO v2.0: New features", "FOMO v2.0: Новые функции",
        "Deep Intel modules, Edge capabilities, signal track record and MiniApp integration.",
        "Deep Intel модули, Edge-возможности, трек-рекорд сигналов и MiniApp-интеграция.",
        {"screen": "home"}, "HIGH",
    )
    broadcast_system_notification(
        "Telegram bot connected", "Telegram-бот подключён",
        "Link Telegram for alerts and support. Profile → Connected Apps.",
        "Привяжите Telegram для оповещений и поддержки. Profile → Connected Apps.",
        {"screen": "profile"}, "LOW",
    )

    # Signal
    create_signal_notification(
        asset="BTC",
        title_en="BTC: Strong BUY signal",
        title_ru="BTC: Сильный BUY-сигнал",
        body_en="Confidence 92%. All modules confirm bullish trend.",
        body_ru="Уверенность 92%. Все модули подтверждают бычий тренд.",
        action="BUY", confidence=0.92, screen="home", priority="HIGH",
    )
    create_signal_notification(
        asset="ETH",
        title_en="ETH: Decision changed to BUY",
        title_ru="ETH: Решение изменилось на BUY",
        body_en="Sentiment increased, on-chain activity rose.",
        body_ru="Сентимент вырос, on-chain активность повысилась.",
        action="BUY", confidence=0.78, screen="home", priority="HIGH",
    )
    create_signal_notification(
        asset="SOL",
        title_en="SOL: Resistance level breakout",
        title_ru="SOL: Пробой уровня сопротивления",
        body_en="SOL broke $85. Next target $95.",
        body_ru="SOL пробил $85. Следующая цель $95.",
        action="BUY", confidence=0.83, screen="feed", priority="MEDIUM",
    )
    create_signal_notification(
        asset="BTC",
        title_en="BTC: High confidence 88%",
        title_ru="BTC: Высокая уверенность 88%",
        body_en="Fractal analysis confirms trend continuation.",
        body_ru="Фрактальный анализ подтверждает продолжение тренда.",
        action="BUY", confidence=0.88, screen="home", priority="MEDIUM",
    )
    create_signal_notification(
        asset="DOGE",
        title_en="DOGE: Volume spike +180%",
        title_ru="DOGE: Всплеск объёма +180%",
        body_en="Anomalous volume growth. Possible significant price move.",
        body_ru="Аномальный рост объёмов. Возможен значительный ценовой движ.",
        action="WAIT", confidence=0.65, screen="feed", priority="LOW",
    )

    logger.info("Seeded initial bilingual notifications (3 system + 5 signal)")


# ═══════════════════════════════════════════════════
#  EDGE NOTIFICATIONS (early money triggers)
# ═══════════════════════════════════════════════════

def create_edge_notification(
    asset: str,
    title_en: str, title_ru: str,
    body_en: str, body_ru: str,
    confidence: float = None,
    edge_type: str = "edge",
    priority: str = "HIGH",
) -> str:
    """Create an EDGE notification — early opportunity detected."""
    data = {"asset": asset, "screen": "edge", "edgeType": edge_type}
    if confidence is not None:
        data["confidence"] = confidence
    return create_notification("EDGE", title_en, title_ru, body_en, body_ru, data, priority, icon="flash")


def create_fomo_notification(
    asset: str,
    title_en: str, title_ru: str,
    body_en: str, body_ru: str,
    pnl_pct: float = None,
    priority: str = "HIGH",
) -> str:
    """Create a FOMO notification — missed opportunity."""
    data = {"asset": asset, "screen": "home"}
    if pnl_pct is not None:
        data["pnlPct"] = pnl_pct
    return create_notification("FOMO", title_en, title_ru, body_en, body_ru, data, priority, icon="alert-circle")


def generate_live_notifications():
    """
    Generate real-time notifications from current market data.
    Called periodically by the scheduler.
    """
    from services.signals_service import generate_signal
    from services.edge_opportunities import generate_edge_opportunities

    try:
        # 1. Check Edge opportunities for new EDGE notifications
        edges = generate_edge_opportunities()
        for edge in edges:
            if edge["confidence"] >= 70:
                # Check if we already notified about this edge
                existing = notifications_col.find_one({
                    "type": "EDGE",
                    "data.asset": edge["asset"],
                    "data.edgeType": edge["type"],
                })
                if not existing:
                    create_edge_notification(
                        asset=edge["asset"],
                        title_en=f"{edge['asset']}: Early edge detected ({edge['confidence']}%)",
                        title_ru=f"{edge['asset']}: Ранний сигнал ({edge['confidence']}%)",
                        body_en=f"{edge['title']}. Signal forming. You are early.",
                        body_ru=f"{edge['title']}. Сигнал формируется. Вы раньше других.",
                        confidence=edge["confidence"] / 100,
                        edge_type=edge["type"],
                    )

        # 2. Check signals for confirmation notifications
        for asset in ["BTC", "ETH", "SOL"]:
            sig = generate_signal(asset)
            if sig["action"] in ("BUY", "SELL") and sig["confidence"] >= 0.6:
                existing = notifications_col.find_one({
                    "type": "SIGNAL",
                    "data.asset": asset,
                    "data.action": sig["action"],
                    "data.confidence": {"$gte": 0.6},
                })
                if not existing:
                    create_signal_notification(
                        asset=asset,
                        title_en=f"{asset} → {sig['action']} confirmed",
                        title_ru=f"{asset} → {sig['action']} подтверждён",
                        body_en=f"Confidence {int(sig['confidence']*100)}%. Most users entering now.",
                        body_ru=f"Уверенность {int(sig['confidence']*100)}%. Большинство входят сейчас.",
                        action=sig["action"], confidence=sig["confidence"],
                        screen="home", priority="HIGH",
                    )

    except Exception as e:
        logger.error(f"generate_live_notifications error: {e}")


def seed_edge_and_fomo_notifications():
    """Seed EDGE and FOMO notifications from current real data."""
    from services.edge_opportunities import generate_edge_opportunities

    # Only seed if no EDGE notifications exist
    if notifications_col.count_documents({"type": "EDGE"}) > 0:
        return

    edges = generate_edge_opportunities()
    for edge in edges[:3]:
        create_edge_notification(
            asset=edge["asset"],
            title_en=f"{edge['asset']}: {edge['badge']}",
            title_ru=f"{edge['asset']}: {edge['badge']}",
            body_en=f"{edge['title']}. You are early. Most will enter later.",
            body_ru=f"{edge['title']}. Вы раньше. Большинство войдут позже.",
            confidence=edge["confidence"] / 100,
            edge_type=edge["type"],
        )

    # FOMO notification
    create_fomo_notification(
        asset="BTC",
        title_en="You missed BTC +3.9%",
        title_ru="Вы пропустили BTC +3.9%",
        body_en="This signal was visible in Edge 14h ago. See current edges before they move.",
        body_ru="Этот сигнал был виден в Edge 14ч назад. Смотрите текущие сигналы пока не поздно.",
        pnl_pct=3.9,
    )

    logger.info(f"Seeded {len(edges[:3])} EDGE + 1 FOMO notifications")

