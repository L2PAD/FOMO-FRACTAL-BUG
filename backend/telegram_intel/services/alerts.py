"""
Telegram Intel - Alerts Service
Version: 1.0.0
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


async def get_alerts(db, actor_id: str = "default", limit: int = 50) -> Dict[str, Any]:
    """Get actor's alerts - generate if none exist (filtered by feed channels)"""
    try:
        from datetime import datetime, timezone, timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        count = await db.tg_alerts.count_documents({"createdAt": {"$gte": cutoff}})
        
        if count == 0:
            try:
                # Get watchlist usernames for filtering
                watchlist = await db.tg_watchlist.find(
                    {"$or": [{"actorId": actor_id}, {"actorId": "a_public"}, {"actorId": "default"}]},
                    {"username": 1, "_id": 0}
                ).to_list(500)
                usernames = list(set(w.get("username") for w in watchlist if w.get("username")))
                
                from telegram_intel.services.metrics import generate_alerts
                await generate_alerts(db, hours=48, usernames=usernames or None)
            except Exception as e:
                logger.warning(f"Alert generation failed: {e}")

        alerts = await db.tg_alerts.find(
            {},
            {"_id": 0}
        ).sort("createdAt", -1).limit(limit).to_list(limit)
        
        return {
            "ok": True,
            "actorId": actor_id,
            "count": len(alerts),
            "alerts": alerts
        }
    except Exception as e:
        logger.error(f"Alerts error: {e}")
        return {"ok": False, "error": str(e), "alerts": [], "count": 0}


async def dispatch_alerts(db, bot_token: Optional[str] = None) -> Dict[str, Any]:
    """Dispatch pending alerts to linked users"""
    if not bot_token:
        return {"ok": False, "error": "Bot token not configured"}
    
    # Placeholder - actual implementation uses delivery_bot
    return {"ok": True, "dispatched": 0}
