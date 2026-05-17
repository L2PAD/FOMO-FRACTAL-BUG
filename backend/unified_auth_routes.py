"""
MOBILE AUTH ADAPTER - Інтеграція з Unified Auth System
"""
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import Optional
import os
from datetime import datetime, timedelta
from jose import jwt
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from unified_auth import UnifiedUser

router = APIRouter(prefix='/api/unified/auth', tags=['unified-auth'])

# Config
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID', '')
JWT_ACCESS_SECRET = os.getenv('JWT_ACCESS_SECRET', 'dev_access_secret')
JWT_REFRESH_SECRET = os.getenv('JWT_REFRESH_SECRET', 'dev_refresh_secret')


class GoogleAuthRequest(BaseModel):
    idToken: str
    platform: str = 'mobile'  # mobile/web/miniapp


class DevLoginRequest(BaseModel):
    email: str
    name: str = "Developer"
    platform: str = 'mobile'


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
    }
    return jwt.encode(payload, JWT_REFRESH_SECRET, algorithm='HS256')


def user_to_response(user: dict) -> dict:
    """Конвертувати user документ в API response"""
    return {
        'id': user['_id'],
        'email': user['email'],
        'name': user.get('name'),
        'avatarUrl': user.get('avatarUrl'),
        'plan': user.get('plan', 'FREE'),
        'planStatus': user.get('planStatus', 'ACTIVE'),
        'memberSince': user.get('memberSince'),
        'authProviders': user.get('authProviders', {}),
        'linkedApps': user.get('linkedApps', {}),
        'referralCode': user.get('referralCode'),
        'preferences': user.get('preferences', {}),
        'stats': user.get('stats', {}),
        'subscription': {
            'plan': user.get('plan', 'FREE'),
            'status': user.get('planStatus', 'ACTIVE'),
            'renewsAt': user.get('planRenewsAt'),
        },
    }


@router.post('/google')
async def google_auth_unified(req: GoogleAuthRequest):
    """
    Google OAuth для всіх платформ (web/mobile/miniapp)
    Використовує Unified Auth System
    """
    try:
        # Verify Google token
        google_info = id_token.verify_oauth2_token(
            req.idToken,
            google_requests.Request(),
            GOOGLE_CLIENT_ID
        )
        
        email = google_info.get('email')
        name = google_info.get('name', email.split('@')[0])
        google_id = google_info.get('sub')
        
        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Email not provided by Google'
            )
        
        # Unified Auth - знайти або створити користувача
        user = UnifiedUser.find_or_create(
            email=email,
            name=name,
            platform=req.platform,  # web/mobile/miniapp
            auth_provider='google',
            provider_id=google_id
        )
        
        # Generate JWT tokens
        access_token = create_access_token(user['_id'], email, user.get('plan', 'FREE'))
        refresh_token = create_refresh_token(user['_id'])
        
        return {
            'accessToken': access_token,
            'refreshToken': refresh_token,
            'user': user_to_response(user),
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f'Invalid Google token: {str(e)}'
        )


@router.post('/dev-login')
async def dev_login_unified(req: DevLoginRequest):
    """
    Dev Login для всіх платформ
    Використовує Unified Auth System
    """
    # Unified Auth - знайти або створити dev користувача
    user = UnifiedUser.find_or_create(
        email=req.email,
        name=req.name,
        platform=req.platform,
        auth_provider='google',  # Для dev login теж використовуємо google
    )
    
    # Generate JWT tokens
    access_token = create_access_token(user['_id'], req.email, user.get('plan', 'FREE'))
    refresh_token = create_refresh_token(user['_id'])
    
    return {
        'accessToken': access_token,
        'refreshToken': refresh_token,
        'user': user_to_response(user),
    }


@router.get('/me')
async def get_current_user_unified(email: str):
    """
    Отримати поточного користувача
    Працює для всіх платформ
    """
    user = UnifiedUser.get_by_email(email)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='User not found'
        )
    
    return user_to_response(user)


@router.post('/sync-subscription')
async def sync_subscription(email: str, plan: str, status: str):
    """
    Синхронізувати підписку на всіх платформах
    
    Коли користувач оплачує на будь-якій платформі,
    викликаємо цей endpoint щоб оновити підписку везде
    """
    success = UnifiedUser.sync_subscription_across_platforms(email, plan, status)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='User not found'
        )
    
    user = UnifiedUser.get_by_email(email)
    
    return {
        'message': f'Subscription synced across all platforms: {plan}',
        'platforms': {
            'web': user['linkedApps'].get('web', False),
            'mobile': user['linkedApps'].get('mobile', False),
            'miniapp': user['linkedApps'].get('miniapp', False),
        },
        'subscription': {
            'plan': user['plan'],
            'status': user['planStatus'],
        }
    }
