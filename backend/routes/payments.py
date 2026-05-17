"""
Crypto Payment Routes - NOWPayments Integration
================================================

Endpoints:
- GET  /api/payments/plans - Get subscription plans and pricing
- POST /api/payments/create-wallet-invoice - Create crypto payment invoice
- POST /api/payments/webhook-wallet - Handle payment confirmation webhook
- GET  /api/payments/status - Get user payment status
"""
from fastapi import APIRouter, Request, Depends, HTTPException
from routes.auth import get_current_user, get_optional_user
from services.payments.wallet_service import create_invoice, handle_webhook
from pymongo import MongoClient
import logging
import os

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/payments", tags=["payments"])

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "intelligence_engine")
_db = MongoClient(MONGO_URL)[DB_NAME]


def _ensure_billing_config():
    """Ensure billing_config exists in MongoDB with NOWPayments pricing."""
    existing = _db.billing_config.find_one({"type": "pricing"})
    if not existing:
        _db.billing_config.insert_one({
            "type": "pricing",
            "billing_mode": "crypto",
            "provider": "nowpayments",
            "product_name": "FOMO Intelligence PRO",
            "monthly_price_usd": 19,
            "yearly_price_usd": 190,
            "yearly_discount_percent": 17,
            "free_access_enabled": False,
            "paywall_enabled": True,
            "features": [
                "Real-time Exchange signals (BTC, ETH, SOL)",
                "Multi-horizon forecasts (24H, 7D, 30D)",
                "Market drivers & alignment analysis",
                "Edge opportunities & hidden patterns",
                "Priority signal alerts",
            ],
        })
        logger.info("✅ billing_config seeded with NOWPayments pricing")
    return _db.billing_config.find_one({"type": "pricing"})


# Seed billing config on module load
_ensure_billing_config()


@router.get("/plans")
async def get_plans():
    """
    Get subscription plans with real pricing from MongoDB billing_config.
    Used by both mobile app and admin panel.
    """
    config = _db.billing_config.find_one({"type": "pricing"})
    if not config:
        config = _ensure_billing_config()

    monthly = config.get("monthly_price_usd") or config.get("monthly_crypto_dollars") or 19
    yearly = config.get("yearly_price_usd") or config.get("yearly_crypto_dollars") or 190
    discount = config.get("yearly_discount_percent", 17)

    return {
        "ok": True,
        "provider": "nowpayments",
        "plans": {
            "billing_mode": config.get("billing_mode", "crypto"),
            "product_name": config.get("product_name", "FOMO Intelligence PRO"),
            "paywall_enabled": config.get("paywall_enabled", True),
            "free_access_enabled": config.get("free_access_enabled", False),
            "monthly": {
                "price": monthly,
                "currency": "usd",
                "interval": "month",
                "payment_method": "crypto",
            },
            "yearly": {
                "price": yearly,
                "currency": "usd",
                "interval": "year",
                "payment_method": "crypto",
                "discount_percent": discount,
                "monthly_equivalent": round(yearly / 12, 2),
            },
            "features": config.get("features", []),
        },
    }


@router.post("/create-wallet-invoice")
async def create_wallet_invoice(req: Request, user=Depends(get_optional_user)):
    """
    Create NOWPayments invoice for PRO subscription.
    Works with both JWT auth (mobile) and body user_id (miniapp).
    """
    try:
        if user and user.get("_id"):
            user_id = str(user["_id"])
        else:
            body = await req.json()
            user_id = body.get("user_id", "")
        if not user_id:
            raise HTTPException(status_code=400, detail="user_id required")
        result = await create_invoice(user_id)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create wallet invoice: {e}")
        raise HTTPException(status_code=500, detail=f"Payment service error: {str(e)}")


@router.post("/webhook-wallet")
async def wallet_webhook(req: Request):
    """
    NOWPayments webhook handler.
    
    Called when:
        - Payment is created
        - Payment is pending
        - Payment is confirmed
        - Payment is finished
    
    We only activate PRO when payment_status == "finished"
    
    Security:
        - Verify IPN signature (x-nowpayments-sig header)
        - Check for duplicate payments
        - Verify payment amount >= $19
    """
    try:
        data = await req.json()
        signature = req.headers.get("x-nowpayments-sig")
        
        logger.info(f"📥 Webhook received: {data.get('payment_status')} for order {data.get('order_id')}")
        
        result = await handle_webhook(data, signature)
        return result
    except Exception as e:
        logger.error(f"❌ Webhook processing failed: {e}")
        return {"status": "error", "message": str(e)}


@router.get("/status")
async def payment_status(req: Request, user=Depends(get_optional_user)):
    """
    Get user payment/subscription status.
    Supports: JWT auth header, telegram-id header, or payment_id query.
    """
    payment_id = req.query_params.get("payment_id")
    
    # If we have an authenticated user
    if user:
        result = {
            "status": "active" if user.get("plan") == "PRO" else "inactive",
            "plan": user.get("plan", "FREE"),
            "expiresAt": user.get("expiresAt").isoformat() if user.get("expiresAt") else None,
            "paymentMethod": "crypto",
            "user": {
                "plan": user.get("plan", "FREE"),
                "email": user.get("email"),
            },
        }
        
        # Check specific payment if requested
        if payment_id:
            payment = _db.payments.find_one({"invoice_id": str(payment_id)})
            if payment:
                result["paymentStatus"] = payment.get("status", "pending")
                if payment.get("status") == "finished":
                    result["status"] = "finished"
        
        return result
    
    # Try Telegram ID header
    telegram_id = req.headers.get("telegram-id")
    if telegram_id:
        tg_user = _db.users.find_one({"telegramChatId": str(telegram_id)})
        if tg_user:
            return {
                "status": "active" if tg_user.get("plan") == "PRO" else "inactive",
                "plan": tg_user.get("plan", "FREE"),
                "user": {"plan": tg_user.get("plan", "FREE")},
            }
    
    return {"plan": "FREE", "status": "inactive"}
    
    return await db.users.find_one({"_id": user_id})
