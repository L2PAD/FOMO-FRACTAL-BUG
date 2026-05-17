"""
Telegram Formatter — clean, actionable messages.

Style:
  [ASSET] [HORIZON] → [DIRECTION]
  Move: ±X%
  Context: 1 line

No JSON. No tech jargon. Every message = a signal.
"""


def format_user_message(event: dict) -> str:
    """Format event for user Telegram bot."""
    etype = event.get("type", "")
    handler = USER_FORMATTERS.get(etype, _default_format)
    return handler(event)


def format_admin_message(event: dict) -> str:
    """Format event for admin Telegram bot."""
    etype = event.get("type", "")
    handler = ADMIN_FORMATTERS.get(etype, _default_admin_format)
    return handler(event)


# ── User formatters ──

def _fmt_prediction(event: dict) -> str:
    p = event.get("payload", {})
    asset = event.get("asset", "?")
    horizon = p.get("horizon", "")
    direction = str(p.get("direction", "")).upper()
    move = float(p.get("expectedMovePct", 0))
    conf = float(p.get("confidence", 0))
    scenario = p.get("scenario", "")

    sign = "+" if move > 0 else ""
    lines = [
        f"<b>{asset} {horizon}</b> → {direction}",
        f"Move: {sign}{move:.1f}%",
        f"Confidence: {conf:.0%}",
    ]
    if scenario:
        lines.append(f"Scenario: {scenario}")
    return "\n".join(lines)


def _fmt_divergence(event: dict) -> str:
    p = event.get("payload", {})
    asset = event.get("asset", "?")
    d7 = p.get("7D", "?")
    d30 = p.get("30D", "?")
    return (
        f"<b>{asset} DIVERGENCE</b>\n"
        f"7D: {d7}\n"
        f"30D: {d30}\n"
        f"Possible reversal or bounce"
    )


def _fmt_whale(event: dict) -> str:
    p = event.get("payload", {})
    asset = event.get("asset", "?")
    amount = p.get("amount", 0)
    direction = p.get("direction", "")
    wallet_type = p.get("walletType", "whale")
    value_usd = p.get("valueUsd", 0)

    label = "Whale" if wallet_type == "whale" else "Smart Money"
    lines = [f"<b>{asset} {label} Activity</b>"]
    if amount:
        lines.append(f"{amount:,.0f} {asset}" if isinstance(amount, (int, float)) else f"{amount} {asset}")
    if value_usd and value_usd > 0:
        lines.append(f"${value_usd / 1e6:.1f}M")
    if direction == "inflow":
        lines.append("→ to exchange")
    elif direction == "outflow":
        lines.append("→ outflow")
    return "\n".join(lines)


def _fmt_sentiment(event: dict) -> str:
    p = event.get("payload", {})
    asset = event.get("asset", "?")
    delta = float(p.get("delta", 0))
    window = p.get("window", "4h")
    direction = "Bullish" if delta > 0 else "Bearish"
    return (
        f"<b>{asset} Sentiment Spike</b>\n"
        f"{direction} momentum {'rising' if delta > 0 else 'falling'}\n"
        f"Delta: {delta:+.1%} ({window})"
    )


def _default_format(event: dict) -> str:
    asset = event.get("asset", "")
    title = event.get("title", event.get("type", "Event"))
    prefix = f"<b>{asset}</b> " if asset else ""
    return f"{prefix}{title}"


# ── Admin formatters ──

def _fmt_system_error(event: dict) -> str:
    p = event.get("payload", {})
    module = p.get("module", "unknown")
    error = p.get("error", "")
    sev = event.get("severity", "high").upper()
    lines = [f"<b>[{sev}] System Error</b>", f"Module: {module}"]
    if error:
        lines.append(f"Error: {error}")
    return "\n".join(lines)


def _fmt_health_warning(event: dict) -> str:
    p = event.get("payload", {})
    msg = p.get("message", "Health check failed")
    return f"<b>Health Warning</b>\n{msg}"


def _fmt_drift(event: dict) -> str:
    p = event.get("payload", {})
    score = p.get("driftScore", "?")
    status = p.get("status", "")
    lines = [f"<b>Drift Spike: {score}</b>"]
    if status:
        lines.append(f"Status: {status}")
    return "\n".join(lines)


def _fmt_ml_risk(event: dict) -> str:
    p = event.get("payload", {})
    asset = event.get("asset", "?")
    risk = p.get("riskScore", "?")
    return f"<b>ML Risk: {asset}</b>\nRisk score: {risk}"


def _default_admin_format(event: dict) -> str:
    sev = event.get("severity", "medium").upper()
    title = event.get("title", event.get("type", "Event"))
    return f"<b>[{sev}]</b> {title}"


def _fmt_aggregator_signal(event: dict) -> str:
    """Format aggregator live signal for user Telegram."""
    p = event.get("payload", {})
    asset = event.get("asset", "?")
    direction = p.get("direction", "?")
    confidence = p.get("confidence", 0)
    components = p.get("components", {})

    emoji = {"LONG": "🟢", "SHORT": "🔴", "NEUTRAL": "⚪"}.get(direction, "⚪")
    conf_bar = "█" * int(confidence * 10) + "░" * (10 - int(confidence * 10))

    lines = [
        f"{emoji} <b>{asset} — {direction}</b>",
        f"Confidence: {conf_bar} {confidence:.0%}",
    ]
    if components:
        lines.append("<i>Sources:</i>")
        for k, v in components.items():
            if abs(v) > 0.001:
                sign = "+" if v > 0 else ""
                lines.append(f"  {k}: {sign}{v:.4f}")

    return "\n".join(lines)


def _fmt_aggregator_alert(event: dict) -> str:
    """Format aggregator degradation alert for admin Telegram."""
    p = event.get("payload", {})
    alert_type = p.get("alert_type", "UNKNOWN")
    message = p.get("message", "")

    return (
        f"⚠️ <b>AGGREGATOR ALERT: {alert_type}</b>\n"
        f"{message}\n"
        f"<i>Action: Check /api/system/aggregator-live-metrics</i>"
    )


USER_FORMATTERS = {
    "exchange.prediction.updated": _fmt_prediction,
    "exchange.scenario.breakdown": _fmt_prediction,
    "exchange.divergence.detected": _fmt_divergence,
    "onchain.whale.transfer": _fmt_whale,
    "onchain.smart_money.entry": _fmt_whale,
    "sentiment.spike": _fmt_sentiment,
    "aggregator.signal.live": _fmt_aggregator_signal,
}

ADMIN_FORMATTERS = {
    "system.error": _fmt_system_error,
    "system.health.warning": _fmt_health_warning,
    "exchange.drift.warning": _fmt_drift,
    "exchange.ml_risk.high": _fmt_ml_risk,
    "aggregator.alert.degradation": _fmt_aggregator_alert,
}
