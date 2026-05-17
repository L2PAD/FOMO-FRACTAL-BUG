"""
Alert Engine — creates decision-grade alerts with actionability scores.

Each alert has:
  - type, priority, severity
  - title, summary
  - actionability score (0-1)
  - meta (action, size, entry_action, repricing_state)
"""
import os
from datetime import datetime, timezone
from pymongo import MongoClient


def _col():
    db = MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "intelligence_engine")]
    return db["prediction_alerts"]


def create_alert(case: dict, trigger: dict) -> dict:
    """
    Create a structured alert from a case and trigger.

    Returns alert dict (also stored in MongoDB).
    """
    alert_type = trigger.get("alert_type", "unknown")
    priority = trigger.get("priority", "low")
    transition = trigger.get("transition", {})

    question = case.get("question", "")[:120]
    market_id = case.get("market_id", "")
    reco = case.get("recommendation", {})
    sizing = case.get("sizing", {})
    entry = case.get("entry_timing", {})
    repricing = case.get("repricing", {})
    analysis = case.get("analysis", {})

    title = _build_title(alert_type, question, transition)
    summary = _build_summary(alert_type, case, transition)
    actionability = _compute_actionability(case)

    alert = {
        "market_id": market_id,
        "alert_type": alert_type,
        "priority": priority,
        "title": title,
        "summary": summary,
        "actionability": actionability,
        "transition": {
            "field": transition.get("field"),
            "from": transition.get("from"),
            "to": transition.get("to"),
        },
        "meta": {
            "action": reco.get("action"),
            "conviction": reco.get("conviction"),
            "size": sizing.get("size"),
            "size_fraction": sizing.get("size_fraction"),
            "entry_action": entry.get("entry_action"),
            "repricing_state": repricing.get("repricing_state"),
            "edge": analysis.get("net_edge"),
            "confidence": analysis.get("model_confidence"),
        },
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    # Persist
    _col().insert_one({**alert, "_stored": True})

    # Remove _id for response
    alert.pop("_id", None)
    alert.pop("_stored", None)
    return alert


def get_recent_alerts(limit: int = 50) -> list[dict]:
    """Get recent alerts, newest first."""
    docs = list(_col().find({}, {"_id": 0, "_stored": 0}).sort("created_at", -1).limit(limit))
    return docs


def _compute_actionability(case: dict) -> float:
    """
    Actionability = how urgently should the user act on this.

    Formula: edge * 0.3 + confidence * 0.25 + urgency * 0.2 + alignment * 0.15 - pricing_penalty * 0.1
    """
    a = case.get("analysis", {})
    entry = case.get("entry_timing", {})
    repricing = case.get("repricing", {})

    edge = abs(a.get("net_edge", 0))
    confidence = a.get("model_confidence", 0)
    alignment = a.get("alignment_score", 0)
    pricing_penalty = repricing.get("pricing_penalty", 0)

    urgency_map = {"high": 1.0, "medium": 0.5, "low": 0.2}
    urgency = urgency_map.get(entry.get("urgency", "low"), 0.2)

    score = (
        min(edge / 0.15, 1.0) * 0.30
        + confidence * 0.25
        + urgency * 0.20
        + alignment * 0.15
        - pricing_penalty * 0.10
    )
    return round(max(0, min(1, score)), 4)


def _build_title(alert_type: str, question: str, transition: dict) -> str:
    short_q = question[:60]
    templates = {
        "entry_window_open": f"Entry window opened: {short_q}",
        "entry_window_closed": f"Entry degraded: {short_q}",
        "watch_to_actionable": f"Now actionable: {short_q}",
        "new_mispricing": f"Fresh mispricing: {short_q}",
        "repricing_started": f"Repricing started: {short_q}",
        "overheated": f"Overheated: {short_q}",
        "thesis_weakened": f"Thesis degraded: {short_q}",
        "size_upgraded": f"Size upgraded: {short_q}",
        "size_downgraded": f"Size downgraded: {short_q}",
        "new_market": f"New market detected: {short_q}",
    }
    return templates.get(alert_type, f"Update: {short_q}")


def _build_summary(alert_type: str, case: dict, transition: dict) -> str:
    a = case.get("analysis", {})
    reco = case.get("recommendation", {})
    sizing = case.get("sizing", {})
    entry = case.get("entry_timing", {})

    edge = a.get("net_edge", 0)
    conf = a.get("model_confidence", 0)

    if alert_type == "entry_window_open":
        return f"Edge {edge:+.0%}, confidence {conf:.0%}. {entry.get('note', '')} Action: {reco.get('action')}, size: {sizing.get('size')}."

    if alert_type == "watch_to_actionable":
        return f"Upgraded to {reco.get('action')}. Edge {edge:+.0%}, confidence {conf:.0%}."

    if alert_type == "new_mispricing":
        return f"Fresh mispricing detected. Edge {edge:+.0%}. Market hasn't started repricing."

    if alert_type == "thesis_weakened":
        fr = transition.get("from", "?")
        to = transition.get("to", "?")
        return f"Recommendation changed {fr} → {to}. Review position."

    if alert_type == "overheated":
        return f"Market appears overheated. Remaining edge {edge:+.0%}. Consider avoiding new entry."

    return f"Market state changed. Current: {reco.get('action')} {sizing.get('size')}."
