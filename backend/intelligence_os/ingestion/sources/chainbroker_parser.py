"""
ChainBroker Parser
==================
Scrapes news articles from chainbroker.io.

The site is a Next.js SPA — articles are rendered server-side and
inlined as JSON inside a `<script id="__NEXT_DATA__">…</script>` tag.

We pull that JSON and walk it for objects with both `slug` and
`title`, then synthesise full URLs against /news/<slug>/.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone

import httpx

from intelligence_os.core.logging_config import get_logger
from intelligence_os.ingestion.base_parser import BaseParser

log = get_logger("source.chainbroker")

CB_NEWS = "https://chainbroker.io/news/"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/123.0 Safari/537.36"
)

_NEXT_DATA_RE = re.compile(
    r'<script\s+id="__NEXT_DATA__"\s+type="application/json"[^>]*>(?P<payload>\{.*?\})</script>',
    re.DOTALL,
)


def _walk(node, hits: list[dict]) -> None:
    if isinstance(node, dict):
        slug = node.get("slug")
        title = node.get("title")
        if isinstance(slug, str) and slug and isinstance(title, str) and title.strip():
            hits.append(node)
        for v in node.values():
            _walk(v, hits)
    elif isinstance(node, list):
        for it in node:
            _walk(it, hits)


class ChainBrokerParser(BaseParser):
    name = "chainbroker"
    raw_collection = "raw_news"

    async def fetch(self, query: dict | None = None) -> list[dict]:
        rows: list[dict] = []
        now = datetime.now(timezone.utc).isoformat()

        async with httpx.AsyncClient(
            timeout=20, headers={"User-Agent": UA}, follow_redirects=True
        ) as client:
            try:
                resp = await client.get(CB_NEWS)
            except Exception as e:
                log.warning(f"ChainBroker fetch failed: {e}")
                return rows
            if resp.status_code != 200:
                log.warning(f"ChainBroker HTTP {resp.status_code}")
                return rows

            m = _NEXT_DATA_RE.search(resp.text)
            if not m:
                log.warning("ChainBroker: __NEXT_DATA__ not found")
                return rows

            try:
                payload = json.loads(m.group("payload"))
            except Exception as e:
                log.warning(f"ChainBroker JSON parse failed: {e}")
                return rows

            hits: list[dict] = []
            _walk(payload, hits)

            seen: set[str] = set()
            for h in hits:
                slug = h.get("slug")
                title = (h.get("title") or "").strip()
                if not slug or not title or slug in seen:
                    continue
                seen.add(slug)
                url = f"https://chainbroker.io/news/{slug}/"
                rows.append(
                    {
                        "source": "chainbroker",
                        "domain": "NEWS",
                        "title": title[:300],
                        "url": url,
                        "summary": (
                            (h.get("description") or h.get("subtitle") or h.get("excerpt") or "")[:500]
                        ),
                        "published_at": h.get("publishedAt") or h.get("createdAt") or h.get("date"),
                        "categories": h.get("categories") or h.get("tags") or [],
                        "fetched_at": now,
                    }
                )

        log.info(f"ChainBroker news/: parsed {len(rows)} unique articles")
        return rows

    def validate(self, rows: list[dict]) -> list[dict]:
        seen_urls: set[str] = set()
        out: list[dict] = []
        for r in rows:
            if not r.get("title") or not r.get("url"):
                continue
            if r["url"] in seen_urls:
                continue
            seen_urls.add(r["url"])
            out.append(r)
        return out
