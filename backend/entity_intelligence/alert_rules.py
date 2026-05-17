"""
On-Chain Alert Rules Engine
============================
Rules-based alert system for on-chain entity intelligence signals.
Rules are stored in MongoDB and evaluated against the latest signals.

Rule format:
{
  "name": "Binance Large Outflow",
  "enabled": true,
  "conditions": {
    "min_score": 70,
    "status": "confirmed",
    "chains": ["ethereum", "arbitrum", "optimism", "base"],
    "signal_types": ["CEX_OUTFLOW"],
    "entities": ["Binance"],
    "min_amount_eth": 100,
    "drivers": []
  },
  "notify": {
    "telegram": true,
    "in_app": true
  }
}
"""

import os
import hashlib
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient, DESCENDING
from typing import Optional

_client = None
ALLOWED_CHAINS = {"ethereum", "arbitrum", "optimism", "base"}
CHAIN_LABELS = {"ethereum": "ETH", "arbitrum": "ARB", "optimism": "OP", "base": "BASE"}

# Default alert cooldown: don't re-alert same signal within this window
ALERT_COOLDOWN_MIN = 30


def _get_db():
    global _client
    if _client is None:
        _client = MongoClient(os.environ["MONGO_URL"])
    return _client[os.environ.get("DB_NAME", "intelligence_engine")]


def _rule_id(name: str) -> str:
    return "rule_" + hashlib.md5(name.encode()).hexdigest()[:10]


# ═══════════════════════════════════════════
# CRUD: Alert Rules
# ═══════════════════════════════════════════

def get_rules() -> list:
    db = _get_db()
    return list(db.alert_rules.find({}, {"_id": 0}).sort("created_at", DESCENDING))


def get_rule(rule_id: str) -> Optional[dict]:
    db = _get_db()
    return db.alert_rules.find_one({"id": rule_id}, {"_id": 0})


def create_rule(rule_data: dict) -> dict:
    db = _get_db()
    name = rule_data.get("name", "Unnamed Rule")
    rule = {
        "id": _rule_id(name + datetime.now(timezone.utc).isoformat()),
        "name": name,
        "enabled": rule_data.get("enabled", True),
        "conditions": {
            "min_score": rule_data.get("conditions", {}).get("min_score", 70),
            "status": rule_data.get("conditions", {}).get("status", "confirmed"),
            "chains": rule_data.get("conditions", {}).get("chains", list(ALLOWED_CHAINS)),
            "signal_types": rule_data.get("conditions", {}).get("signal_types", []),
            "entities": rule_data.get("conditions", {}).get("entities", []),
            "min_amount_eth": rule_data.get("conditions", {}).get("min_amount_eth", 0),
            "drivers": rule_data.get("conditions", {}).get("drivers", []),
        },
        "notify": {
            "telegram": rule_data.get("notify", {}).get("telegram", True),
            "in_app": rule_data.get("notify", {}).get("in_app", True),
        },
        "created_at": datetime.now(timezone.utc).isoformat(),
        "fired_count": 0,
        "last_fired": None,
    }
    db.alert_rules.insert_one(rule)
    rule.pop("_id", None)
    return rule


def update_rule(rule_id: str, updates: dict) -> Optional[dict]:
    db = _get_db()
    allowed = {"name", "enabled", "conditions", "notify"}
    upd = {k: v for k, v in updates.items() if k in allowed}
    if not upd:
        return get_rule(rule_id)
    db.alert_rules.update_one({"id": rule_id}, {"$set": upd})
    return get_rule(rule_id)


def delete_rule(rule_id: str) -> bool:
    db = _get_db()
    result = db.alert_rules.delete_one({"id": rule_id})
    return result.deleted_count > 0


# ═══════════════════════════════════════════
# Evaluation Engine
# ═══════════════════════════════════════════

def _matches_rule(signal: dict, rule: dict) -> bool:
    """Check if a signal matches a rule's conditions."""
    cond = rule.get("conditions", {})

    # Score threshold
    if signal.get("score", 0) < cond.get("min_score", 70):
        return False

    # Status filter
    req_status = cond.get("status", "")
    if req_status and signal.get("status", "") != req_status:
        return False

    # Chain filter
    chains = cond.get("chains", [])
    if chains and signal.get("chain", "ethereum") not in chains:
        return False

    # Signal type filter
    sig_types = cond.get("signal_types", [])
    if sig_types and signal.get("signal_type", "") not in sig_types:
        return False

    # Entity filter
    entities = cond.get("entities", [])
    if entities:
        sig_entity = signal.get("entity", "")
        if sig_entity not in entities:
            return False

    # Min amount ETH
    min_eth = cond.get("min_amount_eth", 0)
    if min_eth > 0 and signal.get("amount_eth", 0) < min_eth:
        return False

    # Drivers filter
    req_drivers = cond.get("drivers", [])
    if req_drivers:
        sig_drivers = signal.get("drivers", [])
        if isinstance(sig_drivers, list):
            if not any(d in sig_drivers for d in req_drivers):
                return False

    # Must have entity OR wallet evidence
    has_entity = bool(signal.get("entity"))
    has_wallet = bool(signal.get("evidence", {}).get("wallet"))
    if not has_entity and not has_wallet:
        return False

    return True


def _dedup_key(signal_id: str, rule_id: str) -> str:
    return hashlib.md5(f"{signal_id}_{rule_id}".encode()).hexdigest()[:16]


def evaluate_rules(signals: list = None) -> list:
    """
    Evaluate all enabled rules against current signals.
    Returns list of new alerts fired.
    """
    db = _get_db()

    if signals is None:
        from signals_v3.signal_engine import generate_signals
        from entity_intelligence.signal_enrichment import generate_entity_signals
        signals = generate_signals() + generate_entity_signals()

    rules = list(db.alert_rules.find({"enabled": True}, {"_id": 0}))
    if not rules:
        return []

    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(minutes=ALERT_COOLDOWN_MIN)).isoformat()

    fired = []

    for signal in signals:
        for rule in rules:
            if not _matches_rule(signal, rule):
                continue

            # Dedup: check if we already fired for this signal+rule combo
            dedup = _dedup_key(signal.get("id", ""), rule.get("id", ""))
            existing = db.alert_history.find_one({
                "dedup_key": dedup,
                "fired_at": {"$gte": cutoff},
            })
            if existing:
                continue

            # Build alert
            chain_label = CHAIN_LABELS.get(signal.get("chain", "ethereum"), "ETH")
            entity_label = signal.get("entity", signal.get("evidence", {}).get("wallet", "")[:10])
            explorer_url = signal.get("explorer_url", signal.get("evidence", {}).get("tx_link", ""))

            alert = {
                "dedup_key": dedup,
                "rule_id": rule["id"],
                "rule_name": rule["name"],
                "signal_id": signal.get("id", ""),
                "signal_type": signal.get("signal_type", ""),
                "chain": signal.get("chain", "ethereum"),
                "chain_label": chain_label,
                "entity": entity_label,
                "entity_type": signal.get("entity_type", ""),
                "score": signal.get("score", 0),
                "severity": signal.get("severity", "WATCH"),
                "direction": signal.get("direction", "NEUTRAL"),
                "amount_eth": signal.get("amount_eth", 0),
                "tx_count": signal.get("tx_count", 0),
                "detail": signal.get("detail", ""),
                "drivers": signal.get("drivers", []),
                "explorer_url": explorer_url,
                "wallet": signal.get("evidence", {}).get("wallet", ""),
                "tx_hash": signal.get("evidence", {}).get("tx_hash", ""),
                "fired_at": now.isoformat(),
                "acknowledged": False,
                "telegram_sent": False,
            }

            db.alert_history.insert_one(alert)
            alert.pop("_id", None)

            # Update rule stats
            db.alert_rules.update_one(
                {"id": rule["id"]},
                {"$inc": {"fired_count": 1}, "$set": {"last_fired": now.isoformat()}},
            )

            fired.append(alert)

    return fired


# ═══════════════════════════════════════════
# Alert History
# ═══════════════════════════════════════════

def get_alert_history(limit: int = 50, unacknowledged_only: bool = False) -> list:
    db = _get_db()
    query = {}
    if unacknowledged_only:
        query["acknowledged"] = False
    return list(
        db.alert_history.find(query, {"_id": 0})
        .sort("fired_at", DESCENDING)
        .limit(limit)
    )


def acknowledge_alert(dedup_key: str) -> bool:
    db = _get_db()
    result = db.alert_history.update_one(
        {"dedup_key": dedup_key},
        {"$set": {"acknowledged": True}},
    )
    return result.modified_count > 0


def get_alert_stats() -> dict:
    db = _get_db()
    total = db.alert_history.count_documents({})
    unack = db.alert_history.count_documents({"acknowledged": False})
    rules_count = db.alert_rules.count_documents({})
    active_rules = db.alert_rules.count_documents({"enabled": True})

    # Last 24h stats
    cutoff_24h = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    last_24h = db.alert_history.count_documents({"fired_at": {"$gte": cutoff_24h}})

    return {
        "total_alerts": total,
        "unacknowledged": unack,
        "last_24h": last_24h,
        "rules_count": rules_count,
        "active_rules": active_rules,
    }


# ═══════════════════════════════════════════
# Telegram Message Builder
# ═══════════════════════════════════════════

def build_telegram_message(alert: dict) -> str:
    """Build a rich Telegram alert message with entity, chain, and explorer links."""
    chain_emoji = {"ETH": "\u26d3\ufe0f", "ARB": "\U0001f535", "OP": "\U0001f534", "BASE": "\U0001f7e3"}.get(alert.get("chain_label", "ETH"), "\u26d3\ufe0f")
    sev_emoji = {"EXTREME": "\U0001f6a8", "STRONG": "\u26a0\ufe0f", "WATCH": "\U0001f440", "WEAK": "\u2022"}.get(alert.get("severity", "WATCH"), "\u2022")
    dir_emoji = {"BULLISH": "\U0001f7e2", "BEARISH": "\U0001f534", "NEUTRAL": "\u26aa"}.get(alert.get("direction", "NEUTRAL"), "\u26aa")

    lines = [
        f"{sev_emoji} <b>{alert.get('signal_type', 'SIGNAL').replace('_', ' ')}</b>  {dir_emoji}",
        f"{chain_emoji} <b>{alert.get('chain_label', 'ETH')}</b>  |  Score: <b>{alert.get('score', 0)}</b>",
    ]

    if alert.get("entity"):
        lines.append(f"Entity: <b>{alert['entity']}</b>  ({alert.get('entity_type', '')})")

    if alert.get("amount_eth", 0) > 0:
        amt = alert["amount_eth"]
        amt_str = f"{amt / 1000:.1f}k ETH" if amt >= 1000 else f"{amt:.1f} ETH"
        lines.append(f"Amount: <b>{amt_str}</b>")
        if alert.get("tx_count", 0) > 1:
            lines[-1] += f"  ({alert['tx_count']} tx)"

    if alert.get("drivers"):
        drivers = alert["drivers"]
        if isinstance(drivers, list):
            labels = [d.replace("_", " ").upper() for d in drivers[:3]]
            lines.append(f"Drivers: {' | '.join(labels)}")

    if alert.get("detail"):
        lines.append(f"<i>{alert['detail'][:120]}</i>")

    if alert.get("explorer_url"):
        lines.append(f'<a href="{alert["explorer_url"]}">View on Explorer</a>')

    lines.append(f"\nRule: {alert.get('rule_name', '')}")

    return "\n".join(lines)
