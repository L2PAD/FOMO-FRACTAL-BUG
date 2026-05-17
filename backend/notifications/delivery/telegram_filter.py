"""
Telegram Filter — decides what is worth sending to Telegram.

Telegram = action signal, NOT a mirror of UI.
Only high-value events pass through.
"""


def should_send_user(event: dict) -> bool:
    """Filter for user Telegram bot. Only strong signals."""
    etype = event.get("type", "")
    payload = event.get("payload", {})

    # Strong predictions: |move| > 1.0%
    if etype == "exchange.prediction.updated":
        move = abs(float(payload.get("expectedMovePct", 0)))
        return move > 1.0

    # Divergence: always important
    if etype == "exchange.divergence.detected":
        return True

    # Scenario breakdown
    if etype == "exchange.scenario.breakdown":
        return True

    # Whale transfers
    if etype == "onchain.whale.transfer":
        return True

    # Smart money entry
    if etype == "onchain.smart_money.entry":
        return True

    # Strong sentiment spikes
    if etype == "sentiment.spike":
        delta = abs(float(payload.get("delta", 0)))
        return delta > 0.4

    return False


def should_send_admin(event: dict) -> bool:
    """Filter for admin Telegram bot. System health only."""
    etype = event.get("type", "")

    # System errors — always
    if etype == "system.error":
        return True

    # Health warnings
    if etype == "system.health.warning":
        return True

    # Drift — always for admin
    if etype == "exchange.drift.warning":
        return True

    # ML Risk high
    if etype == "exchange.ml_risk.high":
        return True

    # Critical anything
    if event.get("severity") == "critical":
        return True

    return False
