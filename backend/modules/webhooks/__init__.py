"""
Webhooks Module
"""

from .routes import router, set_database, emit_funding_event, emit_unlock_event, emit_news_event, emit_price_alert
from .emitter import (
    WebhookEventEmitter, 
    get_emitter,
    emit_on_funding_insert,
    emit_on_unlock_insert,
    emit_on_news_insert
)

__all__ = [
    'router',
    'set_database',
    'emit_funding_event',
    'emit_unlock_event', 
    'emit_news_event',
    'emit_price_alert',
    'WebhookEventEmitter',
    'get_emitter',
    'emit_on_funding_insert',
    'emit_on_unlock_insert',
    'emit_on_news_insert'
]
