"""
Stripe provider — real fiat checkout, subscription, portal, webhook.

Config-driven. If STRIPE_SECRET_KEY is missing/empty, is_configured() returns
False and orchestrator can fail gracefully (403 / provider_not_configured).

Required env vars for live operation:
    STRIPE_SECRET_KEY        sk_live_* or sk_test_*
    STRIPE_WEBHOOK_SECRET    whsec_*
    STRIPE_PRICE_MONTHLY     price_* — Stripe Price ID for monthly plan
    STRIPE_PRICE_YEARLY      price_* — Stripe Price ID for yearly plan
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient

from ..base import (
    BillingProvider,
    CheckoutResult,
    PlanId,
    PortalResult,
    StatusResult,
    Surface,
    WebhookResult,
)

logger = logging.getLogger(__name__)


class StripeProvider(BillingProvider):
    name = "stripe"

    def __init__(self) -> None:
        self._stripe = None  # Lazy-loaded on first call

    # ── Config ────────────────────────────────────────────────────────
    @property
    def secret_key(self) -> str:
        return os.environ.get("STRIPE_SECRET_KEY", "") or os.environ.get("STRIPE_API_KEY", "")

    @property
    def webhook_secret(self) -> str:
        return os.environ.get("STRIPE_WEBHOOK_SECRET", "")

    @property
    def publishable_key(self) -> str:
        return os.environ.get("STRIPE_PUBLISHABLE_KEY", "")

    def is_configured(self) -> bool:
        key = self.secret_key
        return bool(key) and not key.startswith("placeholder")

    def _get_stripe(self):
        if not self.is_configured():
            return None
        if self._stripe is None:
            import stripe
            stripe.api_key = self.secret_key
            # Emergent-hosted Stripe test proxy (used with sk_test_emergent key)
            if "sk_test_emergent" in self.secret_key:
                stripe.api_base = "https://integrations.emergentagent.com/stripe"
            self._stripe = stripe
        return self._stripe

    def _db(self):
        return AsyncIOMotorClient(
            os.environ.get("MONGO_URL", "mongodb://localhost:27017")
        )[os.environ.get("DB_NAME", "test_database")]

    # ── Helpers ───────────────────────────────────────────────────────
    async def _ensure_customer(self, user: dict) -> str:
        """Find or create Stripe customer for user. Returns customer_id."""
        existing = user.get("stripe_customer_id", "")
        if existing:
            return existing

        stripe = self._get_stripe()
        customer = stripe.Customer.create(
            email=user.get("email", ""),
            name=user.get("name") or user.get("display_name", ""),
            metadata={"user_id": str(user.get("user_id") or user.get("_id") or "")},
        )

        # Persist back to users collection
        user_id = str(user.get("user_id") or user.get("_id") or "")
        if user_id:
            try:
                db = self._db()
                await db["users"].update_one(
                    {"$or": [{"user_id": user_id}, {"_id": user_id}]},
                    {"$set": {"stripe_customer_id": customer.id}},
                )
            except Exception:
                logger.warning("Failed to persist stripe_customer_id — non-fatal")

        return customer.id

    def _price_id(self, plan_id: PlanId) -> str:
        key = "STRIPE_PRICE_YEARLY" if plan_id == "year" else "STRIPE_PRICE_MONTHLY"
        return os.environ.get(key) or os.environ.get("STRIPE_PRICE_ID", "")

    # ── Checkout ──────────────────────────────────────────────────────
    async def create_checkout(
        self,
        user: dict,
        plan_id: PlanId,
        *,
        surface: Surface = "web",
        origin_url: str = "",
    ) -> CheckoutResult:
        if not self.is_configured():
            return {"ok": False, "error": "stripe_not_configured", "provider": self.name}

        price_id = self._price_id(plan_id)
        if not price_id:
            return {
                "ok": False,
                "error": "stripe_price_id_missing",
                "detail": f"Set STRIPE_PRICE_{plan_id.upper()}LY in env",
                "provider": self.name,
            }

        stripe = self._get_stripe()
        user_id = str(user.get("user_id") or user.get("_id") or "").strip()
        if not user_id:
            return {"ok": False, "error": "user_id_required", "provider": self.name}

        try:
            customer_id = await self._ensure_customer(user)

            base = (origin_url or os.environ.get("APP_URL", "")).rstrip("/")
            success_url = f"{base}/api/panel/info?billing=success&session_id={{CHECKOUT_SESSION_ID}}"
            cancel_url = f"{base}/api/panel/info?billing=cancelled"

            session = stripe.checkout.Session.create(
                mode="subscription",
                customer=customer_id,
                line_items=[{"price": price_id, "quantity": 1}],
                metadata={
                    "user_id": user_id,
                    "plan_id": plan_id,
                    "surface": surface,
                },
                subscription_data={
                    "metadata": {
                        "user_id": user_id,
                        "plan_id": plan_id,
                    },
                },
                success_url=success_url,
                cancel_url=cancel_url,
                allow_promotion_codes=True,
            )
        except Exception as e:
            logger.exception("Stripe checkout creation failed")
            return {"ok": False, "error": "provider_error", "detail": str(e), "provider": self.name}

        # Audit trail
        try:
            db = self._db()
            await db["checkout_sessions"].insert_one(
                {
                    "provider": self.name,
                    "user_id": user_id,
                    "plan_id": plan_id,
                    "surface": surface,
                    "session_id": session.id,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "status": "created",
                }
            )
        except Exception:
            logger.warning("checkout_sessions audit failed (non-fatal)")

        return {
            "ok": True,
            "provider": self.name,
            "url": session.url,
            "session_id": session.id,
        }

    # ── Status ────────────────────────────────────────────────────────
    async def get_status(self, user: dict) -> StatusResult:
        if not self.is_configured():
            return {"ok": True, "provider": self.name, "subscribed": False, "plan_status": "free"}

        customer_id = user.get("stripe_customer_id", "")
        if not customer_id:
            return {"ok": True, "provider": self.name, "subscribed": False, "plan_status": "free"}

        stripe = self._get_stripe()
        try:
            subs = stripe.Subscription.list(customer=customer_id, status="all", limit=1)
        except Exception as e:
            logger.exception("Stripe subscription lookup failed")
            return {"ok": False, "provider": self.name, "subscribed": False, "plan_status": "free", "error": str(e)}

        data = subs.data if hasattr(subs, "data") else []
        if not data:
            return {"ok": True, "provider": self.name, "subscribed": False, "plan_status": "free"}

        sub = data[0]
        status = sub.status  # active | trialing | past_due | canceled | etc.
        period_end = getattr(sub, "current_period_end", 0)

        return {
            "ok": True,
            "provider": self.name,
            "subscribed": status in ("active", "trialing"),
            "plan_status": status,
            "current_period_end": (
                datetime.fromtimestamp(period_end, tz=timezone.utc).isoformat() if period_end else ""
            ),
            "subscription_id": sub.id,
            "customer_id": customer_id,
        }

    # ── Portal ────────────────────────────────────────────────────────
    async def open_portal(self, user: dict, *, origin_url: str = "") -> PortalResult:
        if not self.is_configured():
            return {"ok": False, "provider": self.name, "error": "stripe_not_configured"}

        customer_id = user.get("stripe_customer_id", "")
        if not customer_id:
            return {"ok": False, "provider": self.name, "error": "no_billing_account"}

        stripe = self._get_stripe()
        base = (origin_url or os.environ.get("APP_URL", "")).rstrip("/")
        try:
            portal = stripe.billing_portal.Session.create(
                customer=customer_id,
                return_url=f"{base}/api/panel/info?tab=billing",
            )
        except Exception:
            logger.exception("Stripe portal creation failed")
            return {"ok": False, "provider": self.name, "error": "provider_error"}

        return {"ok": True, "provider": self.name, "url": portal.url}

    # ── Webhook ───────────────────────────────────────────────────────
    async def handle_webhook(self, body: bytes, headers: dict) -> WebhookResult:
        if not self.is_configured():
            return {"ok": False, "error": "stripe_not_configured", "event_type": ""}

        stripe = self._get_stripe()
        sig = headers.get("stripe-signature") or headers.get("Stripe-Signature") or ""

        # Construct + verify event
        try:
            if self.webhook_secret:
                event = stripe.Webhook.construct_event(body, sig, self.webhook_secret)
            else:
                import json
                event = json.loads(body)
        except Exception as e:
            logger.warning(f"Stripe webhook signature verification failed: {e}")
            return {"ok": False, "error": "signature_invalid", "event_type": ""}

        event_type = event.get("type", "") if isinstance(event, dict) else event["type"]
        data_obj = (event.get("data", {}) or {}).get("object", {}) if isinstance(event, dict) else event["data"]["object"]

        db = self._db()

        # Audit — log all events
        try:
            await db["billing_events"].insert_one(
                {
                    "provider": self.name,
                    "event_type": event_type,
                    "event_id": event.get("id", "") if isinstance(event, dict) else event["id"],
                    "received_at": datetime.now(timezone.utc).isoformat(),
                    "raw": {k: data_obj.get(k) for k in ("id", "customer", "subscription", "metadata", "status")},
                }
            )
        except Exception:
            pass

        user_id = ""
        processed = False

        try:
            if event_type == "checkout.session.completed":
                user_id = (data_obj.get("metadata") or {}).get("user_id", "")
                subscription_id = data_obj.get("subscription", "")
                customer_id = data_obj.get("customer", "")

                if subscription_id:
                    sub = stripe.Subscription.retrieve(subscription_id)
                    await self._activate_subscription(db, user_id, customer_id, sub)
                    processed = True

            elif event_type in ("customer.subscription.updated", "customer.subscription.created"):
                sub = data_obj  # already a subscription object
                customer_id = sub.get("customer", "")
                user_id = (sub.get("metadata") or {}).get("user_id", "")
                if not user_id and customer_id:
                    u = await db["users"].find_one({"stripe_customer_id": customer_id}, {"user_id": 1, "_id": 0})
                    if u:
                        user_id = u.get("user_id", "")

                class _Obj:
                    """Mimic stripe object attribute access."""
                    def __init__(self, d): self.__dict__.update(d)
                    def __getattr__(self, k): return self.__dict__.get(k)

                await self._activate_subscription(db, user_id, customer_id, _Obj(sub))
                processed = True

            elif event_type == "customer.subscription.deleted":
                customer_id = data_obj.get("customer", "")
                await db["subscriptions"].update_many(
                    {"stripe_customer_id": customer_id},
                    {"$set": {"status": "canceled", "updated_at": datetime.now(timezone.utc).isoformat()}},
                )
                processed = True

            elif event_type == "invoice.payment_succeeded":
                customer_id = data_obj.get("customer", "")
                amount = (data_obj.get("amount_paid") or 0) / 100.0
                await db["payments"].insert_one(
                    {
                        "provider": self.name,
                        "stripe_customer_id": customer_id,
                        "amount_usd": amount,
                        "status": "succeeded",
                        "received_at": datetime.now(timezone.utc).isoformat(),
                        "invoice_id": data_obj.get("id", ""),
                    }
                )
                processed = True

        except Exception as e:
            logger.exception("Stripe webhook handler failure")
            return {"ok": False, "error": str(e), "event_type": event_type, "processed": False, "user_id": user_id}

        return {"ok": True, "event_type": event_type, "processed": processed, "user_id": user_id}

    async def _activate_subscription(self, db, user_id: str, customer_id: str, sub: Any) -> None:
        """Upsert subscription record + mark user as PRO."""
        sub_id = sub.id if hasattr(sub, "id") else sub.get("id", "")
        status = sub.status if hasattr(sub, "status") else sub.get("status", "active")
        period_end = (
            getattr(sub, "current_period_end", 0) if hasattr(sub, "current_period_end") else sub.get("current_period_end", 0)
        )

        payload = {
            "provider": self.name,
            "user_id": user_id,
            "stripe_customer_id": customer_id,
            "stripe_subscription_id": sub_id,
            "subscription_id": sub_id,
            "status": status,
            "current_period_end": (
                datetime.fromtimestamp(period_end, tz=timezone.utc).isoformat() if period_end else ""
            ),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        await db["subscriptions"].update_one(
            {"stripe_subscription_id": sub_id},
            {"$set": payload, "$setOnInsert": {"created_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True,
        )

        if user_id and status in ("active", "trialing"):
            await db["users"].update_one(
                {"$or": [{"user_id": user_id}, {"_id": user_id}]},
                {"$set": {"plan_status": "pro", "plan_updated_at": datetime.now(timezone.utc).isoformat()}},
            )
