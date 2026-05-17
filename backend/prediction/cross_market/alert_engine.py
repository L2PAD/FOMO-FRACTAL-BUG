"""
Cross-Market Alert Engine — prepares alert messages for high-confidence signals.

Currently a STUB — does NOT send. Will be activated after:
  - Phase 2.5 stabilized
  - Kalshi Batch 2 complete
  - 3-5 stable signals confirmed
"""
import logging

logger = logging.getLogger("cross_market.alert_engine")

# Alert thresholds
ALERT_MIN_SCORE = 0.7
ALERT_MIN_ACTIONABILITY = 0.65
ALERT_MIN_VOLUME = 10000


def should_send_alert(strategy: dict) -> bool:
    """Check if a strategy meets alert criteria."""
    if strategy.get("strategy_type") != "LOGICAL_ARBITRAGE":
        return False
    if strategy.get("mispricing_score", 0) < ALERT_MIN_SCORE:
        return False
    if strategy.get("actionability_score", 0) < ALERT_MIN_ACTIONABILITY:
        return False
    return True


def format_alert_message(strategy: dict) -> str:
    """Format strategy into readable alert message."""
    severity = strategy.get("actionability_severity", "MEDIUM")
    action_a = strategy.get("action_a", "")
    action_b = strategy.get("action_b", "")
    threshold_a = strategy.get("threshold_a", 0)
    threshold_b = strategy.get("threshold_b", 0)
    price_a = strategy.get("price_a", 0)
    price_b = strategy.get("price_b", 0)
    gap_pct = strategy.get("gap_pct", 0)
    score = strategy.get("mispricing_score", 0)
    act_score = strategy.get("actionability_score", 0)
    mode = strategy.get("mode", "SUBSET")
    rationale = strategy.get("rationale", "")

    ab = strategy.get("actionability_breakdown", {})
    liq = ab.get("liquidity_component", 0)
    exe = ab.get("execution_component", 0)

    liq_label = "High" if liq >= 0.24 else "Good" if liq >= 0.15 else "Low"
    exe_label = "Good" if exe >= 0.14 else "Low"

    msg = (
        f"LOGICAL ARBITRAGE\n\n"
        f"Mode: {mode}\n"
        f"Gap: +{gap_pct}%\n"
        f"Score: {score:.3f}\n"
        f"Actionability: {act_score:.3f} ({severity})\n\n"
        f"{action_a} (${threshold_a:,.0f}) @ {price_a:.1%}\n"
        f"{action_b} (${threshold_b:,.0f}) @ {price_b:.1%}\n\n"
        f"Liquidity: {liq_label}\n"
        f"Execution: {exe_label}\n\n"
        f"Reason:\n{rationale}\n\n"
        f"Risk:\nLow liquidity spike / fast correction"
    )
    return msg


def process_alert(strategy: dict) -> dict:
    """Process a strategy for alerting. Returns alert payload.

    NOTE: Currently a STUB - does NOT send to any channel.
    """
    if not should_send_alert(strategy):
        return {"sent": False, "reason": "below_threshold"}

    message = format_alert_message(strategy)

    # STUB: Log but don't send
    logger.info(f"[AlertEngine] Alert prepared (NOT SENT): {strategy.get('strategy_type')}")

    return {
        "sent": False,  # Will be True when Telegram integration is activated
        "reason": "stub_mode",
        "message": message,
        "strategy_type": strategy.get("strategy_type"),
        "score": strategy.get("mispricing_score"),
        "actionability": strategy.get("actionability_score"),
    }
