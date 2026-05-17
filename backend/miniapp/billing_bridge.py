"""
MiniApp Billing — Stripe bridge for Telegram users.
====================================================
Maps telegram_id → miniapp_users → stripe_customer_id.
Reuses the existing Stripe setup from billing_routes.py.
"""

import os
import stripe
from datetime import datetime, timezone, timedelta

STRIPE_API_KEY = os.environ.get("STRIPE_API_KEY", "")
stripe.api_key = STRIPE_API_KEY
if "sk_test_emergent" in STRIPE_API_KEY:
    stripe.api_base = "https://integrations.emergentagent.com/stripe"


async def get_plans(db) -> dict:
    """Get available plans (public).

    Augmented by Task 6 (Honest Crypto-Only Sprint · 2026-05-12) with a
    `paymentMethods` envelope so the TG mini-app never has to interpret a
    half-configured Stripe surface.
    """
    config = await db["billing_config"].find_one({"type": "pricing"}, {"_id": 0})
    keys_config = await db["billing_config"].find_one({"type": "stripe_keys"}, {"_id": 0})

    billing_mode = "paid"
    free_trial_days = 7
    monthly_cents = 100
    yearly_cents = 1000
    product_name = "FOMO Intelligence PRO"

    if config:
        billing_mode = config.get("billing_mode", "paid")
        free_trial_days = config.get("free_trial_days", 7)
        monthly_cents = config.get("monthly_card_cents", 100)
        yearly_cents = config.get("yearly_card_cents", 1000)
        product_name = config.get("product_name", "FOMO Intelligence PRO")

    from services.billing.payment_methods import (
        compute_payment_methods,
        is_stripe_configured_from_keys_doc,
    )
    stripe_configured = is_stripe_configured_from_keys_doc(keys_config)
    payment_methods = compute_payment_methods(
        stripe_configured=stripe_configured,
        crypto_configured=True,
    )

    return {
        "billingMode": billing_mode,
        "freeTrialDays": free_trial_days,
        "productName": product_name,
        "paymentMethods": payment_methods,
        "monthly": {
            "price": monthly_cents / 100,
            "currency": "usd",
        },
        "yearly": {
            "price": yearly_cents / 100,
            "currency": "usd",
            "monthlyEquivalent": round(yearly_cents / 12 / 100, 2),
        },
    }


async def get_billing_status(db, telegram_id: str) -> dict:
    """Get subscription status for a telegram user."""
    if not telegram_id:
        return {"subscribed": False, "planStatus": "free", "subscription": None}

    user = await db["miniapp_users"].find_one(
        {"telegram_id": telegram_id}, {"_id": 0}
    )
    if not user:
        return {"subscribed": False, "planStatus": "free", "subscription": None}

    sub = await db["miniapp_subscriptions"].find_one(
        {"telegram_id": telegram_id}, {"_id": 0}
    )
    if not sub or sub.get("status") not in ("active", "trialing"):
        # Check if expired
        if sub and sub.get("status") in ("past_due", "canceled"):
            return {
                "subscribed": False,
                "planStatus": sub["status"],
                "subscription": {
                    "status": sub["status"],
                    "currentPeriodEnd": sub.get("current_period_end"),
                },
            }
        return {"subscribed": False, "planStatus": "free", "subscription": None}

    return {
        "subscribed": True,
        "planStatus": "active",
        "subscription": {
            "status": sub["status"],
            "currentPeriodEnd": sub.get("current_period_end"),
            "stripeSubscriptionId": sub.get("stripe_subscription_id"),
        },
    }


async def _ensure_stripe_customer(db, telegram_id: str) -> str:
    """Get or create Stripe customer for a Telegram user."""
    user = await db["miniapp_users"].find_one(
        {"telegram_id": telegram_id}, {"_id": 0}
    )
    if not user:
        user = {
            "telegram_id": telegram_id,
            "name": "Telegram User",
            "plan_status": "free",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db["miniapp_users"].insert_one(user)
        user.pop("_id", None)

    if user.get("stripe_customer_id"):
        return user["stripe_customer_id"]

    customer = stripe.Customer.create(
        name=user.get("name", "Telegram User"),
        metadata={"telegram_id": telegram_id, "source": "miniapp"},
    )

    await db["miniapp_users"].update_one(
        {"telegram_id": telegram_id},
        {"$set": {"stripe_customer_id": customer.id}},
    )
    return customer.id


async def _get_or_create_price(db, interval: str = "month") -> str:
    """Get subscription price ID."""
    config = await db["billing_config"].find_one({"type": "pricing"}, {"_id": 0})

    if config:
        if interval == "year" and config.get("stripe_yearly_price_id"):
            return config["stripe_yearly_price_id"]
        if interval == "month" and config.get("stripe_monthly_price_id"):
            return config["stripe_monthly_price_id"]

    price_id = os.environ.get("STRIPE_PRICE_ID")
    if price_id:
        return price_id

    amount = 100
    if config:
        amount = int(config.get("monthly_card_cents", 100)) if interval == "month" else int(config.get("yearly_card_cents", 1000))

    product = stripe.Product.create(
        name="FOMO Intelligence PRO",
        description="Crypto Decision Intelligence",
    )
    price = stripe.Price.create(
        product=product.id,
        unit_amount=amount,
        currency="usd",
        recurring={"interval": interval},
    )

    price_field = "stripe_yearly_price_id" if interval == "year" else "stripe_monthly_price_id"
    await db["billing_config"].update_one(
        {"type": "pricing"},
        {"$set": {price_field: price.id, "stripe_product_id": product.id}},
        upsert=True,
    )
    return price.id


async def create_checkout(db, telegram_id: str, origin_url: str, interval: str = "month") -> dict:
    """Create Stripe Checkout session for a Telegram user.

    Guarded by Task 6 (Honest Crypto-Only Sprint · 2026-05-12). If Stripe is
    not configured, return a truthful "crypto_only" envelope instead of
    crashing on `stripe.checkout.Session.create` with an empty API key.
    """
    if not telegram_id:
        return {"success": False, "message": "telegram_id required"}
    if not origin_url:
        return {"success": False, "message": "origin_url required"}

    # Honest crypto-only guard ─────────────────────────────────────────
    keys_config = await db["billing_config"].find_one({"type": "stripe_keys"}, {"_id": 0})
    from services.billing.payment_methods import (
        compute_payment_methods,
        is_stripe_configured_from_keys_doc,
    )
    if not is_stripe_configured_from_keys_doc(keys_config) and not STRIPE_API_KEY:
        return {
            "success": False,
            "ok": False,
            "error": "stripe_not_configured",
            "reason": "stripe_not_configured",
            "message": "Card payments are not configured. Use crypto checkout instead.",
            "paymentMethods": compute_payment_methods(stripe_configured=False),
        }

    customer_id = await _ensure_stripe_customer(db, telegram_id)
    price_id = await _get_or_create_price(db, interval)

    success_url = f"{origin_url}/miniapp?billing=success&session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{origin_url}/miniapp?billing=cancel"

    config = await db["billing_config"].find_one({"type": "pricing"}, {"_id": 0})
    billing_mode = config.get("billing_mode", "paid") if config else "paid"
    free_trial_days = config.get("free_trial_days", 7) if config else 7

    session_kwargs = {
        "customer": customer_id,
        "mode": "subscription",
        "payment_method_types": ["card"],
        "line_items": [{"price": price_id, "quantity": 1}],
        "success_url": success_url,
        "cancel_url": cancel_url,
        "metadata": {"telegram_id": telegram_id, "source": "miniapp"},
    }

    if billing_mode == "free_trial":
        session_kwargs["subscription_data"] = {"trial_period_days": free_trial_days}

    session = stripe.checkout.Session.create(**session_kwargs)

    return {"success": True, "url": session.url, "sessionId": session.id}


async def create_portal(db, telegram_id: str, origin_url: str) -> dict:
    """Create Stripe Customer Portal for billing management."""
    if not telegram_id:
        return {"success": False, "message": "telegram_id required"}

    user = await db["miniapp_users"].find_one(
        {"telegram_id": telegram_id}, {"_id": 0}
    )
    if not user or not user.get("stripe_customer_id"):
        return {"success": False, "message": "No billing account found"}

    portal = stripe.billing_portal.Session.create(
        customer=user["stripe_customer_id"],
        return_url=f"{origin_url}/miniapp",
    )

    return {"success": True, "url": portal.url}


async def handle_checkout_success(db, session_id: str) -> dict:
    """Verify checkout completion and activate subscription."""
    try:
        session = stripe.checkout.Session.retrieve(session_id)
    except Exception as e:
        return {"success": False, "message": f"Invalid session: {str(e)[:100]}"}

    if session.payment_status != "paid" and session.status != "complete":
        return {"success": False, "status": session.status, "paymentStatus": session.payment_status}

    telegram_id = (session.metadata or {}).get("telegram_id", "")
    if not telegram_id:
        return {"success": False, "message": "No telegram_id in session metadata"}

    sub_id = session.subscription
    if sub_id:
        stripe_sub = stripe.Subscription.retrieve(sub_id)
        period_end = datetime.fromtimestamp(
            stripe_sub.current_period_end, tz=timezone.utc
        ).isoformat()

        await db["miniapp_subscriptions"].update_one(
            {"telegram_id": telegram_id},
            {"$set": {
                "telegram_id": telegram_id,
                "status": stripe_sub.status,
                "stripe_subscription_id": stripe_sub.id,
                "stripe_customer_id": stripe_sub.customer,
                "current_period_end": period_end,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }},
            upsert=True,
        )

        await db["miniapp_users"].update_one(
            {"telegram_id": telegram_id},
            {"$set": {"plan_status": "active", "renew_date": period_end}},
        )

    return {"success": True, "status": "active"}
