"""
Tactical Layer Core Tests
===========================
Block X — Tests for signal builder, fusion engine, and advisor.
"""

import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _snap(**overrides):
    base = {
        "imbalance": 0.0, "dominance": 0.5, "aggressor_bias": "NEUTRAL",
        "long_liq_volume": 0, "short_liq_volume": 0,
        "cascade_active": False, "cascade_direction": "", "cascade_phase": "",
        "funding_score": 0.0, "funding_trend": 0.0, "funding_label": "NEUTRAL",
        "absorption": False, "absorption_side": "",
        "volume_delta": 0, "oi_delta_pct": 0,
        "uncertainty": 0.5, "regime": "range", "phase": None,
    }
    base.update(overrides)
    return base


class TestSignalBuilder:
    def test_neutral_baseline(self):
        from tactical.tactical_signal_builder import build_tactical_signals
        s = build_tactical_signals(_snap())
        assert not s["bearish_orderflow"]
        assert not s["bullish_orderflow"]
        assert not s["forced_selling"]
        assert not s["crowded_longs"]

    def test_bearish_orderflow(self):
        from tactical.tactical_signal_builder import build_tactical_signals
        s = build_tactical_signals(_snap(imbalance=-0.3, dominance=0.7))
        assert s["bearish_orderflow"]
        assert not s["bullish_orderflow"]

    def test_bullish_orderflow(self):
        from tactical.tactical_signal_builder import build_tactical_signals
        s = build_tactical_signals(_snap(imbalance=0.3, dominance=0.7))
        assert s["bullish_orderflow"]
        assert not s["bearish_orderflow"]

    def test_forced_selling(self):
        from tactical.tactical_signal_builder import build_tactical_signals
        s = build_tactical_signals(_snap(
            cascade_active=True, cascade_direction="LONG", cascade_phase="PEAK",
        ))
        assert s["forced_selling"]
        assert not s["forced_buying"]

    def test_forced_buying(self):
        from tactical.tactical_signal_builder import build_tactical_signals
        s = build_tactical_signals(_snap(
            cascade_active=True, cascade_direction="SHORT", cascade_phase="START",
        ))
        assert s["forced_buying"]

    def test_crowded_longs(self):
        from tactical.tactical_signal_builder import build_tactical_signals
        s = build_tactical_signals(_snap(funding_label="BULLISH_EXTREME"))
        assert s["crowded_longs"]

    def test_crowded_shorts(self):
        from tactical.tactical_signal_builder import build_tactical_signals
        s = build_tactical_signals(_snap(funding_score=-0.7))
        assert s["crowded_shorts"]

    def test_seller_exhaustion(self):
        from tactical.tactical_signal_builder import build_tactical_signals
        s = build_tactical_signals(_snap(absorption=True, absorption_side="ASK"))
        assert s["seller_exhaustion"]
        assert not s["buyer_exhaustion"]

    def test_liquidation_imbalance(self):
        from tactical.tactical_signal_builder import build_tactical_signals
        s = build_tactical_signals(_snap(long_liq_volume=100000, short_liq_volume=20000))
        assert s["liquidation_imbalance_direction"] == "long"

    def test_high_volatility(self):
        from tactical.tactical_signal_builder import build_tactical_signals
        s = build_tactical_signals(_snap(oi_delta_pct=4.5))
        assert s["high_volatility"]


class TestFusionEngine:
    def test_neutral_no_signals(self):
        from tactical.tactical_fusion_engine import fuse_tactical_signals
        from tactical.tactical_signal_builder import build_tactical_signals
        signals = build_tactical_signals(_snap())
        fusion = fuse_tactical_signals(signals)
        assert fusion["bias"] == "neutral"
        assert fusion["score"] == 0.0

    def test_bearish_cascade(self):
        from tactical.tactical_fusion_engine import fuse_tactical_signals
        from tactical.tactical_signal_builder import build_tactical_signals
        signals = build_tactical_signals(_snap(
            cascade_active=True, cascade_direction="LONG", cascade_phase="PEAK",
            imbalance=-0.3, dominance=0.7,
        ))
        fusion = fuse_tactical_signals(signals)
        assert fusion["bias"] == "bearish"
        assert fusion["score"] <= -2.0

    def test_bullish_squeeze(self):
        from tactical.tactical_fusion_engine import fuse_tactical_signals
        from tactical.tactical_signal_builder import build_tactical_signals
        signals = build_tactical_signals(_snap(
            cascade_active=True, cascade_direction="SHORT", cascade_phase="START",
            imbalance=0.3, dominance=0.7,
        ))
        fusion = fuse_tactical_signals(signals)
        assert fusion["bias"] == "bullish"
        assert fusion["score"] >= 2.0

    def test_single_weak_signal_stays_neutral(self):
        """Single weak signal should NOT flip bias.
        With calibrated threshold (1.0), need opposing signals to stay neutral.
        seller_exhaustion (+0.8) partially cancels bearish_orderflow (-1.0) → score -0.2 → neutral.
        """
        from tactical.tactical_fusion_engine import fuse_tactical_signals
        from tactical.tactical_signal_builder import build_tactical_signals
        # bearish_orderflow (-1.0) + seller_exhaustion (+0.8) → net -0.2 → neutral
        signals = build_tactical_signals(_snap(
            imbalance=-0.3, dominance=0.7,
            absorption=True, absorption_side="ASK",
        ))
        fusion = fuse_tactical_signals(signals)
        assert fusion["bias"] == "neutral"

    def test_stacked_signals_flip(self):
        """Multiple aligned signals should flip bias."""
        from tactical.tactical_fusion_engine import fuse_tactical_signals
        from tactical.tactical_signal_builder import build_tactical_signals
        signals = build_tactical_signals(_snap(
            imbalance=-0.3, dominance=0.7,  # bearish_orderflow = -1.0
            funding_label="BULLISH_EXTREME",  # crowded_longs = -1.5
        ))
        fusion = fuse_tactical_signals(signals)
        assert fusion["bias"] == "bearish"
        assert fusion["bearish_count"] >= 2


class TestAdvisor:
    def test_default_neutral(self):
        from tactical.tactical_signal_builder import build_tactical_signals
        from tactical.tactical_fusion_engine import fuse_tactical_signals
        from tactical.tactical_advisor import build_tactical_advice
        snap = _snap()
        signals = build_tactical_signals(snap)
        fusion = fuse_tactical_signals(signals)
        advice = build_tactical_advice(fusion, snap)
        assert advice["executionAdvice"] == "normal"
        assert advice["tacticalBias"] == "neutral"

    def test_cascade_wait(self):
        from tactical.tactical_signal_builder import build_tactical_signals
        from tactical.tactical_fusion_engine import fuse_tactical_signals
        from tactical.tactical_advisor import build_tactical_advice
        snap = _snap(
            cascade_active=True, cascade_direction="LONG", cascade_phase="PEAK",
            imbalance=-0.3, dominance=0.7,
        )
        signals = build_tactical_signals(snap)
        fusion = fuse_tactical_signals(signals)
        advice = build_tactical_advice(fusion, snap)
        assert advice["executionAdvice"] == "wait"
        assert advice["tradeQuality"] == "low"
        assert "forced_selling" in advice["reasonFlags"]

    def test_high_uncertainty_bearish(self):
        from tactical.tactical_signal_builder import build_tactical_signals
        from tactical.tactical_fusion_engine import fuse_tactical_signals
        from tactical.tactical_advisor import build_tactical_advice
        snap = _snap(
            imbalance=-0.3, dominance=0.7,
            funding_label="BULLISH_EXTREME",
            uncertainty=0.8,
        )
        signals = build_tactical_signals(snap)
        fusion = fuse_tactical_signals(signals)
        advice = build_tactical_advice(fusion, snap)
        assert advice["executionAdvice"] == "wait"
        assert "high_uncertainty" in advice["reasonFlags"]

    def test_has_note(self):
        from tactical.tactical_signal_builder import build_tactical_signals
        from tactical.tactical_fusion_engine import fuse_tactical_signals
        from tactical.tactical_advisor import build_tactical_advice
        snap = _snap()
        signals = build_tactical_signals(snap)
        fusion = fuse_tactical_signals(signals)
        advice = build_tactical_advice(fusion, snap)
        assert len(advice["note"]) > 5


class TestAssembler:
    def test_full_pipeline_from_snapshot(self):
        from tactical.tactical_assembler import build_tactical_from_snapshot
        snap = _snap(
            imbalance=-0.4, dominance=0.8,
            cascade_active=True, cascade_direction="LONG", cascade_phase="START",
            funding_label="BULLISH_EXTREME",
        )
        result = build_tactical_from_snapshot(snap)
        assert result["advice"]["tacticalBias"] == "bearish"
        assert result["fusion"]["score"] < 0
        assert len(result["fusion"]["active_signals"]) >= 2

    def test_various_conditions(self):
        from tactical.tactical_assembler import build_tactical_from_snapshot
        conditions = [
            _snap(),  # neutral
            _snap(imbalance=-0.4, dominance=0.8, funding_label="BULLISH_EXTREME"),  # bearish
            _snap(imbalance=0.4, dominance=0.8, cascade_active=True, cascade_direction="SHORT", cascade_phase="PEAK"),  # bullish
            _snap(absorption=True, absorption_side="ASK"),  # seller exhaustion
            _snap(oi_delta_pct=5.0),  # high vol
        ]
        for snap in conditions:
            result = build_tactical_from_snapshot(snap)
            assert result["advice"]["tacticalBias"] in ("bullish", "neutral", "bearish")
            assert result["advice"]["executionAdvice"] in ("normal", "reduced", "avoid_aggressive", "wait")
