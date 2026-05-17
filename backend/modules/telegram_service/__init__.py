"""
Telegram Service Module
=======================

Notification system for FOMO platform.

Components:
- alert_templates_ru.py - Russian message templates
- alert_engine.py - Alert processing engine
- telegram_worker.py - Telegram Bot API worker
- routes.py - API endpoints

Architecture:
System Event → Alert Engine → Notification Queue → Telegram Worker → Bot API
"""

from .alert_templates_ru import (
    ALERT_TEMPLATES,
    AlertSeverity,
    SEVERITY_ICONS,
    render_alert,
    get_alert_severity,
    get_alert_cooldown,
    get_alert_category,
    get_all_alert_codes
)

from .alert_engine import (
    AlertEngine,
    get_alert_engine
)

from .telegram_worker import (
    TelegramWorker,
    TelegramBot,
    get_telegram_worker,
    get_telegram_bot
)

__all__ = [
    # Templates
    "ALERT_TEMPLATES",
    "AlertSeverity",
    "SEVERITY_ICONS",
    "render_alert",
    "get_alert_severity",
    "get_alert_cooldown",
    "get_alert_category",
    "get_all_alert_codes",
    # Engine
    "AlertEngine",
    "get_alert_engine",
    # Worker
    "TelegramWorker",
    "TelegramBot",
    "get_telegram_worker",
    "get_telegram_bot"
]
