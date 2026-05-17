"""
Webhook Event Emitter Service
=============================

Integrates with parsers and news intelligence to emit webhook events
when new data is detected.
"""

import logging
import asyncio
from typing import Dict, Any, Optional, Set
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Track emitted events to avoid duplicates
_emitted_funding_ids: Set[str] = set()
_emitted_unlock_ids: Set[str] = set()
_emitted_news_ids: Set[str] = set()


class WebhookEventEmitter:
    """
    Emits webhook events when new data is detected.
    
    Usage:
        emitter = WebhookEventEmitter(db)
        await emitter.check_new_funding()
        await emitter.check_new_unlocks()
        await emitter.check_new_news()
    """
    
    def __init__(self, db):
        self.db = db
        self._initialized = False
        
    async def _init_tracking(self):
        """Initialize tracking sets from database on first run."""
        if self._initialized:
            return
            
        global _emitted_funding_ids, _emitted_unlock_ids, _emitted_news_ids
        
        # Load existing IDs to avoid re-emitting on restart
        async for doc in self.db.intel_funding.find({}, {"id": 1}):
            _emitted_funding_ids.add(doc.get("id"))
        
        async for doc in self.db.token_unlocks.find({}, {"id": 1}):
            _emitted_unlock_ids.add(doc.get("id"))
            
        async for doc in self.db.news_events.find({}, {"id": 1}):
            _emitted_news_ids.add(doc.get("id"))
        
        self._initialized = True
        logger.info(f"[WebhookEmitter] Initialized: {len(_emitted_funding_ids)} funding, {len(_emitted_unlock_ids)} unlocks, {len(_emitted_news_ids)} news")
    
    async def emit_funding_event(self, funding_data: Dict[str, Any]):
        """Emit webhook for new funding round."""
        from modules.webhooks.routes import emit_funding_event
        
        funding_id = funding_data.get("id")
        if not funding_id or funding_id in _emitted_funding_ids:
            return False
        
        try:
            # Prepare webhook payload
            payload = {
                "funding_id": funding_id,
                "project_slug": funding_data.get("project_slug") or funding_data.get("slug"),
                "project_name": funding_data.get("project_name") or funding_data.get("name"),
                "stage": funding_data.get("stage") or funding_data.get("round_type"),
                "amount": funding_data.get("amount") or funding_data.get("raised"),
                "currency": funding_data.get("currency", "USD"),
                "valuation": funding_data.get("valuation"),
                "lead_investors": funding_data.get("lead_investors", []),
                "all_investors": funding_data.get("investors", []),
                "announced_at": funding_data.get("date") or funding_data.get("announced_at"),
                "source": funding_data.get("source", "parser")
            }
            
            await emit_funding_event(payload)
            _emitted_funding_ids.add(funding_id)
            
            logger.info(f"[WebhookEmitter] Emitted funding.round: {payload.get('project_name')} - ${payload.get('amount', 0):,}")
            return True
            
        except Exception as e:
            logger.error(f"[WebhookEmitter] Error emitting funding event: {e}")
            return False
    
    async def emit_unlock_event(self, unlock_data: Dict[str, Any]):
        """Emit webhook for token unlock."""
        from modules.webhooks.routes import emit_unlock_event
        
        unlock_id = unlock_data.get("id")
        if not unlock_id or unlock_id in _emitted_unlock_ids:
            return False
        
        try:
            payload = {
                "unlock_id": unlock_id,
                "project": unlock_data.get("project") or unlock_data.get("project_slug"),
                "token": unlock_data.get("token") or unlock_data.get("symbol"),
                "unlock_date": unlock_data.get("unlock_date") or unlock_data.get("date"),
                "amount": unlock_data.get("amount") or unlock_data.get("tokens_amount"),
                "value_usd": unlock_data.get("value_usd") or unlock_data.get("usd_value"),
                "percent_of_supply": unlock_data.get("percent_of_supply"),
                "unlock_type": unlock_data.get("type") or unlock_data.get("category"),
                "source": unlock_data.get("source", "parser")
            }
            
            await emit_unlock_event(payload)
            _emitted_unlock_ids.add(unlock_id)
            
            logger.info(f"[WebhookEmitter] Emitted token.unlock: {payload.get('token')} - ${payload.get('value_usd', 0):,}")
            return True
            
        except Exception as e:
            logger.error(f"[WebhookEmitter] Error emitting unlock event: {e}")
            return False
    
    async def emit_news_event(self, news_data: Dict[str, Any], breaking: bool = False):
        """Emit webhook for news event."""
        from modules.webhooks.routes import emit_news_event
        
        news_id = news_data.get("id")
        if not news_id or news_id in _emitted_news_ids:
            return False
        
        # Only emit for high importance news (> 0.7) or breaking
        importance = news_data.get("importance_score", 0)
        if not breaking and importance < 0.7:
            return False
        
        try:
            payload = {
                "event_id": news_id,
                "headline": news_data.get("headline"),
                "headline_ru": news_data.get("headline_ru"),
                "summary": news_data.get("summary"),
                "event_type": news_data.get("event_type", "news"),
                "importance_score": importance,
                "primary_assets": news_data.get("primary_assets", []),
                "sources": news_data.get("source_names", []),
                "sources_count": news_data.get("sources_count", 1),
                "sentiment": news_data.get("sentiment"),
                "language": news_data.get("language", "en"),
                "first_seen": news_data.get("first_seen") or news_data.get("created_at")
            }
            
            await emit_news_event(payload, breaking=breaking)
            _emitted_news_ids.add(news_id)
            
            event_type = "news.breaking" if breaking else "news.important"
            logger.info(f"[WebhookEmitter] Emitted {event_type}: {payload.get('headline', '')[:50]}...")
            return True
            
        except Exception as e:
            logger.error(f"[WebhookEmitter] Error emitting news event: {e}")
            return False
    
    async def check_new_funding(self, since_minutes: int = 30) -> Dict[str, int]:
        """
        Check for new funding rounds and emit webhooks.
        
        Args:
            since_minutes: Check for funding rounds added in last N minutes
            
        Returns:
            Dict with counts of emitted events
        """
        await self._init_tracking()
        
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=since_minutes)
        
        emitted = 0
        cursor = self.db.intel_funding.find({
            "$or": [
                {"created_at": {"$gte": cutoff.isoformat()}},
                {"updated_at": {"$gte": cutoff.isoformat()}}
            ]
        })
        
        async for doc in cursor:
            doc_id = doc.get("id")
            if doc_id and doc_id not in _emitted_funding_ids:
                if await self.emit_funding_event(doc):
                    emitted += 1
        
        return {"funding_emitted": emitted}
    
    async def check_new_unlocks(self, days_ahead: int = 7) -> Dict[str, int]:
        """
        Check for upcoming token unlocks and emit webhooks.
        
        Args:
            days_ahead: Emit for unlocks within N days
            
        Returns:
            Dict with counts of emitted events
        """
        await self._init_tracking()
        
        from datetime import timedelta
        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(days=days_ahead)
        
        emitted = 0
        cursor = self.db.token_unlocks.find({
            "unlock_date": {
                "$gte": now.isoformat(),
                "$lte": cutoff.isoformat()
            }
        })
        
        async for doc in cursor:
            doc_id = doc.get("id")
            if doc_id and doc_id not in _emitted_unlock_ids:
                if await self.emit_unlock_event(doc):
                    emitted += 1
        
        return {"unlocks_emitted": emitted}
    
    async def check_new_news(self, since_minutes: int = 30) -> Dict[str, int]:
        """
        Check for new important news and emit webhooks.
        
        Args:
            since_minutes: Check for news added in last N minutes
            
        Returns:
            Dict with counts of emitted events
        """
        await self._init_tracking()
        
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=since_minutes)
        
        emitted_breaking = 0
        emitted_important = 0
        
        cursor = self.db.news_events.find({
            "created_at": {"$gte": cutoff.isoformat()},
            "importance_score": {"$gte": 0.7}
        }).sort("importance_score", -1)
        
        async for doc in cursor:
            doc_id = doc.get("id")
            if doc_id and doc_id not in _emitted_news_ids:
                importance = doc.get("importance_score", 0)
                breaking = importance >= 0.9
                
                if await self.emit_news_event(doc, breaking=breaking):
                    if breaking:
                        emitted_breaking += 1
                    else:
                        emitted_important += 1
        
        return {
            "breaking_emitted": emitted_breaking,
            "important_emitted": emitted_important
        }
    
    async def run_all_checks(self) -> Dict[str, Any]:
        """
        Run all webhook checks.
        
        Returns:
            Combined results from all checks
        """
        results = {}
        
        try:
            funding = await self.check_new_funding()
            results.update(funding)
        except Exception as e:
            logger.error(f"[WebhookEmitter] Funding check error: {e}")
            results["funding_error"] = str(e)
        
        try:
            unlocks = await self.check_new_unlocks()
            results.update(unlocks)
        except Exception as e:
            logger.error(f"[WebhookEmitter] Unlocks check error: {e}")
            results["unlocks_error"] = str(e)
        
        try:
            news = await self.check_new_news()
            results.update(news)
        except Exception as e:
            logger.error(f"[WebhookEmitter] News check error: {e}")
            results["news_error"] = str(e)
        
        results["checked_at"] = datetime.now(timezone.utc).isoformat()
        return results


# Global instance
_emitter: Optional[WebhookEventEmitter] = None

def get_emitter(db) -> WebhookEventEmitter:
    """Get or create webhook emitter instance."""
    global _emitter
    if _emitter is None:
        _emitter = WebhookEventEmitter(db)
    return _emitter


async def emit_on_funding_insert(db, funding_data: Dict[str, Any]):
    """
    Call this after inserting a new funding round.
    
    Usage in parser:
        await db.intel_funding.update_one(...)
        await emit_on_funding_insert(db, funding_data)
    """
    emitter = get_emitter(db)
    await emitter.emit_funding_event(funding_data)


async def emit_on_unlock_insert(db, unlock_data: Dict[str, Any]):
    """
    Call this after inserting a new token unlock.
    """
    emitter = get_emitter(db)
    await emitter.emit_unlock_event(unlock_data)


async def emit_on_news_insert(db, news_data: Dict[str, Any]):
    """
    Call this after inserting a new news event.
    Only emits if importance_score >= 0.7
    """
    emitter = get_emitter(db)
    importance = news_data.get("importance_score", 0)
    breaking = importance >= 0.9
    await emitter.emit_news_event(news_data, breaking=breaking)
