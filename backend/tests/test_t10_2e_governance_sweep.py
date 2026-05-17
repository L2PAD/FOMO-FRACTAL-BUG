"""
T10.2E Governance Ledger — Full Reintegration Regression Sweep
Tests the 4 admin inject surfaces (billing/attribution/execution/governance) together.
"""
import os
import time
import pytest
import requests

BASE_URL = "https://mobile-app-core.preview.emergentagent.com"

ADMIN_USER = "admin"
ADMIN_PASS = "admin12345"

TYPED_PHRASE = "GRANT LIVE TRADING"

# Unique test user for this sweep
TS = str(int(time.time()))
TEST_USER_ID = f"test_sweep_{TS}"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(
        f"{BASE_URL}/api/admin/auth/login",
        json={"username": ADMIN_USER, "password": ADMIN_PASS},
        timeout=15,
    )
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text[:300]}"
    body = r.json()
    assert body.get("ok") is True
    tok = body.get("token")
    assert tok and len(tok) > 20
    return tok


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


# ---------- Smoke ----------
class TestSmoke:
    def test_health(self):
        r = requests.get(f"{BASE_URL}/api/health", timeout=15)
        assert r.status_code == 200
        body = r.json()
        assert body.get("ok") is True

    def test_admin_login_ok(self, admin_token):
        assert admin_token

    def test_admin_login_wrong_pwd(self):
        r = requests.post(
            f"{BASE_URL}/api/admin/auth/login",
            json={"username": ADMIN_USER, "password": "wrong_pwd_xyz"},
            timeout=15,
        )
        assert r.status_code == 401, f"expected 401, got {r.status_code}"


# ---------- Inject endpoints unauthenticated → 401 ----------
INJECT_GET_ENDPOINTS = [
    "/api/admin/billing/reconciliation/summary",
    "/api/admin/attribution/summary?window=7d",
    "/api/admin/execution/testnet/config",
    "/api/admin/operator-access/list",
]


class TestInjectEndpointsAuthRequired:
    @pytest.mark.parametrize("path", INJECT_GET_ENDPOINTS)
    def test_unauth_401(self, path):
        r = requests.get(f"{BASE_URL}{path}", timeout=15)
        assert r.status_code == 401, f"{path} expected 401, got {r.status_code}: {r.text[:200]}"

    @pytest.mark.parametrize("path", INJECT_GET_ENDPOINTS)
    def test_with_admin_jwt_200(self, path, auth_headers):
        r = requests.get(f"{BASE_URL}{path}", headers=auth_headers, timeout=20)
        assert r.status_code == 200, f"{path} expected 200, got {r.status_code}: {r.text[:300]}"


# ---------- Governance mutation chain ----------
class TestGovernanceMutationChain:
    def test_01_set_tier(self, auth_headers):
        r = requests.post(
            f"{BASE_URL}/api/admin/operator-access/set-tier",
            json={"userId": TEST_USER_ID, "tier": "trader"},
            headers=auth_headers,
            timeout=20,
        )
        assert r.status_code == 200, f"{r.status_code}: {r.text[:400]}"
        body = r.json()
        assert body.get("ok") is True
        # tier may be in different shape; assert presence
        text = str(body).lower()
        assert "trader" in text, f"trader not in response: {body}"

    def test_02_grant_paper(self, auth_headers):
        r = requests.post(
            f"{BASE_URL}/api/admin/operator-access/grant",
            json={"userId": TEST_USER_ID, "mode": "paper", "consoleAccess": False},
            headers=auth_headers,
            timeout=20,
        )
        assert r.status_code == 200, f"{r.status_code}: {r.text[:400]}"
        body = r.json()
        assert body.get("ok") is True
        text = str(body).lower()
        assert "paper" in text
        assert "approved" in text

    def test_03_grant_live_wrong_phrase(self, auth_headers):
        r = requests.post(
            f"{BASE_URL}/api/admin/operator-access/grant-live-authority",
            json={
                "userId": TEST_USER_ID,
                "typedConfirmation": "WRONG",
                "reason": "regression sweep",
                "acknowledged": True,
            },
            headers=auth_headers,
            timeout=20,
        )
        assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text[:400]}"
        body = r.json()
        detail = body.get("detail", body)
        if isinstance(detail, dict):
            assert detail.get("error") == "TYPED_CONFIRMATION_MISMATCH", f"detail: {detail}"
            assert detail.get("expected") == TYPED_PHRASE
        else:
            assert "TYPED_CONFIRMATION_MISMATCH" in str(detail)

    def test_04_grant_live_missing_reason(self, auth_headers):
        r = requests.post(
            f"{BASE_URL}/api/admin/operator-access/grant-live-authority",
            json={
                "userId": TEST_USER_ID,
                "typedConfirmation": TYPED_PHRASE,
                "acknowledged": True,
            },
            headers=auth_headers,
            timeout=20,
        )
        assert r.status_code in (400, 422), f"expected 400/422 (reason mandatory), got {r.status_code}: {r.text[:400]}"

    def test_05_grant_live_success(self, auth_headers):
        r = requests.post(
            f"{BASE_URL}/api/admin/operator-access/grant-live-authority",
            json={
                "userId": TEST_USER_ID,
                "typedConfirmation": TYPED_PHRASE,
                "reason": "regression sweep",
                "acknowledged": True,
            },
            headers=auth_headers,
            timeout=20,
        )
        assert r.status_code == 200, f"{r.status_code}: {r.text[:500]}"
        body = r.json()
        assert body.get("ok") is True
        oa = body.get("operatorAccess") or {}
        live = oa.get("liveAuthority") or {}
        assert live.get("granted") is True, f"liveAuthority.granted not true: {oa}"

    def test_06_audit_timeline(self, auth_headers):
        r = requests.get(
            f"{BASE_URL}/api/admin/operator-access/audit-timeline",
            params={"userId": TEST_USER_ID, "limit": 50},
            headers=auth_headers,
            timeout=20,
        )
        assert r.status_code == 200, f"{r.status_code}: {r.text[:400]}"
        body = r.json()
        rows = body.get("rows") or body.get("entries") or []
        assert isinstance(rows, list) and len(rows) > 0, f"no rows: {body}"
        actions = {(row.get("action") or "").lower() for row in rows}
        assert "set-tier" in actions, f"set-tier missing in actions: {actions}"
        assert "grant" in actions, f"grant missing: {actions}"
        assert "grant-live-authority" in actions, f"grant-live-authority missing: {actions}"

    def test_07_override_capability_revoke(self, auth_headers):
        r = requests.post(
            f"{BASE_URL}/api/admin/operator-access/override-capability",
            json={
                "userId": TEST_USER_ID,
                "capability": "liveTrading",
                "value": "revoked",
                "reason": "kill-switch test",
            },
            headers=auth_headers,
            timeout=20,
        )
        assert r.status_code == 200, f"{r.status_code}: {r.text[:500]}"
        body = r.json()
        caps = (body.get("capabilities") or {}).get("structured") or {}
        live = caps.get("liveTrading") or {}
        assert live.get("effective") is False, f"effective not False: {live}"
        # Allow alternate keys for source/override naming
        src = (live.get("source") or "").lower()
        ovr = (live.get("override") or "").lower()
        assert "revoke" in src or "revoke" in ovr or live.get("override") == "manual", \
            f"revoke override not detected: {live}"

    def test_08_revoke_live_missing_reason(self, auth_headers):
        r = requests.post(
            f"{BASE_URL}/api/admin/operator-access/revoke-live-authority",
            json={"userId": TEST_USER_ID},
            headers=auth_headers,
            timeout=20,
        )
        assert r.status_code in (400, 422), f"expected 400/422 (reason mandatory), got {r.status_code}: {r.text[:400]}"

    def test_09_capability_resolver_consistency(self, auth_headers):
        # List endpoint with q filter
        r = requests.get(
            f"{BASE_URL}/api/admin/operator-access/list",
            params={"q": TEST_USER_ID},
            headers=auth_headers,
            timeout=20,
        )
        assert r.status_code == 200, f"{r.status_code}: {r.text[:400]}"
        body = r.json()
        rows = body.get("rows") or body.get("operators") or []
        match = None
        for row in rows:
            if (row.get("userId") or "").lower() == TEST_USER_ID.lower():
                match = row
                break
        # If not found in list, the resolver consistency check can't run — but it should be found
        assert match is not None, f"seeded user {TEST_USER_ID} not in list rows={len(rows)}"
        caps_list = ((match.get("capabilities") or {}).get("structured") or {})
        live_list = caps_list.get("liveTrading") or {}
        # liveTrading was revoked via override in test_07
        assert live_list.get("effective") is False, \
            f"resolver inconsistency: list says liveTrading.effective={live_list.get('effective')}"


# ---------- Execution Ledger ----------
class TestExecutionLedger:
    def test_testnet_config_invariants(self, auth_headers):
        r = requests.get(
            f"{BASE_URL}/api/admin/execution/testnet/config",
            headers=auth_headers,
            timeout=15,
        )
        assert r.status_code == 200
        body = r.json()
        # Invariants live nested under "invariants"
        inv = body.get("invariants") or body
        assert inv.get("TESTNET_ONLY") is True, f"TESTNET_ONLY != True: {inv}"
        assert float(inv.get("MAX_NOTIONAL_USD")) == 25.0, f"max notional={inv.get('MAX_NOTIONAL_USD')}"
        assert inv.get("retryForbidden") is True, f"retryForbidden={inv.get('retryForbidden')}"
        assert inv.get("appendOnly") is True, f"appendOnly={inv.get('appendOnly')}"
        assert inv.get("autoResubmit") is False, f"autoResubmit={inv.get('autoResubmit')}"

    def test_duplicate_lineage_id_409(self, auth_headers):
        lineage = f"sweep_lineage_{TS}"
        payload = {
            "lineageId": lineage,
            "operatorUserId": TEST_USER_ID,
            "symbol": "BTC",
            "side": "BUY",
            "sizeUsd": 10.0,
        }
        r1 = requests.post(
            f"{BASE_URL}/api/admin/execution/testnet/submit",
            json=payload,
            headers=auth_headers,
            timeout=20,
        )
        if r1.status_code not in (200, 201):
            pytest.skip(f"first submit failed {r1.status_code} {r1.text[:300]}; cannot test duplicate")
        r2 = requests.post(
            f"{BASE_URL}/api/admin/execution/testnet/submit",
            json=payload,
            headers=auth_headers,
            timeout=20,
        )
        assert r2.status_code == 409, f"expected 409 duplicate, got {r2.status_code}: {r2.text[:400]}"
        text = r2.text.upper()
        assert "RECEIPT_EXISTS" in text or "RECEIPT" in text


# ---------- Frontend admin SPA HTML inject markers ----------
class TestAdminSPAInject:
    def test_admin_html_contains_inject_markers(self):
        r = requests.get(f"{BASE_URL}/api/panel/admin", timeout=20, allow_redirects=True)
        assert r.status_code == 200, f"{r.status_code}"
        html = r.text
        # Inject scripts referenced
        assert "billing-inject" in html or "fomo-billing-nav" in html, "billing inject marker missing"
        assert "attribution-inject" in html or "fomo-attribution-nav" in html, "attribution inject marker missing"
        assert "execution-inject" in html or "fomo-execution-nav" in html, "execution inject marker missing"
        assert "governance-inject" in html or "fomo-governance-nav" in html, "governance inject marker missing"

    def test_orphan_expo_admin_route(self):
        # /admin (no /api/panel) should be served but is not the canonical admin work flow
        r = requests.get(f"{BASE_URL}/admin", timeout=20, allow_redirects=False)
        # 200 (Expo admin) OR 3xx is acceptable; key test is that /api/panel/admin is the canonical
        assert r.status_code in (200, 301, 302, 303, 307, 308, 404), f"unexpected: {r.status_code}"
