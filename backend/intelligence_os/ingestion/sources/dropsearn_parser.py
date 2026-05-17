"""
DropsEarn Source Adapter
========================
Fetches activity/airdrop data from DropsEarn.
"""
import sys
from datetime import datetime, timezone
from intelligence_os.ingestion.base_parser import BaseParser
from intelligence_os.core.logging_config import get_logger

log = get_logger("source.dropsearn")


class DropsEarnParser(BaseParser):
    name = "dropsearn"
    raw_collection = "raw_activities"

    async def fetch(self, query: dict | None = None) -> list[dict]:
        rows = []
        now = datetime.now(timezone.utc).isoformat()

        try:
            sys.path.insert(0, "/app/backend")
            from modules.parsers.parser_dropsearn import DropsEarnParser as LegacyParser
            legacy = LegacyParser(self.db)
            data = await legacy.fetch_airdrops()
            for item in data:
                rows.append({
                    "source": "dropsearn",
                    "domain": "ACTIVITIES",
                    "project_name": item.get("name") or item.get("project_name"),
                    "activity_type": item.get("type", "airdrop"),
                    "status": item.get("status"),
                    "reward": item.get("reward"),
                    "description": item.get("description"),
                    "url": item.get("url"),
                    "fetched_at": now,
                })
        except Exception as e:
            log.warning(f"DropsEarn legacy parser failed: {e}")

        log.info(f"Fetched {len(rows)} activities from DropsEarn")
        return rows

    def validate(self, rows: list[dict]) -> list[dict]:
        return [r for r in rows if r.get("project_name")]
