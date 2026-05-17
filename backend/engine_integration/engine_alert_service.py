"""
Engine Alert Service — E6
===========================
Event-driven alert system that detects CHANGES in engine state.
Compares current engine output with previous snapshot to generate alerts.

Key principle: Alerts react to state TRANSITIONS, not current state.

Collections:
  - engine_state_snapshots: stores engine state for comparison
  - engine_alerts: stores generated alert events

10 alert types, 4 severity levels, deduplication via alert_hash, auto-expiry.
"""

import os
import hashlib
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient

_client = None
_db = None


def _get_db():
    global _client, _db
    if _db is None:
        _client = MongoClient(os.environ.get("MONGO_URL"))
        _db = _client[os.environ.get("DB_NAME", "test_database")]
    return _db


# ── Expiry durations by severity ──
EXPIRY_HOURS = {
    "INFO": 1,
    "WATCH": 2,
    "IMPORTANT": 6,
    "CRITICAL": 12,
}

# ── Deduplication window (minutes) ──
DEDUP_MINUTES = 30


def _make_hash(asset: str, alert_type: str, detail: str) -> str:
    raw = f"{asset}_{alert_type}_{detail}"
    return hashlib.md5(raw.encode()).hexdigest()


def _is_duplicate(db, alert_hash: str) -> bool:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=DEDUP_MINUTES)
    existing = db["engine_alerts"].find_one(
        {"alert_hash": alert_hash, "timestamp": {"$gte": cutoff.isoformat()}},
        {"_id": 0, "alert_hash": 1},
    )
    return existing is not None


def _create_alert(
    alert_type: str,
    severity: str,
    message: str,
    confidence: float,
    asset: str = "BTC",
    detail: str = "",
) -> dict:
    now = datetime.now(timezone.utc)
    expiry_h = EXPIRY_HOURS.get(severity, 2)
    expires_at = now + timedelta(hours=expiry_h)

    return {
        "type": alert_type,
        "severity": severity,
        "asset": asset,
        "message": message,
        "confidence": round(confidence, 3),
        "event_category": _categorize_alert(alert_type),
        "impact_score": _impact_score(severity, confidence),
        "timestamp": now.isoformat(),
        "expires_at": expires_at.isoformat(),
        "alert_hash": _make_hash(asset, alert_type, detail),
    }


# ── Event categorization ──
CATEGORY_MAP = {
    "decision_change": "critical",
    "regime_shift": "critical",
    "setup_upgrade": "setup",
    "setup_failure": "setup",
    "probability_shift": "setup",
    "actor_conflict": "actor",
    "otc_trade": "actor",
    "flow_acceleration": "flow",
    "liquidity_target": "liquidity",
    "risk_increase": "critical",
}


def _categorize_alert(alert_type: str) -> str:
    return CATEGORY_MAP.get(alert_type, "critical")


def _impact_score(severity: str, confidence: float) -> str:
    sev_weight = {"CRITICAL": 1.0, "IMPORTANT": 0.7, "WATCH": 0.4, "INFO": 0.2}
    score = sev_weight.get(severity, 0.3) * 0.6 + confidence * 0.4
    if score >= 0.7:
        return "HIGH"
    if score >= 0.4:
        return "MEDIUM"
    return "LOW"


# ══════════════════════════════════════════════════════════
#  DETECTORS
# ══════════════════════════════════════════════════════════


def detect_decision_change(prev: dict, curr: dict) -> list:
    """CRITICAL: Decision changed (BUY→NEUTRAL, NEUTRAL→SELL, etc.)."""
    alerts = []
    old_d = prev.get("decision", "")
    new_d = curr.get("decision", "")

    if old_d and new_d and old_d != new_d:
        conf = curr.get("confidence", {}).get("score", 0) / 100
        alerts.append(_create_alert(
            "decision_change",
            "CRITICAL",
            f"Decision changed: {old_d} → {new_d}",
            conf,
            detail=f"{old_d}_{new_d}",
        ))
    return alerts


def detect_regime_shift(prev: dict, curr: dict) -> list:
    """CRITICAL (major) / INFO (minor): Regime changed."""
    alerts = []
    old_r = prev.get("regime", "")
    new_r = curr.get("regime", "")
    old_rs = prev.get("regime_status", "")
    new_rs = curr.get("regime_status", "")

    if old_r and new_r and old_r != new_r:
        # Major shifts
        major_pairs = [
            ("bull_trend", "bear_trend"),
            ("bear_trend", "bull_trend"),
            ("accumulation", "distribution"),
            ("distribution", "accumulation"),
        ]
        is_major = (old_r, new_r) in major_pairs
        severity = "CRITICAL" if is_major else "INFO"
        conf = curr.get("regime_confidence", 0.5)

        old_label = old_r.replace("_", " ").title()
        new_label = new_r.replace("_", " ").title()
        alerts.append(_create_alert(
            "regime_shift",
            severity,
            f"Regime shifted: {old_label} → {new_label}",
            conf,
            detail=f"{old_r}_{new_r}",
        ))
    elif old_r == new_r and old_rs and new_rs and old_rs != new_rs:
        # Status change within same regime
        label = new_r.replace("_", " ").title()
        alerts.append(_create_alert(
            "regime_shift",
            "INFO",
            f"{label} regime status: {old_rs} → {new_rs}",
            0.5,
            detail=f"{new_r}_{old_rs}_{new_rs}",
        ))
    return alerts


def detect_setup_upgrade(prev: dict, curr: dict) -> list:
    """IMPORTANT: Setup status improved (forming→confirmed, weak→active)."""
    alerts = []
    old_s = prev.get("setup_status", "")
    new_s = curr.get("setup_status", "")
    setup_type = curr.get("setup", "mixed")

    upgrade_transitions = [
        ("weak", "forming"),
        ("weak", "active"),
        ("weak", "confirmed"),
        ("forming", "active"),
        ("forming", "confirmed"),
        ("active", "confirmed"),
    ]

    if old_s and new_s and (old_s, new_s) in upgrade_transitions:
        conf = curr.get("setup_confidence", 0.5)
        label = setup_type.replace("_", " ").title()
        alerts.append(_create_alert(
            "setup_upgrade",
            "IMPORTANT",
            f"{label} upgraded: {old_s} → {new_s}",
            conf,
            detail=f"{setup_type}_{old_s}_{new_s}",
        ))
    return alerts


def detect_setup_failure(prev: dict, curr: dict) -> list:
    """CRITICAL: Setup was strong but now failed/changed."""
    alerts = []
    old_s = prev.get("setup_status", "")
    new_s = curr.get("setup_status", "")
    old_type = prev.get("setup", "")
    new_type = curr.get("setup", "")

    # Setup type changed from strong to different
    if old_type and new_type and old_type != new_type:
        if old_s in ("confirmed", "active"):
            old_label = old_type.replace("_", " ").title()
            new_label = new_type.replace("_", " ").title()
            alerts.append(_create_alert(
                "setup_failure",
                "CRITICAL",
                f"Setup failed: {old_label} ({old_s}) → {new_label}",
                0.7,
                detail=f"{old_type}_{new_type}",
            ))

    # Status downgrade within same setup
    downgrade_transitions = [
        ("confirmed", "active"),
        ("confirmed", "forming"),
        ("confirmed", "weak"),
        ("active", "forming"),
        ("active", "weak"),
    ]
    if old_type == new_type and old_s and new_s and (old_s, new_s) in downgrade_transitions:
        label = new_type.replace("_", " ").title()
        alerts.append(_create_alert(
            "setup_failure",
            "IMPORTANT",
            f"{label} weakened: {old_s} → {new_s}",
            0.6,
            detail=f"{new_type}_{old_s}_{new_s}",
        ))

    return alerts


def detect_probability_shift(prev: dict, curr: dict) -> list:
    """WATCH: Significant probability change (>15%)."""
    alerts = []
    old_prob = prev.get("probability", {})
    new_prob = curr.get("probability", {})

    for key, label in [("continuation", "Continuation"), ("failure", "Failure")]:
        old_v = old_prob.get(key, 0)
        new_v = new_prob.get(key, 0)
        if old_v > 0 and new_v > 0:
            delta = new_v - old_v
            if abs(delta) >= 0.15:
                direction = "increased" if delta > 0 else "decreased"
                pct_old = round(old_v * 100)
                pct_new = round(new_v * 100)
                alerts.append(_create_alert(
                    "probability_shift",
                    "WATCH",
                    f"{label} probability {direction}: {pct_old}% → {pct_new}%",
                    new_v,
                    detail=f"{key}_{pct_old}_{pct_new}",
                ))
    return alerts


def detect_actor_conflict(curr_engine: dict) -> list:
    """IMPORTANT: Actor conflict setup detected."""
    alerts = []
    setup_engine = curr_engine.get("setup_engine", {})
    primary = setup_engine.get("primary", {})

    if primary.get("type") == "actor_conflict" and primary.get("status") in ("confirmed", "active"):
        conf = primary.get("confidence", 0.5)
        alerts.append(_create_alert(
            "actor_conflict",
            "IMPORTANT",
            f"Actor conflict detected ({primary.get('status')}) — key entities disagree on direction",
            conf,
            detail="actor_conflict_active",
        ))
    return alerts


def detect_otc_event(curr_engine: dict) -> list:
    """INFO: OTC trades detected."""
    alerts = []
    otc = curr_engine.get("otc_mm_influence", {})

    if otc.get("otc_bias") != "neutral" and otc.get("confidence_adjustment", 0) != 0:
        bias = otc.get("otc_bias", "neutral")
        drivers = otc.get("drivers", [])
        msg = drivers[0] if drivers else f"OTC activity detected ({bias} bias)"
        alerts.append(_create_alert(
            "otc_trade",
            "INFO",
            msg,
            0.5,
            detail=f"otc_{bias}",
        ))
    return alerts


def detect_flow_acceleration(prev: dict, curr: dict) -> list:
    """WATCH/IMPORTANT: Flow state changed."""
    alerts = []
    old_flow = prev.get("flow_state", "neutral")
    new_flow = curr.get("flow_state", "neutral")

    if old_flow != new_flow:
        # Starting acceleration is more important
        if new_flow in ("bullish_acceleration", "bearish_acceleration") and old_flow == "neutral":
            label = new_flow.replace("_", " ").title()
            alerts.append(_create_alert(
                "flow_acceleration",
                "IMPORTANT",
                f"Flow acceleration started: {label}",
                0.6,
                detail=f"flow_{old_flow}_{new_flow}",
            ))
        elif new_flow == "flow_exhaustion":
            alerts.append(_create_alert(
                "flow_acceleration",
                "WATCH",
                "Flow momentum exhausting — velocity declining",
                0.5,
                detail=f"flow_{old_flow}_{new_flow}",
            ))
        elif new_flow == "neutral" and old_flow != "neutral":
            old_label = old_flow.replace("_", " ").title()
            alerts.append(_create_alert(
                "flow_acceleration",
                "WATCH",
                f"Flow acceleration stopped: {old_label} → Neutral",
                0.4,
                detail=f"flow_{old_flow}_{new_flow}",
            ))
    return alerts


def detect_liquidity_proximity(curr_engine: dict) -> list:
    """IMPORTANT: High-confidence liquidity targets."""
    alerts = []
    liq = curr_engine.get("liquidity_map", {})
    targets = liq.get("target_zones", [])

    for t in targets:
        if t.get("confidence", 0) >= 0.7:
            direction = t.get("direction", "neutral")
            reason = t.get("reason", "liquidity target")
            alerts.append(_create_alert(
                "liquidity_target",
                "IMPORTANT",
                f"Liquidity target ({direction}): {reason}",
                t["confidence"],
                detail=f"liq_{direction}_{reason[:20]}",
            ))
            break  # Only one target alert at a time
    return alerts


def detect_risk_increase(prev: dict, curr: dict) -> list:
    """WATCH: Risk level increased."""
    alerts = []
    old_risk = prev.get("risk_status", "LOW")
    new_risk = curr.get("risk_status", "LOW")

    risk_order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
    if risk_order.get(new_risk, 0) > risk_order.get(old_risk, 0):
        alerts.append(_create_alert(
            "risk_increase",
            "WATCH",
            f"Risk level increased: {old_risk} → {new_risk}",
            0.6,
            detail=f"risk_{old_risk}_{new_risk}",
        ))
    return alerts


# ══════════════════════════════════════════════════════════
#  SNAPSHOT MANAGEMENT
# ══════════════════════════════════════════════════════════


def _extract_snapshot(engine_data: dict) -> dict:
    """Extract comparison-relevant fields from engine output."""
    regime_primary = engine_data.get("regime_engine", {}).get("primary", {})
    setup_primary = engine_data.get("setup_engine", {}).get("primary", {})
    prob = engine_data.get("probability_layer", {})
    flow = engine_data.get("flow_engine", {})

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "decision": engine_data.get("decision", "NEUTRAL"),
        "setup": setup_primary.get("type", "mixed"),
        "setup_status": setup_primary.get("status", "weak"),
        "setup_confidence": setup_primary.get("confidence", 0),
        "regime": regime_primary.get("type", "neutral_chop"),
        "regime_status": regime_primary.get("status", "weak"),
        "regime_confidence": regime_primary.get("confidence", 0),
        "probability": {
            "continuation": prob.get("continuation", 0),
            "failure": prob.get("failure", 0),
            "upgrade": prob.get("upgrade", 0),
        },
        "flow_state": flow.get("state", "neutral"),
        "composite": engine_data.get("scores", {}).get("composite", 50),
        "confidence_score": engine_data.get("confidence", {}).get("score", 0),
        "risk_status": engine_data.get("gates", {}).get("risk", {}).get("status", "LOW"),
    }


def _get_previous_snapshot(db) -> dict:
    """Get the most recent snapshot from MongoDB."""
    doc = db["engine_state_snapshots"].find_one(
        {}, {"_id": 0}, sort=[("timestamp", -1)]
    )
    return doc or {}


def _save_snapshot(db, snapshot: dict):
    """Save current snapshot. Keep only last 100."""
    db["engine_state_snapshots"].insert_one(snapshot)
    count = db["engine_state_snapshots"].count_documents({})
    if count > 100:
        oldest = db["engine_state_snapshots"].find(
            {}, {"_id": 1}, sort=[("timestamp", 1)]
        ).limit(count - 100)
        ids = [d["_id"] for d in oldest]
        if ids:
            db["engine_state_snapshots"].delete_many({"_id": {"$in": ids}})


# ══════════════════════════════════════════════════════════
#  MAIN ENTRY
# ══════════════════════════════════════════════════════════


def generate_alerts(engine_data: dict) -> list:
    """
    Main entry point — compare current engine state with previous,
    detect changes, generate alerts, save to MongoDB.
    Returns list of new + recent active alerts (max 10).
    """
    db = _get_db()

    # Extract current snapshot
    curr_snapshot = _extract_snapshot(engine_data)

    # Get previous snapshot
    prev_snapshot = _get_previous_snapshot(db)

    # Run all detectors
    new_alerts = []

    # Change-based detectors (need prev vs curr)
    if prev_snapshot:
        new_alerts.extend(detect_decision_change(prev_snapshot, curr_snapshot))
        new_alerts.extend(detect_regime_shift(prev_snapshot, curr_snapshot))
        new_alerts.extend(detect_setup_upgrade(prev_snapshot, curr_snapshot))
        new_alerts.extend(detect_setup_failure(prev_snapshot, curr_snapshot))
        new_alerts.extend(detect_probability_shift(prev_snapshot, curr_snapshot))
        new_alerts.extend(detect_flow_acceleration(prev_snapshot, curr_snapshot))
        new_alerts.extend(detect_risk_increase(prev_snapshot, curr_snapshot))

    # State-based detectors (only need current)
    new_alerts.extend(detect_actor_conflict(engine_data))
    new_alerts.extend(detect_otc_event(engine_data))
    new_alerts.extend(detect_liquidity_proximity(engine_data))

    # Deduplicate and save
    saved = []
    for alert in new_alerts:
        if not _is_duplicate(db, alert["alert_hash"]):
            db["engine_alerts"].insert_one(alert)
            # Remove _id for response
            alert.pop("_id", None)
            saved.append(alert)

    # Save current snapshot
    _save_snapshot(db, curr_snapshot)

    # Return recent active (non-expired) alerts
    now = datetime.now(timezone.utc).isoformat()
    active_alerts = list(
        db["engine_alerts"].find(
            {"expires_at": {"$gte": now}},
            {"_id": 0},
        ).sort("timestamp", -1).limit(10)
    )

    return active_alerts


def get_all_alerts(limit: int = 50) -> list:
    """Get all active (non-expired) alerts for the dedicated endpoint."""
    db = _get_db()
    now = datetime.now(timezone.utc).isoformat()
    alerts = list(
        db["engine_alerts"].find(
            {"expires_at": {"$gte": now}},
            {"_id": 0},
        ).sort("timestamp", -1).limit(limit)
    )
    return alerts
