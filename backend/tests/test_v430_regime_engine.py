"""
v4.3.0 Regime Engine V2 Tests
==============================
Tests for the Regime Engine probability engine, postprocessor,
feature builder, adjustment engine, and audit builder.
"""
import sys
import math
import pytest

sys.path.insert(0, "/app/backend")

from forecast.regime.regime_types import REGIME_NAMES
from forecast.regime.regime_probability_engine import compute_regime_probabilities, _TEMPERATURE
from forecast.regime.regime_postprocessor import postprocess_regime
from forecast.regime.regime_feature_builder import build_regime_features
from forecast.regime.regime_adjustment_engine import apply_regime_adjustments
from forecast.regime.regime_audit_builder import build_regime_audit


# ═══════════════ Fixtures ═══════════════

def _make_features(**overrides):
    base = {
        "trend_strength": 0.40,
        "trend_persistence": 0.50,
        "exhaustion": 0.20,
        "reversal_risk": 0.20,
        "drawdown_pressure": 0.15,
        "structure_alignment": 0.50,
        "volatility_expansion": 0.30,
    }
    base.update(overrides)
    return base


STRONG_TREND = _make_features(
    trend_strength=0.85, trend_persistence=0.80,
    exhaustion=0.10, reversal_risk=0.10,
    drawdown_pressure=0.05, structure_alignment=0.90,
)

RANGE_BOUND = _make_features(
    trend_strength=0.15, trend_persistence=0.20,
    exhaustion=0.10, reversal_risk=0.15,
    drawdown_pressure=0.10, structure_alignment=0.25,
    volatility_expansion=0.20,
)

PULLBACK = _make_features(
    trend_strength=0.60, trend_persistence=0.55,
    reversal_risk=0.45, structure_alignment=0.35,
)

TRANSITION = _make_features(
    trend_strength=0.30, trend_persistence=0.25,
    exhaustion=0.55, reversal_risk=0.65,
    drawdown_pressure=0.30, structure_alignment=0.20,
    volatility_expansion=0.60,
)

BREAKDOWN = _make_features(
    trend_strength=0.20, trend_persistence=0.25,
    exhaustion=0.50, reversal_risk=0.55,
    drawdown_pressure=0.85, structure_alignment=0.15,
    volatility_expansion=0.75,
)


# ═══════════════ Probability Engine Tests ═══════════════

class TestRegimeProbabilityEngine:
    def test_probabilities_sum_to_one(self):
        for phase in ["continuation", "late_trend", "pullback", "breakdown",
                       "recovery_attempt", "unstable_transition", "mixed_range"]:
            probs = compute_regime_probabilities(STRONG_TREND, context_phase=phase)
            total = sum(probs.values())
            assert abs(total - 1.0) < 1e-4, f"Probs sum={total} for phase={phase}"

    def test_no_nan_values(self):
        probs = compute_regime_probabilities(STRONG_TREND, context_phase="continuation")
        for name, p in probs.items():
            assert not math.isnan(p), f"NaN for regime={name}"
            assert not math.isinf(p), f"Inf for regime={name}"

    def test_all_probabilities_non_negative(self):
        probs = compute_regime_probabilities(TRANSITION, context_phase="unstable_transition")
        for name, p in probs.items():
            assert p >= 0, f"Negative prob for regime={name}: {p}"

    def test_temperature_is_calibrated(self):
        assert _TEMPERATURE == 0.25, f"Expected temp=0.25, got {_TEMPERATURE}"

    def test_trend_dominant_for_strong_trend(self):
        probs = compute_regime_probabilities(STRONG_TREND, context_phase="continuation")
        assert max(probs, key=probs.get) == "trend"
        assert probs["trend"] > 0.50

    def test_range_dominant_for_range_bound(self):
        probs = compute_regime_probabilities(RANGE_BOUND, context_phase="mixed_range")
        assert max(probs, key=probs.get) == "range"
        assert probs["range"] > 0.50

    def test_pullback_dominant_for_pullback(self):
        probs = compute_regime_probabilities(PULLBACK, context_phase="pullback")
        assert max(probs, key=probs.get) == "pullback"
        assert probs["pullback"] > 0.40

    def test_transition_dominant_for_unstable(self):
        probs = compute_regime_probabilities(TRANSITION, context_phase="unstable_transition")
        assert max(probs, key=probs.get) == "transition"
        assert probs["transition"] > 0.40

    def test_breakdown_dominant_for_stress(self):
        probs = compute_regime_probabilities(BREAKDOWN, context_phase="breakdown")
        assert max(probs, key=probs.get) == "breakdown"
        assert probs["breakdown"] > 0.50

    def test_all_regimes_have_some_probability(self):
        """No regime should have exactly 0 probability."""
        probs = compute_regime_probabilities(TRANSITION, context_phase="unstable_transition")
        for name, p in probs.items():
            assert p > 0.001, f"Regime {name} has near-zero prob: {p}"

    def test_distribution_not_too_sharp(self):
        """Dominant should not exceed 0.95 (not argmax-like)."""
        probs = compute_regime_probabilities(STRONG_TREND, context_phase="continuation")
        dominant_p = max(probs.values())
        assert dominant_p < 0.95, f"Distribution too sharp: {dominant_p}"

    def test_distribution_not_too_flat(self):
        """Dominant should exceed 0.30 even in ambiguous cases."""
        probs = compute_regime_probabilities(_make_features(), context_phase="mixed_range")
        dominant_p = max(probs.values())
        assert dominant_p > 0.30, f"Distribution too flat: {dominant_p}"


# ═══════════════ Postprocessor Tests ═══════════════

class TestRegimePostprocessor:
    def test_dominant_regime_is_string(self):
        probs = compute_regime_probabilities(STRONG_TREND, context_phase="continuation")
        post = postprocess_regime(probs)
        assert isinstance(post["dominant_regime"], str)
        assert post["dominant_regime"] in REGIME_NAMES

    def test_entropy_range(self):
        """Entropy should be in [0, 1] (normalized)."""
        for feats, phase in [(STRONG_TREND, "continuation"), (TRANSITION, "unstable_transition"),
                             (_make_features(), "mixed_range")]:
            probs = compute_regime_probabilities(feats, context_phase=phase)
            post = postprocess_regime(probs)
            assert 0.0 <= post["regime_entropy"] <= 1.0, f"Entropy out of range: {post['regime_entropy']}"

    def test_low_entropy_for_clear_cases(self):
        probs = compute_regime_probabilities(RANGE_BOUND, context_phase="mixed_range")
        post = postprocess_regime(probs)
        assert post["regime_entropy"] < 0.60, f"Expected low entropy, got {post['regime_entropy']}"

    def test_higher_entropy_for_ambiguous(self):
        mixed = _make_features(trend_strength=0.40, trend_persistence=0.45,
                               exhaustion=0.30, reversal_risk=0.30)
        probs = compute_regime_probabilities(mixed, context_phase="late_trend")
        post = postprocess_regime(probs)
        assert post["regime_entropy"] > 0.60, f"Expected higher entropy, got {post['regime_entropy']}"

    def test_ambiguity_flag_for_close_regimes(self):
        """When top1-top2 gap < 0.08, ambiguous flag should appear."""
        # Create features where two regimes are very close
        mixed = _make_features(trend_strength=0.50, trend_persistence=0.45,
                               exhaustion=0.35, reversal_risk=0.35,
                               structure_alignment=0.45, volatility_expansion=0.40)
        probs = compute_regime_probabilities(mixed, context_phase="late_trend")
        post = postprocess_regime(probs)
        gap = probs[post["dominant_regime"]] - sorted(probs.values(), reverse=True)[1]
        if gap < 0.08:
            assert "ambiguous_regime" in post["flags"]

    def test_confidence_equals_top_probability(self):
        probs = compute_regime_probabilities(STRONG_TREND, context_phase="continuation")
        post = postprocess_regime(probs)
        expected_conf = max(probs.values())
        # May be scaled by ambiguity
        assert post["regime_confidence"] <= expected_conf + 0.001

    def test_low_entropy_strong_flag(self):
        probs = compute_regime_probabilities(RANGE_BOUND, context_phase="mixed_range")
        post = postprocess_regime(probs)
        if post["regime_entropy"] < 0.50:
            assert "low_entropy_strong" in post["flags"]


# ═══════════════ Adjustment Engine Tests ═══════════════

class TestRegimeAdjustmentEngine:
    def _make_regime(self, dominant, confidence=0.6, entropy=0.5, probs=None):
        return {
            "dominant_regime": dominant,
            "regime_confidence": confidence,
            "regime_entropy": entropy,
            "flags": [],
            "probabilities": probs or {},
        }

    def _make_features(self, sa=0.5, ts=0.5):
        return {"structure_alignment": sa, "trend_strength": ts}

    def test_score_never_modified(self):
        """Regime MUST NOT change score direction."""
        for score in [-0.5, -0.1, 0.0, 0.1, 0.5]:
            for regime in REGIME_NAMES:
                result = apply_regime_adjustments(
                    score=score, conf_dir=0.5, conf_tgt=0.5,
                    band_mult=1.0, regime=self._make_regime(regime),
                )
                # Score is not in the output — regime never modifies it
                assert "score" not in result

    def test_confidence_within_caps(self):
        for regime in REGIME_NAMES:
            result = apply_regime_adjustments(
                score=-0.3, conf_dir=0.5, conf_tgt=0.5,
                band_mult=1.0, regime=self._make_regime(regime),
                regime_features=self._make_features(),
            )
            assert 0.70 * 0.5 - 0.001 <= result["conf_dir"] <= 1.10 * 0.5 + 0.001
            assert 0.70 * 0.5 - 0.001 <= result["conf_tgt"] <= 1.08 * 0.5 + 0.001
            assert 0.93 <= result["band_mult"] <= 1.15 + 0.001

    def test_trend_boosts_confidence(self):
        result = apply_regime_adjustments(
            score=0.3, conf_dir=0.5, conf_tgt=0.5, band_mult=1.0,
            regime=self._make_regime("trend", confidence=0.5, entropy=0.3),
            regime_features=self._make_features(sa=0.8, ts=0.8),
        )
        # Trend has moderate uncertainty (0.55 prior) but entropy=0.3 lowers it
        assert "trend_boost" in result["adjustments"]["flags"]

    def test_transition_reduces_confidence_hard(self):
        """v4.3.1: Transition gets both base + hard rule → strong reduction."""
        result = apply_regime_adjustments(
            score=0.3, conf_dir=0.5, conf_tgt=0.5, band_mult=1.0,
            regime=self._make_regime("transition", entropy=0.8),
            regime_features=self._make_features(sa=0.2, ts=0.3),
        )
        assert result["conf_dir"] < 0.40, f"Transition should reduce conf strongly, got {result['conf_dir']}"
        assert "transition_caution" in result["adjustments"]["flags"]
        assert "transition_hard_dampen" in result["adjustments"]["flags"]

    def test_pullback_boosts(self):
        """v4.3.1: Pullback has high accuracy → confidence boost."""
        result = apply_regime_adjustments(
            score=0.3, conf_dir=0.5, conf_tgt=0.5, band_mult=1.0,
            regime=self._make_regime("pullback", confidence=0.6, entropy=0.4),
            regime_features=self._make_features(sa=0.5, ts=0.5),
        )
        assert "pullback_boost" in result["adjustments"]["flags"]
        # Pullback has low uncertainty (0.15 prior) → no damping
        assert result["conf_dir"] >= 0.5

    def test_range_dampens(self):
        result = apply_regime_adjustments(
            score=0.3, conf_dir=0.5, conf_tgt=0.5, band_mult=1.0,
            regime=self._make_regime("range", entropy=0.6),
            regime_features=self._make_features(),
        )
        assert result["conf_dir"] < 0.5
        assert result["band_mult"] > 1.0
        assert "range_dampen" in result["adjustments"]["flags"]

    def test_decision_uncertainty_computed(self):
        """v4.3.1: decision_uncertainty should be in adjustments."""
        result = apply_regime_adjustments(
            score=0.3, conf_dir=0.5, conf_tgt=0.5, band_mult=1.0,
            regime=self._make_regime("trend", entropy=0.5),
            regime_features=self._make_features(sa=0.8, ts=0.7),
        )
        assert "decision_uncertainty" in result["adjustments"]
        du = result["adjustments"]["decision_uncertainty"]
        assert 0.0 <= du <= 1.0

    def test_high_uncertainty_dampens(self):
        """High decision uncertainty should dampen confidence."""
        # Low uncertainty case
        low_u = apply_regime_adjustments(
            score=0.3, conf_dir=0.5, conf_tgt=0.5, band_mult=1.0,
            regime=self._make_regime("trend", confidence=0.7, entropy=0.3),
            regime_features=self._make_features(sa=0.9, ts=0.9),
        )
        # High uncertainty case
        high_u = apply_regime_adjustments(
            score=0.3, conf_dir=0.5, conf_tgt=0.5, band_mult=1.0,
            regime=self._make_regime("trend", confidence=0.5, entropy=0.9),
            regime_features=self._make_features(sa=0.1, ts=0.1),
        )
        assert high_u["conf_dir"] < low_u["conf_dir"], \
            f"High uncertainty should give lower conf: {high_u['conf_dir']} vs {low_u['conf_dir']}"

    def test_ambiguity_gap_dampen(self):
        """v4.3.1: Close top1/top2 gap should trigger ambiguity dampen."""
        probs = {"trend": 0.25, "range": 0.24, "pullback": 0.20,
                 "transition": 0.16, "breakdown": 0.15}
        result = apply_regime_adjustments(
            score=0.3, conf_dir=0.5, conf_tgt=0.5, band_mult=1.0,
            regime=self._make_regime("trend", entropy=0.7, probs=probs),
            regime_features=self._make_features(),
        )
        assert "ambiguity_gap_dampen" in result["adjustments"]["flags"]

    def test_synergy_pullback_trend_boost(self):
        """v4.3.1: pullback phase + trend regime → boost."""
        result = apply_regime_adjustments(
            score=0.3, conf_dir=0.5, conf_tgt=0.5, band_mult=1.0,
            regime=self._make_regime("trend", confidence=0.6, entropy=0.4),
            regime_features=self._make_features(sa=0.8, ts=0.7),
            context_phase="pullback",
        )
        assert "synergy_pullback_trend" in result["adjustments"]["flags"]

    def test_synergy_transition_weak(self):
        """v4.3.1: unstable_transition phase + transition regime → weaken."""
        result = apply_regime_adjustments(
            score=0.3, conf_dir=0.5, conf_tgt=0.5, band_mult=1.0,
            regime=self._make_regime("transition", entropy=0.8),
            regime_features=self._make_features(sa=0.2, ts=0.3),
            context_phase="unstable_transition",
        )
        assert "synergy_transition_weak" in result["adjustments"]["flags"]

    def test_breakdown_bear_affirm(self):
        result = apply_regime_adjustments(
            score=-0.3, conf_dir=0.5, conf_tgt=0.5, band_mult=1.0,
            regime=self._make_regime("breakdown", entropy=0.5),
            regime_features=self._make_features(sa=0.2, ts=0.2),
        )
        assert "breakdown_bear_affirm" in result["adjustments"]["flags"]

    def test_breakdown_bull_caution(self):
        result = apply_regime_adjustments(
            score=0.3, conf_dir=0.5, conf_tgt=0.5, band_mult=1.0,
            regime=self._make_regime("breakdown", entropy=0.5),
            regime_features=self._make_features(sa=0.2, ts=0.2),
        )
        assert "breakdown_bull_caution" in result["adjustments"]["flags"]


# ═══════════════ Feature Builder Tests ═══════════════

class TestRegimeFeatureBuilder:
    def test_all_features_in_range(self):
        base = {"volatility": 0.04, "ret_1d": 0.01, "ret_7d": 0.03,
                "ret_14d": 0.05, "momentum": 0.1, "price": 50000}
        structure = {"structure_bias_score": 0.2}
        context = {"trend_strength": 0.5, "trend_persistence": 0.5,
                   "trend_exhaustion": 0.1, "reversal_risk": 0.1,
                   "drawdown_pressure": 0.1, "volatility_state": "normal"}
        multiscale = {
            "major": {"structure_bias_score": 0.3},
            "minor": {"structure_bias_score": 0.2},
            "mode": "aligned",
        }
        features = build_regime_features(base, structure, context, multiscale)
        for key, val in features.items():
            assert 0.0 <= val <= 1.0, f"Feature {key}={val} out of [0,1]"

    def test_all_seven_features_present(self):
        features = build_regime_features(
            {"volatility": 0.04}, {}, {"trend_strength": 0.5, "trend_persistence": 0.5,
             "trend_exhaustion": 0.1, "reversal_risk": 0.1, "drawdown_pressure": 0.1,
             "volatility_state": "normal"},
            {"major": {}, "minor": {}, "mode": "aligned"},
        )
        expected = ["trend_strength", "trend_persistence", "exhaustion",
                    "reversal_risk", "drawdown_pressure", "structure_alignment",
                    "volatility_expansion"]
        for key in expected:
            assert key in features, f"Missing feature: {key}"


# ═══════════════ Audit Builder Tests ═══════════════

class TestRegimeAuditBuilder:
    def test_audit_structure(self):
        features = _make_features()
        regime = {
            "dominant_regime": "trend",
            "regime_confidence": 0.7,
            "regime_entropy": 0.3,
            "flags": ["low_entropy_strong"],
            "probabilities": {"trend": 0.7, "range": 0.1, "pullback": 0.1,
                             "transition": 0.05, "breakdown": 0.05},
        }
        adjustments = {
            "adjustments": {"conf_dir_mult": 1.04, "conf_tgt_mult": 1.0,
                           "band_mult": 0.96, "flags": ["trend_boost"]},
        }
        audit = build_regime_audit(features, regime, adjustments)
        assert "regime_v2" in audit
        assert "regime_adjustments" in audit
        assert audit["regime_v2"]["dominant_regime"] == "trend"


# ═══════════════ Integration Tests ═══════════════

class TestRegimeIntegration:
    def test_full_pipeline(self):
        """Test complete pipeline: features → probs → postprocess → adjust → audit"""
        base = {"volatility": 0.04, "ret_1d": 0.01, "ret_7d": 0.03,
                "ret_14d": 0.05, "momentum": 0.1, "price": 50000}
        structure = {"structure_bias_score": 0.2}
        context = {"trend_strength": 0.7, "trend_persistence": 0.6,
                   "trend_exhaustion": 0.1, "reversal_risk": 0.15,
                   "drawdown_pressure": 0.1, "volatility_state": "normal"}
        multiscale = {
            "major": {"structure_bias_score": 0.4},
            "minor": {"structure_bias_score": 0.3},
            "mode": "aligned",
        }

        feats = build_regime_features(base, structure, context, multiscale)
        probs = compute_regime_probabilities(feats, context_phase="continuation")
        post = postprocess_regime(probs)
        adj = apply_regime_adjustments(
            score=0.3, conf_dir=0.5, conf_tgt=0.5, band_mult=1.0, regime=post,
        )
        audit = build_regime_audit(feats, post, adj)

        # Verify complete pipeline output
        assert sum(probs.values()) - 1.0 < 1e-5
        assert post["dominant_regime"] in REGIME_NAMES
        assert 0.0 <= post["regime_entropy"] <= 1.0
        assert 0.0 < adj["conf_dir"] < 1.0
        assert "regime_v2" in audit

    def test_all_five_regimes_can_dominate(self):
        """Across different scenarios, all 5 regimes should appear as dominant."""
        scenarios = [
            (STRONG_TREND, "continuation"),
            (RANGE_BOUND, "mixed_range"),
            (PULLBACK, "pullback"),
            (TRANSITION, "unstable_transition"),
            (BREAKDOWN, "breakdown"),
        ]
        dominants = set()
        for feats, phase in scenarios:
            probs = compute_regime_probabilities(feats, context_phase=phase)
            post = postprocess_regime(probs)
            dominants.add(post["dominant_regime"])

        assert dominants == set(REGIME_NAMES), f"Not all regimes activated: {dominants}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
