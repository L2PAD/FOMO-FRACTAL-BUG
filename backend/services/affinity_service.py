"""
Affinity Service — Dynamic User-Asset Relationship Scoring
============================================================

NOT a simple counter. A weighted behavioral model with exponential decay.

Formula:
  raw_score = (views * 1) + (time_spent * 2) + (clicks * 3) +
              (notifications_opened * 4) + (positions_opened * 5) -
              (ignored_signals * 2)

  affinity = raw_score * exp(-time_since_last_interaction / τ)

  τ = 72h (3 days half-life)

Output: { SOL: 0.82, ETH: 0.55, BTC: 0.91 }
"""

import math
import logging
import os
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient, DESCENDING
from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent
load_dotenv(ROOT_DIR / '.env')

logger = logging.getLogger(__name__)

MONGO_URL = os.getenv('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.getenv('DB_NAME', 'test_database')

client = MongoClient(MONGO_URL)
db = client[DB_NAME]

events_col = db['behavior_events']
affinity_col = db['user_affinity']
affinity_col.create_index([('userId', 1)], unique=True)

# ═══════════════════════════════════════
#  WEIGHTS
# ═══════════════════════════════════════

WEIGHTS = {
    'VIEW_ASSET': 1.0,
    'view_asset': 1.0,
    'OPEN_INTELLIGENCE': 1.5,
    'open_intelligence': 1.5,
    'TIME_ON_SCREEN': 2.0,       # per 10 seconds
    'time_on_screen': 2.0,
    'CLICK_SIGNAL': 3.0,
    'click_signal': 3.0,
    'edge_click': 3.0,
    'signal_view': 2.0,
    'OPEN_NOTIFICATION': 4.0,
    'open_notification': 4.0,
    'push_clicked': 4.0,
    'OPEN_POSITION': 5.0,
    'open_position': 5.0,
    'trade_open': 5.0,
    'IGNORE_SIGNAL': -2.0,
    'ignore_signal': -2.0,
    'push_ignored': -1.5,
}

# Decay constant: τ = 72 hours (in seconds)
TAU_SECONDS = 72 * 3600

# Default assets to always include
DEFAULT_ASSETS = ['BTC', 'ETH', 'SOL']


# ═══════════════════════════════════════
#  COMPUTE AFFINITY
# ═══════════════════════════════════════

def compute_affinity(user_id: str, lookback_days: int = 14) -> dict:
    """
    Compute weighted affinity scores for all assets the user interacted with.
    Applies exponential time decay.
    Returns: { 'BTC': 0.91, 'SOL': 0.82, 'ETH': 0.55, ... }
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=lookback_days)

    # Get all events for this user in lookback window
    events = list(events_col.find({
        'userId': user_id,
        'createdAt': {'$gte': cutoff},
    }).sort('createdAt', DESCENDING))

    # Aggregate raw scores per asset
    asset_scores = {}
    asset_last_seen = {}

    for event in events:
        event_type = event.get('type', '')
        data = event.get('data', {}) or {}
        symbol = data.get('symbol', data.get('asset', '')).upper()
        created_at = event.get('createdAt', now)

        if not symbol:
            continue

        weight = WEIGHTS.get(event_type, 0.5)

        # Special handling for time_on_screen
        if 'time' in event_type.lower():
            seconds = data.get('seconds', data.get('duration', 10))
            weight = WEIGHTS.get(event_type, 2.0) * (seconds / 10)

        # Time decay: exp(-Δt / τ)
        if isinstance(created_at, datetime):
            # Make both timezone-aware
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            delta_seconds = (now - created_at).total_seconds()
        else:
            delta_seconds = 0
        decay = math.exp(-max(0, delta_seconds) / TAU_SECONDS)

        # Accumulate
        if symbol not in asset_scores:
            asset_scores[symbol] = 0
        asset_scores[symbol] += weight * decay

        # Track last interaction time
        if symbol not in asset_last_seen or created_at > asset_last_seen[symbol]:
            asset_last_seen[symbol] = created_at

    # Also factor in open positions (strong signal of interest)
    positions = list(db['portfolio_positions'].find({
        'userId': user_id,
        'status': 'OPEN',
    }))
    for pos in positions:
        sym = pos.get('symbol', '').upper()
        if sym:
            asset_scores[sym] = asset_scores.get(sym, 0) + 5.0  # Position = strong affinity

    # Ensure default assets exist
    for asset in DEFAULT_ASSETS:
        if asset not in asset_scores:
            asset_scores[asset] = 0.1  # Minimum presence

    # Normalize to 0-1 range
    if asset_scores:
        max_score = max(asset_scores.values()) or 1
        normalized = {k: round(min(1.0, v / max_score), 3) for k, v in asset_scores.items()}
    else:
        normalized = {a: 0.5 for a in DEFAULT_ASSETS}

    # Sort by score descending
    sorted_affinity = dict(sorted(normalized.items(), key=lambda x: x[1], reverse=True))

    # Cache result
    affinity_col.update_one(
        {'userId': user_id},
        {'$set': {
            'affinity': sorted_affinity,
            'rawScores': {k: round(v, 2) for k, v in asset_scores.items()},
            'lastSeen': {k: v.isoformat() if isinstance(v, datetime) else str(v) for k, v in asset_last_seen.items()},
            'updatedAt': now,
        }},
        upsert=True,
    )

    return sorted_affinity


def get_cached_affinity(user_id: str) -> dict:
    """Get cached affinity or compute fresh."""
    doc = affinity_col.find_one({'userId': user_id})
    if doc:
        updated = doc.get('updatedAt')
        if updated and isinstance(updated, datetime):
            now = datetime.now(timezone.utc)
            if updated.tzinfo is None:
                updated = updated.replace(tzinfo=timezone.utc)
            age_min = (now - updated).total_seconds() / 60
            if age_min < 5:  # Cache for 5 minutes
                return doc.get('affinity', {})
    return compute_affinity(user_id)


def get_top_affinity_assets(user_id: str, limit: int = 5) -> list:
    """Get user's top affinity assets sorted by score."""
    affinity = get_cached_affinity(user_id)
    return [{'symbol': k, 'score': v} for k, v in list(affinity.items())[:limit]]


def get_asset_affinity(user_id: str, symbol: str) -> float:
    """Get affinity score for a specific asset."""
    affinity = get_cached_affinity(user_id)
    return affinity.get(symbol.upper(), 0.0)


# ═══════════════════════════════════════
#  USER STATE ENGINE
# ═══════════════════════════════════════

def compute_user_state(user_id: str) -> dict:
    """
    Determine user engagement state based on last activity.

    States:
      ACTIVE     — interacted in last 6h
      DORMANT    — 6h-24h since last interaction
      SLEEPING   — 24h-72h
      CHURN_RISK — 72h+
    """
    now = datetime.now(timezone.utc)

    # Get last event
    last_event = events_col.find_one(
        {'userId': user_id},
        sort=[('createdAt', DESCENDING)]
    )

    if not last_event or not last_event.get('createdAt'):
        return {
            'state': 'NEW',
            'hoursSinceActive': 999,
            'pushStrategy': 'onboarding',
            'pushIntensity': 'low',
        }

    last_active = last_event['createdAt']
    if not isinstance(last_active, datetime):
        last_active = now

    # Ensure timezone-aware comparison
    if last_active.tzinfo is None:
        last_active = last_active.replace(tzinfo=timezone.utc)

    hours_since = (now - last_active).total_seconds() / 3600

    if hours_since < 6:
        state = 'ACTIVE'
        strategy = 'momentum'      # More edge/momentum pushes
        intensity = 'normal'
    elif hours_since < 24:
        state = 'DORMANT'
        strategy = 'pnl_update'    # PnL-based return triggers
        intensity = 'medium'
    elif hours_since < 72:
        state = 'SLEEPING'
        strategy = 'regret_fomo'   # Missed signals, regret pushes
        intensity = 'high'
    else:
        state = 'CHURN_RISK'
        strategy = 'reactivation'  # Strongest: "Market moving without you"
        intensity = 'critical'

    result = {
        'state': state,
        'hoursSinceActive': round(hours_since, 1),
        'pushStrategy': strategy,
        'pushIntensity': intensity,
    }

    # Update in behavior collection
    db['user_behavior'].update_one(
        {'userId': user_id},
        {'$set': {
            'userState': state,
            'hoursSinceActive': round(hours_since, 1),
            'pushStrategy': strategy,
            'stateUpdatedAt': now,
        }},
        upsert=True,
    )

    return result


# ═══════════════════════════════════════
#  BEHAVIOR MEMORY (for contextual pushes)
# ═══════════════════════════════════════

def get_behavior_memory(user_id: str, symbol: str) -> dict:
    """
    Get behavior memory for a specific asset.
    Used to build contextual push messages.

    Returns: {
      'lastViewed': '2h ago',
      'viewCount': 5,
      'wasIgnored': False,
      'hasPosition': True,
      'pnlSinceLastView': +3.2,
      'narrative': 'You checked SOL yesterday. Now it's moving.'
    }
    """
    now = datetime.now(timezone.utc)
    sym = symbol.upper()

    # Last view of this asset
    last_view = events_col.find_one(
        {
            'userId': user_id,
            'data.symbol': sym,
            'type': {'$in': ['VIEW_ASSET', 'view_asset', 'OPEN_INTELLIGENCE', 'signal_view', 'edge_click']},
        },
        sort=[('createdAt', DESCENDING)],
    )

    # View count in last 7 days
    week_ago = now - timedelta(days=7)
    view_count = events_col.count_documents({
        'userId': user_id,
        'data.symbol': sym,
        'createdAt': {'$gte': week_ago},
    })

    # Was signal ignored?
    ignored = events_col.find_one({
        'userId': user_id,
        'data.symbol': sym,
        'type': {'$in': ['IGNORE_SIGNAL', 'ignore_signal', 'push_ignored']},
        'createdAt': {'$gte': week_ago},
    })

    # Has open position?
    position = db['portfolio_positions'].find_one({
        'userId': user_id,
        'symbol': sym,
        'status': 'OPEN',
    })

    # Price change since last view
    price_at_view = None
    if last_view and last_view.get('data', {}).get('price'):
        price_at_view = float(last_view['data']['price'])

    # Build memory object
    memory = {
        'symbol': sym,
        'lastViewed': last_view['createdAt'].isoformat() if last_view else None,
        'hoursSinceView': None,
        'viewCount': view_count,
        'wasIgnored': ignored is not None,
        'hasPosition': position is not None,
        'positionSide': position.get('side') if position else None,
        'positionPnl': position.get('pnlPct', 0) if position else None,
    }

    if last_view and last_view.get('createdAt'):
        hours = (now - last_view['createdAt']).total_seconds() / 3600
        memory['hoursSinceView'] = round(hours, 1)

    # Build narrative
    memory['narrative'] = _build_narrative(memory)

    return memory


def _build_narrative(memory: dict) -> str:
    """Build a human narrative from behavior memory."""
    sym = memory.get('symbol', '')
    hours = memory.get('hoursSinceView')
    views = memory.get('viewCount', 0)
    ignored = memory.get('wasIgnored', False)
    has_pos = memory.get('hasPosition', False)
    pnl = memory.get('positionPnl', 0)

    # Has position + PnL
    if has_pos and pnl:
        if pnl > 2:
            return f"You entered {sym} early. Still building."
        elif pnl > 0:
            return f"Your {sym} position. Momentum forming."
        elif pnl > -2:
            return f"Your {sym} position. Watching closely."
        else:
            return f"Your {sym} under pressure. Re-evaluate."

    # Ignored signal
    if ignored:
        return f"You passed on {sym} earlier. It kept moving."

    # Recent viewer
    if hours and hours < 6:
        return f"You were just looking at {sym}."
    elif hours and hours < 24:
        if views > 3:
            return f"You keep coming back to {sym}."
        return f"You checked {sym} yesterday."
    elif hours and hours < 72:
        return f"You looked at {sym} {int(hours / 24)}d ago."

    # High view count
    if views > 5:
        return f"You watch {sym} often."
    elif views > 2:
        return f"{sym} caught your attention."

    return ""


# ═══════════════════════════════════════
#  FEED MUTATION DATA
# ═══════════════════════════════════════

def get_feed_mutations(user_id: str) -> dict:
    """
    Get feed personalization mutations based on user behavior.

    Returns:
    {
      'ordering_boost': { 'SOL': 0.3, 'BTC': 0.27, ... },  // affinity boost for sorting
      'highlights': [
        { 'symbol': 'SOL', 'message': 'You keep watching SOL', 'type': 'affinity' },
      ],
      'narratives': [
        { 'symbol': 'SOL', 'original': 'SOL forming', 'rewrite': 'You saw this forming. Now it's faster.', 'type': 'rewrite' },
      ],
      'userState': 'ACTIVE',
    }
    """
    affinity = get_cached_affinity(user_id)
    user_state = compute_user_state(user_id)

    mutations = {
        'ordering_boost': {},
        'highlights': [],
        'narratives': [],
        'userState': user_state.get('state', 'NEW'),
        'affinity': affinity,
    }

    # Level 1: Ordering boost (affinity * 0.3)
    for sym, score in affinity.items():
        mutations['ordering_boost'][sym] = round(score * 0.3, 3)

    # Level 2: Highlights for high-affinity assets
    for sym, score in affinity.items():
        if score >= 0.7:
            memory = get_behavior_memory(user_id, sym)
            narrative = memory.get('narrative', '')
            if narrative:
                mutations['highlights'].append({
                    'symbol': sym,
                    'message': narrative,
                    'score': score,
                    'type': 'affinity',
                })

    # Level 3: Narrative rewrites based on state
    state = user_state.get('state', 'ACTIVE')
    top_assets = list(affinity.keys())[:3]

    for sym in top_assets:
        memory = get_behavior_memory(user_id, sym)

        if state == 'SLEEPING' and memory.get('wasIgnored'):
            mutations['narratives'].append({
                'symbol': sym,
                'rewrite': f"You passed on {sym} earlier. It kept moving.",
                'emotion': 'regret',
                'type': 'rewrite',
            })
        elif state == 'DORMANT' and memory.get('hasPosition'):
            pnl = memory.get('positionPnl', 0)
            if pnl > 0:
                mutations['narratives'].append({
                    'symbol': sym,
                    'rewrite': f"Your {sym} is up. You entered before the crowd.",
                    'emotion': 'validation',
                    'type': 'rewrite',
                })
        elif memory.get('viewCount', 0) > 3:
            mutations['narratives'].append({
                'symbol': sym,
                'rewrite': f"You keep coming back to {sym}. It's forming again.",
                'emotion': 'fomo',
                'type': 'rewrite',
            })

    return mutations
