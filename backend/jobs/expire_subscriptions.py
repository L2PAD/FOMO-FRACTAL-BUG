"""
Background Job: Expire Subscriptions
=====================================

Runs every hour via cron to ensure all expired PRO subscriptions
are downgraded to FREE automatically, without waiting for user requests.

WHY THIS MATTERS:
- Keeps database state accurate for analytics
- Prevents "ghost PRO users" in admin dashboard
- Ensures billing metrics are real-time
"""
import os
import logging
from datetime import datetime, timezone
from pymongo import MongoClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "intelligence_engine")


def expire_subscriptions():
    """
    Find all PRO users with expiresAt < now and downgrade them to FREE.
    
    Returns:
        int: Number of users downgraded
    """
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    
    now = datetime.now(timezone.utc)
    
    # Find expired PRO subscriptions
    result = db.users.update_many(
        {
            "plan": "PRO",
            "expiresAt": {"$lt": now, "$ne": None}
        },
        {
            "$set": {
                "plan": "FREE",
                "planStatus": "EXPIRED",
                "expiresAt": None,
                "expiredAt": now  # Track when it expired
            }
        }
    )
    
    count = result.modified_count
    
    if count > 0:
        logger.info(f"✅ Expired {count} PRO subscriptions")
    else:
        logger.info("✅ No subscriptions to expire")
    
    client.close()
    return count


if __name__ == "__main__":
    logger.info("🕐 Running subscription expiration job...")
    count = expire_subscriptions()
    logger.info(f"🏁 Job complete. Downgraded {count} users.")
