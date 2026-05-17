"""
MiniApp Edge + Profile + Polymarket Ingestion Tests
====================================================
Tests for:
- POST /api/miniapp/polymarket/ingest - Polymarket data ingestion
- GET /api/miniapp/edge - Edge Engine with Polymarket source
- GET /api/miniapp/accuracy/audit - Accuracy audit with directional metrics
- GET /api/miniapp/profile - Profile with directional performance
- Regression tests for home, feed, billing/plans
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestPolymarketIngestion:
    """Test Polymarket data ingestion endpoint"""
    
    def test_polymarket_ingest_returns_ok(self):
        """POST /api/miniapp/polymarket/ingest should return ok=true with ingested count"""
        response = requests.post(f"{BASE_URL}/api/miniapp/polymarket/ingest")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") is True
        assert "ingested" in data
        assert "total_fetched" in data
        assert "assets_covered" in data
        assert isinstance(data["ingested"], int)
        assert isinstance(data["total_fetched"], int)
        assert isinstance(data["assets_covered"], list)
        print(f"Polymarket ingestion: {data['ingested']} markets ingested, assets: {data['assets_covered']}")


class TestEdgeEndpoint:
    """Test Edge Engine endpoint with Polymarket data"""
    
    def test_edge_returns_active_status(self):
        """GET /api/miniapp/edge should return ACTIVE status when prediction_markets has data"""
        response = requests.get(f"{BASE_URL}/api/miniapp/edge")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") is True
        assert data.get("status") == "ACTIVE"
        assert data.get("source") == "polymarket"
        print(f"Edge status: {data['status']}, source: {data.get('source')}")
    
    def test_edge_best_contains_required_fields(self):
        """GET /api/miniapp/edge best edge should contain all required fields"""
        response = requests.get(f"{BASE_URL}/api/miniapp/edge")
        assert response.status_code == 200
        data = response.json()
        
        best = data.get("best")
        assert best is not None, "Best edge should not be None"
        
        # Required fields
        required_fields = ["question", "marketProbability", "modelProbability", "edge", "direction", "confidence", "reason"]
        for field in required_fields:
            assert field in best, f"Best edge missing field: {field}"
        
        # Validate types
        assert isinstance(best["question"], str)
        assert isinstance(best["marketProbability"], (int, float))
        assert isinstance(best["modelProbability"], (int, float))
        assert isinstance(best["edge"], (int, float))
        assert best["direction"] in ["BUY", "SELL", "WAIT"]
        assert isinstance(best["confidence"], (int, float))
        assert isinstance(best["reason"], list)
        
        print(f"Best edge: {best['asset']} - {best['question'][:50]}...")
        print(f"  Market: {best['marketProbability']}, Model: {best['modelProbability']}, Edge: {best['edge']}")
        print(f"  Direction: {best['direction']}, Confidence: {best['confidence']}")
    
    def test_edge_markets_list_has_polymarket_source(self):
        """GET /api/miniapp/edge markets should have source='polymarket'"""
        response = requests.get(f"{BASE_URL}/api/miniapp/edge")
        assert response.status_code == 200
        data = response.json()
        
        markets = data.get("markets", [])
        assert len(markets) > 0, "Markets list should not be empty"
        
        for market in markets:
            assert market.get("source") == "polymarket", f"Market source should be 'polymarket', got: {market.get('source')}"
            assert "question" in market
            assert "marketProbability" in market
            assert "modelProbability" in market
            assert "edge" in market
        
        print(f"Found {len(markets)} markets with polymarket source")


class TestAccuracyAudit:
    """Test Accuracy Audit endpoint"""
    
    def test_accuracy_audit_returns_ok(self):
        """GET /api/miniapp/accuracy/audit should return ok=true"""
        response = requests.get(f"{BASE_URL}/api/miniapp/accuracy/audit")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") is True
        print(f"Accuracy audit: totalEvaluated={data.get('totalEvaluated')}")
    
    def test_accuracy_audit_overall_structure(self):
        """GET /api/miniapp/accuracy/audit should return directional accuracy metrics"""
        response = requests.get(f"{BASE_URL}/api/miniapp/accuracy/audit")
        assert response.status_code == 200
        data = response.json()
        
        overall = data.get("overall", {})
        
        # Required directional metrics
        assert "directionalAccuracy" in overall
        assert "directionalTotal" in overall
        assert "directionalCorrect" in overall
        assert "coverage" in overall
        assert "riskAccuracy" in overall
        assert "catastrophicRate" in overall
        
        # Validate types
        assert isinstance(overall["directionalAccuracy"], (int, float))
        assert isinstance(overall["directionalTotal"], int)
        assert isinstance(overall["directionalCorrect"], int)
        assert isinstance(overall["coverage"], (int, float))
        assert isinstance(overall["riskAccuracy"], (int, float))
        assert isinstance(overall["catastrophicRate"], (int, float))
        
        print(f"Directional accuracy: {overall['directionalAccuracy']*100:.1f}%")
        print(f"Directional: {overall['directionalCorrect']}/{overall['directionalTotal']}")
        print(f"Coverage: {overall['coverage']*100:.1f}%")
        print(f"Risk accuracy: {overall['riskAccuracy']*100:.1f}%")
        print(f"Catastrophic rate: {overall['catastrophicRate']*100:.1f}%")
    
    def test_accuracy_audit_breakdowns(self):
        """GET /api/miniapp/accuracy/audit should return byType, byHorizon, byAsset breakdowns"""
        response = requests.get(f"{BASE_URL}/api/miniapp/accuracy/audit")
        assert response.status_code == 200
        data = response.json()
        
        assert "byType" in data
        assert "byHorizon" in data
        assert "byAsset" in data
        
        # Validate byType structure
        by_type = data.get("byType", {})
        for type_name, type_data in by_type.items():
            assert "accuracy" in type_data
            assert "correct" in type_data
            assert "total" in type_data
        
        print(f"byType: {list(by_type.keys())}")
        print(f"byHorizon: {list(data.get('byHorizon', {}).keys())}")
        print(f"byAsset: {list(data.get('byAsset', {}).keys())}")


class TestProfileEndpoint:
    """Test Profile endpoint with directional performance"""
    
    def test_profile_returns_ok(self):
        """GET /api/miniapp/profile should return ok=true"""
        response = requests.get(f"{BASE_URL}/api/miniapp/profile")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") is True
        print(f"Profile: user={data.get('user', {}).get('name')}")
    
    def test_profile_performance_directional_fields(self):
        """GET /api/miniapp/profile performance should contain directional metrics"""
        response = requests.get(f"{BASE_URL}/api/miniapp/profile")
        assert response.status_code == 200
        data = response.json()
        
        performance = data.get("performance", {})
        
        # Required directional fields
        assert "directionalTotal" in performance
        assert "directionalCorrect" in performance
        assert "accuracy" in performance
        assert "coverage" in performance
        
        # Validate types
        assert isinstance(performance["directionalTotal"], int)
        assert isinstance(performance["directionalCorrect"], int)
        assert isinstance(performance["accuracy"], (int, float))
        assert isinstance(performance["coverage"], (int, float))
        
        print(f"Profile performance:")
        print(f"  Directional: {performance['directionalCorrect']}/{performance['directionalTotal']}")
        print(f"  Accuracy: {performance['accuracy']*100:.0f}%")
        print(f"  Coverage: {performance['coverage']*100:.0f}%")
    
    def test_profile_contains_all_sections(self):
        """GET /api/miniapp/profile should contain user, performance, favorites, referral, promo, settings"""
        response = requests.get(f"{BASE_URL}/api/miniapp/profile")
        assert response.status_code == 200
        data = response.json()
        
        required_sections = ["user", "performance", "favorites", "referral", "promo", "settings"]
        for section in required_sections:
            assert section in data, f"Profile missing section: {section}"
        
        print(f"Profile sections: {list(data.keys())}")


class TestRegressionEndpoints:
    """Regression tests for existing MiniApp endpoints"""
    
    def test_home_endpoint(self):
        """GET /api/miniapp/home?asset=BTC should return ok=true"""
        response = requests.get(f"{BASE_URL}/api/miniapp/home?asset=BTC")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") is True
        assert data.get("asset") == "BTC"
        assert "decision" in data
        assert "price" in data
        print(f"Home: BTC price={data.get('price')}, decision={data.get('decision', {}).get('action')}")
    
    def test_feed_endpoint(self):
        """GET /api/miniapp/feed should return ok=true with sections"""
        response = requests.get(f"{BASE_URL}/api/miniapp/feed")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") is True
        assert "sections" in data
        assert isinstance(data["sections"], list)
        print(f"Feed: {len(data['sections'])} sections, {data.get('counts', {}).get('all', 0)} items")
    
    def test_billing_plans_endpoint(self):
        """GET /api/miniapp/billing/plans should return ok=true"""
        response = requests.get(f"{BASE_URL}/api/miniapp/billing/plans")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("ok") is True
        assert "billingMode" in data
        assert "monthly" in data
        assert "yearly" in data
        print(f"Billing plans: mode={data.get('billingMode')}, monthly=${data.get('monthly', {}).get('price')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
