"""
Behavior Engine — User State Machine + Smart Push + Conversion Tracking.

Tracks user actions, adapts notifications, prevents spam, measures revenue.
"""

import os
import logging
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient, DESCENDING
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent.parent / '.env')
logger = logging.getLogger(__name__)

MONGO_URL = os.getenv('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.getenv('DB_NAME', 'test_database')

client = MongoClient(MONGO_URL)
db = client[DB_NAME]

behavior_col = db['user_behavior']
events_col = db['behavior_events']
push_log_col = db['push_log']

# Indexes
behavior_col.create_index('userId', unique=True)
events_col.create_index([('userId', 1), ('createdAt', DESCENDING)])
events_col.create_index('type')
push_log_col.create_index([('userId', 1), ('sentAt', DESCENDING)])


# ═══════════════════════════════════════
#  1. USER STATE MACHINE
# ═══════════════════════════════════════

def get_user_state(user_id: str) -> dict:
    """Get or create user behavior state."""
    state = behavior_col.find_one({'userId': user_id}, {'_id': 0})
    if not state:
        state = {
            'userId': user_id,
            'lastActiveAt': datetime.now(timezone.utc).isoformat(),
            'lastAction': None,
            'totalSessions': 0,
            'edgeViews': 0,
            'edgeClicks': 0,
            'signalViews': 0,
            'tradeOpens': 0,
            'paywallViews': 0,
            'missedSignalsShown': 0,
            'pushesReceived24h': 0,
            'pushesIgnored': 0,
            'pushesClicked': 0,
            'preferredAssets': ['BTC'],
            'ignoredAssets': [],
            'conversionFunnel': 'awareness',  # awareness → interest → desire → action
            'engagementScore': 0.5,
            'createdAt': datetime.now(timezone.utc).isoformat(),
        }
        behavior_col.insert_one({**state, '_id': user_id})
    return state


def track_event(user_id: str, event_type: str, data: dict = None) -> dict:
    """Track a user behavior event. Returns updated state."""
    now = datetime.now(timezone.utc)

    # Record event
    events_col.insert_one({
        'userId': user_id,
        'type': event_type,
        'data': data or {},
        'createdAt': now,
    })

    # Update state
    updates: dict = {
        '$set': {'lastActiveAt': now.isoformat(), 'lastAction': event_type},
        '$inc': {},
    }

    if event_type == 'session_start':
        updates['$inc']['totalSessions'] = 1
    elif event_type == 'edge_view':
        updates['$inc']['edgeViews'] = 1
    elif event_type == 'edge_click':
        updates['$inc']['edgeClicks'] = 1
        if data and data.get('asset'):
            updates['$addToSet'] = {'preferredAssets': data['asset']}
    elif event_type == 'signal_view':
        updates['$inc']['signalViews'] = 1
    elif event_type == 'trade_open':
        updates['$inc']['tradeOpens'] = 1
        updates['$set']['conversionFunnel'] = 'action'
    elif event_type == 'paywall_view':
        updates['$inc']['paywallViews'] = 1
        updates['$set']['conversionFunnel'] = 'desire'
    elif event_type == 'push_clicked':
        updates['$inc']['pushesClicked'] = 1
    elif event_type == 'push_ignored':
        updates['$inc']['pushesIgnored'] = 1
    elif event_type == 'converted_to_pro':
        updates['$set']['conversionFunnel'] = 'converted'

    # Clean up empty $inc
    if not updates['$inc']:
        del updates['$inc']

    behavior_col.update_one(
        {'userId': user_id},
        updates,
        upsert=True,
    )

    # Recalculate engagement score
    _recalc_engagement(user_id)

    return get_user_state(user_id)


def _recalc_engagement(user_id: str):
    """Recalculate engagement score based on recent activity."""
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)

    recent_events = events_col.count_documents({
        'userId': user_id,
        'createdAt': {'$gte': week_ago},
    })

    clicks = events_col.count_documents({
        'userId': user_id,
        'type': {'$in': ['edge_click', 'signal_view', 'trade_open']},
        'createdAt': {'$gte': week_ago},
    })

    # Score: 0-1 based on activity
    score = min(1.0, (recent_events * 0.05) + (clicks * 0.15))

    behavior_col.update_one(
        {'userId': user_id},
        {'$set': {'engagementScore': round(score, 2)}},
    )


# ═══════════════════════════════════════
#  2. SMART PUSH LOGIC
# ═══════════════════════════════════════

def should_send_push(user_id: str, push_type: str, asset: str = None) -> tuple[bool, str]:
    """
    Decide if a push should be sent. Returns (should_send, reason).
    Anti-spam + personalization + priority.
    """
    state = get_user_state(user_id)
    now = datetime.now(timezone.utc)

    # Rate limit: max 5 pushes per 24h
    day_ago = now - timedelta(hours=24)
    recent_pushes = push_log_col.count_documents({
        'userId': user_id,
        'sentAt': {'$gte': day_ago},
    })
    if recent_pushes >= 5:
        return False, 'rate_limited'

    # If user ignored last 3 pushes, downgrade
    recent_ignored = events_col.count_documents({
        'userId': user_id,
        'type': 'push_ignored',
        'createdAt': {'$gte': day_ago},
    })
    if recent_ignored >= 3 and push_type not in ('signal_confirmed', 'big_move'):
        return False, 'user_disengaged'

    # Asset preference: don't push ignored assets
    if asset and asset in state.get('ignoredAssets', []):
        return False, 'asset_ignored'

    # Duplicate check: don't push same type+asset within 4h
    four_h_ago = now - timedelta(hours=4)
    duplicate = push_log_col.find_one({
        'userId': user_id,
        'pushType': push_type,
        'asset': asset,
        'sentAt': {'$gte': four_h_ago},
    })
    if duplicate:
        return False, 'duplicate_recent'

    return True, 'ok'


def log_push_sent(user_id: str, push_type: str, asset: str = None, data: dict = None):
    """Log that a push was sent."""
    push_log_col.insert_one({
        'userId': user_id,
        'pushType': push_type,
        'asset': asset,
        'data': data or {},
        'sentAt': datetime.now(timezone.utc),
    })
    behavior_col.update_one(
        {'userId': user_id},
        {'$inc': {'pushesReceived24h': 1}},
    )


# ═══════════════════════════════════════
#  3. PRIORITY ENGINE
# ═══════════════════════════════════════

def calculate_push_priority(
    edge_score: float = 0,
    signal_confidence: float = 0,
    user_engagement: float = 0.5,
    is_preferred_asset: bool = True,
) -> float:
    """
    Calculate push priority score (0-1).
    Only send if priority > 0.4
    """
    priority = (
        edge_score * 0.35 +
        signal_confidence * 0.30 +
        (0.1 if is_preferred_asset else 0) +
        user_engagement * 0.15 +
        0.10  # base
    )
    return round(min(1.0, priority), 2)


# ═══════════════════════════════════════
#  4. PERSONALIZED PUSH SELECTOR
# ═══════════════════════════════════════

def get_personalized_push(user_id: str, context: dict) -> dict | None:
    """
    Select the best push for this user based on their behavior.
    Returns push dict or None if shouldn't send.
    """
    state = get_user_state(user_id)
    funnel = state.get('conversionFunnel', 'awareness')
    engagement = state.get('engagementScore', 0.5)
    edge_clicks = state.get('edgeClicks', 0)
    trade_opens = state.get('tradeOpens', 0)
    paywall_views = state.get('paywallViews', 0)

    # If user clicks Edge but doesn't buy PRO
    if edge_clicks > 3 and funnel != 'converted' and paywall_views > 0:
        return {
            'type': 'conversion_nudge',
            'title_en': 'You keep finding early signals',
            'body_en': 'Execution is locked. Unlock before next confirmation.',
            'cta': 'UNLOCK EARLY ACCESS',
            'screen': 'paywall',
            'priority': 'critical',
        }

    # If user ignores Edge
    if edge_clicks == 0 and state.get('edgeViews', 0) > 0:
        return {
            'type': 'edge_reminder',
            'title_en': 'Signals you saw already moved',
            'body_en': 'You keep missing early entries. Check current edges.',
            'cta': 'See edges',
            'screen': 'edge',
            'priority': 'silent',
        }

    # Active trader
    if trade_opens > 2:
        return {
            'type': 'trader_update',
            'title_en': f'New setup available',
            'body_en': context.get('summary', 'High conviction setup detected.'),
            'cta': 'Open Trade',
            'screen': 'home',
            'priority': 'critical',
        }

    # Default: engagement-based
    if engagement < 0.3:
        return {
            'type': 'reactivation',
            'title_en': 'Market changed while you were away',
            'body_en': 'New signals available. Check what you missed.',
            'cta': 'Open App',
            'screen': 'home',
            'priority': 'silent',
        }

    return None


# ═══════════════════════════════════════
#  5. CONVERSION TRACKING
# ═══════════════════════════════════════

def get_conversion_stats() -> dict:
    """Get conversion funnel stats across all users."""
    pipeline = [
        {'$group': {
            '_id': '$conversionFunnel',
            'count': {'$sum': 1},
        }},
    ]
    results = list(behavior_col.aggregate(pipeline))
    funnel = {r['_id']: r['count'] for r in results}

    total = sum(funnel.values()) or 1
    return {
        'funnel': funnel,
        'conversionRate': round(funnel.get('converted', 0) / total * 100, 1),
        'paywallRate': round(funnel.get('desire', 0) / total * 100, 1),
        'totalUsers': total,
    }


def get_push_effectiveness() -> dict:
    """Get push notification effectiveness metrics."""
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)

    total_sent = push_log_col.count_documents({'sentAt': {'$gte': week_ago}})
    total_clicked = events_col.count_documents({
        'type': 'push_clicked',
        'createdAt': {'$gte': week_ago},
    })

    # By type
    pipeline = [
        {'$match': {'sentAt': {'$gte': week_ago}}},
        {'$group': {'_id': '$pushType', 'count': {'$sum': 1}}},
    ]
    by_type = {r['_id']: r['count'] for r in push_log_col.aggregate(pipeline)}

    return {
        'totalSent': total_sent,
        'totalClicked': total_clicked,
        'clickRate': round(total_clicked / max(total_sent, 1) * 100, 1),
        'byType': by_type,
    }
