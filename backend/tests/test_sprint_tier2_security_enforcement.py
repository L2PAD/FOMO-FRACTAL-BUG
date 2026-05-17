"""Sprint TIER-2 — Backend Capability Enforcement tests.

Acceptance:
  * curl without auth → 401 across the trading & broker surface
  * authenticated user without operator capability → 403 (explicit
    `required` + `granted` lists in response body)
  * dev_user (seeded approved+paper) → 200 on paper-tier endpoints
  * dev_user → 403 on live-only endpoints (no live grant)
  * frontend visibility never counts as security:
        backend enforces independently of any client state
"""
import os
import pytest
import requests


BASE_URL = (os.environ.get("EXPO_PUBLIC_BACKEND_URL")
            or "https://merge-verify-4.preview.emergentagent.com").rstrip("/")


# Endpoints grouped by required capability:
ENDPOINTS_AUTH_REQUIRED = [
    ("GET", "/api/trading/verdict/BTC"),
    ("GET", "/api/trading/opportunities?symbols=BTC"),
    ("GET", "/api/trading/intelligence/calibration?symbol=BTC"),
]
ENDPOINTS_TRADING_OS_VISIBLE = [
    ("GET", "/api/trading/runtime/status"),
    ("GET", "/api/broker/status"),
    ("GET", "/api/broker/heartbeat"),
    ("GET", "/api/broker/balances"),
    ("GET", "/api/broker/markets"),
]
ENDPOINTS_EXECUTION_CONSOLE = [
    ("GET", "/api/trading/paper/scheduler/status"),
    ("GET", "/api/broker/audit?limit=5"),
]
ENDPOINTS_PAPER_TRADING_READ = [
    ("GET", "/api/trading/paper/account"),
    ("GET", "/api/trading/paper/positions?status=OPEN"),
    ("GET", "/api/trading/paper/orders?limit=5"),
    ("GET", "/api/trading/paper/events?limit=5"),
]
ENDPOINTS_PAPER_TRADING_POST = [
    ("POST", "/api/trading/paper/evaluate-hits", {}),
]
ENDPOINTS_LIVE_TRADING = [
    ("POST", "/api/broker/live/submit", {"symbol": "BTC", "action": "LONG", "sizeUsd": 500}),
]


def _call(method, path, headers=None, body=None):
    url = f"{BASE_URL}{path}"
    if method == "GET":
        return requests.get(url, headers=headers or {}, timeout=15)
    return requests.post(url, json=body or {}, headers={**(headers or {}), "Content-Type": "application/json"}, timeout=15)


# ── 401 anonymous ────────────────────────────────────────────────────


class TestAnonymousReturns401:
    @pytest.mark.parametrize("method,path", ENDPOINTS_AUTH_REQUIRED + ENDPOINTS_TRADING_OS_VISIBLE + ENDPOINTS_EXECUTION_CONSOLE + ENDPOINTS_PAPER_TRADING_READ)
    def test_get_anon_401(self, method, path):
        r = _call(method, path)
        assert r.status_code == 401, f"{path} → {r.status_code}"
        body = r.json()
        # Body wrapped under FastAPI 'detail'
        detail = body.get("detail") or body
        assert detail.get("error") == "authentication_required", body

    @pytest.mark.parametrize("method,path,body", ENDPOINTS_PAPER_TRADING_POST + ENDPOINTS_LIVE_TRADING)
    def test_post_anon_401(self, method, path, body):
        r = _call(method, path, body=body)
        assert r.status_code == 401, f"{path} → {r.status_code}"


# ── 403 free user (auth present but no operator capability) ──────────


FREE_HEADERS = {"X-User-Id": "tier2_free_user_xyz_abc"}


class TestFreeUserReturns403:
    @pytest.mark.parametrize("method,path", ENDPOINTS_TRADING_OS_VISIBLE + ENDPOINTS_EXECUTION_CONSOLE + ENDPOINTS_PAPER_TRADING_READ)
    def test_free_user_blocked(self, method, path):
        r = _call(method, path, headers=FREE_HEADERS)
        assert r.status_code == 403, f"{path} → {r.status_code}: {r.text[:200]}"
        detail = (r.json().get("detail") or r.json())
        assert detail.get("error") == "capability_required"
        assert isinstance(detail.get("required"), list) and len(detail["required"]) >= 1
        assert "granted" in detail  # explicit transparency
        assert detail.get("tier") == "free"

    def test_free_user_can_still_read_verdict_no_extra_cap_needed(self):
        # /verdict is "authenticated" only — any authed user passes.
        r = _call("GET", "/api/trading/verdict/BTC", headers=FREE_HEADERS)
        assert r.status_code == 200, r.text[:200]

    @pytest.mark.parametrize("method,path,body", ENDPOINTS_LIVE_TRADING)
    def test_free_user_blocked_on_live_submit(self, method, path, body):
        r = _call(method, path, headers=FREE_HEADERS, body=body)
        assert r.status_code == 403


# ── 200 dev_user (seeded approved+paper) ─────────────────────────────


DEV_HEADERS = {"X-User-Id": "dev_user"}


class TestDevUserAllowedOnPaperTier:
    @pytest.mark.parametrize("method,path", ENDPOINTS_AUTH_REQUIRED + ENDPOINTS_TRADING_OS_VISIBLE + ENDPOINTS_EXECUTION_CONSOLE + ENDPOINTS_PAPER_TRADING_READ)
    def test_dev_user_200(self, method, path):
        r = _call(method, path, headers=DEV_HEADERS)
        assert r.status_code == 200, f"{path} → {r.status_code}: {r.text[:200]}"

    @pytest.mark.parametrize("method,path,body", ENDPOINTS_PAPER_TRADING_POST)
    def test_dev_user_paper_post_200(self, method, path, body):
        r = _call(method, path, headers=DEV_HEADERS, body=body)
        assert r.status_code == 200, r.text[:200]


# ── dev_user still blocked on live (no live grant) ───────────────────


class TestDevUserBlockedOnLive:
    """dev_user is seeded with mode='paper'. Live endpoints must refuse."""

    @pytest.mark.parametrize("method,path,body", ENDPOINTS_LIVE_TRADING)
    def test_dev_user_403_on_live(self, method, path, body):
        r = _call(method, path, headers=DEV_HEADERS, body=body)
        assert r.status_code == 403, f"expected 403 got {r.status_code}: {r.text[:200]}"
        detail = (r.json().get("detail") or r.json())
        assert detail.get("error") == "capability_required"
        assert "liveTrading" in detail.get("required", [])
        assert "paperTrading" in detail.get("granted", []), (
            f"dev_user should have paperTrading granted: {detail.get('granted')}"
        )


# ── Error response shape contract ────────────────────────────────────


class TestErrorShape:
    def test_401_shape(self):
        r = _call("GET", "/api/trading/runtime/status")
        assert r.status_code == 401
        body = r.json()
        detail = body.get("detail") or body
        assert detail.get("error") == "authentication_required"
        assert "hint" in detail

    def test_403_shape(self):
        r = _call("GET", "/api/broker/status", headers=FREE_HEADERS)
        assert r.status_code == 403
        body = r.json()
        detail = body.get("detail") or body
        for k in ("error", "required", "granted", "tier", "userId", "hint"):
            assert k in detail, f"missing {k} in error body: {detail}"
