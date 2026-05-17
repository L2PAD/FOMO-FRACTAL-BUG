"""
TIER-4B.3 — Billing Analytics (derived read-only business intelligence)

Architectural contract (locked by user):
  * Analytics is a DERIVED READ MODEL — never a source of truth.
    Source of truth remains: billing_invoices, billing_audit,
    operator_access, operator_access_audit, reconciliation findings.
  * NO mutation of invoice records to attach analytics fields.
  * Refunds are visually DUAL-TRACKED — never silently netted out:
    gross / refunded / net are surfaced separately so analytics never
    lies about business health.
  * Churn semantics are SEPARATED — refund-driven downgrades and
    voluntary admin downgrades are different operational stories.
  * Time windows are rolling (7d / 30d / 90d), NOT calendar months —
    operational phase, not accounting reporting phase.

Out of scope (per user direction):
  * LTV, CAC, cohort analytics, retention curves — premature given
    immature lifecycle history.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone, timedelta
from typing import Literal, Optional

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Query, Request
from pymongo import MongoClient

from routes.operator_access import _is_admin as _is_operator_admin

load_dotenv()

_client = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
_db = _client[os.environ.get("DB_NAME", "test_database")]

_invoices       = _db.billing_invoices
_billing_audit  = _db.billing_audit
_operator_coll  = _db.operator_access
_operator_audit = _db.operator_access_audit

Window = Literal["7d", "30d", "90d"]
WINDOW_DAYS = {"7d": 7, "30d": 30, "90d": 90}

router = APIRouter(prefix="/api/admin/billing/analytics", tags=["billing-analytics"])


# ── Helpers ──────────────────────────────────────────────────────────


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _resolve_window(window: str) -> tuple[datetime, datetime, int]:
    if window not in WINDOW_DAYS:
        raise HTTPException(
            status_code=400,
            detail={"error": "INVALID_WINDOW", "supported": list(WINDOW_DAYS.keys())},
        )
    end = _now()
    days = WINDOW_DAYS[window]
    start = end - timedelta(days=days)
    return start, end, days


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _safe_div(num: float, den: float, default: float = 0.0) -> float:
    return (num / den) if den else default


def _pct(num: float, den: float) -> float:
    return round(_safe_div(num, den) * 100, 2)


# ── Section computations ────────────────────────────────────────────


def _revenue_block(start: datetime, end: datetime) -> dict:
    """Gross / refunded / net revenue inside the window.

    NOTE: refunds are not subtracted in `gross` — they are presented
    side-by-side.  This is the user-mandated dual-track invariant:
    analytics must never silently net out refunds.
    """
    start_iso, end_iso = _iso(start), _iso(end)
    # Paid in window
    paid_pipeline = [
        {"$match": {"status": "paid",
                    "paidAt": {"$gte": start_iso, "$lte": end_iso}}},
        {"$group": {"_id": "$productCode",
                    "count":   {"$sum": 1},
                    "revenue": {"$sum": "$priceUsd"}}},
    ]
    paid_rows = list(_invoices.aggregate(paid_pipeline))
    gross_count   = sum(r["count"] for r in paid_rows)
    gross_revenue = sum(r["revenue"] for r in paid_rows)

    # Also count invoices that were paid then refunded inside window
    # (so gross still reflects the original commercial event).
    paid_then_refunded = list(_invoices.aggregate([
        {"$match": {"status": "refunded",
                    "paidAt":     {"$gte": start_iso, "$lte": end_iso}}},
        {"$group": {"_id": None,
                    "count":   {"$sum": 1},
                    "revenue": {"$sum": "$priceUsd"}}},
    ]))
    if paid_then_refunded:
        gross_count   += paid_then_refunded[0]["count"]
        gross_revenue += paid_then_refunded[0]["revenue"]

    # Refunded in window (use refundedAt for refund-side timing)
    refunded_pipeline = [
        {"$match": {"status": "refunded",
                    "refundedAt": {"$gte": start_iso, "$lte": end_iso}}},
        {"$group": {"_id": "$productCode",
                    "count":   {"$sum": 1},
                    "revenue": {"$sum": "$priceUsd"}}},
    ]
    refunded_rows = list(_invoices.aggregate(refunded_pipeline))
    refunded_count   = sum(r["count"] for r in refunded_rows)
    refunded_revenue = sum(r["revenue"] for r in refunded_rows)

    net_revenue = gross_revenue - refunded_revenue

    return {
        "grossRevenue":     round(gross_revenue, 2),
        "grossPaidCount":   gross_count,
        "refundedRevenue":  round(refunded_revenue, 2),
        "refundedCount":    refunded_count,
        "netRevenue":       round(net_revenue, 2),
    }


def _mrr_block() -> dict:
    """Trailing-30-day NET revenue as a canonical MRR proxy.

    Products here are one-time invoice issuance (not recurring
    subscriptions), so this is intentionally an APPROXIMATION — the
    operator UI labels it as such.  Stays fixed at 30d regardless of
    the page's window selector so it remains a stable benchmark.
    """
    end = _now()
    start = end - timedelta(days=30)
    block = _revenue_block(start, end)
    return {
        "mrrApproxUsd":           block["netRevenue"],
        "trailingWindowDays":     30,
        "trailingGrossRevenue":   block["grossRevenue"],
        "trailingRefundedRevenue":block["refundedRevenue"],
    }


def _conversion_block(start: datetime, end: datetime) -> dict:
    """Funnel metrics on invoices CREATED within the window.

    created → paid → activated, plus failed/stuck rates.
    `stuck_pending` is independent of the user-mandated
    reconciliation threshold (24h) so the analytics surface can
    cross-reference it.
    """
    start_iso, end_iso = _iso(start), _iso(end)
    stuck_threshold = (_now() - timedelta(hours=24)).isoformat()

    pipeline = [
        {"$match": {"createdAt": {"$gte": start_iso, "$lte": end_iso}}},
        {"$group": {
            "_id": "$status",
            "count": {"$sum": 1},
            "stuckPending": {"$sum": {
                "$cond": [{"$and": [
                    {"$eq": ["$status", "pending"]},
                    {"$lt": ["$createdAt", stuck_threshold]},
                ]}, 1, 0]
            }},
        }},
    ]
    by_status = {r["_id"]: r for r in _invoices.aggregate(pipeline)}
    created_count   = sum(r["count"] for r in by_status.values())
    paid_count      = by_status.get("paid",      {}).get("count", 0)
    refunded_count  = by_status.get("refunded",  {}).get("count", 0)
    failed_count    = by_status.get("failed",    {}).get("count", 0)
    pending_count   = by_status.get("pending",   {}).get("count", 0)
    stuck_pending   = by_status.get("pending",   {}).get("stuckPending", 0)

    # paid+refunded both used to pass through the paid state once.
    monetized_count = paid_count + refunded_count

    # Activated: invoices where entitlement_activated audit event
    # exists.  We compute per the window's created invoices to keep
    # the funnel self-contained.
    activated_count = _billing_audit.count_documents({
        "action": "entitlement_activated",
        "invoiceId": {"$in": [
            d["invoiceId"] for d in _invoices.find(
                {"createdAt": {"$gte": start_iso, "$lte": end_iso}},
                {"invoiceId": 1, "_id": 0},
            )
        ]},
    })

    return {
        "createdCount":       created_count,
        "paidCount":          paid_count,
        "refundedCount":      refunded_count,
        "failedCount":        failed_count,
        "pendingCount":       pending_count,
        "stuckPendingCount":  stuck_pending,
        "activatedCount":     activated_count,
        "conversionRatePct":  _pct(monetized_count, created_count),  # paid+refunded ever
        "failureRatePct":     _pct(failed_count,    created_count),
        "stuckRatePct":       _pct(stuck_pending,   created_count),
        "activationRatePct":  _pct(activated_count, monetized_count),
    }


def _product_mix_block(start: datetime, end: datetime) -> dict:
    """PRO vs TRADER count + revenue + split."""
    start_iso, end_iso = _iso(start), _iso(end)
    rows = list(_invoices.aggregate([
        {"$match": {"status": {"$in": ["paid", "refunded"]},
                    "paidAt": {"$gte": start_iso, "$lte": end_iso}}},
        {"$group": {"_id": "$productCode",
                    "count": {"$sum": 1},
                    "grossRevenue": {"$sum": "$priceUsd"}}},
    ]))
    by_code = {r["_id"]: r for r in rows}
    pro = by_code.get("PRO", {"count": 0, "grossRevenue": 0.0})
    trader = by_code.get("TRADER", {"count": 0, "grossRevenue": 0.0})
    total_count = pro["count"] + trader["count"]
    total_rev = pro["grossRevenue"] + trader["grossRevenue"]
    return {
        "pro": {
            "count":       pro["count"],
            "grossRevenue": round(pro["grossRevenue"], 2),
            "countShare":  _pct(pro["count"], total_count),
            "revShare":    _pct(pro["grossRevenue"], total_rev),
        },
        "trader": {
            "count":       trader["count"],
            "grossRevenue": round(trader["grossRevenue"], 2),
            "countShare":  _pct(trader["count"], total_count),
            "revShare":    _pct(trader["grossRevenue"], total_rev),
        },
        "totalPaidPlusRefunded": total_count,
        "totalGrossRevenue":     round(total_rev, 2),
    }


def _refund_rate_block(start: datetime, end: datetime) -> dict:
    """Refund-rate breakdown — per product, in the window."""
    start_iso, end_iso = _iso(start), _iso(end)
    # All invoices that were paid (now paid OR now refunded) in window
    paid_ever = list(_invoices.aggregate([
        {"$match": {"paidAt": {"$gte": start_iso, "$lte": end_iso}}},
        {"$group": {"_id": "$productCode",
                    "paidCount":     {"$sum": 1},
                    "refundedCount": {"$sum": {"$cond": [{"$eq": ["$status", "refunded"]}, 1, 0]}}}}
    ]))
    by_code = {r["_id"]: r for r in paid_ever}
    pro     = by_code.get("PRO",    {"paidCount": 0, "refundedCount": 0})
    trader  = by_code.get("TRADER", {"paidCount": 0, "refundedCount": 0})
    pro_rate    = _pct(pro["refundedCount"],    pro["paidCount"])
    trader_rate = _pct(trader["refundedCount"], trader["paidCount"])
    total_paid     = pro["paidCount"] + trader["paidCount"]
    total_refunded = pro["refundedCount"] + trader["refundedCount"]
    overall_rate   = _pct(total_refunded, total_paid)
    return {
        "overallRefundRatePct": overall_rate,
        "pro":    {"paidCount": pro["paidCount"],    "refundedCount": pro["refundedCount"],    "refundRatePct": pro_rate},
        "trader": {"paidCount": trader["paidCount"], "refundedCount": trader["refundedCount"], "refundRatePct": trader_rate},
    }


def _churn_block(start: datetime, end: datetime) -> dict:
    """Churn semantics — dual-tracked.

    Refund-driven downgrade: a `downgrade` event in billing_audit.
    Voluntary downgrade: a set-tier event in operator_access_audit
        where before.tier in (pro, trader) and after.tier == 'free'
        AND actor != 'billing_system' (i.e. NOT the refund-system path).

    These two are NEVER merged into a single "churn" number — they're
    different operational stories.
    """
    start_iso, end_iso = _iso(start), _iso(end)

    # Refund-driven downgrades (commercial path)
    refund_down_pipeline = [
        {"$match": {"action": "downgrade",
                    "ts":     {"$gte": start_iso, "$lte": end_iso}}},
    ]
    refund_downs = list(_billing_audit.aggregate(refund_down_pipeline))
    refund_pro    = sum(1 for d in refund_downs if (d.get("before") or {}).get("tier") == "pro")
    refund_trader = sum(1 for d in refund_downs if (d.get("before") or {}).get("tier") == "trader")

    # Voluntary admin downgrades (governance path) — actor explicitly
    # NOT the billing_system shim that the refund flow uses.
    vol_match = {
        "action": "set-tier",
        "ts": {"$gte": start_iso, "$lte": end_iso},
        "actor": {"$ne": "billing_system"},
    }
    vol_pro = 0
    vol_trader = 0
    for ev in _operator_audit.find(vol_match, {"_id": 0, "before": 1, "after": 1}):
        before_tier = ((ev.get("before") or {}).get("tier")
                       or (ev.get("before") or {}).get("operatorAccess", {}).get("tier"))
        after_tier  = ((ev.get("after")  or {}).get("tier")
                       or (ev.get("after")  or {}).get("operatorAccess", {}).get("tier"))
        if after_tier == "free":
            if   before_tier == "pro":    vol_pro += 1
            elif before_tier == "trader": vol_trader += 1

    return {
        "refundDriven": {
            "proToFree":    refund_pro,
            "traderToFree": refund_trader,
            "total":        refund_pro + refund_trader,
        },
        "voluntary": {
            "proToFree":    vol_pro,
            "traderToFree": vol_trader,
            "total":        vol_pro + vol_trader,
        },
    }


# ── Endpoint ────────────────────────────────────────────────────────


@router.get("/summary")
def summary(
    request: Request,
    window: str = Query("30d", description="Rolling window: 7d, 30d, or 90d"),
):
    """Single derived snapshot powering the entire analytics surface.

    The whole block is computed on read — there is no materialized
    table.  Dataset is small enough at this stage; will evolve to a
    materialized snapshot once volume requires it.
    """
    if not _is_operator_admin(request):
        raise HTTPException(status_code=401, detail={"error": "ADMIN_REQUIRED"})
    start, end, days = _resolve_window(window)
    return {
        "ok": True,
        "window": window,
        "windowDays": days,
        "windowStart": _iso(start),
        "windowEnd":   _iso(end),
        "computedAt":  _iso(_now()),
        "revenue":     _revenue_block(start, end),
        "mrr":         _mrr_block(),
        "conversion":  _conversion_block(start, end),
        "productMix":  _product_mix_block(start, end),
        "refundRate":  _refund_rate_block(start, end),
        "churn":       _churn_block(start, end),
    }
