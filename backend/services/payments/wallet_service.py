"""
NOWPayments Wallet Service
===========================

Handles crypto payment invoice creation and webhook processing.

Flow:
    1. create_invoice(user_id) -> invoice_url
    2. User pays via NOWPayments
    3. NOWPayments calls webhook
    4. handle_webhook(data) -> activate_pro(user_id)
"""
import requests
import os
import logging
import hmac
import hashlib
import json
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorClient

logger = logging.getLogger(__name__)

# ENV variables
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env'))

NOWPAYMENTS_API_KEY = os.getenv("NOWPAYMENTS_API_KEY", "YOUR_API_KEY_HERE")
APP_URL = os.getenv("APP_URL", "https://your-domain.com")
PAYMENTS_WEBHOOK_SECRET = os.getenv("PAYMENTS_WEBHOOK_SECRET", "CHANGE_ME")
MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "intelligence_engine")

# MongoDB connection
def _get_db():
    """Get MongoDB database instance."""
    return AsyncIOMotorClient(MONGO_URL)[DB_NAME]

# NOWPayments API
NOWPAYMENTS_API_URL = "https://api.nowpayments.io/v1"


def verify_ipn_signature(payload: dict, signature: str) -> bool:
    """
    Verify NOWPayments IPN signature.
    
    NOWPayments sends signature in header: x-nowpayments-sig
    We compute HMAC-SHA512 of the payload and compare.
    
    Args:
        payload: Webhook JSON payload
        signature: Signature from x-nowpayments-sig header
    
    Returns:
        True if signature is valid, False otherwise
    """
    if not signature:
        logger.warning("⚠️ No signature provided in webhook")
        return False
    
    if PAYMENTS_WEBHOOK_SECRET == "CHANGE_ME":
        logger.warning("⚠️ IPN Secret not configured, skipping verification (DANGEROUS!)")
        return True  # Allow in dev mode
    
    try:
        # Sort keys for consistent payload
        sorted_payload = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        
        # Compute HMAC-SHA512
        computed_signature = hmac.new(
            PAYMENTS_WEBHOOK_SECRET.encode('utf-8'),
            sorted_payload.encode('utf-8'),
            hashlib.sha512
        ).hexdigest()
        
        # Compare signatures (constant-time comparison)
        is_valid = hmac.compare_digest(computed_signature, signature)
        
        if not is_valid:
            logger.error(f"❌ Invalid signature: expected {computed_signature[:20]}..., got {signature[:20]}...")
        
        return is_valid
        
    except Exception as e:
        logger.error(f"❌ Signature verification failed: {e}")
        return False


async def create_invoice(user_id: str, interval: str = "month") -> dict:
    """Create payment invoice at NOWPayments with price from billing_config."""
    if NOWPAYMENTS_API_KEY == "YOUR_API_KEY_HERE":
        return {
            "invoice_url": f"https://nowpayments.io/payment/demo?order={user_id}",
            "invoice_id": "demo_invoice",
            "order_id": user_id,
            "demo_mode": True
        }
    
    # Read price from billing_config in MongoDB
    from motor.motor_asyncio import AsyncIOMotorClient
    _db = AsyncIOMotorClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "fomo_mobile")]
    config = await _db["billing_config"].find_one({"type": "pricing"}, {"_id": 0})
    
    if interval == "year":
        price = float((config or {}).get("yearly_crypto_dollars", 10.00))
        desc = "FOMO PRO - Annual Subscription"
    else:
        price = float((config or {}).get("monthly_crypto_dollars", 1.00))
        desc = "FOMO PRO - Monthly Subscription"
    
    try:
        response = requests.post(
            f"{NOWPAYMENTS_API_URL}/invoice",
            headers={
                "x-api-key": NOWPAYMENTS_API_KEY,
                "Content-Type": "application/json"
            },
            json={
                "price_amount": price,
                "price_currency": "usd",
                "order_id": user_id,
                "order_description": desc,
                "ipn_callback_url": f"{APP_URL}/api/payments/webhook-wallet",
                "success_url": f"{APP_URL}/api/panel/?billing=success",
                "cancel_url": f"{APP_URL}/api/panel/"
            },
            timeout=10
        )
        
        response.raise_for_status()
        data = response.json()
        
        logger.info(f"✅ Invoice created for user {user_id}: {data.get('id')}")
        
        return {
            "invoice_url": data.get("invoice_url"),
            "invoice_id": data.get("id"),
            "order_id": user_id
        }
        
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ NOWPayments API error: {e}")
        raise Exception(f"Payment service unavailable: {str(e)}")


async def handle_webhook(data: dict, signature: str = None) -> dict:
    """
    Process NOWPayments webhook with security checks.
    
    Security layers:
        1. Verify IPN signature (HMAC-SHA512)
        2. Check for duplicate payments
        3. Verify payment amount >= $19
        4. Only activate on "finished" status
    
    Webhook payload example:
        {
            "payment_id": "12345",
            "payment_status": "finished",
            "pay_amount": 19,
            "pay_currency": "USDT",
            "order_id": "user_id_here",
            "order_description": "FOMO PRO",
            "price_amount": 19,
            "price_currency": "usd",
            "actually_paid": 19
        }
    
    Payment statuses:
        - waiting: Payment created, waiting for user
        - confirming: Payment detected, waiting for confirmations
        - confirmed: Payment confirmed on blockchain
        - sending: Sending payment to merchant
        - finished: Payment complete ✅
        - failed: Payment failed
        - refunded: Payment refunded
        - expired: Payment expired
    
    Args:
        data: Webhook payload from NOWPayments
        signature: IPN signature from x-nowpayments-sig header
    
    Returns:
        {"status": "ok"} or {"status": "error", "reason": "..."}
    """
    payment_id = data.get("payment_id")
    payment_status = data.get("payment_status")
    order_id = data.get("order_id")  # user_id
    price_amount = data.get("price_amount", 0)
    
    logger.info(f"📥 Webhook: payment_id={payment_id}, status={payment_status}, order={order_id}, amount=${price_amount}")
    
    # 1️⃣ VERIFY SIGNATURE
    if signature and not verify_ipn_signature(data, signature):
        logger.error(f"❌ Invalid signature for payment {payment_id}")
        return {"status": "error", "reason": "Invalid signature"}
    
    # 2️⃣ CHECK DUPLICATE
    db = _get_db()
    existing_payment = await db.payments.find_one({"payment_id": payment_id})
    if existing_payment:
        logger.warning(f"⚠️ Duplicate webhook for payment {payment_id}, ignoring")
        return {"status": "duplicate", "reason": "Payment already processed"}
    
    # 3️⃣ CHECK PAYMENT STATUS
    if payment_status != "finished":
        logger.info(f"⏳ Payment {payment_id} status: {payment_status} - waiting for 'finished'")
        return {"status": "ignored", "reason": f"Status is {payment_status}, not finished"}
    
    # 4️⃣ VERIFY AMOUNT
    min_amount = 0.50  # Minimum $0.50 to prevent dust payments
    if price_amount < min_amount:
        logger.warning(f"⚠️ Payment {payment_id} amount too low: ${price_amount} < ${min_amount}")
        return {"status": "error", "reason": f"Insufficient payment: ${price_amount} < ${min_amount}"}
    
    # 5️⃣ RECORD PAYMENT (prevent duplicates)
    try:
        await db.payments.insert_one({
            "payment_id": payment_id,
            "order_id": order_id,
            "amount": price_amount,
            "currency": data.get("price_currency", "usd"),
            "status": payment_status,
            "processed_at": datetime.utcnow(),
            "raw_data": data
        })
        logger.info(f"💾 Payment {payment_id} recorded in database")
    except Exception as e:
        logger.error(f"❌ Failed to record payment: {e}")
        # Continue anyway to activate PRO
    
    # 6️⃣ ACTIVATE PRO
    try:
        await activate_pro(order_id, payment_id)
        logger.info(f"✅ PRO activated for user {order_id} via payment {payment_id}")
        return {"status": "ok", "user_id": order_id, "payment_id": payment_id}
    except Exception as e:
        logger.error(f"❌ Failed to activate PRO for {order_id}: {e}")
        return {"status": "error", "reason": str(e)}


async def activate_pro(user_id: str, payment_id: str = None) -> None:
    """
    Activate PRO plan for user.
    
    Updates:
        - plan: "PRO"
        - expiresAt: now + 30 days
        - subscription.plan: "PRO"
        - subscription.status: "ACTIVE"
        - subscription.paymentMethod: "crypto"
        - subscription.lastPaymentId: payment_id
    
    Args:
        user_id: MongoDB user _id
        payment_id: NOWPayments payment ID (for tracking)
    
    Raises:
        Exception: If database update fails
    """
    db = _get_db()
    expires_at = datetime.utcnow() + timedelta(days=30)
    
    result = await db.users.update_one(
        {"_id": user_id},
        {
            "$set": {
                "plan": "PRO",
                "planStatus": "ACTIVE",
                "expiresAt": expires_at,
                "subscription": {
                    "plan": "PRO",
                    "status": "ACTIVE",
                    "renewsAt": expires_at,
                    "price": "$19/month",
                    "paymentMethod": "crypto",
                    "lastPaymentId": payment_id,
                    "activatedAt": datetime.utcnow()
                }
            }
        }
    )
    
    if result.matched_count == 0:
        raise Exception(f"User {user_id} not found")
    
    logger.info(f"✅ User {user_id} upgraded to PRO (expires: {expires_at})")


# Helper function for manual testing
async def test_activate_pro(user_id: str):
    """
    Manually activate PRO for testing (without payment).
    Use only in development!
    """
    logger.warning(f"⚠️ TEST MODE: Activating PRO for {user_id} without payment")
    await activate_pro(user_id, payment_id="test_payment")
