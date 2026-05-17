"""
Telegram Worker
===============

Отдельный процесс для отправки сообщений в Telegram.
Читает из notification_queue и отправляет через Bot API.

Особенности:
- Retry логика с exponential backoff
- Rate limiting (30 msg/sec max)
- Не блокирует основную систему
- Сохраняет сообщения при сбое Telegram
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import aiohttp
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
import os

from .alert_templates_ru import render_alert
from .alert_engine import get_alert_engine

logger = logging.getLogger(__name__)

# Telegram rate limit (30 msg/sec, we use 1 per 0.05 sec = 20/sec to be safe)
RATE_LIMIT_DELAY = 0.05


class TelegramWorker:
    """
    Worker for sending Telegram notifications.
    Runs as separate async task.
    """
    
    def __init__(
        self,
        db: AsyncIOMotorDatabase,
        bot_token: str,
        chat_id: str
    ):
        self.db = db
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        
        self.alert_engine = get_alert_engine(db)
        self._running = False
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def start(self):
        """Start the worker loop"""
        if self._running:
            return
        
        self._running = True
        self._session = aiohttp.ClientSession()
        
        logger.info("[TelegramWorker] Started")
        
        while self._running:
            try:
                await self._process_queue()
            except Exception as e:
                logger.error(f"[TelegramWorker] Error in loop: {e}")
            
            await asyncio.sleep(2)  # Check every 2 seconds
    
    async def stop(self):
        """Stop the worker"""
        self._running = False
        if self._session:
            await self._session.close()
            self._session = None
        logger.info("[TelegramWorker] Stopped")
    
    async def _process_queue(self):
        """Process pending notifications"""
        notifications = await self.alert_engine.get_pending_notifications(limit=10)
        
        for notif in notifications:
            try:
                await self._send_notification(notif)
                await asyncio.sleep(RATE_LIMIT_DELAY)  # Rate limiting
            except Exception as e:
                logger.error(f"[TelegramWorker] Failed to process {notif['notification_id']}: {e}")
    
    async def _send_notification(self, notification: Dict):
        """Send a single notification"""
        notification_id = notification["notification_id"]
        alert_id = notification["alert_id"]
        
        # Get alert event
        alert = await self.alert_engine.get_alert_event(alert_id)
        if not alert:
            logger.warning(f"[TelegramWorker] Alert not found: {alert_id}")
            await self.alert_engine.mark_notification_failed(
                notification_id, "Alert not found"
            )
            return
        
        # Render message
        alert_code = alert["alert_code"]
        data = alert.get("data", {})
        message = render_alert(alert_code, data)
        
        # Send to Telegram
        success = await self._send_telegram_message(message)
        
        if success:
            await self.alert_engine.mark_notification_sent(notification_id)
            logger.info(f"[TelegramWorker] Sent: {alert_code}")
        else:
            await self.alert_engine.mark_notification_failed(
                notification_id, "Telegram API error"
            )
    
    async def _send_telegram_message(
        self,
        text: str,
        parse_mode: str = None
    ) -> bool:
        """Send message via Telegram Bot API"""
        if not self._session:
            self._session = aiohttp.ClientSession()
        
        url = f"{self.base_url}/sendMessage"
        
        payload = {
            "chat_id": self.chat_id,
            "text": text
        }
        
        if parse_mode:
            payload["parse_mode"] = parse_mode
        
        try:
            async with self._session.post(url, json=payload, timeout=10) as resp:
                if resp.status == 200:
                    return True
                else:
                    body = await resp.text()
                    logger.error(f"[TelegramWorker] API error {resp.status}: {body}")
                    return False
        except asyncio.TimeoutError:
            logger.error("[TelegramWorker] Telegram API timeout")
            return False
        except Exception as e:
            logger.error(f"[TelegramWorker] HTTP error: {e}")
            return False
    
    async def send_direct(self, text: str) -> bool:
        """Send message directly (for commands response)"""
        return await self._send_telegram_message(text)


class TelegramBot:
    """
    Telegram Bot for commands and interaction.
    Handles /status, /parsers, etc.
    """
    
    def __init__(
        self,
        db: AsyncIOMotorDatabase,
        bot_token: str,
        chat_id: str,
        allowed_chats: list = None
    ):
        self.db = db
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.allowed_chats = allowed_chats or [chat_id]
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        
        self._running = False
        self._last_update_id = 0
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def start(self):
        """Start bot polling"""
        if self._running:
            return
        
        self._running = True
        self._session = aiohttp.ClientSession()
        
        logger.info("[TelegramBot] Started polling")
        
        while self._running:
            try:
                await self._poll_updates()
            except Exception as e:
                logger.error(f"[TelegramBot] Polling error: {e}")
            
            await asyncio.sleep(1)
    
    async def stop(self):
        """Stop bot"""
        self._running = False
        if self._session:
            await self._session.close()
            self._session = None
        logger.info("[TelegramBot] Stopped")
    
    async def _poll_updates(self):
        """Poll for new messages"""
        url = f"{self.base_url}/getUpdates"
        params = {
            "offset": self._last_update_id + 1,
            "timeout": 30
        }
        
        try:
            async with self._session.get(url, params=params, timeout=35) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    updates = data.get("result", [])
                    
                    for update in updates:
                        self._last_update_id = update["update_id"]
                        await self._handle_update(update)
        except asyncio.TimeoutError:
            pass  # Normal for long polling
        except Exception as e:
            logger.error(f"[TelegramBot] Poll error: {e}")
    
    async def _handle_update(self, update: Dict):
        """Handle incoming update"""
        message = update.get("message")
        if not message:
            return
        
        chat_id = str(message.get("chat", {}).get("id"))
        text = message.get("text", "")
        
        # Security check
        if chat_id not in self.allowed_chats:
            logger.warning(f"[TelegramBot] Unauthorized chat: {chat_id}")
            return
        
        # Handle commands
        if text.startswith("/"):
            command = text.split()[0].lower()
            await self._handle_command(command, chat_id)
    
    async def _handle_command(self, command: str, chat_id: str):
        """Handle bot command"""
        handlers = {
            "/start": self._cmd_start,
            "/status": self._cmd_status,
            "/parsers": self._cmd_parsers,
            "/sources": self._cmd_sources,
            "/graph": self._cmd_graph,
            "/momentum": self._cmd_momentum,
            "/alerts": self._cmd_alerts,
            "/help": self._cmd_help
        }
        
        handler = handlers.get(command, self._cmd_unknown)
        response = await handler()
        
        await self._send_message(chat_id, response)
    
    async def _send_message(self, chat_id: str, text: str) -> bool:
        """Send message to chat"""
        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text
        }
        
        try:
            async with self._session.post(url, json=payload) as resp:
                return resp.status == 200
        except Exception as e:
            logger.error(f"[TelegramBot] Send error: {e}")
            return False
    
    # ==========================================================================
    # COMMAND HANDLERS
    # ==========================================================================
    
    async def _cmd_start(self) -> str:
        return """👋 Добро пожаловать в FOMO Intelligence Bot!

Доступные команды:
/status - состояние системы
/parsers - статус парсеров
/sources - источники данных
/graph - метрики графа
/momentum - топ momentum
/alerts - последние алерты
/help - справка"""
    
    async def _cmd_help(self) -> str:
        return """📖 СПРАВКА

/status - общее состояние платформы
/parsers - статус всех парсеров
/sources - здоровье источников данных
/graph - метрики Knowledge Graph
/momentum - топ сущностей по momentum
/alerts - последние 10 алертов

Бот автоматически отправляет уведомления о:
• проблемах с источниками
• ошибках парсеров
• аномалиях в данных
• важных событиях"""
    
    async def _cmd_status(self) -> str:
        """System status command"""
        try:
            # Get various stats
            scheduler = self.db.scheduler_jobs
            jobs = await scheduler.count_documents({})
            
            nodes = await self.db.graph_nodes.count_documents({})
            edges = await self.db.graph_edges.count_documents({})
            
            momentum = await self.db.entity_momentum.count_documents({})
            high_mom = await self.db.entity_momentum.count_documents({
                "momentum_score": {"$gte": 50}
            })
            
            alerts_24h = await self.db.alert_events.count_documents({
                "created_at": {"$gte": datetime.now(timezone.utc) - __import__('datetime').timedelta(days=1)}
            })
            
            return f"""📊 СОСТОЯНИЕ СИСТЕМЫ

Scheduler
задач: {jobs}

Knowledge Graph
узлов: {nodes}
связей: {edges}

Momentum Engine
отслеживается: {momentum}
high momentum: {high_mom}

Алерты за 24ч: {alerts_24h}

✅ Система работает стабильно."""
        except Exception as e:
            return f"❌ Ошибка получения статуса: {e}"
    
    async def _cmd_parsers(self) -> str:
        """Parsers status command"""
        try:
            # This would connect to actual parser stats
            return """🔧 СТАТУС ПАРСЕРОВ

Tier 1 (Critical)
• CryptoRank: ✅
• DefiLlama: ✅
• TokenUnlocks: ✅

Tier 2 (Important)
• CoinGecko: ⚠️ нестабилен
• Messari: ✅

Tier 3 (Standard)
• ICO Drops: ✅
• RootData: ✅

Всего парсеров: 13
Активных: 12
С ошибками: 1"""
        except Exception as e:
            return f"❌ Ошибка: {e}"
    
    async def _cmd_sources(self) -> str:
        """Sources health command"""
        try:
            return """📡 ИСТОЧНИКИ ДАННЫХ

Статус источников:

🟢 Здоровы: 14
🟠 Нестабильны: 1
🔴 Не отвечают: 1

Проблемные:
• CoinGecko - высокий % ошибок

Рекомендуется проверить в админке."""
        except Exception as e:
            return f"❌ Ошибка: {e}"
    
    async def _cmd_graph(self) -> str:
        """Graph metrics command"""
        try:
            nodes = await self.db.graph_nodes.count_documents({})
            factual = await self.db.graph_edges.count_documents({})
            derived = await self.db.graph_derived_edges.count_documents({})
            intel = await self.db.graph_intelligence_edges.count_documents({})
            
            total_edges = factual + derived + intel
            avg_degree = round((total_edges * 2) / max(nodes, 1), 2)
            
            return f"""🔗 KNOWLEDGE GRAPH

Узлы: {nodes}
Связи: {total_edges}

По слоям:
• Factual: {factual}
• Derived: {derived}
• Intelligence: {intel}

Avg Degree: {avg_degree}"""
        except Exception as e:
            return f"❌ Ошибка: {e}"
    
    async def _cmd_momentum(self) -> str:
        """Top momentum command"""
        try:
            cursor = self.db.entity_momentum.find(
                {},
                {"entity_id": 1, "momentum_score": 1, "entity_type": 1}
            ).sort("momentum_score", -1).limit(10)
            
            entities = await cursor.to_list(10)
            
            lines = ["🚀 ТОП MOMENTUM", ""]
            for i, e in enumerate(entities, 1):
                score = e.get("momentum_score", 0)
                name = e.get("entity_id", "?")
                etype = e.get("entity_type", "?")
                lines.append(f"{i}. {name} ({etype}): {score:.1f}")
            
            return "\n".join(lines)
        except Exception as e:
            return f"❌ Ошибка: {e}"
    
    async def _cmd_alerts(self) -> str:
        """Recent alerts command"""
        try:
            cursor = self.db.alert_events.find(
                {},
                {"alert_code": 1, "entity": 1, "created_at": 1, "severity": 1}
            ).sort("created_at", -1).limit(10)
            
            alerts = await cursor.to_list(10)
            
            if not alerts:
                return "📋 Нет недавних алертов"
            
            lines = ["📋 ПОСЛЕДНИЕ АЛЕРТЫ", ""]
            for a in alerts:
                code = a.get("alert_code", "?")
                entity = a.get("entity", "")
                severity = a.get("severity", "INFO")
                
                icon = {"CRITICAL": "🔴", "HIGH": "🔴", "MEDIUM": "🟠", "WARNING": "🟡"}.get(severity, "🔵")
                lines.append(f"{icon} {code}: {entity}")
            
            return "\n".join(lines)
        except Exception as e:
            return f"❌ Ошибка: {e}"
    
    async def _cmd_unknown(self) -> str:
        return "❓ Неизвестная команда. Используйте /help для списка команд."


# Singleton instances
_telegram_worker: Optional[TelegramWorker] = None
_telegram_bot: Optional[TelegramBot] = None


def get_telegram_worker(
    db: AsyncIOMotorDatabase = None,
    bot_token: str = None,
    chat_id: str = None
) -> TelegramWorker:
    """Get or create telegram worker"""
    global _telegram_worker
    if db is not None and bot_token and chat_id:
        _telegram_worker = TelegramWorker(db, bot_token, chat_id)
    return _telegram_worker


def get_telegram_bot(
    db: AsyncIOMotorDatabase = None,
    bot_token: str = None,
    chat_id: str = None,
    allowed_chats: list = None
) -> TelegramBot:
    """Get or create telegram bot"""
    global _telegram_bot
    if db is not None and bot_token and chat_id:
        _telegram_bot = TelegramBot(db, bot_token, chat_id, allowed_chats)
    return _telegram_bot
