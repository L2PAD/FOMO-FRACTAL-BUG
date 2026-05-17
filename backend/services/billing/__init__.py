"""
Unified Billing Layer — FOMO Platform.

ONE orchestrator, TWO providers (NOWPayments crypto + Stripe fiat),
config-driven switch via `billing_config.provider_mode`.

Usage:
    from services.billing import billing_service
    result = await billing_service.create_checkout(user, plan_id="month", surface="web")
"""
from .service import billing_service, BillingService
from .base import BillingProvider, PlanId, Surface

__all__ = ["billing_service", "BillingService", "BillingProvider", "PlanId", "Surface"]
