"""
Quality Layer Router — /api/quality/*

Endpoints (all admin-gated except /resolve-timing-mode):
    GET  /api/quality/pretruth                 — 5+2 gates verdict
    GET  /api/quality/accumulation             — M1-M5 metrics + status
    GET  /api/quality/integrity/inventory      — corruption breakdown (read-only)
    POST /api/quality/integrity/run            — apply guard sweep (admin)
    GET  /api/quality/integrity/dry-run        — what would be marked (read-only)
    GET  /api/quality/resolve-timing-mode      — current mode + diff sample
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request

from services.quality import (
    accumulation_monitor,
    diff_modes,
    integrity_guard,
    pre_truth_check,
)

router = APIRouter(prefix="/api/quality", tags=["quality"])


def _is_admin(request: Request) -> bool:
    auth = request.headers.get("authorization", "") or request.headers.get("Authorization", "")
    if not auth.lower().startswith("bearer "):
        return False
    token = auth.split(" ", 1)[1].strip()
    if not token:
        return False
    try:
        import jwt
        secret = (
            os.environ.get("ADMIN_JWT_SECRET", "")
            or os.environ.get("JWT_ACCESS_SECRET", "")
        )
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        return payload.get("role") in ("superadmin", "admin")
    except Exception:
        return False


def _require_admin(request: Request) -> None:
    if not _is_admin(request):
        raise HTTPException(status_code=401, detail={"error": "ADMIN_REQUIRED"})


# ── Read-only ────────────────────────────────────────────────────────
@router.get("/pretruth")
async def quality_pretruth(request: Request):
    _require_admin(request)
    return await pre_truth_check.run()


@router.get("/accumulation")
async def quality_accumulation(request: Request):
    _require_admin(request)
    return await accumulation_monitor.snapshot()


@router.get("/integrity/inventory")
async def quality_integrity_inventory(request: Request):
    _require_admin(request)
    return await integrity_guard.inventory()


@router.get("/integrity/dry-run")
async def quality_integrity_dry_run(request: Request):
    _require_admin(request)
    return await integrity_guard.dry_run()


# ── Mutating (additive only — sets `corrupted=true`, never deletes) ──
@router.post("/integrity/run")
async def quality_integrity_run(request: Request):
    _require_admin(request)
    return await integrity_guard.run()


# ── Diagnostic: resolve-timing physics ───────────────────────────────
@router.get("/resolve-timing-mode")
async def quality_resolve_timing(request: Request):
    """Returns active mode + sample diff between v1 (legacy) and v2 (truth-lane).
    Mode is set via env RESOLVE_TIMING_MODE; production scheduler still uses
    v1 unless explicitly switched in code AND env at the same time."""
    _require_admin(request)
    sample = diff_modes(datetime.now(timezone.utc), "1D")
    return {
        "ok": True,
        "active_mode": os.environ.get("RESOLVE_TIMING_MODE", "v1"),
        "scheduler_uses": "legacy_v1",  # production untouched
        "sample_now_horizon_1D": sample,
        "switching_instructions": [
            "1. Set RESOLVE_TIMING_MODE=v2 in backend/.env",
            "2. Edit scheduler/forecast_recorder to call compute_resolve_at()",
            "3. Old outcomes immutable (R-invariants), only NEW use v2",
        ],
    }
