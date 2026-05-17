"""
Rule Types — conditions that decide WHO gets notified about WHAT.
"""


def default_user_rules() -> list:
    """Built-in rules for user notifications."""
    return [
        {
            "id": "rule_user_exchange_prediction",
            "audience": "user",
            "isEnabled": True,
            "eventTypes": [
                "exchange.prediction.updated",
                "exchange.divergence.detected",
                "exchange.scenario.breakdown",
            ],
            "conditions": {
                "minSeverity": "medium",
            },
            "channels": ["ui", "telegram_user"],
            "cooldownMinutes": 120,
            "isBuiltin": True,
        },
        {
            "id": "rule_user_onchain_whale",
            "audience": "user",
            "isEnabled": True,
            "eventTypes": [
                "onchain.whale.transfer",
                "onchain.smart_money.entry",
            ],
            "conditions": {
                "minSeverity": "medium",
            },
            "channels": ["ui", "telegram_user"],
            "cooldownMinutes": 60,
            "isBuiltin": True,
        },
        {
            "id": "rule_user_sentiment",
            "audience": "user",
            "isEnabled": True,
            "eventTypes": [
                "sentiment.spike",
                "fractal.signal.updated",
                "telegram.signal.detected",
            ],
            "conditions": {
                "minSeverity": "medium",
            },
            "channels": ["ui", "telegram_user"],
            "cooldownMinutes": 120,
            "isBuiltin": True,
        },
    ]


def default_admin_rules() -> list:
    """Built-in rules for admin notifications."""
    return [
        {
            "id": "rule_admin_system",
            "audience": "admin",
            "isEnabled": True,
            "eventTypes": [
                "system.error",
                "system.health.warning",
                "exchange.drift.warning",
                "exchange.ml_risk.high",
            ],
            "conditions": {
                "minSeverity": "medium",
            },
            "channels": ["ui", "telegram_admin"],
            "cooldownMinutes": 30,
            "isBuiltin": True,
        },
        {
            "id": "rule_admin_all_critical",
            "audience": "admin",
            "isEnabled": True,
            "eventTypes": [],
            "conditions": {
                "minSeverity": "critical",
            },
            "channels": ["ui", "telegram_admin"],
            "cooldownMinutes": 10,
            "isBuiltin": True,
        },
    ]
