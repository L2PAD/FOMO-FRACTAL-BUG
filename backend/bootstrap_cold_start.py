"""
Cold Start Bootstrap — Seeds minimum data for a fresh deployment.

Run after first deployment:
  python bootstrap_cold_start.py

Creates:
  - Default dev user
  - Initial portfolio positions (BTC/ETH/SOL)
  - Sample notifications
  - Ensures all MongoDB indexes exist
"""

import os
import sys
from datetime import datetime, timezone
from pymongo import MongoClient, ASCENDING, DESCENDING
from dotenv import load_dotenv

load_dotenv()

MONGO_URL = os.getenv('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.getenv('DB_NAME', 'test_database')

client = MongoClient(MONGO_URL)
db = client[DB_NAME]


def ensure_indexes():
    """Create all required MongoDB indexes."""
    print("[Bootstrap] Creating indexes...")

    db.users.create_index([('email', ASCENDING)], unique=True)
    db.users.create_index([('googleId', ASCENDING)])

    db.portfolio_positions.create_index([('userId', ASCENDING), ('status', ASCENDING)])
    db.portfolio_snapshots.create_index([('userId', ASCENDING)])

    db.notifications.create_index([('createdAt', DESCENDING)])
    db.notifications.create_index([('read', ASCENDING), ('createdAt', DESCENDING)])

    db.behavior_events.create_index([('userId', ASCENDING), ('createdAt', DESCENDING)])
    db.behavior_events.create_index([('userId', ASCENDING), ('type', ASCENDING)])

    db.push_triggers_log.create_index([('userId', ASCENDING), ('type', ASCENDING), ('symbol', ASCENDING), ('createdAt', DESCENDING)])

    db.user_affinity.create_index([('userId', ASCENDING)], unique=True)
    db.edge_tracking.create_index([('userId', ASCENDING), ('edgeId', ASCENDING)])

    db.exchange_observations.create_index([('symbol', ASCENDING), ('timestamp', DESCENDING)])

    # ── Growth Layer G1 (share / analytics / referrals) ──
    # analytics_events: 10 whitelisted events fired from Hero/Edge/Missed/Share.
    #   See /app/backend/routes/mobile_analytics.py and GROWTH_LAYER.md.
    db.analytics_events.create_index([('userId', ASCENDING), ('event', ASCENDING), ('timestamp', DESCENDING)])
    db.analytics_events.create_index([('event', ASCENDING), ('timestamp', DESCENDING)])
    db.analytics_events.create_index([('timestamp', DESCENDING)])

    # referrals collection (existing; idempotent if already present)
    try:
        db.referrals.create_index([('code', ASCENDING)], unique=True)
        db.referrals.create_index([('referrerId', ASCENDING)])
        db.referrals.create_index([('referredUserId', ASCENDING)])
    except Exception:
        # mobile_auth.py also creates these at import-time; ignore duplicates.
        pass

    print("[Bootstrap] Indexes created.")


def seed_dev_user():
    """Create default dev user if not exists."""
    existing = db.users.find_one({'email': 'dev@fomo.ai'})
    if existing:
        print("[Bootstrap] Dev user already exists.")
        return

    db.users.insert_one({
        'email': 'dev@fomo.ai',
        'name': 'Dev User',
        'plan': 'PRO',
        'preferences': {'plan': 'PRO', 'theme': 'dark', 'lang': 'en'},
        'createdAt': datetime.now(timezone.utc),
    })
    print("[Bootstrap] Dev user created (dev@fomo.ai).")


def seed_portfolio():
    """Create initial portfolio positions."""
    existing = db.portfolio_positions.count_documents({'userId': 'dev_user', 'status': 'OPEN'})
    if existing > 0:
        print(f"[Bootstrap] Portfolio already has {existing} positions.")
        return

    now = datetime.now(timezone.utc)
    positions = [
        {'symbol': 'BTC', 'side': 'LONG', 'allocation': 0.5, 'entryPrice': 71102, 'role': 'CORE', 'roleLabel': 'Core Anchor'},
        {'symbol': 'ETH', 'side': 'LONG', 'allocation': 0.3, 'entryPrice': 2193, 'role': 'CONFIRMATION', 'roleLabel': 'Confirmation'},
        {'symbol': 'SOL', 'side': 'LONG', 'allocation': 0.2, 'entryPrice': 83, 'role': 'EARLY', 'roleLabel': 'Early Beta'},
    ]

    for pos in positions:
        db.portfolio_positions.insert_one({
            'userId': 'dev_user',
            'snapshotId': 'bootstrap',
            'symbol': pos['symbol'],
            'side': pos['side'],
            'allocation': pos['allocation'],
            'entryPrice': pos['entryPrice'],
            'currentPrice': pos['entryPrice'],
            'pnlPct': 0.0,
            'status': 'OPEN',
            'role': pos['role'],
            'roleLabel': pos['roleLabel'],
            'openedAt': now.isoformat(),
            'closedAt': None,
        })

    print(f"[Bootstrap] Created {len(positions)} portfolio positions.")


def seed_notifications():
    """Seed welcome notifications."""
    existing = db.notifications.count_documents({})
    if existing > 5:
        print(f"[Bootstrap] Notifications already seeded ({existing} total).")
        return

    now = datetime.now(timezone.utc)
    db.notifications.insert_one({
        'nid': 'n_bootstrap_welcome',
        'type': 'SYSTEM',
        'title_en': 'Welcome to Trading Intelligence',
        'title_ru': 'Добро пожаловать в Trading Intelligence',
        'body_en': 'Your decision engine is ready. Start with Edge.',
        'body_ru': 'Твой decision engine готов. Начни с Edge.',
        'data': {'screen': 'edge'},
        'priority': 'HIGH',
        'icon': 'flash',
        'read': False,
        'readAt': None,
        'createdAt': now,
    })
    print("[Bootstrap] Welcome notification created.")


def run():
    print(f"[Bootstrap] MongoDB: {MONGO_URL} / {DB_NAME}")
    print(f"[Bootstrap] Starting cold start bootstrap...")

    ensure_indexes()
    seed_dev_user()
    seed_portfolio()
    seed_notifications()

    print(f"[Bootstrap] Done. System ready.")
    print(f"[Bootstrap] Collections: {db.list_collection_names()[:15]}")


if __name__ == '__main__':
    run()
