"""
Unified Notification Engine — Event Types

All platform modules emit ONE type: NotificationEvent.
No alerts, no watchlists, no notifications — just events.
"""
from typing import Optional
from enum import Enum


class EventType(str, Enum):
    # Exchange
    EXCHANGE_PREDICTION_UPDATED = "exchange.prediction.updated"
    EXCHANGE_DIVERGENCE_DETECTED = "exchange.divergence.detected"
    EXCHANGE_SCENARIO_BREAKDOWN = "exchange.scenario.breakdown"
    EXCHANGE_ML_RISK_HIGH = "exchange.ml_risk.high"
    EXCHANGE_DRIFT_WARNING = "exchange.drift.warning"
    # Fractal
    FRACTAL_SIGNAL_UPDATED = "fractal.signal.updated"
    # Aggregator
    AGGREGATOR_SIGNAL = "aggregator.signal.live"
    AGGREGATOR_ALERT = "aggregator.alert.degradation"
    # OnChain
    ONCHAIN_WHALE_TRANSFER = "onchain.whale.transfer"
    ONCHAIN_SMART_MONEY_ENTRY = "onchain.smart_money.entry"
    # Sentiment
    SENTIMENT_SPIKE = "sentiment.spike"
    # Telegram
    TELEGRAM_SIGNAL_DETECTED = "telegram.signal.detected"
    # System
    SYSTEM_ERROR = "system.error"
    SYSTEM_HEALTH_WARNING = "system.health.warning"


class EventSource(str, Enum):
    EXCHANGE = "exchange"
    FRACTAL = "fractal"
    AGGREGATOR = "aggregator"
    ONCHAIN = "onchain"
    SENTIMENT = "sentiment"
    TELEGRAM = "telegram"
    SYSTEM = "system"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class EntityType(str, Enum):
    ASSET = "asset"
    WALLET = "wallet"
    PROJECT = "project"
    SYSTEM = "system"


SEVERITY_RANK = {
    Severity.LOW: 1,
    Severity.MEDIUM: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}
