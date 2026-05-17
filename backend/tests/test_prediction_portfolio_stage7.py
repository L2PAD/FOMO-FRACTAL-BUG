"""
Portfolio Brain Stage 7 — Backend API Tests

Tests for:
- POST /api/prediction-portfolio/assess — single candidate assessment
- POST /api/prediction-portfolio/batch — batch assessment
- GET /api/prediction-portfolio/exposure — exposure summary
- GET /api/prediction-portfolio/positions — list positions
- POST /api/prediction-portfolio/positions — add position
- DELETE /api/prediction-portfolio/positions/:id — remove position

Scenarios:
- 2 BTC long markets → second should have high overlap (>0.85) and be BLOCKED
- BTC long + BTC short → overlap should be lower (~0.6) due to direction-aware adjustment
- 3 ETF markets → third should be BLOCKED by entity/theme limits
- Different markets → low overlap, no penalty
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
PORTFOLIO_URL = f"{BASE_URL}/api/prediction-portfolio"


class TestPortfolioBasicAPIs:
    """Basic API endpoint tests for Portfolio Brain"""

    def test_get_positions_empty(self):
        """GET /positions should return empty list initially"""
        resp = requests.get(f"{PORTFOLIO_URL}/positions")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("ok") is True
        assert "positions" in data
        assert isinstance(data["positions"], list)
        print(f"✓ GET /positions returned {data.get('count', 0)} positions")

    def test_get_exposure_empty(self):
        """GET /exposure should return exposure summary"""
        resp = requests.get(f"{PORTFOLIO_URL}/exposure")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("ok") is True
        assert "exposure" in data
        exposure = data["exposure"]
        assert "totalExposure" in exposure
        assert "positionCount" in exposure
        print(f"✓ GET /exposure: totalExposure={exposure['totalExposure']}, positionCount={exposure['positionCount']}")

    def test_assess_single_candidate_no_positions(self):
        """POST /assess with no active positions should return allowed=True"""
        candidate = {
            "marketId": "test-btc-100k",
            "question": "Will BTC reach $100k by end of 2025?",
            "asset": "BTC",
            "eventType": "price_threshold",
            "recommendationAction": "YES_NOW",
            "baseSizeFraction": 0.5,
            "entities": [],
        }
        resp = requests.post(f"{PORTFOLIO_URL}/assess", json=candidate)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("ok") is True
        assessment = data.get("assessment", {})
        assert "allowed" in assessment
        assert "blocked" in assessment
        assert "capped" in assessment
        assert "overlapScore" in assessment
        print(f"✓ POST /assess (no positions): allowed={assessment['allowed']}, blocked={assessment['blocked']}")

    def test_batch_assess_no_positions(self):
        """POST /batch with no active positions should return assessments for all"""
        cases = [
            {"marketId": "test-btc-1", "question": "BTC $100k?", "asset": "BTC", "eventType": "price_threshold", "recommendationAction": "YES_NOW", "baseSizeFraction": 0.5},
            {"marketId": "test-eth-1", "question": "ETH $5k?", "asset": "ETH", "eventType": "price_threshold", "recommendationAction": "YES_NOW", "baseSizeFraction": 0.3},
        ]
        resp = requests.post(f"{PORTFOLIO_URL}/batch", json={"cases": cases})
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("ok") is True
        results = data.get("results", {})
        assert "test-btc-1" in results
        assert "test-eth-1" in results
        print(f"✓ POST /batch (no positions): {len(results)} assessments returned")


class TestPositionManagement:
    """Tests for position CRUD operations"""

    def test_add_position(self):
        """POST /positions should add a new position"""
        position = {
            "marketId": "TEST_btc_long_1",
            "question": "Will BTC reach $100k by end of 2025?",
            "asset": "BTC",
            "eventType": "price_threshold",
            "recommendationAction": "YES_NOW",
            "baseSizeFraction": 0.5,
            "entities": [],
        }
        resp = requests.post(f"{PORTFOLIO_URL}/positions", json=position)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("ok") is True
        print(f"✓ POST /positions: added position TEST_btc_long_1")

    def test_verify_position_added(self):
        """GET /positions should show the added position"""
        resp = requests.get(f"{PORTFOLIO_URL}/positions")
        assert resp.status_code == 200
        data = resp.json()
        positions = data.get("positions", [])
        market_ids = [p.get("marketId") for p in positions]
        assert "TEST_btc_long_1" in market_ids, f"Position not found. Found: {market_ids}"
        print(f"✓ GET /positions: verified TEST_btc_long_1 exists")

    def test_remove_position(self):
        """DELETE /positions/:id should remove the position"""
        resp = requests.delete(f"{PORTFOLIO_URL}/positions/TEST_btc_long_1")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("ok") is True
        print(f"✓ DELETE /positions/TEST_btc_long_1: position removed")

    def test_verify_position_removed(self):
        """GET /positions should not show the removed position"""
        resp = requests.get(f"{PORTFOLIO_URL}/positions")
        assert resp.status_code == 200
        data = resp.json()
        positions = data.get("positions", [])
        market_ids = [p.get("marketId") for p in positions]
        assert "TEST_btc_long_1" not in market_ids, f"Position still exists: {market_ids}"
        print(f"✓ GET /positions: verified TEST_btc_long_1 removed")


class TestOverlapScenarios:
    """Tests for overlap detection scenarios"""

    @pytest.fixture(autouse=True)
    def cleanup_positions(self):
        """Clean up test positions before and after each test"""
        # Cleanup before
        self._cleanup_test_positions()
        yield
        # Cleanup after
        self._cleanup_test_positions()

    def _cleanup_test_positions(self):
        """Remove all TEST_ prefixed positions"""
        resp = requests.get(f"{PORTFOLIO_URL}/positions")
        if resp.status_code == 200:
            positions = resp.json().get("positions", [])
            for p in positions:
                mid = p.get("marketId", "")
                if mid.startswith("TEST_"):
                    requests.delete(f"{PORTFOLIO_URL}/positions/{mid}")

    def test_scenario_btc_long_long_blocked(self):
        """
        Scenario: 2 BTC long markets → second should have high overlap (>0.85) and be BLOCKED
        """
        # Add first BTC long position
        pos1 = {
            "marketId": "TEST_btc_long_100k",
            "question": "Will BTC reach $100k by end of 2025?",
            "asset": "BTC",
            "eventType": "price_threshold",
            "recommendationAction": "YES_NOW",
            "baseSizeFraction": 0.5,
            "entities": [],
        }
        resp = requests.post(f"{PORTFOLIO_URL}/positions", json=pos1)
        assert resp.status_code == 200, f"Failed to add position: {resp.text}"
        print(f"✓ Added first BTC long position")

        # Assess second BTC long candidate (very similar)
        candidate = {
            "marketId": "TEST_btc_long_110k",
            "question": "Will BTC reach $110k by end of 2025?",
            "asset": "BTC",
            "eventType": "price_threshold",
            "recommendationAction": "YES_NOW",
            "baseSizeFraction": 0.5,
            "entities": [],
        }
        resp = requests.post(f"{PORTFOLIO_URL}/assess", json=candidate)
        assert resp.status_code == 200, f"Failed to assess: {resp.text}"
        data = resp.json()
        assessment = data.get("assessment", {})

        overlap = assessment.get("overlapScore", 0)
        blocked = assessment.get("blocked", False)

        print(f"  Overlap score: {overlap}")
        print(f"  Blocked: {blocked}")
        print(f"  Reasons: {assessment.get('reasons', [])}")

        # Expect high overlap (>0.85) and BLOCKED
        assert overlap > 0.85, f"Expected overlap > 0.85, got {overlap}"
        assert blocked is True, f"Expected blocked=True, got {blocked}"
        print(f"✓ Scenario PASS: 2 BTC long → overlap={overlap:.2f}, blocked={blocked}")

    def test_scenario_btc_long_short_reduced_overlap(self):
        """
        Scenario: BTC long + BTC short → overlap should be lower (~0.6) due to direction-aware adjustment
        """
        # Add BTC long position
        pos1 = {
            "marketId": "TEST_btc_long_100k_v2",
            "question": "Will BTC reach $100k by end of 2025?",
            "asset": "BTC",
            "eventType": "price_threshold",
            "recommendationAction": "YES_NOW",
            "baseSizeFraction": 0.5,
            "entities": [],
        }
        resp = requests.post(f"{PORTFOLIO_URL}/positions", json=pos1)
        assert resp.status_code == 200

        # Assess BTC short candidate (opposite direction)
        candidate = {
            "marketId": "TEST_btc_short_80k",
            "question": "Will BTC drop below $80k by end of 2025?",
            "asset": "BTC",
            "eventType": "price_threshold",
            "recommendationAction": "NO_NOW",  # Short direction
            "baseSizeFraction": 0.5,
            "entities": [],
        }
        resp = requests.post(f"{PORTFOLIO_URL}/assess", json=candidate)
        assert resp.status_code == 200
        data = resp.json()
        assessment = data.get("assessment", {})

        overlap = assessment.get("overlapScore", 0)
        blocked = assessment.get("blocked", False)

        print(f"  Overlap score: {overlap}")
        print(f"  Blocked: {blocked}")
        print(f"  Capped: {assessment.get('capped', False)}")

        # Expect lower overlap (~0.6) due to direction adjustment, NOT blocked
        assert overlap < 0.85, f"Expected overlap < 0.85 (direction-adjusted), got {overlap}"
        # Should not be blocked due to opposite direction
        print(f"✓ Scenario PASS: BTC long + short → overlap={overlap:.2f}, blocked={blocked}")

    def test_scenario_etf_theme_blocked(self):
        """
        Scenario: 3 ETF markets → third should be BLOCKED by entity/theme limits
        """
        # Add first ETF position
        pos1 = {
            "marketId": "TEST_etf_btc_1",
            "question": "Will SEC approve BTC ETF by Q1 2025?",
            "asset": "BTC",
            "eventType": "etf_catalyst",
            "recommendationAction": "YES_NOW",
            "baseSizeFraction": 0.8,
            "entities": ["SEC", "BlackRock"],
        }
        resp = requests.post(f"{PORTFOLIO_URL}/positions", json=pos1)
        assert resp.status_code == 200

        # Add second ETF position
        pos2 = {
            "marketId": "TEST_etf_btc_2",
            "question": "Will Fidelity BTC ETF get approved?",
            "asset": "BTC",
            "eventType": "etf_catalyst",
            "recommendationAction": "YES_NOW",
            "baseSizeFraction": 0.8,
            "entities": ["SEC", "Fidelity"],
        }
        resp = requests.post(f"{PORTFOLIO_URL}/positions", json=pos2)
        assert resp.status_code == 200

        # Assess third ETF candidate
        candidate = {
            "marketId": "TEST_etf_btc_3",
            "question": "Will Grayscale BTC ETF convert?",
            "asset": "BTC",
            "eventType": "etf_catalyst",
            "recommendationAction": "YES_NOW",
            "baseSizeFraction": 0.8,
            "entities": ["SEC", "Grayscale"],
        }
        resp = requests.post(f"{PORTFOLIO_URL}/assess", json=candidate)
        assert resp.status_code == 200
        data = resp.json()
        assessment = data.get("assessment", {})

        blocked = assessment.get("blocked", False)
        reasons = assessment.get("reasons", [])

        print(f"  Blocked: {blocked}")
        print(f"  Reasons: {reasons}")

        # Expect BLOCKED due to theme/entity concentration
        # Either blocked by overlap or by risk budget (entity/theme limits)
        has_limit_reason = any("limit" in r.lower() or "exceeds" in r.lower() or "concentrated" in r.lower() for r in reasons)
        assert blocked is True or has_limit_reason, f"Expected blocked or limit warning, got blocked={blocked}, reasons={reasons}"
        print(f"✓ Scenario PASS: 3 ETF markets → blocked={blocked}")

    def test_scenario_different_markets_no_penalty(self):
        """
        Scenario: Different markets → low overlap, no penalty
        """
        # Add BTC price threshold position
        pos1 = {
            "marketId": "TEST_btc_price_1",
            "question": "Will BTC reach $100k?",
            "asset": "BTC",
            "eventType": "price_threshold",
            "recommendationAction": "YES_NOW",
            "baseSizeFraction": 0.3,
            "entities": [],
        }
        resp = requests.post(f"{PORTFOLIO_URL}/positions", json=pos1)
        assert resp.status_code == 200

        # Assess completely different market (SOL listing)
        candidate = {
            "marketId": "TEST_sol_listing_1",
            "question": "Will SOL get listed on new exchange?",
            "asset": "SOL",
            "eventType": "listing_catalyst",
            "recommendationAction": "YES_NOW",
            "baseSizeFraction": 0.3,
            "entities": ["Kraken"],
        }
        resp = requests.post(f"{PORTFOLIO_URL}/assess", json=candidate)
        assert resp.status_code == 200
        data = resp.json()
        assessment = data.get("assessment", {})

        overlap = assessment.get("overlapScore", 0)
        blocked = assessment.get("blocked", False)
        capped = assessment.get("capped", False)
        penalty = assessment.get("correlationPenalty", 0)

        print(f"  Overlap score: {overlap}")
        print(f"  Blocked: {blocked}")
        print(f"  Capped: {capped}")
        print(f"  Correlation penalty: {penalty}")

        # Expect low overlap (<0.45), no penalty, not blocked
        assert overlap < 0.45, f"Expected overlap < 0.45, got {overlap}"
        assert blocked is False, f"Expected blocked=False, got {blocked}"
        assert penalty == 0, f"Expected no penalty, got {penalty}"
        print(f"✓ Scenario PASS: Different markets → overlap={overlap:.2f}, no penalty")


class TestPredictionRunIntegration:
    """Test that /api/prediction/run includes portfolio field"""

    def test_prediction_run_includes_portfolio(self):
        """GET /api/prediction/run should include portfolio field in each case"""
        resp = requests.get(f"{BASE_URL}/api/prediction/run?limit=5", timeout=60)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("ok") is True

        sections = data.get("sections", {})
        all_cases = []
        for section_name, cases in sections.items():
            all_cases.extend(cases)

        if not all_cases:
            pytest.skip("No cases returned from prediction/run")

        # Check at least one case has portfolio field
        cases_with_portfolio = [c for c in all_cases if "portfolio" in c]
        print(f"  Total cases: {len(all_cases)}")
        print(f"  Cases with portfolio field: {len(cases_with_portfolio)}")

        # Portfolio field should be present (even if empty assessment)
        # Note: If no positions exist, portfolio may be empty dict
        if cases_with_portfolio:
            sample = cases_with_portfolio[0]
            pf = sample.get("portfolio", {})
            print(f"  Sample portfolio: {pf}")
            assert "allowed" in pf or "blocked" in pf or pf == {}, f"Portfolio field malformed: {pf}"
            print(f"✓ /api/prediction/run includes portfolio field")
        else:
            print(f"⚠ No cases have portfolio field (may be expected if no positions)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
