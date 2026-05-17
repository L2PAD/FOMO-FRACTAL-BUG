"""
ICO Drops Parser
================

Parser for ICODrops.com - ICO and token sale calendar.
Data types: ico_calendar, token_sales, launchpads

Note: ICO Drops doesn't have public API, uses web scraping.
"""

import httpx
import logging
from typing import Dict, List, Any
from datetime import datetime, timezone
from bs4 import BeautifulSoup
import re

logger = logging.getLogger(__name__)

ICODROPS_URL = "https://icodrops.com"


async def fetch_icodrops_upcoming() -> List[Dict]:
    """Fetch upcoming ICOs from ICODrops"""
    icos = []
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{ICODROPS_URL}/upcoming-ico/",
                headers={"User-Agent": "Mozilla/5.0"}
            )
            
            if response.status_code != 200:
                logger.warning(f"ICODrops returned {response.status_code}")
                return icos
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Parse ICO cards
            cards = soup.select('.a_ico')
            
            for card in cards[:50]:
                try:
                    name_el = card.select_one('.ico-row h3 a')
                    name = name_el.text.strip() if name_el else "Unknown"
                    link = name_el.get('href', '') if name_el else ""
                    
                    # Get category/tags
                    category_el = card.select_one('.categ_type')
                    category = category_el.text.strip() if category_el else ""
                    
                    # Get dates
                    date_el = card.select_one('.date')
                    date_text = date_el.text.strip() if date_el else ""
                    
                    # Get raised amount
                    raised_el = card.select_one('.funds-raised')
                    raised = raised_el.text.strip() if raised_el else ""
                    
                    # Get interest score
                    interest_el = card.select_one('.interest')
                    interest = interest_el.text.strip() if interest_el else ""
                    
                    icos.append({
                        "name": name,
                        "url": f"{ICODROPS_URL}{link}" if link.startswith('/') else link,
                        "category": category,
                        "date": date_text,
                        "raised": raised,
                        "interest": interest
                    })
                except Exception as e:
                    logger.debug(f"Error parsing ICO card: {e}")
                    continue
                    
    except Exception as e:
        logger.error(f"ICODrops fetch error: {e}")
    
    return icos


async def fetch_icodrops_ended() -> List[Dict]:
    """Fetch ended ICOs from ICODrops"""
    icos = []
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{ICODROPS_URL}/ico-stats/",
                headers={"User-Agent": "Mozilla/5.0"}
            )
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                cards = soup.select('.a_ico')
                
                for card in cards[:30]:
                    try:
                        name_el = card.select_one('.ico-row h3 a')
                        name = name_el.text.strip() if name_el else "Unknown"
                        
                        roi_el = card.select_one('.roi')
                        roi = roi_el.text.strip() if roi_el else ""
                        
                        icos.append({
                            "name": name,
                            "roi": roi,
                            "status": "ended"
                        })
                    except:
                        continue
    except Exception as e:
        logger.error(f"ICODrops ended fetch error: {e}")
    
    return icos


async def sync_icodrops_data(db, limit: int = 50) -> Dict[str, Any]:
    """
    Sync ICODrops data to MongoDB.
    """
    now = datetime.now(timezone.utc).isoformat()
    results = {
        "ok": True,
        "source": "icodrops",
        "upcoming": 0,
        "ended": 0,
        "errors": []
    }
    
    # Sync upcoming ICOs
    try:
        upcoming = await fetch_icodrops_upcoming()
        for item in upcoming[:limit]:
            doc = {
                "id": f"icodrops_{item['name'].lower().replace(' ', '_')}",
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
            
            await db.intel_events.update_one(
                {"id": doc["id"]},
                {"$set": doc},
                upsert=True
            )
            results["upcoming"] += 1
    except Exception as e:
        results["errors"].append(f"Upcoming sync error: {e}")
    
    # Update data source status
    await db.data_sources.update_one(
        {"id": "icodrops"},
        {
            "$set": {
                "last_sync": now,
                "status": "active",
                "updated_at": now
            },
            "$inc": {"sync_count": 1}
        }
    )
    
    logger.info(f"[ICODrops] Synced: {results['upcoming']} upcoming ICOs")
    return results
