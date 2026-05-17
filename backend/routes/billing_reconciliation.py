"""
TIER-4B.2 — Billing Reconciliation Integrity Layer

Architectural contract (locked by user):
  * Reconciliation OBSERVES.  It never auto-heals, auto-refunds,
    auto-rewrites tiers, or mutates the billing ledger.
  * Findings are IMMUTABLE.  Once persisted, neither severity, evidence,
    detectedAt nor any payload field is ever rewritten.  If a stuck
    invoice escalates from elevated to critical, a NEW finding row is
    written and the existing one is kept as historical truth.
  * Snapshot-at-detection is MANDATORY.  Every finding embeds the full
    state it observed at detection time (invoice + user operator_access
    + relevant audit slice).  Future state changes never drift a
    finding's evidence.
  * Acknowledgement is SECONDARY ATTESTATION, not resolution.  Operator
    attestations live in a separate append-only collection and overlay
    findings only at read-time.  Underlying findings stay open forever
    in their own right.
  * No reconciliation writes touch billing_invoices, billing_audit,
    operator_access, or operator_access_audit collections — period.

Six detectors, all read-only:
  1. stuck_pending           — pending invoice > 24h (elevated) / 72h (critical)
  2. entitlement_mismatch    — paid invoice but user.tier != productSnapshot.tier
  3. tier_without_billing_trail — user.tier in (pro, trader) without any paid invoice
  4. failed_activation       — invoice paid but no entitlement_activated audit row
  5. refunded_but_not_downgraded — refund event without a matching downgrade event
  6. orphan_audit_row        — billing_audit row references a non-existent invoice

Dedup discipline:
  Each finding has a composite dedupKey on (findingType, primaryRefId, severity).
  A unique index on dedupKey makes re-running the scanner idempotent.
  Severity escalation INTENTIONALLY produces a new dedupKey, so the elevated
  finding is preserved when the critical one is added (escalation chain via
  parentFindingId).
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Literal, Optional, Any

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError

# Reuse the admin auth predicate from operator_access — no second auth path.
from routes.operator_access import (
    _is_admin as _is_operator_admin,
    _now as _ts,
)

load_dotenv()

_client = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
_db = _client[os.environ.get("DB_NAME", "test_database")]

_findings       = _db.billing_reconciliation_findings
_attestations   = _db.billing_reconciliation_attestations
_scans          = _db.billing_reconciliation_scans

_invoices       = _db.billing_invoices
_billing_audit  = _db.billing_audit
_operator_coll  = _db.operator_access

_findings.create_index("dedupKey", unique=True)
_findings.create_index("findingId", unique=True)
_findings.create_index([("findingType", 1), ("detectedAt", -1)])
_findings.create_index([("severity", 1), ("detectedAt", -1)])
_findings.create_index([("invoiceId", 1)])
_findings.create_index([("userId", 1)])
_attestations.create_index([("findingId", 1), ("ts", -1)])
_attestations.create_index("attestationId", unique=True)
_scans.create_index("scanId", unique=True)

FindingType = Literal[
    "stuck_pending",
    "entitlement_mismatch",
    "tier_without_billing_trail",
    "failed_activation",
    "refunded_but_not_downgraded",
    "orphan_audit_row",
]
Severity = Literal["info", "elevated", "critical"]
AttestAction = Literal["acknowledge", "mark_resolved_later"]

STUCK_ELEVATED_HOURS = 24
STUCK_CRITICAL_HOURS = 72


# ── Schemas ──────────────────────────────────────────────────────────


class AttestBody(BaseModel):
    action: AttestAction
    reason: Optional[str] = None
    note: Optional[str] = None


# ── Helpers ──────────────────────────────────────────────────────────


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:18]}"


def _parse_iso(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        # billing_invoices.createdAt is written by _ts() in operator_access;
        # always tz-aware ISO 8601.
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _persist_finding(doc: dict) -> Optional[dict]:
    """Idempotent insert: respect the unique(dedupKey) constraint so the
    same anomaly band reported by repeat scans is *not* duplicated, but
    severity escalations *do* get a new row (different dedupKey)."""
    try:
        _findings.insert_one(doc)
        return doc
    except DuplicateKeyError:
        return None


def _build_finding(
    *,
    finding_type: FindingType,
    severity: Severity,
    user_id: Optional[str],
    invoice_id: Optional[str],
    dedup_key: str,
    evidence: dict,
    scan_id: str,
    parent_finding_id: Optional[str] = None,
) -> dict:
    return {
        "findingId":       _new_id("fnd"),
        "findingType":     finding_type,
        "severity":        severity,
        "userId":          user_id,
        "invoiceId":       invoice_id,
        "dedupKey":        dedup_key,
        "parentFindingId": parent_finding_id,
        "scanId":          scan_id,
        "detectedAt":      _ts(),
        "evidence":        evidence,   # snapshot — immutable
    }


def _invoice_snapshot(inv: dict) -> dict:
    """Tight slice of invoice fields suitable for embedding inside a
    finding evidence block.  No _id; never embed the entire MongoCursor
    output verbatim because productSnapshot can be heavy."""
    return {
        "invoiceId":        inv.get("invoiceId"),
        "userId":           inv.get("userId"),
        "productCode":      inv.get("productCode"),
        "priceUsd":         inv.get("priceUsd"),
        "status":           inv.get("status"),
        "paymentReference": inv.get("paymentReference"),
        "createdAt":        inv.get("createdAt"),
        "paidAt":           inv.get("paidAt"),
        "failedAt":         inv.get("failedAt"),
        "refundedAt":       inv.get("refundedAt"),
        "productTier":      (inv.get("productSnapshot") or {}).get("tier"),
    }


def _user_snapshot(user_id: str) -> dict:
    u = _operator_coll.find_one({"userId": user_id}, {"_id": 0}) or {}
    oa = u.get("operatorAccess") or {}
    return {
        "tier":              u.get("tier", "free"),
        "consoleAccess":     bool(oa.get("consoleAccess")),
        "liveAuthority":     {
            "granted": bool((oa.get("liveAuthority") or {}).get("granted")),
            "expiresAt": (oa.get("liveAuthority") or {}).get("expiresAt"),
        },
        "capabilityOverrides": oa.get("capabilityOverrides") or {},
        "mode":              oa.get("mode", "none"),
        "status":            oa.get("status", "none"),
        "updatedAt":         u.get("updatedAt"),
    }


# ── Detectors ────────────────────────────────────────────────────────


def _detect_stuck_pending(scan_id: str) -> list[dict]:
    """Pending invoices > 24h (elevated) or > 72h (critical).
    Both severity bands can coexist: the elevated finding is preserved
    when the same invoice later escalates to critical."""
    out: list[dict] = []
    now = _now_utc()
    cursor = _invoices.find({"status": "pending"}, {"_id": 0})
    for inv in cursor:
        created = _parse_iso(inv.get("createdAt"))
        if not created:
            continue
        age = now - created
        age_h = age.total_seconds() / 3600.0
        if age_h < STUCK_ELEVATED_HOURS:
            continue
        # always try to record the elevated band first
        elevated_doc = _build_finding(
            finding_type="stuck_pending",
            severity="elevated",
            user_id=inv.get("userId"),
            invoice_id=inv.get("invoiceId"),
            dedup_key=f"stuck_pending::{inv.get('invoiceId')}::elevated",
            evidence={
                "ageHours":          round(age_h, 2),
                "invoiceSnapshot":   _invoice_snapshot(inv),
                "thresholdHours":    STUCK_ELEVATED_HOURS,
            },
            scan_id=scan_id,
        )
        elevated_inserted = _persist_finding(elevated_doc)
        if elevated_inserted:
            out.append(elevated_inserted)
        # if old enough, also record the critical band as a SEPARATE finding
        if age_h >= STUCK_CRITICAL_HOURS:
            parent = None
            if elevated_inserted is None:
                # the elevated row exists from a previous scan; link to it
                prev = _findings.find_one(
                    {"dedupKey": f"stuck_pending::{inv.get('invoiceId')}::elevated"},
                    {"_id": 0, "findingId": 1},
                )
                parent = prev.get("findingId") if prev else None
            else:
                parent = elevated_inserted["findingId"]
            critical_doc = _build_finding(
                finding_type="stuck_pending",
                severity="critical",
                user_id=inv.get("userId"),
                invoice_id=inv.get("invoiceId"),
                dedup_key=f"stuck_pending::{inv.get('invoiceId')}::critical",
                evidence={
                    "ageHours":        round(age_h, 2),
                    "invoiceSnapshot": _invoice_snapshot(inv),
                    "thresholdHours":  STUCK_CRITICAL_HOURS,
                },
                scan_id=scan_id,
                parent_finding_id=parent,
            )
            ins = _persist_finding(critical_doc)
            if ins:
                out.append(ins)
    return out


def _detect_entitlement_mismatch(scan_id: str) -> list[dict]:
    """Paid invoices whose product.tier differs from the user's current
    tier.  The mismatch may be legitimate (admin downgraded for cause,
    later refund pending) — that's WHY this surfaces rather than
    auto-heals.  Snapshotted at detection so future tier shifts cannot
    silently invalidate the observation."""
    out: list[dict] = []
    for inv in _invoices.find({"status": "paid"}, {"_id": 0}):
        snap_tier = (inv.get("productSnapshot") or {}).get("tier")
        if not snap_tier:
            continue
        u = _user_snapshot(inv.get("userId"))
        if u["tier"] == snap_tier:
            continue
        out_doc = _build_finding(
            finding_type="entitlement_mismatch",
            severity="elevated",
            user_id=inv.get("userId"),
            invoice_id=inv.get("invoiceId"),
            dedup_key=f"entitlement_mismatch::{inv.get('invoiceId')}",
            evidence={
                "expectedTier":      snap_tier,
                "actualTier":        u["tier"],
                "invoiceSnapshot":   _invoice_snapshot(inv),
                "userSnapshot":      u,
            },
            scan_id=scan_id,
        )
        ins = _persist_finding(out_doc)
        if ins:
            out.append(ins)
    return out


def _detect_tier_without_billing_trail(scan_id: str) -> list[dict]:
    """Users carrying tier=pro or tier=trader without ANY paid invoice
    of the corresponding product.  Often legitimate (admin grant, comp,
    promotional uplift) — left to operator attestation.  Refunded
    invoices don't count as a billing trail."""
    out: list[dict] = []
    for u in _operator_coll.find({"tier": {"$in": ["pro", "trader"]}}, {"_id": 0}):
        uid = u.get("userId")
        tier = u.get("tier")
        # Map tier → expected productCode
        expected_code = "TRADER" if tier == "trader" else "PRO"
        paid = _invoices.find_one(
            {"userId": uid, "productCode": expected_code, "status": "paid"},
            {"_id": 0, "invoiceId": 1},
        )
        if paid:
            continue
        out_doc = _build_finding(
            finding_type="tier_without_billing_trail",
            severity="info",
            user_id=uid,
            invoice_id=None,
            dedup_key=f"tier_without_billing_trail::{uid}::{tier}",
            evidence={
                "tier":           tier,
                "expectedCode":   expected_code,
                "userSnapshot":   _user_snapshot(uid),
            },
            scan_id=scan_id,
        )
        ins = _persist_finding(out_doc)
        if ins:
            out.append(ins)
    return out


def _detect_failed_activation(scan_id: str) -> list[dict]:
    """Invoice paid but no `entitlement_activated` audit row recorded
    for that invoiceId.  Indicates the activation transaction failed
    half-way or the audit write was lost.  Critical because the
    customer paid but didn't get what they bought."""
    out: list[dict] = []
    for inv in _invoices.find({"status": "paid"}, {"_id": 0}):
        ok = _billing_audit.find_one({
            "invoiceId": inv.get("invoiceId"),
            "action": "entitlement_activated",
        }, {"_id": 0, "ts": 1})
        if ok:
            continue
        # Also surface entitlement_failed if present, for evidence
        failed = _billing_audit.find_one({
            "invoiceId": inv.get("invoiceId"),
            "action": "entitlement_failed",
        }, {"_id": 0})
        out_doc = _build_finding(
            finding_type="failed_activation",
            severity="critical",
            user_id=inv.get("userId"),
            invoice_id=inv.get("invoiceId"),
            dedup_key=f"failed_activation::{inv.get('invoiceId')}",
            evidence={
                "invoiceSnapshot":     _invoice_snapshot(inv),
                "failedAuditPresent":  bool(failed),
                "failedAuditDetail":   failed,
                "userSnapshot":        _user_snapshot(inv.get("userId")),
            },
            scan_id=scan_id,
        )
        ins = _persist_finding(out_doc)
        if ins:
            out.append(ins)
    return out


def _detect_refunded_not_downgraded(scan_id: str) -> list[dict]:
    """A `refund` audit event exists for an invoice but no matching
    `downgrade` event.  Means the tier was not actually walked back
    after the commercial refund — a billing integrity break."""
    out: list[dict] = []
    seen_invoice_ids = set()
    for ev in _billing_audit.find({"action": "refund"}, {"_id": 0}):
        inv_id = ev.get("invoiceId")
        if not inv_id or inv_id in seen_invoice_ids:
            continue
        seen_invoice_ids.add(inv_id)
        down = _billing_audit.find_one({
            "invoiceId": inv_id,
            "action": "downgrade",
        }, {"_id": 0})
        if down:
            continue
        inv = _invoices.find_one({"invoiceId": inv_id}, {"_id": 0}) or {}
        out_doc = _build_finding(
            finding_type="refunded_but_not_downgraded",
            severity="critical",
            user_id=ev.get("userId"),
            invoice_id=inv_id,
            dedup_key=f"refunded_but_not_downgraded::{inv_id}",
            evidence={
                "refundEvent":     ev,
                "invoiceSnapshot": _invoice_snapshot(inv) if inv else None,
                "userSnapshot":    _user_snapshot(ev.get("userId")) if ev.get("userId") else None,
            },
            scan_id=scan_id,
        )
        ins = _persist_finding(out_doc)
        if ins:
            out.append(ins)
    return out


def _detect_orphan_audit_rows(scan_id: str) -> list[dict]:
    """billing_audit rows whose invoiceId does not resolve to any
    existing invoice document.  Usually indicates manual db cleanup or
    a partially deleted record."""
    out: list[dict] = []
    seen = set()
    for ev in _billing_audit.find({"invoiceId": {"$ne": None}}, {"_id": 0}):
        inv_id = ev.get("invoiceId")
        if not inv_id or inv_id in seen:
            continue
        seen.add(inv_id)
        if _invoices.count_documents({"invoiceId": inv_id}, limit=1) > 0:
            continue
        out_doc = _build_finding(
            finding_type="orphan_audit_row",
            severity="elevated",
            user_id=ev.get("userId"),
            invoice_id=inv_id,
            dedup_key=f"orphan_audit_row::{inv_id}",
            evidence={
                "sampleAuditEvent": ev,
                "auditCount":       _billing_audit.count_documents({"invoiceId": inv_id}),
            },
            scan_id=scan_id,
        )
        ins = _persist_finding(out_doc)
        if ins:
            out.append(ins)
    return out


_DETECTORS = [
    ("stuck_pending",              _detect_stuck_pending),
    ("entitlement_mismatch",       _detect_entitlement_mismatch),
    ("tier_without_billing_trail", _detect_tier_without_billing_trail),
    ("failed_activation",          _detect_failed_activation),
    ("refunded_but_not_downgraded", _detect_refunded_not_downgraded),
    ("orphan_audit_row",           _detect_orphan_audit_rows),
]


# ── Status overlay ───────────────────────────────────────────────────


def _effective_status(finding_id: str) -> dict:
    """Compute the operator-attestation overlay for a finding.  The
    underlying finding never mutates; this is purely a read-time view.
    'open' is the default until an attestation event is recorded."""
    latest = _attestations.find_one(
        {"findingId": finding_id},
        {"_id": 0},
        sort=[("ts", -1)],
    )
    if not latest:
        return {"status": "open", "lastAttestation": None}
    status = "acknowledged" if latest.get("action") == "acknowledge" else "resolved_later"
    return {"status": status, "lastAttestation": latest}


# ── Router ───────────────────────────────────────────────────────────


router = APIRouter(prefix="/api/admin/billing/reconciliation", tags=["billing-reconciliation"])


@router.post("/scan")
def run_scan(request: Request):
    """Manually trigger all detectors.  Returns the scan summary AND
    the list of newly persisted findings (deduplicated entries are not
    returned twice — they remain anchored to their original scanId)."""
    if not _is_operator_admin(request):
        raise HTTPException(status_code=401, detail={"error": "ADMIN_REQUIRED"})

    scan_id = _new_id("scn")
    started = _now_utc()
    by_category: dict[str, int] = {}
    new_findings: list[dict] = []
    errors: list[dict] = []

    for name, fn in _DETECTORS:
        try:
            produced = fn(scan_id)
            by_category[name] = len(produced)
            new_findings.extend(produced)
        except Exception as e:
            errors.append({"detector": name, "error": str(e)})
            by_category[name] = 0

    finished = _now_utc()
    duration_ms = int((finished - started).total_seconds() * 1000)

    scan_doc = {
        "scanId":           scan_id,
        "actor":            "admin",
        "startedAt":        started.isoformat(),
        "finishedAt":       finished.isoformat(),
        "durationMs":       duration_ms,
        "findingsProduced": by_category,
        "newFindingsCount": len(new_findings),
        "errors":           errors,
    }
    _scans.insert_one(scan_doc)
    scan_doc.pop("_id", None)

    # Return a slim summary; full findings can be fetched via /findings.
    return {
        "ok":            True,
        "scan":          scan_doc,
        "newFindings":   [{k: f[k] for k in ("findingId", "findingType", "severity", "userId", "invoiceId")} for f in new_findings],
    }


@router.get("/findings")
def list_findings(
    request: Request,
    findingType: Optional[str] = None,
    severity:    Optional[str] = None,
    status:      Optional[str] = None,        # open | acknowledged | resolved_later
    userId:      Optional[str] = None,
    invoiceId:   Optional[str] = None,
    limit: int = 100,
):
    if not _is_operator_admin(request):
        raise HTTPException(status_code=401, detail={"error": "ADMIN_REQUIRED"})

    q: dict[str, Any] = {}
    if findingType: q["findingType"] = findingType
    if severity:    q["severity"]    = severity
    if userId:      q["userId"]      = userId.lower()
    if invoiceId:   q["invoiceId"]   = invoiceId
    rows = list(_findings.find(q, {"_id": 0}).sort("detectedAt", -1).limit(int(limit)))

    out = []
    for r in rows:
        overlay = _effective_status(r["findingId"])
        if status and overlay["status"] != status:
            continue
        out.append({**r, **overlay})
    return {"ok": True, "n": len(out), "rows": out}


@router.get("/findings/{finding_id}")
def get_finding(finding_id: str, request: Request):
    if not _is_operator_admin(request):
        raise HTTPException(status_code=401, detail={"error": "ADMIN_REQUIRED"})
    row = _findings.find_one({"findingId": finding_id}, {"_id": 0})
    if not row:
        raise HTTPException(status_code=404, detail={"error": "FINDING_NOT_FOUND"})
    overlay = _effective_status(finding_id)
    # also fetch the full attestation timeline (append-only)
    attests = list(_attestations.find({"findingId": finding_id}, {"_id": 0}).sort("ts", -1))
    return {"ok": True, "finding": {**row, **overlay}, "attestations": attests}


@router.post("/findings/{finding_id}/attest")
def attest_finding(finding_id: str, body: AttestBody, request: Request):
    """Add an operator attestation to a finding.  The finding itself
    never mutates — the attestation is a separate append-only event.
    Multiple attestations may exist for the same finding; the most
    recent one drives the effective status overlay at read time."""
    if not _is_operator_admin(request):
        raise HTTPException(status_code=401, detail={"error": "ADMIN_REQUIRED"})
    row = _findings.find_one({"findingId": finding_id}, {"_id": 0, "findingId": 1})
    if not row:
        raise HTTPException(status_code=404, detail={"error": "FINDING_NOT_FOUND"})

    doc = {
        "attestationId": _new_id("att"),
        "findingId":     finding_id,
        "action":        body.action,
        "actor":         "admin",
        "reason":        (body.reason or "").strip() or None,
        "note":          (body.note or "").strip() or None,
        "ts":            _ts(),
    }
    _attestations.insert_one(doc)
    doc.pop("_id", None)
    return {"ok": True, "attestation": doc, "effectiveStatus": _effective_status(finding_id)}


@router.get("/scans")
def list_scans(request: Request, limit: int = 50):
    if not _is_operator_admin(request):
        raise HTTPException(status_code=401, detail={"error": "ADMIN_REQUIRED"})
    rows = list(_scans.find({}, {"_id": 0}).sort("startedAt", -1).limit(int(limit)))
    return {"ok": True, "n": len(rows), "rows": rows}


@router.get("/summary")
def summary(request: Request):
    """Cheap aggregated counts for the dashboard top strip."""
    if not _is_operator_admin(request):
        raise HTTPException(status_code=401, detail={"error": "ADMIN_REQUIRED"})

    by_severity = {"info": 0, "elevated": 0, "critical": 0}
    by_category: dict[str, int] = {}
    open_count = 0
    ack_count = 0
    rl_count = 0

    for r in _findings.find({}, {"_id": 0, "findingId": 1, "severity": 1, "findingType": 1}):
        sev = r.get("severity") or "info"
        by_severity[sev] = by_severity.get(sev, 0) + 1
        cat = r.get("findingType") or "unknown"
        by_category[cat] = by_category.get(cat, 0) + 1
        ov = _effective_status(r["findingId"])
        if ov["status"] == "open":              open_count += 1
        elif ov["status"] == "acknowledged":    ack_count += 1
        elif ov["status"] == "resolved_later":  rl_count += 1

    last_scan = _scans.find_one({}, {"_id": 0}, sort=[("startedAt", -1)])
    return {
        "ok":              True,
        "totalFindings":   sum(by_severity.values()),
        "bySeverity":      by_severity,
        "byCategory":      by_category,
        "byStatus": {
            "open":           open_count,
            "acknowledged":   ack_count,
            "resolved_later": rl_count,
        },
        "lastScan":        last_scan,
    }
