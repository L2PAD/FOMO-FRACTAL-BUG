"""
Unified Structure Engine V2
==============================
Replaces independent bullish/bearish_structure with a single coherent
structural surface from which both sides are derived.

Pipeline position:
  raw features → DRR Engine → UnifiedStructureEngine → bull/bear/clarity/state

Components computed first (market-structure-as-object):
  1. continuation_support  — trend holding, momentum alive
  2. breakdown_support     — drawdown + structural break
  3. reversal_pressure     — early warning of regime shift
  4. range_pressure        — neither trend nor break, flat

Then derived:
  bullish_structure  = f(continuation - reversal - breakdown)
  bearish_structure  = f(breakdown + reversal - continuation)
  structure_clarity  = gap between dominant and runner-up component
  structure_state    = bullish / bearish / range / transition / mixed
"""

from dataclasses import dataclass, field


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


@dataclass
class StructureInputs:
    trend_strength: float
    trend_persistence: float
    momentum: float
    structure_alignment: float
    volatility_expansion: float
    drawdown_pressure: float
    reversal_risk: float
    breakdown_risk: float
    regime: str


@dataclass
class UnifiedStructureOutput:
    bullish_structure: float
    bearish_structure: float
    structure_clarity: float
    structure_state: str
    audit: dict


class UnifiedStructureEngine:

    def evaluate(self, x: StructureInputs) -> UnifiedStructureOutput:
        cont = self._continuation_support(x)
        brk = self._breakdown_support(x)
        rev = self._reversal_pressure(x)
        rng = self._range_pressure(x)

        clarity = self._structure_clarity(cont, brk, rev, rng)
        state = self._structure_state(cont, brk, rev, rng, clarity)

        bull = self._bullish_structure(cont, brk, rev, x.structure_alignment, x.momentum, clarity)
        bear = self._bearish_structure(cont, brk, rev, x.structure_alignment, clarity)

        bull, bear = self._symmetry_guardrail(bull, bear, clarity)

        return UnifiedStructureOutput(
            bullish_structure=round(bull, 4),
            bearish_structure=round(bear, 4),
            structure_clarity=round(clarity, 4),
            structure_state=state,
            audit={
                "continuation_support": round(cont, 4),
                "breakdown_support": round(brk, 4),
                "reversal_pressure": round(rev, 4),
                "range_pressure": round(rng, 4),
            },
        )

    # ── Components ──

    @staticmethod
    def _continuation_support(x: StructureInputs) -> float:
        return _clamp(
            0.35 * x.trend_strength
            + 0.25 * x.trend_persistence
            + 0.20 * x.momentum
            + 0.20 * x.structure_alignment
        )

    @staticmethod
    def _breakdown_support(x: StructureInputs) -> float:
        return _clamp(
            0.35 * x.drawdown_pressure
            + 0.30 * x.breakdown_risk
            + 0.20 * (1.0 - x.structure_alignment)
            + 0.15 * x.volatility_expansion
        )

    @staticmethod
    def _reversal_pressure(x: StructureInputs) -> float:
        base = (
            0.35 * x.reversal_risk
            + 0.25 * (1.0 - x.trend_strength)
            + 0.20 * (1.0 - x.momentum)
            + 0.20 * x.volatility_expansion
        )
        if x.regime == "transition":
            base += 0.08
        elif x.regime == "breakdown":
            base += 0.12
        return _clamp(base)

    @staticmethod
    def _range_pressure(x: StructureInputs) -> float:
        mid_momentum = max(0.0, 1.0 - abs(x.momentum - 0.5) * 2.0)
        return _clamp(
            0.35 * (1.0 - x.trend_strength)
            + 0.25 * (1.0 - x.trend_persistence)
            + 0.20 * mid_momentum
            + 0.20 * (1.0 - x.structure_alignment)
        )

    # ── Derived ──

    @staticmethod
    def _structure_clarity(cont: float, brk: float, rev: float, rng: float) -> float:
        components = sorted([cont, brk, rev, rng], reverse=True)
        top1, top2 = components[0], components[1]
        return _clamp(top1 - top2 + 0.5 * top1)

    @staticmethod
    def _structure_state(
        cont: float, brk: float, rev: float, rng: float, clarity: float,
    ) -> str:
        if cont > 0.65 and clarity > 0.55:
            return "bullish"
        if brk > 0.65 and clarity > 0.55:
            return "bearish"
        if rev > 0.55 and rev >= rng:
            return "transition"
        if rng > 0.60:
            return "range"
        if rev > 0.55:
            return "transition"
        return "mixed"

    @staticmethod
    def _bullish_structure(
        cont: float, brk: float, rev: float,
        struct_align: float, momentum: float, clarity: float,
    ) -> float:
        raw = (
            0.55 * cont
            + 0.15 * struct_align
            + 0.15 * momentum
            + 0.15 * clarity
            - 0.20 * rev
            - 0.20 * brk
        )
        return _clamp(raw)

    @staticmethod
    def _bearish_structure(
        cont: float, brk: float, rev: float,
        struct_align: float, clarity: float,
    ) -> float:
        raw = (
            0.40 * brk
            + 0.30 * rev
            + 0.15 * (1.0 - struct_align)
            + 0.15 * clarity
            - 0.15 * cont
        )
        return _clamp(raw)

    @staticmethod
    def _symmetry_guardrail(
        bull: float, bear: float, clarity: float,
    ) -> tuple:
        imbalance = abs(bull - bear)
        if imbalance > 0.75 and clarity < 0.4:
            bull = 0.9 * bull + 0.1 * 0.5
            bear = 0.9 * bear + 0.1 * 0.5
        return bull, bear
