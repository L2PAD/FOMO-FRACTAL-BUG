"""Block 8.2 — Calibration Metrics Tests"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from exchange.calibration.calibration_metrics import (
    compute_brier_score,
    compute_ece,
    compute_sharpness,
)


class TestBrierScore:
    """Brier score validation."""

    def test_perfect_predictions(self):
        """Perfect calibration → Brier = 0."""
        preds = [
            {"confidence": 1.0, "correct": True},
            {"confidence": 0.0, "correct": False},
        ]
        assert compute_brier_score(preds) == 0.0

    def test_worst_predictions(self):
        """Worst calibration → Brier = 1."""
        preds = [
            {"confidence": 1.0, "correct": False},
            {"confidence": 0.0, "correct": True},
        ]
        assert compute_brier_score(preds) == 1.0

    def test_mid_predictions(self):
        """All 0.5 → Brier = 0.25."""
        preds = [
            {"confidence": 0.5, "correct": True},
            {"confidence": 0.5, "correct": False},
        ]
        assert compute_brier_score(preds) == 0.25

    def test_empty_returns_none(self):
        assert compute_brier_score([]) is None

    def test_brier_bounded(self):
        """Brier must be in [0, 1]."""
        preds = [{"confidence": 0.3, "correct": True}] * 50 + \
                [{"confidence": 0.7, "correct": False}] * 50
        result = compute_brier_score(preds)
        assert 0.0 <= result <= 1.0


class TestECE:
    """Expected Calibration Error validation."""

    def test_perfect_calibration(self):
        """All 0.6 confidence with 60% accuracy → ECE ≈ 0."""
        preds = [{"confidence": 0.6, "correct": True}] * 60 + \
                [{"confidence": 0.6, "correct": False}] * 40
        ece, buckets = compute_ece(preds, n_bins=5)
        assert ece < 0.01

    def test_empty_returns_none(self):
        ece, buckets = compute_ece([], n_bins=5)
        assert ece is None
        assert buckets == []

    def test_ece_non_negative(self):
        preds = [{"confidence": 0.3, "correct": True}] * 30 + \
                [{"confidence": 0.8, "correct": False}] * 70
        ece, _ = compute_ece(preds, n_bins=5)
        assert ece >= 0

    def test_bucket_structure(self):
        preds = [{"confidence": 0.5, "correct": True}] * 10
        _, buckets = compute_ece(preds, n_bins=5)
        assert len(buckets) == 5
        for b in buckets:
            assert "range" in b
            assert "avgConf" in b
            assert "accuracy" in b
            assert "gap" in b
            assert "count" in b

    def test_buckets_cover_range(self):
        preds = [{"confidence": 0.5, "correct": True}]
        _, buckets = compute_ece(preds, n_bins=5)
        assert buckets[0]["range"][0] == 0.0
        assert buckets[-1]["range"][1] == 1.0


class TestSharpness:
    """Sharpness = variance of confidence."""

    def test_flat_model(self):
        """All same confidence → sharpness = 0."""
        preds = [{"confidence": 0.5, "correct": True}] * 100
        assert compute_sharpness(preds) == 0.0

    def test_sharp_model(self):
        """Mix of high and low confidence → sharpness > 0."""
        preds = [{"confidence": 0.1, "correct": False}] * 50 + \
                [{"confidence": 0.9, "correct": True}] * 50
        result = compute_sharpness(preds)
        assert result > 0.1

    def test_empty_returns_none(self):
        assert compute_sharpness([]) is None

    def test_sharpness_non_negative(self):
        preds = [{"confidence": 0.3, "correct": True}, {"confidence": 0.7, "correct": False}]
        assert compute_sharpness(preds) >= 0
