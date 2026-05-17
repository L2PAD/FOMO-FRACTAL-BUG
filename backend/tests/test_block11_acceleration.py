"""Block 11 — Data Acceleration Tests"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from forecast.acceleration import (
    get_current_slot,
    get_current_bucket,
    get_bucket_date,
    get_bucket_slot,
    get_overlap_group,
    compute_feature_delta,
    compute_quality_score,
    MIN_FEATURE_DELTA,
)


class TestSlotSystem:
    def test_slot_is_valid(self):
        slot = get_current_slot()
        assert slot in ("00h", "06h", "12h", "18h")

    def test_bucket_format(self):
        bucket = get_current_bucket()
        # Must be YYYY-MM-DD_HHh format
        parts = bucket.split("_")
        assert len(parts) == 2
        date_part = parts[0]
        assert len(date_part) == 10  # YYYY-MM-DD
        slot_part = parts[1]
        assert slot_part in ("00h", "06h", "12h", "18h")

    def test_bucket_date_extraction_new_format(self):
        assert get_bucket_date("2026-03-20_06h") == "2026-03-20"

    def test_bucket_date_extraction_old_format(self):
        assert get_bucket_date("2026-03-20") == "2026-03-20"

    def test_bucket_slot_extraction_new(self):
        assert get_bucket_slot("2026-03-20_06h") == "06h"

    def test_bucket_slot_extraction_old(self):
        assert get_bucket_slot("2026-03-20") == "daily"


class TestOverlapGroup:
    def test_format(self):
        g = get_overlap_group("BTC", "7D", "2026-03-20_06h")
        assert g == "BTC_7D_2026-03-20"

    def test_same_day_same_group(self):
        g1 = get_overlap_group("BTC", "7D", "2026-03-20_00h")
        g2 = get_overlap_group("BTC", "7D", "2026-03-20_18h")
        assert g1 == g2

    def test_different_day_different_group(self):
        g1 = get_overlap_group("BTC", "7D", "2026-03-20_06h")
        g2 = get_overlap_group("BTC", "7D", "2026-03-21_06h")
        assert g1 != g2


class TestFeatureDelta:
    def test_identical_features(self):
        f = {"ret_1d": 0.01, "volatility": 0.03, "momentum": 0.5}
        delta = compute_feature_delta(f, f)
        assert delta == 0.0

    def test_no_previous(self):
        f = {"ret_1d": 0.01}
        delta = compute_feature_delta(f, None)
        assert delta == 1.0

    def test_no_current(self):
        delta = compute_feature_delta(None, {"ret_1d": 0.01})
        assert delta == 1.0

    def test_changed_features(self):
        f1 = {"ret_1d": 0.01, "volatility": 0.03, "momentum": 0.5}
        f2 = {"ret_1d": 0.05, "volatility": 0.06, "momentum": 0.3}
        delta = compute_feature_delta(f1, f2)
        assert delta > 0.0

    def test_small_change_below_threshold(self):
        f1 = {"ret_1d": 0.01, "volatility": 0.03, "momentum": 0.50}
        f2 = {"ret_1d": 0.0101, "volatility": 0.0301, "momentum": 0.501}
        delta = compute_feature_delta(f1, f2)
        assert delta < MIN_FEATURE_DELTA


class TestQualityScore:
    def test_no_change(self):
        score = compute_quality_score(0.0, False, 0.0)
        assert score == 0.0

    def test_maximum_information(self):
        score = compute_quality_score(0.5, True, 1.0)
        assert score == 1.0

    def test_regime_change_boosts_quality(self):
        no_change = compute_quality_score(0.1, False, 0.1)
        with_change = compute_quality_score(0.1, True, 0.1)
        assert with_change > no_change

    def test_bounded(self):
        for fd in [0.0, 0.1, 0.5, 2.0]:
            for rc in [True, False]:
                for vs in [0.0, 0.2, 1.0]:
                    score = compute_quality_score(fd, rc, vs)
                    assert 0.0 <= score <= 1.0
