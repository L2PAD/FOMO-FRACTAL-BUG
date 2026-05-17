"""
Crypto Intelligence Operating System — ID Generation
"""
import hashlib
from datetime import datetime, timezone


def make_entity_id(entity_type: str, name: str) -> str:
    normalized = name.strip().lower().replace(" ", "-")
    return f"{entity_type}:{normalized}"


def make_event_id(event_type: str, source: str, key: str) -> str:
    raw = f"{event_type}:{source}:{key}"
    h = hashlib.md5(raw.encode()).hexdigest()[:12]
    return f"evt:{event_type}:{h}"


def make_edge_id(from_id: str, to_id: str, edge_type: str) -> str:
    raw = f"{from_id}→{to_id}:{edge_type}"
    h = hashlib.md5(raw.encode()).hexdigest()[:12]
    return f"edge:{h}"


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()
