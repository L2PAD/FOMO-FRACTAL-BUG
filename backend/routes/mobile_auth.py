from fastapi import APIRouter, Depends, HTTPException, status, Header
from pydantic import BaseModel
from typing import Optional
import os
import logging
from datetime import datetime, timedelta
from jose import jwt, JWTError
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from dotenv import load_dotenv
from pathlib import Path
from pymongo import MongoClient
import uuid
import hashlib
import secrets
import re

import bcrypt

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).parent.parent
load_dotenv(ROOT_DIR / '.env')

# Config
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID', '')
JWT_ACCESS_SECRET = os.getenv('JWT_ACCESS_SECRET', 'dev_access_secret')
JWT_REFRESH_SECRET = os.getenv('JWT_REFRESH_SECRET', 'dev_refresh_secret')
MONGO_URL = os.getenv('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.getenv('DB_NAME', 'test_database')

# DB
client = MongoClient(MONGO_URL)
db = client[DB_NAME]
users_collection = db['users']
refresh_tokens_collection = db['refresh_tokens']

# Ensure indexes
users_collection.create_index('email', unique=True)
users_collection.create_index('googleId')
refresh_tokens_collection.create_index('userId')
refresh_tokens_collection.create_index('expiresAt', expireAfterSeconds=0)

# Plan rank hierarchy for subscription sync
PLAN_RANK = {'FREE': 0, 'TRIAL': 1, 'PRO': 2, 'INSTITUTIONAL': 3}

auth_router = APIRouter(prefix='/api/mobile/auth', tags=['auth'])


# ==================== DTOs ====================

class GoogleAuthRequest(BaseModel):
    idToken: str


class RefreshRequest(BaseModel):
    refreshToken: str


# ==================== HELPERS ====================

def create_access_token(user_id: str, email: str, plan: str) -> str:
    payload = {
        'sub': user_id,
        'email': email,
        'plan': plan,
        'exp': datetime.utcnow() + timedelta(minutes=15),
        'iat': datetime.utcnow(),
        'type': 'access',
    }
    return jwt.encode(payload, JWT_ACCESS_SECRET, algorithm='HS256')


def create_refresh_token(user_id: str) -> str:
    payload = {
        'sub': user_id,
        'exp': datetime.utcnow() + timedelta(days=30),
        'iat': datetime.utcnow(),
        'type': 'refresh',
        'jti': str(uuid.uuid4()),
    }
    return jwt.encode(payload, JWT_REFRESH_SECRET, algorithm='HS256')


def verify_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, JWT_ACCESS_SECRET, algorithms=['HS256'])
        if payload.get('type') != 'access':
            raise JWTError('Invalid token type')
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f'Invalid token: {str(e)}',
        )


def get_current_user(authorization: Optional[str] = Header(None)):
    """Dependency to extract current user from Bearer token header"""
    if not authorization or not authorization.startswith('Bearer '):
        raise HTTPException(status_code=401, detail='Missing authorization header')
    token = authorization.replace('Bearer ', '')
    payload = verify_access_token(token)
    user = users_collection.find_one({'_id': payload['sub']})
    if not user:
        raise HTTPException(status_code=401, detail='User not found')

    # Sync subscription from linked Telegram (cross-platform PRO)
    chat_id = user.get('telegramChatId')
    if chat_id:
        current_plan = user.get('plan', 'FREE')
        current_rank = PLAN_RANK.get(current_plan, 0)
        # Check other users with same chatId for higher plan
        all_with_chat = list(users_collection.find({'telegramChatId': chat_id}))
        best_plan = current_plan
        best_rank = current_rank
        for u in all_with_chat:
            p = u.get('plan', 'FREE')
            r = PLAN_RANK.get(p, 0)
            if r > best_rank:
                best_plan = p
                best_rank = r
        if best_rank > current_rank:
            users_collection.update_one(
                {'_id': user['_id']},
                {'$set': {
                    'plan': best_plan,
                    'subscription.plan': best_plan,
                    'access.fullSignals': best_plan != 'FREE',
                    'access.fullIntel': best_plan != 'FREE',
                    'access.edge': best_plan != 'FREE',
                    'updatedAt': datetime.utcnow(),
                }}
            )
            user = users_collection.find_one({'_id': user['_id']})
            logger.info(f'Subscription synced for {user.get("email")}: {current_plan} -> {best_plan}')

    return user


def get_optional_user(authorization: Optional[str] = Header(None)):
    """Dependency for optional auth — returns user if token present, None otherwise.
    Used for endpoints that work both with and without login (e.g. Home, Feed)."""
    if not authorization or not authorization.startswith('Bearer '):
        return None
    try:
        token = authorization.replace('Bearer ', '')
        payload = verify_access_token(token)
        user = users_collection.find_one({'_id': payload['sub']})
        return user
    except Exception:
        return None


def user_to_response(user: dict) -> dict:
    return {
        'id': user['_id'],
        'email': user['email'],
        'name': user.get('name', ''),
        'avatarUrl': user.get('avatar') or user.get('avatarUrl'),
        'plan': user.get('plan', 'FREE'),
        'planStatus': user.get('planStatus', 'ACTIVE'),
        'memberSince': user.get('memberSince', datetime.utcnow().strftime('%b %Y')),
        'hasPassword': bool(user.get('passwordHash')),
        'authProviders': user.get('authProviders', {'google': False, 'email': False, 'telegram': False}),
        'linkedApps': user.get('linkedApps', {'web': False, 'miniapp': False, 'mobile': True}),
        'subscription': user.get('subscription', {
            'plan': user.get('plan', 'FREE'),
            'status': 'ACTIVE',
            'renewsAt': None,
            'price': '$0/month',
        }),
        'access': user.get('access', {
            'miniSignals': True,
            'fullSignals': user.get('plan', 'FREE') != 'FREE',
            'fullIntel': user.get('plan', 'FREE') != 'FREE',
            'edge': user.get('plan', 'FREE') != 'FREE',
            'tradingPreview': False,
            'tradingFull': False,
        }),
        'preferences': {
            'defaultAsset': user.get('preferences', {}).get('defaultAsset', 'BTC'),
            'theme': user.get('preferences', {}).get('theme', 'dark'),
            'language': user.get('preferences', {}).get('language', 'en'),
            'notifications': user.get('preferences', {}).get('notifications', True),
            'startScreen': user.get('preferences', {}).get('startScreen', 'HOME'),
            'haptics': user.get('preferences', {}).get('haptics', True),
            'dataSources': user.get('preferences', {}).get('dataSources', {
                'exchange': True,
                'onchain': True,
                'sentiment': True,
                'fractals': True,
                'technicals': True,
                'prediction': True,
            }),
            'notificationSettings': user.get('preferences', {}).get('notificationSettings', {
                'decisionChanges': True,
                'confidenceShifts': True,
                'keyEvents': True,
                'edgeOpportunities': False,
                'edgeHigh': True,
                'highImpactFeed': True,
                'allFeedEvents': False,
                'billing': True,
                'systemUpdates': False,
                'push': True,
                'email': False,
            }),
        },
        'referrals': user.get('referrals', {
            'code': f"FOMO-{user['_id'][-4:].upper()}",
            'invites': 0,
            'paidReferrals': 0,
            'earned': '$0',
        }),
        'stats': user.get('stats', {
            'signalsViewed': 0,
            'edgeBetsPlaced': 0,
            'avgSessionMin': 0,
        }),
        'twoFactorEnabled': user.get('twoFactorEnabled', False),
        'telegramUsername': user.get('telegramUsername'),
    }


def verify_google_token(id_token_str: str) -> dict:
    """Verify Google ID token and return user info"""
    try:
        idinfo = id_token.verify_oauth2_token(
            id_token_str,
            google_requests.Request(),
            GOOGLE_CLIENT_ID,
        )
        
        if idinfo['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
            raise ValueError('Wrong issuer')
        
        return {
            'email': idinfo['email'],
            'name': idinfo.get('name', idinfo['email'].split('@')[0]),
            'picture': idinfo.get('picture'),
            'googleId': idinfo['sub'],
            'emailVerified': idinfo.get('email_verified', False),
        }
    except ValueError as e:
        logger.error(f'Google token verification failed: {e}')
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f'Invalid Google token: {str(e)}',
        )


# ==================== ROUTES ====================

@auth_router.post('/google')
async def google_auth(body: GoogleAuthRequest):
    """Authenticate with Google ID token"""
    # Verify Google token
    google_info = verify_google_token(body.idToken)
    
    if not google_info.get('emailVerified', False):
        raise HTTPException(status_code=401, detail='Google email not verified')
    
    # Find or create user
    user = users_collection.find_one({'email': google_info['email']})
    
    now = datetime.utcnow()
    
    if not user:
        # Create new user
        user_id = f'u_{uuid.uuid4().hex[:12]}'
        user = {
            '_id': user_id,
            'email': google_info['email'],
            'name': google_info['name'],
            'avatarUrl': google_info.get('picture'),
            'googleId': google_info['googleId'],
            'plan': 'FREE',
            'planStatus': 'ACTIVE',
            'memberSince': now.strftime('%b %Y'),
            'createdAt': now,
            'updatedAt': now,
            'authProviders': {'google': True, 'email': False, 'telegram': False},
            'linkedApps': {'web': False, 'miniapp': False, 'mobile': True},
            'subscription': {
                'plan': 'FREE',
                'status': 'ACTIVE',
                'renewsAt': None,
                'price': '$0/month',
            },
            'access': {
                'miniSignals': True,
                'fullSignals': False,
                'fullIntel': False,
                'edge': False,
                'tradingPreview': False,
                'tradingFull': False,
            },
            'preferences': {
                'defaultAsset': 'BTC',
                'theme': 'dark',
                'language': 'en',
                'notifications': True,
            },
            'referrals': {
                'code': f'FOMO-{user_id[-4:].upper()}',
                'invites': 0,
                'paidReferrals': 0,
                'earned': '$0',
            },
            'stats': {
                'signalsViewed': 0,
                'edgeBetsPlaced': 0,
                'avgSessionMin': 0,
            },
        }
        users_collection.insert_one(user)
        logger.info(f'Created new user: {user["email"]}')
    else:
        # Update existing user - link Google if not yet
        update = {
            'updatedAt': now,
            'authProviders.google': True,
            'linkedApps.mobile': True,
        }
        if not user.get('avatarUrl') and google_info.get('picture'):
            update['avatarUrl'] = google_info['picture']
        if not user.get('googleId'):
            update['googleId'] = google_info['googleId']
        
        users_collection.update_one({'_id': user['_id']}, {'$set': update})
        user = users_collection.find_one({'_id': user['_id']})
        logger.info(f'Updated existing user: {user["email"]}')
    
    # Generate tokens
    access_token = create_access_token(user['_id'], user['email'], user.get('plan', 'FREE'))
    refresh_token = create_refresh_token(user['_id'])
    
    # Store refresh token
    refresh_tokens_collection.insert_one({
        'token': refresh_token,
        'userId': user['_id'],
        'createdAt': now,
        'expiresAt': now + timedelta(days=30),
    })
    
    return {
        'accessToken': access_token,
        'refreshToken': refresh_token,
        'user': user_to_response(user),
    }


@auth_router.post('/refresh')
async def refresh_token(body: RefreshRequest):
    """Refresh access token"""
    try:
        payload = jwt.decode(body.refreshToken, JWT_REFRESH_SECRET, algorithms=['HS256'])
        if payload.get('type') != 'refresh':
            raise JWTError('Invalid token type')
    except JWTError:
        raise HTTPException(status_code=401, detail='Invalid refresh token')
    
    user_id = payload['sub']
    
    # Verify refresh token exists in DB
    stored = refresh_tokens_collection.find_one({'token': body.refreshToken, 'userId': user_id})
    if not stored:
        raise HTTPException(status_code=401, detail='Refresh token revoked')
    
    user = users_collection.find_one({'_id': user_id})
    if not user:
        raise HTTPException(status_code=401, detail='User not found')
    
    # Rotate tokens
    refresh_tokens_collection.delete_one({'_id': stored['_id']})
    
    new_access = create_access_token(user['_id'], user['email'], user.get('plan', 'FREE'))
    new_refresh = create_refresh_token(user['_id'])
    
    now = datetime.utcnow()
    refresh_tokens_collection.insert_one({
        'token': new_refresh,
        'userId': user['_id'],
        'createdAt': now,
        'expiresAt': now + timedelta(days=30),
    })
    
    return {
        'accessToken': new_access,
        'refreshToken': new_refresh,
        'user': user_to_response(user),
    }


@auth_router.get('/me')
async def get_me(user: dict = Depends(get_current_user)):
    """Get current authenticated user"""
    return user_to_response(user)


@auth_router.post('/logout')
async def logout(body: RefreshRequest):
    """Logout - invalidate refresh token"""
    try:
        payload = jwt.decode(body.refreshToken, JWT_REFRESH_SECRET, algorithms=['HS256'])
        refresh_tokens_collection.delete_many({'userId': payload['sub']})
    except JWTError:
        pass  # Logout should be idempotent
    
    return {'success': True}


# ==================== ACCOUNT MANAGEMENT ====================

@auth_router.patch('/update-email')
async def request_email_change(body: dict, user: dict = Depends(get_current_user)):
    """
    Step 1: Request email change.
    Validates new email, generates 6-digit OTP, sends to OLD email via SMTP.
    Falls back to Telegram if SMTP not configured.
    """
    import random
    from services.email_service import send_otp_email, is_smtp_configured

    new_email = body.get('email', '').strip().lower()

    if not new_email:
        raise HTTPException(status_code=400, detail='Email is required')

    # Strict email validation
    if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', new_email):
        raise HTTPException(status_code=400, detail='Invalid email format')

    if new_email == user.get('email'):
        raise HTTPException(status_code=400, detail='Same as current email')

    # Check if email is already taken
    existing = users_collection.find_one({'email': new_email})
    if existing:
        raise HTTPException(status_code=409, detail='Email already in use')

    # Generate 6-digit OTP
    otp_code = str(random.randint(100000, 999999))
    expires = datetime.utcnow() + timedelta(minutes=10)

    # Store pending email change
    users_collection.update_one(
        {'_id': user['_id']},
        {'$set': {
            'pendingEmailChange': {
                'newEmail': new_email,
                'otpCode': otp_code,
                'expiresAt': expires,
                'createdAt': datetime.utcnow(),
            }
        }}
    )

    old_email = user.get('email', '')
    delivery_method = 'none'

    # Priority 1: Send OTP to OLD email via SMTP
    if old_email and is_smtp_configured():
        email_sent = await send_otp_email(old_email, otp_code, new_email)
        if email_sent:
            delivery_method = 'email'

    # Priority 2: Fallback to Telegram
    if delivery_method == 'none':
        try:
            bot_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
            telegram_chat_id = user.get('telegramChatId')
            if bot_token and telegram_chat_id:
                import httpx
                msg = (
                    f"🔐 *Код подтверждения смены email*\n\n"
                    f"Ваш код: `{otp_code}`\n\n"
                    f"Новый email: {new_email}\n"
                    f"Действителен 10 минут.\n\n"
                    f"Если вы не запрашивали смену — проигнорируйте."
                )
                async with httpx.AsyncClient() as client:
                    resp = await client.post(
                        f"https://api.telegram.org/bot{bot_token}/sendMessage",
                        json={"chat_id": telegram_chat_id, "text": msg, "parse_mode": "Markdown"}
                    )
                    if resp.json().get('ok'):
                        delivery_method = 'telegram'
        except Exception as e:
            logger.warning(f"Failed to send OTP via Telegram: {e}")

    logger.info(f'Email change requested: {old_email} → {new_email}, OTP sent via {delivery_method}')

    return {
        'success': True,
        'step': 'otp_sent',
        'deliveryMethod': delivery_method,
        'message': f'Code sent to {old_email}' if delivery_method == 'email' else 'Verification code generated',
        # Show code only when neither email nor telegram delivery worked
        **({'devCode': otp_code} if delivery_method == 'none' else {}),
    }


@auth_router.post('/confirm-email-change')
async def confirm_email_change(body: dict, user: dict = Depends(get_current_user)):
    """
    Step 2: Confirm email change with OTP code.
    """
    otp_code = body.get('code', '').strip()

    if not otp_code or len(otp_code) != 6:
        raise HTTPException(status_code=400, detail='6-digit code required')

    pending = user.get('pendingEmailChange')
    if not pending:
        raise HTTPException(status_code=400, detail='No pending email change')

    # Check expiry
    if datetime.utcnow() > pending['expiresAt']:
        users_collection.update_one({'_id': user['_id']}, {'$unset': {'pendingEmailChange': 1}})
        raise HTTPException(status_code=410, detail='Code expired. Request a new one.')

    # Verify code
    if otp_code != pending['otpCode']:
        raise HTTPException(status_code=403, detail='Incorrect code')

    new_email = pending['newEmail']

    # Double-check email not taken
    existing = users_collection.find_one({'email': new_email})
    if existing:
        users_collection.update_one({'_id': user['_id']}, {'$unset': {'pendingEmailChange': 1}})
        raise HTTPException(status_code=409, detail='Email already in use')

    # Apply email change
    old_email = user.get('email')
    users_collection.update_one(
        {'_id': user['_id']},
        {
            '$set': {
                'email': new_email,
                'authProviders.email': True,
                'updatedAt': datetime.utcnow(),
            },
            '$unset': {'pendingEmailChange': 1}
        }
    )

    updated = users_collection.find_one({'_id': user['_id']})
    logger.info(f'Email confirmed: {old_email} → {new_email}')
    return {'success': True, 'user': user_to_response(updated)}



import re as _re

def _validate_password(password: str):
    """Validate password strength: 8+ chars, uppercase, digit, special char, Latin only."""
    if len(password) < 8:
        raise HTTPException(status_code=400, detail='Password must be at least 8 characters')
    if _re.search(r'[а-яА-ЯёЁ]', password):
        raise HTTPException(status_code=400, detail='Password must use Latin characters only')
    if not _re.search(r'[A-Z]', password):
        raise HTTPException(status_code=400, detail='Password must contain at least one uppercase letter')
    if not _re.search(r'[0-9]', password):
        raise HTTPException(status_code=400, detail='Password must contain at least one digit')
    if not _re.search(r'[!@#$%^&*()_+\-=\[\]{};\':\"\\|,.<>\/?~`]', password):
        raise HTTPException(status_code=400, detail='Password must contain at least one special character')


@auth_router.post('/set-password')
async def set_password(body: dict, user: dict = Depends(get_current_user)):
    """Set password for users who don't have one (e.g. Google OAuth users). Requires 2FA."""
    password = body.get('password', '')
    totp_code = body.get('totpCode', '')

    # 2FA must be enabled and code verified
    if not user.get('twoFactorEnabled'):
        raise HTTPException(status_code=403, detail='Enable 2FA before setting a password')

    if not totp_code or len(totp_code) != 6:
        raise HTTPException(status_code=400, detail='Valid 6-digit 2FA code required')

    secret = user.get('twoFactorSecret', '')
    if not secret:
        raise HTTPException(status_code=400, detail='2FA secret not found')

    import pyotp
    totp = pyotp.TOTP(secret)
    if not totp.verify(totp_code, valid_window=1):
        raise HTTPException(status_code=401, detail='Invalid 2FA code')

    # Password validation
    _validate_password(password)

    if user.get('passwordHash'):
        raise HTTPException(status_code=400, detail='Password already set. Use change-password instead')

    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    now = datetime.utcnow()
    users_collection.update_one(
        {'_id': user['_id']},
        {'$set': {
            'passwordHash': hashed,
            'authProviders.email': True,
            'updatedAt': now,
        }}
    )

    logger.info(f'Password set for user: {user["email"]}')
    return {'success': True, 'message': 'Password set successfully'}


@auth_router.post('/change-password')
async def change_password(body: dict, user: dict = Depends(get_current_user)):
    """Change existing password — requires current password + 2FA code"""
    current_password = body.get('currentPassword', '')
    new_password = body.get('newPassword', '')
    totp_code = body.get('totpCode', '')

    # 2FA must be enabled and code verified
    if not user.get('twoFactorEnabled'):
        raise HTTPException(status_code=403, detail='Enable 2FA before changing password')

    if not totp_code or len(totp_code) != 6:
        raise HTTPException(status_code=400, detail='Valid 6-digit 2FA code required')

    secret = user.get('twoFactorSecret', '')
    if not secret:
        raise HTTPException(status_code=400, detail='2FA secret not found')

    import pyotp
    totp = pyotp.TOTP(secret)
    if not totp.verify(totp_code, valid_window=1):
        raise HTTPException(status_code=401, detail='Invalid 2FA code')

    if not user.get('passwordHash'):
        raise HTTPException(status_code=400, detail='No password set. Use set-password instead')

    # Verify current password
    if not bcrypt.checkpw(current_password.encode('utf-8'), user['passwordHash'].encode('utf-8')):
        raise HTTPException(status_code=401, detail='Current password is incorrect')

    # Validate new password
    _validate_password(new_password)

    if current_password == new_password:
        raise HTTPException(status_code=400, detail='New password must be different from current')

    hashed = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    now = datetime.utcnow()
    users_collection.update_one(
        {'_id': user['_id']},
        {'$set': {
            'passwordHash': hashed,
            'updatedAt': now,
        }}
    )

    logger.info(f'Password changed for user: {user["email"]}')
    return {'success': True, 'message': 'Password changed successfully'}


# ==================== REFERRAL SYSTEM ====================

referrals_collection = db['referrals']
referrals_collection.create_index('code', unique=True)
referrals_collection.create_index('referrerId')
referrals_collection.create_index('referredUserId')


def generate_referral_code(user_id: str) -> str:
    """Generate a unique referral code"""
    base = hashlib.md5(user_id.encode()).hexdigest()[:6].upper()
    return f'FOMO-{base}'


def ensure_referral_code(user: dict) -> str:
    """Ensure user has a referral code, create if missing"""
    referrals = user.get('referrals', {})
    code = referrals.get('code', '')

    if not code or code.startswith('FOMO-') and len(code) < 8:
        code = generate_referral_code(user['_id'])
        users_collection.update_one(
            {'_id': user['_id']},
            {'$set': {'referrals.code': code}}
        )
    return code


@auth_router.get('/referrals')
async def get_referrals(user: dict = Depends(get_current_user)):
    """Get user's referral data — code, invites, earnings"""
    code = ensure_referral_code(user)

    # Count actual referrals
    total_invites = referrals_collection.count_documents({'referrerId': user['_id']})
    paid_referrals = referrals_collection.count_documents({
        'referrerId': user['_id'],
        'referredUserPlan': {'$ne': 'FREE'},
    })

    # Calculate earnings ($5 per paid referral for now)
    earnings = paid_referrals * 5

    return {
        'code': code,
        'invites': total_invites,
        'paidReferrals': paid_referrals,
        'earned': f'${earnings}',
        'shareUrl': f'https://fomo.ai/r/{code}',
    }


# Promo codes collection (admin-managed)
promo_codes_collection = db['promo_codes']
promo_codes_collection.create_index('code', unique=True)
promo_codes_usage_collection = db['promo_codes_usage']
promo_codes_usage_collection.create_index([('userId', 1), ('promoCode', 1)], unique=True)


@auth_router.post('/referrals/apply')
async def apply_referral_code(body: dict, user: dict = Depends(get_current_user)):
    """Apply a referral code or promo code"""
    code = body.get('code', '').strip().upper()

    if not code:
        raise HTTPException(status_code=400, detail='Code is required')

    # ── 1. Try as PROMO CODE first ──
    promo = promo_codes_collection.find_one({'code': code})
    if promo:
        # Check if promo is active
        now = datetime.utcnow()
        if promo.get('expiresAt') and promo['expiresAt'] < now:
            raise HTTPException(status_code=400, detail='Promo code has expired')
        if promo.get('maxUses') and promo.get('usedCount', 0) >= promo['maxUses']:
            raise HTTPException(status_code=400, detail='Promo code usage limit reached')

        # Check if user already used this promo
        already_used = promo_codes_usage_collection.find_one({
            'userId': user['_id'], 'promoCode': code
        })
        if already_used:
            raise HTTPException(status_code=400, detail='You have already used this promo code')

        # Apply promo benefit
        benefit = promo.get('benefit', {})
        update_user = {}
        benefit_msg = ''

        if benefit.get('type') == 'plan_upgrade':
            new_plan = benefit.get('plan', 'PRO')
            update_user['plan'] = new_plan
            update_user['subscription.plan'] = new_plan
            update_user['subscription.status'] = 'ACTIVE'
            update_user['access.fullSignals'] = True
            update_user['access.fullIntel'] = True
            update_user['access.edge'] = True
            benefit_msg = f'Plan upgraded to {new_plan}!'
        elif benefit.get('type') == 'discount':
            pct = benefit.get('percent', 0)
            benefit_msg = f'{pct}% discount applied!'
        elif benefit.get('type') == 'trial_extend':
            days = benefit.get('days', 7)
            benefit_msg = f'{days}-day trial extension applied!'
        else:
            benefit_msg = 'Promo code applied!'

        if update_user:
            update_user['updatedAt'] = now
            users_collection.update_one({'_id': user['_id']}, {'$set': update_user})

        # Record usage
        promo_codes_usage_collection.insert_one({
            'userId': user['_id'],
            'promoCode': code,
            'benefit': benefit,
            'appliedAt': now,
        })
        promo_codes_collection.update_one(
            {'code': code},
            {'$inc': {'usedCount': 1}}
        )

        logger.info(f'Promo code applied: {user.get("email")} used {code} — {benefit_msg}')
        return {'success': True, 'message': benefit_msg}

    # ── 2. Try as REFERRAL CODE ──
    # Check if user already used a referral
    existing = referrals_collection.find_one({'referredUserId': user['_id']})
    if existing:
        raise HTTPException(status_code=400, detail='You have already used a referral code')

    # Prevent self-referral
    user_code = ensure_referral_code(user)
    if code == user_code:
        raise HTTPException(status_code=400, detail='Cannot use your own referral code')

    # Find referrer by code
    referrer = users_collection.find_one({'referrals.code': code})
    if not referrer:
        raise HTTPException(status_code=404, detail='Invalid code')

    now = datetime.utcnow()

    # Record referral
    referrals_collection.insert_one({
        'referrerId': referrer['_id'],
        'referredUserId': user['_id'],
        'code': code,
        'referredUserPlan': user.get('plan', 'FREE'),
        'createdAt': now,
    })

    # Update referrer stats
    total = referrals_collection.count_documents({'referrerId': referrer['_id']})
    paid = referrals_collection.count_documents({
        'referrerId': referrer['_id'],
        'referredUserPlan': {'$ne': 'FREE'},
    })
    users_collection.update_one(
        {'_id': referrer['_id']},
        {'$set': {
            'referrals.invites': total,
            'referrals.paidReferrals': paid,
            'referrals.earned': f'${paid * 5}',
        }}
    )

    logger.info(f'Referral applied: {user["email"]} used code {code} from {referrer["email"]}')
    return {'success': True, 'message': f'Referral code applied! Invited by {referrer.get("name", "a friend")}'}


# ==================== TWO-FACTOR AUTHENTICATION ====================

@auth_router.post('/2fa/setup')
async def setup_2fa(user: dict = Depends(get_current_user)):
    """Generate TOTP secret for 2FA setup"""
    import pyotp

    if user.get('twoFactorEnabled'):
        raise HTTPException(status_code=400, detail='2FA is already enabled')

    secret = pyotp.random_base32()

    users_collection.update_one(
        {'_id': user['_id']},
        {'$set': {'twoFactorSecret': secret, 'updatedAt': datetime.utcnow()}}
    )

    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(name=user.get('email', ''), issuer_name='FOMO')

    return {
        'secret': secret,
        'uri': uri,
        'issuer': 'FOMO',
        'account': user.get('email', ''),
    }


@auth_router.post('/2fa/verify')
async def verify_2fa(body: dict, user: dict = Depends(get_current_user)):
    """Verify TOTP code and enable 2FA"""
    import pyotp

    code = body.get('code', '').strip()
    if not code or len(code) != 6:
        raise HTTPException(status_code=400, detail='Code must be 6 digits')

    secret = user.get('twoFactorSecret')
    if not secret:
        raise HTTPException(status_code=400, detail='No 2FA setup in progress. Call /2fa/setup first')

    totp = pyotp.TOTP(secret)
    if not totp.verify(code, valid_window=1):
        raise HTTPException(status_code=400, detail='Invalid verification code')

    users_collection.update_one(
        {'_id': user['_id']},
        {'$set': {
            'twoFactorEnabled': True,
            'updatedAt': datetime.utcnow(),
        }}
    )

    logger.info(f'2FA enabled for user: {user["email"]}')
    return {'success': True, 'message': '2FA enabled successfully'}


@auth_router.post('/2fa/disable')
async def disable_2fa(body: dict, user: dict = Depends(get_current_user)):
    """Disable 2FA — requires valid TOTP code"""
    import pyotp

    code = body.get('code', '').strip()
    if not code:
        raise HTTPException(status_code=400, detail='Verification code is required')

    if not user.get('twoFactorEnabled'):
        raise HTTPException(status_code=400, detail='2FA is not enabled')

    secret = user.get('twoFactorSecret')
    if not secret:
        raise HTTPException(status_code=400, detail='2FA secret not found')

    totp = pyotp.TOTP(secret)
    if not totp.verify(code, valid_window=1):
        raise HTTPException(status_code=400, detail='Invalid verification code')

    users_collection.update_one(
        {'_id': user['_id']},
        {'$set': {
            'twoFactorEnabled': False,
            'twoFactorSecret': None,
            'updatedAt': datetime.utcnow(),
        }}
    )

    logger.info(f'2FA disabled for user: {user["email"]}')
    return {'success': True, 'message': '2FA disabled'}


# ==================== SUBSCRIPTION SYNC ====================

@auth_router.post('/sync-subscription')
async def sync_subscription(user: dict = Depends(get_current_user)):
    """
    Manually trigger subscription sync between platforms.
    Checks if the user's linked Telegram has a higher plan (e.g. PRO from MiniApp).
    """
    chat_id = user.get('telegramChatId')
    if not chat_id:
        return {
            'success': True,
            'plan': user.get('plan', 'FREE'),
            'synced': False,
            'message': 'No Telegram linked',
        }

    old_plan = user.get('plan', 'FREE')
    old_rank = PLAN_RANK.get(old_plan, 0)

    # Find all users with this chatId
    all_with_chat = list(users_collection.find({'telegramChatId': chat_id}))
    best_plan = old_plan
    best_rank = old_rank

    for u in all_with_chat:
        p = u.get('plan', 'FREE')
        r = PLAN_RANK.get(p, 0)
        if r > best_rank:
            best_plan = p
            best_rank = r

    synced = False
    if best_rank > old_rank:
        users_collection.update_one(
            {'_id': user['_id']},
            {'$set': {
                'plan': best_plan,
                'subscription.plan': best_plan,
                'subscription.status': 'ACTIVE',
                'access.fullSignals': best_plan != 'FREE',
                'access.fullIntel': best_plan != 'FREE',
                'access.edge': best_plan != 'FREE',
                'updatedAt': datetime.utcnow(),
            }}
        )
        synced = True
        logger.info(f'Manual subscription sync for {user.get("email")}: {old_plan} -> {best_plan}')

    return {
        'success': True,
        'plan': best_plan,
        'synced': synced,
        'previousPlan': old_plan,
    }


# ==================== TELEGRAM LINKING ====================

@auth_router.post('/telegram-link-code')
async def generate_telegram_link_code(user: dict = Depends(get_current_user)):
    """Generate a one-time code for linking Telegram via bot."""
    import random
    import string
    
    code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    expires = datetime.utcnow() + timedelta(minutes=10)
    
    users_collection.update_one(
        {'_id': user['_id']},
        {'$set': {
            'telegramLinkCode': code,
            'telegramLinkExpires': expires,
        }}
    )
    
    bot_url = f"https://t.me/FOMO_Trading_bot?start=link_{code}"
    logger.info(f'Telegram link code generated for {user["email"]}: {code}')
    return {
        'success': True,
        'code': code,
        'botUrl': bot_url,
        'expiresIn': 600,
    }


@auth_router.get('/telegram-status')
async def get_telegram_status(user: dict = Depends(get_current_user)):
    """Check if Telegram is linked."""
    return {
        'linked': bool(user.get('telegramChatId')),
        'username': user.get('telegramUsername'),
        'chatId': user.get('telegramChatId'),
    }


@auth_router.delete('/unlink-telegram')
async def unlink_telegram(user: dict = Depends(get_current_user)):
    """Unlink Telegram from account."""
    users_collection.update_one(
        {'_id': user['_id']},
        {
            '$set': {
                'authProviders.telegram': False,
                'updatedAt': datetime.utcnow(),
            },
            '$unset': {
                'telegramUsername': 1,
                'telegramChatId': 1,
                'telegramLinkCode': 1,
                'telegramLinkExpires': 1,
            }
        }
    )
    logger.info(f'Telegram unlinked for user: {user["email"]}')
    return {'success': True}


# ==================== DEV LOGIN (Remove in production) ====================

class DevLoginRequest(BaseModel):
    email: str = 'ddvtop@gmail.com'
    name: str = 'FOMO Developer'


@auth_router.post('/dev-login')
async def dev_login(body: DevLoginRequest):
    """Development-only login - bypasses Google OAuth.
    Creates or finds a user by email and returns JWT tokens.
    REMOVE THIS ENDPOINT IN PRODUCTION.
    """
    now = datetime.utcnow()
    
    user = users_collection.find_one({'email': body.email})
    
    if not user:
        user_id = f'u_{uuid.uuid4().hex[:12]}'
        user = {
            '_id': user_id,
            'email': body.email,
            'name': body.name,
            'avatarUrl': None,
            'googleId': None,
            'plan': 'FREE',
            'planStatus': 'ACTIVE',
            'memberSince': now.strftime('%b %Y'),
            'createdAt': now,
            'updatedAt': now,
            'authProviders': {'google': False, 'email': True, 'telegram': False},
            'linkedApps': {'web': False, 'miniapp': False, 'mobile': True},
            'subscription': {
                'plan': 'FREE',
                'status': 'ACTIVE',
                'renewsAt': None,
                'price': '$0/month',
            },
            'access': {
                'miniSignals': True,
                'fullSignals': False,
                'fullIntel': False,
                'edge': False,
                'tradingPreview': False,
                'tradingFull': False,
            },
            'preferences': {
                'defaultAsset': 'BTC',
                'theme': 'dark',
                'language': 'en',
                'notifications': True,
            },
            'referrals': {
                'code': f'FOMO-{user_id[-4:].upper()}',
                'invites': 0,
                'paidReferrals': 0,
                'earned': '$0',
            },
            'stats': {
                'signalsViewed': 0,
                'edgeBetsPlaced': 0,
                'avgSessionMin': 0,
            },
        }
        users_collection.insert_one(user)
        logger.info(f'DEV LOGIN: Created new user: {user["email"]}')
    else:
        users_collection.update_one(
            {'_id': user['_id']},
            {'$set': {'updatedAt': now, 'linkedApps.mobile': True}}
        )
        user = users_collection.find_one({'_id': user['_id']})
        logger.info(f'DEV LOGIN: Logged in existing user: {user["email"]}')
    
    # Generate tokens
    access_token = create_access_token(user['_id'], user['email'], user.get('plan', 'FREE'))
    refresh_token = create_refresh_token(user['_id'])
    
    # Store refresh token
    refresh_tokens_collection.insert_one({
        'token': refresh_token,
        'userId': user['_id'],
        'createdAt': now,
        'expiresAt': now + timedelta(days=30),
    })
    
    return {
        'accessToken': access_token,
        'refreshToken': refresh_token,
        'user': user_to_response(user),
    }
