"""
Direction Override Gate
========================
Allows controlled override of weak base scores when structure
is strongly directional and conditions are strictly met.

v4.2.1: Phase-aware override modulation
  - Override strength filter (disable weak overrides)
  - Phase multiplier (amplify/dampen by market phase)
  - Strength multiplier (scale by signal quality)
  - Anti-overfitting guard (clamp max shift)
  - Phase-specific disable (unstable_transition + weak signal)

Override rules:
  A. base score after structure is still weak (abs < 0.15)
  B. fused structure bias is strong (abs > 0.35)
  C. mode is aligned or reversal_candidate (NOT pullback/mixed_range)
  D. fused trend is strong (> 0.28)
  E. reversal risk is low (< 0.55)
"""


# Phase-aware multiplier profile (v4.2.1)
PHASE_OVERRIDE_PROFILE = {
    "continuation": 1.05,
    "pullback": 1.15,
    "recovery_attempt": 1.05,
    "late_trend": 0.95,
    "breakdown": 1.00,
    "unstable_transition": 0.75,
    "mixed_range": 0.85,
}

# Override strength thresholds
_UNSTABLE_MIN_STRENGTH = 0.15
_MAX_OVERRIDE_SHIFT = 0.25


class DirectionOverrideGate:
    """Controlled direction unlock for weak base + strong structure."""

    # Override target scores (just above MILD threshold of 0.20)
    OVERRIDE_SCORE_FULL = 0.22
    OVERRIDE_SCORE_FALLBACK = 0.20  # When major used relaxed profile

    def maybe_override(
        self,
        base_score: float,
        fused_structure: dict,
        mode: str,
        major_fallback_used: bool = False,
    ) -> dict:
        """
        Check if a direction override is warranted.
        base_score: score AFTER structure optimization + guards.
        """
        bias = fused_structure.get("structure_bias_score", 0.0)
        trend = fused_structure.get("structure_trend_score", 0.0)
        reversal = fused_structure.get("structure_reversal_risk", 0.0)

        # Rule A: base must be weak (still near NEUTRAL after all processing)
        if abs(base_score) >= 0.15:
            return self._none("base_too_strong")

        # Rule B: structure must have clear directional bias
        if abs(bias) <= 0.35:
            return self._none("bias_too_weak")

        # Rule C + F: only aligned or reversal_candidate (no pullback/mixed_range)
        if mode not in ("aligned", "reversal_candidate"):
            return self._none("mode_not_overrideable")

        # Rule D: strong trend confirmation
        if trend <= 0.28:
            return self._none("trend_too_weak")

        # Rule E: reversal risk must be low
        if reversal >= 0.55:
            return self._none("reversal_risk_too_high")

        # v4.2.1: Compute override strength for modulation
        override_strength = abs(bias) * trend

        # Determine override score (slightly reduced if fallback major was used)
        target = self.OVERRIDE_SCORE_FALLBACK if major_fallback_used else self.OVERRIDE_SCORE_FULL

        if bias > 0:
            return {
                "override_allowed": True,
                "override_type": "to_mild_bull",
                "override_score": target,
                "override_strength": round(override_strength, 4),
                "reason": "strong_structure_bull_weak_base",
            }

        return {
            "override_allowed": True,
            "override_type": "to_mild_bear",
            "override_score": -target,
            "override_strength": round(override_strength, 4),
            "reason": "strong_structure_bear_weak_base",
        }

    def modulate_override(
        self,
        override_result: dict,
        market_phase: str,
    ) -> dict:
        """
        v4.2.1: Apply phase-aware + strength-aware modulation to override.
        Returns modified override_result (or disabled if filters triggered).
        """
        if not override_result.get("override_allowed"):
            return override_result

        override_score = override_result["override_score"]
        override_strength = override_result.get("override_strength", 0.3)
        phase = market_phase or "mixed_range"

        # Phase-specific disable: unstable_transition with weak signal
        if phase == "unstable_transition" and override_strength < _UNSTABLE_MIN_STRENGTH:
            return {
                **override_result,
                "override_allowed": False,
                "override_score": None,
                "reason": "unstable_phase_weak_strength",
                "modulation": {"disabled": True, "phase": phase},
            }

        # Phase multiplier
        phase_mult = PHASE_OVERRIDE_PROFILE.get(phase, 0.85)

        # Strength multiplier (calibrated for actual range ~0.10-0.25)
        if override_strength > 0.20:
            strength_mult = 1.10
        elif override_strength > 0.14:
            strength_mult = 1.00
        else:
            strength_mult = 0.90

        # Modulated override
        sign = 1.0 if override_score > 0 else -1.0
        modulated = abs(override_score) * phase_mult * strength_mult

        # Anti-overfitting guard: clamp
        modulated = min(modulated, _MAX_OVERRIDE_SHIFT)
        final_score = round(sign * modulated, 6)

        return {
            **override_result,
            "override_score": final_score,
            "modulation": {
                "phase": phase,
                "phase_mult": phase_mult,
                "strength_mult": strength_mult,
                "override_strength": override_strength,
                "original_score": override_result.get("override_score"),
                "final_score": final_score,
            },
        }

    def _none(self, reason: str) -> dict:
        return {
            "override_allowed": False,
            "override_type": None,
            "override_score": None,
            "reason": reason,
        }
