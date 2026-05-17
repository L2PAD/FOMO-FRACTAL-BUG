"""
Notification Templates — format event into user-facing messages.
"""


def build_template(event: dict, audience: str) -> dict:
    """Build title + message for a notification from an event."""
    event_type = event.get("type", "")
    asset = event.get("asset", "Asset")
    payload = event.get("payload", {})

    handler = TEMPLATES.get(event_type)
    if handler:
        return handler(event, audience)

    return {
        "title": event.get("title", event_type),
        "message": _payload_summary(payload),
    }


def _payload_summary(payload: dict) -> str:
    parts = []
    for k, v in list(payload.items())[:4]:
        parts.append(f"{k}: {v}")
    return " | ".join(parts) if parts else ""


def _exchange_prediction(event: dict, audience: str) -> dict:
    asset = event.get("asset", "?")
    p = event.get("payload", {})
    horizon = p.get("horizon", "")
    direction = str(p.get("direction", "")).upper()
    pct = float(p.get("expectedMovePct", 0))
    conf = float(p.get("confidence", 0))
    sign = "+" if pct > 0 else ""
    return {
        "title": f"{asset} {horizon} outlook updated",
        "message": f"{direction} | expected move {sign}{pct:.2f}% | confidence {conf:.0%}",
    }


def _exchange_divergence(event: dict, audience: str) -> dict:
    asset = event.get("asset", "?")
    return {
        "title": f"{asset} divergence detected",
        "message": "Short-term and long-term forecasts disagree.",
    }


def _exchange_drift(event: dict, audience: str) -> dict:
    p = event.get("payload", {})
    score = p.get("driftScore", "?")
    return {
        "title": "Exchange drift warning",
        "message": f"Drift score: {score}. Check system health.",
    }


def _exchange_ml_risk(event: dict, audience: str) -> dict:
    p = event.get("payload", {})
    risk = p.get("riskScore", "?")
    return {
        "title": f"ML Risk elevated: {event.get('asset', '?')}",
        "message": f"Risk score: {risk}. Confidence may be reduced.",
    }


def _onchain_whale(event: dict, audience: str) -> dict:
    p = event.get("payload", {})
    amount = p.get("amount", "?")
    asset = event.get("asset", "?")
    return {
        "title": f"Large {asset} transfer",
        "message": f"Amount: {amount} {asset}",
    }


def _sentiment_spike(event: dict, audience: str) -> dict:
    p = event.get("payload", {})
    delta = p.get("delta", "?")
    window = p.get("window", "?")
    return {
        "title": f"{event.get('asset', '?')} sentiment spike",
        "message": f"Delta: {delta} over {window}",
    }


def _system_error(event: dict, audience: str) -> dict:
    p = event.get("payload", {})
    module = p.get("module", "unknown")
    error = p.get("error", "")
    if audience == "admin":
        return {
            "title": f"System error: {module}",
            "message": f"Error: {error}" if error else f"Module {module} reported failure.",
        }
    return {
        "title": "Service instability detected",
        "message": "Some features may be temporarily unavailable.",
    }


def _system_health(event: dict, audience: str) -> dict:
    p = event.get("payload", {})
    return {
        "title": "System health warning",
        "message": p.get("message", "Health check degraded."),
    }


TEMPLATES = {
    "exchange.prediction.updated": _exchange_prediction,
    "exchange.divergence.detected": _exchange_divergence,
    "exchange.scenario.breakdown": _exchange_prediction,
    "exchange.drift.warning": _exchange_drift,
    "exchange.ml_risk.high": _exchange_ml_risk,
    "onchain.whale.transfer": _onchain_whale,
    "onchain.smart_money.entry": _onchain_whale,
    "sentiment.spike": _sentiment_spike,
    "system.error": _system_error,
    "system.health.warning": _system_health,
}
