"""
API Documentation Routes

Provides bilingual API documentation from MongoDB.
"""

from fastapi import APIRouter, Query
from typing import Optional
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/docs", tags=["documentation"])


def get_registry():
    """Get documentation registry"""
    from server import db
    from .documentation_registry import init_api_registry, get_api_registry
    registry = get_api_registry()
    if registry is None:
        registry = init_api_registry(db)
    return registry


@router.get("/")
async def get_all_documentation(
    lang: str = Query("en", description="Language: en or ru")
):
    """
    Get all API documentation.
    
    Language options:
    - en: English (default)
    - ru: Russian
    """
    registry = get_registry()
    docs = await registry.get_all(lang)
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "lang": lang,
        "count": len(docs),
        "endpoints": docs
    }


@router.get("/list")
async def list_documentation(
    lang: str = Query("en", description="Language: en or ru"),
    category: Optional[str] = Query(None, description="Filter by category"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200)
):
    """
    List API documentation with pagination.
    """
    registry = get_registry()
    
    if category:
        docs = await registry.get_by_category(category, lang)
    else:
        docs = await registry.get_all(lang)
    
    total = len(docs)
    skip = (page - 1) * limit
    items = docs[skip:skip + limit]
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "lang": lang,
        "page": page,
        "limit": limit,
        "total": total,
        "items": items
    }


@router.get("/category/{category}")
async def get_by_category(
    category: str,
    lang: str = Query("en", description="Language: en or ru")
):
    """
    Get documentation by category.
    
    Categories: entity, query, correlation, trust, exchange, system
    """
    registry = get_registry()
    docs = await registry.get_by_category(category, lang)
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "category": category,
        "lang": lang,
        "count": len(docs),
        "endpoints": docs
    }


@router.get("/endpoint/{endpoint_id}")
async def get_endpoint_docs(
    endpoint_id: str,
    lang: str = Query("en", description="Language: en or ru")
):
    """
    Get documentation for specific endpoint.
    """
    registry = get_registry()
    doc = await registry.get_by_endpoint(endpoint_id, lang)
    
    if not doc:
        return {
            "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
            "error": "Endpoint not found",
            "endpoint_id": endpoint_id
        }
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "lang": lang,
        "endpoint": doc
    }


@router.get("/search")
async def search_documentation(
    q: str = Query(..., min_length=1, description="Search query"),
    lang: str = Query("en", description="Language: en or ru")
):
    """
    Search API documentation.
    
    Searches in titles, descriptions, paths, and tags.
    """
    registry = get_registry()
    docs = await registry.search(q, lang)
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "query": q,
        "lang": lang,
        "count": len(docs),
        "results": docs
    }


@router.post("/seed")
async def seed_documentation():
    """
    Seed database with API documentation.
    
    Populates api_documentation collection with structured docs.
    """
    registry = get_registry()
    result = await registry.seed_documentation()
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "ok": True,
        **result
    }


@router.get("/categories")
async def list_categories():
    """
    Get list of documentation categories.
    """
    categories = [
        # Market Data Layer (First Layer)
        {"id": "market", "name_en": "Market Data", "name_ru": "Рыночные данные", "icon": "chart-line", "order": 1},
        {"id": "derivatives", "name_en": "Derivatives", "name_ru": "Деривативы", "icon": "trending-up", "order": 2},
        {"id": "indices", "name_en": "Market Indices", "name_ru": "Рыночные индексы", "icon": "bar-chart", "order": 3},
        {"id": "exchange", "name_en": "Exchange API", "name_ru": "API бирж", "icon": "building", "order": 4},
        {"id": "spot", "name_en": "Spot Markets", "name_ru": "Спот рынки", "icon": "dollar-sign", "order": 5},
        
        # Intel Layer (Second Layer)
        {"id": "entity", "name_en": "Entity Intelligence", "name_ru": "Интеллект сущностей", "icon": "brain", "order": 10},
        {"id": "query", "name_en": "Query Engine", "name_ru": "Движок запросов", "icon": "search", "order": 11},
        {"id": "correlation", "name_en": "Event Correlation", "name_ru": "Корреляция событий", "icon": "link", "order": 12},
        {"id": "trust", "name_en": "Source Trust", "name_ru": "Доверие источников", "icon": "shield", "order": 13},
        
        # Intelligence Index (NEW)
        {"id": "intelligence", "name_en": "Intelligence Index", "name_ru": "Индекс интеллекта", "icon": "target", "order": 14},
        {"id": "narratives", "name_en": "Narrative Dominance", "name_ru": "Доминирование нарративов", "icon": "trending-up", "order": 15},
        {"id": "activity", "name_en": "Entity Activity", "name_ru": "Активность сущностей", "icon": "activity", "order": 16},
        
        # Cache & Redis (NEW)
        {"id": "cache", "name_en": "Cache & Redis", "name_ru": "Кэш и Redis", "icon": "database", "order": 17},
        {"id": "queues", "name_en": "Task Queues", "name_ru": "Очереди задач", "icon": "layers", "order": 18},
        
        # Data Categories
        {"id": "global", "name_en": "Global Stats", "name_ru": "Глобальная статистика", "icon": "globe", "order": 20},
        {"id": "projects", "name_en": "Projects", "name_ru": "Проекты", "icon": "folder", "order": 21},
        {"id": "funds", "name_en": "Funds / VCs", "name_ru": "Фонды / VC", "icon": "briefcase", "order": 22},
        {"id": "persons", "name_en": "Persons", "name_ru": "Персоны", "icon": "users", "order": 23},
        {"id": "fundraising", "name_en": "Fundraising", "name_ru": "Финансирование", "icon": "dollar-sign", "order": 24},
        {"id": "unlocks", "name_en": "Token Unlocks", "name_ru": "Анлоки токенов", "icon": "unlock", "order": 25},
        {"id": "ico", "name_en": "ICO / Token Sales", "name_ru": "ICO / Продажи токенов", "icon": "tag", "order": 26},
        {"id": "exchanges", "name_en": "Exchanges", "name_ru": "Биржи", "icon": "activity", "order": 27},
        {"id": "search", "name_en": "Search", "name_ru": "Поиск", "icon": "search", "order": 28},
        
        # New Categories
        {"id": "activities", "name_en": "Crypto Activities", "name_ru": "Криптоактивности", "icon": "zap", "order": 30},
        {"id": "feed", "name_en": "Intel Feed", "name_ru": "Лента событий", "icon": "rss", "order": 31},
        
        # Graph & Knowledge
        {"id": "graph", "name_en": "Knowledge Graph", "name_ru": "Граф знаний", "icon": "share-2", "order": 40},
        {"id": "webhooks", "name_en": "Webhooks", "name_ru": "Вебхуки", "icon": "webhook", "order": 41},
        
        # System
        {"id": "system", "name_en": "System", "name_ru": "Система", "icon": "settings", "order": 99}
    ]
    
    return {
        "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
        "categories": sorted(categories, key=lambda x: x.get("order", 50))
    }
