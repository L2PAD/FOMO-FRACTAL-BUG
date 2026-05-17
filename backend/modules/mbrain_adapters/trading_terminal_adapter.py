"""
Trading Terminal Adapter — HONEST STUB
=======================================

The F-TRADE-MODULE side-car (host: localhost:8002) and its reverse-proxy
gateway were retired by the Terminal Removal Sprint on 2026-05-12.

This module is intentionally kept (not deleted) because two consumers still
import its public surface:

    * `modules/mbrain_adapters/ta_shadow_fusion.py` → `get_signal`
    * `routes/mbrain_shadow.py`                    → `health`

Rather than break those import paths and the shadow-fusion telemetry surface,
we keep the same function signatures but return the honest "degraded — source
removed" envelope. No HTTP, no network, no side-car contact. The shadow-fusion
pipeline interprets `ok=False` and routes around this adapter without lying
about a "running" TA terminal.

This mirrors the Truthful Degradation contract enforced platform-wide:
when a cognitive source is absent, we say so explicitly and never inflate
confidence or fabricate bias.

Migration record: /app/memory/TERMINAL_REMOVAL_SPRINT_2026-05-12.md
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


# Stable identifier so logs / metrics keep a recognisable source name.
SOURCE_ID: str = "ta_terminal"

# Reason string surfaced to every downstream consumer.
_REMOVED_ERROR: str = "terminal_removed"

_REMOVED_DETAIL: str = (
    "Trading Terminal side-car (F-TRADE-MODULE) was retired on 2026-05-12. "
    "This adapter no longer performs HTTP calls. See "
    "/app/memory/TERMINAL_REMOVAL_SPRINT_2026-05-12.md for the migration "
    "record."
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _removed_envelope(asset: str, horizon: str) -> Dict[str, Any]:
    """Honest degraded envelope mirroring the original shape."""
    return {
        "source":     SOURCE_ID,
        "asset":      (asset or "").upper(),
        "bias":       "neutral",
        "signal":     0.0,
        "confidence": 0.0,
        "weight":     0.0,
        "horizon":    horizon,
        "components": {},
        "timestamp":  _utc_now(),
        "ok":         False,
        "error":      _REMOVED_ERROR,
        "detail":     _REMOVED_DETAIL,
    }


# ──────────────────────────────────────────────────────────────────────────
# Public API — same signatures as the pre-removal adapter, all return
# the honest "removed" envelope.
# ──────────────────────────────────────────────────────────────────────────


def get_signal(
    asset: str,
    horizon: str = "24H",
    *,
    weight: float = 1.0,
    timeframe: Optional[str] = None,
    base_url: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Backwards-compatible public API.

    Always returns the honest "terminal_removed" envelope. No HTTP, no
    side-car contact, no DB read. The shadow-fusion layer recognises
    `ok=False` and routes around this source.
    """
    return _removed_envelope(asset, horizon)


def get_signal_bundle(
    asset: str,
    horizons: Optional[list] = None,
    *,
    weight: float = 1.0,
    timeframe: Optional[str] = None,
    base_url: Optional[str] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Backwards-compatible bundle API. Returns the honest envelope per horizon.
    """
    hs = horizons or ["24H", "7D", "30D"]
    return {h: _removed_envelope(asset, h) for h in hs}


def health() -> Dict[str, Any]:
    """
    Backwards-compatible liveness probe. Always reports `ok=False` with the
    "terminal_removed" reason so dashboards and admin pages render the source
    as deliberately offline rather than transiently failing.
    """
    return {
        "ok":         False,
        "source":     SOURCE_ID,
        "error":      _REMOVED_ERROR,
        "detail":     _REMOVED_DETAIL,
        "gateway":    None,
        "upstream":   None,
        "upstream_ok": False,
        "prefixes_n": 0,
        "timestamp":  _utc_now(),
    }
