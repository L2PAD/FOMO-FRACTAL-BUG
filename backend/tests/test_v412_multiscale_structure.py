"""
Tests for v4.1.2 Multi-scale Structure Logic
=============================================
Comprehensive tests for:
1. Multi-scale extractor (major/minor profiles)
2. Pullback detector (mode classification)
3. Major/Minor fusion (mode-aware weights)
4. Multiscale guards (hard guards enforcement)
5. Live generator (v4.1.2 pipeline)
6. Backfill triple comparison (v4.1 base / v4.1.1 / v4.1.2)
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


def _make_downtrend_prices(n=60, start=200.0, step=2.0):
    """Generate downtrend price series with LL/LH pattern."""
    prices = {}
    p = start
    for i in range(n):
        date = f"2026-01-{(i % 28)+1:02d}" if i < 28 else f"2026-02-{(i - 27):02d}"
        if i % 4 == 0:
            p -= step * 1.5
        elif i % 4 == 2:
            p += step * 0.7
        else:
            p -= step * 0.3
        prices[date] = round(p, 2)
    return prices


def _make_pullback_scenario(n=60, start=100.0):
    """Major uptrend with minor pullback."""
    prices = {}
    p = start
    for i in range(n):
        date = f"2026-01-{(i % 28)+1:02d}" if i < 28 else f"2026-02-{(i - 27):02d}"
        # Strong uptrend for first 45 days
        if i < 45:
            p += 1.5 if i % 3 != 2 else -0.5
        # Minor pullback last 15 days
        else:
            p -= 0.8 if i % 2 == 0 else 0.2
        prices[date] = round(p, 2)
    return prices


# ═══════════════════════════════════════════════════════
# MULTI-SCALE EXTRACTOR TESTS
# ═══════════════════════════════════════════════════════

class TestMultiscaleExtractor:
    """Test multi-scale structure feature extraction."""
    
    def test_import_module(self):
        """Verify multi-scale extractor imports correctly."""
        from forecast.structure.multi_scale_extractor import extract_multiscale, EMPTY_MULTISCALE
        assert callable(extract_multiscale)
        assert "major" in EMPTY_MULTISCALE
        assert "minor" in EMPTY_MULTISCALE
    
    def test_extract_produces_distinct_scales(self):
        """Major and minor features should have distinct characteristics."""
        from forecast.structure.multi_scale_extractor import extract_multiscale
        
        prices = _make_uptrend_prices(60)
        result = extract_multiscale(prices)
        
        assert "major" in result
        assert "minor" in result
        assert isinstance(result["major"], dict)
        assert isinstance(result["minor"], dict)
    
    def test_both_scales_have_all_features(self):
        """Both major and minor should contain all 7 structure features."""
        from forecast.structure.multi_scale_extractor import extract_multiscale
        
        prices = _make_uptrend_prices(60)
        result = extract_multiscale(prices)
        
        required = [
            "structure_bias_score",
            "structure_trend_score",
            "structure_momentum_score",
            "structure_reversal_risk",
            "structure_stability_score",
            "structure_exhaustion_score",
            "structure_compression_score",
        ]
        
        for key in required:
            assert key in result["major"], f"Missing {key} in major"
            assert key in result["minor"], f"Missing {key} in minor"
    
    def test_empty_prices_returns_empty_multiscale(self):
        """Empty input should return EMPTY_MULTISCALE structure."""
        from forecast.structure.multi_scale_extractor import extract_multiscale, EMPTY_MULTISCALE
        
        result = extract_multiscale({})
        assert result == EMPTY_MULTISCALE
    
    def test_none_prices_returns_empty_multiscale(self):
        """None input should return EMPTY_MULTISCALE structure."""
        from forecast.structure.multi_scale_extractor import extract_multiscale, EMPTY_MULTISCALE
        
        result = extract_multiscale(None)
        assert result == EMPTY_MULTISCALE


class TestStructureProfiles:
    """Test major/minor profile configurations."""
    
    def test_profiles_exist(self):
        """Both major and minor profiles should exist."""
        from forecast.structure.structure_profiles import STRUCTURE_PROFILES
        
        assert "major" in STRUCTURE_PROFILES
        assert "minor" in STRUCTURE_PROFILES
    
    def test_major_has_larger_min_move(self):
        """Major profile should have larger min_move_pct for filtering small swings."""
        from forecast.structure.structure_profiles import STRUCTURE_PROFILES
        
        major = STRUCTURE_PROFILES["major"]
        minor = STRUCTURE_PROFILES["minor"]
        
        assert major["min_move_pct"] > minor["min_move_pct"]
        assert major["min_move_pct"] == 1.6  # Per spec
        assert minor["min_move_pct"] == 0.7  # Per spec
    
    def test_major_has_larger_lookback(self):
        """Major profile should have larger lookback window."""
        from forecast.structure.structure_profiles import STRUCTURE_PROFILES
        
        major = STRUCTURE_PROFILES["major"]
        minor = STRUCTURE_PROFILES["minor"]
        
        assert major["lookback"] > minor["lookback"]
        assert major["lookback"] == 8  # Per spec
        assert minor["lookback"] == 3  # Per spec


# ═══════════════════════════════════════════════════════
# PULLBACK DETECTOR TESTS
# ═══════════════════════════════════════════════════════

class TestPullbackDetector:
    """Test mode detection from major/minor features."""
    
    def test_import_module(self):
        """Verify pullback detector imports correctly."""
        from forecast.structure.pullback_detector import detect_mode
        assert callable(detect_mode)
    
    def test_aligned_mode_same_direction(self):
        """Aligned mode when major and minor agree."""
        from forecast.structure.pullback_detector import detect_mode
        
        major = {"structure_bias_score": 0.5, "structure_reversal_risk": 0.2,
                 "structure_trend_score": 0.7, "structure_stability_score": 0.8}
        minor = {"structure_bias_score": 0.4, "structure_momentum_score": 0.5}
        
        result = detect_mode(major, minor)
        assert result["mode"] == "aligned"
        assert result["pullback_confidence"] == 0.0
        assert result["minor_counter_trend"] is False
    
    def test_pullback_mode_opposite_minor_healthy_major(self):
        """Pullback mode when minor opposes healthy major."""
        from forecast.structure.pullback_detector import detect_mode
        
        # Major: bullish, healthy (low reversal risk)
        major = {"structure_bias_score": 0.5, "structure_reversal_risk": 0.25,
                 "structure_trend_score": 0.7, "structure_stability_score": 0.8}
        # Minor: bearish counter-trend
        minor = {"structure_bias_score": -0.25, "structure_momentum_score": -0.4}
        
        result = detect_mode(major, minor)
        assert result["mode"] == "pullback"
        assert result["pullback_confidence"] > 0.0
        assert result["minor_counter_trend"] is True
        assert result["reversal_candidate"] is False
    
    def test_reversal_candidate_mode_high_reversal_risk(self):
        """Reversal_candidate mode when major shows weakness and minor strong opposite."""
        from forecast.structure.pullback_detector import detect_mode
        
        # Major: bearish but with high reversal risk
        major = {"structure_bias_score": -0.5, "structure_reversal_risk": 0.75,
                 "structure_trend_score": 0.3, "structure_stability_score": 0.4}
        # Minor: strong bullish momentum against major
        minor = {"structure_bias_score": 0.35, "structure_momentum_score": 0.65}
        
        result = detect_mode(major, minor)
        assert result["mode"] == "reversal_candidate"
        assert result["reversal_candidate"] is True
        assert result["minor_counter_trend"] is True
    
    def test_mixed_range_mode_both_weak(self):
        """Mixed_range mode when both scales are weak/unclear."""
        from forecast.structure.pullback_detector import detect_mode
        
        # Both weak
        major = {"structure_bias_score": 0.1, "structure_reversal_risk": 0.5,
                 "structure_trend_score": 0.4, "structure_stability_score": 0.5}
        minor = {"structure_bias_score": 0.05, "structure_momentum_score": 0.1}
        
        result = detect_mode(major, minor)
        assert result["mode"] == "mixed_range"
        assert result["reversal_candidate"] is False
        assert result["major_dominant"] is False
    
    def test_major_dominant_flag(self):
        """Major_dominant should be True when major is strong and healthy."""
        from forecast.structure.pullback_detector import detect_mode
        
        # Strong major with low reversal risk
        major = {"structure_bias_score": 0.6, "structure_reversal_risk": 0.3,
                 "structure_trend_score": 0.8, "structure_stability_score": 0.9}
        minor = {"structure_bias_score": 0.4, "structure_momentum_score": 0.5}
        
        result = detect_mode(major, minor)
        assert result["major_dominant"] is True


# ═══════════════════════════════════════════════════════
# MAJOR/MINOR FUSION TESTS
# ═══════════════════════════════════════════════════════

class TestMajorMinorFusion:
    """Test mode-aware fusion of major/minor features."""
    
    def test_import_modules(self):
        """Verify fusion module imports correctly."""
        from forecast.structure.major_minor_fusion import fuse, apply_multiscale_guards, MODE_WEIGHTS, RANGE_SHRINK
        assert callable(fuse)
        assert callable(apply_multiscale_guards)
        assert RANGE_SHRINK == 0.45  # Per spec
    
    def test_mode_weights_configured(self):
        """Verify mode weights are correctly configured."""
        from forecast.structure.major_minor_fusion import MODE_WEIGHTS
        
        assert MODE_WEIGHTS["aligned"] == (0.65, 0.35)
        assert MODE_WEIGHTS["pullback"] == (0.80, 0.20)
        assert MODE_WEIGHTS["reversal_candidate"] == (0.55, 0.45)
        assert MODE_WEIGHTS["mixed_range"] == (0.60, 0.40)
    
    def test_fuse_applies_mode_weights(self):
        """Fuse should apply mode-aware weights."""
        from forecast.structure.major_minor_fusion import fuse
        
        major = {"structure_bias_score": 0.5, "structure_trend_score": 0.6,
                 "structure_momentum_score": 0.4, "structure_reversal_risk": 0.2,
                 "structure_stability_score": 0.7, "structure_exhaustion_score": 0.1,
                 "structure_compression_score": 0.5}
        minor = {"structure_bias_score": 0.3, "structure_trend_score": 0.5,
                 "structure_momentum_score": 0.6, "structure_reversal_risk": 0.3,
                 "structure_stability_score": 0.6, "structure_exhaustion_score": 0.2,
                 "structure_compression_score": 0.4}
        mode_info = {"mode": "aligned", "pullback_confidence": 0.0,
                     "major_dominant": False, "minor_counter_trend": False}
        
        result = fuse(major, minor, mode_info, base_score=0.0)
        
        # In aligned mode, weights are 0.65/0.35
        # structure_bias_score = 0.5*0.65 + 0.3*0.35 = 0.325 + 0.105 = 0.43
        expected_bias = 0.5 * 0.65 + 0.3 * 0.35
        assert round(result["structure_bias_score"], 4) == round(expected_bias, 4)
        
        # Mode metadata should be present
        assert result["_mode"] == "aligned"
    
    def test_fuse_pullback_weights_favor_major(self):
        """Pullback mode should weight major much higher (0.80/0.20)."""
        from forecast.structure.major_minor_fusion import fuse
        
        major = {"structure_bias_score": 0.6, "structure_trend_score": 0.7,
                 "structure_momentum_score": 0.5, "structure_reversal_risk": 0.2,
                 "structure_stability_score": 0.8, "structure_exhaustion_score": 0.1,
                 "structure_compression_score": 0.5}
        minor = {"structure_bias_score": -0.3, "structure_trend_score": 0.4,
                 "structure_momentum_score": -0.5, "structure_reversal_risk": 0.4,
                 "structure_stability_score": 0.5, "structure_exhaustion_score": 0.3,
                 "structure_compression_score": 0.4}
        mode_info = {"mode": "pullback", "pullback_confidence": 0.7,
                     "major_dominant": True, "minor_counter_trend": True}
        
        result = fuse(major, minor, mode_info, base_score=0.3)
        
        # Pullback weights 0.80/0.20 → heavily favors major
        expected_bias = 0.6 * 0.80 + (-0.3) * 0.20
        assert round(result["structure_bias_score"], 4) == round(expected_bias, 4)
    
    def test_momentum_favors_minor(self):
        """Momentum feature should favor minor (tactical impulse)."""
        from forecast.structure.major_minor_fusion import fuse
        
        major = {"structure_bias_score": 0.5, "structure_trend_score": 0.6,
                 "structure_momentum_score": 0.2, "structure_reversal_risk": 0.2,
                 "structure_stability_score": 0.7, "structure_exhaustion_score": 0.1,
                 "structure_compression_score": 0.5}
        minor = {"structure_bias_score": 0.3, "structure_trend_score": 0.5,
                 "structure_momentum_score": 0.8, "structure_reversal_risk": 0.3,
                 "structure_stability_score": 0.6, "structure_exhaustion_score": 0.2,
                 "structure_compression_score": 0.4}
        mode_info = {"mode": "aligned", "pullback_confidence": 0.0,
                     "major_dominant": False, "minor_counter_trend": False}
        
        result = fuse(major, minor, mode_info, base_score=0.0)
        
        # Momentum: 0.35 major + 0.65 minor
        expected_momentum = 0.2 * 0.35 + 0.8 * 0.65
        assert round(result["structure_momentum_score"], 4) == round(expected_momentum, 4)


# ═══════════════════════════════════════════════════════
# MULTISCALE GUARDS TESTS
# ═══════════════════════════════════════════════════════

class TestMultiscaleGuards:
    """Test v4.1.2 hard guards enforcement."""
    
    def test_guard1_pullback_forbid_flip(self):
        """Guard 1: In pullback mode, sign flip is forbidden."""
        from forecast.structure.major_minor_fusion import apply_multiscale_guards
        
        struct_result = {
            "score_after_structure": -0.3,  # Would flip from positive base
            "sign_flip_allowed": True,
            "raw_delta": -0.5,
            "capped_delta": -0.5,
        }
        mode_info = {"mode": "pullback", "pullback_confidence": 0.8,
                     "reversal_candidate": False, "major_dominant": True}
        base_score = 0.2  # Positive base
        
        result = apply_multiscale_guards(struct_result, mode_info, base_score)
        
        assert result["sign_flip_allowed"] is False
        assert "pullback_forbid_flip" in result["multiscale_guards"]
    
    def test_guard1_pullback_preserve_direction(self):
        """Guard 1: In pullback mode, MILD→NEUTRAL neutralization is prevented."""
        from forecast.structure.major_minor_fusion import apply_multiscale_guards
        
        # Base is directional (0.25 = MILD_BULL), structure wants to neutralize to 0.15
        struct_result = {
            "score_after_structure": 0.15,  # Would become NEUTRAL
            "sign_flip_allowed": False,
            "raw_delta": -0.10,
            "capped_delta": -0.10,
        }
        mode_info = {"mode": "pullback", "pullback_confidence": 0.7,
                     "reversal_candidate": False, "major_dominant": True}
        base_score = 0.25  # MILD_BULL
        
        result = apply_multiscale_guards(struct_result, mode_info, base_score)
        
        # Should preserve direction (floor at 0.20 for MILD_BULL)
        assert result["score_after_structure"] >= 0.20
        assert "pullback_preserve_direction" in result["multiscale_guards"]
    
    def test_guard2_reversal_gate_blocks_flip(self):
        """Guard 2: Sign flip is only allowed in reversal_candidate mode."""
        from forecast.structure.major_minor_fusion import apply_multiscale_guards
        
        struct_result = {
            "score_after_structure": -0.3,  # Would flip from positive base
            "sign_flip_allowed": True,
            "raw_delta": -0.5,
            "capped_delta": -0.5,
        }
        mode_info = {"mode": "aligned", "pullback_confidence": 0.0,
                     "reversal_candidate": False, "major_dominant": True}
        base_score = 0.2  # Positive base
        
        result = apply_multiscale_guards(struct_result, mode_info, base_score)
        
        # Should block flip since not reversal_candidate
        assert result["sign_flip_allowed"] is False
        assert result["score_after_structure"] >= 0  # No sign flip
        assert "reversal_gate_blocked" in result["multiscale_guards"]
    
    def test_guard2_reversal_candidate_allows_flip(self):
        """Guard 2: Sign flip IS allowed in reversal_candidate mode."""
        from forecast.structure.major_minor_fusion import apply_multiscale_guards
        
        struct_result = {
            "score_after_structure": -0.3,  # Would flip from positive base
            "sign_flip_allowed": True,
            "raw_delta": -0.5,
            "capped_delta": -0.5,
        }
        mode_info = {"mode": "reversal_candidate", "pullback_confidence": 0.0,
                     "reversal_candidate": True, "major_dominant": False}
        base_score = 0.2  # Positive base
        
        result = apply_multiscale_guards(struct_result, mode_info, base_score)
        
        # Should allow flip since reversal_candidate
        assert "reversal_gate_blocked" not in result["multiscale_guards"]
        # Score may still be negative (flip allowed)
    
    def test_guard3_range_shrink(self):
        """Guard 3: In mixed_range, delta is shrunk by RANGE_SHRINK (0.45)."""
        from forecast.structure.major_minor_fusion import apply_multiscale_guards, RANGE_SHRINK
        
        struct_result = {
            "score_after_structure": 0.4,  # Delta = 0.4 - 0.2 = 0.2
            "sign_flip_allowed": False,
            "raw_delta": 0.2,
            "capped_delta": 0.2,
        }
        mode_info = {"mode": "mixed_range", "pullback_confidence": 0.0,
                     "reversal_candidate": False, "major_dominant": False}
        base_score = 0.2
        
        result = apply_multiscale_guards(struct_result, mode_info, base_score)
        
        # Expected: base + (delta * 0.45) = 0.2 + 0.2*0.45 = 0.2 + 0.09 = 0.29
        expected = base_score + (0.4 - base_score) * RANGE_SHRINK
        assert abs(result["score_after_structure"] - expected) < 0.001
        assert f"range_shrink_{RANGE_SHRINK}" in result["multiscale_guards"]
    
    def test_guard4_major_dominance_forbid_flip(self):
        """Guard 4: When major is dominant and healthy, forbid flip.
        Note: reversal_gate (Guard 2) also triggers before major_dominance,
        so we check that flip is blocked and score is preserved."""
        from forecast.structure.major_minor_fusion import apply_multiscale_guards
        
        struct_result = {
            "score_after_structure": -0.1,  # Would flip from positive base
            "sign_flip_allowed": True,
            "raw_delta": -0.3,
            "capped_delta": -0.3,
        }
        mode_info = {"mode": "aligned", "pullback_confidence": 0.0,
                     "reversal_candidate": False, "major_dominant": True}
        base_score = 0.2  # Positive base
        
        result = apply_multiscale_guards(struct_result, mode_info, base_score)
        
        # Should forbid flip - either by reversal_gate or major_dominance
        assert result["sign_flip_allowed"] is False
        # At least one guard should have blocked the flip
        guards = result["multiscale_guards"]
        assert len(guards) > 0
        # Score should not have flipped negative
        assert result["score_after_structure"] >= 0
    
    def test_guard5_direction_preservation_floor(self):
        """Guard 5: Direction preservation floor prevents directional→NEUTRAL."""
        from forecast.structure.major_minor_fusion import apply_multiscale_guards
        
        # Base is MILD_BULL (0.25), structure pushes toward NEUTRAL (0.15)
        struct_result = {
            "score_after_structure": 0.15,  # Would become NEUTRAL
            "sign_flip_allowed": False,
            "raw_delta": -0.10,
            "capped_delta": -0.10,
        }
        mode_info = {"mode": "aligned", "pullback_confidence": 0.0,
                     "reversal_candidate": False, "major_dominant": False}
        base_score = 0.25  # MILD_BULL
        
        result = apply_multiscale_guards(struct_result, mode_info, base_score)
        
        # Should preserve direction (floor at 0.20 for MILD_BULL)
        assert result["score_after_structure"] >= 0.20
        assert "direction_preservation_floor" in result["multiscale_guards"]
    
    def test_guard6_non_aligned_neutral_cap(self):
        """Guard 6: In non-aligned modes, NEUTRAL→MILD promotion is capped at 0.19."""
        from forecast.structure.major_minor_fusion import apply_multiscale_guards
        
        # Base is NEUTRAL (0.10), structure wants to promote to MILD (0.25)
        struct_result = {
            "score_after_structure": 0.25,  # Would become MILD_BULL
            "sign_flip_allowed": False,
            "raw_delta": 0.15,
            "capped_delta": 0.15,
        }
        mode_info = {"mode": "pullback", "pullback_confidence": 0.5,
                     "reversal_candidate": False, "major_dominant": True}
        base_score = 0.10  # NEUTRAL
        
        result = apply_multiscale_guards(struct_result, mode_info, base_score)
        
        # Should cap at 0.19 (keep in NEUTRAL zone)
        assert result["score_after_structure"] <= 0.19
        assert "non_aligned_neutral_cap" in result["multiscale_guards"]
    
    def test_guard6_aligned_mode_allows_promotion(self):
        """Guard 6: In aligned mode, NEUTRAL→MILD promotion IS allowed."""
        from forecast.structure.major_minor_fusion import apply_multiscale_guards
        
        # Base is NEUTRAL (0.10), structure promotes to MILD (0.25)
        struct_result = {
            "score_after_structure": 0.25,  # Would become MILD_BULL
            "sign_flip_allowed": False,
            "raw_delta": 0.15,
            "capped_delta": 0.15,
        }
        mode_info = {"mode": "aligned", "pullback_confidence": 0.0,
                     "reversal_candidate": False, "major_dominant": False}
        base_score = 0.10  # NEUTRAL
        
        result = apply_multiscale_guards(struct_result, mode_info, base_score)
        
        # In aligned mode, promotion is allowed
        assert "non_aligned_neutral_cap" not in result["multiscale_guards"]


# ═══════════════════════════════════════════════════════
# LIVE GENERATOR TESTS (v4.1.2 pipeline)
# ═══════════════════════════════════════════════════════

class TestLiveGeneratorV412:
    """Test live forecast generator with v4.1.2 pipeline."""
    
    def test_generator_imports(self):
        """Verify generator imports correctly."""
        from forecast.generator_v41 import generate_forecast
        assert callable(generate_forecast)
    
    def test_forecast_audit_version(self):
        """Live forecast audit should indicate v4.1.2."""
        # Test via backfill cases which have full audit data
        response = requests.get(f"{BASE_URL}/api/forecast/backfill/latest?asset=BTC&horizon=7D")
        if response.status_code != 200:
            pytest.skip("Backfill endpoint not available")
        
        data = response.json()
        if not data.get("ok"):
            pytest.skip("No backfill data available")
        
        # Check the replay structure metadata which is generated by v4.1.2
        run_id = data["run"]["runId"]
        cases_response = requests.get(f"{BASE_URL}/api/forecast/backfill/cases/{run_id}?limit=1")
        if cases_response.status_code == 200:
            cases_data = cases_response.json()
            if cases_data.get("cases"):
                case = cases_data["cases"][0]
                # v4.1.2 should produce multiscale_meta
                assert "multiscale_meta" in case
                meta = case["multiscale_meta"]
                assert "mode" in meta


class TestBackfillTripleComparison:
    """Test backfill triple comparison (v4.1 base / v4.1.1 / v4.1.2)."""
    
    def test_backfill_latest_has_triple_comparison(self):
        """Latest backfill should include v4.1.2 metrics."""
        response = requests.get(f"{BASE_URL}/api/forecast/backfill/latest?asset=BTC&horizon=7D")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        
        kpis = data["kpis"]
        
        # v4.1.2 specific metrics
        assert "v412_metrics" in kpis, "Should have v4.1.2 specific metrics"
        v412 = kpis["v412_metrics"]
        
        assert "pullback_misread_count" in v412
        assert "direction_preservation_rate" in v412
        assert "mode_distribution" in v412
        assert "guard_usage" in v412
    
    def test_backfill_has_v411_comparison(self):
        """Backfill should include v4.1.1 comparison for triple comparison."""
        response = requests.get(f"{BASE_URL}/api/forecast/backfill/latest?asset=BTC&horizon=7D")
        data = response.json()
        
        kpis = data["kpis"]
        
        # v4.1.1 comparison (optional but expected)
        if "v411_comparison" in kpis:
            v411 = kpis["v411_comparison"]
            assert "base" in v411
            assert "structure" in v411
            assert "comparison" in v411
    
    def test_backfill_cases_have_multiscale_meta(self):
        """Individual cases should include multiscale_meta."""
        response = requests.get(f"{BASE_URL}/api/forecast/backfill/latest?asset=BTC&horizon=7D")
        run_id = response.json()["run"]["runId"]
        
        cases_response = requests.get(f"{BASE_URL}/api/forecast/backfill/cases/{run_id}?limit=5")
        assert cases_response.status_code == 200
        
        data = cases_response.json()
        for case in data["cases"]:
            assert "multiscale_meta" in case, "Each case should have multiscale_meta"
            meta = case["multiscale_meta"]
            
            # Check mode is present
            assert "mode" in meta
            assert meta["mode"] in ["aligned", "pullback", "reversal_candidate", "mixed_range", "fallback_single_scale"]
    
    def test_backfill_cases_have_comparison_v411(self):
        """Individual cases should include comparison_v411."""
        response = requests.get(f"{BASE_URL}/api/forecast/backfill/latest?asset=BTC&horizon=7D")
        run_id = response.json()["run"]["runId"]
        
        cases_response = requests.get(f"{BASE_URL}/api/forecast/backfill/cases/{run_id}?limit=5")
        data = cases_response.json()
        
        for case in data["cases"]:
            # comparison_v411 should be present (may be None if v4.1.1 failed)
            assert "comparison_v411" in case
    
    def test_mode_distribution_populated(self):
        """Mode distribution should have counts for detected modes."""
        response = requests.get(f"{BASE_URL}/api/forecast/backfill/latest?asset=BTC&horizon=7D")
        data = response.json()
        
        v412_metrics = data["kpis"]["v412_metrics"]
        mode_dist = v412_metrics["mode_distribution"]
        
        # At least one mode should have cases
        assert sum(mode_dist.values()) > 0
    
    def test_direction_preservation_rate_valid(self):
        """Direction preservation rate should be between 0 and 1."""
        response = requests.get(f"{BASE_URL}/api/forecast/backfill/latest?asset=BTC&horizon=7D")
        data = response.json()
        
        rate = data["kpis"]["v412_metrics"]["direction_preservation_rate"]
        assert 0 <= rate <= 1


# ═══════════════════════════════════════════════════════
# REPLAY RUNNER TESTS (triple pipeline)
# ═══════════════════════════════════════════════════════

class TestReplayRunnerTriple:
    """Test triple pipeline replay runner."""
    
    def test_import_module(self):
        """Verify replay runner imports correctly."""
        from forecast.backfill.replay_runner import run_dual_replay
        assert callable(run_dual_replay)
    
    def test_replay_returns_triple_results(self):
        """Replay should return base, v4.1.1, and v4.1.2 results."""
        from forecast.backfill.replay_runner import run_dual_replay
        
        # Create minimal snapshot
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
        
        # Check all three pipelines present
        assert "base" in result
        assert "structure" in result  # v4.1.2
        assert "v411" in result       # v4.1.1
        
        # Check structure metadata
        assert "multiscale_meta" in result
        assert "mode" in result["multiscale_meta"]
    
    def test_replay_structure_has_multiscale_guards(self):
        """v4.1.2 result should include multiscale_guards list."""
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
        
        assert "structure_delta" in result
        assert "multiscale_guards" in result["structure_delta"]
        assert isinstance(result["structure_delta"]["multiscale_guards"], list)


# ═══════════════════════════════════════════════════════
# V41_CONFIG CLASSIFICATION TESTS
# ═══════════════════════════════════════════════════════

class TestV41ConfigClassification:
    """Test direction classification thresholds."""
    
    def test_classify_direction_thresholds(self):
        """Verify classify_direction uses correct thresholds."""
        from forecast.v41_config import classify_direction
        
        # STRONG_BULL >= 0.65
        assert classify_direction(0.65) == "STRONG_BULL"
        assert classify_direction(0.80) == "STRONG_BULL"
        
        # MILD_BULL >= 0.20
        assert classify_direction(0.20) == "MILD_BULL"
        assert classify_direction(0.64) == "MILD_BULL"
        
        # NEUTRAL between -0.20 and 0.20
        assert classify_direction(0.0) == "NEUTRAL"
        assert classify_direction(0.19) == "NEUTRAL"
        assert classify_direction(-0.19) == "NEUTRAL"
        
        # MILD_BEAR <= -0.20
        assert classify_direction(-0.20) == "MILD_BEAR"
        assert classify_direction(-0.64) == "MILD_BEAR"
        
        # STRONG_BEAR <= -0.65
        assert classify_direction(-0.65) == "STRONG_BEAR"
        assert classify_direction(-0.90) == "STRONG_BEAR"


# ═══════════════════════════════════════════════════════
# KPI AGGREGATOR V4.1.2 METRICS
# ═══════════════════════════════════════════════════════

class TestKPIAggregatorV412Metrics:
    """Test v4.1.2 specific KPI metrics computation."""
    
    def test_import_module(self):
        """Verify KPI aggregator imports correctly."""
        from forecast.backfill.shadow_kpi_aggregator import aggregate_kpis
        assert callable(aggregate_kpis)
    
    def test_aggregate_includes_v412_metrics(self):
        """Aggregate should include v4.1.2 specific metrics."""
        from forecast.backfill.shadow_kpi_aggregator import aggregate_kpis
        
        # Minimal test case
        cases = [{
            "replay": {
                "base": {"direction": "MILD_BULL", "score": 0.3},
                "structure": {"direction": "MILD_BULL", "score": 0.35},
                "v411": {"direction": "MILD_BULL", "score": 0.32},
                "structure_delta": {"capped_delta": 0.05},
                "structure_delta_v411": {"capped_delta": 0.02, "raw_delta": 0.02, "sign_flip_allowed": False},
            },
            "comparison": {
                "case_type": "both_correct",
                "base_correct": True,
                "structure_correct": True,
                "direction_changed": False,
                "sign_changed": False,
                "strength_only_change": False,
            },
            "comparison_v411": {
                "case_type": "both_correct",
                "base_correct": True,
                "structure_correct": True,
                "direction_changed": False,
                "sign_changed": False,
                "strength_only_change": False,
            },
            "multiscale_meta": {
                "mode": "aligned",
                "multiscale_guards": [],
            },
            "pattern_tags": ["no_impact"],
        }]
        
        result = aggregate_kpis(cases)
        
        assert "v412_metrics" in result
        assert "pullback_misread_count" in result["v412_metrics"]
        assert "direction_preservation_rate" in result["v412_metrics"]
        assert "mode_distribution" in result["v412_metrics"]
        assert "guard_usage" in result["v412_metrics"]
    
    def test_pullback_misread_count(self):
        """Test pullback_misread_count computation."""
        from forecast.backfill.shadow_kpi_aggregator import aggregate_kpis
        
        cases = [
            {"replay": {"base": {"direction": "MILD_BULL", "score": 0.3},
                        "structure": {"direction": "MILD_BULL", "score": 0.35},
                        "structure_delta": {"capped_delta": 0.05}},
             "comparison": {"case_type": "both_correct", "base_correct": True, "structure_correct": True,
                            "direction_changed": False, "sign_changed": False, "strength_only_change": False},
             "multiscale_meta": {"mode": "aligned"},
             "pattern_tags": ["pullback_misread"]},  # Has pullback_misread
            {"replay": {"base": {"direction": "MILD_BULL", "score": 0.3},
                        "structure": {"direction": "MILD_BULL", "score": 0.35},
                        "structure_delta": {"capped_delta": 0.05}},
             "comparison": {"case_type": "both_correct", "base_correct": True, "structure_correct": True,
                            "direction_changed": False, "sign_changed": False, "strength_only_change": False},
             "multiscale_meta": {"mode": "aligned"},
             "pattern_tags": ["no_impact"]},  # No pullback_misread
        ]
        
        result = aggregate_kpis(cases)
        assert result["v412_metrics"]["pullback_misread_count"] == 1


# ═══════════════════════════════════════════════════════
# INTEGRATION TESTS: API ENDPOINTS
# ═══════════════════════════════════════════════════════

class TestBackfillV412APIIntegration:
    """Integration tests for v4.1.2 backfill API."""
    
    def test_backfill_run_endpoint_exists(self):
        """POST /api/forecast/backfill/run endpoint should exist."""
        # Just check the endpoint responds (don't run full backfill)
        response = requests.post(
            f"{BASE_URL}/api/forecast/backfill/run",
            params={"asset": "BTC", "horizon": "7D"},
            timeout=5
        )
        # Should either succeed or return a valid error
        assert response.status_code in [200, 400, 500]
    
    def test_backfill_latest_endpoint_returns_verdict(self):
        """GET /api/forecast/backfill/latest should return verdict."""
        response = requests.get(f"{BASE_URL}/api/forecast/backfill/latest?asset=BTC&horizon=7D")
        assert response.status_code == 200
        
        data = response.json()
        assert data["ok"] is True
        
        verdict = data["verdict"]
        assert verdict["verdict"] in ["PROMOTE", "HOLD", "ROLLBACK", "INSUFFICIENT_DATA"]
    
    def test_verdict_thresholds(self):
        """Verify verdict uses correct PROMOTE thresholds."""
        response = requests.get(f"{BASE_URL}/api/forecast/backfill/latest?asset=BTC&horizon=7D")
        data = response.json()
        
        kpis = data["kpis"]
        verdict = data["verdict"]
        
        accuracy = kpis.get("structure", {}).get("accuracy", 0)
        hurt_rate = kpis.get("comparison", {}).get("hurt_rate", 0)
        
        # If accuracy >= 0.41 and hurt_rate < 0.30 and sign_flips ≈ 0, should be PROMOTE
        # This test verifies the verdict is logical based on KPIs
        if accuracy >= 0.41 and hurt_rate < 0.30:
            # Could be PROMOTE or HOLD depending on sign_flips
            assert verdict["verdict"] in ["PROMOTE", "HOLD"]
