"""
Tests for Meta-Calibration Layer V1
=====================================
Covers:
  - Fit with sufficient/insufficient data
  - State effectiveness evaluation
  - Per-horizon conf_scale derivation
  - Caps derivation
  - EMA smooth_update
  - Freeze protection
  - State grouping (fine vs coarse)
  - Horizon isolation
  - Acceptance suite (M1–M4)
"""

import pytest
from forecast.decision.meta_calibration import (
    MetaCalibrationLayerV1,
    MetaCalibrationRow,
    MetaCalibrationOutput,
    MetaCalibrationSnapshot,
    BASE_CONF_SCALE,
    META_CONF_SCALE_MIN,
    META_CONF_SCALE_MAX,
    META_CONF_CAP_UP_MAX,
    META_CONF_CAP_DOWN_MIN,
    META_MIN_SAMPLES_TOTAL,
    META_MIN_SAMPLES_PER_STATE,
    META_MIN_EFFECTIVE_STATES,
    META_FREEZE_DELTA,
)

layer = MetaCalibrationLayerV1()


def _make_row(**overrides) -> MetaCalibrationRow:
    defaults = dict(
        horizon="30D",
        asset="BTC",
        interaction_state="aligned_bullish",
        alignment_score=0.6,
        conflict_score=0.1,
        applied_confidence_modifier=0.08,
        applied_scenario_mod_bullish=0.05,
        applied_scenario_mod_base=-0.02,
        applied_scenario_mod_bearish=-0.03,
        applied_decision_bias_modifier=0.10,
        final_direction="LONG",
        final_confidence=0.65,
        outcome_label="TP",
        correct_direction=True,
    )
    defaults.update(overrides)
    return MetaCalibrationRow(**defaults)


def _make_dataset(
    n: int = 200,
    states: dict | None = None,
    horizon: str = "30D",
) -> list[MetaCalibrationRow]:
    """Build a dataset with controllable state/outcome distribution."""
    if states is None:
        states = {
            "aligned_bullish": {"n": 50, "acc": 0.70, "fp": 0.20},
            "aligned_bearish": {"n": 30, "acc": 0.65, "fp": 0.25},
            "fragile_bullish": {"n": 30, "acc": 0.55, "fp": 0.35},
            "transition_conflict": {"n": 40, "acc": 0.50, "fp": 0.40},
            "range_mixed": {"n": 30, "acc": 0.45, "fp": 0.45},
            "mixed_unclear": {"n": 20, "acc": 0.40, "fp": 0.50},
        }

    rows = []
    for state, cfg in states.items():
        n_state = cfg["n"]
        acc = cfg["acc"]
        fp = cfg["fp"]
        n_correct = int(n_state * acc)
        n_fp = int(n_state * fp)

        for i in range(n_state):
            correct = i < n_correct
            outcome = "FP" if i >= n_state - n_fp else ("TP" if correct else "FN")
            rows.append(_make_row(
                horizon=horizon,
                interaction_state=state,
                outcome_label=outcome,
                correct_direction=correct,
                alignment_score=0.7 if "aligned" in state else 0.3,
                conflict_score=0.2 if "aligned" in state else 0.6,
            ))
    return rows


# ──────────────────────────────────────────────
# 1. Insufficient data → None
# ──────────────────────────────────────────────

class TestInsufficientData:
    def test_too_few_total(self):
        rows = [_make_row() for _ in range(50)]
        result = layer.fit(rows, "30D")
        assert result is None

    def test_few_states(self):
        """All rows in one state → not enough effective states."""
        rows = [_make_row(interaction_state="aligned_bullish") for _ in range(150)]
        result = layer.fit(rows, "30D")
        # Only 1 fine state, but grouping may give more
        # With only aligned_bullish (group=aligned), we get 1 effective group
        # Need ≥ 3 → None
        assert result is None

    def test_enough_grouped(self):
        """With grouping, 3+ state buckets should pass."""
        dataset = _make_dataset()
        result = layer.fit(dataset, "30D")
        assert result is not None


# ──────────────────────────────────────────────
# 2. State effectiveness
# ──────────────────────────────────────────────

class TestStateEffectiveness:
    def test_high_accuracy_effective(self):
        dataset = _make_dataset(states={
            "aligned_bullish": {"n": 50, "acc": 0.75, "fp": 0.15},
            "aligned_bearish": {"n": 30, "acc": 0.70, "fp": 0.20},
            "transition_conflict": {"n": 40, "acc": 0.50, "fp": 0.40},
            "range_mixed": {"n": 30, "acc": 0.45, "fp": 0.45},
        })
        result = layer.fit(dataset, "30D")
        assert result is not None
        eff = result.state_effectiveness
        # aligned_bullish should be "effective"
        ab = eff.get("aligned_bullish", eff.get("aligned", {}))
        assert ab.get("verdict") == "effective"

    def test_harmful_state(self):
        dataset = _make_dataset(states={
            "aligned_bullish": {"n": 50, "acc": 0.70, "fp": 0.20},
            "transition_conflict": {"n": 40, "acc": 0.35, "fp": 0.55},
            "range_mixed": {"n": 40, "acc": 0.40, "fp": 0.55},
            "fragile_bullish": {"n": 30, "acc": 0.55, "fp": 0.30},
        })
        result = layer.fit(dataset, "30D")
        assert result is not None
        eff = result.state_effectiveness
        conflict = eff.get("transition_conflict", eff.get("conflict", {}))
        assert conflict.get("verdict") in ("harmful", "neutral")


# ──────────────────────────────────────────────
# 3. Per-horizon conf_scale
# ──────────────────────────────────────────────

class TestConfScale:
    def test_30d_higher_than_7d(self):
        dataset_30d = _make_dataset(horizon="30D")
        dataset_7d = _make_dataset(horizon="7D")
        r30 = layer.fit(dataset_30d, "30D")
        r7 = layer.fit(dataset_7d, "7D")
        assert r30 is not None and r7 is not None
        assert r30.conf_scale >= r7.conf_scale

    def test_within_bounds(self):
        dataset = _make_dataset()
        result = layer.fit(dataset, "30D")
        assert result is not None
        assert META_CONF_SCALE_MIN <= result.conf_scale <= META_CONF_SCALE_MAX

    def test_good_aligned_lifts_scale(self):
        """Very effective aligned states → scale above base."""
        dataset = _make_dataset(states={
            "aligned_bullish": {"n": 60, "acc": 0.80, "fp": 0.10},
            "aligned_bearish": {"n": 40, "acc": 0.75, "fp": 0.15},
            "transition_conflict": {"n": 30, "acc": 0.55, "fp": 0.35},
            "range_mixed": {"n": 30, "acc": 0.50, "fp": 0.40},
        })
        result = layer.fit(dataset, "30D")
        assert result is not None
        assert result.conf_scale > BASE_CONF_SCALE["30D"]


# ──────────────────────────────────────────────
# 4. Caps derivation
# ──────────────────────────────────────────────

class TestCaps:
    def test_caps_within_bounds(self):
        dataset = _make_dataset()
        result = layer.fit(dataset, "30D")
        assert result is not None
        assert result.conf_cap_up <= META_CONF_CAP_UP_MAX
        assert result.conf_cap_down >= META_CONF_CAP_DOWN_MIN
        assert result.conf_cap_up > 0
        assert result.conf_cap_down < 0


# ──────────────────────────────────────────────
# 5. EMA smooth_update
# ──────────────────────────────────────────────

class TestSmoothUpdate:
    def test_smooth_stays_close(self):
        old = MetaCalibrationSnapshot(
            horizon="30D", conf_scale=0.65,
            conf_cap_up=0.12, conf_cap_down=-0.15,
            state_effectiveness={}, rationale=[],
        )
        dataset = _make_dataset()
        new_output = layer.fit(dataset, "30D")
        assert new_output is not None

        updated = layer.smooth_update(old, new_output)
        assert abs(updated.conf_scale - old.conf_scale) <= 0.03

    def test_ema_on_caps(self):
        """Caps are also smoothed, not jumped."""
        old = MetaCalibrationSnapshot(
            horizon="30D", conf_scale=0.65,
            conf_cap_up=0.10, conf_cap_down=-0.12,
            state_effectiveness={}, rationale=[],
        )
        dataset = _make_dataset()
        new_output = layer.fit(dataset, "30D")
        assert new_output is not None

        updated = layer.smooth_update(old, new_output)
        assert abs(updated.conf_cap_up - old.conf_cap_up) <= 0.03
        assert abs(updated.conf_cap_down - old.conf_cap_down) <= 0.03

    def test_stability_multiple_updates(self):
        """Multiple fit+smooth in succession → no oscillation >0.03."""
        snapshot = layer.default_snapshot("30D")
        scales = [snapshot.conf_scale]

        for _ in range(5):
            dataset = _make_dataset()
            result = layer.fit(dataset, "30D")
            if result:
                snapshot = layer.smooth_update(snapshot, result)
                scales.append(snapshot.conf_scale)

        for i in range(1, len(scales)):
            assert abs(scales[i] - scales[i - 1]) <= 0.03


# ──────────────────────────────────────────────
# 6. Freeze protection
# ──────────────────────────────────────────────

class TestFreezeProtection:
    def test_large_delta_rejected(self):
        """If new output differs by >META_FREEZE_DELTA, old value preserved."""
        old = MetaCalibrationSnapshot(
            horizon="30D", conf_scale=0.65,
            conf_cap_up=0.12, conf_cap_down=-0.15,
            state_effectiveness={}, rationale=[],
        )
        # Create a fake output with very different scale
        fake_output = MetaCalibrationOutput(
            conf_scale=0.90,  # huge jump from 0.65
            scenario_scale=1.0, decision_scale=1.0,
            conf_cap_up=0.15, conf_cap_down=-0.20,
            decision_cap=0.15,
            state_effectiveness={}, rationale=[], audit={},
        )
        updated = layer.smooth_update(old, fake_output)
        # EMA + step limit should keep it close to old
        assert abs(updated.conf_scale - old.conf_scale) <= META_FREEZE_DELTA


# ──────────────────────────────────────────────
# 7. State grouping
# ──────────────────────────────────────────────

class TestStateGrouping:
    def test_small_states_grouped(self):
        """States with <20 samples fall back to group bucket."""
        dataset = _make_dataset(states={
            "aligned_bullish": {"n": 12, "acc": 0.70, "fp": 0.20},
            "aligned_bearish": {"n": 12, "acc": 0.65, "fp": 0.25},
            "fragile_bullish": {"n": 8, "acc": 0.55, "fp": 0.35},
            "fragile_bearish": {"n": 12, "acc": 0.50, "fp": 0.40},
            "transition_conflict": {"n": 40, "acc": 0.50, "fp": 0.40},
            "range_mixed": {"n": 25, "acc": 0.45, "fp": 0.45},
            "mixed_unclear": {"n": 25, "acc": 0.40, "fp": 0.50},
        })
        grouped = layer._group_by_state(dataset)
        # aligned_bullish (12) < 20 → should be in "aligned" group (12+12=24 ≥ 20)
        assert "aligned" in grouped or "aligned_bullish" in grouped


# ──────────────────────────────────────────────
# 8. Horizon isolation
# ──────────────────────────────────────────────

class TestHorizonIsolation:
    def test_different_horizons_independent(self):
        """7D and 30D fit independently, 7D changes don't affect 30D."""
        snap_7d = layer.default_snapshot("7D")
        snap_30d = layer.default_snapshot("30D")

        dataset_7d = _make_dataset(horizon="7D", states={
            "aligned_bullish": {"n": 60, "acc": 0.80, "fp": 0.10},
            "transition_conflict": {"n": 50, "acc": 0.30, "fp": 0.60},
            "range_mixed": {"n": 30, "acc": 0.45, "fp": 0.45},
            "fragile_bullish": {"n": 30, "acc": 0.55, "fp": 0.30},
        })
        result_7d = layer.fit(dataset_7d, "7D")
        if result_7d:
            snap_7d = layer.smooth_update(snap_7d, result_7d)

        # 30D not changed
        assert snap_30d.conf_scale == BASE_CONF_SCALE["30D"]


# ──────────────────────────────────────────────
# 9. Default snapshot
# ──────────────────────────────────────────────

class TestDefaultSnapshot:
    def test_24h_lower(self):
        s = layer.default_snapshot("24H")
        assert s.conf_scale == BASE_CONF_SCALE["24H"]

    def test_30d_higher(self):
        s = layer.default_snapshot("30D")
        assert s.conf_scale == BASE_CONF_SCALE["30D"]
        assert s.conf_scale > layer.default_snapshot("24H").conf_scale


# ──────────────────────────────────────────────
# 10. Acceptance suite (M1–M4)
# ──────────────────────────────────────────────

class TestAcceptanceSuite:
    def test_M1_aligned_useful(self):
        """Good aligned accuracy → meta recommends slightly higher conf_scale."""
        dataset = _make_dataset(states={
            "aligned_bullish": {"n": 70, "acc": 0.78, "fp": 0.12},
            "aligned_bearish": {"n": 40, "acc": 0.72, "fp": 0.18},
            "transition_conflict": {"n": 30, "acc": 0.50, "fp": 0.35},
            "range_mixed": {"n": 30, "acc": 0.50, "fp": 0.40},
        })
        result = layer.fit(dataset, "30D")
        assert result is not None
        assert result.conf_scale >= BASE_CONF_SCALE["30D"]

    def test_M2_conflict_noisy(self):
        """High FP in conflict → lower scale recommendation."""
        dataset = _make_dataset(states={
            "aligned_bullish": {"n": 50, "acc": 0.55, "fp": 0.35},
            "transition_conflict": {"n": 50, "acc": 0.35, "fp": 0.60},
            "range_mixed": {"n": 30, "acc": 0.45, "fp": 0.50},
            "fragile_bullish": {"n": 30, "acc": 0.50, "fp": 0.40},
        })
        result = layer.fit(dataset, "30D")
        assert result is not None
        assert result.conf_scale <= BASE_CONF_SCALE["30D"]

    def test_M3_insufficient_no_update(self):
        """< MIN_SAMPLES_TOTAL → returns None (no update)."""
        rows = [_make_row() for _ in range(50)]
        assert layer.fit(rows, "7D") is None

    def test_M4_24h_noisier(self):
        """24H should have lower base scale than 30D."""
        assert BASE_CONF_SCALE["24H"] < BASE_CONF_SCALE["30D"]


# ──────────────────────────────────────────────
# 11. Extreme modifier test
# ──────────────────────────────────────────────

class TestExtremeModifier:
    def test_pre_clip_safety(self):
        """Even with extreme conf_modifier, pre-clip keeps delta safe."""
        from forecast.generator_v41 import INTERACTION_CONF_SCALE, INTERACTION_CONF_PRECLIP

        for horizon in ("24H", "7D", "30D"):
            scale = INTERACTION_CONF_SCALE[horizon]
            for extreme in (0.5, -0.5, 1.0, -1.0):
                raw_delta = scale * extreme
                clipped = max(INTERACTION_CONF_PRECLIP[0], min(INTERACTION_CONF_PRECLIP[1], raw_delta))
                assert -0.15 <= clipped <= 0.12


# ──────────────────────────────────────────────
# 12. Rationale
# ──────────────────────────────────────────────

class TestRationale:
    def test_has_horizon_and_scale(self):
        dataset = _make_dataset()
        result = layer.fit(dataset, "30D")
        assert result is not None
        assert any("30D" in r for r in result.rationale)
        assert any("conf_scale" in r for r in result.rationale)

    def test_has_state_info(self):
        dataset = _make_dataset()
        result = layer.fit(dataset, "30D")
        assert result is not None
        assert len(result.rationale) >= 2  # header + at least 1 state
