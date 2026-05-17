"""Labs Endpoints (PROD-GAP-1.5)

Explicit experimental registry instead of silent-missing 404s.

The Web Alpha page consumes /api/labs/widgets to discover which
experimental widgets are enabled. We expose a deterministic registry
and explicit feature-flag responses so the UI hook stops emitting
`console.error` and renders a clean disabled state.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Query

router = APIRouter(prefix="/api/labs", tags=["labs"])


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# Static registry. To enable a widget in prod, flip `enabled: True` here
# OR set env LABS_<UPPER_ID>=1.
_REGISTRY: List[Dict[str, Any]] = [
    {
        "id":          "sentiment_interaction_lab",
        "title":       "Sentiment × Price Interaction",
        "description": "Cross-correlation lab between sentiment substrate and price action.",
        "category":    "sentiment",
        "enabled":     False,
        "reason_disabled": "awaiting_sentiment_substrate_p3",
    },
    {
        "id":          "onchain_per_asset_lab",
        "title":       "On-chain Per-Asset Diversification",
        "description": "Asset-specific on-chain consensus, not yet symbol-agnostic.",
        "category":    "onchain",
        "enabled":     False,
        "reason_disabled": "awaiting_onchain_p4",
    },
    {
        "id":          "metabrain_drift_lab",
        "title":       "MetaBrain Drift Detection",
        "description": "Real-time drift signal on MetaBrain consensus stability.",
        "category":    "metabrain",
        "enabled":     False,
        "reason_disabled": "awaiting_calibration_p5",
    },
]


def _is_enabled(item: Dict[str, Any]) -> bool:
    env_key = "LABS_" + item["id"].upper()
    if os.environ.get(env_key, "").strip().lower() in ("1", "true", "on", "yes"):
        return True
    return bool(item.get("enabled", False))


@router.get("/widgets")
def list_widgets(category: str = Query(None)) -> Dict[str, Any]:
    """Return the experimental widget registry.

    Each item has a stable `id`, `enabled` flag and (when disabled)
    a `reason_disabled` slug so the UI can render an informative
    placeholder instead of an error.
    """
    items = list(_REGISTRY)
    if category:
        items = [it for it in items if it.get("category") == category]
    enriched = [{**it, "enabled": _is_enabled(it)} for it in items]
    return {
        "ok":        True,
        "widgets":   enriched,
        "items":     enriched,  # legacy compat shape
        "count":     len(enriched),
        "enabledCount": sum(1 for w in enriched if w["enabled"]),
        "asOf":      _now_iso(),
    }


@router.get("/widgets/{widget_id}")
def get_widget(widget_id: str) -> Dict[str, Any]:
    for it in _REGISTRY:
        if it["id"] == widget_id:
            return {**it, "enabled": _is_enabled(it), "asOf": _now_iso()}
    return {
        "ok":      False,
        "id":      widget_id,
        "error":   "unknown_widget",
        "enabled": False,
        "asOf":    _now_iso(),
    }


@router.get("/health")
def labs_health() -> Dict[str, Any]:
    enabled = [w for w in _REGISTRY if _is_enabled(w)]
    return {
        "ok":           True,
        "totalWidgets": len(_REGISTRY),
        "enabled":      len(enabled),
        "asOf":         _now_iso(),
    }
