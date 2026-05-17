"""Profile routes."""
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from datetime import datetime
from routes.auth import get_current_user
import base64

router = APIRouter()


@router.get("/profile")
async def get_profile(user=Depends(get_current_user)):
    from routes.auth import user_to_response
    return user_to_response(user)


@router.patch("/profile")
async def update_profile(body: dict, user=Depends(get_current_user)):
    from routes.auth import users_collection, user_to_response

    update_fields = {}
    if 'name' in body and isinstance(body['name'], str) and body['name'].strip():
        update_fields['name'] = body['name'].strip()

    if update_fields:
        update_fields['updatedAt'] = datetime.utcnow()
        users_collection.update_one({'_id': user['_id']}, {'$set': update_fields})

    updated = users_collection.find_one({'_id': user['_id']})
    return user_to_response(updated)


@router.post("/profile/avatar")
async def upload_avatar(body: dict, user=Depends(get_current_user)):
    """Upload user avatar as base64."""
    from routes.auth import users_collection, user_to_response

    avatar_base64 = body.get('avatar', '')
    if not avatar_base64:
        raise HTTPException(status_code=400, detail='Avatar data is required')

    # Limit: ~2MB base64
    if len(avatar_base64) > 2_800_000:
        raise HTTPException(status_code=400, detail='Avatar too large (max 2MB)')

    users_collection.update_one(
        {'_id': user['_id']},
        {'$set': {
            'avatar': avatar_base64,
            'updatedAt': datetime.utcnow(),
        }}
    )

    updated = users_collection.find_one({'_id': user['_id']})
    return {'success': True, 'user': user_to_response(updated)}


@router.patch("/profile/preferences")
async def update_preferences(body: dict, user=Depends(get_current_user)):
    from routes.auth import users_collection, user_to_response

    update_fields = {}

    if 'defaultAsset' in body:
        from services.asset_registry import normalize_symbol
        update_fields['preferences.defaultAsset'] = normalize_symbol(body['defaultAsset'])

    if 'theme' in body and body['theme'] in ('dark', 'light'):
        update_fields['preferences.theme'] = body['theme']

    if 'language' in body and body['language'] in ('en', 'ru'):
        update_fields['preferences.language'] = body['language']

    if 'notifications' in body:
        if isinstance(body['notifications'], bool):
            update_fields['preferences.notifications'] = body['notifications']

    if 'notificationSettings' in body and isinstance(body['notificationSettings'], dict):
        valid_keys = [
            'decisionChanges', 'confidenceShifts', 'keyEvents',
            'edgeOpportunities', 'edgeHigh', 'highImpactFeed',
            'allFeedEvents', 'billing', 'systemUpdates', 'push', 'email',
        ]
        for key, val in body['notificationSettings'].items():
            if key in valid_keys:
                update_fields[f'preferences.notificationSettings.{key}'] = bool(val)

    if 'startScreen' in body and body['startScreen'] in ('HOME', 'FEED', 'EDGE'):
        update_fields['preferences.startScreen'] = body['startScreen']

    if 'haptics' in body and isinstance(body['haptics'], bool):
        update_fields['preferences.haptics'] = body['haptics']

    # Data sources toggle (e.g. dataSources.exchange, dataSources.onchain, etc.)
    if 'dataSources' in body and isinstance(body['dataSources'], dict):
        valid_sources = ['exchange', 'onchain', 'sentiment', 'fractals', 'technicals', 'prediction']
        for key, val in body['dataSources'].items():
            if key in valid_sources:
                update_fields[f'preferences.dataSources.{key}'] = bool(val)

    # Support dot-notation keys like "dataSources.exchange" directly
    for key in list(body.keys()):
        if key.startswith('dataSources.'):
            src_key = key.split('.', 1)[1]
            valid_sources = ['exchange', 'onchain', 'sentiment', 'fractals', 'technicals', 'prediction']
            if src_key in valid_sources:
                update_fields[f'preferences.{key}'] = bool(body[key])

    if update_fields:
        update_fields['updatedAt'] = datetime.utcnow()
        users_collection.update_one({'_id': user['_id']}, {'$set': update_fields})

    updated = users_collection.find_one({'_id': user['_id']})
    return user_to_response(updated)
