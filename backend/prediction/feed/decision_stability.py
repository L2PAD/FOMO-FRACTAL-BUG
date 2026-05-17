"""
Decision Stability — prevents UI flickering (BUY → WATCH → BUY).

Implements:
  1. Sticky layer: keep decision if edge/conf delta < threshold
  2. Flip protection: lock if > 2 flips in 3 min
  3. Direction protection: ignore YES→NO flip if conf < threshold
  4. BUY protection: keep BUY if edge still decent

Uses MongoDB `decision_states` collection for tracking.
Pipeline position: LAST layer, after decision gate + sizing.
"""
import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger("feed.decision_stability")

# Thresholds
EDGE_DELTA_STICKY = 0.02    # edge must change by > 2% to update
CONF_DELTA_STICKY = 0.03    # confidence must change by > 3%
FLIP_WINDOW = 180            # 3 minutes in seconds
MAX_FLIPS = 2                # lock after this many flips
LOCK_DURATION = 120          # lock for 2 minutes
BUY_PROTECT_EDGE = 0.05     # keep BUY if edge > 5%
DIR_FLIP_CONF_THRESHOLD = 0.65  # only allow YES→NO if conf > this


def apply_stability(
    market_id: str,
    new_action: str,
    new_urgency: str,
    new_edge: float,
    new_confidence: float,
    new_size_label: str,
    db,
) -> dict:
    """Apply decision stability to the final decision.

    Returns:
        action: str (possibly overridden)
        urgency: str
        edge: float
        size_label: str
        stability_state: STABLE | UNSTABLE | LOCKED
        stability_reasons: list[str]
    """
    if db is None:
        return _passthrough(new_action, new_urgency, new_edge, new_size_label, "STABLE")

    now = datetime.now(timezone.utc)
    reasons = []

    # Load previous state
    prev = _get_state(market_id, db)

    if not prev:
        # First time seeing this market — save and pass through
        _upsert_state(market_id, new_action, new_urgency, new_edge,
                       new_confidence, new_size_label, now, 0, None, db)
        return _passthrough(new_action, new_urgency, new_edge, new_size_label, "STABLE")

    prev_action = prev.get("last_action", "WATCH")
    prev_urgency = prev.get("last_urgency", "watch")
    prev_edge = prev.get("last_edge", 0)
    prev_conf = prev.get("last_confidence", 0)
    prev_size = prev.get("last_size_label", "NONE")
    flip_count = prev.get("flip_count", 0)
    locked_until = prev.get("locked_until")
    last_updated = prev.get("last_updated_at")

    # ── Check LOCK ──
    if locked_until:
        try:
            lock_time = datetime.fromisoformat(str(locked_until).replace("Z", "+00:00"))
            if now < lock_time:
                reasons.append("DECISION_LOCKED")
                return _passthrough(prev_action, prev_urgency, prev_edge,
                                     prev_size, "LOCKED", reasons)
        except Exception:
            pass

    # ── Sticky layer: ignore tiny changes ──
    edge_delta = abs(new_edge - prev_edge)
    conf_delta = abs(new_confidence - prev_conf)
    action_changed = new_action != prev_action

    if not action_changed and edge_delta < EDGE_DELTA_STICKY and conf_delta < CONF_DELTA_STICKY:
        # No meaningful change — keep previous
        return _passthrough(prev_action, prev_urgency, prev_edge,
                             prev_size, "STABLE", ["STICKY_NO_CHANGE"])

    # ── BUY protection ──
    # If was BUY and now WATCH, but edge still decent → keep BUY
    if (prev_action in ("BUY_YES", "BUY_NO") and
            new_action == "WATCH" and
            abs(new_edge) > BUY_PROTECT_EDGE):
        reasons.append("BUY_PROTECTED")
        _upsert_state(market_id, prev_action, prev_urgency, new_edge,
                       new_confidence, prev_size, now, flip_count, locked_until, db)
        return _passthrough(prev_action, prev_urgency, new_edge,
                             prev_size, "STABLE", reasons)

    # ── Direction protection ──
    # YES → NO or NO → YES flip: only if confidence is high
    is_direction_flip = (
        (prev_action == "BUY_YES" and new_action == "BUY_NO") or
        (prev_action == "BUY_NO" and new_action == "BUY_YES")
    )
    if is_direction_flip and new_confidence < DIR_FLIP_CONF_THRESHOLD:
        reasons.append("DIR_FLIP_BLOCKED")
        _upsert_state(market_id, prev_action, prev_urgency, prev_edge,
                       prev_conf, prev_size, now, flip_count, locked_until, db)
        return _passthrough(prev_action, prev_urgency, prev_edge,
                             prev_size, "STABLE", reasons)

    # ── Flip protection ──
    if action_changed:
        # Count recent flips
        if last_updated:
            try:
                last_ts = datetime.fromisoformat(str(last_updated).replace("Z", "+00:00"))
                if (now - last_ts).total_seconds() < FLIP_WINDOW:
                    flip_count += 1
                else:
                    flip_count = 1  # Reset: long time since last change
            except Exception:
                flip_count = 1
        else:
            flip_count = 1

        if flip_count >= MAX_FLIPS:
            # LOCK the decision
            lock_until = (now + timedelta(seconds=LOCK_DURATION)).isoformat()
            reasons.append("FLIP_LOCKED")
            _upsert_state(market_id, prev_action, prev_urgency, prev_edge,
                           prev_conf, prev_size, now, flip_count, lock_until, db)
            return _passthrough(prev_action, prev_urgency, prev_edge,
                                 prev_size, "LOCKED", reasons)

    # ── Accept the new decision ──
    _upsert_state(market_id, new_action, new_urgency, new_edge,
                   new_confidence, new_size_label, now, flip_count, None, db)

    stability = "STABLE" if not action_changed else "UNSTABLE"
    return _passthrough(new_action, new_urgency, new_edge, new_size_label, stability, reasons)


def _get_state(market_id: str, db) -> dict | None:
    """Load previous decision state."""
    try:
        return db.decision_states.find_one(
            {"market_id": market_id}, {"_id": 0}
        )
    except Exception:
        return None


def _upsert_state(market_id: str, action: str, urgency: str, edge: float,
                   confidence: float, size_label: str,
                   now: datetime, flip_count: int, locked_until, db):
    """Upsert decision state."""
    try:
        db.decision_states.update_one(
            {"market_id": market_id},
            {"$set": {
                "market_id": market_id,
                "last_action": action,
                "last_urgency": urgency,
                "last_edge": edge,
                "last_confidence": confidence,
                "last_size_label": size_label,
                "last_updated_at": now.isoformat(),
                "flip_count": flip_count,
                "locked_until": locked_until,
            }},
            upsert=True,
        )
    except Exception as e:
        logger.debug(f"Decision state upsert error: {e}")


def _passthrough(action: str, urgency: str, edge: float,
                  size_label: str, stability: str,
                  reasons: list | None = None) -> dict:
    return {
        "action": action,
        "urgency": urgency,
        "edge": edge,
        "size_label": size_label,
        "stability_state": stability,
        "stability_reasons": reasons or [],
    }
