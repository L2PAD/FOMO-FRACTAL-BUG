"""
On-Chain Alert Rules API Routes
================================
CRUD for alert rules + evaluation + history.
"""

from fastapi import APIRouter, Query, Path
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/alerts/onchain", tags=["onchain_alerts"])


class RuleCreate(BaseModel):
    name: str
    enabled: bool = True
    conditions: dict = {}
    notify: dict = {"telegram": True, "in_app": True}


class RuleUpdate(BaseModel):
    name: Optional[str] = None
    enabled: Optional[bool] = None
    conditions: Optional[dict] = None
    notify: Optional[dict] = None


@router.get("/rules")
def list_rules():
    """List all alert rules."""
    from .alert_rules import get_rules
    rules = get_rules()
    return JSONResponse(content={"ok": True, "rules": rules, "count": len(rules)})


@router.post("/rules")
def create_rule(body: RuleCreate):
    """Create a new alert rule."""
    from .alert_rules import create_rule as _create
    rule = _create(body.dict())
    return JSONResponse(content={"ok": True, "rule": rule})


@router.put("/rules/{rule_id}")
def update_rule(rule_id: str, body: RuleUpdate):
    """Update an existing alert rule."""
    from .alert_rules import update_rule as _update
    updates = {k: v for k, v in body.dict().items() if v is not None}
    rule = _update(rule_id, updates)
    if not rule:
        return JSONResponse(status_code=404, content={"ok": False, "error": "Rule not found"})
    return JSONResponse(content={"ok": True, "rule": rule})


@router.delete("/rules/{rule_id}")
def delete_rule(rule_id: str):
    """Delete an alert rule."""
    from .alert_rules import delete_rule as _delete
    ok = _delete(rule_id)
    return JSONResponse(content={"ok": ok})


@router.post("/evaluate")
def evaluate_alerts():
    """Manually trigger rule evaluation against current signals."""
    try:
        from .alert_rules import evaluate_rules
        fired = evaluate_rules()
        return JSONResponse(content={
            "ok": True,
            "fired": fired,
            "count": len(fired),
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})


@router.get("/history")
def alert_history(
    limit: int = Query(50, ge=1, le=200),
    unacknowledged: bool = Query(False),
):
    """Get alert history."""
    from .alert_rules import get_alert_history
    alerts = get_alert_history(limit=limit, unacknowledged_only=unacknowledged)
    return JSONResponse(content={"ok": True, "alerts": alerts, "count": len(alerts)})


@router.post("/acknowledge/{dedup_key}")
def acknowledge_alert(dedup_key: str):
    """Acknowledge an alert."""
    from .alert_rules import acknowledge_alert as _ack
    ok = _ack(dedup_key)
    return JSONResponse(content={"ok": ok})


@router.get("/stats")
def alert_stats():
    """Get alert statistics."""
    from .alert_rules import get_alert_stats
    stats = get_alert_stats()
    return JSONResponse(content={"ok": True, **stats})
