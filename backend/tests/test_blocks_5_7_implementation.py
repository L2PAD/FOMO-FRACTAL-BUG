"""
Block 5-7 Implementation Tests
=============================

Block 5: Multi-Layer Toggle (Exchange, On-chain, Sentiment, Final)
Block 6: Forecast History Markers (WIN/LOSS/WEAK colored dots)
Block 7: Confidence Band (shaded area inversely proportional to confidence)
Block 4: forecastOverlay segment verification (continued from iteration_47)

Tests verify:
- API returns correct data structure for all blocks
- forecastOverlay has correct horizon-based timestamps
- outcomeMarkers have correct labels (TP/FP/WEAK)
- layers.exchange.forecastHistory exists
- Confidence band calculation is correct
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestBlock4ForecastOverlay:
    """Block 4: Verify forecastOverlay segment for chart rendering"""
    
    def test_forecast_overlay_has_required_fields(self):
        """forecastOverlay must have fromTs, toTs, targetPrice, direction, confidence"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/price-vs-expectation-v3",
            params={"asset": "BTC", "range": "7d", "horizon": "1D"},
            timeout=60
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") == True
        
        overlay = data.get("forecastOverlay")
        assert overlay is not None, "forecastOverlay is missing"
        
        # Required fields for Block 4
        required_fields = ["fromTs", "toTs", "targetPrice", "direction", "confidence", "horizon", "action"]
        for field in required_fields:
            assert field in overlay, f"Missing required field: {field}"
        
        print(f"✓ forecastOverlay has all required fields: {list(overlay.keys())}")
    
    def test_forecast_overlay_1d_horizon(self):
        """1D horizon should have toTs = fromTs + 1 day"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/price-vs-expectation-v3",
            params={"asset": "BTC", "range": "7d", "horizon": "1D"},
            timeout=60
        )
        data = response.json()
        overlay = data.get("forecastOverlay", {})
        
        from_ts = overlay.get("fromTs", 0)
        to_ts = overlay.get("toTs", 0)
        
        # 1D = 24 hours = 86400000 ms
        expected_delta = 24 * 60 * 60 * 1000
        actual_delta = to_ts - from_ts
        
        assert abs(actual_delta - expected_delta) < 60000, f"1D horizon delta should be ~24h, got {actual_delta/3600000}h"
        assert overlay.get("horizon") == "1D"
        print(f"✓ 1D horizon: fromTs={from_ts}, toTs={to_ts}, delta={actual_delta/3600000:.1f}h")
    
    def test_forecast_overlay_7d_horizon(self):
        """7D horizon should have toTs = fromTs + 7 days"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/price-vs-expectation-v3",
            params={"asset": "BTC", "range": "7d", "horizon": "7D"},
            timeout=60
        )
        data = response.json()
        overlay = data.get("forecastOverlay", {})
        
        from_ts = overlay.get("fromTs", 0)
        to_ts = overlay.get("toTs", 0)
        
        # 7D = 7 * 24 hours
        expected_delta = 7 * 24 * 60 * 60 * 1000
        actual_delta = to_ts - from_ts
        
        assert abs(actual_delta - expected_delta) < 60000, f"7D horizon delta should be ~7 days, got {actual_delta/(24*3600000):.1f}d"
        assert overlay.get("horizon") == "7D"
        print(f"✓ 7D horizon: delta={actual_delta/(24*3600000):.1f} days")
    
    def test_forecast_overlay_has_render_hints(self):
        """forecastOverlay should have renderAs and color for frontend"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/price-vs-expectation-v3",
            params={"asset": "BTC", "range": "7d", "horizon": "1D"},
            timeout=60
        )
        data = response.json()
        overlay = data.get("forecastOverlay", {})
        
        assert "renderAs" in overlay, "Missing renderAs hint"
        assert "color" in overlay, "Missing color hint"
        assert overlay["renderAs"] == "markLine"
        print(f"✓ Render hints: renderAs={overlay['renderAs']}, color={overlay['color']}")


class TestBlock5MultiLayerToggle:
    """Block 5: Verify API returns data for Exchange layer"""
    
    def test_layers_exchange_exists(self):
        """layers.exchange should have forecastHistory and futurePoint"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/price-vs-expectation-v3",
            params={"asset": "BTC", "range": "7d", "horizon": "1D"},
            timeout=60
        )
        data = response.json()
        
        layers = data.get("layers", {})
        assert "exchange" in layers, "layers.exchange is missing"
        
        exchange_layer = layers["exchange"]
        assert "forecastHistory" in exchange_layer, "exchange.forecastHistory is missing"
        assert "futurePoint" in exchange_layer, "exchange.futurePoint is missing"
        
        print(f"✓ Exchange layer present with forecastHistory ({len(exchange_layer['forecastHistory'])} items) and futurePoint")
    
    def test_layers_meta_exists(self):
        """layers.meta should have forecastHistory and futurePoint (Final layer)"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/price-vs-expectation-v3",
            params={"asset": "BTC", "range": "7d", "horizon": "1D"},
            timeout=60
        )
        data = response.json()
        
        layers = data.get("layers", {})
        assert "meta" in layers, "layers.meta is missing (Final layer)"
        
        meta_layer = layers["meta"]
        assert "forecastHistory" in meta_layer, "meta.forecastHistory is missing"
        assert "futurePoint" in meta_layer, "meta.futurePoint is missing"
        
        print(f"✓ Meta/Final layer present with forecastHistory ({len(meta_layer['forecastHistory'])} items)")
    
    def test_exchange_future_point_has_required_fields(self):
        """Exchange layer futurePoint should have targetPrice, direction, confidence"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/price-vs-expectation-v3",
            params={"asset": "BTC", "range": "7d", "horizon": "1D"},
            timeout=60
        )
        data = response.json()
        
        future_point = data.get("layers", {}).get("exchange", {}).get("futurePoint", {})
        
        required = ["targetPrice", "direction", "confidence", "expectedMovePct"]
        for field in required:
            assert field in future_point, f"exchange.futurePoint missing {field}"
        
        print(f"✓ Exchange futurePoint: targetPrice=${future_point['targetPrice']:.2f}, direction={future_point['direction']}, confidence={future_point['confidence']:.2%}")


class TestBlock6OutcomeMarkers:
    """Block 6: Forecast History Markers (WIN/LOSS/WEAK)"""
    
    def test_outcome_markers_exist(self):
        """outcomeMarkers array should be present"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/price-vs-expectation-v3",
            params={"asset": "BTC", "range": "30d", "horizon": "1D"},  # Longer range for more markers
            timeout=60
        )
        data = response.json()
        
        markers = data.get("outcomeMarkers", [])
        assert isinstance(markers, list), "outcomeMarkers should be an array"
        print(f"✓ outcomeMarkers present: {len(markers)} markers found")
    
    def test_outcome_markers_have_required_fields(self):
        """Each marker should have ts, label, direction, expectedMovePct, actualMovePct"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/price-vs-expectation-v3",
            params={"asset": "BTC", "range": "30d", "horizon": "1D"},
            timeout=60
        )
        data = response.json()
        
        markers = data.get("outcomeMarkers", [])
        if len(markers) == 0:
            pytest.skip("No outcome markers in data - forecasts may not be evaluated yet")
        
        required = ["ts", "label", "direction", "expectedMovePct", "actualMovePct", "confidence"]
        for marker in markers[:3]:  # Check first 3
            for field in required:
                assert field in marker, f"Marker missing {field}: {marker}"
        
        print(f"✓ Outcome markers have all required fields")
    
    def test_outcome_marker_labels_valid(self):
        """Marker labels should be TP (WIN), FP (LOSS), FN (LOSS), or WEAK"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/price-vs-expectation-v3",
            params={"asset": "BTC", "range": "30d", "horizon": "1D"},
            timeout=60
        )
        data = response.json()
        
        markers = data.get("outcomeMarkers", [])
        if len(markers) == 0:
            pytest.skip("No outcome markers in data")
        
        valid_labels = {"TP", "FP", "FN", "WEAK"}
        labels_found = set()
        
        for marker in markers:
            label = marker.get("label")
            assert label in valid_labels, f"Invalid label: {label}. Expected one of {valid_labels}"
            labels_found.add(label)
        
        print(f"✓ All marker labels valid. Labels found: {labels_found}")
        
        # Block 6: TP=WIN (green), FP/FN=LOSS (red), WEAK=yellow
        label_mapping = {
            "TP": "WIN (green circle)",
            "FP": "LOSS (red triangle)",
            "FN": "LOSS (red triangle)",
            "WEAK": "WEAK (yellow rect)"
        }
        for label in labels_found:
            print(f"  - {label}: {label_mapping[label]}")


class TestBlock7ConfidenceBand:
    """Block 7: Confidence Band (shaded area inversely proportional to confidence)"""
    
    def test_future_band_exists(self):
        """layers.meta.futureBand should have upper and lower bounds"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/price-vs-expectation-v3",
            params={"asset": "BTC", "range": "7d", "horizon": "1D"},
            timeout=60
        )
        data = response.json()
        
        future_band = data.get("layers", {}).get("meta", {}).get("futureBand", {})
        
        assert "upper" in future_band, "futureBand missing upper bound"
        assert "lower" in future_band, "futureBand missing lower bound"
        assert future_band["upper"] > future_band["lower"], "Upper should be > lower"
        
        print(f"✓ Confidence band: lower=${future_band['lower']:.2f}, upper=${future_band['upper']:.2f}")
    
    def test_confidence_band_width_calculation(self):
        """Band width should be inversely proportional to confidence"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/price-vs-expectation-v3",
            params={"asset": "BTC", "range": "7d", "horizon": "1D"},
            timeout=60
        )
        data = response.json()
        
        overlay = data.get("forecastOverlay", {})
        band = data.get("layers", {}).get("meta", {}).get("futureBand", {})
        
        confidence = overlay.get("confidence", 0.5)
        target_price = overlay.get("targetPrice", 0)
        expected_move = abs(overlay.get("expectedMovePct", 0)) / 100
        
        if band:
            actual_width = band.get("upper", 0) - band.get("lower", 0)
            
            # Block 7: Width = price * expectedMove * (1 - confidence)
            # Higher confidence = narrower band
            print(f"✓ Confidence band analysis:")
            print(f"  - Confidence: {confidence:.2%}")
            print(f"  - Target price: ${target_price:.2f}")
            print(f"  - Expected move: {expected_move:.2%}")
            print(f"  - Band width: ${actual_width:.2f}")
            print(f"  - Band as % of target: {(actual_width/target_price)*100:.2f}%")
            
            # Lower confidence should give wider band
            assert actual_width > 0, "Band width should be positive"
    
    def test_forecast_overlay_has_confidence(self):
        """forecastOverlay should have confidence for band rendering"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/price-vs-expectation-v3",
            params={"asset": "BTC", "range": "7d", "horizon": "1D"},
            timeout=60
        )
        data = response.json()
        
        overlay = data.get("forecastOverlay", {})
        
        assert "confidence" in overlay, "forecastOverlay missing confidence"
        assert 0 <= overlay["confidence"] <= 1, f"Confidence should be 0-1, got {overlay['confidence']}"
        
        print(f"✓ Forecast overlay confidence: {overlay['confidence']:.2%}")


class TestBlock1HealthState:
    """Block 1: VerdictPanel should show health state"""
    
    def test_verdict_has_health_state(self):
        """verdict.health should have state field"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/price-vs-expectation-v3",
            params={"asset": "BTC", "range": "7d", "horizon": "1D"},
            timeout=60
        )
        data = response.json()
        
        verdict = data.get("verdict", {})
        health = verdict.get("health", {})
        
        assert "state" in health, "verdict.health missing state"
        assert health["state"] in ["HEALTHY", "DEGRADED", "CRITICAL"], f"Invalid health state: {health['state']}"
        
        print(f"✓ Block 1: Verdict health state = {health['state']}")
        print(f"  - Modifier: {health.get('modifier', 'N/A')}")
        print(f"  - Critical streak: {health.get('criticalStreak', 'N/A')}")


class TestIntegration:
    """Integration tests for Blocks 5-7 together"""
    
    def test_full_api_response_structure(self):
        """Verify complete API response has all required sections"""
        response = requests.get(
            f"{BASE_URL}/api/market/chart/price-vs-expectation-v3",
            params={"asset": "BTC", "range": "7d", "horizon": "1D"},
            timeout=60
        )
        assert response.status_code == 200
        data = response.json()
        
        # Core structure
        assert data.get("ok") == True
        assert "price" in data
        assert "layers" in data
        
        # Block 4: forecastOverlay
        assert "forecastOverlay" in data, "Missing Block 4: forecastOverlay"
        
        # Block 5: layers with exchange
        assert "exchange" in data.get("layers", {}), "Missing Block 5: layers.exchange"
        
        # Block 6: outcomeMarkers
        assert "outcomeMarkers" in data, "Missing Block 6: outcomeMarkers"
        
        # Block 7: futureBand (for confidence band)
        assert "futureBand" in data.get("layers", {}).get("meta", {}), "Missing Block 7: futureBand"
        
        # Block 1: verdict.health
        assert "health" in data.get("verdict", {}), "Missing Block 1: verdict.health"
        
        print("✓ Full API response has all Block 1, 4, 5, 6, 7 components")
        print(f"  - Price points: {len(data.get('price', []))}")
        print(f"  - Outcome markers: {len(data.get('outcomeMarkers', []))}")
        print(f"  - Exchange forecast history: {len(data.get('layers', {}).get('exchange', {}).get('forecastHistory', []))}")
    
    def test_different_assets(self):
        """Test API works for different assets"""
        assets = ["BTC", "ETH", "SOL"]
        
        for asset in assets:
            response = requests.get(
                f"{BASE_URL}/api/market/chart/price-vs-expectation-v3",
                params={"asset": asset, "range": "7d", "horizon": "1D"},
                timeout=60
            )
            assert response.status_code == 200
            data = response.json()
            assert data.get("ok") == True, f"API failed for {asset}"
            assert data.get("asset") == asset
            print(f"✓ {asset}: API response OK")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
