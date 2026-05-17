"""
Auto-Sync Scheduler
===================

Automated scheduler for syncing all active data sources.
Runs parsers on a schedule (hourly by default).

Usage:
    from modules.sync_scheduler import AutoSyncScheduler
    scheduler = AutoSyncScheduler(db)
    await scheduler.start()
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)


class AutoSyncScheduler:
    """
    Auto-Sync Scheduler for data sources.
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.running = False
        self.sync_interval_hours = 1
        self.sync_tasks = []
        
        # Parser mapping
        self.parsers = {
            "coingecko": self._sync_coingecko,
            "cryptorank": self._sync_cryptorank,
            "defillama": self._sync_defillama,
            "tokenunlocks": self._sync_tokenunlocks,
            "dropstab": self._sync_dropstab,
            "dropsearn": self._sync_dropsearn,
            "messari": self._sync_messari,
            "rootdata": self._sync_rootdata,
            "icodrops": self._sync_icodrops,
            "dappradar": self._sync_dappradar,
            "cointelegraph": self._sync_cointelegraph,
            "theblock": self._sync_theblock,
            "coindesk": self._sync_coindesk,
            "airdropalert": self._sync_airdropalert,
            "coinmarketcap": self._sync_coinmarketcap,
            "crunchbase": self._sync_crunchbase,
            "incrypted": self._sync_incrypted,
        }
    
    async def start(self):
        """Start the auto-sync scheduler"""
        if self.running:
            logger.warning("[Scheduler] Already running")
            return
        
        self.running = True
        logger.info("[Scheduler] Starting auto-sync scheduler")
        
        # Run initial sync
        await self.sync_all_active()
        
        # Start background loop
        asyncio.create_task(self._scheduler_loop())
    
    async def stop(self):
        """Stop the scheduler"""
        self.running = False
        logger.info("[Scheduler] Stopped")
    
    async def _scheduler_loop(self):
        """Main scheduler loop"""
        while self.running:
            try:
                # Wait for next interval
                await asyncio.sleep(self.sync_interval_hours * 3600)
                
                if not self.running:
                    break
                
                logger.info("[Scheduler] Running scheduled sync...")
                await self.sync_all_active()
                
            except Exception as e:
                logger.error(f"[Scheduler] Loop error: {e}")
    
    async def sync_all_active(self) -> Dict[str, Any]:
        """Sync all active data sources"""
        results = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "sources_synced": 0,
            "errors": [],
            "details": {}
        }
        
        # Get active data sources from DB
        cursor = self.db.data_sources.find({"status": "active"})
        active_sources = await cursor.to_list(100)
        
        # Also include sources with parsers defined
        all_source_ids = set(s.get("id") for s in active_sources)
        
        logger.info(f"[Scheduler] Syncing {len(active_sources)} active sources...")
        
        for source in active_sources:
            source_id = source.get("id")
            
            if source_id in self.parsers:
                try:
                    sync_result = await self.parsers[source_id]()
                    results["details"][source_id] = sync_result
                    results["sources_synced"] += 1
                    
                except Exception as e:
                    error_msg = f"{source_id}: {e}"
                    results["errors"].append(error_msg)
                    logger.error(f"[Scheduler] Sync error - {error_msg}")
        
        logger.info(f"[Scheduler] Sync complete: {results['sources_synced']} sources")
        
        # Store sync log
        await self.db.sync_logs.insert_one({
            "type": "auto_sync",
            "timestamp": results["ts"],
            "sources_synced": results["sources_synced"],
            "errors": results["errors"]
        })
        
        return results
    
    async def sync_source(self, source_id: str) -> Dict[str, Any]:
        """Sync a specific data source"""
        if source_id not in self.parsers:
            return {"ok": False, "error": f"No parser for {source_id}"}
        
        try:
            return await self.parsers[source_id]()
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    # ═══════════════════════════════════════════════════════════════
    # PARSER WRAPPERS
    # ═══════════════════════════════════════════════════════════════
    
    async def _sync_coingecko(self) -> Dict:
        from modules.parsers.parser_coingecko import sync_coingecko_data
        return await sync_coingecko_data(self.db)
    
    async def _sync_cryptorank(self) -> Dict:
        from modules.parsers.parser_cryptorank import sync_cryptorank_data
        return await sync_cryptorank_data(self.db)
    
    async def _sync_defillama(self) -> Dict:
        from modules.parsers.parser_defillama import sync_defillama_data
        return await sync_defillama_data(self.db)
    
    async def _sync_tokenunlocks(self) -> Dict:
        from modules.parsers.parser_tokenunlocks import sync_tokenunlocks_data
        return await sync_tokenunlocks_data(self.db)
    
    async def _sync_dropstab(self) -> Dict:
        from modules.parsers.parser_activities import sync_activities_data
        return await sync_activities_data(self.db)
    
    async def _sync_dropsearn(self) -> Dict:
        # DropsEarn is handled by same activities parser
        from modules.parsers.parser_activities import sync_activities_data
        return await sync_activities_data(self.db)
    
    async def _sync_messari(self) -> Dict:
        from modules.parsers.parser_messari import sync_messari_data
        return await sync_messari_data(self.db)
    
    async def _sync_rootdata(self) -> Dict:
        from modules.parsers.parser_rootdata import sync_rootdata_data
        return await sync_rootdata_data(self.db)
    
    async def _sync_icodrops(self) -> Dict:
        from modules.parsers.parser_icodrops import sync_icodrops_data
        return await sync_icodrops_data(self.db)
    
    async def _sync_dappradar(self) -> Dict:
        from modules.parsers.parser_dappradar import sync_dappradar_data
        return await sync_dappradar_data(self.db)
    
    async def _sync_cointelegraph(self) -> Dict:
        from modules.parsers.parser_news import sync_cointelegraph_data
        return await sync_cointelegraph_data(self.db)
    
    async def _sync_theblock(self) -> Dict:
        from modules.parsers.parser_news import sync_theblock_data
        return await sync_theblock_data(self.db)
    
    async def _sync_coindesk(self) -> Dict:
        from modules.parsers.parser_news import sync_coindesk_data
        return await sync_coindesk_data(self.db)
    
    async def _sync_airdropalert(self) -> Dict:
        from modules.parsers.parser_airdropalert import sync_airdropalert_data
        return await sync_airdropalert_data(self.db)
    
    async def _sync_coinmarketcap(self) -> Dict:
        from modules.parsers.parser_coinmarketcap import sync_coinmarketcap_data
        return await sync_coinmarketcap_data(self.db)
    
    async def _sync_crunchbase(self) -> Dict:
        from modules.parsers.parser_crunchbase import sync_crunchbase_data
        return await sync_crunchbase_data(self.db)
    
    async def _sync_incrypted(self) -> Dict:
        from modules.parsers.parser_incrypted import sync_incrypted_data
        return await sync_incrypted_data(self.db)


# Singleton instance
_scheduler: Optional[AutoSyncScheduler] = None


def get_sync_scheduler(db: AsyncIOMotorDatabase = None) -> AutoSyncScheduler:
    """Get or create sync scheduler instance"""
    global _scheduler
    if db is not None:
        _scheduler = AutoSyncScheduler(db)
    return _scheduler
