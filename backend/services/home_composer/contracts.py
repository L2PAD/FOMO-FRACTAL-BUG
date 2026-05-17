"""
Internal contracts for the Home Composer.

These dataclasses are NOT part of any public API. They are the typed
substrate that composer.compose() hands to module adapters. Modules
return slices of the final dict (matching the existing /api/miniapp/home
schema byte-for-byte).

A canonical CognitionSnapshot (Pass 2A/2B) MAY be embedded here for
internal coherence checks, but the public payload format is unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class HomeContext:
    """
    Pre-fetched cognition payloads for one asset. compose() fills this
    once; assembly modules consume it without ever re-fetching.

    Every field is OPTIONAL — the composer fills what it can; module
    adapters handle missing fields with the same honest-degraded
    fallbacks the original server.py logic used (preserving byte-level
    public payload identity).
    """

    asset: str

    # Primary unified signal (services.signals_service.generate_signal).
    # When this fails the whole orchestration falls back to the legacy
    # miniapp.home_builder.build_home() — same as today.
    sig: Optional[Dict[str, Any]] = None

    # Pre-fetched cognition payloads.
    ta_payload: Optional[Dict[str, Any]] = None
    sentiment_payload: Optional[Dict[str, Any]] = None
    fractal_payload: Optional[Dict[str, Any]] = None

    # MetaBrain enrichment (build_horizon_forecasts output).
    metabrain: Optional[Dict[str, Any]] = None

    # Prediction chart enrichment (build_prediction_payload output).
    prediction: Optional[Dict[str, Any]] = None

    # Live spot price fallback (when sig.price is empty).
    live_price: Optional[float] = None

    # Internal coherence — canonical snapshots for the 7 modules.
    # NOT serialized into the public payload. Used only for discipline
    # checks (e.g. composer must NEVER amplify certainty across modules).
    canonical_snapshots: Dict[str, Any] = field(default_factory=dict)
