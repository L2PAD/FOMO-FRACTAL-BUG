"""
Rule Engine — evaluates events against rules and creates notifications.
"""
from notifications.events.event_types import SEVERITY_RANK, Severity
from notifications.storage.rule_repo import get_matching_rules
from notifications.notifications.notification_service import create_notifications_for_rule


async def evaluate_rules(event: dict) -> list:
    """
    Find all rules matching this event type, evaluate conditions,
    and create notifications for each matched rule.
    Returns list of created notification dicts.
    """
    event_type = event.get("type", "")
    matching_rules = await get_matching_rules(event_type)
    created = []

    for rule in matching_rules:
        if not rule.get("isEnabled", True):
            continue

        # Check asset filter
        conditions = rule.get("conditions", {})
        rule_assets = conditions.get("assets", [])
        if rule_assets and event.get("asset"):
            if event["asset"] not in rule_assets:
                continue

        # Check severity filter
        min_sev = conditions.get("minSeverity")
        if min_sev:
            event_sev = event.get("severity", "low")
            if SEVERITY_RANK.get(event_sev, 0) < SEVERITY_RANK.get(min_sev, 0):
                continue

        # Check expected move filter
        min_move = conditions.get("minExpectedMovePct")
        if min_move:
            pct = abs(float(event.get("payload", {}).get("expectedMovePct", 0)))
            if pct < min_move:
                continue

        # All conditions passed — create notifications
        notifications = await create_notifications_for_rule(event, rule)
        created.extend(notifications)

    return created
