"""
Web Platform Billing Routes — NOWPayments Only
================================================
Handles subscription payments for the web platform via crypto (NOWPayments).
All payments via NOWPayments crypto gateway.
"""
from fastapi import APIRouter, HTTPException, Request
from datetime import datetime, timezone
from dotenv import load_dotenv
import os
import uuid
import logging

load_dotenv()
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/billing", tags=["billing"])

from pymongo import MongoClient
MONGO_URL = os.getenv('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.getenv('DB_NAME', 'test_database')
client = MongoClient(MONGO_URL)
db = client[DB_NAME]

from services.payments.wallet_service import create_invoice


async def _get_current_user(request: Request) -> dict:
    """Extract user from session cookie or Authorization header."""
    from routes.auth import get_current_user_optional
    try:
        return await get_current_user_optional(request)
    except Exception:
        raise HTTPException(401, "Authentication required")


def _get_pricing():
    """Get pricing from DB config or defaults."""
    config = db["billing_config"].find_one({"type": "pricing"})
    if config:
        return {
            "monthly": float(config.get("monthly_crypto_dollars", 19.0)),
            "yearly": float(config.get("yearly_crypto_dollars", 149.0)),
            "product_name": config.get("product_name", "FOMO Intelligence PRO"),
        }
    return {
        "monthly": float(os.getenv("CRYPTO_MONTHLY_PRICE", "19.0")),
        "yearly": float(os.getenv("CRYPTO_YEARLY_PRICE", "149.0")),
        "product_name": "FOMO Intelligence PRO",
    }


@router.get("/plans")
async def get_plans():
    """Get available subscription plans."""
    pricing = _get_pricing()
    return {
        "ok": True,
        "plans": [
            {
                "id": "free",
                "name": "FREE",
                "price": 0,
                "currency": "USD",
                "interval": "forever",
                "features": ["Basic signals", "Limited feed", "Home screen"],
            },
            {
                "id": "pro_monthly",
                "name": "PRO",
                "price": pricing["monthly"],
                "currency": "USD",
                "interval": "month",
                "features": [
                    "Full signals with reasoning",
                    "Edge analytics",
                    "Deep Intel (Exchange, On-chain, Sentiment, Fractal)",
                    "Priority push alerts",
                    "Track record & history",
                ],
            },
            {
                "id": "pro_annual",
                "name": "PRO",
                "price": pricing["yearly"],
                "currency": "USD",
                "interval": "year",
                "features": [
                    "Everything in PRO Monthly",
                    "2 months free",
                    "Annual billing",
                ],
            },
        ],
        "paymentMethod": "crypto",
        "provider": "NOWPayments",
    }


@router.get("/status")
async def get_billing_status(request: Request):
    """Get current user billing status."""
    try:
        user = await _get_current_user(request)
    except Exception:
        return {"ok": True, "plan": "FREE", "status": "ACTIVE", "authenticated": False}

    return {
        "ok": True,
        "authenticated": True,
        "plan": user.get("plan", "FREE"),
        "planStatus": user.get("planStatus", "ACTIVE"),
        "subscription": user.get("subscription", {}),
        "access": user.get("access", {}),
        "paymentMethod": "crypto",
    }


@router.post("/create-crypto-checkout")
async def create_crypto_checkout(request: Request):
    """Create NOWPayments crypto invoice for web platform."""
    user = await _get_current_user(request)
    body = await request.json()
    interval = body.get("interval", "month")

    pricing = _get_pricing()
    amount = pricing["yearly"] if interval == "year" else pricing["monthly"]

    try:
        invoice = await create_invoice(
            user_id=str(user.get("_id", user.get("user_id", "unknown"))),
            amount=amount,
            currency="usd",
        )
    except Exception as e:
        logger.error(f"Failed to create crypto invoice: {e}")
        raise HTTPException(500, f"Payment gateway error: {str(e)}")

    # Record transaction
    txn_id = f"txn_{uuid.uuid4().hex[:12]}"
    db["payment_transactions"].insert_one({
        "id": txn_id,
        "user_id": str(user.get("_id", "")),
        "email": user.get("email", ""),
        "invoice_id": invoice.get("id", ""),
        "invoice_url": invoice.get("invoice_url", ""),
        "amount": amount,
        "currency": "usd",
        "interval": interval,
        "payment_method": "crypto_nowpayments",
        "payment_status": "waiting",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    return {
        "ok": True,
        "url": invoice.get("invoice_url", ""),
        "invoice_id": invoice.get("id", ""),
        "session_id": txn_id,
    }


@router.get("/crypto-checkout-status/{session_id}")
async def get_crypto_checkout_status(session_id: str):
    """Check crypto checkout payment status."""
    txn = db["payment_transactions"].find_one({"id": session_id}, {"_id": 0})
    if not txn:
        raise HTTPException(404, "Transaction not found")

    return {
        "ok": True,
        "status": "complete" if txn.get("payment_status") == "paid" else "pending",
        "payment_status": txn.get("payment_status", "unknown"),
        "amount": txn.get("amount"),
        "currency": txn.get("currency"),
    }


@router.post("/apply-referral")
async def apply_referral_code(request: Request):
    """Apply referral/promo code to user's account."""
    user = await _get_current_user(request)
    body = await request.json()
    code = body.get("code", "").strip().upper()

    if not code:
        raise HTTPException(400, "Referral code required")

    promo = db["promo_codes"].find_one({"code": code, "active": True})
    if not promo:
        raise HTTPException(404, "Invalid or expired code")

    # Check if already used
    user_id = str(user.get("_id", ""))
    if user_id in promo.get("usedBy", []):
        raise HTTPException(400, "Code already used")

    discount = promo.get("discount", 0)

    # Apply to user
    db["users"].update_one(
        {"_id": user["_id"]},
        {"$set": {"appliedPromo": code, "promoDiscount": discount, "updatedAt": datetime.utcnow()}}
    )

    # Track usage
    db["promo_codes"].update_one(
        {"code": code},
        {"$push": {"usedBy": user_id}, "$inc": {"usageCount": 1}}
    )

    return {"ok": True, "discount": discount, "message": f"Code {code} applied: {discount}% off"}
