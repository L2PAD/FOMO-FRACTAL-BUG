"""
TokenUnlocks Source Adapter
===========================
Fetches unlock schedule data.
"""
from datetime import datetime, timezone
from intelligence_os.ingestion.base_parser import BaseParser
from intelligence_os.core.logging_config import get_logger

log = get_logger("source.tokenunlocks")


class TokenUnlocksParser(BaseParser):
    name = "tokenunlocks"
    raw_collection = "raw_unlocks"

    async def fetch(self, query: dict | None = None) -> list[dict]:
        rows = []
        now = datetime.now(timezone.utc).isoformat()

        # Bridge to existing token_unlocks collection
        cursor = self.db["token_unlocks"].find(
            {"_raw_migrated": {"$ne": True}},
            {"_id": 0},
        ).limit(200)

        async for unlock in cursor:
            rows.append({
                "source": "tokenunlocks",
                "domain": "UNLOCKS",
                "project_name": unlock.get("project") or unlock.get("name"),
                "symbol": unlock.get("symbol"),
                "unlock_date": unlock.get("unlock_date") or unlock.get("date"),
                "unlock_amount_usd": unlock.get("amount_usd"),
                "unlock_pct": unlock.get("percentage"),
                "unlock_type": unlock.get("type"),
                "fetched_at": now,
            })

        log.info(f"Fetched {len(rows)} unlocks from TokenUnlocks bridge")
        return rows

    def validate(self, rows: list[dict]) -> list[dict]:
        return [r for r in rows if r.get("project_name")]
