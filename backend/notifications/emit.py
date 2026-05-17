"""
Notification Engine — Public API

Import this in any module to emit events:

    from notifications.emit import emit_exchange_forecast, emit_system_error
    await emit_exchange_forecast(forecast_doc)
    await emit_system_error("cron_ingestion", "timeout")
"""
from notifications.events.event_bus import publish_event
from notifications.events.event_normalizers import (
    normalize_exchange_forecast,
    normalize_exchange_divergence,
    normalize_ml_risk,
    normalize_drift_warning,
    normalize_onchain_whale,
    normalize_sentiment_spike,
    normalize_system_error,
    normalize_system_health,
    normalize_telegram_signal,
    normalize_fractal_signal,
    normalize_aggregator_signal,
    normalize_aggregator_alert,
)


async def emit_exchange_forecast(forecast: dict) -> dict:
    return await publish_event(normalize_exchange_forecast(forecast))


async def emit_exchange_divergence(asset: str, details: dict = None) -> dict:
    return await publish_event(normalize_exchange_divergence(asset, details))


async def emit_ml_risk(asset: str, risk_score: float, details: dict = None) -> dict:
    return await publish_event(normalize_ml_risk(asset, risk_score, details))


async def emit_drift_warning(drift_score: float, details: dict = None) -> dict:
    return await publish_event(normalize_drift_warning(drift_score, details))


async def emit_onchain_whale(asset: str, amount: float, from_addr: str = "", to_addr: str = "") -> dict:
    return await publish_event(normalize_onchain_whale(asset, amount, from_addr, to_addr))


async def emit_sentiment_spike(asset: str, delta: float, window: str = "4h") -> dict:
    return await publish_event(normalize_sentiment_spike(asset, delta, window))


async def emit_system_error(module: str, error: str, severity: str = None) -> dict:
    return await publish_event(normalize_system_error(module, error, severity))


async def emit_system_health(message: str, severity: str = None) -> dict:
    return await publish_event(normalize_system_health(message, severity))


async def emit_telegram_signal(asset: str, signal_type: str, details: dict = None) -> dict:
    return await publish_event(normalize_telegram_signal(asset, signal_type, details))


async def emit_fractal_signal(asset: str, signal: str, details: dict = None) -> dict:
    return await publish_event(normalize_fractal_signal(asset, signal, details))


async def emit_aggregator_signal(asset: str, direction: str, confidence: float, details: dict = None) -> dict:
    """Emit aggregator live signal (to user bot if confidence > 0.7)."""
    return await publish_event(normalize_aggregator_signal(asset, direction, confidence, details))


async def emit_aggregator_alert(alert_type: str, message: str, details: dict = None) -> dict:
    """Emit aggregator degradation alert (to admin bot)."""
    return await publish_event(normalize_aggregator_alert(alert_type, message, details))
