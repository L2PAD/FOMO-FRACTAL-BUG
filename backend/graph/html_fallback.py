"""
HTML Fallback Layer for Parsers
===============================
When primary API/RSC fails, fall back to HTML scraping.

Specific adapters for:
  - CryptoRank: api.cryptorank.io → cryptorank.io/currencies (HTML)
  - Dropstab: RSC format → dropstab.com standard HTML
  - ICODrops: already HTML, add retry with proxy rotation

Each adapter returns the SAME data format as the primary parser.
Integration: called automatically from sync_ functions on primary failure.

Rule: if primary fails 2x consecutive → activate HTML fallback.
"""

import httpx
import logging
import re
import time
from typing import List, Dict, Optional
from datetime import datetime, timezone
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# ─── Shared HTTP client config ───

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


async def _fetch_html(url: str, proxy_url: str = None, timeout: int = 30) -> Optional[str]:
    """Fetch HTML from URL with optional proxy."""
    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            proxy=proxy_url,
            headers=DEFAULT_HEADERS,
            follow_redirects=True,
        ) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                return resp.text
            logger.warning(f"[HTMLFallback] {url} returned {resp.status_code}")
    except Exception as e:
        logger.error(f"[HTMLFallback] {url} error: {e}")
    return None


# ============================================================
# CRYPTORANK HTML FALLBACK
# ============================================================

async def cryptorank_html_coins(proxy_url: str = None, limit: int = 100) -> List[Dict]:
    """
    Fallback: scrape cryptorank.io homepage __NEXT_DATA__.
    Returns same format as CryptoRankParser.fetch_coins().
    """
    url = "https://cryptorank.io/"
    html = await _fetch_html(url, proxy_url)
    if not html:
        return []

    coins = []
    try:
        soup = BeautifulSoup(html, "html.parser")
        next_data = soup.find("script", {"id": "__NEXT_DATA__"})
        if not next_data or not next_data.string:
            logger.warning("[CryptoRank HTML] No __NEXT_DATA__ found")
            return []

        import json
        data = json.loads(next_data.string)
        props = data.get("props", {}).get("pageProps", {})

        # Merge all available coin lists
        all_coins = []
        for key in ("fallbackCoins", "trendingCoins", "gainersCoins", "losersCoins", "athCoins", "atlCoins"):
            coin_list = props.get(key, [])
            if isinstance(coin_list, list):
                all_coins.extend(coin_list)

        # Deduplicate by symbol
        seen = set()
        for c in all_coins:
            sym = (c.get("symbol") or "").upper()
            if not sym or sym in seen:
                continue
            seen.add(sym)

            price = c.get("price")
            if isinstance(price, dict):
                price = price.get("USD")

            coins.append({
                "cryptorank_id": c.get("id"),
                "symbol": sym,
                "name": c.get("name", ""),
                "slug": c.get("key", c.get("slug")),
                "rank": c.get("rank"),
                "price_usd": price,
                "market_cap": c.get("marketCap"),
                "volume_24h": c.get("volume24h"),
                "change_24h": c.get("priceChange24h") or c.get("percentChange24h"),
                "source": "cryptorank_html",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })

            if len(coins) >= limit:
                break

        logger.info(f"[CryptoRank HTML] Extracted {len(coins)} coins from __NEXT_DATA__")
    except Exception as e:
        logger.error(f"[CryptoRank HTML] Parse error: {e}")

    return coins


async def cryptorank_html_funding(proxy_url: str = None) -> List[Dict]:
    """
    Fallback: scrape cryptorank.io homepage for funding rounds from __NEXT_DATA__.
    Returns same format as CryptoRankParser.fetch_funding_rounds().
    """
    url = "https://cryptorank.io/"
    html = await _fetch_html(url, proxy_url)
    if not html:
        return []

    rounds = []
    try:
        soup = BeautifulSoup(html, "html.parser")
        next_data = soup.find("script", {"id": "__NEXT_DATA__"})
        if not next_data or not next_data.string:
            return []

        import json
        data = json.loads(next_data.string)
        props = data.get("props", {}).get("pageProps", {})
        funding_list = props.get("fallbackRecentFundingRounds", [])

        for r in funding_list[:50]:
            coin = r.get("coin", {})
            funds = r.get("funds", [])
            project_name = coin.get("name", "") if isinstance(coin, dict) else str(coin)
            project_key = coin.get("key", project_name.lower().replace(" ", "-")) if isinstance(coin, dict) else project_name.lower().replace(" ", "-")

            investors = []
            if isinstance(funds, list):
                for f in funds:
                    if isinstance(f, dict) and f.get("name"):
                        investors.append(f["name"])
                    elif isinstance(f, str):
                        investors.append(f)

            raised = r.get("raise") or 0
            if isinstance(raised, str):
                raised_clean = re.sub(r"[^0-9.]", "", raised)
                try:
                    raised = float(raised_clean)
                except ValueError:
                    raised = 0

            if not project_name:
                continue

            rounds.append({
                "id": f"cr_html:funding:{project_key}",
                "project": project_name,
                "project_key": project_key,
                "raised_usd": raised,
                "round_type": r.get("type", ""),
                "investors": investors,
                "lead_investors": investors[:1],
                "source": "cryptorank_html",
                "created_at": datetime.now(timezone.utc).isoformat(),
            })

        logger.info(f"[CryptoRank HTML] Extracted {len(rounds)} funding rounds")
    except Exception as e:
        logger.error(f"[CryptoRank HTML] Funding parse error: {e}")

    return rounds


# ============================================================
# DROPSTAB HTML FALLBACK
# ============================================================

async def dropstab_html_activities(proxy_url: str = None) -> List[Dict]:
    """
    Fallback: scrape dropstab.com/activities standard HTML.
    Returns same format as ActivitiesParser.parse_dropstab().
    """
    url = "https://dropstab.com/activities"
    html = await _fetch_html(url, proxy_url)
    if not html:
        return []

    activities = []
    try:
        soup = BeautifulSoup(html, "html.parser")

        # Dropstab renders links to /coins/<slug>/activities
        links = soup.select("a[href*='/coins/']")
        seen = set()

        for link in links:
            try:
                href = link.get("href", "")
                if "/coins/" not in href:
                    continue

                # Extract slug: /coins/<slug> or /coins/<slug>/activities
                parts = href.rstrip("/").split("/")
                coins_idx = parts.index("coins") if "coins" in parts else -1
                if coins_idx < 0 or coins_idx + 1 >= len(parts):
                    continue
                slug = parts[coins_idx + 1]

                if not slug or slug in seen or len(slug) < 2:
                    continue
                seen.add(slug)

                # Get name from link text (strip emoji and date noise)
                raw_text = link.get_text(strip=True)
                # Pattern: "Active...ProjectNameActivityType"
                # Try to extract clean name by removing common prefixes
                name = slug.replace("-", " ").title()
                # Look for a child element with the project name
                name_el = link.select_one("[class*='name'], h3, h4, span")
                if name_el:
                    name = name_el.get_text(strip=True)
                elif raw_text:
                    # Clean up text: remove emoji, dates, status words
                    clean = re.sub(r"[^\w\s.]", " ", raw_text)
                    clean = re.sub(r"\b(Active|From|TBA|Potential|Airdrop|AirDrop|Point|Farming|Ended|Upcoming)\b", "", clean, flags=re.I)
                    clean = re.sub(r"\d{1,2}\s+\w+,?\s*\d{4}", "", clean)  # dates
                    clean = re.sub(r"\s+", " ", clean).strip()
                    if clean and len(clean) > 1:
                        name = clean

                # Find image nearby
                img = link.select_one("img")
                logo = img.get("src") if img else None

                activities.append({
                    "id": f"ds_html:activity:{slug}",
                    "project_id": slug,
                    "project_name": name,
                    "project_logo": logo if logo and logo.startswith("http") else None,
                    "title": f"{name} Activity",
                    "type": "airdrop",
                    "category": "community",
                    "status": "active",
                    "source": "dropstab_html",
                    "source_url": f"https://dropstab.com/coins/{slug}",
                    "score": 70,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                })
            except Exception as e:
                logger.debug(f"[Dropstab HTML] Link parse error: {e}")

        logger.info(f"[Dropstab HTML] Extracted {len(activities)} activities from links")
    except Exception as e:
        logger.error(f"[Dropstab HTML] Parse error: {e}")

    return activities


# ============================================================
# ICODROPS ENHANCED (already HTML, add retry)
# ============================================================

async def icodrops_html_upcoming(proxy_url: str = None) -> List[Dict]:
    """
    Enhanced ICODrops scraper with proxy support.
    Returns same format as fetch_icodrops_upcoming().
    Tries homepage and category page for upcoming ICOs.
    """
    icos = []

    for url in ["https://icodrops.com/", "https://icodrops.com/category/upcoming-ico/"]:
        html = await _fetch_html(url, proxy_url)
        if not html:
            continue

        try:
            soup = BeautifulSoup(html, "html.parser")
            cards = soup.select("[class*='ico']")

            for card in cards[:50]:
                try:
                    name_el = card.select_one("h3 a, h4 a, [class*='name'] a, a[class*='title']")
                    if not name_el:
                        name_el = card.select_one("a")
                    if not name_el:
                        continue

                    name = name_el.get_text(strip=True)
                    link = name_el.get("href", "")
                    if not name or len(name) < 2 or name in [i["name"] for i in icos]:
                        continue

                    category_el = card.select_one("[class*='categ'], [class*='type']")
                    category = category_el.get_text(strip=True) if category_el else ""

                    date_el = card.select_one("[class*='date']")
                    date_text = date_el.get_text(strip=True) if date_el else ""

                    raised_el = card.select_one("[class*='funds'], [class*='raise']")
                    raised = raised_el.get_text(strip=True) if raised_el else ""

                    interest_el = card.select_one("[class*='interest'], [class*='rating']")
                    interest = interest_el.get_text(strip=True) if interest_el else ""

                    icos.append({
                        "name": name,
                        "url": f"https://icodrops.com{link}" if link.startswith("/") else link,
                        "category": category,
                        "date": date_text,
                        "raised": raised,
                        "interest": interest,
                        "source": "icodrops_html",
                    })
                except Exception:
                    continue

            if icos:
                break  # Got data from first working URL

        except Exception as e:
            logger.error(f"[ICODrops HTML] Parse error for {url}: {e}")

    logger.info(f"[ICODrops HTML] Extracted {len(icos)} upcoming ICOs")
    return icos


# ============================================================
# FALLBACK ORCHESTRATOR
# ============================================================

class FallbackManager:
    """
    Tracks consecutive failures per parser.
    Activates HTML fallback after 2 consecutive failures.
    """

    def __init__(self, db):
        self.db = db

    async def get_failure_count(self, parser_name: str) -> int:
        """Get consecutive failure count for a parser."""
        doc = await self.db.parser_registry.find_one(
            {"name": parser_name}, {"_id": 0, "consecutive_failures": 1}
        )
        return (doc or {}).get("consecutive_failures", 0)

    async def record_success(self, parser_name: str):
        """Reset consecutive failures on success."""
        await self.db.parser_registry.update_one(
            {"name": parser_name},
            {"$set": {"consecutive_failures": 0, "html_fallback_active": False}},
        )

    async def record_failure(self, parser_name: str) -> bool:
        """
        Increment consecutive failures. Returns True if fallback should activate.
        """
        result = await self.db.parser_registry.find_one_and_update(
            {"name": parser_name},
            {"$inc": {"consecutive_failures": 1}},
            return_document=True,
            projection={"_id": 0, "consecutive_failures": 1},
        )
        count = (result or {}).get("consecutive_failures", 1)
        if count >= 2:
            await self.db.parser_registry.update_one(
                {"name": parser_name},
                {"$set": {"html_fallback_active": True}},
            )
            return True
        return False

    async def should_use_fallback(self, parser_name: str) -> bool:
        """Check if fallback is active for this parser."""
        doc = await self.db.parser_registry.find_one(
            {"name": parser_name}, {"_id": 0, "html_fallback_active": 1}
        )
        return (doc or {}).get("html_fallback_active", False)


async def run_with_fallback(db, parser_name: str, primary_fn, fallback_fn,
                            proxy_url: str = None) -> Dict:
    """
    Run primary parser. If it fails, try HTML fallback.

    Args:
        db: MongoDB database
        parser_name: registry name (e.g., "CryptoRank")
        primary_fn: async callable returning data
        fallback_fn: async callable (HTML scraper) returning same format
        proxy_url: optional proxy

    Returns:
        {ok, data, source, used_fallback}
    """
    mgr = FallbackManager(db)
    start = time.time()

    # Try primary
    try:
        data = await primary_fn()
        if data:
            await mgr.record_success(parser_name)
            duration = round(time.time() - start, 1)
            logger.info(f"[Fallback] {parser_name} primary OK: {len(data)} items ({duration}s)")
            return {
                "ok": True,
                "data": data,
                "source": "api",
                "used_fallback": False,
                "count": len(data),
                "duration_sec": duration,
            }
    except Exception as e:
        logger.warning(f"[Fallback] {parser_name} primary failed: {e}")

    # Primary failed — try fallback
    should_fallback = await mgr.record_failure(parser_name)
    logger.info(f"[Fallback] {parser_name} activating HTML fallback (should_fallback={should_fallback})")

    try:
        data = await fallback_fn(proxy_url=proxy_url)
        if data:
            duration = round(time.time() - start, 1)
            logger.info(f"[Fallback] {parser_name} HTML fallback OK: {len(data)} items ({duration}s)")
            return {
                "ok": True,
                "data": data,
                "source": "html_fallback",
                "used_fallback": True,
                "count": len(data),
                "duration_sec": duration,
            }
    except Exception as e:
        logger.error(f"[Fallback] {parser_name} HTML fallback also failed: {e}")

    duration = round(time.time() - start, 1)
    return {
        "ok": False,
        "data": [],
        "source": "none",
        "used_fallback": True,
        "count": 0,
        "error": "both primary and fallback failed",
        "duration_sec": duration,
    }
