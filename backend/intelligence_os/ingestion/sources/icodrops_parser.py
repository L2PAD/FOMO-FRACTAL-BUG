"""
ICODrops Source Adapter
=======================
Fetches ICO/token sale data from ICODrops.
"""
import sys
from datetime import datetime, timezone
from intelligence_os.ingestion.base_parser import BaseParser
from intelligence_os.core.logging_config import get_logger

log = get_logger("source.icodrops")


class ICODropsParser(BaseParser):
    name = "icodrops"
    raw_collection = "raw_ico"

    async def fetch(self, query: dict | None = None) -> list[dict]:
        rows = []
        now = datetime.now(timezone.utc).isoformat()

        try:
            sys.path.insert(0, "/app/backend")
            from modules.parsers.parser_icodrops import ICODropsParser as LegacyParser
            legacy = LegacyParser(self.db)
            data = await legacy.fetch_upcoming()
            for item in data:
                rows.append({
                    "source": "icodrops",
                    "domain": "ICO",
                    "project_name": item.get("name") or item.get("project_name"),
                    "symbol": item.get("symbol"),
                    "status": item.get("status", "upcoming"),
                    "raise_target": item.get("raise"),
                    "category": item.get("category"),
                    "description": item.get("description"),
                    "fetched_at": now,
                })
        except Exception as e:
            log.warning(f"ICODrops legacy parser failed: {e}, using direct fetch")
            import sys, httpx
            try:
                sys.path.insert(0, "/app/backend")
                from modules.parsers.proxy_helper import get_proxy_url
                proxy_url = get_proxy_url()
            except Exception:
                proxy_url = None
            async with httpx.AsyncClient(timeout=30, proxy=proxy_url, headers={"User-Agent": "Mozilla/5.0"}) as client:
                resp = await client.get("https://icodrops.com/category/upcoming-ico/")
                if resp.status_code == 200:
                    log.info("ICODrops HTML fetched, parsing needed")

        log.info(f"Fetched {len(rows)} ICOs from ICODrops")
        return rows

    def validate(self, rows: list[dict]) -> list[dict]:
        return [r for r in rows if r.get("project_name")]
