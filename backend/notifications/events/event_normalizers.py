"""
Event Normalizers — Adapter layer that converts legacy alerts to unified events.

Usage:
    from notifications.events.event_normalizers import normalize_exchange_forecast
    event = normalize_exchange_forecast(forecast_doc)
    await publish_event(event)
"""
from notifications.events.event_types import EventType, EventSource, Severity


def normalize_exchange_forecast(forecast: dict) -> dict:
    """Convert exchange forecast doc to a notification event."""
    asset = forecast.get("symbol") or forecast.get("asset", "?")
    horizon = forecast.get("horizon", "")
    direction = forecast.get("direction", "neutral")
    confidence = float(forecast.get("confidence", 0))
    expected_move = float(forecast.get("expectedMovePct", forecast.get("expected_move_pct", 0)))

    severity = Severity.LOW.value
    if abs(expected_move) > 3:
        severity = Severity.HIGH.value
    elif abs(expected_move) > 1.5:
        severity = Severity.MEDIUM.value

    return {
        "type": EventType.EXCHANGE_PREDICTION_UPDATED.value,
        "source": EventSource.EXCHANGE.value,
        "asset": asset,
        "severity": severity,
        "title": f"{asset} {horizon} outlook updated",
        "payload": {
            "horizon": horizon,
            "direction": direction,
            "confidence": confidence,
            "expectedMovePct": expected_move,
        },
    }


def normalize_exchange_divergence(asset: str, details: dict = None) -> dict:
    """Convert divergence detection to event."""
    return {
        "type": EventType.EXCHANGE_DIVERGENCE_DETECTED.value,
        "source": EventSource.EXCHANGE.value,
        "asset": asset,
        "severity": Severity.MEDIUM.value,
        "title": f"{asset} divergence detected",
        "payload": details or {},
    }


def normalize_ml_risk(asset: str, risk_score: float, details: dict = None) -> dict:
    """ML overlay detected high risk."""
    severity = Severity.HIGH.value if risk_score > 0.7 else Severity.MEDIUM.value
    return {
        "type": EventType.EXCHANGE_ML_RISK_HIGH.value,
        "source": EventSource.EXCHANGE.value,
        "asset": asset,
        "severity": severity,
        "title": f"ML Risk elevated: {asset}",
        "payload": {"riskScore": risk_score, **(details or {})},
    }


def normalize_drift_warning(drift_score: float, details: dict = None) -> dict:
    """Exchange drift detected."""
    severity = Severity.HIGH.value if drift_score > 0.8 else Severity.MEDIUM.value
    return {
        "type": EventType.EXCHANGE_DRIFT_WARNING.value,
        "source": EventSource.EXCHANGE.value,
        "severity": severity,
        "title": "Exchange drift warning",
        "payload": {"driftScore": drift_score, **(details or {})},
    }


def normalize_onchain_whale(asset: str, amount: float, from_addr: str = "", to_addr: str = "") -> dict:
    """Large on-chain transfer."""
    return {
        "type": EventType.ONCHAIN_WHALE_TRANSFER.value,
        "source": EventSource.ONCHAIN.value,
        "asset": asset,
        "severity": Severity.HIGH.value,
        "title": f"Large {asset} transfer",
        "payload": {"amount": amount, "from": from_addr, "to": to_addr},
    }


def normalize_sentiment_spike(asset: str, delta: float, window: str = "4h") -> dict:
    """Sentiment score spike."""
    severity = Severity.HIGH.value if abs(delta) > 0.5 else Severity.MEDIUM.value
    return {
        "type": EventType.SENTIMENT_SPIKE.value,
        "source": EventSource.SENTIMENT.value,
        "asset": asset,
        "severity": severity,
        "title": f"{asset} sentiment spike",
        "payload": {"delta": delta, "window": window},
    }


def normalize_system_error(module: str, error: str, severity: str = None) -> dict:
    """System error event."""
    return {
        "type": EventType.SYSTEM_ERROR.value,
        "source": EventSource.SYSTEM.value,
        "severity": severity or Severity.CRITICAL.value,
        "title": f"System error: {module}",
        "payload": {"module": module, "error": error},
    }


def normalize_system_health(message: str, severity: str = None) -> dict:
    """System health warning."""
    return {
        "type": EventType.SYSTEM_HEALTH_WARNING.value,
        "source": EventSource.SYSTEM.value,
        "severity": severity or Severity.MEDIUM.value,
        "title": "System health warning",
        "payload": {"message": message},
    }


def normalize_telegram_signal(asset: str, signal_type: str, details: dict = None) -> dict:
    """Telegram channel signal detected."""
    return {
        "type": EventType.TELEGRAM_SIGNAL_DETECTED.value,
        "source": EventSource.TELEGRAM.value,
        "asset": asset,
        "severity": Severity.MEDIUM.value,
        "title": f"Telegram signal: {asset}",
        "payload": {"signalType": signal_type, **(details or {})},
    }


def normalize_fractal_signal(asset: str, signal: str, details: dict = None) -> dict:
    """Fractal analysis signal."""
    return {
        "type": EventType.FRACTAL_SIGNAL_UPDATED.value,
        "source": EventSource.FRACTAL.value,
        "asset": asset,
        "severity": Severity.MEDIUM.value,
        "title": f"{asset} fractal signal: {signal}",
        "payload": {"signal": signal, **(details or {})},
    }


def normalize_aggregator_signal(asset: str, direction: str, confidence: float, details: dict = None) -> dict:
    """System Aggregator live signal."""
    severity = Severity.LOW.value
    if confidence >= 0.7:
        severity = Severity.HIGH.value
    elif confidence >= 0.5:
        severity = Severity.MEDIUM.value

    return {
        "type": EventType.AGGREGATOR_SIGNAL.value,
        "source": EventSource.AGGREGATOR.value,
        "asset": asset,
        "severity": severity,
        "title": f"{asset} Aggregator Signal → {direction}",
        "payload": {
            "direction": direction,
            "confidence": confidence,
            **(details or {}),
        },
    }


def normalize_aggregator_alert(alert_type: str, message: str, details: dict = None) -> dict:
    """System Aggregator degradation alert (admin only)."""
    return {
        "type": EventType.AGGREGATOR_ALERT.value,
        "source": EventSource.AGGREGATOR.value,
        "asset": "SYSTEM",
        "severity": Severity.CRITICAL.value,
        "title": f"Aggregator Alert: {alert_type}",
        "payload": {"alert_type": alert_type, "message": message, **(details or {})},
    }
