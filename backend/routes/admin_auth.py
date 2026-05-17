"""
Admin Auth Routes — Python port of Fastify admin auth
Handles admin panel login, status check, and user management.
"""
from fastapi import APIRouter, HTTPException, Depends, Request
from datetime import datetime, timedelta
import hashlib
import secrets
import os
import jwt
import logging

from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])

# Config
ADMIN_JWT_SECRET = os.getenv('ADMIN_JWT_SECRET', 'dev_admin_secret_change_me_in_prod')
ADMIN_JWT_TTL_SEC = int(os.getenv('ADMIN_JWT_TTL_SEC', str(60 * 60 * 12)))  # 12 hours
SEED_USERNAME = os.getenv('ADMIN_SEED_USERNAME', 'admin')
SEED_PASSWORD = os.getenv('ADMIN_SEED_PASSWORD', 'admin12345')
SEED_ROLE = os.getenv('ADMIN_SEED_ROLE', 'ADMIN')

# MongoDB
from pymongo import MongoClient
MONGO_URL = os.getenv('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.getenv('DB_NAME', 'test_database')
client = MongoClient(MONGO_URL)
db = client[DB_NAME]
admin_users = db['admin_users']
admin_audit = db['admin_audit_log']


# ============================================
# PASSWORD HASHING (PBKDF2 — compatible with Node.js version)
# ============================================
def pbkdf2_hash(password: str) -> str:
    salt = secrets.token_bytes(16)
    iterations = 120_000
    derived = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, iterations, dklen=32)
    return f"pbkdf2${iterations}${salt.hex()}${derived.hex()}"


def pbkdf2_verify(password: str, stored: str) -> bool:
    parts = stored.split('$')
    if len(parts) != 4 or parts[0] != 'pbkdf2':
        return False
    iterations = int(parts[1])
    salt = bytes.fromhex(parts[2])
    expected = bytes.fromhex(parts[3])
    derived = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, iterations, dklen=32)
    return secrets.compare_digest(derived, expected)


# ============================================
# ADMIN SEED
# ============================================
def ensure_admin_seed():
    count = admin_users.count_documents({})
    if count > 0:
        logger.info('[Admin] Admin users exist, skipping seed')
        return
    now = int(datetime.utcnow().timestamp())
    admin_users.insert_one({
        'username': SEED_USERNAME,
        'passwordHash': pbkdf2_hash(SEED_PASSWORD),
        'role': SEED_ROLE,
        'isActive': True,
        'createdAtTs': now,
        'updatedAtTs': now,
    })
    logger.info(f'[Admin] Created seed admin: {SEED_USERNAME} (role: {SEED_ROLE})')


# Run seed on import
ensure_admin_seed()


# ============================================
# JWT HELPERS
# ============================================
def create_admin_token(user_id: str, username: str, role: str) -> dict:
    now = int(datetime.utcnow().timestamp())
    exp = now + ADMIN_JWT_TTL_SEC
    payload = {
        'sub': user_id,
        'username': username,
        'role': role,
        'iat': now,
        'exp': exp,
    }
    token = jwt.encode(payload, ADMIN_JWT_SECRET, algorithm='HS256')
    return {'token': token, 'iat': now, 'exp': exp}


def verify_admin_token(token: str) -> dict:
    try:
        return jwt.decode(token, ADMIN_JWT_SECRET, algorithms=['HS256'])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail='Token expired')
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail='Invalid token')


def get_admin(request: Request) -> dict:
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        raise HTTPException(status_code=401, detail='Authorization required')
    return verify_admin_token(auth[7:])


# ============================================
# ROUTES
# ============================================
@router.post('/auth/login')
async def admin_login(body: dict):
    username = body.get('username', '')
    password = body.get('password', '')

    if not username or not password:
        raise HTTPException(status_code=400, detail='Username and password required')

    user = admin_users.find_one({'username': username, 'isActive': True})
    if not user or not pbkdf2_verify(password, user.get('passwordHash', '')):
        admin_audit.insert_one({
            'adminId': 'unknown',
            'adminUsername': username,
            'action': 'LOGIN_FAILED',
            'result': 'failure',
            'timestamp': datetime.utcnow(),
        })
        raise HTTPException(status_code=401, detail='Invalid username or password')

    token_data = create_admin_token(str(user['_id']), username, user['role'])

    admin_audit.insert_one({
        'adminId': str(user['_id']),
        'adminUsername': username,
        'action': 'LOGIN_SUCCESS',
        'result': 'success',
        'timestamp': datetime.utcnow(),
    })

    return {
        'ok': True,
        'token': token_data['token'],
        'role': user['role'],
        'username': username,
        'issuedAtTs': token_data['iat'],
        'expiresAtTs': token_data['exp'],
    }


@router.get('/auth/status')
async def admin_status(admin=Depends(get_admin)):
    now = int(datetime.utcnow().timestamp())
    return {
        'ok': True,
        'data': {
            'role': admin['role'],
            'userId': admin['sub'],
            'issuedAtTs': admin['iat'],
            'expiresAtTs': admin['exp'],
            'expiresIn': admin['exp'] - now,
        },
    }


@router.get('/auth/users')
async def list_admin_users(admin=Depends(get_admin)):
    if admin['role'] != 'ADMIN':
        raise HTTPException(status_code=403, detail='Admin role required')
    users = list(admin_users.find({'isActive': True}, {'passwordHash': 0}))
    for u in users:
        u['_id'] = str(u['_id'])
    return {'ok': True, 'data': {'users': users}}


@router.post('/auth/users')
async def create_admin_user(body: dict, admin=Depends(get_admin)):
    if admin['role'] != 'ADMIN':
        raise HTTPException(status_code=403, detail='Admin role required')
    username = body.get('username', '')
    password = body.get('password', '')
    role = body.get('role', 'MODERATOR')
    if not username or not password:
        raise HTTPException(status_code=400, detail='Username and password required')
    if admin_users.find_one({'username': username}):
        raise HTTPException(status_code=409, detail='Username already exists')
    now = int(datetime.utcnow().timestamp())
    admin_users.insert_one({
        'username': username,
        'passwordHash': pbkdf2_hash(password),
        'role': role,
        'isActive': True,
        'createdAtTs': now,
        'updatedAtTs': now,
    })
    return {'ok': True, 'message': f'Admin user {username} created with role {role}'}


@router.post('/auth/change-password')
async def change_admin_password(body: dict, admin=Depends(get_admin)):
    current = body.get('currentPassword', '')
    new_pwd = body.get('newPassword', '')
    if not current or not new_pwd or len(new_pwd) < 8:
        raise HTTPException(status_code=400, detail='Valid current and new password required (min 8 chars)')
    user = admin_users.find_one({'username': admin['username'], 'isActive': True})
    if not user or not pbkdf2_verify(current, user.get('passwordHash', '')):
        raise HTTPException(status_code=401, detail='Current password is incorrect')
    admin_users.update_one({'_id': user['_id']}, {'$set': {
        'passwordHash': pbkdf2_hash(new_pwd),
        'updatedAtTs': int(datetime.utcnow().timestamp()),
    }})
    return {'ok': True, 'message': 'Password changed successfully'}
