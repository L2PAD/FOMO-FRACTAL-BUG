"""
Top-level Home Composer — Phase D Pass 3.

This is the ONLY place in the home_composer package that is allowed to
call cognition entry points (analyze / runtime / generate_signal /
build_horizon_forecasts / build_prediction_payload / market_prices.get_price).
This is the orchestration boundary.

Module adapters under .modules/ are assembly-only (A10).

The function `compose(asset)` returns a dict that is byte-level identical
to the original /api/miniapp/home `result` block in server.py (the dict
that gets merged with {"ok": True}). The HTTP route in server.py still
owns the response envelope and exception fallback to home_builder.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from .contracts import HomeContext
from .modules import (
    cognition_slots,
    decision_module,
    pressure_module,
    price_module,
    signal_module,
    structure_module,
)

logger = logging.getLogger(__name__)


# ─── ORCHESTRATION BOUNDARY — these helpers are the ONLY allowed callers
#     of analyze() / runtime() / generate_signal() / build_*() in the
#     home_composer package. Module adapters never touch them. ─────────


def _fetch_sig(asset: str) -> Dict[str, Any]:
    from services.signals_service import generate_signal
    return generate_signal(asset.upper())


def _fetch_ta(asset: str) -> Optional[Dict[str, Any]]:
    try:
        from services.technical_analysis import analyze as _ta_analyze
        return _ta_analyze(asset)
    except Exception:
        return None


def _fetch_sentiment(asset: str) -> Optional[Dict[str, Any]]:
    try:
        from services.sentiment_runtime import runtime as _sr_runtime
        return _sr_runtime(asset)
    except Exception:
        return None


def _fetch_fractal(asset: str) -> Optional[Dict[str, Any]]:
    try:
        from services.fractal_runtime import runtime as _fr_runtime
        return _fr_runtime(asset)
    except Exception:
        return None


def _fetch_live_price(cur_price: float, asset: str) -> Optional[float]:
    """Only used when sig.price is missing — mirrors server.py exactly."""
    if cur_price and cur_price > 0:
        return None
    try:
        from services.market_prices import get_price as _mp_get_price
        live = _mp_get_price(asset)
        if live.get("ok") and live.get("price"):
            return float(live["price"])
    except Exception:
        pass
    return None


def _fetch_metabrain(asset: str) -> Optional[Dict[str, Any]]:
    try:
        from services.meta_brain_service import build_horizon_forecasts
        return build_horizon_forecasts(asset.upper()) or {}
    except Exception as e:
        logger.warning(f"home_composer MetaBrain enrichment failed: {e}")
        return None


def _fetch_prediction(asset: str) -> Optional[Dict[str, Any]]:
    try:
        from services.prediction_chart_service import build_prediction_payload as _bpp
        return _bpp(asset.upper(), "30D", "FREE") or {}
    except Exception as e:
        logger.warning(f"home_composer prediction chart enrichment failed: {e}")
        return None


# ─── compose() — public entrypoint ──────────────────────────────────


def compose(asset: str) -> Dict[str, Any]:
    """
    Build the /api/miniapp/home `result` dict.

    Discipline:
      - The route handler in server.py wraps the return value with
        `{"ok": True, **result}` exactly as before. This function returns
        ONLY the inner result.
      - On any unrecoverable error, the route handler falls back to
        miniapp.home_builder.build_home() (legacy). This function does
        NOT wrap its own catch — propagate exceptions cleanly.
      - All cognition fetches happen here (orchestration boundary).
      - Module adapters in .modules/ are pure assembly only.

    Returns a dict with the EXACT same top-level keys as the original
    server.py block (asset, price, decision, actionPlan, signal,
    structure, technicalAnalysis, sentimentRuntime, fractalRuntime,
    pressure, marketStory, why, truth, entryWindow, conflict,
    generated_at).
    """

    # ── Fetch layer (orchestration boundary) ────────────────────────
    sig = _fetch_sig(asset)
    ta_payload = _fetch_ta(asset)
    sentiment_payload = _fetch_sentiment(asset)
    fractal_payload = _fetch_fractal(asset)

    # Resolve current price (sig + CG fallback)
    raw_price = sig.get("price", 0) or 0
    try:
        raw_price = float(raw_price)
    except (TypeError, ValueError):
        raw_price = 0
    live_price = _fetch_live_price(raw_price, asset)

    # MetaBrain + Prediction (best-effort, may return None / {})
    metabrain = _fetch_metabrain(asset)
    prediction = _fetch_prediction(asset)

    # Build context
    ctx = HomeContext(
        asset=asset,
        sig=sig,
        ta_payload=ta_payload,
        sentiment_payload=sentiment_payload,
        fractal_payload=fractal_payload,
        metabrain=metabrain,
        prediction=prediction,
        live_price=live_price,
    )

    # ── Assembly layer (pure) ───────────────────────────────────────
    cur_price = price_module.assemble(ctx)
    enrichment = decision_module.compute_metabrain_enrichment(ctx, cur_price)

    return {
        "asset": asset.upper(),
        "price": cur_price,
        "decision": decision_module.assemble_decision(ctx, enrichment),
        "actionPlan": decision_module.assemble_action_plan(ctx),
        "signal": signal_module.assemble_signal_card(ctx),
        "structure": structure_module.assemble(ctx, enrichment["confidence_01"]),
        "technicalAnalysis": cognition_slots.ta_slot(ctx),
        "sentimentRuntime": cognition_slots.sentiment_slot(ctx),
        "fractalRuntime": cognition_slots.fractal_slot(ctx),
        "pressure": pressure_module.assemble(ctx),
        "marketStory": signal_module.assemble_market_story(ctx),
        "why": signal_module.assemble_why(ctx),
        "truth": signal_module.assemble_truth(ctx),
        "entryWindow": signal_module.assemble_entry_window(ctx),
        "conflict": signal_module.assemble_conflict(ctx),
        "generated_at": signal_module.assemble_generated_at(ctx),
    }
