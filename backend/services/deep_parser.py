"""
Deep Parser — visits per-project pages on CryptoRank, ICODrops, DropsTab and
extracts the data that homepage-only parsers miss:

  • investors / funds / backers
  • team / persons / advisors
  • token sale rounds (seed/private/strategic/public)
  • vesting / unlock schedules
  • categories / sectors / tags

Quotes (price/marketcap/volume) are deliberately NOT pulled here — that
data is already handled by the homepage parsers and live market feeds.

Output collections (fomo_mobile):
  • deep_projects        — one doc per project profile (investors, team, sectors)
  • deep_funding_rounds  — one doc per (project, round) — Seed/Series A/etc.
  • deep_persons         — team members with role, project, twitter
  • deep_unlocks         — per-project vesting/unlock schedule
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import httpx
from bs4 import BeautifulSoup
from pymongo import MongoClient, DESCENDING

log = logging.getLogger("deep_parser")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [deep_parser] %(message)s")

_mongo = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
_db = _mongo[os.environ.get("DB_NAME", "fomo_mobile")]

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
_HEADERS = {"User-Agent": _UA, "Accept-Language": "en-US,en;q=0.9"}

_NEXT_RX = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL)


# ───────────────────────────────────────────────────────────────────────────
# Helpers
# ───────────────────────────────────────────────────────────────────────────
def _extract_next_data(html: str) -> Optional[Dict[str, Any]]:
    m = _NEXT_RX.search(html or "")
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except Exception:
        return None


async def _fetch_html(client: httpx.AsyncClient, url: str, *, retries: int = 2) -> Optional[str]:
    for attempt in range(retries + 1):
        try:
            r = await client.get(url, follow_redirects=True)
            if r.status_code == 200 and len(r.content) > 1000:
                return r.text
            log.info(f"  ! {url} → HTTP {r.status_code}")
        except Exception as e:
            log.info(f"  ! {url} → {type(e).__name__}: {str(e)[:80]}")
        if attempt < retries:
            await asyncio.sleep(0.6 + 0.4 * attempt)
    return None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ───────────────────────────────────────────────────────────────────────────
# CryptoRank — per-project deep scrape
# ───────────────────────────────────────────────────────────────────────────
async def _cryptorank_list_keys(client: httpx.AsyncClient, limit: int = 80) -> List[str]:
    """Pull top coin keys via public API."""
    try:
        r = await client.get("https://api.cryptorank.io/v0/coins", params={"limit": limit})
        if r.status_code != 200:
            return []
        return [c.get("key") for c in (r.json().get("data") or []) if c.get("key")]
    except Exception as e:
        log.warning(f"cryptorank list failed: {e}")
        return []


async def _cryptorank_funding_keys(client: httpx.AsyncClient) -> List[str]:
    """Pull ICO/funding-round project keys via Next.js HTML on category page."""
    keys: List[str] = []
    for tab in ("active", "upcoming", "ended"):
        html = await _fetch_html(client, f"https://cryptorank.io/ico/{tab}")
        if not html:
            continue
        nd = _extract_next_data(html)
        if not nd:
            continue
        try:
            data = (
                nd.get("props", {})
                .get("pageProps", {})
                .get("fallbackData", {})
                .get("data")
                or nd.get("props", {}).get("pageProps", {}).get("data", [])
            )
            if isinstance(data, dict):
                data = data.get("rows") or data.get("items") or []
            for row in (data or [])[:100]:
                if isinstance(row, dict) and row.get("key"):
                    keys.append(row["key"])
        except Exception:
            pass
    return list(dict.fromkeys(keys))[:120]


async def _cryptorank_scrape_project(
    client: httpx.AsyncClient, key: str
) -> Dict[str, Any]:
    """Scrape /ico/{key} and /price/{key} for investors + rounds + tokenomics."""
    out: Dict[str, Any] = {"source": "cryptorank", "project_key": key}
    # Try /ico/{key} first (richer for funding rounds)
    html = await _fetch_html(client, f"https://cryptorank.io/ico/{key}")
    if not html:
        html = await _fetch_html(client, f"https://cryptorank.io/price/{key}")
    if not html:
        return {}
    nd = _extract_next_data(html)
    if not nd:
        return {}
    pq = nd.get("props", {}).get("pageProps", {})
    coin = pq.get("coin") or {}
    out["name"] = coin.get("name") or key
    out["symbol"] = coin.get("symbol")
    out["category"] = coin.get("category")
    out["tagIds"] = coin.get("tagIds") or []
    out["hasFundingRounds"] = bool(coin.get("hasFundingRounds"))

    # Investors (the gold)
    investors_obj = pq.get("fallbackInvestors") or {}
    raw_investors = investors_obj.get("investors") or []
    investors = []
    for inv in raw_investors:
        if not isinstance(inv, dict):
            continue
        investors.append({
            "slug":     inv.get("slug"),
            "name":     inv.get("name"),
            "tier":     inv.get("tier"),
            "isLead":   bool(inv.get("isLead")),
            "category": inv.get("category"),
            "stage":    inv.get("stage") or [],
            "image":    inv.get("image"),
        })
    out["investors"] = investors
    out["investorCount"] = len(investors)

    # Rounds (kind is visible even when auth-blocked)
    cts = pq.get("coinTokenSales") or {}
    rounds_raw = cts.get("rounds") or []
    rounds = []
    for r in rounds_raw:
        if not isinstance(r, dict):
            continue
        rounds.append({
            "kind":         r.get("kind"),
            "saleName":     r.get("saleName") or r.get("name"),
            "raisedUsd":    r.get("totalRaisedInUsd") or r.get("raisedAmount") or r.get("raisedUsd"),
            "tokenPrice":   r.get("tokenPrice") or r.get("price"),
            "valuation":    r.get("valuation"),
            "startDate":    r.get("startDate"),
            "endDate":      r.get("endDate"),
            "investorsCnt": len(r.get("investors") or []),
            "investors":    [i.get("name") for i in (r.get("investors") or []) if isinstance(i, dict)],
        })
    out["rounds"] = rounds
    out["roundsCount"] = len(rounds)

    # Tokenomics / unlocks (initData)
    init_data = pq.get("initData") or {}
    out["initialSupply"] = (cts.get("coin") or {}).get("initialSupply")
    out["totalSupply"]   = (cts.get("coin") or {}).get("totalSupply")
    out["scrapedAt"]     = _now_iso()
    return out


# ───────────────────────────────────────────────────────────────────────────
# ICODrops — per-project deep scrape
# ───────────────────────────────────────────────────────────────────────────
_ICODROPS_EXCLUDE = {
    "about", "advertising", "calendar", "category", "ico-stats", "legal",
    "press-releases", "contact", "team", "premium", "vc", "points-farming",
    "newsletter", "search", "all-events", "events", "ad", "ads",
}


async def _icodrops_list_slugs(client: httpx.AsyncClient) -> List[str]:
    slugs: List[str] = []
    for cat_url in (
        "https://icodrops.com/category/upcoming-ico/",
        "https://icodrops.com/category/active-ico/",
        "https://icodrops.com/category/ended-ico/",
        "https://icodrops.com/",
    ):
        html = await _fetch_html(client, cat_url)
        if not html:
            continue
        soup = BeautifulSoup(html, "html.parser")
        # Match BOTH absolute and relative single-segment slugs.
        pat = re.compile(r"^(?:https?://(?:www\.)?icodrops\.com)?/([a-z0-9][a-z0-9\-]{2,})/?$")
        for a in soup.find_all("a", href=True):
            h = a.get("href", "")
            m = pat.match(h)
            if not m:
                continue
            slug = m.group(1)
            if slug in _ICODROPS_EXCLUDE or slug.startswith("category"):
                continue
            slugs.append(slug)
    return list(dict.fromkeys(slugs))[:80]


async def _icodrops_scrape_project(
    client: httpx.AsyncClient, slug: str
) -> Dict[str, Any]:
    html = await _fetch_html(client, f"https://icodrops.com/{slug}/")
    if not html:
        return {}
    soup = BeautifulSoup(html, "html.parser")
    out: Dict[str, Any] = {"source": "icodrops", "project_key": slug, "scrapedAt": _now_iso()}

    # Title
    h1 = soup.find("h1")
    out["name"] = (h1.get_text(strip=True) if h1 else slug.replace("-", " ").title())

    # ── Investors — ICODrops renders backers as alt-text or img title in dedicated section
    investors: List[Dict[str, Any]] = []
    # Strategy 1: look for class names containing investor/backer/partner
    for blk in soup.find_all(class_=re.compile(r"(investor|backer|partner|fund)", re.I)):
        # Investors are typically images with alt=name OR links
        for img in blk.find_all("img"):
            alt = (img.get("alt") or "").strip()
            if alt and 2 <= len(alt) <= 60 and "logo" not in alt.lower():
                investors.append({"name": alt, "image": img.get("src")})
        for a in blk.find_all("a"):
            txt = a.get_text(strip=True)
            href = a.get("href", "")
            if txt and 2 <= len(txt) <= 60:
                investors.append({"name": txt, "url": href})
    # Strategy 2: header "Investors/Backers/Funds" then siblings
    for hdr_text in ("Backers", "Investors", "Funds", "Partners", "Backed By"):
        hdr = soup.find(
            lambda tag: tag.name in ("h1", "h2", "h3", "h4", "div", "span")
                       and hdr_text.lower() in (tag.get_text("") or "").lower()
                       and len(tag.get_text("") or "") < 80
        )
        if not hdr:
            continue
        for sib in [hdr.find_next("ul"), hdr.find_next("div"), hdr.find_next("section")]:
            if not sib:
                continue
            for img in sib.find_all("img", limit=30):
                alt = (img.get("alt") or "").strip()
                if alt and 2 <= len(alt) <= 60 and "logo" not in alt.lower():
                    investors.append({"name": alt, "image": img.get("src")})

    # Dedup by lowercase name
    seen = set()
    dedup_inv = []
    for i in investors:
        n = (i.get("name") or "").strip()
        if not n or n.lower() in seen:
            continue
        # Drop obvious noise
        nl = n.lower()
        if any(k in nl for k in ("icon", "click here", "subscribe", "join", "twitter", "telegram", "discord", "github")):
            continue
        seen.add(nl)
        dedup_inv.append(i)
    out["investors"] = dedup_inv[:60]
    out["investorCount"] = len(out["investors"])

    # ── Token sale rounds — look for table or sections with "$X.XM Raised"
    rounds: List[Dict[str, Any]] = []
    # Look for $ amounts associated with round labels
    for el in soup.find_all(string=re.compile(r"\$[\d,.]+[MBmb]?\b")):
        parent = el.find_parent()
        if not parent:
            continue
        amt_match = re.search(r"\$([\d,.]+)\s?([MBmb]?)", el)
        if not amt_match:
            continue
        try:
            num_raw = amt_match.group(1).replace(",", "")
            num = float(num_raw)
            mult = 1_000_000 if amt_match.group(2).upper() == "M" else 1_000_000_000 if amt_match.group(2).upper() == "B" else 1
            raised = int(num * mult)
        except Exception:
            continue
        if raised < 100_000:
            continue
        # Look upward for a round label
        ctx = parent.get_text(" ", strip=True)[:120]
        label_match = re.search(r"\b(Seed|Private|Public|Strategic|Series\s+[A-C]|Pre-?Sale|IDO|ICO|IEO)\b", ctx, re.I)
        if not label_match:
            continue
        rounds.append({"label": label_match.group(0).title(), "raisedUsd": raised, "rawText": ctx})
    # Dedup by (label, amount)
    seen_r = set()
    rounds_unique = []
    for r in rounds:
        k = (r["label"], r["raisedUsd"])
        if k not in seen_r:
            seen_r.add(k)
            rounds_unique.append(r)
    out["rounds"] = rounds_unique[:10]
    out["roundsCount"] = len(out["rounds"])

    # ── Team members
    team: List[Dict[str, Any]] = []
    hdr = soup.find(lambda tag: tag.name in ("h2", "h3") and "team" in (tag.get_text("") or "").lower())
    if hdr:
        block = hdr.find_next(["div", "section", "ul"])
        if block:
            for member in block.find_all(["li", "div"], limit=30):
                name_el = member.find(["h4", "h5", "strong", "b", "a"])
                role_el = member.find(["p", "span", "em"])
                if name_el and name_el.get_text(strip=True):
                    nm = name_el.get_text(strip=True)
                    if 2 <= len(nm) <= 60:
                        team.append({
                            "name": nm,
                            "role": (role_el.get_text(strip=True)[:80] if role_el else None),
                        })
    out["team"] = team[:30]
    out["teamCount"] = len(out["team"])

    # ── Tags / category
    for tag in soup.find_all("meta", attrs={"property": "article:tag"}):
        if not out.get("tags"):
            out["tags"] = []
        out["tags"].append(tag.get("content"))
    cat_el = soup.find(class_=re.compile(r"category|tag", re.I))
    if cat_el:
        out["category"] = cat_el.get_text(strip=True)[:80]
    return out


# ───────────────────────────────────────────────────────────────────────────
# DropsTab — per-project deep scrape (uses /coins/{slug} + Next.js data)
# ───────────────────────────────────────────────────────────────────────────
async def _dropstab_list_slugs(client: httpx.AsyncClient) -> List[str]:
    """Pull coin slugs from DropsTab homepage Next.js data."""
    slugs: List[str] = []
    for url in (
        "https://dropstab.com/",
        "https://dropstab.com/portfolio",
    ):
        html = await _fetch_html(client, url)
        if not html:
            continue
        nd = _extract_next_data(html)
        if not nd:
            continue
        try:
            pq = nd.get("props", {}).get("pageProps", {})
            for src in ("coinsBody", "fallbackTopGainers", "presetsBody"):
                v = pq.get(src) or {}
                if isinstance(v, dict):
                    coins = v.get("coins") or []
                else:
                    coins = v if isinstance(v, list) else []
                for c in coins[:80]:
                    if isinstance(c, dict) and c.get("slug"):
                        slugs.append(c["slug"])
        except Exception as e:
            log.info(f"  dropstab list parse: {e!r}")
    return list(dict.fromkeys(slugs))[:60]


async def _dropstab_scrape_project(
    client: httpx.AsyncClient, slug: str
) -> Dict[str, Any]:
    """Pulls EVERYTHING DropsTab exposes per project — investors, funds,
    sales rounds, vesting unlocks (past+upcoming+schedule), token
    distribution, persons (via tweetscout influencers/funds), events,
    certik audit, rank, tags."""
    html = await _fetch_html(client, f"https://dropstab.com/coins/{slug}")
    if not html:
        return {}
    out: Dict[str, Any] = {"source": "dropstab", "project_key": slug, "scrapedAt": _now_iso()}
    nd = _extract_next_data(html)
    if not nd:
        return out
    try:
        pq = nd.get("props", {}).get("pageProps", {})
        coin = pq.get("coin") or {}
        if not isinstance(coin, dict):
            return out

        out["name"]      = coin.get("name") or slug.title()
        out["symbol"]    = coin.get("symbol")
        out["rank"]      = coin.get("rank")
        out["mainTag"]   = (coin.get("mainTag") or {}).get("name") if isinstance(coin.get("mainTag"), dict) else None
        out["category"]  = out["mainTag"]
        out["tags"]      = [
            (t.get("name") if isinstance(t, dict) else str(t))
            for t in (coin.get("tags") or [])
        ][:25]
        out["description"] = (coin.get("description") or "")[:600]
        out["links"]     = coin.get("links") or []
        out["isVestingExists"]    = bool(coin.get("isVestingExists"))
        out["isFundraisingExists"] = bool(coin.get("isFundraisingExists"))
        out["certikData"] = coin.get("certikData")

        # ── 1. INVESTORS (basic + leadInvestors flag)
        raw_investors  = coin.get("investors") or []
        lead_investors = coin.get("leadInvestors") or []
        lead_set = {
            (i.get("name") if isinstance(i, dict) else str(i)).lower()
            for i in lead_investors if i
        }
        investors_list: List[Dict[str, Any]] = []
        for inv in raw_investors:
            if not isinstance(inv, dict):
                continue
            name = (inv.get("name") or "").strip()
            if not name:
                continue
            investors_list.append({
                "id":      inv.get("id"),
                "name":    name,
                "slug":    inv.get("slug"),
                "tier":    inv.get("tier"),
                "isLead":  name.lower() in lead_set,
                "image":   inv.get("image") or inv.get("logo"),
                "country": (inv.get("country") or {}).get("name") if isinstance(inv.get("country"), dict) else None,
            })
        out["investors"]     = investors_list
        out["investorCount"] = len(investors_list)
        out["leadInvestors"] = sorted(lead_set)

        # ── 2. FUNDRAISING — the rich source (sales, VCs with full info, distributions, vesting)
        fr = coin.get("fundraising") or {}
        out["totalRaised"]       = fr.get("totalRaised")
        out["totalTokens"]       = fr.get("totalTokens")
        out["totalTokensSold"]   = fr.get("totalTokensSold")
        out["totalSoldPercent"]  = fr.get("totalSoldPercent")
        out["icodropsHypeRate"]  = fr.get("icodropsHypeRate")
        out["icodropsRiskRate"]  = fr.get("icodropsRiskRate")
        out["icodropsRoiRate"]   = fr.get("icodropsRoiRate")
        out["icodropsInterest"]  = fr.get("icodropsInterest")
        out["icodropsUrl"]       = fr.get("icodropsUrl")

        # 2a. Sales rounds (real ones with $ amounts)
        sales = fr.get("sales") or []
        rounds_list: List[Dict[str, Any]] = []
        for s in sales:
            if not isinstance(s, dict):
                continue
            rounds_list.append({
                "id":             s.get("id"),
                "kind":           s.get("type") or "Sale",
                "saleName":       s.get("name"),
                "raisedUsd":      s.get("raised"),
                "tokenPrice":     s.get("price"),
                "valuation":      s.get("preValuation") or s.get("valuation"),
                "tokensForSale":  s.get("tokensForSaleAmount"),
                "startDate":      s.get("startDate"),
                "endDate":        s.get("endDate"),
                "investors":      [
                    (i.get("name") if isinstance(i, dict) else str(i))
                    for i in (s.get("ventureCapitals") or s.get("investors") or [])
                ],
                "investorsCnt":   len(s.get("ventureCapitals") or s.get("investors") or []),
            })
        out["rounds"]      = rounds_list
        out["roundsCount"] = len(rounds_list)

        # 2b. Token distributions (Team %, Investors %, etc.)
        td = fr.get("tokenDistributions") or []
        out["tokenDistributions"] = [
            {"name": d.get("name"), "value": d.get("value"), "amount": d.get("amount"), "saleId": d.get("saleId")}
            for d in td if isinstance(d, dict)
        ]

        # ── 3. VESTING / UNLOCKS — past + upcoming + schedule
        vesting = (fr.get("vesting") or {}) if isinstance(fr.get("vesting"), dict) else {}
        out["tgeDate"] = vesting.get("tgeDate")
        out["totalUnlockProgress"] = vesting.get("totalUnlockProgress")
        out["nextUnlockDetails"]   = vesting.get("nextUnlockDetails")
        past_unlocks     = vesting.get("pastUnlocks") or []
        upcoming_unlocks = vesting.get("upcomingUnlocks") or []
        vesting_schedule = vesting.get("vestingSchedule") or []
        all_unlocks: List[Dict[str, Any]] = []
        for ul in past_unlocks[:50]:
            if isinstance(ul, dict):
                all_unlocks.append({**ul, "phase": "past"})
        for ul in upcoming_unlocks[:50]:
            if isinstance(ul, dict):
                all_unlocks.append({**ul, "phase": "upcoming"})
        out["unlocks"]       = all_unlocks
        out["unlockCount"]   = len(all_unlocks)
        out["vestingSchedule"] = vesting_schedule[:60]

        # ── 4. PERSONS — via tweetscout influencers + funds (REAL X handles!)
        ts = coin.get("tweetscout") or {}
        out["twitterScore"] = ts.get("score")
        persons: List[Dict[str, Any]] = []
        for kind, list_key in (("influencer", "influencers"), ("fund_person", "funds"), ("project", "projects")):
            for p in (ts.get(list_key) or []):
                if not isinstance(p, dict):
                    continue
                handle = (p.get("username") or "").strip()
                if not handle:
                    continue
                persons.append({
                    "handle":     handle,
                    "name":       p.get("fullName") or handle,
                    "kind":       kind,
                    "score":      p.get("score"),
                    "followers":  p.get("followersCount"),
                    "avatar":     p.get("avatar"),
                    "tag":        p.get("tag"),
                })
        out["persons"]     = persons
        out["personCount"] = len(persons)

        # ── 5. EVENTS (62 per project sometimes — list/airdrop/partnership)
        events_list: List[Dict[str, Any]] = []
        for e in (coin.get("events") or []):
            if not isinstance(e, dict):
                continue
            events_list.append({
                "title":       e.get("title"),
                "description": (e.get("description") or "")[:200],
                "eventDate":   e.get("eventDate"),
                "source":      e.get("source"),
                "proof":       e.get("proof"),
                "type":        e.get("type"),
            })
        out["events"]     = events_list[:50]
        out["eventCount"] = len(events_list[:50])

        # ── 6. ACTIVITIES (already paginated, take widget)
        wa = pq.get("widgetActivities") or {}
        if isinstance(wa, dict):
            wa_content = wa.get("content") or []
            out["activitiesPreview"] = wa_content[:10]

    except Exception as e:
        log.info(f"  dropstab parse {slug}: {type(e).__name__}: {e!r}")
    return out


async def _dropstab_funds_list(client: httpx.AsyncClient, pages: int = 3) -> List[str]:
    """List of DropsTab investor/fund slugs from /investors paginated."""
    slugs: List[str] = []
    for p in range(1, pages + 1):
        url = "https://dropstab.com/investors" if p == 1 else f"https://dropstab.com/investors?page={p}"
        html = await _fetch_html(client, url)
        if not html:
            continue
        nd = _extract_next_data(html)
        if not nd:
            continue
        try:
            content = (
                nd.get("props", {}).get("pageProps", {})
                .get("fallbackBody", {}).get("content")
                or []
            )
            for inv in content:
                if isinstance(inv, dict) and inv.get("investorSlug"):
                    slugs.append(inv["investorSlug"])
        except Exception:
            pass
    return list(dict.fromkeys(slugs))[:40]


async def _dropstab_scrape_fund(
    client: httpx.AsyncClient, slug: str
) -> Optional[Dict[str, Any]]:
    """Per-fund deep profile from DropsTab /investors/{slug}."""
    html = await _fetch_html(client, f"https://dropstab.com/investors/{slug}")
    if not html:
        return None
    nd = _extract_next_data(html)
    if not nd:
        return None
    try:
        pq = nd.get("props", {}).get("pageProps", {})
        inv = pq.get("fallbackBodyInvestor") or {}
        if not isinstance(inv, dict) or not inv.get("name"):
            return None
        portfolio_obj = pq.get("fallbackBodyPortfolio") or {}
        if isinstance(portfolio_obj, list):
            portfolio_raw = portfolio_obj
        elif isinstance(portfolio_obj, dict):
            portfolio_raw = portfolio_obj.get("content") or portfolio_obj.get("data") or []
        else:
            portfolio_raw = []
        portfolio: List[Dict[str, Any]] = []
        for proj in portfolio_raw[:40]:
            if not isinstance(proj, dict):
                continue
            portfolio.append({
                "id":         proj.get("id"),
                "slug":       proj.get("slug"),
                "name":       proj.get("name"),
                "symbol":     proj.get("symbol"),
                "rank":       proj.get("rank"),
                "fundsRaised": proj.get("fundsRaised"),
            })
        return {
            "id":                f"dropstab:fund:{slug}",
            "source":            "dropstab",
            "slug":              slug,
            "name":              inv.get("name"),
            "tier":              inv.get("tier"),
            "ventureType":       inv.get("ventureType"),
            "rank":              inv.get("rank"),
            "rating":            inv.get("rating"),
            "country":           (
                inv["country"].get("name") if isinstance(inv.get("country"), dict)
                else (inv["country"][0].get("name") if isinstance(inv.get("country"), list) and inv["country"] and isinstance(inv["country"][0], dict)
                      else (str(inv["country"][0]) if isinstance(inv.get("country"), list) and inv["country"]
                            else inv.get("country") if isinstance(inv.get("country"), str)
                            else None))
            ),
            "twitterUrl":        inv.get("twitterUrl"),
            "totalInvestments":  inv.get("totalInvestments"),
            "leadInvestments":   inv.get("leadInvestments") if not isinstance(inv.get("leadInvestments"), list) else len(inv.get("leadInvestments") or []),
            "avgPublicRoi":      inv.get("avgPublicRoi"),
            "avgPrivateRoi":     inv.get("avgPrivateRoi"),
            "roundsPerYear":     inv.get("roundsPerYear"),
            "description":       (inv.get("description") or "")[:600],
            "logo":              inv.get("logo") or inv.get("image"),
            "links":             inv.get("links") or [],
            "portfolio":         portfolio,
            "portfolioCount":    len(portfolio),
            "scrapedAt":         _now_iso(),
        }
    except Exception as e:
        log.warning(f"  fund scrape {slug}: {type(e).__name__}: {e!r}")
        return None


def _persist_fund(fund: Dict[str, Any]) -> None:
    if not fund or not fund.get("id"):
        return
    _db.deep_funds.update_one(
        {"id": fund["id"]},
        {"$set": {**fund, "updatedAt": datetime.now(timezone.utc)}},
        upsert=True,
    )


# ───────────────────────────────────────────────────────────────────────────
# CoinMarketCap — best-effort unlocks parser
# ───────────────────────────────────────────────────────────────────────────
# Strategy: CMC's data-api subdomain is geo-blocked from many cloud IPs
# (Chinese 404 page returned). We use the public SSR pages where token unlock
# info may be embedded in __NEXT_DATA__.props.pageProps.detailRes.tokenUnlockLatest.
# When that field is null, we still upsert a minimal placeholder so that the
# UI can show "CMC: data unavailable for this region" gracefully, instead
# of pretending the source doesn't exist at all.

_CMC_ASSETS = [
    "arbitrum", "optimism", "sui", "aptos", "celestia",
    "jito", "pyth-network", "sei", "starknet", "blast",
    "ondo-finance", "ethena", "manta-network", "wormhole", "altlayer",
    "dymension", "pixels", "portal", "io-net", "ena",
]


async def _coinmarketcap_scrape_unlock(
    client: httpx.AsyncClient, slug: str
) -> Optional[Dict[str, Any]]:
    """Pulls unlock data from CMC SSR page (when available)."""
    html = await _fetch_html(client, f"https://coinmarketcap.com/currencies/{slug}/")
    if not html:
        return None
    nd = _extract_next_data(html)
    if not nd:
        return None
    try:
        pp = nd.get("props", {}).get("pageProps", {}) or {}
        det_res = pp.get("detailRes", {}) or {}
        detail  = det_res.get("detail", {}) or {}
        tul     = det_res.get("tokenUnlockLatest")
        # Always emit a record - even if tul is None it documents the source
        statistics = (detail.get("statistics") or {}) if isinstance(detail, dict) else {}
        out = {
            "source":       "coinmarketcap",
            "project_key":  slug,
            "name":         detail.get("name") or slug,
            "symbol":       detail.get("symbol"),
            "category":     detail.get("category"),
            "cmcId":        detail.get("id"),
            "marketCap":    statistics.get("marketCap"),
            "price":        statistics.get("price"),
            "scrapedAt":    _now_iso(),
        }
        if tul and isinstance(tul, dict):
            out["tokenUnlockLatest"] = tul
            out["nextUnlockDate"]    = tul.get("nextUnlockDate") or tul.get("unlockDate")
            out["nextUnlockAmount"]  = tul.get("nextUnlockAmount") or tul.get("unlockAmount")
            out["totalUnlocked"]     = tul.get("totalUnlocked")
            out["totalLocked"]       = tul.get("totalLocked")
            out["hasData"]           = True
        else:
            out["hasData"]           = False
            out["note"]              = "CMC SSR did not embed tokenUnlockLatest — data is client-loaded"
        return out
    except Exception as e:
        log.info(f"  cmc unlock parse {slug}: {type(e).__name__}: {e!r}")
        return None


def _persist_cmc_unlock(doc: Dict[str, Any]) -> None:
    if not doc or not doc.get("project_key"):
        return
    uid = f"coinmarketcap:{doc['project_key']}:unlock_latest"
    _db.deep_unlocks.update_one(
        {"id": uid},
        {"$set": {**doc, "id": uid, "kind": "cmc_unlock_latest",
                  "updatedAt": datetime.now(timezone.utc)}},
        upsert=True,
    )


# ───────────────────────────────────────────────────────────────────────────
# Persistence
# ───────────────────────────────────────────────────────────────────────────
def _persist(doc: Dict[str, Any]) -> None:
    if not doc or not doc.get("project_key"):
        return
    key = f"{doc['source']}:{doc['project_key']}"
    _db.deep_projects.update_one(
        {"id": key},
        {"$set": {**doc, "id": key, "updatedAt": datetime.now(timezone.utc)}},
        upsert=True,
    )
    # Persist each funding round
    project_name = doc.get("name") or doc.get("project_key")
    for i, rnd in enumerate(doc.get("rounds") or []):
        round_id = f"{key}:round:{i}:{rnd.get('saleName') or rnd.get('kind') or rnd.get('label') or i}"
        payload = {
            **rnd,
            "id":           round_id,
            "raw_id":       rnd.get("id"),
            "source":       doc["source"],
            "project_key":  doc["project_key"],
            "project_name": project_name,
            "updatedAt":    datetime.now(timezone.utc),
        }
        _db.deep_funding_rounds.update_one(
            {"id": round_id},
            {"$set": payload},
            upsert=True,
        )
    # Persist team members (legacy "team" field)
    for m in doc.get("team") or []:
        if not isinstance(m, dict) or not m.get("name"):
            continue
        person_id = f"{doc['source']}:{doc['project_key']}:person:{m['name'].lower().replace(' ', '-')}"
        _db.deep_persons.update_one(
            {"id": person_id},
            {"$set": {
                "id":           person_id,
                "source":       doc["source"],
                "project_key":  doc["project_key"],
                "project_name": project_name,
                "name":         m.get("name"),
                "role":         m.get("role"),
                "kind":         "team",
                "updatedAt":    datetime.now(timezone.utc),
            }},
            upsert=True,
        )
    # Persist persons (DropsTab tweetscout: influencers / funds / projects)
    for p in doc.get("persons") or []:
        if not isinstance(p, dict) or not p.get("handle"):
            continue
        handle = p["handle"].lstrip("@").lower()
        person_id = f"{doc['source']}:{doc['project_key']}:person:{handle}"
        _db.deep_persons.update_one(
            {"id": person_id},
            {"$set": {
                "id":           person_id,
                "source":       doc["source"],
                "project_key":  doc["project_key"],
                "project_name": project_name,
                "handle":       handle,
                "name":         p.get("name") or handle,
                "kind":         p.get("kind"),
                "tag":          p.get("tag"),
                "score":        p.get("score"),
                "followers":    p.get("followers"),
                "avatar":       p.get("avatar"),
                "updatedAt":    datetime.now(timezone.utc),
            }},
            upsert=True,
        )
    # Persist unlocks — one doc per unlock event (so we can rank/filter properly)
    for i, ul in enumerate(doc.get("unlocks") or []):
        if not isinstance(ul, dict):
            continue
        # IMPORTANT: place explicit id AFTER **ul so it isn't overwritten
        # by ul['id'] (raw provider id, often numeric / None).
        unlock_id = f"{doc['source']}:{doc['project_key']}:unlock:{ul.get('id') or i}"
        payload = {
            **ul,
            "id":            unlock_id,
            "raw_id":        ul.get("id"),
            "source":        doc["source"],
            "project_key":   doc["project_key"],
            "project_name":  project_name,
            "symbol":        doc.get("symbol"),
            "updatedAt":     datetime.now(timezone.utc),
        }
        _db.deep_unlocks.update_one(
            {"id": unlock_id},
            {"$set": payload},
            upsert=True,
        )
    # Persist project-level vesting schedule snapshot
    if doc.get("vestingSchedule") or doc.get("totalUnlockProgress") or doc.get("nextUnlockDetails"):
        snap_id = f"{doc['source']}:{doc['project_key']}:vesting_snapshot"
        _db.deep_unlocks.update_one(
            {"id": snap_id},
            {"$set": {
                "id":             snap_id,
                "source":         doc["source"],
                "project_key":    doc["project_key"],
                "project_name":   project_name,
                "symbol":         doc.get("symbol"),
                "kind":           "vesting_snapshot",
                "tgeDate":        doc.get("tgeDate"),
                "totalUnlockProgress": doc.get("totalUnlockProgress"),
                "nextUnlockDetails":   doc.get("nextUnlockDetails"),
                "vestingSchedule": doc.get("vestingSchedule"),
                "updatedAt":      datetime.now(timezone.utc),
            }},
            upsert=True,
        )
    # Persist events (airdrops, listings, partnerships)
    for i, ev in enumerate(doc.get("events") or []):
        if not isinstance(ev, dict) or not ev.get("title"):
            continue
        evid = f"{doc['source']}:{doc['project_key']}:event:{i}:{(ev.get('title') or '')[:60]}"
        payload = {
            **ev,
            "id":            evid,
            "raw_id":        ev.get("id"),
            "source":        doc["source"],
            "project_key":   doc["project_key"],
            "project_name":  project_name,
            "updatedAt":     datetime.now(timezone.utc),
        }
        _db.deep_project_events.update_one(
            {"id": evid},
            {"$set": payload},
            upsert=True,
        )


# ───────────────────────────────────────────────────────────────────────────
# Public entry points
# ───────────────────────────────────────────────────────────────────────────
async def run_cycle(
    cryptorank_limit: int = 40,
    icodrops_limit: int = 30,
    dropstab_limit: int = 30,
    funds_limit: int = 25,
    cmc_limit: int = 20,
    concurrency: int = 4,
) -> Dict[str, Any]:
    """Run one deep-scrape cycle across all sources + funds."""
    started = time.time()
    summary: Dict[str, Any] = {
        "cryptorank": 0, "icodrops": 0, "dropstab": 0, "funds": 0, "cmc": 0, "errors": [],
    }
    sem = asyncio.Semaphore(concurrency)

    async with httpx.AsyncClient(timeout=30, headers=_HEADERS) as client:
        # 1. CryptoRank
        keys = await _cryptorank_list_keys(client, limit=cryptorank_limit)
        log.info(f"CryptoRank: {len(keys)} project keys")

        async def _do_cr(k: str) -> None:
            async with sem:
                try:
                    doc = await _cryptorank_scrape_project(client, k)
                    if doc:
                        _persist(doc)
                        summary["cryptorank"] += 1
                except Exception as e:
                    summary["errors"].append(f"cr:{k}:{type(e).__name__}")
        await asyncio.gather(*(_do_cr(k) for k in keys[:cryptorank_limit]))

        # 2. ICODrops
        slugs = await _icodrops_list_slugs(client)
        log.info(f"ICODrops: {len(slugs)} project slugs")

        async def _do_id(s: str) -> None:
            async with sem:
                try:
                    doc = await _icodrops_scrape_project(client, s)
                    if doc:
                        _persist(doc)
                        summary["icodrops"] += 1
                except Exception as e:
                    summary["errors"].append(f"id:{s}:{type(e).__name__}")
        await asyncio.gather(*(_do_id(s) for s in slugs[:icodrops_limit]))

        # 3. DropsTab projects
        ds_slugs = await _dropstab_list_slugs(client)
        log.info(f"DropsTab: {len(ds_slugs)} project slugs")

        async def _do_ds(s: str) -> None:
            async with sem:
                try:
                    doc = await _dropstab_scrape_project(client, s)
                    if doc:
                        _persist(doc)
                        summary["dropstab"] += 1
                except Exception as e:
                    summary["errors"].append(f"ds:{s}:{type(e).__name__}")
        await asyncio.gather(*(_do_ds(s) for s in ds_slugs[:dropstab_limit]))

        # 4. DropsTab funds (deep VC profiles with ROI / portfolio / tier)
        fund_slugs = await _dropstab_funds_list(client)
        log.info(f"DropsTab funds: {len(fund_slugs)} slugs")

        async def _do_fund(s: str) -> None:
            async with sem:
                try:
                    fund = await _dropstab_scrape_fund(client, s)
                    if fund:
                        _persist_fund(fund)
                        summary["funds"] += 1
                except Exception as e:
                    summary["errors"].append(f"fund:{s}:{type(e).__name__}")
        await asyncio.gather(*(_do_fund(s) for s in fund_slugs[:funds_limit]))

        # 5. CoinMarketCap unlocks (best-effort SSR scrape — falls back to placeholder
        # when CMC client-loaded unlock data is unavailable due to geo-block)
        cmc_slugs = _CMC_ASSETS[:cmc_limit]
        log.info(f"CoinMarketCap: {len(cmc_slugs)} assets to probe")

        async def _do_cmc(s: str) -> None:
            async with sem:
                try:
                    doc = await _coinmarketcap_scrape_unlock(client, s)
                    if doc:
                        _persist_cmc_unlock(doc)
                        summary["cmc"] += 1
                except Exception as e:
                    summary["errors"].append(f"cmc:{s}:{type(e).__name__}")
        await asyncio.gather(*(_do_cmc(s) for s in cmc_slugs))

    summary["elapsed"] = round(time.time() - started, 2)
    summary["ts"] = _now_iso()
    log.info(f"deep cycle done: {summary}")
    return summary


async def _loop(interval_sec: int = 6 * 3600):
    log.info(f"deep parser loop starting (every {interval_sec}s)")
    await asyncio.sleep(120)  # give backend startup priority
    while True:
        try:
            await run_cycle()
        except Exception as e:
            log.error(f"deep cycle error: {e!r}")
        try:
            await asyncio.sleep(interval_sec)
        except asyncio.CancelledError:
            log.info("deep parser loop cancelled")
            raise


def start_loop_if_enabled() -> Dict[str, Any]:
    flag = os.environ.get("DEEP_PARSER_ENABLED", "true").strip().lower()
    if flag in ("0", "false", "no", "off"):
        return {"started": False, "reason": "disabled_by_flag"}
    interval = int(os.environ.get("DEEP_PARSER_INTERVAL_SEC", 6 * 3600))
    asyncio.create_task(_loop(interval))
    return {"started": True, "interval_sec": interval}


# Best-effort indexes
try:
    _db.deep_projects.create_index([("id", 1)], unique=True)
    _db.deep_projects.create_index([("source", 1), ("project_key", 1)])
    _db.deep_projects.create_index([("name", 1)])
    _db.deep_funding_rounds.create_index([("id", 1)], unique=True)
    _db.deep_funding_rounds.create_index([("project_key", 1)])
    _db.deep_persons.create_index([("id", 1)], unique=True)
    _db.deep_persons.create_index([("project_key", 1)])
    _db.deep_persons.create_index([("handle", 1)])
    _db.deep_persons.create_index([("kind", 1)])
    _db.deep_unlocks.create_index([("id", 1)], unique=True)
    _db.deep_unlocks.create_index([("project_key", 1)])
    _db.deep_unlocks.create_index([("symbol", 1)])
    _db.deep_funds.create_index([("id", 1)], unique=True)
    _db.deep_funds.create_index([("slug", 1)])
    _db.deep_funds.create_index([("tier", 1)])
    _db.deep_project_events.create_index([("id", 1)], unique=True)
    _db.deep_project_events.create_index([("project_key", 1)])
except Exception:
    pass


if __name__ == "__main__":
    asyncio.run(run_cycle())
