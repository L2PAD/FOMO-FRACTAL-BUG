"""
Phase 1.3: Session Selection for Parser Runtime (AUTO/MANUAL)
Tests for runtime selection endpoints and preferred account management.

Endpoints tested:
- GET /api/v4/twitter/runtime/selection - preview без cookies
- GET /api/v4/twitter/runtime/selection/full - полный config с cookies
- GET /api/v4/twitter/runtime/candidates - список всех кандидатов
- GET /api/v4/twitter/accounts/preferred - получить текущий preferred
- POST /api/v4/twitter/accounts/:id/preferred - установить preferred
- DELETE /api/v4/twitter/accounts/preferred - сбросить preferred
"""

import pytest
import requests
import os

BASE_URL = "http://localhost:8003"

# Test accounts (owned by dev-user)
ACCOUNT_1_ID = "697fa7d52dd38baab2b57c28"  # test_twitter_user
ACCOUNT_2_ID = "697fab792dd38baab2c880a4"  # second_twitter_user
NON_EXISTENT_ACCOUNT = "000000000000000000000000"


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    # Don't set Content-Type globally - only set it when sending JSON body
    return session


@pytest.fixture(scope="module", autouse=True)
def cleanup_preferred_module(api_client):
    """Cleanup preferred account at start and end of module"""
    # Clear at start of module
    api_client.delete(f"{BASE_URL}/api/v4/twitter/accounts/preferred")
    yield
    # Clear at end of module
    api_client.delete(f"{BASE_URL}/api/v4/twitter/accounts/preferred")


class TestRuntimeSelectionPreview:
    """Tests for GET /api/v4/twitter/runtime/selection (preview without cookies)"""

    def test_selection_preview_auto_mode(self, api_client):
        """AUTO mode returns best account based on ranking algorithm"""
        response = api_client.get(f"{BASE_URL}/api/v4/twitter/runtime/selection")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is True
        assert "selection" in data
        
        selection = data["selection"]
        assert "account" in selection
        assert "session" in selection
        assert selection["mode"] == "AUTO"
        
        # Verify account structure
        assert "id" in selection["account"]
        assert "username" in selection["account"]
        assert "isPreferred" in selection["account"]
        
        # Verify session structure
        assert "id" in selection["session"]
        assert "version" in selection["session"]
        assert "status" in selection["session"]
        assert "riskScore" in selection["session"]
        
        # Verify scrollProfileHint is present
        assert "scrollProfileHint" in selection
        assert selection["scrollProfileHint"] in ["SAFE", "NORMAL", "AGGRESSIVE"]

    def test_selection_preview_manual_mode_no_preferred(self, api_client):
        """MANUAL mode without preferred account falls back to AUTO behavior"""
        response = api_client.get(
            f"{BASE_URL}/api/v4/twitter/runtime/selection",
            params={"mode": "MANUAL"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is True
        assert data["selection"]["mode"] == "MANUAL"
        # Without preferred, should still return a valid selection
        assert data["selection"]["account"]["isPreferred"] is False

    def test_selection_preview_manual_mode_with_preferred(self, api_client):
        """MANUAL mode with preferred account returns that account"""
        # Set preferred account first
        api_client.post(f"{BASE_URL}/api/v4/twitter/accounts/{ACCOUNT_2_ID}/preferred")
        
        response = api_client.get(
            f"{BASE_URL}/api/v4/twitter/runtime/selection",
            params={"mode": "MANUAL"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is True
        assert data["selection"]["mode"] == "MANUAL"
        assert data["selection"]["account"]["id"] == ACCOUNT_2_ID
        assert data["selection"]["account"]["isPreferred"] is True
        
        # Cleanup
        api_client.delete(f"{BASE_URL}/api/v4/twitter/accounts/preferred")


class TestRuntimeSelectionFull:
    """Tests for GET /api/v4/twitter/runtime/selection/full (with cookies)"""

    def test_selection_full_returns_cookies(self, api_client):
        """Full selection returns decrypted cookies"""
        response = api_client.get(f"{BASE_URL}/api/v4/twitter/runtime/selection/full")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is True
        assert "config" in data
        assert "meta" in data
        
        config = data["config"]
        assert "ownerUserId" in config
        assert "accountId" in config
        assert "sessionId" in config
        assert "cookies" in config
        assert "userAgent" in config
        assert "scrollProfileHint" in config
        
        # Verify cookies is a list
        assert isinstance(config["cookies"], list)
        assert len(config["cookies"]) > 0
        
        # Verify cookie structure
        for cookie in config["cookies"]:
            assert "name" in cookie
            assert "value" in cookie

    def test_selection_full_with_specific_account(self, api_client):
        """Full selection with accountId parameter returns that account"""
        response = api_client.get(
            f"{BASE_URL}/api/v4/twitter/runtime/selection/full",
            params={"accountId": ACCOUNT_2_ID}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is True
        assert data["config"]["accountId"] == ACCOUNT_2_ID
        assert data["meta"]["chosenAccount"]["id"] == ACCOUNT_2_ID

    def test_selection_full_require_proxy_no_proxy_available(self, api_client):
        """Full selection with requireProxy=true returns error when no proxy"""
        response = api_client.get(
            f"{BASE_URL}/api/v4/twitter/runtime/selection/full",
            params={"requireProxy": "true"}
        )
        
        assert response.status_code == 400
        data = response.json()
        
        assert data["ok"] is False
        assert data["reason"] == "NO_PROXY_AVAILABLE"

    def test_selection_full_meta_structure(self, api_client):
        """Full selection meta contains all required fields"""
        response = api_client.get(f"{BASE_URL}/api/v4/twitter/runtime/selection/full")
        
        assert response.status_code == 200
        data = response.json()
        
        meta = data["meta"]
        assert "mode" in meta
        assert "chosenAccount" in meta
        assert "session" in meta
        assert "alternativeAccounts" in meta
        
        # Verify chosenAccount structure
        assert "id" in meta["chosenAccount"]
        assert "username" in meta["chosenAccount"]
        assert "isPreferred" in meta["chosenAccount"]
        
        # Verify session structure
        assert "id" in meta["session"]
        assert "version" in meta["session"]
        assert "status" in meta["session"]
        assert "riskScore" in meta["session"]


class TestRuntimeCandidates:
    """Tests for GET /api/v4/twitter/runtime/candidates"""

    def test_candidates_returns_all_accounts(self, api_client):
        """Candidates endpoint returns all enabled accounts with sessions"""
        response = api_client.get(f"{BASE_URL}/api/v4/twitter/runtime/candidates")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is True
        assert "data" in data
        assert "candidates" in data["data"]
        assert "stats" in data["data"]
        
        candidates = data["data"]["candidates"]
        assert len(candidates) >= 2  # At least 2 test accounts
        
        # Verify candidate structure
        for candidate in candidates:
            assert "account" in candidate
            assert "session" in candidate
            assert "canParse" in candidate
            
            account = candidate["account"]
            assert "id" in account
            assert "username" in account
            assert "isPreferred" in account
            assert "priority" in account

    def test_candidates_stats_structure(self, api_client):
        """Candidates stats contains all required fields"""
        response = api_client.get(f"{BASE_URL}/api/v4/twitter/runtime/candidates")
        
        assert response.status_code == 200
        data = response.json()
        
        stats = data["data"]["stats"]
        assert "total" in stats
        assert "canParse" in stats
        assert "withOkSession" in stats
        assert "withPreferred" in stats
        
        # Verify stats are integers
        assert isinstance(stats["total"], int)
        assert isinstance(stats["canParse"], int)
        assert isinstance(stats["withOkSession"], int)
        assert isinstance(stats["withPreferred"], int)

    def test_candidates_sorted_by_preferred_first(self, api_client):
        """Candidates are sorted with preferred account first"""
        # Set preferred account
        api_client.post(f"{BASE_URL}/api/v4/twitter/accounts/{ACCOUNT_2_ID}/preferred")
        
        response = api_client.get(f"{BASE_URL}/api/v4/twitter/runtime/candidates")
        
        assert response.status_code == 200
        data = response.json()
        
        candidates = data["data"]["candidates"]
        # First candidate should be the preferred one
        assert candidates[0]["account"]["id"] == ACCOUNT_2_ID
        assert candidates[0]["account"]["isPreferred"] is True
        
        # Cleanup
        api_client.delete(f"{BASE_URL}/api/v4/twitter/accounts/preferred")


class TestPreferredAccountManagement:
    """Tests for preferred account CRUD operations"""

    @pytest.fixture(autouse=True)
    def cleanup_after_test(self, api_client):
        """Cleanup preferred account after each test in this class"""
        yield
        api_client.delete(f"{BASE_URL}/api/v4/twitter/accounts/preferred")

    def test_get_preferred_no_preferred_set(self, api_client):
        """Get preferred returns AUTO mode when no preferred set"""
        # First ensure no preferred is set
        api_client.delete(f"{BASE_URL}/api/v4/twitter/accounts/preferred")
        
        response = api_client.get(f"{BASE_URL}/api/v4/twitter/accounts/preferred")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is True
        assert data["mode"] == "AUTO"
        assert data["preferred"] is None

    def test_set_preferred_account(self, api_client):
        """Set preferred account returns success"""
        response = api_client.post(
            f"{BASE_URL}/api/v4/twitter/accounts/{ACCOUNT_1_ID}/preferred"
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is True
        assert "message" in data
        assert data["accountId"] == ACCOUNT_1_ID

    def test_get_preferred_after_set(self, api_client):
        """Get preferred returns MANUAL mode after setting preferred"""
        # Set preferred
        api_client.post(f"{BASE_URL}/api/v4/twitter/accounts/{ACCOUNT_1_ID}/preferred")
        
        response = api_client.get(f"{BASE_URL}/api/v4/twitter/accounts/preferred")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is True
        assert data["mode"] == "MANUAL"
        assert data["preferred"] is not None
        assert data["preferred"]["id"] == ACCOUNT_1_ID
        assert "username" in data["preferred"]

    def test_set_preferred_replaces_previous(self, api_client):
        """Setting new preferred replaces the previous one"""
        # Set first preferred
        api_client.post(f"{BASE_URL}/api/v4/twitter/accounts/{ACCOUNT_1_ID}/preferred")
        
        # Set second preferred
        api_client.post(f"{BASE_URL}/api/v4/twitter/accounts/{ACCOUNT_2_ID}/preferred")
        
        response = api_client.get(f"{BASE_URL}/api/v4/twitter/accounts/preferred")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["preferred"]["id"] == ACCOUNT_2_ID

    def test_set_preferred_non_existent_account(self, api_client):
        """Setting preferred for non-existent account returns 404"""
        response = api_client.post(
            f"{BASE_URL}/api/v4/twitter/accounts/{NON_EXISTENT_ACCOUNT}/preferred"
        )
        
        assert response.status_code == 404
        data = response.json()
        
        assert data["ok"] is False
        assert "error" in data

    def test_clear_preferred_via_delete(self, api_client):
        """DELETE /api/v4/twitter/accounts/preferred clears preferred"""
        # Set preferred first
        api_client.post(f"{BASE_URL}/api/v4/twitter/accounts/{ACCOUNT_1_ID}/preferred")
        
        # Clear via DELETE
        response = api_client.delete(f"{BASE_URL}/api/v4/twitter/accounts/preferred")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is True
        assert "message" in data
        
        # Verify cleared
        get_response = api_client.get(f"{BASE_URL}/api/v4/twitter/accounts/preferred")
        assert get_response.json()["mode"] == "AUTO"
        assert get_response.json()["preferred"] is None

    def test_clear_preferred_via_post_with_false(self, api_client):
        """POST with isPreferred=false clears preferred"""
        # Set preferred first
        api_client.post(f"{BASE_URL}/api/v4/twitter/accounts/{ACCOUNT_1_ID}/preferred")
        
        # Clear via POST with isPreferred=false
        response = api_client.post(
            f"{BASE_URL}/api/v4/twitter/accounts/{ACCOUNT_1_ID}/preferred",
            json={"isPreferred": False}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["ok"] is True
        
        # Verify cleared
        get_response = api_client.get(f"{BASE_URL}/api/v4/twitter/accounts/preferred")
        assert get_response.json()["mode"] == "AUTO"


class TestScrollProfileHint:
    """Tests for scrollProfileHint generation"""

    def test_scroll_profile_hint_values(self, api_client):
        """scrollProfileHint is one of SAFE, NORMAL, AGGRESSIVE"""
        response = api_client.get(f"{BASE_URL}/api/v4/twitter/runtime/selection")
        
        assert response.status_code == 200
        data = response.json()
        
        hint = data["selection"]["scrollProfileHint"]
        assert hint in ["SAFE", "NORMAL", "AGGRESSIVE"]

    def test_scroll_profile_hint_in_full_config(self, api_client):
        """scrollProfileHint is present in full config"""
        response = api_client.get(f"{BASE_URL}/api/v4/twitter/runtime/selection/full")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "scrollProfileHint" in data["config"]
        assert data["config"]["scrollProfileHint"] in ["SAFE", "NORMAL", "AGGRESSIVE"]


class TestSelectionRanking:
    """Tests for selection ranking algorithm"""

    def test_auto_mode_selects_best_session(self, api_client):
        """AUTO mode selects account with best session (OK status, low riskScore)"""
        response = api_client.get(f"{BASE_URL}/api/v4/twitter/runtime/selection")
        
        assert response.status_code == 200
        data = response.json()
        
        # Should select account with OK status
        assert data["selection"]["session"]["status"] == "OK"

    def test_manual_mode_prefers_preferred_account(self, api_client):
        """MANUAL mode prefers the preferred account even if not best ranked"""
        # Set account 2 as preferred
        api_client.post(f"{BASE_URL}/api/v4/twitter/accounts/{ACCOUNT_2_ID}/preferred")
        
        response = api_client.get(
            f"{BASE_URL}/api/v4/twitter/runtime/selection",
            params={"mode": "MANUAL"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should select the preferred account
        assert data["selection"]["account"]["id"] == ACCOUNT_2_ID
        assert data["selection"]["account"]["isPreferred"] is True
        
        # Cleanup
        api_client.delete(f"{BASE_URL}/api/v4/twitter/accounts/preferred")


class TestSelectionReasons:
    """Tests for selection failure reasons"""

    def test_no_proxy_available_reason(self, api_client):
        """NO_PROXY_AVAILABLE reason when requireProxy=true and no proxy"""
        response = api_client.get(
            f"{BASE_URL}/api/v4/twitter/runtime/selection/full",
            params={"requireProxy": "true"}
        )
        
        assert response.status_code == 400
        data = response.json()
        
        assert data["ok"] is False
        assert data["reason"] == "NO_PROXY_AVAILABLE"


class TestIntegrationFlow:
    """Integration tests for complete selection flow"""

    @pytest.fixture(autouse=True)
    def cleanup_before_and_after(self, api_client):
        """Cleanup preferred account before and after each test"""
        api_client.delete(f"{BASE_URL}/api/v4/twitter/accounts/preferred")
        yield
        api_client.delete(f"{BASE_URL}/api/v4/twitter/accounts/preferred")

    def test_full_manual_mode_flow(self, api_client):
        """Complete flow: set preferred -> select MANUAL -> verify -> clear"""
        # Step 1: Verify initial state is AUTO
        initial = api_client.get(f"{BASE_URL}/api/v4/twitter/accounts/preferred")
        assert initial.json()["mode"] == "AUTO"
        
        # Step 2: Set preferred account
        set_response = api_client.post(
            f"{BASE_URL}/api/v4/twitter/accounts/{ACCOUNT_2_ID}/preferred"
        )
        assert set_response.json()["ok"] is True
        
        # Step 3: Verify preferred is set
        preferred = api_client.get(f"{BASE_URL}/api/v4/twitter/accounts/preferred")
        assert preferred.json()["mode"] == "MANUAL"
        assert preferred.json()["preferred"]["id"] == ACCOUNT_2_ID
        
        # Step 4: Selection in MANUAL mode returns preferred
        selection = api_client.get(
            f"{BASE_URL}/api/v4/twitter/runtime/selection",
            params={"mode": "MANUAL"}
        )
        assert selection.json()["selection"]["account"]["id"] == ACCOUNT_2_ID
        
        # Step 5: Full selection also returns preferred
        full = api_client.get(
            f"{BASE_URL}/api/v4/twitter/runtime/selection/full",
            params={"mode": "MANUAL"}
        )
        assert full.json()["config"]["accountId"] == ACCOUNT_2_ID
        
        # Step 6: Clear preferred
        clear = api_client.delete(f"{BASE_URL}/api/v4/twitter/accounts/preferred")
        assert clear.json()["ok"] is True
        
        # Step 7: Verify back to AUTO
        final = api_client.get(f"{BASE_URL}/api/v4/twitter/accounts/preferred")
        assert final.json()["mode"] == "AUTO"

    def test_candidates_reflect_preferred_changes(self, api_client):
        """Candidates endpoint reflects preferred account changes"""
        # Initial: no preferred
        initial = api_client.get(f"{BASE_URL}/api/v4/twitter/runtime/candidates")
        initial_stats = initial.json()["data"]["stats"]
        assert initial_stats["withPreferred"] == 0
        
        # Set preferred
        api_client.post(f"{BASE_URL}/api/v4/twitter/accounts/{ACCOUNT_1_ID}/preferred")
        
        # After: one preferred
        after = api_client.get(f"{BASE_URL}/api/v4/twitter/runtime/candidates")
        after_stats = after.json()["data"]["stats"]
        assert after_stats["withPreferred"] == 1
        
        # Find preferred in candidates
        candidates = after.json()["data"]["candidates"]
        preferred_candidate = next(
            (c for c in candidates if c["account"]["id"] == ACCOUNT_1_ID), 
            None
        )
        assert preferred_candidate is not None
        assert preferred_candidate["account"]["isPreferred"] is True
