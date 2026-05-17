"""
Admin Billing Routes - Crypto Payments Management
===================================================

Endpoints for admin dashboard to manage crypto payments, view stats, and configure API keys.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timedelta
import os

router = APIRouter(prefix="/api/admin/billing/crypto", tags=["admin-billing-crypto"])

# MongoDB connection
MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "intelligence_engine")

def _get_db():
    return AsyncIOMotorClient(MONGO_URL)[DB_NAME]


# ═══════════════════════════════════════════════════════════════
# STATS
# ═══════════════════════════════════════════════════════════════

@router.get("/stats")
async def get_crypto_stats():
    """
    Get crypto payments statistics for admin dashboard.
    
    Returns:
        {
            "totalRevenue": 1234.56,
            "totalPayments": 65,
            "proUsers": 42,
            "mrr": 798.00,
            "last30Days": {
                "revenue": 380.00,
                "payments": 20,
                "newPro": 15
            }
        }
    """
    db = _get_db()
    
    # Total payments & revenue
    pipeline = [
        {"$match": {"status": "finished"}},
        {"$group": {
            "_id": None,
            "totalRevenue": {"$sum": "$amount"},
            "totalPayments": {"$sum": 1}
        }}
    ]
    
    result = await db.payments.aggregate(pipeline).to_list(length=1)
    total_revenue = result[0]["totalRevenue"] if result else 0
    total_payments = result[0]["totalPayments"] if result else 0
    
    # PRO users count
    pro_users = await db.users.count_documents({"plan": "PRO"})
    
    # MRR (Monthly Recurring Revenue) - assuming $19/month per PRO user
    mrr = pro_users * 19
    
    # Last 30 days
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    last_30_payments = await db.payments.count_documents({
        "status": "finished",
        "processed_at": {"$gte": thirty_days_ago}
    })
    
    last_30_pipeline = [
        {"$match": {
            "status": "finished",
            "processed_at": {"$gte": thirty_days_ago}
        }},
        {"$group": {
            "_id": None,
            "revenue": {"$sum": "$amount"}
        }}
    ]
    last_30_result = await db.payments.aggregate(last_30_pipeline).to_list(length=1)
    last_30_revenue = last_30_result[0]["revenue"] if last_30_result else 0
    
    # New PRO users in last 30 days
    new_pro = await db.users.count_documents({
        "plan": "PRO",
        "subscription.activatedAt": {"$gte": thirty_days_ago}
    })
    
    return {
        "totalRevenue": round(total_revenue, 2),
        "totalPayments": total_payments,
        "proUsers": pro_users,
        "mrr": mrr,
        "last30Days": {
            "revenue": round(last_30_revenue, 2),
            "payments": last_30_payments,
            "newPro": new_pro
        }
    }


# ═══════════════════════════════════════════════════════════════
# TRANSACTIONS
# ═══════════════════════════════════════════════════════════════

@router.get("/transactions")
async def get_crypto_transactions():
    """
    Get recent crypto payment transactions.
    
    Returns:
        {
            "transactions": [
                {
                    "payment_id": "12345",
                    "order_id": "u_483ac978e64e",
                    "amount": 19,
                    "currency": "usd",
                    "status": "finished",
                    "processed_at": "2026-04-10T12:00:00Z"
                }
            ]
        }
    """
    db = _get_db()
    
    # Get last 100 transactions, sorted by date desc
    transactions = await db.payments.find().sort("processed_at", -1).limit(100).to_list(length=100)
    
    # Format for frontend
    formatted = []
    for tx in transactions:
        formatted.append({
            "payment_id": tx.get("payment_id"),
            "order_id": tx.get("order_id"),
            "amount": tx.get("amount"),
            "currency": tx.get("currency"),
            "status": tx.get("status"),
            "processed_at": tx.get("processed_at").isoformat() if tx.get("processed_at") else None
        })
    
    return {"transactions": formatted}


# ═══════════════════════════════════════════════════════════════
# SETTINGS
# ═══════════════════════════════════════════════════════════════

class CryptoSettings(BaseModel):
    apiKey: str
    ipnSecret: str
    webhookUrl: str


@router.get("/settings")
async def get_crypto_settings():
    """
    Get current NOWPayments API settings (masked for security).
    
    Returns:
        {
            "apiKey": "S5T82FH-***",
            "ipnSecret": "cefc9da9-***",
            "webhookUrl": "https://..."
        }
    """
    api_key = os.getenv("NOWPAYMENTS_API_KEY", "")
    ipn_secret = os.getenv("PAYMENTS_WEBHOOK_SECRET", "")
    app_url = os.getenv("APP_URL", "")
    
    # Mask sensitive data
    masked_api_key = api_key[:8] + "-***" if len(api_key) > 8 else "***"
    masked_ipn = ipn_secret[:8] + "-***" if len(ipn_secret) > 8 else "***"
    
    return {
        "apiKey": masked_api_key,
        "ipnSecret": masked_ipn,
        "webhookUrl": f"{app_url}/api/payments/webhook-wallet"
    }


@router.put("/settings")
async def update_crypto_settings(settings: CryptoSettings):
    """
    Update NOWPayments API settings.
    
    NOTE: This updates environment variables in memory.
    For production, you should update .env file and restart the server.
    
    Args:
        settings: New API key, IPN secret, webhook URL
    
    Returns:
        {"success": true, "message": "Settings updated"}
    """
    # Update environment variables (in-memory only)
    os.environ["NOWPAYMENTS_API_KEY"] = settings.apiKey
    os.environ["PAYMENTS_WEBHOOK_SECRET"] = settings.ipnSecret
    os.environ["APP_URL"] = settings.webhookUrl.replace("/api/payments/webhook-wallet", "")
    
    # TODO: For production, write to .env file
    # with open("/app/backend/.env", "a") as f:
    #     f.write(f"\nNOWPAYMENTS_API_KEY={settings.apiKey}\n")
    
    return {
        "success": True,
        "message": "Settings updated. Note: Restart server to persist changes."
    }


# ═══════════════════════════════════════════════════════════════
# USER MANAGEMENT
# ═══════════════════════════════════════════════════════════════

@router.post("/activate-pro/{user_id}")
async def manually_activate_pro(user_id: str, days: int = 30):
    """
    Manually activate PRO for a user (admin action).
    
    Args:
        user_id: User ID to activate
        days: Number of days to grant PRO (default 30)
    
    Returns:
        {"success": true, "user_id": "...", "expiresAt": "..."}
    """
    from services.payments.wallet_service import activate_pro
    
    try:
        # Activate PRO with custom duration
        await activate_pro(user_id, payment_id="admin_manual")
        
        # Get updated user
        db = _get_db()
        user = await db.users.find_one({"_id": user_id})
        
        return {
            "success": True,
            "user_id": user_id,
            "plan": user.get("plan"),
            "expiresAt": user.get("expiresAt").isoformat() if user.get("expiresAt") else None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/deactivate-pro/{user_id}")
async def manually_deactivate_pro(user_id: str):
    """
    Manually deactivate PRO for a user (admin action).
    
    Args:
        user_id: User ID to deactivate
    
    Returns:
        {"success": true, "user_id": "..."}
    """
    db = _get_db()
    
    try:
        result = await db.users.update_one(
            {"_id": user_id},
            {"$set": {
                "plan": "FREE",
                "planStatus": "INACTIVE",
                "expiresAt": None,
                "subscription.status": "CANCELLED"
            }}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="User not found")
        
        return {
            "success": True,
            "user_id": user_id
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
