"""
Tests for v4.1.3 Adaptive Major Profile + Direction Override Gate
==================================================================
Tests the NEW v4.1.3 features:
1. Adaptive major extractor (strict → relaxed fallback)
2. Direction override gate with controlled NEUTRAL → MILD promotion
3. Override gate blocked in pullback/mixed_range modes
4. v4.1.3 metrics: override_allowed_count, override_success_count, major_profile_distribution

Key thresholds:
- Trend threshold for override: 0.28
- MILD_BULL threshold: >= 0.20
- STRONG_BULL threshold: >= 0.65
- Override score: 0.22 (strict major) or 0.20 (relaxed major)
"""

import pytest
import requests
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://expo-telegram-web.preview.emergentagent.com")


# ═══════════════════════════════════════════════════════
# HELPER: Generate price scenarios
# ═══════════════════════════════════════════════════════

def _make_strong_uptrend_prices(n=60, start=100.0, step=3.0):
    """Generate strong uptrend - should trigger strict major profile."""
    prices = {}
    p = start
    for i in range(n):
        date = f"2026-01-{(i % 28)+1:02d}" if i < 28 else f"2026-02-{(i - 27):02d}"
        if i % 4 == 0:
            p += step * 1.8  # Strong swing high
        elif i % 4 == 2:
            p -= step * 0.5  # Shallow pullback (HH/HL pattern)
        else:
            p += step * 0.4
        prices[date] = round(p, 2)
    return prices


def _make_weak_range_prices(n=60, center=150.0, amplitude=2.0):
    """Generate weak range-bound prices - should trigger relaxed fallback."""
    import math
    prices = {}
    for i in range(n):
        date = f"2026-01-{(i % 28)+1:02d}" if i < 28 else f"2026-02-{(i - 27):02d}"
        # Small random-like oscillation
        prices[date] = round(center + amplitude * math.sin(i * 0.3), 2)
    return prices


def _make_uptrend_prices(n=60, start=100.0, step=2.0):
    """Generate uptrend price series with HH/HL pattern."""
    prices = {}
    p = start
    for i in range(n):
        date = f"2026-01-{(i % 28)+1:02d}" if i < 28 else f"2026-02-{(i - 27):02d}"
        if i % 4 == 0:
            p += step * 1.5
        elif i % 4 == 2:
            p -= step * 0.7
        else:
            p += step * 0.3
        prices[date] = round(p, 2)
    return prices


# ═══════════════════════════════════════════════════════
# ADAPTIVE MAJOR EXTRACTOR TESTS
# ═══════════════════════════════════════════════════════

class TestAdaptiveMajorExtractor:
    """Test adaptive major extractor with strict → relaxed fallback."""
    
    def test_import_module(self):
        """Verify adaptive major extractor imports correctly."""
        from forecast.structure.adaptive_major_extractor import extract_adaptive_major
        assert callable(extract_adaptive_major)
    
    def test_returns_profile_metadata(self):
        """Result should include profile_used and fallback_used metadata."""
        from forecast.structure.adaptive_major_extractor import extract_adaptive_major
        
        prices = _make_strong_uptrend_prices(60)
        result = extract_adaptive_major(prices)
        
        assert "features" in result
        assert "profile_used" in result
        assert "fallback_used" in result
        assert isinstance(result["fallback_used"], bool)
        assert result["profile_used"] in ["strict", "relaxed"]
    
    def test_empty_prices_returns_strict_no_fallback(self):
        """Empty input should return strict profile with no fallback."""
        from forecast.structure.adaptive_major_extractor import extract_adaptive_major
        
        result = extract_adaptive_major({})
        
        assert result["profile_used"] == "strict"
        assert result["fallback_used"] is False
        assert result["features"]["structure_bias_score"] == 0.0
    
    def test_none_prices_returns_strict_no_fallback(self):
        """None input should return strict profile with no fallback."""
        from forecast.structure.adaptive_major_extractor import extract_adaptive_major
        
        result = extract_adaptive_major(None)
        
        assert result["profile_used"] == "strict"
        assert result["fallback_used"] is False
    
    def test_strict_profile_thresholds(self):
        """Verify strict profile validity thresholds: bias>=0.15 OR trend>=0.30."""
        from forecast.structure.adaptive_major_extractor import _MIN_BIAS, _MIN_TREND
        
        assert _MIN_BIAS == 0.15
        assert _MIN_TREND == 0.30


class TestAdaptiveMajorProfiles:
    """Test strict and relaxed major profile configurations."""
    
    def test_strict_profile_config(self):
        """Verify strict major profile configuration."""
        from forecast.structure.structure_profiles import STRICT_MAJOR_PROFILE
        
        assert STRICT_MAJOR_PROFILE["lookback"] == 8
        assert STRICT_MAJOR_PROFILE["min_move_pct"] == 1.6
        assert STRICT_MAJOR_PROFILE["min_candles"] == 30
        assert STRICT_MAJOR_PROFILE["label"] == "strict_major"
    
    def test_relaxed_profile_config(self):
        """Verify relaxed major profile configuration."""
        from forecast.structure.structure_profiles import RELAXED_MAJOR_PROFILE
        
        assert RELAXED_MAJOR_PROFILE["lookback"] == 6
        assert RELAXED_MAJOR_PROFILE["min_move_pct"] == 1.0
        assert RELAXED_MAJOR_PROFILE["min_candles"] == 24
        assert RELAXED_MAJOR_PROFILE["label"] == "relaxed_major"
    
    def test_relaxed_less_strict_than_strict(self):
        """Relaxed profile should be less restrictive than strict."""
        from forecast.structure.structure_profiles import STRICT_MAJOR_PROFILE, RELAXED_MAJOR_PROFILE
        
        # Relaxed has smaller min_move_pct (captures smaller swings)
        assert RELAXED_MAJOR_PROFILE["min_move_pct"] < STRICT_MAJOR_PROFILE["min_move_pct"]
        # Relaxed has smaller lookback (shorter window)
        assert RELAXED_MAJOR_PROFILE["lookback"] < STRICT_MAJOR_PROFILE["lookback"]


# ═══════════════════════════════════════════════════════
# DIRECTION OVERRIDE GATE TESTS
# ═══════════════════════════════════════════════════════

class TestDirectionOverrideGate:
    """Test direction override gate with v4.1.3 threshold (trend > 0.28)."""
    
    def test_import_module(self):
        """Verify direction override gate imports correctly."""
        from forecast.structure.direction_override_gate import DirectionOverrideGate
        assert DirectionOverrideGate is not None
    
    def test_override_scores(self):
        """Verify override score constants."""
        from forecast.structure.direction_override_gate import DirectionOverrideGate
        
        gate = DirectionOverrideGate()
        assert gate.OVERRIDE_SCORE_FULL == 0.22  # For strict major
        assert gate.OVERRIDE_SCORE_FALLBACK == 0.20  # For relaxed major
    
    def test_override_allowed_conditions(self):
        """Override should fire when all conditions are met:
        - abs(base_score) < 0.15 (weak base)
        - abs(bias) > 0.35 (strong bias)
        - mode in (aligned, reversal_candidate)
        - trend > 0.28
        - reversal < 0.55
        """
        from forecast.structure.direction_override_gate import DirectionOverrideGate
        
        gate = DirectionOverrideGate()
        
        fused_structure = {
            "structure_bias_score": 0.50,   # Strong bullish bias > 0.35
            "structure_trend_score": 0.40,   # Strong trend > 0.28
            "structure_reversal_risk": 0.30,  # Low reversal < 0.55
        }
        
        result = gate.maybe_override(
            base_score=0.10,  # Weak base < 0.15
            fused_structure=fused_structure,
            mode="aligned",  # Overrideable mode
            major_fallback_used=False,
        )
        
        assert result["override_allowed"] is True
        assert result["override_type"] == "to_mild_bull"
        assert result["override_score"] == 0.22  # Full score (strict major)
        assert result["reason"] == "strong_structure_bull_weak_base"
    
    def test_override_allowed_bearish(self):
        """Override should work for bearish direction too."""
        from forecast.structure.direction_override_gate import DirectionOverrideGate
        
        gate = DirectionOverrideGate()
        
        fused_structure = {
            "structure_bias_score": -0.50,   # Strong bearish bias
            "structure_trend_score": 0.40,
            "structure_reversal_risk": 0.30,
        }
        
        result = gate.maybe_override(
            base_score=-0.10,  # Weak bearish base
            fused_structure=fused_structure,
            mode="aligned",
            major_fallback_used=False,
        )
        
        assert result["override_allowed"] is True
        assert result["override_type"] == "to_mild_bear"
        assert result["override_score"] == -0.22


class TestOverrideGateBlocked:
    """Test conditions that block the override gate."""
    
    def test_blocked_base_too_strong(self):
        """Override blocked when base_score >= 0.15 (already directional)."""
        from forecast.structure.direction_override_gate import DirectionOverrideGate
        
        gate = DirectionOverrideGate()
        
        fused_structure = {
            "structure_bias_score": 0.50,
            "structure_trend_score": 0.40,
            "structure_reversal_risk": 0.30,
        }
        
        result = gate.maybe_override(
            base_score=0.20,  # Too strong >= 0.15
            fused_structure=fused_structure,
            mode="aligned",
            major_fallback_used=False,
        )
        
        assert result["override_allowed"] is False
        assert result["reason"] == "base_too_strong"
    
    def test_blocked_bias_too_weak(self):
        """Override blocked when abs(bias) <= 0.35."""
        from forecast.structure.direction_override_gate import DirectionOverrideGate
        
        gate = DirectionOverrideGate()
        
        fused_structure = {
            "structure_bias_score": 0.30,   # Weak bias <= 0.35
            "structure_trend_score": 0.40,
            "structure_reversal_risk": 0.30,
        }
        
        result = gate.maybe_override(
            base_score=0.10,
            fused_structure=fused_structure,
            mode="aligned",
            major_fallback_used=False,
        )
        
        assert result["override_allowed"] is False
        assert result["reason"] == "bias_too_weak"
    
    def test_blocked_pullback_mode(self):
        """Override blocked in pullback mode."""
        from forecast.structure.direction_override_gate import DirectionOverrideGate
        
        gate = DirectionOverrideGate()
        
        fused_structure = {
            "structure_bias_score": 0.50,
            "structure_trend_score": 0.40,
            "structure_reversal_risk": 0.30,
        }
        
        result = gate.maybe_override(
            base_score=0.10,
            fused_structure=fused_structure,
            mode="pullback",  # Not overrideable
            major_fallback_used=False,
        )
        
        assert result["override_allowed"] is False
        assert result["reason"] == "mode_not_overrideable"
    
    def test_blocked_mixed_range_mode(self):
        """Override blocked in mixed_range mode."""
        from forecast.structure.direction_override_gate import DirectionOverrideGate
        
        gate = DirectionOverrideGate()
        
        fused_structure = {
            "structure_bias_score": 0.50,
            "structure_trend_score": 0.40,
            "structure_reversal_risk": 0.30,
        }
        
        result = gate.maybe_override(
            base_score=0.10,
            fused_structure=fused_structure,
            mode="mixed_range",  # Not overrideable
            major_fallback_used=False,
        )
        
        assert result["override_allowed"] is False
        assert result["reason"] == "mode_not_overrideable"
    
    def test_blocked_trend_too_weak(self):
        """Override blocked when trend <= 0.28 (v4.1.3 threshold)."""
        from forecast.structure.direction_override_gate import DirectionOverrideGate
        
        gate = DirectionOverrideGate()
        
        fused_structure = {
            "structure_bias_score": 0.50,
            "structure_trend_score": 0.25,   # Weak trend <= 0.28
            "structure_reversal_risk": 0.30,
        }
        
        result = gate.maybe_override(
            base_score=0.10,
            fused_structure=fused_structure,
            mode="aligned",
            major_fallback_used=False,
        )
        
        assert result["override_allowed"] is False
        assert result["reason"] == "trend_too_weak"
    
    def test_blocked_reversal_risk_too_high(self):
        """Override blocked when reversal_risk >= 0.55."""
        from forecast.structure.direction_override_gate import DirectionOverrideGate
        
        gate = DirectionOverrideGate()
        
        fused_structure = {
            "structure_bias_score": 0.50,
            "structure_trend_score": 0.40,
            "structure_reversal_risk": 0.60,   # High reversal >= 0.55
        }
        
        result = gate.maybe_override(
            base_score=0.10,
            fused_structure=fused_structure,
            mode="aligned",
            major_fallback_used=False,
        )
        
        assert result["override_allowed"] is False
        assert result["reason"] == "reversal_risk_too_high"


class TestOverrideGateFallbackMajor:
    """Test override gate with fallback (relaxed) major profile."""
    
    def test_reduced_score_for_fallback_major(self):
        """Override score should be reduced when fallback major was used."""
        from forecast.structure.direction_override_gate import DirectionOverrideGate
        
        gate = DirectionOverrideGate()
        
        fused_structure = {
            "structure_bias_score": 0.50,
            "structure_trend_score": 0.40,
            "structure_reversal_risk": 0.30,
        }
        
        # With fallback used
        result = gate.maybe_override(
            base_score=0.10,
            fused_structure=fused_structure,
            mode="aligned",
            major_fallback_used=True,  # Fallback was used
        )
        
        assert result["override_allowed"] is True
        assert result["override_score"] == 0.20  # Reduced score (vs 0.22)
    
    def test_full_score_for_strict_major(self):
        """Override score should be full (0.22) when strict major was used."""
        from forecast.structure.direction_override_gate import DirectionOverrideGate
        
        gate = DirectionOverrideGate()
        
        fused_structure = {
            "structure_bias_score": 0.50,
            "structure_trend_score": 0.40,
            "structure_reversal_risk": 0.30,
        }
        
        # Without fallback (strict major)
        result = gate.maybe_override(
            base_score=0.10,
            fused_structure=fused_structure,
            mode="aligned",
            major_fallback_used=False,  # Strict major used
        )
        
        assert result["override_allowed"] is True
        assert result["override_score"] == 0.22  # Full score


class TestOverrideGateReversalCandidate:
    """Test override gate in reversal_candidate mode."""
    
    def test_override_allowed_in_reversal_candidate(self):
        """Override should be allowed in reversal_candidate mode."""
        from forecast.structure.direction_override_gate import DirectionOverrideGate
        
        gate = DirectionOverrideGate()
        
        fused_structure = {
            "structure_bias_score": 0.50,
            "structure_trend_score": 0.40,
            "structure_reversal_risk": 0.30,
        }
        
        result = gate.maybe_override(
            base_score=0.10,
            fused_structure=fused_structure,
            mode="reversal_candidate",  # Should be overrideable
            major_fallback_used=False,
        )
        
        assert result["override_allowed"] is True


# ═══════════════════════════════════════════════════════
# MULTI-SCALE EXTRACTOR v4.1.3 METADATA TESTS
# ═══════════════════════════════════════════════════════

class TestMultiscaleExtractorV413:
    """Test multi-scale extractor returns v4.1.3 metadata."""
    
    def test_returns_major_profile_metadata(self):
        """extract_multiscale should return major_profile_used and major_fallback_used."""
        from forecast.structure.multi_scale_extractor import extract_multiscale
        
        prices = _make_uptrend_prices(60)
        result = extract_multiscale(prices)
        
        assert "major_profile_used" in result
        assert "major_fallback_used" in result
        assert result["major_profile_used"] in ["strict", "relaxed"]
        assert isinstance(result["major_fallback_used"], bool)


# ═══════════════════════════════════════════════════════
# LIVE GENERATOR v4.1.3 TESTS
# ═══════════════════════════════════════════════════════

class TestLiveGeneratorV413:
    """Test live forecast generator with v4.1.3 pipeline."""
    
    def test_generator_version(self):
        """Generator should use v4.1.3 by default."""
        from forecast.generator_v41 import generate_forecast
        from forecast import Horizon
        
        # Generate a forecast
        result = generate_forecast("BTC", Horizon.D7, model_version="v4.1.3")
        
        if result is not None:
            assert result.modelVersion == "v4.1.3"
    
    def test_forecast_audit_has_override_gate(self):
        """Forecast audit should include override_gate in structureInfluence."""
        # Test via backfill cases which have full audit data
        response = requests.get(f"{BASE_URL}/api/forecast/backfill/latest?asset=BTC&horizon=7D")
        if response.status_code != 200:
            pytest.skip("Backfill endpoint not available")
        
        data = response.json()
        if not data.get("ok"):
            pytest.skip("No backfill data available")
        
        run_id = data["run"]["runId"]
        cases_response = requests.get(f"{BASE_URL}/api/forecast/backfill/cases/{run_id}?limit=10")
        
        if cases_response.status_code == 200:
            cases_data = cases_response.json()
            if cases_data.get("cases"):
                # Check that multiscale_meta exists and has override info
                for case in cases_data["cases"]:
                    if "multiscale_meta" in case:
                        meta = case["multiscale_meta"]
                        # v4.1.3 should have override info
                        assert "override" in meta, "v4.1.3 should have override in multiscale_meta"
                        override = meta["override"]
                        assert "override_allowed" in override
                        assert "reason" in override
                        break


# ═══════════════════════════════════════════════════════
# BACKFILL v4.1.3 METRICS TESTS
# ═══════════════════════════════════════════════════════

class TestBackfillV413Metrics:
    """Test backfill returns v4.1.3 specific metrics."""
    
    def test_backfill_has_v413_metrics(self):
        """Backfill KPIs should include v4.1.3 specific metrics."""
        response = requests.get(f"{BASE_URL}/api/forecast/backfill/latest?asset=BTC&horizon=7D")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        
        kpis = data["kpis"]
        
        # v4.1.3 specific metrics
        assert "v413_metrics" in kpis, "Should have v4.1.3 specific metrics"
        v413 = kpis["v413_metrics"]
        
        assert "override_allowed_count" in v413
        assert "override_success_count" in v413
        assert "major_profile_distribution" in v413
        assert "major_fallback_count" in v413
    
    def test_override_success_rate_valid(self):
        """Override success rate should be valid (0-1 or None if no overrides)."""
        response = requests.get(f"{BASE_URL}/api/forecast/backfill/latest?asset=BTC&horizon=7D")
        data = response.json()
        
        v413 = data["kpis"]["v413_metrics"]
        
        if v413["override_allowed_count"] > 0:
            rate = v413["override_success_rate"]
            assert rate is not None
            assert 0 <= rate <= 1
        else:
            # No overrides → rate may be None
            assert v413["override_success_rate"] is None
    
    def test_major_profile_distribution(self):
        """Major profile distribution should have counts for strict/relaxed."""
        response = requests.get(f"{BASE_URL}/api/forecast/backfill/latest?asset=BTC&horizon=7D")
        data = response.json()
        
        v413 = data["kpis"]["v413_metrics"]
        dist = v413["major_profile_distribution"]
        
        # Should have at least one profile type
        assert isinstance(dist, dict)
        # Total should match number of cases
        total_cases = data["kpis"]["n"]
        total_profiles = sum(dist.values())
        assert total_profiles == total_cases
    
    def test_override_reasons_tracked(self):
        """Override reasons should be tracked in v413_metrics."""
        response = requests.get(f"{BASE_URL}/api/forecast/backfill/latest?asset=BTC&horizon=7D")
        data = response.json()
        
        v413 = data["kpis"]["v413_metrics"]
        
        assert "override_reasons" in v413
        reasons = v413["override_reasons"]
        assert isinstance(reasons, dict)
        
        # Reasons should be valid override gate reasons
        valid_reasons = {
            "base_too_strong", "bias_too_weak", "mode_not_overrideable",
            "trend_too_weak", "reversal_risk_too_high",
            "strong_structure_bull_weak_base", "strong_structure_bear_weak_base"
        }
        for reason in reasons.keys():
            assert reason in valid_reasons, f"Unknown override reason: {reason}"


class TestBackfillV413Cases:
    """Test individual backfill cases have v4.1.3 metadata."""
    
    def test_cases_have_override_info(self):
        """Individual cases should include override info in multiscale_meta."""
        response = requests.get(f"{BASE_URL}/api/forecast/backfill/latest?asset=BTC&horizon=7D")
        if response.status_code != 200:
            pytest.skip("Backfill endpoint not available")
        
        data = response.json()
        if not data.get("ok"):
            pytest.skip("No backfill data available")
        
        run_id = data["run"]["runId"]
        cases_response = requests.get(f"{BASE_URL}/api/forecast/backfill/cases/{run_id}?limit=5")
        assert cases_response.status_code == 200
        
        data = cases_response.json()
        for case in data["cases"]:
            if "multiscale_meta" in case:
                meta = case["multiscale_meta"]
                assert "override" in meta
                override = meta["override"]
                assert "override_allowed" in override
                assert "reason" in override
    
    def test_cases_have_major_profile_info(self):
        """Individual cases should include major profile metadata."""
        response = requests.get(f"{BASE_URL}/api/forecast/backfill/latest?asset=BTC&horizon=7D")
        data = response.json()
        
        run_id = data["run"]["runId"]
        cases_response = requests.get(f"{BASE_URL}/api/forecast/backfill/cases/{run_id}?limit=5")
        
        data = cases_response.json()
        for case in data["cases"]:
            if "multiscale_meta" in case:
                meta = case["multiscale_meta"]
                assert "major_profile_used" in meta
                assert "major_fallback_used" in meta
                assert meta["major_profile_used"] in ["strict", "relaxed", "unknown"]


# ═══════════════════════════════════════════════════════
# REPLAY RUNNER v4.1.3 TESTS
# ═══════════════════════════════════════════════════════

class TestReplayRunnerV413:
    """Test replay runner with v4.1.3 pipeline."""
    
    def test_replay_has_override_result(self):
        """Replay result should include override gate result."""
        from forecast.backfill.replay_runner import run_dual_replay
        
        prices = _make_uptrend_prices(60)
        snapshot = {
            "asset": "BTC",
            "horizon": "7D",
            "as_of": "2026-02-15",
            "features": {
                "price": 150.0,
                "ret_1d": 0.02,
                "ret_7d": 0.10,
                "ret_14d": 0.15,
                "volatility": 0.03,
                "momentum": 0.05,
            },
            "baseline": {
                "meanReturn": 0.02,
                "stdReturn": 0.05,
                "dirHitMean": 0.55,
                "medianReturn": 0.01,
            },
            "regime": "TREND",
            "regime_confidence": 0.8,
            "recent_perf": {"rollingWinRate": 0.5, "recentCount": 0},
            "prices": prices,
        }
        
        result = run_dual_replay(snapshot)
        
        # v4.1.3 should have override info in multiscale_meta
        assert "multiscale_meta" in result
        meta = result["multiscale_meta"]
        assert "override" in meta
        
        override = meta["override"]
        assert "override_allowed" in override
        assert "reason" in override
    
    def test_replay_has_major_profile_info(self):
        """Replay result should include major profile metadata."""
        from forecast.backfill.replay_runner import run_dual_replay
        
        prices = _make_uptrend_prices(60)
        snapshot = {
            "asset": "BTC",
            "horizon": "7D",
            "as_of": "2026-02-15",
            "features": {
                "price": 150.0,
                "ret_1d": 0.02,
                "ret_7d": 0.10,
                "ret_14d": 0.15,
                "volatility": 0.03,
                "momentum": 0.05,
            },
            "baseline": {
                "meanReturn": 0.02,
                "stdReturn": 0.05,
                "dirHitMean": 0.55,
                "medianReturn": 0.01,
            },
            "regime": "TREND",
            "regime_confidence": 0.8,
            "recent_perf": {"rollingWinRate": 0.5, "recentCount": 0},
            "prices": prices,
        }
        
        result = run_dual_replay(snapshot)
        
        meta = result["multiscale_meta"]
        assert "major_profile_used" in meta
        assert "major_fallback_used" in meta


# ═══════════════════════════════════════════════════════
# KPI AGGREGATOR v4.1.3 METRICS TESTS
# ═══════════════════════════════════════════════════════

class TestKPIAggregatorV413:
    """Test KPI aggregator computes v4.1.3 metrics correctly."""
    
    def test_aggregate_includes_v413_metrics(self):
        """Aggregate should include v4.1.3 specific metrics."""
        from forecast.backfill.shadow_kpi_aggregator import aggregate_kpis
        
        # Minimal test case with v4.1.3 override data
        cases = [{
            "replay": {
                "base": {"direction": "NEUTRAL", "score": 0.10},
                "structure": {"direction": "MILD_BULL", "score": 0.22},
                "v411": {"direction": "NEUTRAL", "score": 0.12},
                "structure_delta": {"capped_delta": 0.12},
                "structure_delta_v411": {"capped_delta": 0.02, "raw_delta": 0.02, "sign_flip_allowed": False},
            },
            "comparison": {
                "case_type": "structure_improved",
                "base_correct": False,
                "structure_correct": True,
                "direction_changed": True,
                "sign_changed": False,
                "strength_only_change": False,
            },
            "comparison_v411": {
                "case_type": "both_wrong",
                "base_correct": False,
                "structure_correct": False,
                "direction_changed": False,
                "sign_changed": False,
                "strength_only_change": False,
            },
            "multiscale_meta": {
                "mode": "aligned",
                "multiscale_guards": [],
                "major_profile_used": "strict",
                "major_fallback_used": False,
                "override": {
                    "override_allowed": True,
                    "reason": "strong_structure_bull_weak_base",
                },
            },
            "pattern_tags": [],
        }]
        
        result = aggregate_kpis(cases)
        
        assert "v413_metrics" in result
        v413 = result["v413_metrics"]
        
        assert v413["override_allowed_count"] == 1
        assert v413["override_success_count"] == 1  # structure_correct=True
        assert v413["major_fallback_count"] == 0
        assert v413["major_profile_distribution"]["strict"] == 1
        assert v413["override_success_rate"] == 1.0
    
    def test_override_reasons_aggregated(self):
        """Override reasons should be aggregated correctly."""
        from forecast.backfill.shadow_kpi_aggregator import aggregate_kpis
        
        cases = [
            {
                "replay": {"base": {"direction": "NEUTRAL", "score": 0.10},
                           "structure": {"direction": "NEUTRAL", "score": 0.10},
                           "structure_delta": {"capped_delta": 0.0}},
                "comparison": {"case_type": "both_wrong", "base_correct": False, "structure_correct": False,
                               "direction_changed": False, "sign_changed": False, "strength_only_change": False},
                "multiscale_meta": {
                    "mode": "pullback",
                    "major_profile_used": "strict",
                    "major_fallback_used": False,
                    "override": {"override_allowed": False, "reason": "mode_not_overrideable"},
                },
                "pattern_tags": [],
            },
            {
                "replay": {"base": {"direction": "MILD_BULL", "score": 0.25},
                           "structure": {"direction": "MILD_BULL", "score": 0.30},
                           "structure_delta": {"capped_delta": 0.05}},
                "comparison": {"case_type": "both_correct", "base_correct": True, "structure_correct": True,
                               "direction_changed": False, "sign_changed": False, "strength_only_change": False},
                "multiscale_meta": {
                    "mode": "aligned",
                    "major_profile_used": "relaxed",
                    "major_fallback_used": True,
                    "override": {"override_allowed": False, "reason": "base_too_strong"},
                },
                "pattern_tags": [],
            },
        ]
        
        result = aggregate_kpis(cases)
        v413 = result["v413_metrics"]
        
        assert v413["override_allowed_count"] == 0
        assert v413["major_fallback_count"] == 1
        assert v413["major_profile_distribution"]["strict"] == 1
        assert v413["major_profile_distribution"]["relaxed"] == 1
        assert v413["override_reasons"]["mode_not_overrideable"] == 1
        assert v413["override_reasons"]["base_too_strong"] == 1


# ═══════════════════════════════════════════════════════
# VERDICT ENGINE PROMOTE THRESHOLD TESTS
# ═══════════════════════════════════════════════════════

class TestVerdictEngineV413:
    """Test verdict engine PROMOTE threshold (accuracy_lift >= 3pp)."""
    
    def test_promote_threshold(self):
        """PROMOTE verdict requires accuracy_lift_pp >= 3."""
        from forecast.backfill.shadow_verdict_engine import build_verdict
        
        # KPIs meeting PROMOTE criteria
        kpis = {
            "n": 50,
            "base": {
                "accuracy": 0.38,
                "distribution": {"neutral_ratio": 0.40, "mild_ratio": 0.40, "strong_ratio": 0.20},
            },
            "structure": {
                "accuracy": 0.465,  # +8.5pp lift
                "distribution": {"neutral_ratio": 0.35, "mild_ratio": 0.45, "strong_ratio": 0.20},
            },
            "comparison": {
                "accuracy_lift_pp": 8.5,  # >= 3
                "hurt_rate": 0.10,         # < 0.35
                "case_types": {"both_correct": 20, "structure_improved": 8, "both_wrong": 20, "structure_hurt": 2},
                "sign_changed": 0,
            },
        }
        
        verdict = build_verdict(kpis)
        assert verdict["verdict"] == "PROMOTE"
        assert "accuracy_lift" in verdict["reasons"][0]
    
    def test_hold_verdict_below_threshold(self):
        """HOLD verdict when accuracy_lift_pp in [-1, +3]."""
        from forecast.backfill.shadow_verdict_engine import build_verdict
        
        kpis = {
            "n": 50,
            "base": {
                "accuracy": 0.38,
                "distribution": {"neutral_ratio": 0.40, "mild_ratio": 0.40, "strong_ratio": 0.20},
            },
            "structure": {
                "accuracy": 0.40,  # +2pp lift
                "distribution": {"neutral_ratio": 0.38, "mild_ratio": 0.42, "strong_ratio": 0.20},
            },
            "comparison": {
                "accuracy_lift_pp": 2.0,  # In HOLD range
                "hurt_rate": 0.10,
                "case_types": {"both_correct": 20, "structure_improved": 2, "both_wrong": 26, "structure_hurt": 2},
                "sign_changed": 1,
                "strength_only_changed": 3,
            },
        }
        
        verdict = build_verdict(kpis)
        assert verdict["verdict"] == "HOLD"


# ═══════════════════════════════════════════════════════
# V41_CONFIG CLASSIFICATION TESTS
# ═══════════════════════════════════════════════════════

class TestV41ConfigClassificationV413:
    """Test direction classification thresholds for v4.1.3."""
    
    def test_mild_bull_threshold(self):
        """MILD_BULL threshold is >= 0.20."""
        from forecast.v41_config import classify_direction, DIRECTION_THRESHOLDS
        
        assert DIRECTION_THRESHOLDS["mild_bull"] == 0.20
        assert classify_direction(0.20) == "MILD_BULL"
        assert classify_direction(0.22) == "MILD_BULL"  # Override score
    
    def test_override_score_maps_to_mild(self):
        """Override scores (0.20, 0.22) should map to MILD_BULL/MILD_BEAR."""
        from forecast.v41_config import classify_direction
        
        assert classify_direction(0.22) == "MILD_BULL"   # Full override
        assert classify_direction(0.20) == "MILD_BULL"   # Fallback override
        assert classify_direction(-0.22) == "MILD_BEAR"  # Bearish override
        assert classify_direction(-0.20) == "MILD_BEAR"  # Bearish fallback
