"""
Billing routes — Stripe subscription management.

Uses emergentintegrations for checkout + raw stripe for subscriptions/portal.
Price is defined by STRIPE_PRICE_ID env var (not hardcoded).
Supports card + crypto (USDC stablecoin) payments.

DEV: $1/month (FOMO Intelligence TEST)
PROD: $99/month (FOMO Intelligence)
"""
import os
import uuid
import stripe
from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException
from emergentintegrations.payments.stripe.checkout import (
    StripeCheckout, CheckoutSessionRequest,
)

router = APIRouter(prefix="/api/billing", tags=["billing"])

MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME", "intelligence_engine")
STRIPE_API_KEY = os.environ.get("STRIPE_API_KEY", "")

stripe.api_key = STRIPE_API_KEY
# Route through Emergent proxy when using the test key
if "sk_test_emergent" in STRIPE_API_KEY:
    stripe.api_base = "https://integrations.emergentagent.com/stripe"


def _get_db():
    from motor.motor_asyncio import AsyncIOMotorClient
    return AsyncIOMotorClient(MONGO_URL)[DB_NAME]


async def _get_current_user(request: Request) -> dict:
    """
    P0: Get authenticated user from EITHER:
      1) Emergent session_token (cookie or Bearer → user_sessions collection)
      2) Unified JWT access token (Bearer → decode HS256 with JWT_ACCESS_SECRET)
    Raises HTTPException(401) if neither works.
    """
    import os as _os
    # 1) Try Emergent session path first (existing behaviour)
    try:
        from auth_routes import _get_current_user as auth_get_user
        u = await auth_get_user(request)
        if u and u.get("user_id"):
            return u
    except Exception:
        pass

    # 2) Fallback: decode Unified JWT from Authorization: Bearer ...
    auth_header = request.headers.get("Authorization", "")
    token = ""
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
    if token:
        try:
            import jwt as _jwt
            secret = _os.getenv("JWT_ACCESS_SECRET", "")
            if secret:
                payload = _jwt.decode(token, secret, algorithms=["HS256"])
                uid = payload.get("sub") or payload.get("user_id") or payload.get("_id")
                if uid:
                    db = _get_db()
                    user = await db["users"].find_one(
                        {"$or": [{"user_id": uid}, {"_id": uid}]}, {"_id": 0}
                    )
                    if user:
                        # Normalize — ensure user_id key exists
                        if not user.get("user_id"):
                            user["user_id"] = uid
                        return user
                    # Bare payload is still acceptable for paywall gating if we
                    # can't find a user row (defensive).
                    return {"user_id": uid, "email": payload.get("email", "")}
        except Exception:
            pass

    raise HTTPException(401, "Not authenticated")


# ─── P0: Identity Gate — hard requirement before any checkout ───
async def _require_authenticated_user(request: Request) -> dict:
    """
    HARD GATE: returns user or raises 401 with a structured AUTH_REQUIRED
    response. No anonymous / email-only / tg-only fallbacks allowed here.
    Every checkout MUST be attached to a known `user_id`.
    """
    try:
        user = await _get_current_user(request)
    except HTTPException:
        raise HTTPException(
            status_code=401,
            detail={"ok": False, "error": "AUTH_REQUIRED", "action": "open_auth_modal"},
        )
    if not user or not user.get("user_id"):
        raise HTTPException(
            status_code=401,
            detail={"ok": False, "error": "AUTH_REQUIRED", "action": "open_auth_modal"},
        )
    return user


async def _record_checkout_session(
    user: dict,
    provider: str,
    plan: str,
    surface: str,
    provider_checkout_id: str = "",
    extra: dict = None,
):
    """Write an audit record for every checkout session started."""
    db = _get_db()
    rec = {
        "session_id": provider_checkout_id or f"local_{uuid.uuid4().hex[:12]}",
        "user_id": user.get("user_id", ""),
        "email": user.get("email", ""),
        "provider": provider,
        "plan": plan,
        "platform": "web",
        "source_surface": surface or "unknown",
        "provider_checkout_id": provider_checkout_id or None,
        "status": "started",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if extra:
        rec.update(extra)
    try:
        await db["checkout_sessions"].insert_one(rec)
    except Exception:
        pass
    return rec


async def _ensure_stripe_customer(user: dict) -> str:
    """Get or create Stripe customer for user."""
    db = _get_db()
    if user.get("stripe_customer_id"):
        return user["stripe_customer_id"]

    customer = stripe.Customer.create(
        email=user["email"],
        name=user.get("name", ""),
        metadata={"user_id": user["user_id"]},
    )

    await db["users"].update_one(
        {"user_id": user["user_id"]},
        {"$set": {"stripe_customer_id": customer.id}},
    )
    return customer.id


PRODUCT_IMAGE_URL = "https://static.prod-images.emergentagent.com/jobs/df7924bb-3513-434f-9ac1-a36539ed9016/images/cd908b9f645ee69f597f94f389a3d897dcd812d2e4fb0fcab448e8ff0511af75.png"


async def _get_or_create_price(interval: str = "month") -> str:
    """Get subscription price ID from DB config, env, or create one."""
    db = _get_db()
    config = await db["billing_config"].find_one({"type": "pricing"})
    
    # 1. Check DB config first
    if config:
        if interval == "year" and config.get("stripe_yearly_price_id"):
            return config["stripe_yearly_price_id"]
        if interval == "month" and config.get("stripe_monthly_price_id"):
            return config["stripe_monthly_price_id"]
    
    # 2. Check env var (monthly only)
    if interval == "month":
        price_id = os.environ.get("STRIPE_PRICE_ID")
        if price_id:
            return price_id

    # 3. Create product + price
    amount = 100  # default $1.00/mo
    product_name = "FOMO Intelligence PRO"
    if config:
        if interval == "year":
            amount = int(config.get("yearly_card_cents", 1000))
        else:
            amount = int(config.get("monthly_card_cents", 100))
        product_name = config.get("product_name", product_name)
    
    product = stripe.Product.create(
        name=product_name,
        description="Crypto Decision Intelligence — Prediction Engine, Exchange Analytics, On-chain Data, MetaBrain, Signal Alerts",
        images=[PRODUCT_IMAGE_URL],
    )
    price = stripe.Price.create(
        product=product.id,
        unit_amount=amount,
        currency="usd",
        recurring={"interval": interval},
    )

    # Store for reuse
    price_field = "stripe_yearly_price_id" if interval == "year" else "stripe_monthly_price_id"
    if interval == "month":
        os.environ["STRIPE_PRICE_ID"] = price.id
    await db["billing_config"].update_one(
        {"type": "pricing"},
        {"$set": {price_field: price.id, "stripe_product_id": product.id}},
        upsert=True,
    )
    return price.id


@router.post("/apply-referral")
async def apply_referral_code(request: Request):
    """Apply a referral code to the current user's account. Stores it for checkout."""
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(401, "Not authenticated")

    body = await request.json()
    code = body.get("code", "").strip().upper()
    if not code:
        raise HTTPException(400, "code required")

    db = _get_db()
    promo = await db["promo_codes"].find_one({"code": code}, {"_id": 0})

    if not promo:
        return {"ok": False, "error": "Invalid referral code"}

    if promo.get("used_by"):
        return {"ok": False, "error": "Code already used"}

    # Store referral info on user for next checkout
    await db["users"].update_one(
        {"user_id": user["user_id"]},
        {"$set": {
            "pending_referral_code": code,
            "referral_discount": promo.get("discount_percent", 0),
        }}
    )

    return {
        "ok": True,
        "discount_percent": promo.get("discount_percent", 0),
        "group_name": promo.get("group_id", ""),
    }


@router.post("/create-checkout")
async def create_checkout(request: Request):
    """Create NOWPayments invoice for subscription.
    
    P0: HARD GATE — authentication is required. Any caller without a valid
    user_id gets 401 AUTH_REQUIRED. No anonymous / email-only / tg fallbacks.
    """
    user = await _require_authenticated_user(request)

    body = await request.json()
    interval = body.get("interval", "month")
    surface = body.get("source_surface", body.get("surface", "web_paywall"))

    # P0: order_id is ALWAYS the canonical user_id. Never anon_* / email:* / tg_*.
    order_id = user["user_id"]

    from services.payments.wallet_service import create_invoice
    result = await create_invoice(order_id, interval=interval)

    if result.get("invoice_url"):
        # P0: audit trail — every started checkout recorded to checkout_sessions.
        await _record_checkout_session(
            user=user,
            provider="nowpayments",
            plan=interval,
            surface=surface,
            provider_checkout_id=result.get("invoice_id", ""),
        )
        return {"ok": True, "url": result["invoice_url"], "invoice_id": result.get("invoice_id")}
    return {"ok": False, "error": result.get("error", "Failed to create invoice")}


# ─── Crypto (USDC) Checkout ──────────────────────────────────────

async def _get_crypto_amount(interval: str = "month") -> float:
    """Get crypto subscription amount from DB config or env."""
    db = _get_db()
    config = await db["billing_config"].find_one({"type": "pricing"})
    if config:
        if interval == "year":
            return float(config.get("yearly_crypto_dollars", 10.00))
        return float(config.get("monthly_crypto_dollars", 1.00))
    return float(os.environ.get("CRYPTO_SUBSCRIPTION_AMOUNT", "1.00"))


@router.post("/create-crypto-checkout")
async def create_crypto_checkout(request: Request):
    """Create NOWPayments invoice for crypto (USDC) payment.
    
    P0: HARD GATE — authentication is required. No anon / email / tg fallbacks.
    """
    user = await _require_authenticated_user(request)

    body = await request.json()
    interval = body.get("interval", "month")
    surface = body.get("source_surface", body.get("surface", "web_crypto_paywall"))

    # P0: order_id is ALWAYS the canonical user_id.
    order_id = user["user_id"]

    from services.payments.wallet_service import create_invoice
    result = await create_invoice(order_id, interval=interval)

    if result.get("invoice_url"):
        await _record_checkout_session(
            user=user,
            provider="nowpayments_crypto",
            plan=interval,
            surface=surface,
            provider_checkout_id=result.get("invoice_id", ""),
        )
        return {"ok": True, "url": result["invoice_url"], "invoice_id": result.get("invoice_id")}
    return {"ok": False, "error": result.get("error", "Failed to create invoice")}


@router.get("/crypto-checkout-status/{session_id}")
async def get_crypto_checkout_status(session_id: str, request: Request):
    """Poll crypto checkout session status."""
    user = await _get_current_user(request)
    db = _get_db()

    # Prevent duplicate processing
    existing = await db["payment_transactions"].find_one(
        {"session_id": session_id, "payment_status": "paid"}, {"_id": 0}
    )
    if existing:
        return {
            "ok": True,
            "status": "complete",
            "payment_status": "paid",
            "already_processed": True,
        }

    # Retrieve session directly from Stripe
    session = stripe.checkout.Session.retrieve(session_id)

    # Update transaction
    await db["payment_transactions"].update_one(
        {"session_id": session_id},
        {"$set": {
            "payment_status": session.payment_status or "unknown",
            "status": session.status,
            "amount": session.amount_total / 100 if session.amount_total else None,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
    )

    if session.payment_status == "paid":
        user_id = (session.metadata or {}).get("user_id", user["user_id"])
        await _activate_crypto_subscription(user_id)

    return {
        "ok": True,
        "status": session.status,
        "payment_status": session.payment_status,
    }


async def _activate_crypto_subscription(user_id: str):
    """Activate subscription from crypto payment (30-day access)."""
    db = _get_db()
    from datetime import timedelta

    period_end = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()

    await db["subscriptions"].update_one(
        {"user_id": user_id},
        {"$set": {
            "user_id": user_id,
            "status": "active",
            "payment_method": "crypto_usdc",
            "current_period_end": period_end,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )

    await db["users"].update_one(
        {"user_id": user_id},
        {"$set": {"plan_status": "active"}},
    )


@router.post("/webhook/crypto")
async def crypto_webhook(request: Request):
    """Handle Stripe webhook for crypto payments."""
    body = await request.body()
    sig_header = request.headers.get("Stripe-Signature", "")
    db = _get_db()

    host_url = str(request.base_url).rstrip("/")
    webhook_url = f"{host_url}/api/billing/webhook/crypto"

    stripe_checkout = StripeCheckout(
        api_key=STRIPE_API_KEY,
        webhook_url=webhook_url,
    )

    try:
        webhook_response = await stripe_checkout.handle_webhook(body, sig_header)

        if webhook_response.payment_status == "paid":
            session_id = webhook_response.session_id
            # Prevent duplicate processing
            existing = await db["payment_transactions"].find_one(
                {"session_id": session_id, "payment_status": "paid"}, {"_id": 0}
            )
            if not existing:
                await db["payment_transactions"].update_one(
                    {"session_id": session_id},
                    {"$set": {
                        "payment_status": "paid",
                        "status": "complete",
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }},
                )
                user_id = webhook_response.metadata.get("user_id", "")
                if user_id:
                    await _activate_crypto_subscription(user_id)

        return {"ok": True}
    except Exception as e:
        import logging
        logging.getLogger("billing").error(f"Crypto webhook error: {e}")
        return {"ok": True}


@router.get("/plans")
async def get_plans():
    """Get available subscription plans and pricing (public)."""
    db = _get_db()
    config = await db["billing_config"].find_one({"type": "pricing"}, {"_id": 0})
    keys_config = await db["billing_config"].find_one({"type": "stripe_keys"}, {"_id": 0})
    
    monthly_card = 100
    yearly_card = 1000
    monthly_crypto = 1.00
    yearly_crypto = 10.00
    discount = 15
    free_enabled = False
    paywall_enabled = True
    product_name = "FOMO Intelligence PRO"
    billing_mode = "paid"
    free_trial_days = 3
    
    if config:
        monthly_card = config.get("monthly_card_cents", 100)
        yearly_card = config.get("yearly_card_cents", 1000)
        monthly_crypto = config.get("monthly_crypto_dollars", 1.00)
        yearly_crypto = config.get("yearly_crypto_dollars", 10.00)
        discount = config.get("yearly_discount_percent", 15)
        free_enabled = config.get("free_access_enabled", False)
        paywall_enabled = config.get("paywall_enabled", True)
        product_name = config.get("product_name", "FOMO Intelligence PRO")
        billing_mode = config.get("billing_mode", "paid")
        free_trial_days = config.get("free_trial_days", 3)
    
    has_publishable_key = bool(keys_config and keys_config.get("stripe_publishable_key"))

    # ─── Task 6 (Honest Crypto-Only Sprint · 2026-05-12) ──────────────
    # Replace the loose `has_publishable_key` boolean with a coherent
    # `paymentMethods` envelope so the UI never has to interpret a half-
    # configured payment surface. The legacy key is kept for backwards
    # compatibility with older clients but the canonical signal is now
    # `paymentMethods.mode` / `paymentMethods.availableMethods`.
    from services.billing.payment_methods import compute_payment_methods
    payment_methods = compute_payment_methods(
        stripe_configured=has_publishable_key,
        crypto_configured=True,  # NOWPayments rail is the default; reflect
                                 # honestly here if it's ever taken offline.
    )

    return {
        "ok": True,
        "plans": {
            "billing_mode": billing_mode,
            "free_trial_days": free_trial_days,
            "free_access_enabled": free_enabled,
            "paywall_enabled": paywall_enabled,
            "product_name": product_name,
            "has_publishable_key": has_publishable_key,
            "paymentMethods": payment_methods,
            "monthly": {
                "card_price": monthly_card / 100,
                "crypto_price": monthly_crypto,
                "interval": "month",
                "currency": "usd",
            },
            "yearly": {
                "card_price": yearly_card / 100,
                "crypto_price": yearly_crypto,
                "interval": "year",
                "currency": "usd",
                "discount_percent": discount,
                "monthly_equivalent": round(yearly_card / 12 / 100, 2),
            },
        },
    }



@router.get("/status")
async def get_billing_status(request: Request):
    """Get current subscription status for the user."""
    user = await _get_current_user(request)
    db = _get_db()

    sub = await db["subscriptions"].find_one(
        {"user_id": user["user_id"]}, {"_id": 0}
    )

    if not sub or sub.get("status") not in ("active", "trialing"):
        return {
            "ok": True,
            "subscribed": False,
            "plan_status": "free",
            "subscription": None,
        }

    return {
        "ok": True,
        "subscribed": True,
        "plan_status": "active",
        "subscription": {
            "status": sub.get("status"),
            "current_period_end": sub.get("current_period_end"),
            "stripe_subscription_id": sub.get("stripe_subscription_id"),
        },
    }


@router.get("/checkout-status/{session_id}")
async def get_checkout_status(session_id: str, request: Request):
    """Check Stripe checkout session status."""
    user = await _get_current_user(request)
    db = _get_db()

    session = stripe.checkout.Session.retrieve(session_id)

    # Update transaction
    await db["payment_transactions"].update_one(
        {"session_id": session_id},
        {"$set": {
            "payment_status": session.payment_status or "unknown",
            "status": session.status,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
    )

    if session.payment_status == "paid" and session.status == "complete":
        # Activate subscription
        sub_id = session.subscription
        if sub_id:
            stripe_sub = stripe.Subscription.retrieve(sub_id)
            await _activate_subscription(user["user_id"], stripe_sub)

    return {
        "ok": True,
        "status": session.status,
        "payment_status": session.payment_status,
    }


async def _activate_subscription(user_id: str, stripe_sub):
    """Create/update subscription record and user plan_status."""
    db = _get_db()

    period_end = datetime.fromtimestamp(
        stripe_sub.current_period_end, tz=timezone.utc
    ).isoformat()

    await db["subscriptions"].update_one(
        {"user_id": user_id},
        {"$set": {
            "user_id": user_id,
            "status": stripe_sub.status,
            "stripe_subscription_id": stripe_sub.id,
            "stripe_customer_id": stripe_sub.customer,
            "current_period_end": period_end,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )

    await db["users"].update_one(
        {"user_id": user_id},
        {"$set": {"plan_status": "active"}},
    )


@router.post("/portal")
async def create_portal_session(request: Request):
    """Create Stripe Customer Portal session for self-serve billing."""
    user = await _get_current_user(request)
    body = await request.json()
    origin_url = body.get("origin_url", "")

    if not user.get("stripe_customer_id"):
        raise HTTPException(400, "No billing account")

    portal_session = stripe.billing_portal.Session.create(
        customer=user["stripe_customer_id"],
        return_url=f"{origin_url}/settings?tab=billing",
    )

    return {"ok": True, "url": portal_session.url}


async def _resolve_user_id_from_payload(db, data_obj: dict) -> tuple:
    """
    P0: Resolve a canonical user_id from payment payload.
    Returns (user_id, orphan_reason) — if orphan_reason is set, caller should
    log to orphan_payments but STILL activate PENDING_ACTIVE subscription.
    Strategy:
      1. metadata.user_id  (clean case)
      2. match by stripe customer_id → users.stripe_customer_id
      3. match by customer_email → users.email
      4. match by legacy order_id prefix (email:*/tg_*/anon_*)
      5. None → true orphan
    """
    meta = data_obj.get("metadata", {}) or {}
    raw_uid = (meta.get("user_id") or "").strip()

    # Clean canonical user_id — happy path
    if raw_uid and not raw_uid.startswith(("anon_", "email:", "tg_")):
        user = await db["users"].find_one({"user_id": raw_uid}, {"_id": 0, "user_id": 1})
        if user:
            return user["user_id"], None
        return raw_uid, "USER_ID_NOT_FOUND"

    reason_parts = []
    if raw_uid:
        reason_parts.append(f"bad_uid={raw_uid[:24]}")

    # Fallback 1: stripe customer_id
    cust_id = data_obj.get("customer")
    if cust_id:
        user = await db["users"].find_one({"stripe_customer_id": cust_id}, {"_id": 0, "user_id": 1})
        if user and user.get("user_id"):
            return user["user_id"], "RESOLVED_BY_CUSTOMER_ID"

    # Fallback 2: customer_email
    email = data_obj.get("customer_email") or meta.get("email") or meta.get("customer_email")
    if email:
        user = await db["users"].find_one({"email": email}, {"_id": 0, "user_id": 1})
        if user and user.get("user_id"):
            return user["user_id"], "RESOLVED_BY_EMAIL"
        reason_parts.append(f"email={email}")

    # Fallback 3: legacy order_id prefixes (email:..., tg_..., anon_...)
    if raw_uid.startswith("email:"):
        maybe_email = raw_uid.split(":", 1)[1]
        user = await db["users"].find_one({"email": maybe_email}, {"_id": 0, "user_id": 1})
        if user and user.get("user_id"):
            return user["user_id"], "RESOLVED_BY_LEGACY_EMAIL"
    elif raw_uid.startswith("tg_"):
        tg_id = raw_uid.split("_", 1)[1]
        user = await db["users"].find_one({"telegram_id": tg_id}, {"_id": 0, "user_id": 1})
        if user and user.get("user_id"):
            return user["user_id"], "RESOLVED_BY_TELEGRAM_ID"

    return None, "ORPHAN_PAYMENT: " + (", ".join(reason_parts) or "no_identity")


async def _record_orphan_payment(db, data_obj: dict, reason: str, provider: str, pending_user_id: str = None):
    """P0: record orphan / half-orphan payment for manual review."""
    try:
        await db["orphan_payments"].insert_one({
            "provider": provider,
            "reason": reason,
            "pending_user_id": pending_user_id,
            "payload": data_obj,
            "status": "PENDING_REVIEW",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception:
        pass


@router.post("/webhook")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events — logs ALL events to billing_events."""
    body = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    db = _get_db()

    try:
        event = stripe.Webhook.construct_event(
            body, sig_header, os.environ.get("STRIPE_WEBHOOK_SECRET", "")
        )
    except Exception:
        import json
        event = json.loads(body)

    event_type = event.get("type", "")
    data_obj = event.get("data", {}).get("object", {})
    user_id = data_obj.get("metadata", {}).get("user_id", "")
    sub_id = data_obj.get("subscription") or data_obj.get("id", "")
    processed = False
    error_msg = None

    try:
        if event_type == "checkout.session.completed":
            # P0: always resolve user_id (or mark ORPHAN and still grant PENDING_ACTIVE)
            resolved_uid, orphan_reason = await _resolve_user_id_from_payload(db, data_obj)
            if data_obj.get("subscription"):
                stripe_sub = stripe.Subscription.retrieve(data_obj["subscription"])
                if resolved_uid:
                    await _activate_subscription(resolved_uid, stripe_sub)
                    await _record_payment(db, resolved_uid, data_obj, "succeeded", "card")
                    user_id = resolved_uid
                    processed = True
                    if orphan_reason:
                        # partial orphan — user resolved but via non-canonical path
                        await _record_orphan_payment(db, data_obj, orphan_reason, "stripe", resolved_uid)
                else:
                    # TRUE ORPHAN: customer paid but we cannot attach to any user_id.
                    # Still activate a PENDING_ACTIVE subscription so the payer gets
                    # access while we reconcile manually.
                    pending_user_id = f"pending_{data_obj.get('id', uuid.uuid4().hex[:12])}"
                    await db["subscriptions"].update_one(
                        {"stripe_subscription_id": stripe_sub.id},
                        {"$set": {
                            "user_id": pending_user_id,
                            "stripe_subscription_id": stripe_sub.id,
                            "status": "pending_active",
                            "payment_method": "card",
                            "orphan_reason": orphan_reason,
                            "created_at": datetime.now(timezone.utc).isoformat(),
                        }},
                        upsert=True,
                    )
                    await _record_orphan_payment(db, data_obj, orphan_reason, "stripe", pending_user_id)
                    user_id = pending_user_id
                    processed = True
            # Update checkout_sessions audit (if record exists)
            try:
                await db["checkout_sessions"].update_one(
                    {"provider_checkout_id": data_obj.get("id")},
                    {"$set": {
                        "status": "completed",
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                        "resolved_user_id": resolved_uid,
                    }},
                )
            except Exception:
                pass

        elif event_type == "invoice.paid":
            inv_sub_id = data_obj.get("subscription")
            if inv_sub_id:
                stripe_sub = stripe.Subscription.retrieve(inv_sub_id)
                customer_id = stripe_sub.customer
                user = await db["users"].find_one(
                    {"stripe_customer_id": customer_id}, {"_id": 0}
                )
                if user:
                    await _activate_subscription(user["user_id"], stripe_sub)
                    await _record_payment(db, user["user_id"], data_obj, "succeeded", "card")
                    user_id = user["user_id"]
                    processed = True

        elif event_type == "invoice.payment_failed":
            inv_sub_id = data_obj.get("subscription")
            if inv_sub_id:
                sub = await db["subscriptions"].find_one(
                    {"stripe_subscription_id": inv_sub_id}, {"_id": 0}
                )
                if sub:
                    user_id = sub["user_id"]
                    await db["subscriptions"].update_one(
                        {"stripe_subscription_id": inv_sub_id},
                        {"$set": {"status": "past_due", "updated_at": datetime.now(timezone.utc).isoformat()}},
                    )
                    await db["users"].update_one(
                        {"user_id": user_id},
                        {"$set": {"plan_status": "past_due"}},
                    )
                    await _record_payment(db, user_id, data_obj, "failed", "card")
                    processed = True

        elif event_type == "customer.subscription.deleted":
            del_sub_id = data_obj.get("id")
            if del_sub_id:
                sub = await db["subscriptions"].find_one(
                    {"stripe_subscription_id": del_sub_id}, {"_id": 0}
                )
                if sub:
                    user_id = sub["user_id"]
                    await db["subscriptions"].update_one(
                        {"stripe_subscription_id": del_sub_id},
                        {"$set": {
                            "status": "canceled",
                            "canceled_at": datetime.now(timezone.utc).isoformat(),
                            "updated_at": datetime.now(timezone.utc).isoformat(),
                        }},
                    )
                    await db["users"].update_one(
                        {"user_id": user_id},
                        {"$set": {"plan_status": "canceled"}},
                    )
                    processed = True

        elif event_type == "charge.refunded":
            customer_id = data_obj.get("customer")
            if customer_id:
                user = await db["users"].find_one(
                    {"stripe_customer_id": customer_id}, {"_id": 0}
                )
                if user:
                    user_id = user["user_id"]
                    await _record_payment(db, user_id, data_obj, "refunded", "card")
                    processed = True

    except Exception as e:
        import logging
        logging.getLogger("billing").error(f"Webhook processing error: {e}")
        error_msg = str(e)

    # Log EVERY webhook event to billing_events
    await db["billing_events"].insert_one({
        "event_id": event.get("id", f"evt_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"),
        "type": event_type,
        "source": "stripe_webhook",
        "user_id": user_id or None,
        "subscription_id": sub_id or None,
        "payload": data_obj,
        "processed": processed,
        "error": error_msg,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    return {"ok": True}


async def _record_payment(db, user_id, data_obj, status, method_type):
    """Create normalized payment record."""
    import uuid
    await db["payments"].insert_one({
        "payment_id": f"pay_{uuid.uuid4().hex[:12]}",
        "user_id": user_id,
        "provider": "stripe",
        "provider_invoice_id": data_obj.get("id", ""),
        "provider_payment_intent_id": data_obj.get("payment_intent", ""),
        "amount": (data_obj.get("amount_paid") or data_obj.get("amount_total") or 0) / 100,
        "currency": data_obj.get("currency", "usd"),
        "status": status,
        "payment_method_type": method_type,
        "paid_at": datetime.now(timezone.utc).isoformat() if status == "succeeded" else None,
        "failed_at": datetime.now(timezone.utc).isoformat() if status == "failed" else None,
        "refunded_at": datetime.now(timezone.utc).isoformat() if status == "refunded" else None,
        "receipt_url": data_obj.get("hosted_invoice_url"),
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
