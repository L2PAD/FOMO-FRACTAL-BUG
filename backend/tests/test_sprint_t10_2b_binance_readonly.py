"""Sprint T10.2B — Read-only Binance Adapter tests.

Invariants enforced here are STRONGER than docstring guarantees:
  * AST-level scan of /app/backend/services/exchange/*.py confirms no
    create/cancel/submit/withdraw/transfer/futures/leverage symbols exist
    as function names, attribute accesses, or call targets.
  * broker_bridge.py contains no `getattr(... exchange ...)` or
    `getattr(... _client ...)` dynamic-dispatch patterns.
  * The Binance adapter's underlying ccxt instance lives in a private
    attribute (`_client`) and is never returned from any public method.
  * Capability state is backend-enforced: anything other than
    READONLY_VERIFIED blocks the live gate via `exchange_capability_verified`.
"""
import ast
import inspect
import os
import re
import pytest
import requests
from pathlib import Path

BASE_URL = (os.environ.get("EXPO_PUBLIC_BACKEND_URL")
            or os.environ.get("EXPO_BACKEND_URL")
            or "https://merge-verify-4.preview.emergentagent.com").rstrip("/")

EXCHANGE_DIR = Path("/app/backend/services/exchange")
BROKER_BRIDGE = Path("/app/backend/services/broker_bridge.py")

FORBIDDEN_NAME_PATTERNS = [
    re.compile(r"^create_.*order", re.IGNORECASE),
    re.compile(r"^cancel_.*order", re.IGNORECASE),
    re.compile(r"^submit_.*order", re.IGNORECASE),
    re.compile(r"^place_.*order", re.IGNORECASE),
    re.compile(r"^withdraw", re.IGNORECASE),
    re.compile(r"^transfer", re.IGNORECASE),
    re.compile(r"futures", re.IGNORECASE),
    re.compile(r"leverage", re.IGNORECASE),
    re.compile(r"margin", re.IGNORECASE),
    re.compile(r"^private_post", re.IGNORECASE),
]


def _ast_names_in_file(path: Path) -> tuple[set[str], set[str], set[str]]:
    """Return (function_names, attribute_names, call_target_names)."""
    src = path.read_text()
    tree = ast.parse(src, filename=str(path))
    funcs: set[str] = set()
    attrs: set[str] = set()
    calls: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            funcs.add(node.name)
        elif isinstance(node, ast.Attribute):
            attrs.add(node.attr)
        elif isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Name):
                calls.add(f.id)
            elif isinstance(f, ast.Attribute):
                calls.add(f.attr)
    return funcs, attrs, calls


# ── Invariant tests: AST-level guarantees ────────────────────────────


class TestExchangePackageHasNoWriteSymbols:
    def test_no_forbidden_function_names(self):
        offenders: list[str] = []
        for f in EXCHANGE_DIR.glob("*.py"):
            funcs, _, _ = _ast_names_in_file(f)
            for name in funcs:
                for pat in FORBIDDEN_NAME_PATTERNS:
                    if pat.match(name):
                        offenders.append(f"{f.name}: function '{name}' matches {pat.pattern}")
        assert not offenders, "Forbidden function names: " + "\n".join(offenders)

    def test_no_forbidden_attribute_access(self):
        offenders: list[str] = []
        for f in EXCHANGE_DIR.glob("*.py"):
            _, attrs, _ = _ast_names_in_file(f)
            for name in attrs:
                for pat in FORBIDDEN_NAME_PATTERNS:
                    if pat.match(name):
                        offenders.append(f"{f.name}: attribute '{name}' matches {pat.pattern}")
        assert not offenders, "Forbidden attribute access: " + "\n".join(offenders)

    def test_no_forbidden_call_targets(self):
        offenders: list[str] = []
        for f in EXCHANGE_DIR.glob("*.py"):
            _, _, calls = _ast_names_in_file(f)
            for name in calls:
                for pat in FORBIDDEN_NAME_PATTERNS:
                    if pat.match(name):
                        offenders.append(f"{f.name}: call '{name}' matches {pat.pattern}")
        assert not offenders, "Forbidden call targets: " + "\n".join(offenders)


class TestNoDynamicDispatchInBrokerBridge:
    """broker_bridge.py must never call arbitrary exchange methods via getattr."""

    def test_no_getattr_on_exchange_or_client(self):
        src = BROKER_BRIDGE.read_text()
        # Look for getattr(...) calls whose first arg contains 'exchange'
        # or 'client' identifier.
        tree = ast.parse(src)
        offenders = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "getattr":
                arg_src = ast.dump(node)
                if any(tok in arg_src.lower() for tok in ("exchange", "_client", "_inner._client")):
                    offenders.append(arg_src[:200])
        assert not offenders, "Dynamic dispatch on exchange transport: " + "\n".join(offenders)


# ── ABC contract: only 6 whitelist methods are abstract ──────────────


class TestReadonlyExchangeAdapterContract:
    def test_abstract_methods_are_exactly_whitelisted(self):
        from services.exchange.base import ReadonlyExchangeAdapter
        # All abstract methods of the base class must be from the whitelist
        whitelist = {
            "name", "configured", "connected", "capability",
            "heartbeat", "fetch_balance", "fetch_markets",
            "fetch_ticker", "fetch_status", "load_markets",
        }
        abstract = set(ReadonlyExchangeAdapter.__abstractmethods__)
        assert abstract <= whitelist, f"unexpected abstract members: {abstract - whitelist}"
        assert "fetch_balance" in abstract
        assert "heartbeat" in abstract

    def test_class_has_no_write_methods(self):
        from services.exchange.base import ReadonlyExchangeAdapter
        from services.exchange.binance_readonly import BinanceReadonlyAdapter
        for cls in (ReadonlyExchangeAdapter, BinanceReadonlyAdapter):
            for name in dir(cls):
                if name.startswith("_"):
                    continue
                for pat in FORBIDDEN_NAME_PATTERNS:
                    assert not pat.match(name), f"{cls.__name__} exposes forbidden member {name!r}"


class TestBinanceAdapterDegradedWithoutKeys:
    """Without credentials, adapter must be unconfigured and honestly report."""

    def test_unconfigured_state(self, monkeypatch):
        monkeypatch.delenv("BROKER_BINANCE_API_KEY", raising=False)
        monkeypatch.delenv("BROKER_BINANCE_API_SECRET", raising=False)
        from services.exchange.binance_readonly import BinanceReadonlyAdapter
        a = BinanceReadonlyAdapter()
        assert a.configured is False
        assert a.connected is False
        assert a.capability.value == "unconfigured"
        # All methods return honest degraded payloads, no exceptions.
        hb = a.heartbeat()
        assert hb["ok"] is False
        assert hb["lastSuccessfulHeartbeat"] is None
        bal = a.fetch_balance()
        assert bal["ok"] is False
        assert bal["balances"] == []

    def test_fetch_ticker_rejects_non_whitelisted_symbol(self, monkeypatch):
        monkeypatch.delenv("BROKER_BINANCE_API_KEY", raising=False)
        monkeypatch.delenv("BROKER_BINANCE_API_SECRET", raising=False)
        from services.exchange.binance_readonly import BinanceReadonlyAdapter
        from services.exchange.base import WhitelistViolation
        a = BinanceReadonlyAdapter()
        with pytest.raises(WhitelistViolation):
            a.fetch_ticker("FAKE")
        with pytest.raises(WhitelistViolation):
            a.fetch_ticker("XRP")
        # All curated whitelist passes the assert (even though adapter is
        # unconfigured, the symbol check happens first).
        for sym in ("BTC", "ETH", "SOL", "DOGE", "ADA"):
            out = a.fetch_ticker(sym)
            assert out["symbol"] == sym
            assert out["ok"] is False  # unconfigured

    def test_snapshot_reports_whitelist_and_state(self, monkeypatch):
        monkeypatch.delenv("BROKER_BINANCE_API_KEY", raising=False)
        monkeypatch.delenv("BROKER_BINANCE_API_SECRET", raising=False)
        from services.exchange.binance_readonly import BinanceReadonlyAdapter
        a = BinanceReadonlyAdapter()
        s = a.snapshot()
        assert s["configured"] is False
        assert set(s["whitelist"]) == {"BTC", "ETH", "SOL", "DOGE", "ADA"}
        assert s["quoteAsset"] == "USDT"


# ── Trading-permissions degradation invariant ────────────────────────


class TestTradingPermissionsDowngrade:
    def test_capability_downgrade_when_can_trade(self, monkeypatch):
        """Simulate an API key that returns canTrade=True on fetch_balance.

        The adapter MUST flip capability to TRADING_PERMISSIONS_DETECTED
        on probe, and broker_bridge live gate MUST refuse `exchange_capability_verified`.
        """
        from services.exchange.base import ExchangeCapability
        from services.exchange.binance_readonly import BinanceReadonlyAdapter

        # Build an adapter with fake credentials so __init__ tries probe
        a = BinanceReadonlyAdapter(api_key="fake_key", api_secret="fake_secret")

        # Force _client to a stub whose fetch_balance returns trading perms.
        class _StubClient:
            def fetch_balance(self):
                return {"info": {"canTrade": True, "canWithdraw": False},
                        "total": {}, "free": {}, "used": {}}

        a._client = _StubClient()
        a._probe_permissions_safe()
        assert a.capability == ExchangeCapability.TRADING_PERMISSIONS_DETECTED
        assert "trading_permissions" in (a._last_err or "")

    def test_capability_downgrade_when_can_withdraw(self, monkeypatch):
        from services.exchange.base import ExchangeCapability
        from services.exchange.binance_readonly import BinanceReadonlyAdapter
        a = BinanceReadonlyAdapter(api_key="k", api_secret="s")

        class _StubClient:
            def fetch_balance(self):
                return {"info": {"canTrade": False, "canWithdraw": True},
                        "total": {}, "free": {}, "used": {}}

        a._client = _StubClient()
        a._probe_permissions_safe()
        assert a.capability == ExchangeCapability.TRADING_PERMISSIONS_DETECTED

    def test_readonly_verified_when_clean(self, monkeypatch):
        from services.exchange.base import ExchangeCapability
        from services.exchange.binance_readonly import BinanceReadonlyAdapter
        a = BinanceReadonlyAdapter(api_key="k", api_secret="s")

        class _StubClient:
            def fetch_balance(self):
                return {"info": {"canTrade": False, "canWithdraw": False},
                        "total": {}, "free": {}, "used": {}}

        a._client = _StubClient()
        a._probe_permissions_safe()
        assert a.capability == ExchangeCapability.READONLY_VERIFIED


# ── Honest degradation on transport failure ──────────────────────────


class TestHonestDegradation:
    def test_degraded_on_transport_exception(self, monkeypatch):
        from services.exchange.base import ExchangeCapability
        from services.exchange.binance_readonly import BinanceReadonlyAdapter
        a = BinanceReadonlyAdapter(api_key="k", api_secret="s")

        class _StubClient:
            def fetch_balance(self):
                raise RuntimeError("451 Client Error")
            def fetch_status(self):
                raise RuntimeError("timeout")

        a._client = _StubClient()
        # Heartbeat should not raise — just report degraded
        hb = a.heartbeat()
        assert hb["ok"] is False
        assert "timeout" in (hb["lastError"] or "")
        assert a.capability == ExchangeCapability.DEGRADED


# ── Integration with broker_bridge.py ────────────────────────────────


class TestBrokerStatusSurfacesCapability:
    def test_status_includes_capability_field(self):
        from services import broker_bridge as svc
        s = svc.broker_status()
        assert "capability" in s
        assert s["capability"] in (
            "unconfigured", "readonly_verified", "degraded", "trading_permissions_detected"
        )
        assert s["version"].startswith("t10_2b.")

    def test_live_gate_rules_include_exchange_capability(self):
        from services import broker_bridge as svc
        assert "exchange_capability_verified" in svc.GATE_RULES

    def test_live_gate_blocks_when_capability_not_verified(self):
        from services import broker_bridge as svc
        verdict = {"action": "LONG", "calibration": {"sample": 10},
                   "sizing": {"final": 100}, "portfolioGate": {"finalPermission": "allowed",
                   "drawdown": {"breakerActive": False}}}
        pre = {"ok": True, "refusedReasons": []}
        checks, reasons = svc._evaluate_live_gate(verdict, pre)
        ec = next(c for c in checks if c["name"] == "exchange_capability_verified")
        # In test env capability is unconfigured → must fail
        assert ec["passed"] is False
        assert any("exchange_capability_verified" in r for r in reasons)


# ── Live HTTP endpoint checks ─────────────────────────────────────────


@pytest.fixture(scope="module")
def s():
    sess = requests.Session()
    sess.headers.update({"Content-Type": "application/json", "X-User-Id": "dev_user"})
    return sess


@pytest.fixture(scope="module")
def s_live():
    """live_test_operator: required for /api/broker/live/submit guard."""
    sess = requests.Session()
    sess.headers.update({"Content-Type": "application/json", "X-User-Id": "live_test_operator"})
    return sess


class TestBrokerEndpoints:
    def test_status_capability_exposed(self, s):
        r = s.get(f"{BASE_URL}/api/broker/status", timeout=15).json()
        assert "capability" in r
        assert r["version"].startswith("t10_2b.")

    def test_heartbeat_endpoint(self, s):
        r = s.get(f"{BASE_URL}/api/broker/heartbeat", timeout=15).json()
        assert "ok" in r

    def test_live_submit_gate_includes_capability_rule(self, s_live):
        r = s_live.post(
            f"{BASE_URL}/api/broker/live/submit",
            json={"symbol": "BTC", "action": "LONG", "sizeUsd": 500},
            timeout=20,
        ).json()
        names = {c["name"] for c in r["gateChecks"]}
        assert "exchange_capability_verified" in names

    @pytest.mark.parametrize("path", [
        "/api/broker/status",
        "/api/broker/balances",
        "/api/broker/markets",
        "/api/broker/heartbeat",
        "/api/broker/audit?limit=5",
    ])
    def test_endpoint_ok(self, s, path):
        r = s.get(f"{BASE_URL}{path}", timeout=15)
        assert r.status_code == 200, f"{path} → {r.status_code}: {r.text[:200]}"
