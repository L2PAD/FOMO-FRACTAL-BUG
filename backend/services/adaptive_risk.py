"""
adaptive_risk — T8 · Adaptive Capital Restraint Layer.

NOT a risk optimizer. NOT a returns booster. NOT a sizing "AI".

This module's *only* job is to shrink (or zero) the deployed size when
the epistemic state degrades. It can never increase past the structural
baseline by more than a tight pre-multiplier ceiling (1.25x at most for
each individual scale), and any combination of weak signals must
produce a smaller size — never a larger one — than the structural base.

Formula (transparent to the user, shown verbatim in the UI):

    size = baseSize × lifetimeWeight × regimeWeight × exposureWeight × uncertaintyPenalty

* baseSize           — structurally-derived position notional (from
                       equity × risk_per_trade / unit_risk). NOT user-
                       controllable. Read-only on UI by design.
* lifetimeWeight     — long-term reliability of this (symbol, side,
                       alignmentBucket, risk) cell. Lower when sample is
                       weak OR historical winRate is mediocre.
* regimeWeight       — recent-30d reliability of the same cell. Lower
                       when the active regime is hostile or unproven.
* exposureWeight     — portfolio restraint. Lower when the book already
                       holds many positions OR carries large notional
                       exposure relative to equity.
* uncertaintyPenalty — second-order penalty for: (a) low samples on
                       either layer, (b) sharp lifetime↔regime divergence
                       (the epistemic state is internally inconsistent).

Invariants:
  * WAIT verdicts → final = 0 (no deployable size).
  * Hostile regime that calibration already hard-gated → final = 0.
  * Low sample reduces size but does NOT block action.
  * baseRisk parameter is NEVER user-mutable.
"""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger("adaptive_risk")


# ── Scale tables (kept as data, not magic) ───────────────────────────


def _lifetime_weight(sample: int, win_rate: float | None) -> tuple[float, str]:
    """Returns (weight, label)."""
    if sample == 0:
        return 0.75, "no lifetime sample yet — conservative scale"
    if sample < 5:
        return 0.70, f"weak lifetime sample ({sample})"
    if sample < 10:
        return 0.85, f"emerging lifetime sample ({sample})"
    wr = float(win_rate or 0.0)
    if wr < 0.45:
        return 0.50, f"lifetime winRate {int(wr * 100)}% below 0.45"
    if wr < 0.50:
        return 0.80, f"lifetime winRate {int(wr * 100)}% mediocre"
    if wr < 0.60:
        return 1.00, f"lifetime winRate {int(wr * 100)}% acceptable"
    if wr < 0.70:
        return 1.15, f"lifetime winRate {int(wr * 100)}% strong"
    return 1.25, f"lifetime winRate {int(wr * 100)}% exceptional"


def _regime_weight(sample: int, win_rate: float | None) -> tuple[float, str]:
    """Returns (weight, label) for 30d regime."""
    if sample < 5:
        return 1.00, f"recent sample emerging ({sample}) — neutral regime weight"
    wr = float(win_rate or 0.0)
    if wr < 0.40:
        return 0.40, f"recent winRate {int(wr * 100)}% hostile regime"
    if wr < 0.50:
        return 0.70, f"recent winRate {int(wr * 100)}% weakening regime"
    if wr < 0.60:
        return 1.00, f"recent winRate {int(wr * 100)}% compatible regime"
    return 1.10, f"recent winRate {int(wr * 100)}% favorable regime"


def _exposure_weight(
    open_count: int,
    notional_exposure_usd: float,
    equity_usd: float,
) -> tuple[float, dict, str]:
    """Restrain sizing when the book is already loaded.

    Returns (weight, components_dict, label).

    components_dict:
        openCount, openCountWeight,
        notionalExposureUsd, notionalRatio, notionalWeight
    """
    # Open-count component: 0 open → 1.0, 5 open → 0.0
    open_count_weight = max(0.0, 1.0 - 0.20 * open_count)

    # Notional component: notional/equity ratio capped at 1.0
    if equity_usd <= 0:
        notional_ratio = 1.0
    else:
        notional_ratio = min(1.0, max(0.0, notional_exposure_usd / equity_usd))
    notional_weight = max(0.0, 1.0 - notional_ratio)

    exposure = open_count_weight * notional_weight

    components = {
        "openCount": int(open_count),
        "openCountWeight": round(open_count_weight, 3),
        "notionalExposureUsd": round(notional_exposure_usd, 2),
        "notionalRatio": round(notional_ratio, 3),
        "notionalWeight": round(notional_weight, 3),
    }

    if open_count == 0 and notional_exposure_usd == 0:
        label = "book empty — full exposure scale"
    elif open_count_weight == 0:
        label = f"{open_count} open positions — book saturated"
    elif notional_weight == 0:
        label = "notional exposure ≥ equity — book saturated"
    else:
        label = (
            f"{open_count} open · "
            f"${notional_exposure_usd:.0f}/${equity_usd:.0f} notional load"
        )
    return exposure, components, label


def _uncertainty_penalty(
    lifetime_sample: int,
    lifetime_wr: float | None,
    regime_sample: int,
    regime_wr: float | None,
) -> tuple[float, str]:
    """Second-order penalty: low samples or epistemic inconsistency."""
    if lifetime_sample < 5 and regime_sample < 5:
        return 0.70, "both lifetime AND recent samples are weak"
    if lifetime_sample < 5 or regime_sample < 5:
        return 0.85, "one of lifetime/recent samples is weak"

    # Both have sample ≥ 5 — check divergence
    lw = float(lifetime_wr or 0.0)
    rw = float(regime_wr or 0.0)
    diff = abs(lw - rw)
    if diff > 0.20:
        return 0.80, (
            f"lifetime↔regime divergence {int(diff * 100)}% — "
            "epistemic state inconsistent"
        )
    if diff > 0.10:
        return 0.92, (
            f"lifetime↔regime divergence {int(diff * 100)}% — "
            "mild internal inconsistency"
        )
    return 1.00, "lifetime and regime are coherent"


# ── Public entry point ───────────────────────────────────────────────


def compute_adaptive_sizing(
    verdict: dict,
    account: dict,
    open_positions: list[dict],
    base_risk_pct: float,
) -> dict:
    """Build the adaptive sizing block for a verdict.

    Args:
        verdict: post-calibration verdict (must have action, calibration block).
        account: paper account doc (provides equityUsd / balanceUsd).
        open_positions: list of currently OPEN paper positions.
        base_risk_pct: configured risk-per-trade percent (NOT user-mutable).

    Returns:
        sizing block (see module docstring). `final` is the deployable
        size in USD; `forcedZeroReason` is set when final = 0.
    """
    action = (verdict.get("action") or "").upper()
    base_size = float(verdict.get("sizeUsd") or 0.0)

    equity = float(account.get("equityUsd") or account.get("balanceUsd") or 0.0)
    base_risk_usd = round(equity * (base_risk_pct / 100.0), 2)

    # Exposure components (always computed — even on WAIT — for UI transparency)
    open_count = len(open_positions)
    notional = sum(float(p.get("sizeUsd") or 0.0) for p in open_positions)
    exposure_w, exposure_components, exposure_label = _exposure_weight(
        open_count, notional, equity
    )

    cal = verdict.get("calibration") or {}
    lifetime_sample = int(cal.get("sample") or 0)
    lifetime_wr = cal.get("winRate")
    rec = cal.get("recent30d") or {}
    regime_sample = int(rec.get("sample") or 0)
    regime_wr = rec.get("winRate")

    lifetime_w, lifetime_label = _lifetime_weight(lifetime_sample, lifetime_wr)
    regime_w, regime_label = _regime_weight(regime_sample, regime_wr)
    penalty, penalty_label = _uncertainty_penalty(
        lifetime_sample, lifetime_wr, regime_sample, regime_wr
    )

    # ── Final ────────────────────────────────────────────────────────
    forced_zero_reason: Optional[str] = None
    if action not in ("LONG", "SHORT"):
        final = 0.0
        forced_zero_reason = "verdict_is_wait"
    elif base_size <= 0:
        final = 0.0
        forced_zero_reason = "no_structural_base_size"
    else:
        final = base_size * lifetime_w * regime_w * exposure_w * penalty
        final = round(max(0.0, final), 2)
        if exposure_w == 0:
            final = 0.0
            forced_zero_reason = "book_saturated"
        elif final < 1.00:
            final = 0.0
            forced_zero_reason = "size_below_min_deployable"

    # ── Human explanation ────────────────────────────────────────────
    if forced_zero_reason == "verdict_is_wait":
        explanation = (
            "Verdict is WAIT — adaptive layer produces no deployable size."
        )
    elif forced_zero_reason == "book_saturated":
        explanation = (
            f"Exposure scale collapsed to 0 ({exposure_label}). "
            "Deployment refused regardless of cognition quality."
        )
    elif forced_zero_reason == "size_below_min_deployable":
        explanation = (
            "Combined restraints reduced size below the minimum deployable "
            "floor ($1.00). Treated as WAIT."
        )
    elif forced_zero_reason == "no_structural_base_size":
        explanation = (
            "No structural base size available (entry/stop not resolved). "
            "Adaptive layer cannot scale a missing baseline."
        )
    else:
        # Build sentence linking the four scales
        explanation = (
            f"Base ${base_size:.2f} × "
            f"{lifetime_w:.2f} lifetime × "
            f"{regime_w:.2f} regime × "
            f"{exposure_w:.2f} exposure × "
            f"{penalty:.2f} uncertainty "
            f"= ${final:.2f} deployable."
        )

    return {
        "baseRiskPct": base_risk_pct,
        "baseRiskUsd": base_risk_usd,
        "baseSize": round(base_size, 2),
        "lifetimeWeight": round(lifetime_w, 3),
        "regimeWeight": round(regime_w, 3),
        "exposureWeight": round(exposure_w, 3),
        "uncertaintyPenalty": round(penalty, 3),
        "final": round(final, 2),
        "components": {
            **exposure_components,
            "lifetimeSample": lifetime_sample,
            "lifetimeWinRate": lifetime_wr,
            "regimeSample": regime_sample,
            "regimeWinRate": regime_wr,
        },
        "labels": {
            "lifetime": lifetime_label,
            "regime": regime_label,
            "exposure": exposure_label,
            "uncertainty": penalty_label,
        },
        "explanation": explanation,
        "forcedZeroReason": forced_zero_reason,
        "version": "t8.adaptive_capital_restraint.v1",
    }
