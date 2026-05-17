"""
NOWPayments provider — thin wrapper over existing wallet_service.
All Crypto invoice logic continues to live in services/payments/wallet_service.py
so we don't duplicate the production flow. This adapter just conforms it
to the BillingProvider interface.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

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


class NowPaymentsProvider(BillingProvider):
    name = "nowpayments"

    # ── Config ────────────────────────────────────────────────────────
    def is_configured(self) -> bool:
        key = os.environ.get("NOWPAYMENTS_API_KEY", "")
        return bool(key) and key != "YOUR_API_KEY_HERE"

    def _db(self):
        return AsyncIOMotorClient(
            os.environ.get("MONGO_URL", "mongodb://localhost:27017")
        )[os.environ.get("DB_NAME", "test_database")]

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
            return {"ok": False, "error": "nowpayments_not_configured", "provider": self.name}

        # Resolve canonical user_id — prefer user_id, fallback to _id
        user_id = str(user.get("user_id") or user.get("_id") or "").strip()
        if not user_id:
            return {"ok": False, "error": "user_id_required", "provider": self.name}

        try:
            from services.payments.wallet_service import create_invoice
            result = await create_invoice(user_id, interval=plan_id)
        except Exception as e:
            logger.exception("NOWPayments create_invoice failed")
            return {"ok": False, "error": "provider_error", "detail": str(e), "provider": self.name}

        if not result.get("invoice_url"):
            return {
                "ok": False,
                "error": result.get("error", "invoice_creation_failed"),
                "provider": self.name,
            }

        # Audit trail
        try:
            db = self._db()
            await db["checkout_sessions"].insert_one(
                {
                    "provider": self.name,
                    "user_id": user_id,
                    "plan_id": plan_id,
                    "surface": surface,
                    "session_id": result.get("invoice_id", ""),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "status": "created",
                }
            )
        except Exception:
            logger.warning("checkout_sessions audit failed (non-fatal)")

        return {
            "ok": True,
            "provider": self.name,
            "url": result["invoice_url"],
            "session_id": result.get("invoice_id", ""),
        }

    # ── Status ────────────────────────────────────────────────────────
    async def get_status(self, user: dict) -> StatusResult:
        user_id = str(user.get("user_id") or user.get("_id") or "").strip()
        if not user_id:
            return {"ok": True, "provider": self.name, "subscribed": False, "plan_status": "free"}

        db = self._db()
        sub = await db["subscriptions"].find_one(
            {"user_id": user_id, "provider": {"$in": [self.name, "nowpayments_crypto", None]}},
            sort=[("created_at", -1)],
            projection={"_id": 0},
        )
        if not sub:
            return {"ok": True, "provider": self.name, "subscribed": False, "plan_status": "free"}

        status = sub.get("status", "free")
        return {
            "ok": True,
            "provider": self.name,
            "subscribed": status in ("active", "trialing"),
            "plan_status": status,
            "current_period_end": sub.get("current_period_end", ""),
            "subscription_id": sub.get("subscription_id", ""),
            "customer_id": "",
        }

    # ── Portal ────────────────────────────────────────────────────────
    async def open_portal(self, user: dict, *, origin_url: str = "") -> PortalResult:
        # NOWPayments has no self-serve portal — cancel / renew is manual.
        return {
            "ok": False,
            "provider": self.name,
            "error": "not_supported",
        }

    # ── Webhook ───────────────────────────────────────────────────────
    async def handle_webhook(self, body: bytes, headers: dict) -> WebhookResult:
        try:
            import json
            payload = json.loads(body)
        except Exception:
            return {"ok": False, "error": "invalid_json", "event_type": ""}

        sig = (
            headers.get("x-nowpayments-sig")
            or headers.get("X-Nowpayments-Sig")
            or headers.get("x-nowpayments-signature")
            or ""
        )

        try:
            from services.payments.wallet_service import handle_webhook as np_webhook
            # Existing wallet_service.handle_webhook verifies signature + writes DB
            result = await np_webhook(payload, signature=sig)
        except TypeError:
            # Older signature — no signature param
            from services.payments.wallet_service import handle_webhook as np_webhook
            result = await np_webhook(payload)
        except Exception:
            logger.exception("NOWPayments webhook processing failed")
            return {"ok": False, "error": "processing_failed", "event_type": payload.get("payment_status", "")}

        return {
            "ok": bool(result.get("ok", True)),
            "event_type": payload.get("payment_status", ""),
            "processed": bool(result.get("activated", False) or result.get("ok", False)),
            "user_id": payload.get("order_id", ""),
        }
