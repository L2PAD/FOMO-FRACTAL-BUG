"""Subscription routes — NOWPayments only (crypto payments)."""
from fastapi import APIRouter, Depends, Request, HTTPException
from routes.auth import get_current_user, get_optional_user
from services.payments.wallet_service import create_invoice, handle_webhook, activate_pro
from pymongo import MongoClient
from datetime import datetime, timezone, timedelta
import logging
import os

logger = logging.getLogger(__name__)
router = APIRouter()

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "fomo_mobile")
_db = MongoClient(MONGO_URL)[DB_NAME]


@router.get('/subscription/plans')
async def get_plans():
    """Get available subscription plans (NOWPayments crypto)."""
    config = _db.billing_config.find_one({"type": "pricing"}, {"_id": 0})
    return {
        'plans': [
            {'id': 'free', 'name': 'Free', 'price': 0, 'features': ['Basic signals', 'Home screen', '3 assets']},
            {'id': 'pro', 'name': 'PRO', 'price': 19, 'currency': 'USD',
             'interval': 'month', 'paymentMethod': 'crypto',
             'features': ['All signals', 'Full feed', 'Unlimited assets', 'Edge', 'Priority alerts']},
        ],
        'paymentMethod': 'crypto',
        'provider': 'nowpayments',
    }


@router.get('/subscription/status')
async def get_subscription_status(user=Depends(get_current_user)):
    """Get current user subscription status."""
    sub = user.get('subscription', {})
    return {
        'plan': user.get('plan', 'FREE'),
        'planStatus': user.get('planStatus', 'ACTIVE'),
        'expiresAt': sub.get('renewsAt'),
        'paymentMethod': sub.get('paymentMethod', 'crypto'),
        'subscription': sub,
    }


@router.post('/subscription/create-invoice')
async def create_subscription_invoice(user=Depends(get_current_user)):
    """Create NOWPayments invoice for PRO subscription."""
    user_id = user.get('userId', user.get('email', ''))
    result = await create_invoice(user_id)
    return result


@router.post('/subscription/activate-test')
async def activate_test(user=Depends(get_current_user)):
    """DEV ONLY: activate PRO without payment for testing."""
    user_id = user.get('userId', user.get('email', ''))
    await activate_pro(user_id, payment_id="test_manual")
    return {'ok': True, 'plan': 'PRO', 'message': 'PRO activated (test mode)'}
