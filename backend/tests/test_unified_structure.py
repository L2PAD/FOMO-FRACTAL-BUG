"""
Unified Structure Engine V2 — Acceptance Tests
=================================================
5 behavioral cases:
  U1 — Strong uptrend        → bullish, high clarity
  U2 — Early reversal        → transition/mixed, bull↓ bear↑
  U3 — Breakdown             → bearish, bear > 0.65
  U4 — Range                 → range state, balanced
  U5 — Noisy mixed           → mixed, low clarity
"""

import pytest
from forecast.decision.unified_structure import (
    UnifiedStructureEngine,
    StructureInputs,
)

engine = UnifiedStructureEngine()


# ═══════ U1 — Strong uptrend ═══════

CASE_U1 = StructureInputs(
    trend_strength=0.85,
    trend_persistence=0.80,
    momentum=0.82,
    structure_alignment=0.88,
    volatility_expansion=0.15,
    drawdown_pressure=0.03,
    reversal_risk=0.05,
    breakdown_risk=0.02,
    regime="trend",
)


def test_u1_strong_uptrend():
    r = engine.evaluate(CASE_U1)
    assert r.structure_state == "bullish", f"Expected bullish, got {r.structure_state}"
    assert r.bullish_structure > 0.65, f"bull={r.bullish_structure}, expected > 0.65"
    assert r.bearish_structure < 0.30, f"bear={r.bearish_structure}, expected < 0.30"
    assert r.structure_clarity > 0.50, f"clarity={r.structure_clarity}, expected > 0.50"


# ═══════ U2 — Early reversal ═══════

CASE_U2 = StructureInputs(
    trend_strength=0.40,
    trend_persistence=0.35,
    momentum=0.30,
    structure_alignment=0.38,
    volatility_expansion=0.55,
    drawdown_pressure=0.30,
    reversal_risk=0.60,
    breakdown_risk=0.15,
    regime="transition",
)


def test_u2_early_reversal():
    r = engine.evaluate(CASE_U2)
    assert r.structure_state in ("transition", "mixed"), f"Expected transition/mixed, got {r.structure_state}"
    assert r.bullish_structure < r.bearish_structure, f"bull={r.bullish_structure} should be < bear={r.bearish_structure}"
    assert r.structure_clarity < 0.65, f"clarity={r.structure_clarity}, expected < 0.65 for reversal"


# ═══════ U3 — Breakdown ═══════

CASE_U3 = StructureInputs(
    trend_strength=0.15,
    trend_persistence=0.20,
    momentum=0.12,
    structure_alignment=0.10,
    volatility_expansion=0.80,
    drawdown_pressure=0.70,
    reversal_risk=0.75,
    breakdown_risk=0.85,
    regime="breakdown",
)


def test_u3_breakdown():
    r = engine.evaluate(CASE_U3)
    assert r.structure_state == "bearish", f"Expected bearish, got {r.structure_state}"
    assert r.bearish_structure > 0.55, f"bear={r.bearish_structure}, expected > 0.55"
    assert r.bullish_structure < 0.20, f"bull={r.bullish_structure}, expected < 0.20"


# ═══════ U4 — Range ═══════

CASE_U4 = StructureInputs(
    trend_strength=0.30,
    trend_persistence=0.35,
    momentum=0.48,
    structure_alignment=0.40,
    volatility_expansion=0.20,
    drawdown_pressure=0.10,
    reversal_risk=0.15,
    breakdown_risk=0.05,
    regime="range",
)


def test_u4_range():
    r = engine.evaluate(CASE_U4)
    assert r.structure_state == "range", f"Expected range, got {r.structure_state}"
    assert 0.15 <= r.bullish_structure <= 0.55, f"bull={r.bullish_structure}, expected 0.15-0.55"
    assert 0.15 <= r.bearish_structure <= 0.55, f"bear={r.bearish_structure}, expected 0.15-0.55"


# ═══════ U5 — Noisy mixed ═══════

CASE_U5 = StructureInputs(
    trend_strength=0.45,
    trend_persistence=0.40,
    momentum=0.50,
    structure_alignment=0.45,
    volatility_expansion=0.45,
    drawdown_pressure=0.35,
    reversal_risk=0.40,
    breakdown_risk=0.20,
    regime="transition",
)


def test_u5_noisy_mixed():
    r = engine.evaluate(CASE_U5)
    assert r.structure_state in ("mixed", "transition", "range"), f"Expected mixed/transition/range, got {r.structure_state}"
    assert r.structure_clarity < 0.55, f"clarity={r.structure_clarity}, expected < 0.55 for noisy"
    assert abs(r.bullish_structure - r.bearish_structure) < 0.40, (
        f"bull={r.bullish_structure}, bear={r.bearish_structure}, too wide for noisy"
    )


# ═══════ Structural invariants ═══════

def test_all_outputs_in_range():
    for case in [CASE_U1, CASE_U2, CASE_U3, CASE_U4, CASE_U5]:
        r = engine.evaluate(case)
        assert 0 <= r.bullish_structure <= 1, f"bull out of range: {r.bullish_structure}"
        assert 0 <= r.bearish_structure <= 1, f"bear out of range: {r.bearish_structure}"
        assert 0 <= r.structure_clarity <= 1, f"clarity out of range: {r.structure_clarity}"
        assert r.structure_state in ("bullish", "bearish", "range", "transition", "mixed")


def test_audit_has_components():
    r = engine.evaluate(CASE_U1)
    for key in ("continuation_support", "breakdown_support", "reversal_pressure", "range_pressure"):
        assert key in r.audit, f"Missing audit key: {key}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
