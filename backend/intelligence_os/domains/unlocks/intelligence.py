"""
Unlocks Intelligence
====================
Builds unlock calendar, upcoming windows, project-level timeline.
"""
from datetime import datetime, timezone, timedelta
from intelligence_os.core.logging_config import get_logger

log = get_logger("domain.unlocks")


class UnlocksIntelligence:
    def __init__(self, db):
        self.db = db

    async def build_unlock_calendar(self) -> dict:
        """Build structured unlock calendar from canonical events."""
        cursor = self.db["canonical_events"].find({"event_type": "unlock"})
        now = datetime.now(timezone.utc)
        upcoming, past, total = 0, 0, 0

        async for event in cursor:
            total += 1
            data = event.get("data", {})
            unlock_date_str = data.get("unlock_date")

            try:
                unlock_date = datetime.fromisoformat(str(unlock_date_str).replace("Z", "+00:00"))
                is_upcoming = unlock_date > now
            except (ValueError, TypeError):
                is_upcoming = False

            if is_upcoming:
                upcoming += 1
            else:
                past += 1

            await self.db["intel_unlock_calendar"].update_one(
                {
                    "project_name": event.get("project_name"),
                    "unlock_date": unlock_date_str,
                },
                {
                    "$set": {
                        "symbol": event.get("symbol"),
                        "project_canonical_id": event.get("project_canonical_id"),
                        "amount_usd": data.get("unlock_amount_usd"),
                        "percentage": data.get("unlock_pct"),
                        "is_upcoming": is_upcoming,
                        "updated_at": now.isoformat(),
                    },
                    "$setOnInsert": {"created_at": now.isoformat()},
                },
                upsert=True,
            )

        log.info(f"[UNLOCKS] Calendar: total={total}, upcoming={upcoming}, past={past}")
        return {"total": total, "upcoming": upcoming, "past": past}

    async def get_upcoming_windows(self, days: int = 7) -> list[dict]:
        """Get unlocks happening in the next N days."""
        now = datetime.now(timezone.utc)
        window_end = now + timedelta(days=days)
        cursor = self.db["intel_unlock_calendar"].find(
            {"is_upcoming": True}, {"_id": 0}
        ).sort("unlock_date", 1).limit(50)
        return await cursor.to_list(length=50)
