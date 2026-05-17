"""
Payment Methods — single source of truth for "what can the user actually pay with".

Added by Task 6 (Honest Crypto-Only Sprint · 2026-05-12).

PURPOSE
-------
Before this module, every `/plans` endpoint exposed a loose
`has_publishable_key: false` boolean. That was a technical truth but a poor
product contract:

  * the UI had to interpret the boolean to decide whether to render card
    buttons
  * three separate endpoints did the interpretation slightly differently
  * none of them said *what user can do* — only what was missing

This helper returns a **coherent crypto-only / dual / disabled envelope**
that the UI consumes verbatim. No interpretation required.

DESIGN
------
`compute_payment_methods()` reads two booleans (Stripe configured + crypto
configured) and produces:

    {
      "mode":                    "crypto_only" | "dual" | "card_only" | "disabled",
      "cardPaymentsAvailable":    bool,
      "cryptoPaymentsAvailable":  bool,
      "availableMethods":         ["crypto", "card", ...],
      "reason":                   "stripe_not_configured" | "crypto_not_configured" | "no_payment_provider" | null,
    }

This mirrors Truthful Degradation: when a payment method is unavailable,
the envelope **says so explicitly** instead of relying on the UI to guess
from an absent key.
"""

from __future__ import annotations

from typing import Any


def compute_payment_methods(
    *,
    stripe_configured: bool,
    crypto_configured: bool = True,
) -> dict[str, Any]:
    """Pure function. Maps two booleans to the honest payment-methods envelope.

    `crypto_configured` defaults to True because the platform's crypto rail
    (NOWPayments) is the default monetisation path and currently always
    enabled. Pass False explicitly only when crypto is genuinely off.
    """
    methods: list[str] = []
    if crypto_configured:
        methods.append("crypto")
    if stripe_configured:
        methods.append("card")

    if stripe_configured and crypto_configured:
        mode = "dual"
        reason: str | None = None
    elif crypto_configured and not stripe_configured:
        mode = "crypto_only"
        reason = "stripe_not_configured"
    elif stripe_configured and not crypto_configured:
        mode = "card_only"
        reason = "crypto_not_configured"
    else:
        mode = "disabled"
        reason = "no_payment_provider"

    return {
        "mode": mode,
        "cardPaymentsAvailable": stripe_configured,
        "cryptoPaymentsAvailable": crypto_configured,
        "availableMethods": methods,
        "reason": reason,
    }


def is_stripe_configured_from_keys_doc(keys_doc: dict | None) -> bool:
    """Resolve Stripe configuration from a `billing_config.stripe_keys` document.

    The historical signal was `has_publishable_key`. We use the same check
    but funnel it through this helper so the rule lives in exactly one place.
    """
    if not keys_doc:
        return False
    return bool(keys_doc.get("stripe_publishable_key"))
