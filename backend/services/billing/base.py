"""
BillingProvider — base abstract interface for all payment providers.

Every provider (NOWPayments, Stripe, future…) implements this contract.
The orchestrator (BillingService) knows nothing about provider-specific APIs.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Literal, TypedDict

# ─── Type aliases ─────────────────────────────────────────────────────
PlanId = Literal["month", "year"]  # Canonical plan keys
Surface = Literal["web", "telegram", "mobile", "admin"]  # Where user initiated


# ─── DTOs ─────────────────────────────────────────────────────────────
class CheckoutResult(TypedDict, total=False):
    ok: bool
    url: str                 # Redirect URL for the user
    provider: str            # "nowpayments" | "stripe"
    session_id: str          # Provider-side session / invoice id
    error: str               # Error code if ok=False
    detail: str              # Human-readable detail


class StatusResult(TypedDict, total=False):
    ok: bool
    provider: str
    subscribed: bool
    plan_status: str         # "free" | "active" | "trialing" | "past_due" | "canceled"
    current_period_end: str  # ISO date or empty
    subscription_id: str
    customer_id: str


class PortalResult(TypedDict, total=False):
    ok: bool
    url: str
    provider: str
    error: str


class WebhookResult(TypedDict, total=False):
    ok: bool
    event_type: str
    processed: bool
    user_id: str
    error: str


# ─── Base class ───────────────────────────────────────────────────────
class BillingProvider(ABC):
    """Every provider must implement this interface."""

    name: str = ""  # e.g. "nowpayments"

    @abstractmethod
    def is_configured(self) -> bool:
        """True if this provider has all required env/keys and can accept traffic."""
        raise NotImplementedError

    @abstractmethod
    async def create_checkout(
        self,
        user: dict,
        plan_id: PlanId,
        *,
        surface: Surface = "web",
        origin_url: str = "",
    ) -> CheckoutResult:
        """Start a checkout session — return provider URL for user redirect."""
        raise NotImplementedError

    @abstractmethod
    async def get_status(self, user: dict) -> StatusResult:
        """Current subscription status for a user."""
        raise NotImplementedError

    @abstractmethod
    async def open_portal(self, user: dict, *, origin_url: str = "") -> PortalResult:
        """Self-serve billing portal URL (may be unsupported for some providers)."""
        raise NotImplementedError

    @abstractmethod
    async def handle_webhook(
        self, body: bytes, headers: dict[str, str]
    ) -> WebhookResult:
        """Process provider webhook — verify signature + mutate subscription state."""
        raise NotImplementedError
