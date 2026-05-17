"""
T10.2C — Testnet Execution route (admin-only, observational).

Single POST endpoint to submit a previously-gated verdict through the
hardcoded Binance Spot Testnet executor.  No retry, no override, no
mainnet code path.  Receipts are append-only by DB-level unique index
on lineageId.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from routes.operator_access import _is_admin
from services.binance_testnet_executor import (
    MAX_NOTIONAL_USD,
    SYMBOL_ALLOWLIST,
    TESTNET_ONLY,
    EXECUTION_PIPELINE_VERSION,
    _resolve_mode,
    submit_testnet_order,
    list_receipts,
    get_receipt,
    get_receipt_by_lineage,
    TestnetExecutorConflict,
)


router = APIRouter(prefix="/api/admin/execution/testnet", tags=["testnet-execution"])


class SubmitBody(BaseModel):
    lineageId:       str = Field(..., min_length=4, max_length=64)
    operatorUserId:  str = Field(..., min_length=1, max_length=128)
    symbol:          str = Field(..., min_length=2,  max_length=20)
    side:            str = Field(..., min_length=2,  max_length=8)
    sizeUsd:         float = Field(...)


@router.get("/config")
def testnet_config(request: Request):
    """Read-only visibility of the hardcoded invariants.  Exposed so an
    operator can verify (and audit) what the system is currently
    constrained to.  Returns the canonical values straight from the
    Python module — there is no way to override them at runtime."""
    if not _is_admin(request):
        raise HTTPException(status_code=401, detail={"error": "ADMIN_REQUIRED"})
    return {
        "ok":               True,
        "pipelineVersion":  EXECUTION_PIPELINE_VERSION,
        "invariants": {
            "TESTNET_ONLY":     TESTNET_ONLY,
            "SYMBOL_ALLOWLIST": sorted(SYMBOL_ALLOWLIST),
            "MAX_NOTIONAL_USD": MAX_NOTIONAL_USD,
            "retryForbidden":   True,
            "appendOnly":       True,
            "autoResubmit":     False,
        },
        "mode": _resolve_mode(),    # 'mock' or 'testnet'
        "framingNote": (
            "Testnet execution is an architecture-validation surface. "
            "It NEVER touches mainnet, NEVER auto-retries, and NEVER "
            "self-heals failures.  Every attempt is an immutable fact."
        ),
    }


@router.post("/submit")
def testnet_submit(body: SubmitBody, request: Request):
    """Single immutable execution attempt for a previously-gated lineage.

    HTTP semantics:
      * 200 — receipt written (success OR observational failure)
      * 401 — admin required
      * 409 — receipt for this lineageId already exists (retry forbidden)
      * 422 — body validation error (FastAPI default)

    Note that 200 with status='preflight_fail' / 'broker_reject' /
    'transport_error' is the EXPECTED shape for failure paths — they
    are observational events, not HTTP errors.  HTTP-level 409 is
    reserved for the architectural retry-forbidden conflict.
    """
    if not _is_admin(request):
        raise HTTPException(status_code=401, detail={"error": "ADMIN_REQUIRED"})
    try:
        receipt = submit_testnet_order(
            lineage_id=body.lineageId,
            operator_user_id=body.operatorUserId,
            symbol=body.symbol,
            side=body.side,
            size_usd=body.sizeUsd,
            submitted_by="admin",
        )
    except TestnetExecutorConflict as e:
        # Architectural: a receipt already exists for this lineageId.
        # We DO NOT silently fall back to returning the existing one —
        # the caller MUST acknowledge the conflict explicitly.  Lookup
        # is offered via /receipts/by-lineage/{lineageId}.
        #
        # Use JSONResponse rather than `raise HTTPException` so the
        # response composes cleanly with BaseHTTPMiddleware chains that
        # capture exceptions before FastAPI's handler runs.
        return JSONResponse(
            status_code=409,
            content={
                "detail": {
                    "error":     "RECEIPT_EXISTS",
                    "lineageId": body.lineageId,
                    "message":   str(e),
                },
            },
        )
    return {"ok": True, "receipt": receipt}


@router.get("/receipts")
def testnet_receipts(
    request: Request,
    limit: int = Query(50, ge=1, le=500),
):
    """Read-only ledger view — most recent first.  Pure observation."""
    if not _is_admin(request):
        raise HTTPException(status_code=401, detail={"error": "ADMIN_REQUIRED"})
    rows = list_receipts(limit=limit)
    return {
        "ok":              True,
        "pipelineVersion": EXECUTION_PIPELINE_VERSION,
        "n":               len(rows),
        "rows":            rows,
    }


@router.get("/receipts/{receipt_id}")
def testnet_receipt_detail(receipt_id: str, request: Request):
    if not _is_admin(request):
        raise HTTPException(status_code=401, detail={"error": "ADMIN_REQUIRED"})
    r = get_receipt(receipt_id)
    if not r:
        raise HTTPException(status_code=404, detail={"error": "RECEIPT_NOT_FOUND"})
    return {"ok": True, "receipt": r}


@router.get("/receipts/by-lineage/{lineage_id}")
def testnet_receipt_by_lineage(lineage_id: str, request: Request):
    if not _is_admin(request):
        raise HTTPException(status_code=401, detail={"error": "ADMIN_REQUIRED"})
    r = get_receipt_by_lineage(lineage_id)
    if not r:
        raise HTTPException(status_code=404, detail={"error": "RECEIPT_NOT_FOUND"})
    return {"ok": True, "receipt": r}
