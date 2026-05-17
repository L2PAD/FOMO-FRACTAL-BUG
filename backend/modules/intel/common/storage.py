"""
Storage utilities: upsert with change detection + moderation queue
"""

import hashlib
import json
import logging
from typing import Optional, Dict, Any, Literal
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)


def hash_payload(obj: Dict) -> str:
    """Create hash of payload for change detection"""
    # Remove fields that change on every update
    clean = {k: v for k, v in obj.items() if k not in ['raw', 'updated_at', 'payloadHash']}
    json_str = json.dumps(clean, sort_keys=True, default=str)
    return hashlib.sha1(json_str.encode()).hexdigest()


async def upsert_with_diff(
    collection,
    doc: Dict,
    key_field: str = 'key',
    emit_webhook: bool = True
) -> Dict[str, Any]:
    """
    Upsert document and detect if it changed.
    Returns: {changed: bool, change_type: 'new'|'updated'|None}
    
    Args:
        collection: MongoDB collection
        doc: Document to upsert
        key_field: Field to use as key for lookup
        emit_webhook: Whether to emit webhook for new projects
    """
    now = datetime.now(timezone.utc)
    payload_hash = hash_payload(doc)
    
    key_value = doc.get(key_field)
    if not key_value:
        return {'changed': False, 'change_type': None, 'error': 'No key'}
    
    existing = await collection.find_one({key_field: key_value})
    
    if not existing:
        # New document
        doc['payloadHash'] = payload_hash
        doc['created_at'] = now
        doc['updated_at'] = now
        await collection.insert_one(doc)
        
        # Emit webhook for new projects
        if emit_webhook and collection.name == 'intel_projects':
            try:
                await _emit_project_webhook(doc)
            except Exception as e:
                logger.warning(f"[Storage] Webhook emit error: {e}")
        
        return {'changed': True, 'change_type': 'new'}
    
    if existing.get('payloadHash') != payload_hash:
        # Updated document
        doc['payloadHash'] = payload_hash
        doc['updated_at'] = now
        await collection.update_one(
            {key_field: key_value},
            {'$set': doc}
        )
        return {'changed': True, 'change_type': 'updated'}
    
    # No change
    return {'changed': False, 'change_type': None}


async def _emit_project_webhook(project_data: Dict):
    """Emit webhook for new project discovery."""
    try:
        from modules.webhooks.routes import get_manager
        from modules.webhooks.routes import WebhookEvent, WebhookEventType
        
        manager = get_manager()
        
        payload = {
            "slug": project_data.get("key") or project_data.get("slug"),
            "name": project_data.get("name"),
            "symbol": project_data.get("symbol"),
            "categories": project_data.get("categories", []),
            "description": project_data.get("description", "")[:200] if project_data.get("description") else None,
            "website": project_data.get("website") or project_data.get("links", {}).get("homepage"),
            "market_cap": project_data.get("market_cap"),
            "discovered_from": project_data.get("source", "unknown"),
            "discovered_at": datetime.now(timezone.utc).isoformat()
        }
        
        await manager.trigger_event(WebhookEvent(
            event_type=WebhookEventType.PROJECT_NEW,
            timestamp=datetime.now(timezone.utc).isoformat(),
            data=payload
        ))
        
        logger.info(f"[Storage] Emitted project.new webhook: {payload.get('name')}")
        
    except Exception as e:
        logger.warning(f"[Storage] Failed to emit project webhook: {e}")


async def push_to_moderation(
    db: AsyncIOMotorDatabase,
    source: str,
    entity: str,
    key: str,
    payload: Dict,
    change_type: Literal['new', 'updated'],
    meta: Optional[Dict] = None
):
    """
    Add item to moderation queue for admin review.
    """
    item = {
        'source': source,
        'entity': entity,
        'key': key,
        'payload': payload,
        'change_type': change_type,
        'status': 'pending',  # pending, approved, rejected
        'created_at': datetime.now(timezone.utc),
        'meta': meta or {}
    }
    
    await db.moderation_queue.insert_one(item)
    logger.debug(f"[Moderation] {change_type} {entity}: {key}")
