"""
FOMO Push Notification Engine — Production Grade

Architecture:
  Signal Engine → DB → Notification Orchestrator → Rule Engine 
    → Eligibility (prefs + limits) → Dedup + Cooldown → Queue (Mongo)
    → Worker (async) → Expo Push API → Mobile (deep link)

Key design decisions (per product owner):
  - Orchestrator pattern (NOT direct triggers from signal creation)
  - scheduledAt from V1 (delayed missed = +15min, quiet hours 23-08)
  - Dedup by type + asset + signalId (not just type)
  - PRO limit = 5/day, FREE = 2/day
  - Priority scoring: confidence*100 + abs(movePct)*10
  - A/B variant support in queue
  - Only BTC/ETH/SOL for V1
  - Only HIGH_CONFIDENCE + MISSED for V1
"""
import logging
import os
import time
import asyncio
from datetime import datetime, timedelta
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

# ==================== COLLECTIONS ====================

push_tokens_col = db['user_push_tokens']
notif_queue_col = db['notifications_queue']
notif_log_col = db['notification_log']
push_analytics_col = db['push_analytics']

# Indexes
push_tokens_col.create_index([('userId', ASCENDING), ('pushToken', ASCENDING)], unique=True)
push_tokens_col.create_index([('userId', ASCENDING)])
notif_queue_col.create_index([('status', ASCENDING), ('scheduledAt', ASCENDING)])
notif_queue_col.create_index([('userId', ASCENDING), ('status', ASCENDING)])
notif_log_col.create_index([('userId', ASCENDING), ('type', ASCENDING), ('sentAt', DESCENDING)])
notif_log_col.create_index([('userId', ASCENDING), ('dedup_key', ASCENDING), ('sentAt', DESCENDING)])

# ==================== CONSTANTS ====================

# V1: Only these assets get push notifications
PUSH_ELIGIBLE_ASSETS = {'BTC', 'ETH', 'SOL'}

# Cooldown periods (seconds)
COOLDOWNS = {
    'HIGH_CONFIDENCE': 7200,   # 2 hours
    'SIGNAL_UPGRADE': 14400,   # 4 hours
    'MISSED': 86400,           # 24 hours
    'DAILY_SUMMARY': 86400,    # 24 hours
}

# Daily caps by plan
DAILY_LIMITS = {
    'FREE': 2,
    'PRO': 5,
    'INSTITUTIONAL': 5,
}

# Quiet hours (UTC-based, adjust per user timezone later)
QUIET_HOUR_START = 23  # 11 PM
QUIET_HOUR_END = 8     # 8 AM

# Missed push delay (seconds)
MISSED_PUSH_DELAY = 900  # 15 minutes


# ==================== TOKEN MANAGEMENT ====================

def register_push_token(user_id: str, push_token: str, platform: str = 'unknown') -> bool:
    """Register or update a user's push token"""
    try:
        now = datetime.utcnow()
        push_tokens_col.update_one(
            {'userId': user_id, 'pushToken': push_token},
            {'$set': {
                'platform': platform,
                'isActive': True,
                'updatedAt': now,
            },
            '$setOnInsert': {
                'createdAt': now,
            }},
            upsert=True,
        )
        logger.info(f"Push token registered: user={user_id} platform={platform}")
        return True
    except Exception as e:
        logger.error(f"Push token registration error: {e}")
        return False


def deactivate_push_token(user_id: str, push_token: str) -> bool:
    """Deactivate a push token (e.g. on logout)"""
    try:
        push_tokens_col.update_one(
            {'userId': user_id, 'pushToken': push_token},
            {'$set': {'isActive': False, 'updatedAt': datetime.utcnow()}},
        )
        return True
    except Exception as e:
        logger.error(f"Push token deactivation error: {e}")
        return False


def get_user_tokens(user_id: str) -> list:
    """Get all active push tokens for a user"""
    return list(push_tokens_col.find({'userId': user_id, 'isActive': True}))


def get_all_active_token_users() -> list:
    """Get all user IDs with active push tokens"""
    pipeline = [
        {'$match': {'isActive': True}},
        {'$group': {'_id': '$userId'}},
    ]
    return [doc['_id'] for doc in push_tokens_col.aggregate(pipeline)]


# ==================== PRIORITY SCORING ====================

def compute_priority(confidence: float = 0, move_pct: float = 0) -> int:
    """
    Simple V1 priority score.
    Higher = more important = send first.
    """
    score = int(confidence * 100) + int(abs(move_pct) * 10)
    return min(score, 200)  # Cap at 200


# ==================== QUIET HOURS ====================

def is_quiet_hours(hour_utc: int = None) -> bool:
    """Check if current time is in quiet hours (23:00-08:00 UTC)"""
    if hour_utc is None:
        hour_utc = datetime.utcnow().hour
    return hour_utc >= QUIET_HOUR_START or hour_utc < QUIET_HOUR_END


def get_next_send_time() -> datetime:
    """Get the next valid send time (after quiet hours)"""
    now = datetime.utcnow()
    if is_quiet_hours(now.hour):
        # Schedule for 8 AM UTC today or tomorrow
        next_morning = now.replace(hour=QUIET_HOUR_END, minute=0, second=0, microsecond=0)
        if next_morning <= now:
            next_morning += timedelta(days=1)
        return next_morning
    return now


# ==================== ANTI-SPAM GUARD ====================

def check_cooldown(user_id: str, notif_type: str) -> bool:
    """Check if cooldown period has passed since last sent notification of this type"""
    cooldown_secs = COOLDOWNS.get(notif_type, 3600)
    cutoff = datetime.utcnow() - timedelta(seconds=cooldown_secs)

    recent = notif_log_col.find_one({
        'userId': user_id,
        'type': notif_type,
        'sentAt': {'$gte': cutoff},
    })
    return recent is None


def check_daily_cap(user_id: str, plan: str = 'FREE') -> bool:
    """Check if user hasn't exceeded daily notification cap"""
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    limit = DAILY_LIMITS.get(plan, 2)

    count = notif_log_col.count_documents({
        'userId': user_id,
        'sentAt': {'$gte': today_start},
    })
    return count < limit


def check_dedup(user_id: str, dedup_key: str) -> bool:
    """
    Check for duplicate notifications using compound dedup key.
    Key format: type:asset:signalId (e.g. HIGH_CONFIDENCE:BTC:sig_123)
    """
    cutoff = datetime.utcnow() - timedelta(hours=2)

    existing = notif_log_col.find_one({
        'userId': user_id,
        'dedup_key': dedup_key,
        'sentAt': {'$gte': cutoff},
    })
    return existing is None


def build_dedup_key(notif_type: str, asset: str, signal_id: str = '') -> str:
    """Build dedup key: type:asset:signalId"""
    parts = [notif_type, asset]
    if signal_id:
        parts.append(signal_id)
    return ':'.join(parts)


# ==================== RULE ENGINE ====================

def should_send_high_confidence(signal: dict) -> bool:
    """Rule: signal confidence >= 0.85 and action != WAIT"""
    return (
        signal.get('confidence', 0) >= 0.85
        and signal.get('action', 'WAIT') != 'WAIT'
        and signal.get('asset', '') in PUSH_ELIGIBLE_ASSETS
    )


def should_send_missed(missed_data: dict) -> bool:
    """Rule: at least 1 missed signal with avg move >= 1.5%"""
    return (
        missed_data.get('count', 0) > 0
        and missed_data.get('avgMovePct', 0) >= 1.5
    )


# ==================== NOTIFICATION BUILDERS ====================

def build_high_confidence_notif(signal: dict, variant: str = 'A') -> dict:
    """Build HIGH_CONFIDENCE notification payload"""
    asset = signal.get('asset', 'BTC')
    action = signal.get('action', 'BUY')
    conf = signal.get('confidence', 0)
    conf_pct = int(conf * 100)
    signal_id = str(signal.get('_id', ''))

    if variant == 'A':
        title = f'{asset} → {action} • {conf_pct}%'
        body = 'Strong signal detected'
    else:
        title = f'High-confidence {asset} signal'
        body = f'The market just aligned — {conf_pct}% conviction'

    return {
        'type': 'HIGH_CONFIDENCE',
        'asset': asset,
        'title': title,
        'body': body,
        'variant': variant,
        'priority': compute_priority(conf, 0),
        'dedup_key': build_dedup_key('HIGH_CONFIDENCE', asset, signal_id),
        'payload': {
            'screen': 'home',
            'asset': asset,
            'action': action,
            'signalId': signal_id,
        },
    }


def build_missed_notif(missed_data: dict, asset: str, variant: str = 'A') -> dict:
    """Build MISSED notification payload (delayed by 15 min)"""
    count = missed_data.get('count', 0)
    avg_move = missed_data.get('avgMovePct', 0)

    if variant == 'A':
        title = f'You missed {count} signal{"s" if count > 1 else ""}'
        body = f'+{avg_move}% avg move — see what happened'
    else:
        title = f'{count} strong signal{"s" if count > 1 else ""} moved without you'
        body = 'See them before they happen'

    return {
        'type': 'MISSED',
        'asset': asset,
        'title': title,
        'body': body,
        'variant': variant,
        'priority': compute_priority(0, avg_move),
        'dedup_key': build_dedup_key('MISSED', asset),
        'payload': {
            'screen': 'paywall',
            'asset': asset,
            'count': count,
            'avgMovePct': avg_move,
        },
    }


# ==================== QUEUE WRITER ====================

def enqueue_notification(
    user_id: str,
    notif: dict,
    plan: str = 'FREE',
    delay_seconds: int = 0,
) -> bool:
    """
    Add notification to queue after passing all anti-spam checks.
    Respects: cooldown, daily cap, dedup, quiet hours.
    """
    notif_type = notif['type']
    dedup_key = notif.get('dedup_key', '')

    # Anti-spam checks
    if not check_cooldown(user_id, notif_type):
        logger.debug(f"Cooldown active: {user_id}/{notif_type}")
        return False

    if not check_daily_cap(user_id, plan):
        logger.debug(f"Daily cap reached: {user_id}")
        return False

    if dedup_key and not check_dedup(user_id, dedup_key):
        logger.debug(f"Duplicate: {user_id}/{dedup_key}")
        return False

    # Compute scheduledAt
    now = datetime.utcnow()
    scheduled_at = now + timedelta(seconds=delay_seconds)

    # Apply quiet hours
    if is_quiet_hours(scheduled_at.hour):
        scheduled_at = get_next_send_time()
        logger.debug(f"Quiet hours — rescheduled to {scheduled_at}")

    # Insert into queue
    doc = {
        'userId': user_id,
        'type': notif_type,
        'asset': notif.get('asset', ''),
        'title': notif['title'],
        'body': notif['body'],
        'payload': notif.get('payload', {}),
        'variant': notif.get('variant', 'A'),
        'priority': notif.get('priority', 50),
        'dedup_key': dedup_key,
        'status': 'PENDING',
        'scheduledAt': scheduled_at,
        'createdAt': now,
        'sentAt': None,
        'opened': False,
        'openedAt': None,
    }
    notif_queue_col.insert_one(doc)

    # Analytics: push_queued
    log_analytics('push_queued', user_id, notif_type, notif.get('asset', ''))

    logger.info(f"Queued {notif_type} for {user_id}: {notif['title']} (scheduled={scheduled_at})")
    return True


# ==================== ANALYTICS ====================

def log_analytics(event: str, user_id: str, notif_type: str = '', asset: str = '', extra: dict = None):
    """Log push analytics event"""
    try:
        doc = {
            'event': event,
            'userId': user_id,
            'type': notif_type,
            'asset': asset,
            'timestamp': datetime.utcnow(),
        }
        if extra:
            doc['extra'] = extra
        push_analytics_col.insert_one(doc)
    except Exception as e:
        logger.warning(f"Analytics log error: {e}")


# ==================== PUSH SENDER ====================

async def send_expo_push(push_token: str, title: str, body: str, data: dict = None) -> bool:
    """Send push notification via Expo Push API"""
    if not push_token or not push_token.startswith('ExponentPushToken'):
        logger.warning(f"Invalid push token: {push_token}")
        return False

    import httpx

    message = {
        'to': push_token,
        'title': title,
        'body': body,
        'sound': 'default',
        'priority': 'high',
    }
    if data:
        message['data'] = data

    try:
        async with httpx.AsyncClient() as http_client:
            response = await http_client.post(
                'https://exp.host/--/api/v2/push/send',
                json=message,
                headers={'Content-Type': 'application/json'},
                timeout=10.0,
            )
            result = response.json()
            if response.status_code == 200:
                status = result.get('data', {}).get('status', '')
                if status == 'ok':
                    logger.info(f"Push sent OK: {title}")
                    return True
                else:
                    logger.warning(f"Push API error: {result}")
                    return False
            else:
                logger.warning(f"Push HTTP error: {response.status_code}")
                return False
    except Exception as e:
        logger.error(f"Push send exception: {e}")
        return False


# ==================== PUSH WORKER ====================

async def process_queue() -> int:
    """
    Process pending notifications that are past their scheduledAt.
    Returns count of processed items.
    """
    now = datetime.utcnow()

    pending = list(notif_queue_col.find(
        {
            'status': 'PENDING',
            'scheduledAt': {'$lte': now},
        },
        sort=[('priority', DESCENDING), ('scheduledAt', ASCENDING)],
    ).limit(20))

    sent_count = 0

    for notif in pending:
        user_id = notif['userId']
        tokens = get_user_tokens(user_id)

        if not tokens:
            notif_queue_col.update_one(
                {'_id': notif['_id']},
                {'$set': {'status': 'SKIPPED', 'reason': 'no_token', 'processedAt': now}},
            )
            continue

        success = False
        for token_doc in tokens:
            push_token = token_doc.get('pushToken', '')
            result = await send_expo_push(
                push_token,
                notif['title'],
                notif['body'],
                notif.get('payload', {}),
            )
            if result:
                success = True

        new_status = 'SENT' if success else 'FAILED'
        notif_queue_col.update_one(
            {'_id': notif['_id']},
            {'$set': {'status': new_status, 'sentAt': now, 'processedAt': now}},
        )

        if success:
            # Log for cooldown/dedup tracking
            notif_log_col.insert_one({
                'userId': user_id,
                'type': notif['type'],
                'asset': notif.get('asset', ''),
                'title': notif['title'],
                'dedup_key': notif.get('dedup_key', ''),
                'payload': notif.get('payload', {}),
                'variant': notif.get('variant', 'A'),
                'sentAt': now,
            })
            log_analytics('push_sent', user_id, notif['type'], notif.get('asset', ''))
            sent_count += 1

    return sent_count


# ==================== NOTIFICATION ORCHESTRATORS ====================

def orchestrate_high_confidence():
    """
    Orchestrator: Check recent signals for high-confidence pushes.
    Runs every 30-60 seconds via background task.
    Does NOT trigger from signal creation directly.
    """
    signals_col = db['signal_history']
    users_col = db['users']

    # Get signals from the last 5 minutes that are OPEN and high confidence
    cutoff = datetime.utcnow() - timedelta(minutes=5)
    recent_signals = list(signals_col.find({
        'status': 'OPEN',
        'confidence': {'$gte': 0.85},
        'action': {'$ne': 'WAIT'},
        'asset': {'$in': list(PUSH_ELIGIBLE_ASSETS)},
        'entryTs': {'$gte': cutoff},
    }).limit(10))

    if not recent_signals:
        return 0

    # Get all users with active push tokens
    active_user_ids = get_all_active_token_users()
    if not active_user_ids:
        return 0

    queued = 0
    for signal in recent_signals:
        if not should_send_high_confidence(signal):
            continue

        notif_a = build_high_confidence_notif(signal, variant='A')
        notif_b = build_high_confidence_notif(signal, variant='B')

        for idx, user_id in enumerate(active_user_ids):
            # Get user plan
            user = users_col.find_one({'_id': user_id}) or users_col.find_one({'userId': user_id})
            plan = 'FREE'
            if user:
                plan = user.get('plan', user.get('preferences', {}).get('plan', 'FREE'))

                # Check user preferences
                prefs = user.get('preferences', {})
                if not prefs.get('signalAlerts', True):
                    continue

                # Check favorites/defaultAsset filter
                default_asset = prefs.get('defaultAsset', '')
                favorites = prefs.get('favorites', [])
                signal_asset = signal.get('asset', '')

                # Only push for user's preferred assets or very high confidence
                if signal.get('confidence', 0) < 0.9:
                    if default_asset and signal_asset != default_asset:
                        if favorites and signal_asset not in favorites:
                            continue

            # A/B: even users get A, odd get B
            notif = notif_a if idx % 2 == 0 else notif_b

            if enqueue_notification(user_id, notif, plan, delay_seconds=0):
                queued += 1

    if queued > 0:
        logger.info(f"High-confidence orchestrator: queued {queued} notifications")
    return queued


def orchestrate_missed():
    """
    Orchestrator: Check missed signals for each user.
    Runs every 10-15 minutes via background task.
    Missed pushes are DELAYED by 15 minutes (scheduledAt).
    """
    from services.missed_engine import get_missed_signals

    users_col = db['users']

    active_user_ids = get_all_active_token_users()
    if not active_user_ids:
        return 0

    queued = 0
    for user_id in active_user_ids:
        user = users_col.find_one({'_id': user_id}) or users_col.find_one({'userId': user_id})
        plan = 'FREE'
        prefs = {}
        if user:
            plan = user.get('plan', user.get('preferences', {}).get('plan', 'FREE'))
            prefs = user.get('preferences', {})

            if not prefs.get('signalAlerts', True):
                continue

        # Check missed for each eligible asset
        for asset in PUSH_ELIGIBLE_ASSETS:
            missed = get_missed_signals(str(user_id), asset, limit=3)

            if not should_send_missed(missed):
                continue

            # A/B variant (based on user_id hash)
            variant = 'A' if hash(str(user_id)) % 2 == 0 else 'B'
            notif = build_missed_notif(missed, asset, variant)

            # Delayed by 15 minutes — gives user a chance to open app first
            if enqueue_notification(user_id, notif, plan, delay_seconds=MISSED_PUSH_DELAY):
                queued += 1

    if queued > 0:
        logger.info(f"Missed orchestrator: queued {queued} notifications (delayed 15min)")
    return queued


# ==================== BACKGROUND RUNNERS ====================

async def run_orchestrators():
    """Background task: run both orchestrators periodically"""
    logger.info("Push orchestrators started")

    signal_interval = 60       # Every 60 seconds
    missed_interval = 600      # Every 10 minutes
    summary_interval = 3600    # Every 1 hour (checks if daily summary needed)
    worker_interval = 5        # Every 5 seconds

    last_signal_run = 0
    last_missed_run = 0
    last_summary_run = 0

    while True:
        try:
            now = time.time()

            # Signal orchestrator (every 60s)
            if now - last_signal_run >= signal_interval:
                try:
                    orchestrate_high_confidence()
                except Exception as e:
                    logger.error(f"Signal orchestrator error: {e}")
                last_signal_run = now

            # Missed orchestrator (every 10min)
            if now - last_missed_run >= missed_interval:
                try:
                    orchestrate_missed()
                except Exception as e:
                    logger.error(f"Missed orchestrator error: {e}")
                last_missed_run = now

            # Daily Summary orchestrator (every 1h, sends in morning window)
            if now - last_summary_run >= summary_interval:
                try:
                    orchestrate_daily_summary()
                except Exception as e:
                    logger.error(f"Daily summary orchestrator error: {e}")
                last_summary_run = now

            # Queue worker (every 5s)
            try:
                sent = await process_queue()
                if sent > 0:
                    logger.info(f"Worker: sent {sent} pushes")
            except Exception as e:
                logger.error(f"Queue worker error: {e}")

            await asyncio.sleep(worker_interval)

        except Exception as e:
            logger.error(f"Orchestrator loop error: {e}")
            await asyncio.sleep(10)


def orchestrate_daily_summary():
    """
    Orchestrator: Send daily summary push to active users.
    Runs every hour, but only sends in the morning window (8-10 AM UTC).
    Uses DAILY_SUMMARY cooldown (24h) so each user gets max 1/day.
    """
    current_hour = datetime.utcnow().hour

    # Only send in morning window (8-10 AM UTC)
    if current_hour < 8 or current_hour > 10:
        return 0

    from services.daily_summary_engine import get_daily_summary, build_daily_summary_push

    users_col = db['users']
    active_user_ids = get_all_active_token_users()
    if not active_user_ids:
        return 0

    queued = 0
    for user_id in active_user_ids:
        user = users_col.find_one({'_id': user_id}) or users_col.find_one({'userId': user_id})
        plan = 'FREE'
        prefs = {}
        default_asset = 'BTC'

        if user:
            plan = user.get('plan', user.get('preferences', {}).get('plan', 'FREE'))
            prefs = user.get('preferences', {})
            default_asset = prefs.get('defaultAsset', 'BTC')

            # Respect dailySummary toggle (default: True)
            if not prefs.get('dailySummary', True):
                continue

        # Generate summary for user's default asset
        summary = get_daily_summary(default_asset, str(user_id), plan)

        if not summary or summary.get('signalsToday', 0) == 0:
            # Don't send if no data for the day — honest
            continue

        # A/B variant
        variant = 'A' if hash(str(user_id)) % 2 == 0 else 'B'
        notif = build_daily_summary_push(summary, variant)

        if enqueue_notification(user_id, notif, plan, delay_seconds=0):
            queued += 1

    if queued > 0:
        logger.info(f"Daily summary orchestrator: queued {queued} summaries")
    return queued


# ==================== PUSH STATUS API ====================

def get_push_status(user_id: str) -> dict:
    """Get push notification status for a user"""
    tokens = get_user_tokens(user_id)
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    sent_today = notif_log_col.count_documents({
        'userId': user_id,
        'sentAt': {'$gte': today_start},
    })

    pending = notif_queue_col.count_documents({
        'userId': user_id,
        'status': 'PENDING',
    })

    recent = list(notif_log_col.find(
        {'userId': user_id},
        sort=[('sentAt', DESCENDING)],
    ).limit(5))

    return {
        'hasToken': len(tokens) > 0,
        'tokenCount': len(tokens),
        'sentToday': sent_today,
        'pendingCount': pending,
        'recentNotifications': [
            {
                'type': n.get('type', ''),
                'title': n.get('title', ''),
                'asset': n.get('asset', ''),
                'sentAt': n['sentAt'].isoformat() if n.get('sentAt') else None,
            }
            for n in recent
        ],
    }


# ==================== PUSH OPEN TRACKING ====================

def mark_push_opened(notification_id: str, user_id: str) -> bool:
    """Track that a push notification was opened by the user"""
    try:
        now = datetime.utcnow()
        result = notif_queue_col.update_one(
            {'_id': notification_id, 'userId': user_id},
            {'$set': {'opened': True, 'openedAt': now}},
        )
        if result.modified_count > 0:
            log_analytics('push_opened', user_id)
        return True
    except Exception as e:
        logger.error(f"Push open tracking error: {e}")
        return False
