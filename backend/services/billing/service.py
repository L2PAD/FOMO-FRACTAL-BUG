"""
BillingService — the single orchestrator that owns all providers.

Config-driven: reads `billing_config.provider_mode` from MongoDB (fallback
to env BILLING_PROVIDER_MODE, default "nowpayments").

Modes:
    "nowpayments"  — single, crypto only (current prod default)
    "stripe"       — single, fiat only
    "dual"         — surface-based routing:
                       telegram → nowpayments
                       web / mobile / admin → stripe

Resolution can be overridden per-call via `provider=` param.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Literal

from motor.motor_asyncio import AsyncIOMotorClient

from .base import (
    BillingProvider,
    CheckoutResult,
    PlanId,
    PortalResult,
    StatusResult,
    Surface,
    WebhookResult,
)
from .providers import NowPaymentsProvider, StripeProvider

logger = logging.getLogger(__name__)

ProviderMode = Literal["nowpayments", "stripe", "dual"]
DEFAULT_MODE: ProviderMode = "nowpayments"


class BillingService:
    """Singleton orchestrator — one instance per app."""

    def __init__(self) -> None:
        self.providers: dict[str, BillingProvider] = {
            "nowpayments": NowPaymentsProvider(),
            "stripe": StripeProvider(),
        }

    # ── DB ────────────────────────────────────────────────────────────
    def _db(self):
        return AsyncIOMotorClient(
            os.environ.get("MONGO_URL", "mongodb://localhost:27017")
        )[os.environ.get("DB_NAME", "test_database")]

    # ── Config ────────────────────────────────────────────────────────
    async def get_config(self) -> dict:
        """Fetch billing_config (provider_mode etc.). Falls back to env."""
        db = self._db()
        doc = await db["billing_config"].find_one({"type": "billing_mode"}, {"_id": 0})
        if not doc:
            doc = {
                "type": "billing_mode",
                "provider_mode": os.environ.get("BILLING_PROVIDER_MODE", DEFAULT_MODE),
            }
        return doc

    async def set_provider_mode(self, mode: ProviderMode) -> dict:
        if mode not in ("nowpayments", "stripe", "dual"):
            raise ValueError(f"Invalid mode: {mode}")
        db = self._db()
        await db["billing_config"].update_one(
            {"type": "billing_mode"},
            {"$set": {"provider_mode": mode}},
            upsert=True,
        )
        return await self.get_config()

    async def resolve_provider(
        self, *, surface: Surface = "web", override: str | None = None
    ) -> str:
        """Return name of provider to use for this call."""
        if override and override in self.providers:
            return override

        cfg = await self.get_config()
        mode: ProviderMode = cfg.get("provider_mode", DEFAULT_MODE)

        if mode == "dual":
            return "nowpayments" if surface == "telegram" else "stripe"
        if mode == "stripe":
            return "stripe"
        return "nowpayments"

    # ── Public API ────────────────────────────────────────────────────
    async def status(self) -> dict:
        """Meta-status of the billing layer: active mode + per-provider configured state."""
        cfg = await self.get_config()
        return {
            "ok": True,
            "provider_mode": cfg.get("provider_mode", DEFAULT_MODE),
            "providers": {
                name: {"configured": p.is_configured(), "name": p.name}
                for name, p in self.providers.items()
            },
        }

    async def plans(self) -> dict:
        """Canonical plan catalog (provider-agnostic), sourced from billing_config.pricing.

        Augmented by Task 6 (Honest Crypto-Only Sprint · 2026-05-12) with a
        coherent `paymentMethods` envelope so the UI never has to interpret
        a loose `has_publishable_key` boolean.
        """
        from services.billing.payment_methods import compute_payment_methods
        db = self._db()
        pricing = await db["billing_config"].find_one({"type": "pricing"}, {"_id": 0}) or {}
        cfg = await self.get_config()

        monthly_crypto = float(pricing.get("monthly_crypto_dollars", pricing.get("monthly_price_usd", 1.0)))
        yearly_crypto = float(pricing.get("yearly_crypto_dollars", pricing.get("yearly_price_usd", 10.0)))
        monthly_card = float(pricing.get("monthly_card_cents", monthly_crypto * 100)) / 100
        yearly_card = float(pricing.get("yearly_card_cents", yearly_crypto * 100)) / 100

        stripe_prov = self.providers.get("stripe")
        crypto_prov = self.providers.get("nowpayments")
        payment_methods = compute_payment_methods(
            stripe_configured=bool(stripe_prov and stripe_prov.is_configured()),
            crypto_configured=bool(crypto_prov and crypto_prov.is_configured()),
        )

        return {
            "ok": True,
            "provider_mode": cfg.get("provider_mode", DEFAULT_MODE),
            "product_name": pricing.get("product_name", "FOMO Intelligence PRO"),
            "paywall_enabled": pricing.get("paywall_enabled", True),
            "free_trial_days": pricing.get("free_trial_days", 0),
            "paymentMethods": payment_methods,
            "monthly": {
                "card_price": monthly_card,
                "crypto_price": monthly_crypto,
                "interval": "month",
                "currency": "usd",
            },
            "yearly": {
                "card_price": yearly_card,
                "crypto_price": yearly_crypto,
                "interval": "year",
                "currency": "usd",
                "discount_percent": pricing.get("yearly_discount_percent", 17),
            },
            "features": pricing.get("features", []),
        }

    async def create_checkout(
        self,
        user: dict,
        plan_id: PlanId,
        *,
        surface: Surface = "web",
        origin_url: str = "",
        provider: str | None = None,
        context: dict | None = None,
    ) -> CheckoutResult:
        name = await self.resolve_provider(surface=surface, override=provider)
        prov = self.providers[name]
        if not prov.is_configured():
            return {"ok": False, "error": "provider_not_configured", "provider": name}
        ctx = context or {}
        result = await prov.create_checkout(user, plan_id, surface=surface, origin_url=origin_url)
        # Enrich audit row with attribution (state, signalId, signal_source)
        if result.get("ok") and (ctx.get("state") or ctx.get("signalId") or ctx.get("signal_source")):
            try:
                db = self._db()
                await db["checkout_sessions"].update_one(
                    {"session_id": result.get("session_id", "")},
                    {
                        "$set": {
                            "attribution": {
                                "state": ctx.get("state", ""),
                                "signal_id": ctx.get("signalId", ""),
                                "signal_source": ctx.get("signal_source", ""),
                            }
                        }
                    },
                )
            except Exception as e:
                logger.warning(f"attribution persist failed: {e}")
        return result

    async def get_status(
        self, user: dict, *, surface: Surface = "web", provider: str | None = None
    ) -> StatusResult:
        name = await self.resolve_provider(surface=surface, override=provider)
        return await self.providers[name].get_status(user)

    async def open_portal(
        self,
        user: dict,
        *,
        surface: Surface = "web",
        origin_url: str = "",
        provider: str | None = None,
    ) -> PortalResult:
        name = await self.resolve_provider(surface=surface, override=provider)
        return await self.providers[name].open_portal(user, origin_url=origin_url)

    async def handle_webhook(self, provider_name: str, body: bytes, headers: dict) -> WebhookResult:
        prov = self.providers.get(provider_name)
        if not prov:
            return {"ok": False, "error": "unknown_provider", "event_type": ""}
        result = await prov.handle_webhook(body, headers)
        # Close the conversion loop — emit payment_success with attribution
        if result.get("processed") and result.get("user_id"):
            await self._emit_payment_success(
                user_id=result["user_id"],
                provider=provider_name,
                event_type=result.get("event_type", ""),
            )
        return result

    async def _emit_payment_success(self, user_id: str, provider: str, event_type: str) -> None:
        """Look up last checkout_session, write payment_success analytics event
        with the *same state/signal_id* that was captured at checkout time.
        This powers conversion_by_state KPI and the return-loop hero override."""
        db = self._db()
        try:
            session = await db["checkout_sessions"].find_one(
                {"user_id": user_id, "provider": provider},
                sort=[("created_at", -1)],
                projection={"_id": 0},
            )
        except Exception:
            session = None

        attribution = (session or {}).get("attribution") or {}
        now = datetime.now(timezone.utc)
        try:
            await db["analytics_events"].insert_one(
                {
                    "event": "payment_success",
                    "userId": user_id,
                    "user_id": user_id,
                    "context": {
                        "state": attribution.get("state", ""),
                        "signal_id": attribution.get("signal_id", ""),
                        "signal_source": attribution.get("signal_source", ""),
                        "provider": provider,
                        "event_type": event_type,
                        "plan_id": (session or {}).get("plan_id", ""),
                        "surface": (session or {}).get("surface", ""),
                    },
                    "timestamp": now,
                }
            )
        except Exception as e:
            logger.warning(f"payment_success emit failed: {e}")
        # Mark user return-loop flag
        try:
            await db["users"].update_one(
                {"$or": [{"user_id": user_id}, {"_id": user_id}]},
                {
                    "$set": {
                        "just_converted_at": now.isoformat(),
                        "conversion_state": attribution.get("state", ""),
                        "conversion_signal_id": attribution.get("signal_id", ""),
                    }
                },
            )
        except Exception:
            pass


# Singleton
billing_service = BillingService()
