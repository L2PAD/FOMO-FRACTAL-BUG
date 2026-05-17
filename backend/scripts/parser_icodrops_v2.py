"""
ICO Drops Parser (Updated)
===========================

Scrapes ICODrops.com for:
- Upcoming ICOs (/category/upcoming-ico/)
- Active ICOs (/category/active-ico/)
- VC Funding Rounds (/vc/funding-rounds/)

Stores to: intel_events, intel_funding
"""

import httpx
import logging
import re
from typing import Dict, List, Any
from datetime import datetime, timezone
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

ICODROPS_URL = "https://icodrops.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


async def fetch_icodrops_upcoming(client) -> List[Dict]:
    """Fetch upcoming ICOs from ICODrops (new URL structure)"""
    icos = []
    try:
        resp = await client.get(f"{ICODROPS_URL}/category/upcoming-ico/", headers=HEADERS)
        if resp.status_code != 200:
            logger.warning(f"ICODrops upcoming returned {resp.status_code}")
            return icos
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # Parse ICO entries — look for various card structures
        for selector in ['.a_ico', '.ico-card', '.icoList .col-md-12', 'article', '.token-row']:
            cards = soup.select(selector)
            if cards:
                logger.info(f"ICODrops upcoming: found {len(cards)} cards with selector '{selector}'")
                for card in cards[:50]:
                    try:
                        # Try multiple name selectors
                        name = ""
                        for ns in ['h3 a', '.ico-row h3 a', 'h3', '.token-name', 'a.name', '.title a']:
                            el = card.select_one(ns)
                            if el and el.text.strip():
                                name = el.text.strip()
                                break
                        
                        if not name or len(name) < 2:
                            continue
                        
                        link = ""
                        for ls in ['h3 a', '.title a', 'a']:
                            el = card.select_one(ls)
                            if el and el.get('href'):
                                link = el['href']
                                break
                        
                        category = ""
                        for cs in ['.categ_type', '.category', '.tag', '.sale-type']:
                            el = card.select_one(cs)
                            if el:
                                category = el.text.strip()
                                break
                        
                        date_text = ""
                        for ds in ['.date', '.sale-date', '.tge-date', 'time']:
                            el = card.select_one(ds)
                            if el:
                                date_text = el.text.strip()
                                break
                        
                        raised = ""
                        for rs in ['.funds-raised', '.raised', '.total-raised']:
                            el = card.select_one(rs)
                            if el:
                                raised = el.text.strip()
                                break
                        
                        interest = ""
                        for ins in ['.interest', '.rating', '.score']:
                            el = card.select_one(ins)
                            if el:
                                interest = el.text.strip()
                                break
                        
                        icos.append({
                            "name": name,
                            "url": f"{ICODROPS_URL}{link}" if link.startswith('/') else link,
                            "category": category,
                            "date": date_text,
                            "raised": raised,
                            "interest": interest,
                            "status": "upcoming",
                            "source": "icodrops"
                        })
                    except Exception as e:
                        logger.debug(f"Error parsing ICO card: {e}")
                        continue
                break  # Found working selector, stop trying others
        
        # Fallback: extract project names from links
        if not icos:
            all_links = soup.select('a[href]')
            for link in all_links:
                href = link.get('href', '')
                text = link.text.strip()
                if href.startswith('/') and len(text) > 2 and not any(x in href.lower() for x in ['category', 'vc', 'about', 'login', 'register', 'tag', 'page', '#', 'points']):
                    if text and len(text) < 50 and text not in ['ICO Drops', 'Home', 'About']:
                        icos.append({
                            "name": text,
                            "url": f"{ICODROPS_URL}{href}",
                            "category": "ico",
                            "status": "upcoming",
                            "source": "icodrops"
                        })
            # Deduplicate
            seen = set()
            unique_icos = []
            for ico in icos:
                if ico['name'] not in seen:
                    seen.add(ico['name'])
                    unique_icos.append(ico)
            icos = unique_icos[:50]
        
        logger.info(f"ICODrops upcoming: {len(icos)} ICOs parsed")
    except Exception as e:
        logger.error(f"ICODrops upcoming error: {e}")
    
    return icos


async def fetch_icodrops_active(client) -> List[Dict]:
    """Fetch active ICOs from ICODrops"""
    icos = []
    try:
        resp = await client.get(f"{ICODROPS_URL}/category/active-ico/", headers=HEADERS)
        if resp.status_code != 200:
            return icos
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        for selector in ['.a_ico', '.ico-card', 'article', '.token-row']:
            cards = soup.select(selector)
            if cards:
                for card in cards[:30]:
                    try:
                        name_el = card.select_one('h3 a') or card.select_one('h3') or card.select_one('.title a')
                        if not name_el:
                            continue
                        name = name_el.text.strip()
                        if not name:
                            continue
                        
                        link = name_el.get('href', '') if name_el.name == 'a' else ''
                        
                        icos.append({
                            "name": name,
                            "url": f"{ICODROPS_URL}{link}" if link.startswith('/') else link,
                            "status": "active",
                            "source": "icodrops"
                        })
                    except:
                        continue
                break
        
        logger.info(f"ICODrops active: {len(icos)} ICOs")
    except Exception as e:
        logger.error(f"ICODrops active error: {e}")
    
    return icos


async def fetch_icodrops_funding_rounds(client) -> List[Dict]:
    """Fetch VC funding rounds from ICODrops"""
    rounds = []
    try:
        resp = await client.get(f"{ICODROPS_URL}/vc/funding-rounds/", headers=HEADERS)
        if resp.status_code != 200:
            logger.warning(f"ICODrops funding returned {resp.status_code}")
            return rounds
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        text = resp.text
        
        # Try structured parsing
        for selector in ['.funding-row', '.vc-row', 'tr', '.round-card', 'article']:
            rows = soup.select(selector)
            if rows and len(rows) > 3:
                logger.info(f"ICODrops funding: found {len(rows)} rows with '{selector}'")
                for row in rows[:100]:
                    try:
                        cells = row.select('td') if row.name == 'tr' else row.select('div, span, p')
                        text_parts = [c.text.strip() for c in cells if c.text.strip()]
                        
                        if len(text_parts) < 2:
                            continue
                        
                        # Try to extract project name and amount
                        name = text_parts[0]
                        amount_text = ""
                        round_type = ""
                        
                        for part in text_parts[1:]:
                            if '$' in part or 'M' in part:
                                amount_text = part
                            if any(rt in part.lower() for rt in ['seed', 'series', 'round', 'pre-', 'strategic', 'funding']):
                                round_type = part
                        
                        if name and len(name) > 1:
                            # Parse amount
                            amount_usd = 0
                            if amount_text:
                                amount_match = re.search(r'[\$]?\s*([\d,.]+)\s*[Mm]', amount_text)
                                if amount_match:
                                    amount_usd = float(amount_match.group(1).replace(',', '')) * 1_000_000
                            
                            rounds.append({
                                "project_name": name,
                                "raised_usd": amount_usd,
                                "round_type": round_type or "Unknown",
                                "source": "icodrops_vc",
                                "raw_text": " | ".join(text_parts[:5])
                            })
                    except:
                        continue
                break
        
        # Fallback: regex-based extraction from raw HTML
        if not rounds:
            # Look for patterns like "$10M", "Series A", project names near dollar amounts
            pattern = re.compile(r'<[^>]*>([A-Z][a-zA-Z0-9\s\.]+?)</[^>]*>\s*.*?\$\s*([\d,.]+)\s*[Mm]', re.DOTALL)
            matches = pattern.findall(text[:50000])
            for name, amount in matches[:50]:
                name = name.strip()
                if len(name) > 2 and len(name) < 40:
                    rounds.append({
                        "project_name": name,
                        "raised_usd": float(amount.replace(',', '')) * 1_000_000,
                        "round_type": "Funding Round",
                        "source": "icodrops_vc",
                    })
        
        logger.info(f"ICODrops funding: {len(rounds)} rounds parsed")
    except Exception as e:
        logger.error(f"ICODrops funding error: {e}")
    
    return rounds


async def sync_icodrops_full(db, limit=50) -> Dict[str, Any]:
    """Full ICODrops sync — upcoming, active, and funding rounds"""
    now = datetime.now(timezone.utc).isoformat()
    results = {
        "ok": True,
        "source": "icodrops",
        "upcoming": 0,
        "active": 0,
        "funding": 0,
        "errors": []
    }
    
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        # Upcoming ICOs
        try:
            upcoming = await fetch_icodrops_upcoming(client)
            for item in upcoming[:limit]:
                doc = {
                    "id": f"icodrops_upcoming_{item['name'].lower().replace(' ', '_')[:40]}",
                    "source": "icodrops",
                    "name": item["name"],
                    "type": "ico",
                    "status": "upcoming",
                    "category": item.get("category", ""),
                    "date": item.get("date", ""),
                    "raised": item.get("raised", ""),
                    "interest": item.get("interest", ""),
                    "url": item.get("url", ""),
                    "created_at": now,
                    "updated_at": now
                }
                await db.intel_events.update_one({"id": doc["id"]}, {"$set": doc}, upsert=True)
                results["upcoming"] += 1
        except Exception as e:
            results["errors"].append(f"Upcoming: {e}")
        
        # Active ICOs
        try:
            active = await fetch_icodrops_active(client)
            for item in active[:limit]:
                doc = {
                    "id": f"icodrops_active_{item['name'].lower().replace(' ', '_')[:40]}",
                    "source": "icodrops",
                    "name": item["name"],
                    "type": "ico",
                    "status": "active",
                    "url": item.get("url", ""),
                    "created_at": now,
                    "updated_at": now
                }
                await db.intel_events.update_one({"id": doc["id"]}, {"$set": doc}, upsert=True)
                results["active"] += 1
        except Exception as e:
            results["errors"].append(f"Active: {e}")
        
        # Funding Rounds
        try:
            funding = await fetch_icodrops_funding_rounds(client)
            for item in funding[:100]:
                doc = {
                    "id": f"icodrops_funding_{item['project_name'].lower().replace(' ', '_')[:40]}",
                    "source": "icodrops_vc",
                    "project_name": item["project_name"],
                    "project_key": item["project_name"].lower().replace(" ", "-"),
                    "round_type": item.get("round_type", "Unknown"),
                    "raised_usd": item.get("raised_usd", 0),
                    "investors": [],
                    "year": datetime.now().year,
                    "created_at": now,
                    "updated_at": now
                }
                await db.intel_funding.update_one({"id": doc["id"]}, {"$set": doc}, upsert=True)
                
                # Also add to funding_rounds for graph builder
                fr_doc = {**doc}
                fr_doc["id"] = f"icodrops:{item['project_name'].lower().replace(' ', '-')}"
                await db.funding_rounds.update_one({"id": fr_doc["id"]}, {"$set": fr_doc}, upsert=True)
                
                results["funding"] += 1
        except Exception as e:
            results["errors"].append(f"Funding: {e}")
    
    # Update source status
    await db.data_sources.update_one(
        {"id": "icodrops"},
        {"$set": {"last_sync": now, "status": "active", "updated_at": now}, "$inc": {"sync_count": 1}},
        upsert=True
    )
    
    logger.info(f"[ICODrops] Synced: {results['upcoming']} upcoming, {results['active']} active, {results['funding']} funding rounds")
    return results
