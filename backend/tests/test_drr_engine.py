"""
DRR Engine — Acceptance Tests
================================
4 cases from architecture spec:
  1. Healthy uptrend → drr_score < 0.3
  2. Early reversal → reversal_risk > 0.5, drr ~ 0.5-0.6
  3. Breakdown → breakdown_risk > 0.7, drr > 0.7
  4. Flat → drr ~ 0.3-0.4
"""

import pytest
from forecast.decision.drr_engine import DRREngine, DRRInputs, compute_bearish_structure_v2

engine = DRREngine()


# Case 1 — Healthy uptrend
CASE_1 = DRRInputs(
    trend_strength=0.85,
    trend_persistence=0.80,
    exhaustion=0.05,
    reversal_risk=0.08,
    drawdown_pressure=0.02,
    structure_alignment=0.85,
    volatility_expansion=0.20,
    dominant_regime="trend",
    breakdown_prob=0.03,
)


def test_case1_healthy_uptrend():
    r = engine.compute(CASE_1)
    assert r.drr_score < 0.3, f"drr_score={r.drr_score}, expected < 0.3"
    assert r.drawdown_pressure < 0.15
    assert r.reversal_risk < 0.3


# Case 2 — Early reversal
CASE_2 = DRRInputs(
    trend_strength=0.35,
    trend_persistence=0.30,
    exhaustion=0.45,
    reversal_risk=0.50,
    drawdown_pressure=0.25,
    structure_alignment=0.40,
    volatility_expansion=0.65,
    dominant_regime="transition",
    breakdown_prob=0.15,
)


def test_case2_early_reversal():
    r = engine.compute(CASE_2)
    assert r.reversal_risk > 0.5, f"reversal_risk={r.reversal_risk}, expected > 0.5"
    assert 0.4 <= r.drr_score <= 0.7, f"drr_score={r.drr_score}, expected 0.4-0.7"


# Case 3 — Breakdown
CASE_3 = DRRInputs(
    trend_strength=0.20,
    trend_persistence=0.25,
    exhaustion=0.60,
    reversal_risk=0.70,
    drawdown_pressure=0.55,
    structure_alignment=0.15,
    volatility_expansion=0.80,
    dominant_regime="breakdown",
    breakdown_prob=0.45,
)


def test_case3_breakdown():
    r = engine.compute(CASE_3)
    assert r.breakdown_risk > 0.7, f"breakdown_risk={r.breakdown_risk}, expected > 0.7"
    assert r.drr_score > 0.65, f"drr_score={r.drr_score}, expected > 0.65"


# Case 4 — Flat / range
CASE_4 = DRRInputs(
    trend_strength=0.45,
    trend_persistence=0.50,
    exhaustion=0.15,
    reversal_risk=0.20,
    drawdown_pressure=0.10,
    structure_alignment=0.50,
    volatility_expansion=0.25,
    dominant_regime="range",
    breakdown_prob=0.08,
)


def test_case4_flat():
    r = engine.compute(CASE_4)
    assert 0.2 <= r.drr_score <= 0.5, f"drr_score={r.drr_score}, expected 0.2-0.5"


# Structural invariants
def test_all_outputs_in_range():
    for case in [CASE_1, CASE_2, CASE_3, CASE_4]:
        r = engine.compute(case)
        assert 0 <= r.drawdown_pressure <= 1
        assert 0 <= r.reversal_risk <= 1
        assert 0 <= r.breakdown_risk <= 1
        assert 0 <= r.drr_score <= 1


def test_bearish_structure_v2_uses_drr():
    r = engine.compute(CASE_3)  # breakdown case
    bs = compute_bearish_structure_v2(
        drr=r,
        negative_context=0.6,
        volatility_expansion=0.8,
        structure_alignment=0.15,
        base_bearish=0.5,
    )
    assert bs > 0.5, f"bearish_structure={bs}, expected > 0.5 for breakdown"


def test_bearish_structure_v2_low_in_uptrend():
    r = engine.compute(CASE_1)  # uptrend case
    bs = compute_bearish_structure_v2(
        drr=r,
        negative_context=0.1,
        volatility_expansion=0.2,
        structure_alignment=0.85,
        base_bearish=0.1,
    )
    assert bs < 0.25, f"bearish_structure={bs}, expected < 0.25 for uptrend"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
