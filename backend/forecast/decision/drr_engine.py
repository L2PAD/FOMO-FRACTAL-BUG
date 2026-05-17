"""
DRR Engine — Drawdown + Reversal Risk
========================================
Block DRR: Gives the system the ability to sense market downside risk.

Computes three independent signals:
  1. drawdown_pressure — how far price has fallen from recent high
  2. reversal_risk — early warning of trend reversal
  3. breakdown_risk — event-level structural break

These feed into bearish_structure to fix the 19:1 bull/bear asymmetry.
"""

from dataclasses import dataclass


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


@dataclass
class DRRInputs:
    trend_strength: float
    trend_persistence: float
    exhaustion: float
    reversal_risk: float
    drawdown_pressure: float
    structure_alignment: float
    volatility_expansion: float
    dominant_regime: str
    breakdown_prob: float


@dataclass
class DRROutput:
    drawdown_pressure: float
    reversal_risk: float
    breakdown_risk: float
    drr_score: float


class DRREngine:

    def compute(self, x: DRRInputs) -> DRROutput:
        dp = self._compute_drawdown_pressure(x)
        rr = self._compute_reversal_risk(x, dp)
        br = self._compute_breakdown_risk(x, dp, x.drawdown_pressure)
        drr = 0.40 * dp + 0.35 * rr + 0.25 * br
        return DRROutput(
            drawdown_pressure=round(dp, 4),
            reversal_risk=round(rr, 4),
            breakdown_risk=round(br, 4),
            drr_score=round(drr, 4),
        )

    @staticmethod
    def _compute_drawdown_pressure(x: DRRInputs) -> float:
        # Base drawdown signal amplified
        dp = x.drawdown_pressure * 1.8

        # Sustained weakness amplifier
        if x.trend_persistence < 0.4:
            dp += 0.1

        # Volatility amplifier
        if x.volatility_expansion > 0.6:
            dp += 0.1

        return _clamp(dp)

    @staticmethod
    def _compute_reversal_risk(x: DRRInputs, drawdown: float) -> float:
        trend_weakening = 1.0 - x.trend_strength
        momentum_loss = x.exhaustion
        structure_break = 1.0 - x.structure_alignment
        vol_spike = x.volatility_expansion

        rr = (
            0.30 * trend_weakening
            + 0.25 * momentum_loss
            + 0.20 * structure_break
            + 0.15 * vol_spike
            + 0.10 * drawdown
        )

        # Regime amplifiers
        if x.dominant_regime == "transition":
            rr += 0.10
        elif x.dominant_regime == "breakdown":
            rr += 0.15

        return _clamp(rr)

    @staticmethod
    def _compute_breakdown_risk(x: DRRInputs, amplified_dp: float, raw_dp: float) -> float:
        # Breakdown is an event — use raw drawdown for trigger check
        breakdown_signal = (
            raw_dp > 0.35
            and x.structure_alignment < 0.5
            and x.trend_strength < 0.5
        )

        if not breakdown_signal:
            # Use breakdown probability from regime model as soft signal
            return _clamp(x.breakdown_prob * 0.8)

        br = 0.6
        if x.volatility_expansion > 0.6:
            br += 0.2
        if x.exhaustion > 0.3:
            br += 0.1

        return _clamp(br)


def compute_bearish_structure_v2(
    drr: DRROutput,
    negative_context: float,
    volatility_expansion: float,
    structure_alignment: float,
    base_bearish: float,
) -> float:
    """
    DRR-powered bearish_structure replacement.
    Symmetric counterpart to bullish_structure.
    """
    result = (
        0.30 * drr.drr_score
        + 0.20 * negative_context
        + 0.15 * volatility_expansion
        + 0.15 * (1.0 - structure_alignment)
        + 0.20 * base_bearish
    )
    return _clamp(result)
