"""Top-level `technicalAnalysis`, `sentimentRuntime`, `fractalRuntime` slots.

Each returns either the pre-fetched payload (if non-None and a dict) or
an honest-degraded fallback record matching the EXACT shape the SPA
expects. Mirrors server.py byte-for-byte.
"""
from __future__ import annotations

from typing import Any, Dict

from ..contracts import HomeContext


def ta_slot(ctx: HomeContext) -> Dict[str, Any]:
    if isinstance(ctx.ta_payload, dict):
        return ctx.ta_payload
    return {
        "symbol": (ctx.asset or "").upper(),
        "ok": False,
        "state": "unavailable",
        "direction": "WAIT",
        "confidence": 0.0,
        "degraded": True,
        "reason": "ta_service_unavailable",
        "source": "native_ta_v1",
    }


def sentiment_slot(ctx: HomeContext) -> Dict[str, Any]:
    if isinstance(ctx.sentiment_payload, dict):
        return ctx.sentiment_payload
    return {
        "symbol": (ctx.asset or "").upper(),
        "ok": False,
        "degraded": True,
        "state": "unavailable",
        "direction": "WAIT",
        "score": 0.0,
        "confidence": 0.0,
        "pressure": "balanced",
        "crowd": {"bullishShare": 0.0, "bearishShare": 0.0, "neutralShare": 0.0},
        "fearEuphoria": "unknown",
        "sample": 0,
        "reason": ["sentiment_runtime_unavailable"],
        "source": "sentiment_events",
    }


def fractal_slot(ctx: HomeContext) -> Dict[str, Any]:
    if isinstance(ctx.fractal_payload, dict):
        return ctx.fractal_payload
    return {
        "symbol": (ctx.asset or "").upper(),
        "ok": False,
        "degraded": True,
        "state": "unavailable",
        "direction": "WAIT",
        "confidence": 0.0,
        "phase": "unavailable",
        "structure": {
            "trend": "neutral", "breakoutRisk": "low",
            "breakdownRisk": "low", "rangeQuality": "weak",
        },
        "evidence": {"snapshots": 0, "microSnapshots": 0, "decisionHistory": 0, "telemetry": 0},
        "reasons": ["fractal_runtime_unavailable"],
        "source": "snapshot_memory",
    }
