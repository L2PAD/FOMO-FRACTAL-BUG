"""
Backend test bootstrap.

After TIER-2 (Backend Capability Enforcement) we need to seed a couple of
operator_access records BEFORE the pytest session starts, so old test
suites (T1/T3/T10.x) that only know how to send ``X-User-Id`` headers
have a valid principal on the other side.

Principals seeded:

  * dev_user           → tier=pro,  operatorAccess approved + mode=paper
                         (this one is already auto-seeded by routes.operator_access
                          on first GET /api/me/capabilities; we just make sure
                          it exists deterministically before any test runs)

  * live_test_operator → tier=pro,  operatorAccess approved + mode=live
                         (required only for T10.1 / T10.2B "live/submit"
                          assertions; the actual exchange is still in safe
                          mode so no real order is ever placed — what we test
                          is that a *live-authorised* caller still gets the
                          honest "refused, here are the gate reasons" body.)

Nothing here ever grants `liveTrading` to a Tier upgrade — live access is
strictly admin-installed via the operator_access seed below.

Also bootstraps EXPO_PUBLIC_BACKEND_URL when missing so legacy tests that
hard-assert on it at import time don't crash collection.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest
from pymongo import MongoClient


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Backend URL fallback ─────────────────────────────────────────────
# A few legacy test modules assert at import time that
# EXPO_PUBLIC_BACKEND_URL is set. Provide a sane default so collection
# doesn't explode in CI / sandbox.
os.environ.setdefault(
    "EXPO_PUBLIC_BACKEND_URL",
    "https://merge-verify-4.preview.emergentagent.com",
)


# ── operator_access seeding ──────────────────────────────────────────


def _seed_operator_access(
    user_id: str,
    *,
    tier: str,
    mode: str,
    console_access: bool = False,
    live_authority: bool = False,
) -> None:
    """Idempotently upsert an operator_access record.

    TIER-3 invariant: `mode` (broker connection) is decoupled from
    `liveAuthority.granted` (operational authority). Tests that need a
    live-authorised principal MUST set `live_authority=True` explicitly."""
    client = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    db = client[os.environ.get("DB_NAME", "test_database")]
    coll = db.operator_access

    coll.create_index("userId", unique=True)
    coll.update_one(
        {"userId": user_id},
        {
            "$set": {
                "userId": user_id,
                "tier": tier,
                "operatorAccess": {
                    "enabled": True,
                    "status": "approved",
                    "mode": mode,
                    "consoleAccess": console_access,
                    "capabilityOverrides": {},
                    "liveAuthority": {
                        "granted": live_authority,
                        "grantedAt": _now() if live_authority else None,
                        "grantedBy": "conftest_seed" if live_authority else None,
                        "reason": "test fixture" if live_authority else None,
                        "expiresAt": None,
                    },
                    "lastCapabilityChangeAt": _now(),
                    "lastCapabilityChangedBy": "conftest_seed",
                    "riskAcknowledgedAt": _now(),
                    "termsAcceptedAt": _now(),
                    "appliedAt": _now(),
                    "approvedAt": _now(),
                    "approvedBy": "conftest_seed",
                    "maxCapitalExposureUsd": None,
                    "allowedExchanges": [],
                },
                "updatedAt": _now(),
            },
            "$setOnInsert": {"createdAt": _now()},
        },
        upsert=True,
    )


@pytest.fixture(scope="session", autouse=True)
def _seed_principals():
    """Run once before the whole pytest session. Idempotent."""
    # dev_user: paper mode + console (operator scheduler/console for dev)
    _seed_operator_access(
        "dev_user", tier="pro", mode="paper",
        console_access=True, live_authority=False,
    )
    # live_test_operator: live mode + console + LIVE AUTHORITY
    # (broker connects live AND admin has issued the typed-confirmation
    # live-authority grant — required by TIER-3 for liveTrading capability)
    _seed_operator_access(
        "live_test_operator", tier="pro", mode="live",
        console_access=True, live_authority=True,
    )
    yield


# ── Convenience header fixtures ──────────────────────────────────────


@pytest.fixture
def dev_headers() -> dict:
    return {"X-User-Id": "dev_user"}


@pytest.fixture
def live_operator_headers() -> dict:
    return {"X-User-Id": "live_test_operator"}


@pytest.fixture
def free_headers() -> dict:
    """A user_id that has never applied / never been granted operator
    access.  routes.operator_access._load will auto-seed them as
    free / status=none, which is exactly what we want to assert 403 on."""
    return {"X-User-Id": "tier2_free_user_xyz_abc"}
