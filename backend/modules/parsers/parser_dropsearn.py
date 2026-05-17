"""
DropsEarn Parser
================

Parser for DropsEarn.com - Airdrop campaigns and ecosystem activities.
Data types: airdrops, campaigns, testnets, quests

TIER 3 source - sync every 30 min
"""

import httpx
import logging
from typing import Dict, List, Any
from datetime import datetime, timezone
from bs4 import BeautifulSoup
import re

from modules.intel.parser_validation import ParserValidator, validate_parser_output

logger = logging.getLogger(__name__)

DROPSEARN_URL = "https://dropsearn.com"


class DropsEarnParser:
    """DropsEarn activities parser with validation"""
    
    source_id = "dropsearn"
    
    def __init__(self, db):
        self.db = db
        self.validator = ParserValidator(self.source_id)
    
    async def fetch_airdrops(self, limit: int = 50) -> List[Dict]:
        """Fetch active airdrops from DropsEarn"""
        airdrops = []
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{DROPSEARN_URL}/airdrops",
                    headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
                )
                
                if response.status_code != 200:
                    logger.warning(f"DropsEarn returned {response.status_code}")
                    return airdrops
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Parse airdrop cards - adjust selectors based on site structure
                cards = soup.select('.airdrop-card, .card, [class*="airdrop"]')[:limit]
                
                for card in cards:
                    try:
                        name_el = card.select_one('h2, h3, .title, .name')
                        name = name_el.text.strip() if name_el else None
                        if not name:
                            continue
                        
                        link_el = card.select_one('a[href]')
                        link = link_el.get('href', '') if link_el else ''
                        
                        desc_el = card.select_one('p, .description, .desc')
                        description = desc_el.text.strip()[:200] if desc_el else ""
                        
                        # Get status/type
                        status_el = card.select_one('.status, .badge, .tag')
                        status = status_el.text.strip().lower() if status_el else "active"
                        
                        airdrops.append({
                            "name": name,
                            "description": description,
                            "url": link if link.startswith('http') else f"{DROPSEARN_URL}{link}",
                            "status": status,
                            "type": "airdrop"
                        })
                    except Exception as e:
                        logger.debug(f"Error parsing card: {e}")
                        continue
                        
        except Exception as e:
            logger.error(f"DropsEarn fetch error: {e}")
        
        return airdrops
    
    async def fetch_testnets(self, limit: int = 30) -> List[Dict]:
        """Fetch active testnets from DropsEarn"""
        testnets = []
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{DROPSEARN_URL}/testnets",
                    headers={"User-Agent": "Mozilla/5.0"}
                )
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    cards = soup.select('.testnet-card, .card')[:limit]
                    
                    for card in cards:
                        try:
                            name_el = card.select_one('h2, h3, .title')
                            name = name_el.text.strip() if name_el else None
                            if not name:
                                continue
                            
                            testnets.append({
                                "name": name,
                                "type": "testnet",
                                "status": "active"
                            })
                        except:
                            continue
        except Exception as e:
            logger.error(f"DropsEarn testnets error: {e}")
        
        return testnets
    
    async def sync(self, limit: int = 50) -> Dict[str, Any]:
        """Sync DropsEarn data to MongoDB with validation"""
        now = datetime.now(timezone.utc).isoformat()
        results = {
            "ok": True,
            "source": self.source_id,
            "airdrops": 0,
            "testnets": 0,
            "validation_stats": {},
            "errors": []
        }
        
        # Sync airdrops
        try:
            airdrops = await self.fetch_airdrops(limit)
            for item in airdrops:
                # Validate data before saving
                doc = {
                    "id": f"dropsearn_{item['name'].lower().replace(' ', '_')}",
                    "source": self.source_id,
                    "name": item["name"],
                    "type": item.get("type", "airdrop"),
                    "status": item.get("status", "active"),
                    "description": item.get("description", ""),
                    "url": item.get("url", ""),
                    "airdrop_campaigns": item["name"],  # Field we own
                    "ecosystem_activities": item.get("description", ""),
                    "created_at": now,
                    "updated_at": now
                }
                
                # Apply validation - removes forbidden fields
                validated_doc = self.validator.filter_data(doc)
                
                await self.db.crypto_activities.update_one(
                    {"id": validated_doc["id"]},
                    {"$set": validated_doc},
                    upsert=True
                )
                results["airdrops"] += 1
        except Exception as e:
            results["errors"].append(f"Airdrops sync error: {e}")
        
        # Sync testnets
        try:
            testnets = await self.fetch_testnets(30)
            for item in testnets:
                doc = {
                    "id": f"dropsearn_testnet_{item['name'].lower().replace(' ', '_')}",
                    "source": self.source_id,
                    "name": item["name"],
                    "type": "testnet",
                    "status": item.get("status", "active"),
                    "created_at": now,
                    "updated_at": now
                }
                
                validated_doc = self.validator.filter_data(doc)
                
                await self.db.crypto_activities.update_one(
                    {"id": validated_doc["id"]},
                    {"$set": validated_doc},
                    upsert=True
                )
                results["testnets"] += 1
        except Exception as e:
            results["errors"].append(f"Testnets sync error: {e}")
        
        # Update data source status
        await self.db.data_sources.update_one(
            {"id": self.source_id},
            {
                "$set": {
                    "last_sync": now,
                    "status": "active",
                    "updated_at": now
                },
                "$inc": {"sync_count": 1}
            }
        )
        
        # Add validation stats
        results["validation_stats"] = self.validator.get_stats()
        
        logger.info(f"[DropsEarn] Synced: {results['airdrops']} airdrops, {results['testnets']} testnets")
        return results


async def sync_dropsearn_data(db, limit: int = 50) -> Dict[str, Any]:
    """Sync DropsEarn data - entry point for scheduler"""
    parser = DropsEarnParser(db)
    return await parser.sync(limit)
