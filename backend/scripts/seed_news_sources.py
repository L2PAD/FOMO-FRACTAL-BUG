"""
Seed news_sources collection from the canonical RSS-feeds catalogue.

Data lives in this repo under  /app/backend/data/crypto_rss_feeds.json
(authoritative 119-feed list).  Idempotent — safe to re-run.
"""
import json
import os
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv
from pymongo import MongoClient

# Local imports / paths
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.environ.get('DB_NAME', 'fomo_mobile')
FEEDS_JSON = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'data',
    'crypto_rss_feeds.json',
)


def load_feeds(path: str = FEEDS_JSON) -> list[dict]:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def main():
    feeds = load_feeds()
    print(f"[seed] loaded {len(feeds)} feeds from {FEEDS_JSON}")

    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    col = db.news_sources

    try:
        col.create_index('id', unique=True)
    except Exception as e:
        print(f"[seed] index warning: {e}")

    now = datetime.now(timezone.utc)
    inserted = 0
    updated = 0

    for f in feeds:
        doc = {
            'id': f['id'],
            'name': f['name'],
            'rss_url': f['url'],
            'url': f['url'],
            'website': f['url'],
            'tier': f['tier'],
            'lang': f['lang'],
            'language': f['lang'],
            'category': 'news',
            'is_active': True,
            'enabled': True,
            'weight': {'A': 1.0, 'B': 0.7, 'C': 0.4}.get(f['tier'], 0.5),
        }
        res = col.update_one(
            {'id': f['id']},
            {
                '$set': doc,
                '$setOnInsert': {
                    'created_at': now,
                    'lastFetchAt': None,
                    'lastSuccessAt': None,
                    'lastErrorAt': None,
                    'lastError': None,
                    'consecutiveFailures': 0,
                    'totalFetches': 0,
                    'totalSuccess': 0,
                    'totalErrors': 0,
                    'totalArticles': 0,
                    'avgLatencyMs': 0,
                    'successRate': 1.0,
                    'healthy': True,
                },
            },
            upsert=True,
        )
        if res.upserted_id:
            inserted += 1
        elif res.modified_count:
            updated += 1

    total = col.count_documents({})
    active = col.count_documents({'is_active': True})
    print(
        f"[seed] inserted={inserted} updated={updated} "
        f"total_in_db={total} active={active}"
    )


if __name__ == '__main__':
    main()
