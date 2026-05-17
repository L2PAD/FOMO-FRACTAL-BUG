"""
Admin Billing Routes — Full billing/subscription control for admin panel.

Provides:
  - Overview KPIs (MRR, subscribers, revenue, churn)
  - Subscriber management (list, detail, filters)
  - Payment history
  - Billing event log (webhook journal)
  - Access control (grant/revoke/override)
"""
import os
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Request, HTTPException
from bson import ObjectId

router = APIRouter(prefix="/api/admin/billing", tags=["admin-billing"])

MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME", "intelligence_engine")


def _get_db():
    from motor.motor_asyncio import AsyncIOMotorClient
    return AsyncIOMotorClient(MONGO_URL)[DB_NAME]


def _serialize(doc):
    """Remove _id and convert ObjectId fields."""
    if not doc:
        return doc
    doc.pop("_id", None)
    for k, v in doc.items():
        if isinstance(v, ObjectId):
            doc[k] = str(v)
    return doc


# ─── Overview ─────────────────────────────────────────────────────

@router.get("/overview")
async def billing_overview():
    """Admin billing dashboard KPIs."""
    db = _get_db()
    now = datetime.now(timezone.utc)
    d30 = (now - timedelta(days=30)).isoformat()
    d7 = (now - timedelta(days=7)).isoformat()

    # User counts
    total_users = await db["users"].count_documents({})
    active_subs = await db["subscriptions"].count_documents({"status": "active"})
    past_due = await db["subscriptions"].count_documents({"status": "past_due"})
    canceled = await db["subscriptions"].count_documents({"status": "canceled"})
    free_users = total_users - active_subs - past_due

    # MRR from active subscriptions
    mrr_pipeline = [
        {"$match": {"status": "active"}},
        {"$group": {"_id": None, "total": {"$sum": {"$ifNull": ["$amount", 0]}}}},
    ]
    mrr_result = await db["subscriptions"].aggregate(mrr_pipeline).to_list(1)
    mrr = mrr_result[0]["total"] if mrr_result else 0

    # Revenue 30d
    rev_pipeline = [
        {"$match": {"payment_status": "paid", "created_at": {"$gte": d30}}},
        {"$group": {"_id": None, "total": {"$sum": {"$ifNull": ["$amount", 0]}}}},
    ]
    rev_result = await db["payments"].aggregate(rev_pipeline).to_list(1)
    revenue_30d = rev_result[0]["total"] if rev_result else 0
    # Fallback to payment_transactions if payments is empty
    if revenue_30d == 0:
        rev_result2 = await db["payment_transactions"].aggregate(rev_pipeline).to_list(1)
        revenue_30d = rev_result2[0]["total"] if rev_result2 else 0

    # Failed payments 7d
    failed_7d = await db["payments"].count_documents(
        {"status": "failed", "created_at": {"$gte": d7}}
    )
    if failed_7d == 0:
        failed_7d = await db["payment_transactions"].count_documents(
            {"payment_status": "failed", "created_at": {"$gte": d7}}
        )

    # Revenue daily (last 30 days)
    revenue_daily = []
    for i in range(30):
        day_start = (now - timedelta(days=29 - i)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        day_rev_pipeline = [
            {"$match": {
                "payment_status": {"$in": ["paid", "succeeded"]},
                "created_at": {"$gte": day_start.isoformat(), "$lt": day_end.isoformat()},
            }},
            {"$group": {"_id": None, "total": {"$sum": {"$ifNull": ["$amount", 0]}}}},
        ]
        day_result = await db["payments"].aggregate(day_rev_pipeline).to_list(1)
        if not day_result:
            day_result = await db["payment_transactions"].aggregate(day_rev_pipeline).to_list(1)
        revenue_daily.append({
            "date": day_start.strftime("%Y-%m-%d"),
            "revenue": day_result[0]["total"] if day_result else 0,
        })

    # New subscribers (last 30d)
    new_subs_30d = await db["subscriptions"].count_documents(
        {"created_at": {"$gte": d30}}
    )

    # Plan status distribution
    plan_distribution = {
        "active": active_subs,
        "free": max(free_users, 0),
        "past_due": past_due,
        "canceled": canceled,
    }

    # Payment method distribution
    card_count = await db["payment_transactions"].count_documents(
        {"payment_status": {"$in": ["paid", "succeeded"]}, "payment_method": {"$ne": "crypto"}}
    )
    crypto_count = await db["payment_transactions"].count_documents(
        {"payment_status": {"$in": ["paid", "succeeded"]}, "payment_method": "crypto"}
    )
    payment_methods = {"card": card_count, "crypto": crypto_count}

    # Recent payments
    recent_payments_cursor = db["payment_transactions"].find(
        {}, {"_id": 0}
    ).sort("created_at", -1).limit(20)
    recent_payments = await recent_payments_cursor.to_list(20)

    # At-risk users (past_due or expiring in 3 days)
    expiring_soon = (now + timedelta(days=3)).isoformat()
    at_risk_cursor = db["subscriptions"].find(
        {"$or": [
            {"status": "past_due"},
            {"status": "active", "current_period_end": {"$lte": expiring_soon}, "cancel_at_period_end": True},
        ]},
        {"_id": 0},
    ).limit(20)
    at_risk_subs = await at_risk_cursor.to_list(20)

    # Enrich at-risk with user info
    at_risk = []
    for sub in at_risk_subs:
        user = await db["users"].find_one({"user_id": sub.get("user_id")}, {"_id": 0, "user_id": 1, "email": 1, "name": 1})
        at_risk.append({**sub, "user": user or {}})

    # Conversion rate
    paid_ever = await db["subscriptions"].count_documents({})
    conversion_rate = round(paid_ever / max(total_users, 1) * 100, 1)

    # Subscriber growth daily (last 30 days)
    subscriber_growth = []
    for i in range(30):
        day_end = (now - timedelta(days=29 - i)).replace(hour=23, minute=59, second=59)
        count = await db["subscriptions"].count_documents(
            {"created_at": {"$lte": day_end.isoformat()}, "status": {"$in": ["active", "past_due"]}}
        )
        subscriber_growth.append({
            "date": day_end.strftime("%Y-%m-%d"),
            "subscribers": count,
        })

    # Refunds summary
    refunds_count = await db["billing_events"].count_documents({"event_type": "refund"})
    refunds_pipeline = [
        {"$match": {"event_type": "refund"}},
        {"$group": {"_id": None, "total": {"$sum": {"$ifNull": ["$amount", 0]}}}},
    ]
    refunds_result = await db["billing_events"].aggregate(refunds_pipeline).to_list(1)
    total_refunded = refunds_result[0]["total"] if refunds_result else 0

    return {
        "ok": True,
        "kpis": {
            "total_users": total_users,
            "active_subscribers": active_subs,
            "free_users": max(free_users, 0),
            "past_due": past_due,
            "canceled": canceled,
            "mrr": mrr,
            "arr_run_rate": mrr * 12,
            "revenue_30d": revenue_30d,
            "failed_payments_7d": failed_7d,
            "new_subscribers_30d": new_subs_30d,
            "conversion_rate": conversion_rate,
            "total_refunds": refunds_count,
            "total_refunded": total_refunded,
        },
        "charts": {
            "revenue_daily": revenue_daily,
            "subscriber_growth": subscriber_growth,
            "plan_distribution": plan_distribution,
            "payment_methods": payment_methods,
        },
        "recent_payments": recent_payments,
        "at_risk": at_risk,
    }


# ─── Subscribers ──────────────────────────────────────────────────

@router.get("/subscribers")
async def list_subscribers(
    status: str = "all",
    limit: int = 50,
    offset: int = 0,
    search: str = "",
):
    """List all users with billing info."""
    db = _get_db()

    user_filter = {}
    if status == "active":
        user_filter["plan_status"] = "active"
    elif status == "free":
        user_filter["plan_status"] = {"$in": ["free", None]}
    elif status == "past_due":
        user_filter["plan_status"] = "past_due"
    elif status == "canceled":
        user_filter["plan_status"] = "canceled"

    if search:
        user_filter["$or"] = [
            {"email": {"$regex": search, "$options": "i"}},
            {"name": {"$regex": search, "$options": "i"}},
        ]

    total = await db["users"].count_documents(user_filter)
    users_cursor = db["users"].find(
        user_filter, {"_id": 0}
    ).sort("created_at", -1).skip(offset).limit(limit)
    users = await users_cursor.to_list(limit)

    # Enrich with subscription data
    result = []
    for u in users:
        sub = await db["subscriptions"].find_one(
            {"user_id": u.get("user_id")}, {"_id": 0}
        )
        last_payment = await db["payment_transactions"].find_one(
            {"user_id": u.get("user_id"), "payment_status": {"$in": ["paid", "succeeded"]}},
            {"_id": 0},
            sort=[("created_at", -1)],
        )
        result.append({
            "user_id": u.get("user_id"),
            "email": u.get("email"),
            "name": u.get("name"),
            "picture": u.get("picture"),
            "auth_provider": u.get("auth_provider", "google"),
            "plan_status": u.get("plan_status", "free"),
            "crypto_customer_id": u.get("crypto_customer_id"),
            "created_at": u.get("created_at"),
            "last_login_at": u.get("last_login_at"),
            "subscription": sub,
            "last_payment": {
                "amount": last_payment.get("amount") if last_payment else None,
                "payment_method": last_payment.get("payment_method", "card") if last_payment else None,
                "created_at": last_payment.get("created_at") if last_payment else None,
            } if last_payment else None,
        })

    return {"ok": True, "total": total, "subscribers": result}


@router.get("/subscribers/{user_id}")
async def subscriber_detail(user_id: str):
    """Get detailed subscriber info with payments + subscription + access."""
    db = _get_db()

    user = await db["users"].find_one({"user_id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(404, "User not found")

    sub = await db["subscriptions"].find_one({"user_id": user_id}, {"_id": 0})

    payments_cursor = db["payment_transactions"].find(
        {"user_id": user_id}, {"_id": 0}
    ).sort("created_at", -1).limit(50)
    payments = await payments_cursor.to_list(50)

    events_cursor = db["billing_events"].find(
        {"user_id": user_id}, {"_id": 0}
    ).sort("created_at", -1).limit(30)
    events = await events_cursor.to_list(30)

    # Access state
    plan = user.get("plan_status", "free")
    override = user.get("access_override_status")
    has_access = plan == "active" or override == "granted"
    if override == "revoked":
        has_access = False

    return {
        "ok": True,
        "user": user,
        "subscription": sub,
        "payments": payments,
        "events": events,
        "access": {
            "has_access": has_access,
            "plan_status": plan,
            "override_status": override,
            "override_reason": user.get("override_reason"),
            "override_expires_at": user.get("override_expires_at"),
        },
    }


# ─── Payments ─────────────────────────────────────────────────────

@router.get("/payments")
async def list_payments(
    status: str = "all",
    method: str = "all",
    limit: int = 50,
    offset: int = 0,
):
    """List all payment transactions."""
    db = _get_db()

    pay_filter = {}
    if status == "paid":
        pay_filter["payment_status"] = {"$in": ["paid", "succeeded"]}
    elif status == "failed":
        pay_filter["payment_status"] = "failed"
    elif status == "initiated":
        pay_filter["payment_status"] = "initiated"

    if method == "card":
        pay_filter["payment_method"] = {"$ne": "crypto"}
    elif method == "crypto":
        pay_filter["payment_method"] = "crypto"

    total = await db["payment_transactions"].count_documents(pay_filter)
    cursor = db["payment_transactions"].find(
        pay_filter, {"_id": 0}
    ).sort("created_at", -1).skip(offset).limit(limit)
    payments = await cursor.to_list(limit)

    # Enrich with user email
    for p in payments:
        if not p.get("email") and p.get("user_id"):
            user = await db["users"].find_one({"user_id": p["user_id"]}, {"_id": 0, "email": 1})
            p["email"] = user.get("email") if user else None

    return {"ok": True, "total": total, "payments": payments}


# ─── Billing Events ──────────────────────────────────────────────

@router.get("/events")
async def list_billing_events(limit: int = 50, offset: int = 0):
    """List webhook/billing events."""
    db = _get_db()
    total = await db["billing_events"].count_documents({})
    cursor = db["billing_events"].find(
        {}, {"_id": 0}
    ).sort("created_at", -1).skip(offset).limit(limit)
    events = await cursor.to_list(limit)
    return {"ok": True, "total": total, "events": events}


# ─── Access Control ───────────────────────────────────────────────

@router.post("/access/{user_id}/grant")
async def grant_access(user_id: str, request: Request):
    """Admin grant access to user."""
    db = _get_db()
    body = await request.json()
    reason = body.get("reason", "Admin grant")
    days = body.get("days", 30)
    expires = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()

    result = await db["users"].update_one(
        {"user_id": user_id},
        {"$set": {
            "plan_status": "active",
            "access_override_status": "granted",
            "override_reason": reason,
            "override_expires_at": expires,
            "override_set_at": datetime.now(timezone.utc).isoformat(),
        }},
    )
    if result.matched_count == 0:
        raise HTTPException(404, "User not found")

    await db["billing_events"].insert_one({
        "event_id": f"evt_admin_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "type": "access_granted",
        "source": "admin",
        "user_id": user_id,
        "payload": {"reason": reason, "days": days, "expires_at": expires},
        "processed": True,
        "error": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    return {"ok": True, "message": f"Access granted for {days} days"}


@router.post("/access/{user_id}/revoke")
async def revoke_access(user_id: str, request: Request):
    """Admin revoke access from user."""
    db = _get_db()
    body = await request.json()
    reason = body.get("reason", "Admin revoke")

    result = await db["users"].update_one(
        {"user_id": user_id},
        {"$set": {
            "plan_status": "free",
            "access_override_status": "revoked",
            "override_reason": reason,
            "override_set_at": datetime.now(timezone.utc).isoformat(),
        }},
    )
    if result.matched_count == 0:
        raise HTTPException(404, "User not found")

    await db["billing_events"].insert_one({
        "event_id": f"evt_admin_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "type": "access_revoked",
        "source": "admin",
        "user_id": user_id,
        "payload": {"reason": reason},
        "processed": True,
        "error": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    return {"ok": True, "message": "Access revoked"}


# ─── Subscriptions Management ─────────────────────────────────────

@router.get("/subscriptions")
async def list_subscriptions(status: str = "all", limit: int = 50, offset: int = 0):
    """List all subscriptions."""
    db = _get_db()
    sub_filter = {}
    if status != "all":
        sub_filter["status"] = status

    total = await db["subscriptions"].count_documents(sub_filter)
    cursor = db["subscriptions"].find(
        sub_filter, {"_id": 0}
    ).sort("created_at", -1).skip(offset).limit(limit)
    subs = await cursor.to_list(limit)

    for s in subs:
        user = await db["users"].find_one({"user_id": s.get("user_id")}, {"_id": 0, "email": 1, "name": 1})
        s["user"] = user or {}

    return {"ok": True, "total": total, "subscriptions": subs}


# ─── NOWPayments Keys Configuration ─────────────────────────────────────

@router.get("/nowpayments-keys")
async def get_nowpayments_keys():
    """Get NOWPayments keys (masked for security)."""
    db = _get_db()
    config = await db["billing_config"].find_one({"type": "nowpayments_keys"}, {"_id": 0})
    sk = config.get("nowpayments_secret_key", "") if config else os.environ.get("NOWPAYMENTS_API_KEY", "")
    pk = config.get("nowpayments_publishable_key", "") if config else ""
    return {
        "ok": True,
        "keys": {
            "nowpayments_secret_key_masked": f"{sk[:7]}...{sk[-4:]}" if len(sk) > 11 else ("*" * len(sk) if sk else ""),
            "nowpayments_publishable_key_masked": f"{pk[:7]}...{pk[-4:]}" if len(pk) > 11 else ("*" * len(pk) if pk else ""),
            "has_secret_key": bool(sk),
            "has_publishable_key": bool(pk),
        },
    }


@router.put("/nowpayments-keys")
async def update_nowpayments_keys(request: Request):
    """Update NOWPayments API keys. Stored in DB billing_config."""
    body = await request.json()
    db = _get_db()

    update_fields = {"type": "nowpayments_keys", "updated_at": datetime.now(timezone.utc).isoformat()}
    sk = body.get("nowpayments_secret_key")
    pk = body.get("nowpayments_publishable_key")

    if sk and sk.startswith("sk_"):
        update_fields["nowpayments_secret_key"] = sk
    if pk and pk.startswith("pk_"):
        update_fields["nowpayments_publishable_key"] = pk

    await db["billing_config"].update_one(
        {"type": "nowpayments_keys"},
        {"$set": update_fields},
        upsert=True,
    )

    # Log event
    await db["billing_events"].insert_one({
        "type": "nowpayments_keys_updated",
        "source": "admin",
        "payload": {"has_sk": bool(sk), "has_pk": bool(pk)},
        "processed": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    return {"ok": True, "message": "NOWPayments keys updated"}


# ─── Pricing Configuration ────────────────────────────────────────

DEFAULT_PRICING = {
    "billing_mode": "paid",              # "free_trial" or "paid"
    "free_trial_days": 3,
    "monthly_card_cents": 100,           # $1.00/mo (test)
    "yearly_card_cents": 1000,           # $10.00/yr (test)
    "monthly_crypto_dollars": 1.00,      # $1.00/mo USDC
    "yearly_crypto_dollars": 10.00,      # $10.00/yr USDC
    "yearly_discount_percent": 15,       # Display: "Save 15%"
    "free_access_enabled": False,
    "paywall_enabled": True,             # Show paywall overlay for free users
    "product_name": "FOMO Intelligence PRO",
    "nowpayments_monthly_price_id": None,
    "nowpayments_yearly_price_id": None,
}


@router.get("/pricing")
async def get_pricing():
    """Get current pricing configuration."""
    db = _get_db()
    config = await db["billing_config"].find_one({"type": "pricing"}, {"_id": 0})
    if not config:
        config = {**DEFAULT_PRICING, "type": "pricing"}
    else:
        # Merge with defaults to include new fields
        merged = {**DEFAULT_PRICING, **config}
        config = merged
    return {"ok": True, "pricing": config}


@router.put("/pricing")
async def update_pricing(request: Request):
    """Update pricing configuration."""
    body = await request.json()
    db = _get_db()
    
    current = await db["billing_config"].find_one({"type": "pricing"}, {"_id": 0})
    if not current:
        current = {**DEFAULT_PRICING, "type": "pricing"}
    
    monthly_card = body.get("monthly_card_cents", current.get("monthly_card_cents", 100))
    yearly_card = body.get("yearly_card_cents", current.get("yearly_card_cents", 1000))
    monthly_crypto = body.get("monthly_crypto_dollars", current.get("monthly_crypto_dollars", 1.0))
    yearly_crypto = body.get("yearly_crypto_dollars", current.get("yearly_crypto_dollars", 10.0))
    discount_pct = body.get("yearly_discount_percent", current.get("yearly_discount_percent", 15))
    free_enabled = body.get("free_access_enabled", current.get("free_access_enabled", False))
    paywall_enabled = body.get("paywall_enabled", current.get("paywall_enabled", True))
    product_name = body.get("product_name", current.get("product_name", "FOMO Intelligence PRO"))
    billing_mode = body.get("billing_mode", current.get("billing_mode", "paid"))
    free_trial_days = body.get("free_trial_days", current.get("free_trial_days", 3))
    
    if billing_mode not in ("free_trial", "paid", "crypto"):
        raise HTTPException(400, "billing_mode must be 'free_trial', 'paid' or 'crypto'")
    
    # Save to DB
    update_doc = {
        "type": "pricing",
        "billing_mode": billing_mode,
        "free_trial_days": int(free_trial_days),
        "monthly_card_cents": int(monthly_card),
        "yearly_card_cents": int(yearly_card),
        "monthly_crypto_dollars": float(monthly_crypto),
        "yearly_crypto_dollars": float(yearly_crypto),
        "yearly_discount_percent": int(discount_pct),
        "free_access_enabled": bool(free_enabled),
        "paywall_enabled": bool(paywall_enabled),
        "product_name": product_name,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    
    await db["billing_config"].update_one(
        {"type": "pricing"},
        {"$set": update_doc},
        upsert=True,
    )
    
    # Log event
    await db["billing_events"].insert_one({
        "type": "pricing_updated",
        "source": "admin",
        "payload": {
            "monthly_card_cents": int(monthly_card),
            "yearly_card_cents": int(yearly_card),
            "monthly_crypto_dollars": float(monthly_crypto),
            "yearly_crypto_dollars": float(yearly_crypto),
            "yearly_discount_percent": int(discount_pct),
            "free_access_enabled": bool(free_enabled),
            "paywall_enabled": bool(paywall_enabled),
        },
        "processed": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    
    return {"ok": True, "pricing": {k: v for k, v in update_doc.items() if k != "_id"}}


# ─── Refund Management ───────────────────────────────────────────

@router.post("/refund")
async def process_refund(request: Request):
    """Process a manual refund for a user."""
    body = await request.json()
    user_id = body.get("user_id", "").strip()
    amount = body.get("amount", 0)
    reason = body.get("reason", "Admin refund")

    if not user_id:
        raise HTTPException(400, "user_id required")

    db = _get_db()
    user = await db["users"].find_one({"user_id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(404, "User not found")

    # Record refund event
    await db["billing_events"].insert_one({
        "event_type": "refund",
        "user_id": user_id,
        "email": user.get("email", ""),
        "amount": float(amount),
        "reason": reason,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    return {"ok": True, "refunded": float(amount), "user_id": user_id}


@router.get("/refunds")
async def list_refunds():
    """Get all refunds."""
    db = _get_db()
    refunds = []
    async for r in db["billing_events"].find(
        {"event_type": "refund"}, {"_id": 0}
    ).sort("created_at", -1).limit(100):
        refunds.append(r)
    return {"ok": True, "refunds": refunds}
