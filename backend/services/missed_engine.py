"""
FOMO Missed Signals Engine — Honest system.

A signal is "missed" when ALL conditions are true:
  1. Signal is CLOSED
  2. Signal had high confidence (>= 0.8) and action != WAIT
  3. User did NOT see the signal (no exposure record)
  4. Signal was profitable (outcome == WIN)
  5. The move was material (above threshold for the horizon)

Collections:
  - user_activity: tracks when user was last seen
  - signal_exposure: tracks which signals user has seen
"""
import logging
import os
from datetime import datetime
from pymongo import MongoClient, ASCENDING, DESCENDING
from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent
load_dotenv(ROOT_DIR / '.env')

logger = logging.getLogger(__name__)

MONGO_URL = os.getenv('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.getenv('DB_NAME', 'test_database')

client = MongoClient(MONGO_URL)
db = client[DB_NAME]

# Collections
user_activity_col = db['user_activity']
signal_exposure_col = db['signal_exposure']
signals_col = db['signal_history']

# Indexes
user_activity_col.create_index([('userId', ASCENDING)], unique=True)
signal_exposure_col.create_index([('userId', ASCENDING), ('signalId', ASCENDING)], unique=True)
signal_exposure_col.create_index([('userId', ASCENDING)])

# ==================== THRESHOLDS ====================
# Honest thresholds — if the move was smaller, don't call it "missed"
MISSED_MOVE_THRESHOLDS = {
    'SCALP': 1.0,
    'INTRADAY': 1.5,
    'SWING': 2.5,
}

MIN_CONFIDENCE = 0.8


# ==================== USER ACTIVITY ====================

def mark_user_seen(user_id: str, screen: str = 'home') -> bool:
    """Update user's lastSeen timestamp. Called on app open / Home visit."""
    try:
        now = datetime.utcnow()
        update_fields = {
            'lastSeenAt': now,
            'updatedAt': now,
        }
        if screen == 'home':
            update_fields['lastHomeSeenAt'] = now

        user_activity_col.update_one(
            {'userId': user_id},
            {'$set': update_fields},
            upsert=True,
        )
        return True
    except Exception as e:
        logger.error(f"mark_user_seen error: {e}")
        return False


def get_user_activity(user_id: str) -> dict | None:
    """Get user activity data"""
    return user_activity_col.find_one({'userId': user_id})


# ==================== SIGNAL EXPOSURE ====================

def mark_signal_exposure(user_id: str, signal_id: str, symbol: str = '', screen: str = 'home') -> bool:
    """Record that a user has seen a specific signal"""
    try:
        signal_exposure_col.update_one(
            {'userId': user_id, 'signalId': signal_id},
            {'$set': {
                'userId': user_id,
                'signalId': signal_id,
                'symbol': symbol,
                'screen': screen,
                'seenAt': datetime.utcnow(),
            }},
            upsert=True,
        )
        return True
    except Exception as e:
        logger.error(f"mark_signal_exposure error: {e}")
        return False


# ==================== MISSED SIGNALS ====================

def get_missed_signals(user_id: str, asset: str = None, limit: int = 3) -> dict:
    """
    Compute honestly missed signals for a user.

    A signal is missed if:
    - CLOSED (within last 7 days)
    - confidence >= 0.8
    - action != WAIT
    - outcome == WIN (only profitable — honest, no grey zones)
    - pnlPct > threshold for the horizon
    - user did NOT have an exposure record for this signal

    Primary honesty check: exposure tracking (user didn't see it on screen).
    Secondary: if user has lastSeenAt, signals entered before that are 
    still missed if user never saw them.
    """
    from datetime import timedelta

    empty = {
        'asset': asset or 'ALL',
        'count': 0,
        'avgMovePct': 0,
        'items': [],
    }

    # Rolling window — only look at last 7 days of signals
    cutoff = datetime.utcnow() - timedelta(days=7)

    # Build signal query
    query = {
        'status': 'CLOSED',
        'action': {'$ne': 'WAIT'},
        'confidence': {'$gte': MIN_CONFIDENCE},
        'outcome': 'WIN',
        'pnlPct': {'$gt': 0},
        'closeTs': {'$gte': cutoff},  # Only recent signals
    }

    if asset:
        query['asset'] = asset

    # Fetch candidates (sorted by close time, most recent first)
    candidates = list(signals_col.find(
        query,
        sort=[('closeTs', DESCENDING)],
    ).limit(50))

    if not candidates:
        return empty

    # Filter out signals user has seen (the HONEST check)
    candidate_ids = [str(c['_id']) for c in candidates]
    exposures = list(signal_exposure_col.find({
        'userId': user_id,
        'signalId': {'$in': candidate_ids},
    }))
    seen_set = set(e['signalId'] for e in exposures)

    # Apply threshold filter and exposure filter
    missed = []
    for signal in candidates:
        sig_id = str(signal['_id'])

        # Skip if user saw this signal (honest: they saw it)
        if sig_id in seen_set:
            continue

        # Check material move threshold
        horizon = signal.get('horizon', 'INTRADAY')
        threshold = MISSED_MOVE_THRESHOLDS.get(horizon, 1.5)
        pnl = signal.get('pnlPct', 0)

        if pnl < threshold:
            continue

        missed.append(signal)

    # Take top N
    top = missed[:limit]

    if not top:
        return empty

    avg_move = sum(abs(s.get('pnlPct', 0)) for s in top) / len(top)

    return {
        'asset': asset or 'ALL',
        'count': len(top),
        'avgMovePct': round(avg_move, 2),
        'items': [
            {
                'id': str(s['_id']),
                'asset': s.get('asset', ''),
                'symbol': s.get('symbol', ''),
                'action': s.get('action', ''),
                'confidence': s.get('confidence', 0),
                'entryPrice': s.get('entryPrice', 0),
                'closePrice': s.get('closePrice', 0),
                'pnlPct': s.get('pnlPct', 0),
                'outcome': s.get('outcome', ''),
                'entryTs': s['entryTs'].isoformat() if s.get('entryTs') else None,
                'closeTs': s['closeTs'].isoformat() if s.get('closeTs') else None,
                'horizon': s.get('horizon', ''),
            }
            for s in top
        ],
    }


def get_missed_summary(user_id: str, asset: str = None) -> dict:
    """
    Quick summary for the Home screen block.
    Returns count + avg move — lightweight query.
    """
    result = get_missed_signals(user_id, asset, limit=3)
    return {
        'asset': result['asset'],
        'count': result['count'],
        'avgMovePct': result['avgMovePct'],
        'topItem': result['items'][0] if result['items'] else None,
    }
