"""
AirdropAlert Parser
===================

Parser for AirdropAlert.com - Airdrop aggregator.

TIER 3 source - sync every 30 min
"""

import httpx
import logging
from typing import Dict, List, Any
from datetime import datetime, timezone
from bs4 import BeautifulSoup

from modules.intel.parser_validation import ParserValidator

logger = logging.getLogger(__name__)

AIRDROPALERT_URL = "https://airdropalert.com"

# Parser validator for field validation
_validator = ParserValidator("airdropalert")


async def fetch_airdropalert_airdrops(limit: int = 50) -> List[Dict]:
    """Fetch airdrops from AirdropAlert"""
    airdrops = []
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{AIRDROPALERT_URL}/new-airdrops",
                headers={"User-Agent": "Mozilla/5.0"}
            )
            
            if response.status_code != 200:
                logger.warning(f"AirdropAlert returned {response.status_code}")
                return airdrops
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Parse airdrop cards
            cards = soup.select('.airdrop-card, .airdrop-item, article')
            
            for card in cards[:limit]:
                try:
                    title_el = card.select_one('h2, h3, .title, .name')
                    title = title_el.text.strip() if title_el else "Unknown"
                    
                    link_el = card.select_one('a[href]')
                    link = link_el.get('href', '') if link_el else ""
                    
                    desc_el = card.select_one('.description, p')
                    desc = desc_el.text.strip() if desc_el else ""
                    
                    value_el = card.select_one('.value, .reward')
                    value = value_el.text.strip() if value_el else ""
                    
                    airdrops.append({
                        "name": title,
                        "url": link if link.startswith('http') else f"{AIRDROPALERT_URL}{link}",
                        "description": desc[:300],
                        "value": value
                    })
                except Exception as e:
                    logger.debug(f"Error parsing airdrop card: {e}")
                    continue
                    
    except Exception as e:
        logger.error(f"AirdropAlert fetch error: {e}")
    
    return airdrops


async def sync_airdropalert_data(db, limit: int = 50) -> Dict[str, Any]:
    """Sync AirdropAlert data to MongoDB"""
    now = datetime.now(timezone.utc).isoformat()
    results = {
        "ok": True,
        "source": "airdropalert",
        "airdrops": 0,
        "errors": []
    }
    
    try:
        airdrops = await fetch_airdropalert_airdrops(limit)
        
        for item in airdrops:
            doc = {
                "id": f"airdropalert_{item['name'].lower().replace(' ', '_')[:30]}",
                "source": "airdropalert",
                "type": "airdrop",
                "title": item["name"],
                "project_name": item["name"],
                "description": item.get("description", ""),
                "reward": item.get("value", ""),
                "url": item.get("url", ""),
                "status": "active",
                "category": "airdrop",
                "airdrop_campaigns": item["name"],  # Field we can provide
                "created_at": now,
                "updated_at": now
            }
            
            # Validate data before saving
            validated_doc = _validator.filter_data(doc)
            
            await db.crypto_activities.update_one(
                {"id": validated_doc["id"]},
                {"$set": validated_doc},
                upsert=True
            )
            results["airdrops"] += 1
    except Exception as e:
        results["errors"].append(str(e))
    
    # Update data source status
    await db.data_sources.update_one(
        {"id": "airdropalert"},
        {
            "$set": {
                "last_sync": now,
                "status": "active",
                "updated_at": now
            },
            "$inc": {"sync_count": 1}
        }
    )
    
    logger.info(f"[AirdropAlert] Synced: {results['airdrops']} airdrops")
    return results
