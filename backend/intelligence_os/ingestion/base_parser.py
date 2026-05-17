"""
Base Parser Contract
====================
Every parser in the system MUST implement this interface.
No exceptions. No shortcuts.

Flow: fetch() → validate() → save_raw()
"""
from abc import ABC, abstractmethod
from typing import Any
from intelligence_os.core.logging_config import get_logger

log = get_logger("parser")


class BaseParser(ABC):
    name: str = "unknown"
    raw_collection: str = "raw_unknown"

    def __init__(self, db):
        self.db = db

    @abstractmethod
    async def fetch(self, query: dict | None = None) -> list[dict[str, Any]]:
        """Fetch data from external source. Returns list of raw documents."""
        raise NotImplementedError

    def validate(self, rows: list[dict]) -> list[dict]:
        """Validate and filter rows. Default: remove empties."""
        return [r for r in rows if r]

    async def save_raw(self, rows: list[dict]) -> int:
        """Save validated rows to raw collection. Returns count saved."""
        if not rows:
            return 0
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        for row in rows:
            row["_raw_source"] = self.name
            row["_raw_fetched_at"] = now
            row["_canonicalized"] = False

        col = self.db[self.raw_collection]
        result = await col.insert_many(rows)
        count = len(result.inserted_ids)
        log.info(f"[RAW] {self.name} → {self.raw_collection}: saved {count} docs")
        return count
