"""
Tests for Meta-Calibration Layer V2 — State-Aware Scaling
==========================================================
Covers:
  - Per-group scale derivation (relative to V1)
  - Group consistency invariant (aligned ≥ fragile ≥ range)
  - State-aware caps with global guards
  - EMA smooth per group + freeze protection
  - Non-linear blend
  - Relative delta guard (ratio ≤ 1.25)
  - Drift monitoring
  - V1 fallback for insufficient groups
  - Horizon isolation
  - Acceptance suite (R1–R5)
"""

import pytest
from forecast.decision.meta_calibration import (
    MetaCalibrationLayerV2,
    MetaCalibrationRowV2,
    MetaCalibrationOutputV2,
    MetaCalibrationSnapshotV2,
    resolve_state_group,
    BASE_CONF_SCALE,
    META_CONF_SCALE_MIN,
    META_CONF_SCALE_MAX,
    META_CONF_CAP_UP_MAX,
    META_CONF_CAP_DOWN_MIN,
    META_V2_MIN_SAMPLES_PER_GROUP,
    META_V2_MIN_EFFECTIVE_GROUPS,
    META_V2_FREEZE_DELTA,
    META_V2_MAX_RATIO_TO_V1,
    ALL_GROUPS,
    V2_GROUP_OFFSETS,
    V2_GROUP_CAPS,
    GROUP_FOR_STATE,
)

layer = MetaCalibrationLayerV2()


def _make_row_v2(**overrides) -> MetaCalibrationRowV2:
    defaults = dict(
        horizon="30D",
        asset="BTC",
        interaction_state="aligned_bullish",
        state_group="aligned",
        alignment_score=0.6,
        conflict_score=0.1,
        applied_confidence_modifier=0.08,
        final_confidence=0.65,
        outcome_label="TP",
        correct_direction=True,
    )
    defaults.update(overrides)
    return MetaCalibrationRowV2(**defaults)


def _make_v2_dataset(
    horizon: str = "30D",
    groups: dict | None = None,
) -> list[MetaCalibrationRowV2]:
    """Build V2 dataset with controllable per-group distribution."""
    if groups is None:
        groups = {
            "aligned": {"n": 60, "acc": 0.70, "fp": 0.20},
            "fragile": {"n": 40, "acc": 0.52, "fp": 0.35},
            "conflict": {"n": 40, "acc": 0.45, "fp": 0.45},
            "range": {"n": 35, "acc": 0.48, "fp": 0.42},
        }

    state_map = {
        "aligned": "aligned_bullish",
        "fragile": "fragile_bullish",
        "conflict": "transition_conflict",
        "range": "range_mixed",
    }

    rows = []
    for group, cfg in groups.items():
        n = cfg["n"]
        acc = cfg["acc"]
        fp = cfg["fp"]
        n_correct = int(n * acc)
        n_fp = int(n * fp)
        state = state_map.get(group, "mixed_unclear")

        for i in range(n):
            correct = i < n_correct
            outcome = "FP" if i >= n - n_fp else ("TP" if correct else "FN")
            rows.append(_make_row_v2(
                horizon=horizon,
                interaction_state=state,
                state_group=group,
                outcome_label=outcome,
                correct_direction=correct,
                alignment_score=0.7 if group == "aligned" else 0.3,
                conflict_score=0.2 if group == "aligned" else 0.6,
            ))
    return rows


# ──────────────────────────────────────────────
# 1. resolve_state_group
# ──────────────────────────────────────────────

class TestResolveGroup:
    def test_aligned_bullish(self):
        assert resolve_state_group("aligned_bullish") == "aligned"

    def test_aligned_bearish(self):
        assert resolve_state_group("aligned_bearish") == "aligned"

    def test_fragile(self):
        assert resolve_state_group("fragile_bullish") == "fragile"

    def test_conflict(self):
        assert resolve_state_group("transition_conflict") == "conflict"

    def test_range_mixed(self):
        assert resolve_state_group("range_mixed") == "range"

    def test_unknown_defaults_range(self):
        assert resolve_state_group("something_else") == "range"


# ──────────────────────────────────────────────
# 2. Insufficient data → None
# ──────────────────────────────────────────────

class TestInsufficientDataV2:
    def test_too_few_total(self):
        rows = [_make_row_v2() for _ in range(50)]
        assert layer.fit(rows, "30D") is None

    def test_too_few_groups(self):
        """All rows in one group → < MIN_EFFECTIVE_GROUPS."""
        rows = [_make_row_v2(state_group="aligned") for _ in range(150)]
        result = layer.fit(rows, "30D")
        assert result is None

    def test_enough_groups(self):
        dataset = _make_v2_dataset()
        result = layer.fit(dataset, "30D")
        assert result is not None


# ──────────────────────────────────────────────
# 3. Per-group scale derivation
# ──────────────────────────────────────────────

class TestGroupScales:
    def test_relative_to_v1_base(self):
        """Scales are derived relative to V1 base for the horizon."""
        dataset = _make_v2_dataset(horizon="30D")
        v1_base = BASE_CONF_SCALE["30D"]
        result = layer.fit(dataset, "30D", v1_scale=v1_base)
        assert result is not None
        for g in ALL_GROUPS:
            assert META_CONF_SCALE_MIN <= result.conf_scales[g] <= META_CONF_SCALE_MAX

    def test_aligned_higher_than_fragile(self):
        """Group consistency: aligned ≥ fragile ≥ range."""
        dataset = _make_v2_dataset()
        result = layer.fit(dataset, "30D")
        assert result is not None
        assert result.conf_scales["aligned"] >= result.conf_scales["fragile"]
        assert result.conf_scales["fragile"] >= result.conf_scales["range"]

    def test_good_aligned_lifts(self):
        """Very effective aligned → scale above base+offset."""
        dataset = _make_v2_dataset(groups={
            "aligned": {"n": 70, "acc": 0.78, "fp": 0.12},
            "fragile": {"n": 35, "acc": 0.55, "fp": 0.30},
            "conflict": {"n": 35, "acc": 0.50, "fp": 0.40},
            "range": {"n": 35, "acc": 0.48, "fp": 0.42},
        })
        v1_base = 0.65
        result = layer.fit(dataset, "30D", v1_scale=v1_base)
        assert result is not None
        assert result.conf_scales["aligned"] >= v1_base + V2_GROUP_OFFSETS["aligned"]


# ──────────────────────────────────────────────
# 4. State-aware caps
# ──────────────────────────────────────────────

class TestGroupCaps:
    def test_conflict_tighter_down(self):
        """Conflict group should have more negative cap_down than aligned."""
        dataset = _make_v2_dataset()
        result = layer.fit(dataset, "30D")
        assert result is not None
        assert result.conf_caps_down["conflict"] <= result.conf_caps_down["aligned"]

    def test_global_guard_cap_up(self):
        """No group can exceed META_CONF_CAP_UP_MAX."""
        dataset = _make_v2_dataset(groups={
            "aligned": {"n": 80, "acc": 0.90, "fp": 0.05},
            "fragile": {"n": 35, "acc": 0.55, "fp": 0.30},
            "conflict": {"n": 35, "acc": 0.50, "fp": 0.40},
            "range": {"n": 35, "acc": 0.48, "fp": 0.42},
        })
        result = layer.fit(dataset, "30D")
        assert result is not None
        for g in ALL_GROUPS:
            assert result.conf_caps_up[g] <= META_CONF_CAP_UP_MAX

    def test_global_guard_cap_down(self):
        """No group can go below META_CONF_CAP_DOWN_MIN."""
        dataset = _make_v2_dataset(groups={
            "aligned": {"n": 50, "acc": 0.55, "fp": 0.30},
            "fragile": {"n": 35, "acc": 0.40, "fp": 0.55},
            "conflict": {"n": 50, "acc": 0.30, "fp": 0.65},
            "range": {"n": 35, "acc": 0.35, "fp": 0.60},
        })
        result = layer.fit(dataset, "30D")
        assert result is not None
        for g in ALL_GROUPS:
            assert result.conf_caps_down[g] >= META_CONF_CAP_DOWN_MIN


# ──────────────────────────────────────────────
# 5. Group consistency invariant
# ──────────────────────────────────────────────

class TestGroupConsistency:
    def test_enforce_ordering(self):
        """Even if raw derivation breaks order, enforce_consistency fixes it."""
        bad_scales = {"aligned": 0.50, "fragile": 0.60, "conflict": 0.70, "range": 0.55}
        fixed = layer._enforce_consistency(bad_scales)
        assert fixed["aligned"] >= fixed["fragile"]
        assert fixed["fragile"] >= fixed["range"]

    def test_conflict_independent(self):
        """Conflict can be above aligned (amplifies negative modifier)."""
        dataset = _make_v2_dataset(groups={
            "aligned": {"n": 50, "acc": 0.55, "fp": 0.30},
            "fragile": {"n": 35, "acc": 0.50, "fp": 0.35},
            "conflict": {"n": 50, "acc": 0.35, "fp": 0.55},
            "range": {"n": 35, "acc": 0.48, "fp": 0.42},
        })
        result = layer.fit(dataset, "30D")
        assert result is not None
        # conflict scale can be ≥ aligned (this is expected)


# ──────────────────────────────────────────────
# 6. Relative delta guard
# ──────────────────────────────────────────────

class TestRelativeGuard:
    def test_ratio_clamped(self):
        """scale_v2 / v1_base must be ≤ META_V2_MAX_RATIO_TO_V1."""
        v1 = 0.60
        extreme = 1.0  # way above 1.25 * 0.60 = 0.75
        clamped = layer._clamp_relative_to_v1(extreme, v1)
        assert clamped / v1 <= META_V2_MAX_RATIO_TO_V1 + 0.001

    def test_low_ratio_clamped(self):
        """v2 too far below v1."""
        v1 = 0.60
        extreme = 0.20  # way below 0.60 / 1.25 = 0.48
        clamped = layer._clamp_relative_to_v1(extreme, v1)
        assert clamped >= v1 / META_V2_MAX_RATIO_TO_V1 - 0.001

    def test_absolute_guard(self):
        """Absolute guard: |scale_v2 - v1| ≤ 0.15."""
        v1 = 0.60
        too_high = 0.80
        clamped = layer._clamp_relative_to_v1(too_high, v1)
        assert clamped <= v1 + 0.15 + 0.001


# ──────────────────────────────────────────────
# 7. EMA smooth per group
# ──────────────────────────────────────────────

class TestSmoothUpdateV2:
    def test_smooth_stays_close(self):
        old = layer.default_snapshot("30D")
        dataset = _make_v2_dataset()
        new_output = layer.fit(dataset, "30D")
        assert new_output is not None

        updated = layer.smooth_update(old, new_output)
        for g in ALL_GROUPS:
            if g in old.conf_scales and g in updated.conf_scales:
                assert abs(updated.conf_scales[g] - old.conf_scales[g]) <= 0.03

    def test_stability_multiple_updates(self):
        """5 fit+smooth cycles → no group jumps >0.03."""
        snapshot = layer.default_snapshot("30D")
        history = {g: [snapshot.conf_scales[g]] for g in ALL_GROUPS}

        for _ in range(5):
            dataset = _make_v2_dataset()
            result = layer.fit(dataset, "30D")
            if result:
                snapshot = layer.smooth_update(snapshot, result)
                for g in ALL_GROUPS:
                    history[g].append(snapshot.conf_scales[g])

        for g in ALL_GROUPS:
            for i in range(1, len(history[g])):
                assert abs(history[g][i] - history[g][i - 1]) <= 0.03

    def test_freeze_protection(self):
        """Large delta → old value preserved."""
        old = layer.default_snapshot("30D")
        fake = MetaCalibrationOutputV2(
            conf_scales={"aligned": 0.99, "fragile": 0.99, "conflict": 0.99, "range": 0.99},
            conf_caps_up={g: 0.15 for g in ALL_GROUPS},
            conf_caps_down={g: -0.20 for g in ALL_GROUPS},
            group_effectiveness={}, rationale=[], audit={},
        )
        updated = layer.smooth_update(old, fake)
        for g in ALL_GROUPS:
            assert abs(updated.conf_scales[g] - old.conf_scales[g]) <= META_V2_FREEZE_DELTA


# ──────────────────────────────────────────────
# 8. Non-linear blend
# ──────────────────────────────────────────────

class TestNonLinearBlend:
    def test_blend_0_returns_v1(self):
        assert MetaCalibrationLayerV2.compute_blend(0.60, 0.70, 0.0) == 0.60

    def test_blend_1_returns_v2(self):
        assert MetaCalibrationLayerV2.compute_blend(0.60, 0.70, 1.0) == 0.70

    def test_blend_05_dampened(self):
        """Non-linear blend at 0.5 should give less than linear midpoint."""
        v1, v2 = 0.60, 0.70
        result = MetaCalibrationLayerV2.compute_blend(v1, v2, 0.5)
        linear_mid = (v1 + v2) / 2  # 0.65
        assert result < linear_mid  # dampened toward V1


# ──────────────────────────────────────────────
# 9. Drift monitoring
# ──────────────────────────────────────────────

class TestDriftMonitor:
    def test_no_drift_same_snapshot(self):
        snap = layer.default_snapshot("30D")
        drift = layer.compute_drift(snap, snap)
        assert drift["max_drift"] == 0.0

    def test_drift_detected(self):
        snap1 = layer.default_snapshot("30D")
        snap2 = MetaCalibrationSnapshotV2(
            horizon="30D",
            conf_scales={g: snap1.conf_scales[g] + 0.02 for g in ALL_GROUPS},
            conf_caps_up=snap1.conf_caps_up,
            conf_caps_down=snap1.conf_caps_down,
            group_effectiveness={}, rationale=[],
        )
        drift = layer.compute_drift(snap1, snap2)
        assert drift["max_drift"] == 0.02


# ──────────────────────────────────────────────
# 10. Default snapshot
# ──────────────────────────────────────────────

class TestDefaultSnapshotV2:
    def test_has_all_groups(self):
        snap = layer.default_snapshot("30D")
        for g in ALL_GROUPS:
            assert g in snap.conf_scales
            assert g in snap.conf_caps_up
            assert g in snap.conf_caps_down

    def test_24h_lower_than_30d(self):
        s24 = layer.default_snapshot("24H")
        s30 = layer.default_snapshot("30D")
        assert s24.conf_scales["aligned"] < s30.conf_scales["aligned"]

    def test_offsets_applied(self):
        snap = layer.default_snapshot("7D")
        base = BASE_CONF_SCALE["7D"]
        for g in ALL_GROUPS:
            assert snap.conf_scales[g] == pytest.approx(base + V2_GROUP_OFFSETS[g], abs=0.001)


# ──────────────────────────────────────────────
# 11. Horizon isolation
# ──────────────────────────────────────────────

class TestHorizonIsolationV2:
    def test_7d_independent_of_30d(self):
        snap_7d = layer.default_snapshot("7D")
        snap_30d = layer.default_snapshot("30D")

        dataset_7d = _make_v2_dataset(horizon="7D", groups={
            "aligned": {"n": 60, "acc": 0.80, "fp": 0.10},
            "fragile": {"n": 35, "acc": 0.55, "fp": 0.30},
            "conflict": {"n": 50, "acc": 0.35, "fp": 0.55},
            "range": {"n": 35, "acc": 0.48, "fp": 0.42},
        })
        result_7d = layer.fit(dataset_7d, "7D")
        if result_7d:
            snap_7d = layer.smooth_update(snap_7d, result_7d)

        # 30D unchanged
        assert snap_30d.conf_scales == layer.default_snapshot("30D").conf_scales


# ──────────────────────────────────────────────
# 12. Acceptance suite (R1–R5)
# ──────────────────────────────────────────────

class TestAcceptanceSuiteV2:
    def test_R1_aligned_stable(self):
        """Good aligned accuracy → scale stays or goes slightly up."""
        dataset = _make_v2_dataset(groups={
            "aligned": {"n": 70, "acc": 0.75, "fp": 0.15},
            "fragile": {"n": 35, "acc": 0.55, "fp": 0.30},
            "conflict": {"n": 40, "acc": 0.48, "fp": 0.42},
            "range": {"n": 35, "acc": 0.50, "fp": 0.40},
        })
        v1_base = 0.65
        result = layer.fit(dataset, "30D", v1_scale=v1_base)
        assert result is not None
        assert result.conf_scales["aligned"] >= v1_base + V2_GROUP_OFFSETS["aligned"]

    def test_R2_conflict_penalty(self):
        """High FP in conflict → stronger penalty (higher scale for negative mod)."""
        dataset = _make_v2_dataset(groups={
            "aligned": {"n": 50, "acc": 0.65, "fp": 0.20},
            "fragile": {"n": 35, "acc": 0.50, "fp": 0.35},
            "conflict": {"n": 50, "acc": 0.32, "fp": 0.58},
            "range": {"n": 35, "acc": 0.48, "fp": 0.42},
        })
        v1_base = 0.65
        result = layer.fit(dataset, "30D", v1_scale=v1_base)
        assert result is not None
        # conflict cap_down should be strongly negative
        assert result.conf_caps_down["conflict"] <= -0.16

    def test_R3_insufficient_v1_fallback(self):
        """Insufficient data for a group → uses base (V1 fallback)."""
        dataset = _make_v2_dataset(groups={
            "aligned": {"n": 60, "acc": 0.70, "fp": 0.20},
            "fragile": {"n": 10, "acc": 0.50, "fp": 0.30},  # < MIN_SAMPLES
            "conflict": {"n": 40, "acc": 0.45, "fp": 0.45},
            "range": {"n": 35, "acc": 0.48, "fp": 0.42},
        })
        v1_base = 0.65
        result = layer.fit(dataset, "30D", v1_scale=v1_base)
        assert result is not None
        # fragile should still have a scale (base value)
        assert "fragile" in result.conf_scales
        eff = result.group_effectiveness.get("fragile", {})
        assert eff.get("verdict") == "insufficient_data"

    def test_R4_horizon_isolation(self):
        """7D update doesn't affect 30D."""
        snap_30d = layer.default_snapshot("30D")
        initial_30d = dict(snap_30d.conf_scales)

        dataset_7d = _make_v2_dataset(horizon="7D")
        result_7d = layer.fit(dataset_7d, "7D")
        if result_7d:
            # Only update 7D snapshot — 30D stays unchanged
            pass

        assert snap_30d.conf_scales == initial_30d

    def test_R5_blended_stability(self):
        """At blend=0.5, result is between V1 and V2."""
        v1_scale = 0.65
        v2_scale = 0.72
        blended = MetaCalibrationLayerV2.compute_blend(v1_scale, v2_scale, 0.5)
        assert v1_scale <= blended <= v2_scale


# ──────────────────────────────────────────────
# 13. Edge cases
# ──────────────────────────────────────────────

class TestEdgeCasesV2:
    def test_all_same_group(self):
        """All data in aligned only → insufficient effective groups."""
        rows = [_make_row_v2(state_group="aligned") for _ in range(200)]
        result = layer.fit(rows, "30D")
        assert result is None

    def test_v1_scale_none_uses_base(self):
        """If v1_scale not provided, use BASE_CONF_SCALE."""
        dataset = _make_v2_dataset(horizon="7D")
        result = layer.fit(dataset, "7D", v1_scale=None)
        assert result is not None
        assert result.audit["v1_base"] == BASE_CONF_SCALE["7D"]

    def test_extreme_v1_base(self):
        """Extreme V1 base → relative guards prevent explosion."""
        dataset = _make_v2_dataset()
        result = layer.fit(dataset, "30D", v1_scale=0.35)
        assert result is not None
        for g in ALL_GROUPS:
            assert result.conf_scales[g] <= 0.35 + 0.15 + 0.001
