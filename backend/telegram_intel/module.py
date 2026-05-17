"""
Telegram Intel Module - Main Entry Point
Version: 1.0.0 (FROZEN)

This is the PUBLIC INTERFACE of the module.
Only methods defined here should be called externally.

SECURITY: DO NOT log session_string under any circumstances.
"""

import logging
from typing import Optional, List, Dict, Any
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from fastapi import APIRouter

from .contracts import TelegramConfig
from .storage import TelegramStorage, ensure_indexes
from .__version__ import VERSION, FROZEN

logger = logging.getLogger(__name__)


class TelegramModule:
    """
    Telegram Intelligence Module - Main Class
    
    This is the ONLY public interface to the module.
    All functionality is accessed through this class.
    
    FROZEN API - Do not add/remove public methods after v1.0.0
    
    SECURITY RULES:
    - session_string is stored ONLY in config (from env)
    - NEVER write to DB, files, or logs
    - NEVER expose in API responses
    """
    
    def __init__(self, config: TelegramConfig):
        """
        Initialize Telegram Module with configuration.
        
        Args:
            config: TelegramConfig with required settings
            
        SECURITY: session_string in config must never be logged or persisted.
        """
        self.config = config
        self._client: Optional[AsyncIOMotorClient] = None
        self._db: Optional[AsyncIOMotorDatabase] = None
        self._storage: Optional[TelegramStorage] = None
        self._router: Optional[APIRouter] = None
        self._started = False
        
        # Service references (lazy loaded)
        self._mtproto = None
        self._scheduler = None
        self._bot = None
        
        # Log init WITHOUT sensitive data
        logger.info(f"TelegramModule initialized (session={'set' if config.session_string else 'not set'})")
    
    # ==========================================
    # VERSION & STATUS (FROZEN)
    # ==========================================
    
    @property
    def version(self) -> str:
        """Get module version"""
        return VERSION
    
    @property
    def frozen(self) -> bool:
        """Check if module is frozen"""
        return FROZEN
    
    def get_version_info(self) -> Dict[str, Any]:
        """
        Get version information.
        
        Returns:
            {"version": "1.0.0", "frozen": true, "module": "telegram-intel"}
        """
        return {
            "version": VERSION,
            "frozen": FROZEN,
            "module": "telegram-intel"
        }
    
    @property
    def router(self) -> APIRouter:
        """Get FastAPI router with all endpoints"""
        if self._router is None:
            self._router = self._create_router()
        return self._router
    
    @property
    def storage(self) -> TelegramStorage:
        """Get storage access layer"""
        if self._storage is None:
            raise RuntimeError("Module not started. Call await module.start() first")
        return self._storage
    
    @property
    def db(self) -> AsyncIOMotorDatabase:
        """Get database instance"""
        if self._db is None:
            raise RuntimeError("Module not started. Call await module.start() first")
        return self._db
    
    # ==========================================
    # LIFECYCLE
    # ==========================================
    
    async def start(self):
        """
        Start the module - connect to database, initialize services.
        Must be called before using the module.
        """
        if self._started:
            return
        
        logger.info(f"Starting Telegram Intel Module v{VERSION}")
        
        # Connect to MongoDB
        self._client = AsyncIOMotorClient(self.config.mongo_uri)
        self._db = self._client[self.config.db_name]
        self._storage = TelegramStorage(self._db)
        
        # Ensure indexes
        await ensure_indexes(self._db)
        
        # Start scheduler if enabled
        if self.config.scheduler_enabled:
            await self._start_scheduler()
        
        self._started = True
        logger.info("Telegram Intel Module started")
    
    async def stop(self):
        """
        Stop the module - cleanup resources.
        Call on application shutdown.
        """
        if not self._started:
            return
        
        logger.info("Stopping Telegram Intel Module")
        
        # Stop scheduler
        if self._scheduler:
            await self._stop_scheduler()
        
        # Disconnect MTProto
        if self._mtproto:
            await self._mtproto.disconnect()
        
        # Close MongoDB
        if self._client:
            self._client.close()
        
        self._started = False
        logger.info("Telegram Intel Module stopped")
    
    # ==========================================
    # PUBLIC API - FEED
    # ==========================================
    
    async def get_feed(
        self,
        actor_id: str = "default",
        page: int = 1,
        limit: int = 50,
        window_days: int = 7,
        language: str = None,
        has_media: bool = None,
        min_views: int = None,
        sort_by: str = "date",
    ) -> Dict[str, Any]:
        """Get feed posts for actor with filters"""
        from .services.feed import get_feed_v2
        return await get_feed_v2(
            self._db, 
            actor_id=actor_id,
            page=page,
            limit=limit,
            window_days=window_days,
            language=language,
            has_media=has_media,
            min_views=min_views,
            sort_by=sort_by,
        )
    
    async def get_feed_stats(self, actor_id: str = "default", hours: int = 24) -> Dict[str, Any]:
        """Get feed statistics"""
        from .services.feed import get_feed_stats
        return await get_feed_stats(self._db, actor_id, hours)
    
    async def get_feed_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get AI-generated feed summary"""
        from .services.feed import get_feed_summary
        return await get_feed_summary(self._db, hours, self.config.llm_api_key, actor_id="default")
    
    # ==========================================
    # PUBLIC API - CHANNEL
    # ==========================================
    
    async def get_channel(self, username: str) -> Dict[str, Any]:
        """
        Get full channel data.
        
        Args:
            username: Channel username (without @)
            
        Returns:
            ChannelResponse dict
        """
        from .services.channel import get_channel_full
        return await get_channel_full(self._db, username)
    
    async def get_channels(
        self,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "fomoScore",
        q: str = None,
        language: str = None
    ) -> Dict[str, Any]:
        """Get list of monitored channels"""
        from .services.channel import get_channel_list
        return await get_channel_list(self._db, limit, offset, sort_by, q, language)
    
    # ==========================================
    # PUBLIC API - WATCHLIST
    # ==========================================
    
    async def get_watchlist(self, actor_id: str = "default") -> Dict[str, Any]:
        """Get actor's watchlist"""
        from .services.watchlist import get_watchlist
        return await get_watchlist(self._db, actor_id)
    
    async def add_to_watchlist(self, username: str, actor_id: str = "default") -> Dict[str, Any]:
        """Add channel to watchlist"""
        from .services.watchlist import add_to_watchlist
        return await add_to_watchlist(self._db, username, actor_id)
    
    async def remove_from_watchlist(self, username: str, actor_id: str = "default") -> Dict[str, Any]:
        """Remove channel from watchlist"""
        from .services.watchlist import remove_from_watchlist
        return await remove_from_watchlist(self._db, username, actor_id)
    
    async def clear_watchlist(self, actor_id: str = "default") -> Dict[str, Any]:
        """Remove all channels from watchlist"""
        from .services.watchlist import clear_watchlist
        return await clear_watchlist(self._db, actor_id)
    
    # ==========================================
    # PUBLIC API - ALERTS
    # ==========================================
    
    async def get_alerts(self, actor_id: str = "default", limit: int = 50) -> Dict[str, Any]:
        """Get actor's alerts"""
        from .services.alerts import get_alerts
        return await get_alerts(self._db, actor_id, limit)
    
    async def dispatch_alerts(self):
        """Dispatch pending alerts to linked users"""
        from .services.alerts import dispatch_alerts
        return await dispatch_alerts(self._db, self.config.bot_token)
    
    # ==========================================
    # PUBLIC API - DIGEST
    # ==========================================
    
    async def run_digest(self, actor_id: str = "default") -> Dict[str, Any]:
        """Generate and optionally deliver digest"""
        from .services.digest import run_digest
        return await run_digest(
            self._db,
            actor_id,
            llm_key=self.config.llm_api_key,
            bot_token=self.config.bot_token
        )
    
    # ==========================================
    # PUBLIC API - BOT
    # ==========================================
    
    async def get_bot_status(self) -> Dict[str, Any]:
        """Get bot status and delivery stats"""
        from .services.bot import get_bot_status
        return await get_bot_status(self._db, self.config.bot_token)
    
    # ==========================================
    # PUBLIC API - CHANNEL SEARCH & ADD
    # ==========================================
    
    async def search_telegram_channel(self, username: str) -> Dict[str, Any]:
        """Search for a channel on Telegram"""
        from .services.channel_add import search_channel_on_telegram
        return await search_channel_on_telegram(self._db, username)
    
    async def add_channel_from_telegram(self, username: str) -> Dict[str, Any]:
        """Add a channel from Telegram to tracking"""
        from .services.channel_add import add_channel_from_telegram
        return await add_channel_from_telegram(self._db, username)
    
    async def analyze_channel_product(self, username: str) -> Dict[str, Any]:
        """AI analysis of channel's product/monetization"""
        from .services.product_analysis import analyze_channel_product
        return await analyze_channel_product(self._db, username)
    
    # ==========================================
    # INTERNAL
    # ==========================================
    
    def _create_router(self) -> APIRouter:
        """Create FastAPI router with all endpoints"""
        from .api.routes import create_router
        return create_router(self)
    
    async def _start_scheduler(self):
        """Start background scheduler"""
        from .workers.scheduler import start_scheduler
        self._scheduler = await start_scheduler(
            self._db,
            interval_minutes=self.config.scheduler_interval_minutes
        )
    
    async def _stop_scheduler(self):
        """Stop background scheduler"""
        from .workers.scheduler import stop_scheduler
        if self._scheduler:
            await stop_scheduler(self._scheduler)
            self._scheduler = None
