"""Block 8.1 — Confidence Calibration Tests"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from exchange.calibration.confidence_calibrator import (
    calibrate_confidence,
    calibrate_confidence_target,
    get_calibration_info,
    CALIBRATION_ANCHORS_BY_HORIZON,
)


class TestCalibrationAnchors:
    """Validate calibration anchor integrity."""

    def test_all_horizons_defined(self):
        for h in ["24H", "7D", "30D"]:
            assert h in CALIBRATION_ANCHORS_BY_HORIZON

    @pytest.mark.parametrize("horizon", ["24H", "7D", "30D"])
    def test_anchors_monotonic(self, horizon):
        """Anchors must be monotonically increasing."""
        anchors = CALIBRATION_ANCHORS_BY_HORIZON[horizon]
        for i in range(1, len(anchors)):
            assert anchors[i][0] >= anchors[i - 1][0], f"raw not monotonic at {i}"
            assert anchors[i][1] >= anchors[i - 1][1], f"calibrated not monotonic at {i}"

    @pytest.mark.parametrize("horizon", ["24H", "7D", "30D"])
    def test_anchors_bounded(self, horizon):
        """All anchor values must be in [0, 1]."""
        for raw, cal in CALIBRATION_ANCHORS_BY_HORIZON[horizon]:
            assert 0.0 <= raw <= 1.0
            assert 0.0 <= cal <= 1.0

    @pytest.mark.parametrize("horizon", ["24H", "7D", "30D"])
    def test_floor_ceiling(self, horizon):
        """First anchor starts at 0, last ends at or near 1."""
        anchors = CALIBRATION_ANCHORS_BY_HORIZON[horizon]
        assert anchors[0][0] == 0.0
        assert anchors[-1][0] == 1.0


class TestCalibrationFunction:
    """Test the calibrate_confidence function."""

    def test_zero_input(self):
        assert calibrate_confidence(0.0, "7D") == 0.0

    def test_one_input(self):
        assert calibrate_confidence(1.0, "7D") == 1.0

    @pytest.mark.parametrize("horizon", ["24H", "7D", "30D"])
    def test_output_bounded(self, horizon):
        for raw in [0.0, 0.05, 0.1, 0.3, 0.5, 0.7, 0.9, 1.0]:
            result = calibrate_confidence(raw, horizon)
            assert 0.0 <= result <= 1.0, f"Out of bounds: {raw} -> {result} for {horizon}"

    @pytest.mark.parametrize("horizon", ["24H", "7D", "30D"])
    def test_monotonic_output(self, horizon):
        """Higher raw input must produce >= calibrated output."""
        prev = 0.0
        for raw in [i / 100 for i in range(0, 101, 5)]:
            result = calibrate_confidence(raw, horizon)
            assert result >= prev, f"Not monotonic: raw={raw}, result={result}, prev={prev}"
            prev = result

    def test_clipping_below_zero(self):
        result = calibrate_confidence(-0.5, "7D")
        assert result == 0.0

    def test_clipping_above_one(self):
        result = calibrate_confidence(1.5, "7D")
        assert result == 1.0

    def test_unknown_horizon_uses_default(self):
        result = calibrate_confidence(0.45, "UNKNOWN")
        assert 0.0 < result < 1.0


class TestCalibrationDirection:
    """Test per-horizon direction of calibration."""

    def test_7d_underconfident_correction(self):
        """7D model is underconfident: calibrated should be HIGHER than raw."""
        raw = 0.43
        cal = calibrate_confidence(raw, "7D")
        assert cal > raw, f"7D should increase: raw={raw}, cal={cal}"

    def test_30d_overconfident_correction(self):
        """30D model is now overconfident after diversification: calibrated should be LOWER."""
        raw = 0.50
        cal = calibrate_confidence(raw, "30D")
        assert cal < raw, f"30D should decrease: raw={raw}, cal={cal}"

    def test_24h_overconfident_correction(self):
        """24H model is overconfident: calibrated should be LOWER at mid range."""
        raw = 0.30
        cal = calibrate_confidence(raw, "24H")
        assert cal < raw, f"24H should decrease: raw={raw}, cal={cal}"


class TestTargetCalibration:
    """Test target calibration (always lower than direction)."""

    @pytest.mark.parametrize("horizon", ["24H", "7D", "30D"])
    def test_target_lower_than_direction(self, horizon):
        for raw in [0.1, 0.3, 0.5, 0.7]:
            dir_cal = calibrate_confidence(raw, horizon)
            tgt_cal = calibrate_confidence_target(raw, horizon)
            assert tgt_cal <= dir_cal, f"Target should be <= direction: {tgt_cal} > {dir_cal}"


class TestCalibrationInfo:
    """Test calibration metadata."""

    @pytest.mark.parametrize("horizon", ["24H", "7D", "30D"])
    def test_info_structure(self, horizon):
        info = get_calibration_info(horizon)
        assert info["horizon"] == horizon
        assert info["method"] == "piecewise_linear_per_horizon"
        assert info["version"] == "8.1"
        assert info["status"] == "active"
        assert len(info["anchors"]) > 0
