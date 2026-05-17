"""
API Documentation Registry

Stores structured API documentation in MongoDB with bilingual support (EN/RU).
Provides complete endpoint descriptions, parameters, examples.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class HttpMethod(Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"


@dataclass
class ApiParameter:
    """API Parameter definition"""
    name: str
    type: str  # string, integer, number, boolean, array, object
    required: bool = False
    location: str = "query"  # query, path, body, header
    description_en: str = ""
    description_ru: str = ""
    default: Any = None
    example: Any = None
    enum: List[str] = None


@dataclass
class ApiResponse:
    """API Response definition"""
    status_code: int
    description_en: str
    description_ru: str
    example: Dict[str, Any] = None
    schema: Dict[str, Any] = None


@dataclass
class ApiEndpoint:
    """Complete API Endpoint documentation"""
    endpoint_id: str
    path: str
    method: HttpMethod
    
    # Bilingual descriptions
    title_en: str
    title_ru: str
    description_en: str
    description_ru: str
    
    # Category/tags
    category: str
    tags: List[str] = field(default_factory=list)
    
    # Parameters
    parameters: List[ApiParameter] = field(default_factory=list)
    
    # Request body (for POST/PUT)
    request_body: Dict[str, Any] = None
    request_example: Dict[str, Any] = None
    
    # Responses
    responses: List[ApiResponse] = field(default_factory=list)
    
    # Curl example
    curl_example: str = None
    
    # Metadata
    version: str = "2.0.0"
    deprecated: bool = False
    auth_required: bool = False
    rate_limit: str = None
    
    created_at: str = None
    updated_at: str = None


# ═══════════════════════════════════════════════════════════════
# API DOCUMENTATION REGISTRY
# ═══════════════════════════════════════════════════════════════

# Import new endpoints documentation
try:
    from .documentation_new_endpoints import NEW_ENDPOINTS_DOCUMENTATION
except ImportError:
    NEW_ENDPOINTS_DOCUMENTATION = []

API_DOCUMENTATION: List[ApiEndpoint] = [
    
    # ───────────────────────────────────────────────────────────
    # ENTITY INTELLIGENCE API
    # ───────────────────────────────────────────────────────────
    
    ApiEndpoint(
        endpoint_id="entity_get",
        path="/api/intel/entity/{query}",
        method=HttpMethod.GET,
        title_en="Get Entity by Identifier",
        title_ru="Получить сущность по идентификатору",
        description_en="Resolve any identifier (symbol, name, address, slug, external key) to entity profile. Returns full entity data with event counts. This is the main endpoint for entity lookup.",
        description_ru="Разрешает любой идентификатор (символ, название, адрес, slug, внешний ключ) в профиль сущности. Возвращает полные данные сущности с количеством событий. Это основной endpoint для поиска сущностей.",
        category="entity",
        tags=["entity", "resolution", "profile"],
        parameters=[
            ApiParameter(
                name="query",
                type="string",
                required=True,
                location="path",
                description_en="Entity identifier: symbol (BTC), name (Bitcoin), address (0x...), slug (bitcoin), or external key (coingecko:bitcoin)",
                description_ru="Идентификатор сущности: символ (BTC), название (Bitcoin), адрес (0x...), slug (bitcoin) или внешний ключ (coingecko:bitcoin)",
                example="arbitrum"
            )
        ],
        responses=[
            ApiResponse(
                status_code=200,
                description_en="Entity profile with event counts",
                description_ru="Профиль сущности с количеством событий",
                example={
                    "ts": 1772717367700,
                    "entity": {
                        "entity_id": "ent_arbitrum_abc123",
                        "type": "token",
                        "canonical": {"name": "Arbitrum", "symbol": "ARB"},
                        "keys": {"coingecko": "arbitrum", "cryptorank": "arb"},
                        "confidence": 0.92
                    },
                    "event_counts": {"funding_round": 3, "unlock_event": 12},
                    "total_events": 15
                }
            ),
            ApiResponse(
                status_code=404,
                description_en="Entity not found",
                description_ru="Сущность не найдена"
            )
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="entity_timeline",
        path="/api/intel/entity/{query}/timeline",
        method=HttpMethod.GET,
        title_en="Get Entity Timeline",
        title_ru="Получить хронологию событий сущности",
        description_en="Get chronological event timeline for entity. Shows all events in order: funding rounds, unlocks, listings, sales. Essential for understanding project lifecycle.",
        description_ru="Получить хронологическую ленту событий для сущности. Показывает все события по порядку: раунды финансирования, анлоки, листинги, продажи. Важно для понимания жизненного цикла проекта.",
        category="entity",
        tags=["entity", "timeline", "events", "lifecycle"],
        parameters=[
            ApiParameter(
                name="query",
                type="string",
                required=True,
                location="path",
                description_en="Entity identifier",
                description_ru="Идентификатор сущности",
                example="eigenlayer"
            ),
            ApiParameter(
                name="types",
                type="string",
                required=False,
                location="query",
                description_en="Comma-separated event types filter",
                description_ru="Фильтр типов событий через запятую",
                example="funding_round,unlock_event"
            ),
            ApiParameter(
                name="limit",
                type="integer",
                required=False,
                location="query",
                description_en="Maximum number of events",
                description_ru="Максимальное количество событий",
                default=100,
                example=50
            )
        ],
        responses=[
            ApiResponse(
                status_code=200,
                description_en="Entity timeline with events",
                description_ru="Хронология сущности с событиями",
                example={
                    "entity": {"entity_id": "ent_eigen_123", "canonical": {"name": "EigenLayer"}},
                    "timeline": [
                        {"type": "funding_round", "ts": "2024-03-01", "data": {"raised_usd": 50000000}},
                        {"type": "unlock_event", "ts": "2024-06-01", "data": {"amount_usd": 120000000}}
                    ],
                    "count": 2
                }
            )
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="entity_stats",
        path="/api/intel/entity/stats",
        method=HttpMethod.GET,
        title_en="Get Entity Intelligence Statistics",
        title_ru="Получить статистику Entity Intelligence",
        description_en="Get statistics about the Entity Intelligence Engine: total entities, index entries, events count, resolver cache size.",
        description_ru="Получить статистику движка Entity Intelligence: всего сущностей, записей в индексе, количество событий, размер кэша резолвера.",
        category="entity",
        tags=["entity", "stats", "monitoring"],
        parameters=[],
        responses=[
            ApiResponse(
                status_code=200,
                description_en="Entity intelligence statistics",
                description_ru="Статистика Entity Intelligence",
                example={
                    "ts": 1772717367700,
                    "entities": 7362,
                    "index_entries": 24890,
                    "events": 10210,
                    "resolver_cache_size": 156
                }
            )
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="entity_resolve",
        path="/api/intel/entity/resolve",
        method=HttpMethod.POST,
        title_en="Resolve Identifier to Entity ID",
        title_ru="Разрешить идентификатор в Entity ID",
        description_en="Resolve any identifier to canonical entity_id. Returns whether the identifier was successfully resolved.",
        description_ru="Разрешить любой идентификатор в канонический entity_id. Возвращает успешность разрешения идентификатора.",
        category="entity",
        tags=["entity", "resolution"],
        parameters=[
            ApiParameter(
                name="query",
                type="string",
                required=True,
                location="query",
                description_en="Identifier to resolve",
                description_ru="Идентификатор для разрешения",
                example="bitcoin"
            )
        ],
        responses=[
            ApiResponse(
                status_code=200,
                description_en="Resolution result",
                description_ru="Результат разрешения",
                example={
                    "ts": 1772717367700,
                    "query": "bitcoin",
                    "entity_id": "ent_bitcoin_abc123",
                    "resolved": True
                }
            )
        ]
    ),
    
    # ───────────────────────────────────────────────────────────
    # QUERY ENGINE API
    # ───────────────────────────────────────────────────────────
    
    ApiEndpoint(
        endpoint_id="query_events",
        path="/api/intel/engine/query/events",
        method=HttpMethod.POST,
        title_en="Query Events with Filters",
        title_ru="Запрос событий с фильтрами",
        description_en="Query events with flexible filters: entity, event_type, investor, amount range, date range, source, confidence. Supports pagination and sorting.",
        description_ru="Запрос событий с гибкими фильтрами: сущность, тип события, инвестор, диапазон сумм, диапазон дат, источник, уверенность. Поддерживает пагинацию и сортировку.",
        category="query",
        tags=["query", "events", "filters", "search"],
        parameters=[
            ApiParameter(
                name="entity",
                type="string",
                required=False,
                location="query",
                description_en="Filter by entity ID",
                description_ru="Фильтр по ID сущности"
            ),
            ApiParameter(
                name="event_type",
                type="string",
                required=False,
                location="query",
                description_en="Filter by event type: funding_round, unlock_event, token_sale, listing",
                description_ru="Фильтр по типу события: funding_round, unlock_event, token_sale, listing",
                enum=["funding_round", "unlock_event", "token_sale", "listing", "investor_activity"]
            ),
            ApiParameter(
                name="investor",
                type="string",
                required=False,
                location="query",
                description_en="Filter by investor name",
                description_ru="Фильтр по имени инвестора",
                example="a16z"
            ),
            ApiParameter(
                name="min_amount",
                type="number",
                required=False,
                location="query",
                description_en="Minimum amount in USD",
                description_ru="Минимальная сумма в USD",
                example=50000000
            ),
            ApiParameter(
                name="days_back",
                type="integer",
                required=False,
                location="query",
                description_en="Filter events from last N days",
                description_ru="Фильтр событий за последние N дней",
                example=30
            ),
            ApiParameter(
                name="limit",
                type="integer",
                required=False,
                location="query",
                description_en="Maximum results",
                description_ru="Максимум результатов",
                default=50
            )
        ],
        responses=[
            ApiResponse(
                status_code=200,
                description_en="Query results with events",
                description_ru="Результаты запроса с событиями",
                example={
                    "ts": 1772717367700,
                    "query": {"event_type": "funding_round", "investor": "a16z"},
                    "total": 156,
                    "count": 50,
                    "results": [{"entity_id": "ent_123", "type": "funding_round", "data": {}}]
                }
            )
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="query_investor_portfolio",
        path="/api/intel/engine/query/investor/{investor}/portfolio",
        method=HttpMethod.GET,
        title_en="Get Investor Portfolio",
        title_ru="Получить портфель инвестора",
        description_en="Get all projects an investor has funded. Shows total invested amount, number of rounds, and detailed investment history.",
        description_ru="Получить все проекты, которые финансировал инвестор. Показывает общую сумму инвестиций, количество раундов и детальную историю инвестиций.",
        category="query",
        tags=["query", "investor", "portfolio", "analysis"],
        parameters=[
            ApiParameter(
                name="investor",
                type="string",
                required=True,
                location="path",
                description_en="Investor name",
                description_ru="Имя инвестора",
                example="a16z"
            )
        ],
        responses=[
            ApiResponse(
                status_code=200,
                description_en="Investor portfolio",
                description_ru="Портфель инвестора",
                example={
                    "ts": 1772717367700,
                    "investor": "a16z",
                    "portfolio_size": 45,
                    "total_invested": 2500000000,
                    "portfolio": [
                        {"entity_id": "ent_uniswap", "total_invested": 150000000, "round_count": 2}
                    ]
                }
            )
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="query_unlocks_upcoming",
        path="/api/intel/engine/query/unlocks/upcoming",
        method=HttpMethod.GET,
        title_en="Get Upcoming Token Unlocks",
        title_ru="Получить предстоящие разблокировки токенов",
        description_en="Get upcoming token unlocks within specified time window. Shows unlock count and total USD exposure.",
        description_ru="Получить предстоящие разблокировки токенов в указанном временном окне. Показывает количество анлоков и общую экспозицию в USD.",
        category="query",
        tags=["query", "unlocks", "upcoming", "risk"],
        parameters=[
            ApiParameter(
                name="days",
                type="integer",
                required=False,
                location="query",
                description_en="Days ahead to look",
                description_ru="Дней вперёд для просмотра",
                default=30,
                example=7
            ),
            ApiParameter(
                name="min_usd",
                type="number",
                required=False,
                location="query",
                description_en="Minimum unlock value in USD",
                description_ru="Минимальная стоимость анлока в USD",
                default=0,
                example=10000000
            )
        ],
        responses=[
            ApiResponse(
                status_code=200,
                description_en="Upcoming unlocks",
                description_ru="Предстоящие разблокировки",
                example={
                    "ts": 1772717367700,
                    "days_ahead": 30,
                    "unlock_count": 45,
                    "total_usd_exposure": 890000000,
                    "unlocks": []
                }
            )
        ]
    ),
    
    # ───────────────────────────────────────────────────────────
    # CORRELATION ENGINE API
    # ───────────────────────────────────────────────────────────
    
    ApiEndpoint(
        endpoint_id="correlation_run",
        path="/api/intel/engine/correlation/run",
        method=HttpMethod.POST,
        title_en="Run Event Correlation",
        title_ru="Запустить корреляцию событий",
        description_en="Run correlation engine to build relationships between events. Discovers chains: Funding → Token Sale → Listing → Unlock.",
        description_ru="Запустить движок корреляции для построения связей между событиями. Обнаруживает цепочки: Funding → Token Sale → Listing → Unlock.",
        category="correlation",
        tags=["correlation", "relations", "pipeline", "analysis"],
        parameters=[
            ApiParameter(
                name="limit",
                type="integer",
                required=False,
                location="query",
                description_en="Maximum entities to process",
                description_ru="Максимум сущностей для обработки",
                default=500
            )
        ],
        responses=[
            ApiResponse(
                status_code=200,
                description_en="Correlation results",
                description_ru="Результаты корреляции",
                example={
                    "ts": 1772717367700,
                    "ok": True,
                    "entities_processed": 500,
                    "relations_created": 1250,
                    "elapsed_sec": 12.5
                }
            )
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="correlation_timeline",
        path="/api/intel/engine/correlation/entity/{entity_id}/timeline",
        method=HttpMethod.GET,
        title_en="Get Entity Correlation Timeline",
        title_ru="Получить таймлайн корреляций сущности",
        description_en="Get full event timeline with correlations for entity. Shows lifecycle: Funding → Sale → Listing → Unlock with relation types.",
        description_ru="Получить полную хронологию событий с корреляциями для сущности. Показывает жизненный цикл: Funding → Sale → Listing → Unlock с типами связей.",
        category="correlation",
        tags=["correlation", "timeline", "lifecycle"],
        parameters=[
            ApiParameter(
                name="entity_id",
                type="string",
                required=True,
                location="path",
                description_en="Entity ID",
                description_ru="ID сущности"
            )
        ],
        responses=[
            ApiResponse(
                status_code=200,
                description_en="Timeline with correlations",
                description_ru="Хронология с корреляциями",
                example={
                    "entity_id": "ent_layerzero",
                    "event_count": 5,
                    "relation_count": 4,
                    "lifecycle": [
                        {"stage": "funding", "date": "2024-01-15"},
                        {"stage": "token_sale", "date": "2024-06-01"},
                        {"stage": "listing", "date": "2024-06-15"}
                    ]
                }
            )
        ]
    ),
    
    # ───────────────────────────────────────────────────────────
    # SOURCE TRUST ENGINE API
    # ───────────────────────────────────────────────────────────
    
    ApiEndpoint(
        endpoint_id="trust_scores",
        path="/api/intel/engine/trust/scores",
        method=HttpMethod.GET,
        title_en="Get Source Trust Scores",
        title_ru="Получить рейтинги доверия источников",
        description_en="Get trust scores for all data sources. Higher score = more reliable source. Affects event confidence and dedup decisions.",
        description_ru="Получить рейтинги доверия для всех источников данных. Высокий рейтинг = более надёжный источник. Влияет на уверенность событий и решения по дедупликации.",
        category="trust",
        tags=["trust", "sources", "quality"],
        parameters=[],
        responses=[
            ApiResponse(
                status_code=200,
                description_en="Trust scores for all sources",
                description_ru="Рейтинги доверия для всех источников",
                example={
                    "ts": 1772717367700,
                    "count": 8,
                    "sources": [
                        {"source_id": "cryptorank", "trust_score": 0.93},
                        {"source_id": "coingecko", "trust_score": 0.91},
                        {"source_id": "dropstab", "trust_score": 0.89}
                    ]
                }
            )
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="trust_source_detail",
        path="/api/intel/engine/trust/source/{source_id}",
        method=HttpMethod.GET,
        title_en="Get Source Trust Details",
        title_ru="Получить детали доверия источника",
        description_en="Get detailed trust information for specific source including metrics: success_rate, schema_stability, freshness, cross_source_agreement.",
        description_ru="Получить детальную информацию о доверии для конкретного источника включая метрики: success_rate, schema_stability, freshness, cross_source_agreement.",
        category="trust",
        tags=["trust", "source", "metrics"],
        parameters=[
            ApiParameter(
                name="source_id",
                type="string",
                required=True,
                location="path",
                description_en="Source identifier",
                description_ru="Идентификатор источника",
                example="cryptorank"
            )
        ],
        responses=[
            ApiResponse(
                status_code=200,
                description_en="Source trust details",
                description_ru="Детали доверия источника",
                example={
                    "source_id": "cryptorank",
                    "trust_score": 0.93,
                    "default_trust": 0.93,
                    "metrics": {
                        "success_rate": 0.97,
                        "schema_stability": 0.95,
                        "freshness": 0.91,
                        "cross_source_agreement": 0.89
                    }
                }
            )
        ]
    ),
    
    # ───────────────────────────────────────────────────────────
    # EXCHANGE API
    # ───────────────────────────────────────────────────────────
    
    ApiEndpoint(
        endpoint_id="exchange_providers",
        path="/api/exchange/providers",
        method=HttpMethod.GET,
        title_en="List Exchange Providers",
        title_ru="Список биржевых провайдеров",
        description_en="Get list of all configured exchange providers with their capabilities (spot, futures, margin, options, websocket).",
        description_ru="Получить список всех настроенных биржевых провайдеров с их возможностями (spot, futures, margin, options, websocket).",
        category="exchange",
        tags=["exchange", "providers", "market_data"],
        parameters=[],
        responses=[
            ApiResponse(
                status_code=200,
                description_en="List of providers",
                description_ru="Список провайдеров",
                example={
                    "ts": 1772717367700,
                    "providers": [
                        {
                            "venue": "hyperliquid",
                            "display_name": "Hyperliquid",
                            "capabilities": {"has_spot": False, "has_futures": True}
                        }
                    ]
                }
            )
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="exchange_ticker",
        path="/api/exchange/ticker",
        method=HttpMethod.GET,
        title_en="Get Exchange Ticker",
        title_ru="Получить тикер биржи",
        description_en="Get real-time ticker data from exchange. Returns last price, 24h change, volume.",
        description_ru="Получить данные тикера в реальном времени с биржи. Возвращает последнюю цену, изменение за 24ч, объём.",
        category="exchange",
        tags=["exchange", "ticker", "price", "realtime"],
        parameters=[
            ApiParameter(
                name="venue",
                type="string",
                required=True,
                location="query",
                description_en="Exchange venue: hyperliquid, coinbase, binance, bybit",
                description_ru="Биржа: hyperliquid, coinbase, binance, bybit",
                example="hyperliquid"
            ),
            ApiParameter(
                name="symbol",
                type="string",
                required=True,
                location="query",
                description_en="Trading symbol",
                description_ru="Торговый символ",
                example="BTC"
            )
        ],
        responses=[
            ApiResponse(
                status_code=200,
                description_en="Ticker data",
                description_ru="Данные тикера",
                example={
                    "ts": 1772717367700,
                    "instrument_id": "hyperliquid:perp:BTC-PERP",
                    "last": 96500.5,
                    "change_24h": 2.35,
                    "volume_24h": 4057639146.47
                }
            )
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="exchange_funding",
        path="/api/exchange/funding",
        method=HttpMethod.GET,
        title_en="Get Funding Rate",
        title_ru="Получить ставку финансирования",
        description_en="Get current funding rate for perpetual futures. Important for derivatives trading strategy.",
        description_ru="Получить текущую ставку финансирования для бессрочных фьючерсов. Важно для стратегии торговли деривативами.",
        category="exchange",
        tags=["exchange", "funding", "derivatives", "perp"],
        parameters=[
            ApiParameter(
                name="venue",
                type="string",
                required=True,
                location="query",
                description_en="Exchange venue",
                description_ru="Биржа",
                example="hyperliquid"
            ),
            ApiParameter(
                name="symbol",
                type="string",
                required=True,
                location="query",
                description_en="Symbol",
                description_ru="Символ",
                example="BTC"
            )
        ],
        responses=[
            ApiResponse(
                status_code=200,
                description_en="Funding rate data",
                description_ru="Данные ставки финансирования",
                example={
                    "ts": 1772717367700,
                    "instrument_id": "hyperliquid:perp:BTC-PERP",
                    "funding_rate": 0.0000125,
                    "funding_time": 1772720000000
                }
            )
        ]
    ),
    
    # ───────────────────────────────────────────────────────────
    # SYSTEM API
    # ───────────────────────────────────────────────────────────
    
    ApiEndpoint(
        endpoint_id="health",
        path="/api/health",
        method=HttpMethod.GET,
        title_en="Health Check",
        title_ru="Проверка работоспособности",
        description_en="Check API health status. Returns service status and available features.",
        description_ru="Проверить состояние API. Возвращает статус сервиса и доступные функции.",
        category="system",
        tags=["system", "health", "monitoring"],
        parameters=[],
        responses=[
            ApiResponse(
                status_code=200,
                description_en="Health status",
                description_ru="Статус работоспособности",
                example={
                    "ok": True,
                    "service": "FOMO Intel API",
                    "features": {
                        "market_data": ["hyperliquid", "coinbase", "binance", "bybit"],
                        "asset_intel": "available"
                    }
                }
            )
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="engine_status",
        path="/api/intel/engine/status",
        method=HttpMethod.GET,
        title_en="Get All Engines Status",
        title_ru="Получить статус всех движков",
        description_en="Get status of all intelligence engines: Correlation, Trust, Query. Shows initialization state and session stats.",
        description_ru="Получить статус всех движков интеллекта: Correlation, Trust, Query. Показывает состояние инициализации и статистику сессии.",
        category="system",
        tags=["system", "engines", "status"],
        parameters=[],
        responses=[
            ApiResponse(
                status_code=200,
                description_en="Engines status",
                description_ru="Статус движков",
                example={
                    "ts": 1772717367700,
                    "engines": {
                        "correlation": {"initialized": True, "entities_processed": 500},
                        "trust": {"initialized": True, "cached_scores": 8},
                        "query": {"initialized": True}
                    }
                }
            )
        ]
    ),
    
    # ───────────────────────────────────────────────────────────
    # GLOBAL API (Public v1)
    # ───────────────────────────────────────────────────────────
    
    ApiEndpoint(
        endpoint_id="global_stats",
        path="/api/v1/global/stats",
        method=HttpMethod.GET,
        title_en="Global Market Statistics",
        title_ru="Глобальная статистика рынка",
        description_en="Get global market statistics: total projects, funds, upcoming unlocks, recent funding rounds.",
        description_ru="Получить глобальную статистику рынка: всего проектов, фондов, предстоящих анлоков, недавних раундов.",
        category="global",
        tags=["global", "stats", "market"],
        parameters=[],
        responses=[
            ApiResponse(
                status_code=200,
                description_en="Global statistics",
                description_ru="Глобальная статистика",
                example={
                    "ts": 1772717367700,
                    "data": {
                        "total_projects": 7362,
                        "total_funds": 130,
                        "upcoming_unlocks": 15,
                        "recent_funding_rounds": 23
                    }
                }
            )
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="global_trending",
        path="/api/v1/global/trending",
        method=HttpMethod.GET,
        title_en="Trending Projects",
        title_ru="Трендовые проекты",
        description_en="Get trending projects based on recent funding, upcoming unlocks, and trading volume.",
        description_ru="Получить трендовые проекты на основе недавнего финансирования, предстоящих анлоков и объёма торгов.",
        category="global",
        tags=["global", "trending", "hot"],
        parameters=[
            ApiParameter(name="limit", type="integer", required=False, location="query",
                        description_en="Maximum results", description_ru="Максимум результатов", default=20)
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Trending projects", description_ru="Трендовые проекты")
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="global_feed",
        path="/api/v1/global/feed",
        method=HttpMethod.GET,
        title_en="Global Activity Feed",
        title_ru="Глобальная лента активности",
        description_en="Combined activity feed: funding rounds, token unlocks, listings, ICO events.",
        description_ru="Комбинированная лента активности: раунды финансирования, анлоки токенов, листинги, ICO.",
        category="global",
        tags=["global", "feed", "activity"],
        parameters=[
            ApiParameter(name="limit", type="integer", required=False, location="query",
                        description_en="Maximum results", description_ru="Максимум результатов", default=50),
            ApiParameter(name="event_type", type="string", required=False, location="query",
                        description_en="Filter: funding, unlock, listing, ico", description_ru="Фильтр: funding, unlock, listing, ico")
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Activity feed", description_ru="Лента активности")
        ]
    ),
    
    # ───────────────────────────────────────────────────────────
    # PROJECTS API (Public v1)
    # ───────────────────────────────────────────────────────────
    
    ApiEndpoint(
        endpoint_id="projects_list_v1",
        path="/api/v1/projects",
        method=HttpMethod.GET,
        title_en="List All Projects",
        title_ru="Список всех проектов",
        description_en="Get list of all projects (tokens + ecosystems). Supports filtering by category and chain.",
        description_ru="Получить список всех проектов (токены + экосистемы). Поддерживает фильтрацию по категории и сети.",
        category="projects",
        tags=["projects", "tokens", "list"],
        parameters=[
            ApiParameter(name="category", type="string", required=False, location="query",
                        description_en="Filter by category", description_ru="Фильтр по категории"),
            ApiParameter(name="chain", type="string", required=False, location="query",
                        description_en="Filter by blockchain", description_ru="Фильтр по блокчейну"),
            ApiParameter(name="limit", type="integer", required=False, location="query",
                        description_en="Maximum results", description_ru="Максимум результатов", default=100),
            ApiParameter(name="offset", type="integer", required=False, location="query",
                        description_en="Offset for pagination", description_ru="Смещение для пагинации", default=0)
        ],
        responses=[
            ApiResponse(status_code=200, description_en="List of projects", description_ru="Список проектов",
                       example={"ts": 1772717367700, "total": 7362, "data": []})
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="project_get",
        path="/api/v1/projects/{project}",
        method=HttpMethod.GET,
        title_en="Get Project Details",
        title_ru="Получить детали проекта",
        description_en="Get full project information by slug, symbol, or key.",
        description_ru="Получить полную информацию о проекте по slug, символу или ключу.",
        category="projects",
        tags=["projects", "details"],
        parameters=[
            ApiParameter(name="project", type="string", required=True, location="path",
                        description_en="Project identifier (slug, symbol, key)", description_ru="Идентификатор проекта",
                        example="ethereum")
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Project details", description_ru="Детали проекта"),
            ApiResponse(status_code=404, description_en="Project not found", description_ru="Проект не найден")
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="project_exchanges",
        path="/api/v1/projects/{project}/exchanges",
        method=HttpMethod.GET,
        title_en="Get Project Exchanges",
        title_ru="Получить биржи проекта",
        description_en="Get list of exchanges where project is traded (spot/perp).",
        description_ru="Получить список бирж, где торгуется проект (spot/perp).",
        category="projects",
        tags=["projects", "exchanges", "trading"],
        parameters=[
            ApiParameter(name="project", type="string", required=True, location="path",
                        description_en="Project identifier", description_ru="Идентификатор проекта")
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Exchange listings", description_ru="Листинги на биржах",
                       example={"project": "ethereum", "data": [{"exchange": "Binance", "pair": "ETH/USDT"}]})
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="project_fundraising",
        path="/api/v1/projects/{project}/fundraising",
        method=HttpMethod.GET,
        title_en="Get Project Fundraising",
        title_ru="Получить раунды финансирования проекта",
        description_en="Get all funding rounds for the project.",
        description_ru="Получить все раунды финансирования проекта.",
        category="projects",
        tags=["projects", "fundraising", "funding"],
        parameters=[
            ApiParameter(name="project", type="string", required=True, location="path",
                        description_en="Project identifier", description_ru="Идентификатор проекта")
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Funding rounds", description_ru="Раунды финансирования")
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="project_unlocks",
        path="/api/v1/projects/{project}/unlocks",
        method=HttpMethod.GET,
        title_en="Get Project Unlocks",
        title_ru="Получить анлоки проекта",
        description_en="Get token unlock schedule for the project.",
        description_ru="Получить расписание разблокировки токенов проекта.",
        category="projects",
        tags=["projects", "unlocks", "vesting"],
        parameters=[
            ApiParameter(name="project", type="string", required=True, location="path",
                        description_en="Project identifier", description_ru="Идентификатор проекта")
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Unlock schedule", description_ru="Расписание анлоков")
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="project_investors_v1",
        path="/api/v1/projects/{project}/investors",
        method=HttpMethod.GET,
        title_en="Get Project Investors",
        title_ru="Получить инвесторов проекта",
        description_en="Get investors who funded this project.",
        description_ru="Получить инвесторов, финансировавших проект.",
        category="projects",
        tags=["projects", "investors", "vc"],
        parameters=[
            ApiParameter(name="project", type="string", required=True, location="path",
                        description_en="Project identifier", description_ru="Идентификатор проекта")
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Investors list", description_ru="Список инвесторов")
        ]
    ),
    
    # ───────────────────────────────────────────────────────────
    # FUNDS API (Public v1)
    # ───────────────────────────────────────────────────────────
    
    ApiEndpoint(
        endpoint_id="funds_list",
        path="/api/v1/funds",
        method=HttpMethod.GET,
        title_en="List All Funds",
        title_ru="Список всех фондов",
        description_en="Get list of all VC funds and investors.",
        description_ru="Получить список всех венчурных фондов и инвесторов.",
        category="funds",
        tags=["funds", "vc", "investors"],
        parameters=[
            ApiParameter(name="tier", type="string", required=False, location="query",
                        description_en="Filter by tier: 1, 2, 3", description_ru="Фильтр по уровню: 1, 2, 3"),
            ApiParameter(name="limit", type="integer", required=False, location="query",
                        description_en="Maximum results", description_ru="Максимум результатов", default=100)
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Funds list", description_ru="Список фондов")
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="fund_get",
        path="/api/v1/funds/{fund}",
        method=HttpMethod.GET,
        title_en="Get Fund Details",
        title_ru="Получить детали фонда",
        description_en="Get detailed information about a fund.",
        description_ru="Получить подробную информацию о фонде.",
        category="funds",
        tags=["funds", "details"],
        parameters=[
            ApiParameter(name="fund", type="string", required=True, location="path",
                        description_en="Fund identifier (slug or name)", description_ru="Идентификатор фонда",
                        example="a16z")
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Fund details", description_ru="Детали фонда"),
            ApiResponse(status_code=404, description_en="Fund not found", description_ru="Фонд не найден")
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="fund_portfolio_v1",
        path="/api/v1/funds/{fund}/portfolio",
        method=HttpMethod.GET,
        title_en="Get Fund Portfolio",
        title_ru="Получить портфель фонда",
        description_en="Get all projects in fund's portfolio.",
        description_ru="Получить все проекты в портфеле фонда.",
        category="funds",
        tags=["funds", "portfolio"],
        parameters=[
            ApiParameter(name="fund", type="string", required=True, location="path",
                        description_en="Fund identifier", description_ru="Идентификатор фонда")
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Portfolio projects", description_ru="Проекты в портфеле")
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="fund_investments",
        path="/api/v1/funds/{fund}/investments",
        method=HttpMethod.GET,
        title_en="Get Fund Investments",
        title_ru="Получить инвестиции фонда",
        description_en="Get investment history for the fund.",
        description_ru="Получить историю инвестиций фонда.",
        category="funds",
        tags=["funds", "investments", "history"],
        parameters=[
            ApiParameter(name="fund", type="string", required=True, location="path",
                        description_en="Fund identifier", description_ru="Идентификатор фонда")
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Investment history", description_ru="История инвестиций")
        ]
    ),
    
    # ───────────────────────────────────────────────────────────
    # PERSONS API (Public v1)
    # ───────────────────────────────────────────────────────────
    
    ApiEndpoint(
        endpoint_id="persons_list_v1",
        path="/api/v1/persons",
        method=HttpMethod.GET,
        title_en="List Notable Persons",
        title_ru="Список известных персон",
        description_en="Get list of notable persons in crypto: founders, investors, advisors.",
        description_ru="Получить список известных персон в крипто: основатели, инвесторы, советники.",
        category="persons",
        tags=["persons", "people", "team"],
        parameters=[
            ApiParameter(name="role", type="string", required=False, location="query",
                        description_en="Filter by role: founder, investor, advisor", description_ru="Фильтр по роли"),
            ApiParameter(name="limit", type="integer", required=False, location="query",
                        description_en="Maximum results", description_ru="Максимум результатов", default=100)
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Persons list", description_ru="Список персон")
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="person_get",
        path="/api/v1/persons/{person}",
        method=HttpMethod.GET,
        title_en="Get Person Details",
        title_ru="Получить детали персоны",
        description_en="Get detailed information about a person.",
        description_ru="Получить подробную информацию о персоне.",
        category="persons",
        tags=["persons", "details"],
        parameters=[
            ApiParameter(name="person", type="string", required=True, location="path",
                        description_en="Person identifier (slug or name)", description_ru="Идентификатор персоны",
                        example="vitalik-buterin")
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Person details", description_ru="Детали персоны"),
            ApiResponse(status_code=404, description_en="Person not found", description_ru="Персона не найдена")
        ]
    ),
    
    # ───────────────────────────────────────────────────────────
    # FUNDRAISING API (Public v1)
    # ───────────────────────────────────────────────────────────
    
    ApiEndpoint(
        endpoint_id="fundraising_list",
        path="/api/v1/fundraising",
        method=HttpMethod.GET,
        title_en="List Fundraising Rounds",
        title_ru="Список раундов финансирования",
        description_en="Get all fundraising rounds with filters.",
        description_ru="Получить все раунды финансирования с фильтрами.",
        category="fundraising",
        tags=["fundraising", "funding", "rounds"],
        parameters=[
            ApiParameter(name="round_type", type="string", required=False, location="query",
                        description_en="Filter: seed, series_a, series_b", description_ru="Фильтр: seed, series_a, series_b"),
            ApiParameter(name="min_amount", type="number", required=False, location="query",
                        description_en="Minimum raise amount in USD", description_ru="Минимальная сумма в USD"),
            ApiParameter(name="limit", type="integer", required=False, location="query",
                        description_en="Maximum results", description_ru="Максимум результатов", default=100)
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Fundraising rounds", description_ru="Раунды финансирования")
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="fundraising_recent",
        path="/api/v1/fundraising/recent",
        method=HttpMethod.GET,
        title_en="Recent Fundraising Rounds",
        title_ru="Недавние раунды финансирования",
        description_en="Get most recent fundraising rounds.",
        description_ru="Получить последние раунды финансирования.",
        category="fundraising",
        tags=["fundraising", "recent"],
        parameters=[
            ApiParameter(name="days", type="integer", required=False, location="query",
                        description_en="Days back", description_ru="Дней назад", default=30),
            ApiParameter(name="limit", type="integer", required=False, location="query",
                        description_en="Maximum results", description_ru="Максимум результатов", default=50)
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Recent rounds", description_ru="Недавние раунды")
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="fundraising_top",
        path="/api/v1/fundraising/top",
        method=HttpMethod.GET,
        title_en="Top Fundraising Rounds",
        title_ru="Топ раунды финансирования",
        description_en="Get largest fundraising rounds by amount.",
        description_ru="Получить крупнейшие раунды финансирования по сумме.",
        category="fundraising",
        tags=["fundraising", "top"],
        parameters=[
            ApiParameter(name="limit", type="integer", required=False, location="query",
                        description_en="Maximum results", description_ru="Максимум результатов", default=20)
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Top rounds", description_ru="Топ раунды")
        ]
    ),
    
    # ───────────────────────────────────────────────────────────
    # UNLOCKS API (Public v1)
    # ───────────────────────────────────────────────────────────
    
    ApiEndpoint(
        endpoint_id="unlocks_list",
        path="/api/v1/unlocks",
        method=HttpMethod.GET,
        title_en="List Token Unlocks",
        title_ru="Список анлоков токенов",
        description_en="Get all token unlocks.",
        description_ru="Получить все анлоки токенов.",
        category="unlocks",
        tags=["unlocks", "vesting", "tokens"],
        parameters=[
            ApiParameter(name="min_value", type="number", required=False, location="query",
                        description_en="Minimum unlock value in USD", description_ru="Минимальная стоимость анлока в USD"),
            ApiParameter(name="limit", type="integer", required=False, location="query",
                        description_en="Maximum results", description_ru="Максимум результатов", default=100)
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Token unlocks", description_ru="Анлоки токенов")
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="unlocks_upcoming",
        path="/api/v1/unlocks/upcoming",
        method=HttpMethod.GET,
        title_en="Upcoming Token Unlocks",
        title_ru="Предстоящие анлоки токенов",
        description_en="Get upcoming token unlocks within time window.",
        description_ru="Получить предстоящие анлоки токенов в заданном окне.",
        category="unlocks",
        tags=["unlocks", "upcoming"],
        parameters=[
            ApiParameter(name="days", type="integer", required=False, location="query",
                        description_en="Days ahead", description_ru="Дней вперёд", default=30),
            ApiParameter(name="limit", type="integer", required=False, location="query",
                        description_en="Maximum results", description_ru="Максимум результатов", default=50)
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Upcoming unlocks", description_ru="Предстоящие анлоки")
        ]
    ),
    
    # ───────────────────────────────────────────────────────────
    # ICO API (Public v1)
    # ───────────────────────────────────────────────────────────
    
    ApiEndpoint(
        endpoint_id="ico_list",
        path="/api/v1/ico",
        method=HttpMethod.GET,
        title_en="List ICOs / Token Sales",
        title_ru="Список ICO / Token Sales",
        description_en="Get all ICOs and token sales.",
        description_ru="Получить все ICO и продажи токенов.",
        category="ico",
        tags=["ico", "token_sale"],
        parameters=[
            ApiParameter(name="status", type="string", required=False, location="query",
                        description_en="Filter: upcoming, active, completed", description_ru="Фильтр: upcoming, active, completed"),
            ApiParameter(name="limit", type="integer", required=False, location="query",
                        description_en="Maximum results", description_ru="Максимум результатов", default=100)
        ],
        responses=[
            ApiResponse(status_code=200, description_en="ICO list", description_ru="Список ICO")
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="ico_upcoming",
        path="/api/v1/ico/upcoming",
        method=HttpMethod.GET,
        title_en="Upcoming ICOs",
        title_ru="Предстоящие ICO",
        description_en="Get upcoming ICOs and token sales.",
        description_ru="Получить предстоящие ICO и продажи токенов.",
        category="ico",
        tags=["ico", "upcoming"],
        parameters=[],
        responses=[
            ApiResponse(status_code=200, description_en="Upcoming ICOs", description_ru="Предстоящие ICO")
        ]
    ),
    
    # ───────────────────────────────────────────────────────────
    # EXCHANGES API (Public v1)
    # ───────────────────────────────────────────────────────────
    
    ApiEndpoint(
        endpoint_id="exchanges_list",
        path="/api/v1/exchanges",
        method=HttpMethod.GET,
        title_en="List Exchanges",
        title_ru="Список бирж",
        description_en="Get list of all exchanges (CEX/DEX).",
        description_ru="Получить список всех бирж (CEX/DEX).",
        category="exchanges",
        tags=["exchanges", "cex", "dex"],
        parameters=[
            ApiParameter(name="limit", type="integer", required=False, location="query",
                        description_en="Maximum results", description_ru="Максимум результатов", default=50)
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Exchanges list", description_ru="Список бирж")
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="exchange_get",
        path="/api/v1/exchanges/{exchange}",
        method=HttpMethod.GET,
        title_en="Get Exchange Details",
        title_ru="Получить детали биржи",
        description_en="Get detailed information about an exchange.",
        description_ru="Получить подробную информацию о бирже.",
        category="exchanges",
        tags=["exchanges", "details"],
        parameters=[
            ApiParameter(name="exchange", type="string", required=True, location="path",
                        description_en="Exchange identifier", description_ru="Идентификатор биржи",
                        example="binance")
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Exchange details", description_ru="Детали биржи")
        ]
    ),
    
    # ───────────────────────────────────────────────────────────
    # SEARCH API (Public v1)
    # ───────────────────────────────────────────────────────────
    
    ApiEndpoint(
        endpoint_id="search",
        path="/api/v1/search",
        method=HttpMethod.GET,
        title_en="Unified Search",
        title_ru="Универсальный поиск",
        description_en="Search across all entities: projects, funds, persons, exchanges.",
        description_ru="Поиск по всем сущностям: проекты, фонды, персоны, биржи.",
        category="search",
        tags=["search", "find"],
        parameters=[
            ApiParameter(name="q", type="string", required=True, location="query",
                        description_en="Search query", description_ru="Поисковый запрос",
                        example="ethereum"),
            ApiParameter(name="limit", type="integer", required=False, location="query",
                        description_en="Maximum results per entity type", description_ru="Максимум результатов по типу", default=20)
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Search results", description_ru="Результаты поиска",
                       example={
                           "query": "ethereum",
                           "total": 5,
                           "results": {
                               "projects": [{"name": "Ethereum", "symbol": "ETH"}],
                               "funds": [],
                               "persons": [{"name": "Vitalik Buterin"}],
                               "exchanges": []
                           }
                       })
        ]
    ),
    
    # ═══════════════════════════════════════════════════════════════
    # MARKET DATA API - First Layer (Exchange/Market Data)
    # ═══════════════════════════════════════════════════════════════
    
    # --- Global Market Stats ---
    ApiEndpoint(
        endpoint_id="market_global",
        path="/api/market/global",
        method=HttpMethod.GET,
        title_en="Global Market Statistics",
        title_ru="Глобальная статистика рынка",
        description_en="Get global cryptocurrency market statistics including total market cap, 24h volume, BTC/ETH dominance. Aggregates data from CoinGecko and exchange providers.",
        description_ru="Получить глобальную статистику криптовалютного рынка: общая капитализация, объём за 24ч, доминация BTC/ETH. Агрегирует данные из CoinGecko и биржевых провайдеров.",
        category="market",
        tags=["market", "global", "stats"],
        responses=[
            ApiResponse(status_code=200, description_en="Global market data", description_ru="Глобальные данные рынка",
                       example={
                           "ts": 1772730000000,
                           "total_market_cap": 2300000000000,
                           "total_volume_24h": 120000000000,
                           "btc_dominance": 52.4,
                           "eth_dominance": 18.3,
                           "market_cap_change_24h": 1.5
                       })
        ]
    ),
    
    # --- Quote ---
    ApiEndpoint(
        endpoint_id="market_quote",
        path="/api/market/quote/{symbol}",
        method=HttpMethod.GET,
        title_en="Get Price Quote",
        title_ru="Получить котировку",
        description_en="Get real-time price quote for any cryptocurrency symbol. Supports multiple providers (HyperLiquid, Binance, Bybit, Coinbase) with automatic fallback.",
        description_ru="Получить котировку в реальном времени для любой криптовалюты. Поддерживает несколько провайдеров (HyperLiquid, Binance, Bybit, Coinbase) с автоматическим переключением.",
        category="market",
        tags=["market", "quote", "price"],
        parameters=[
            ApiParameter(name="symbol", type="string", required=True, location="path",
                        description_en="Cryptocurrency symbol (BTC, ETH, SOL)", description_ru="Символ криптовалюты (BTC, ETH, SOL)", example="BTC"),
            ApiParameter(name="provider", type="string", required=False, location="query",
                        description_en="Data provider", description_ru="Провайдер данных", default="auto", enum=["auto", "hyperliquid", "binance", "bybit", "coinbase"]),
            ApiParameter(name="vs", type="string", required=False, location="query",
                        description_en="Quote currency", description_ru="Валюта котировки", default="usd")
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Price quote", description_ru="Котировка",
                       example={
                           "symbol": "BTC",
                           "vs": "usd",
                           "price": 69123.12,
                           "change": {"24h": 1.85},
                           "volume": {"24h": 31234567890},
                           "provider": "hyperliquid"
                       })
        ]
    ),
    
    # --- Index Price ---
    ApiEndpoint(
        endpoint_id="market_index",
        path="/api/market/index/{symbol}",
        method=HttpMethod.GET,
        title_en="Aggregated Index Price",
        title_ru="Агрегированная индексная цена",
        description_en="Get aggregated index price calculated using Robust VWAP (Volume-Weighted Average Price) from all exchanges. Shows price sources, weights, outliers, and spread.",
        description_ru="Получить агрегированную индексную цену, рассчитанную по методу Robust VWAP (взвешенная по объёму средняя цена) со всех бирж. Показывает источники цен, веса, выбросы и спред.",
        category="market",
        tags=["market", "index", "vwap", "aggregation"],
        parameters=[
            ApiParameter(name="symbol", type="string", required=True, location="path",
                        description_en="Cryptocurrency symbol", description_ru="Символ криптовалюты", example="BTC")
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Index price data", description_ru="Данные индексной цены",
                       example={
                           "symbol": "BTC",
                           "index_price": 64210.5,
                           "method": "robust_vwap",
                           "sources": [
                               {"exchange": "binance", "price": 64212, "weight": 0.36},
                               {"exchange": "bybit", "price": 64205, "weight": 0.28}
                           ],
                           "spread_bps": 6.2
                       })
        ]
    ),
    
    # --- Market Context ---
    ApiEndpoint(
        endpoint_id="market_context",
        path="/api/market/context",
        method=HttpMethod.GET,
        title_en="Market Context Dashboard",
        title_ru="Контекст рынка (дашборд)",
        description_en="Get comprehensive market context for dashboard: total market cap, BTC/ETH dominance, Fear & Greed index, BTC price and volume.",
        description_ru="Получить полный контекст рынка для дашборда: общая капитализация, доминация BTC/ETH, индекс Fear & Greed, цена и объём BTC.",
        category="market",
        tags=["market", "context", "dashboard"],
        responses=[
            ApiResponse(status_code=200, description_en="Market context", description_ru="Контекст рынка",
                       example={
                           "total_market_cap": 3000000000000,
                           "btc_dominance": 59.16,
                           "eth_dominance": 11.76,
                           "fear_greed": 34,
                           "fear_greed_label": "Extreme Fear"
                       })
        ]
    ),
    
    # --- Exchanges List ---
    ApiEndpoint(
        endpoint_id="market_exchanges_list",
        path="/api/market/exchanges",
        method=HttpMethod.GET,
        title_en="Supported Exchanges",
        title_ru="Поддерживаемые биржи",
        description_en="Get list of all supported exchanges with their health status, latency, and proxy usage.",
        description_ru="Получить список всех поддерживаемых бирж с их статусом здоровья, задержкой и использованием прокси.",
        category="market",
        tags=["market", "exchanges", "status"],
        responses=[
            ApiResponse(status_code=200, description_en="Exchanges list", description_ru="Список бирж",
                       example={
                           "exchanges": [
                               {"exchange": "binance", "healthy": True, "latency_ms": 150, "using_proxy": True},
                               {"exchange": "hyperliquid", "healthy": True, "latency_ms": 50, "using_proxy": False}
                           ]
                       })
        ]
    ),
    
    # --- Where Token Trades ---
    ApiEndpoint(
        endpoint_id="market_token_exchanges",
        path="/api/market/exchanges/{symbol}",
        method=HttpMethod.GET,
        title_en="Where Token Trades",
        title_ru="Где торгуется токен",
        description_en="Get list of exchanges where specific token is traded, with pairs count, top pairs, volume, and last price.",
        description_ru="Получить список бирж, где торгуется конкретный токен, с количеством пар, топ-парами, объёмом и последней ценой.",
        category="market",
        tags=["market", "exchanges", "token"],
        parameters=[
            ApiParameter(name="symbol", type="string", required=True, location="path",
                        description_en="Token symbol", description_ru="Символ токена", example="ETH")
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Token exchanges", description_ru="Биржи токена",
                       example={
                           "symbol": "ETH",
                           "exchanges_count": 4,
                           "exchanges": [
                               {"exchange": "binance", "pairs_count": 312, "top_pairs": ["ETH/USDT"], "volume_24h": 1234567890}
                           ]
                       })
        ]
    ),
    
    # --- Market Health ---
    ApiEndpoint(
        endpoint_id="market_health",
        path="/api/market/health/{symbol}",
        method=HttpMethod.GET,
        title_en="Market Health Assessment",
        title_ru="Оценка здоровья рынка",
        description_en="Get market health assessment for symbol: data freshness, available/missing providers, price dispersion, anomalies.",
        description_ru="Получить оценку здоровья рынка для символа: актуальность данных, доступные/недоступные провайдеры, разброс цен, аномалии.",
        category="market",
        tags=["market", "health", "quality"],
        parameters=[
            ApiParameter(name="symbol", type="string", required=True, location="path",
                        description_en="Symbol", description_ru="Символ", example="BTC")
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Health assessment", description_ru="Оценка здоровья",
                       example={
                           "symbol": "BTC",
                           "health_score": 85,
                           "freshness": "live",
                           "providers": {"available": ["hyperliquid", "binance"], "missing": []},
                           "dispersion_pct": 0.05
                       })
        ]
    ),
    
    # --- Candles ---
    ApiEndpoint(
        endpoint_id="market_candles",
        path="/api/market/candles/{symbol}",
        method=HttpMethod.GET,
        title_en="OHLCV Candles",
        title_ru="Свечи OHLCV",
        description_en="Get OHLCV (Open, High, Low, Close, Volume) candlestick data for charting. Supports multiple timeframes.",
        description_ru="Получить данные свечей OHLCV (Open, High, Low, Close, Volume) для графиков. Поддерживает различные таймфреймы.",
        category="market",
        tags=["market", "candles", "ohlcv", "chart"],
        parameters=[
            ApiParameter(name="symbol", type="string", required=True, location="path",
                        description_en="Symbol", description_ru="Символ", example="BTC"),
            ApiParameter(name="tf", type="string", required=False, location="query",
                        description_en="Timeframe", description_ru="Таймфрейм", default="1h", enum=["1m", "5m", "15m", "1h", "4h", "1d"]),
            ApiParameter(name="limit", type="integer", required=False, location="query",
                        description_en="Number of candles", description_ru="Количество свечей", default=300)
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Candle data", description_ru="Данные свечей",
                       example={
                           "symbol": "BTC",
                           "tf": "1h",
                           "candles": [[1709996400, 68900, 69200, 68750, 69123, 1234.56]]
                       })
        ]
    ),
    
    # --- Market Signals ---
    ApiEndpoint(
        endpoint_id="market_signals",
        path="/api/market/signals/{symbol}",
        method=HttpMethod.GET,
        title_en="Trading Signals",
        title_ru="Торговые сигналы",
        description_en="Get computed trading signals: momentum, trend strength, volatility, liquidity depth, funding pressure.",
        description_ru="Получить рассчитанные торговые сигналы: моментум, сила тренда, волатильность, глубина ликвидности, давление фандинга.",
        category="market",
        tags=["market", "signals", "indicators"],
        parameters=[
            ApiParameter(name="symbol", type="string", required=True, location="path",
                        description_en="Symbol", description_ru="Символ", example="BTC"),
            ApiParameter(name="timeframe", type="string", required=False, location="query",
                        description_en="Timeframe", description_ru="Таймфрейм", default="1h")
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Trading signals", description_ru="Торговые сигналы",
                       example={
                           "symbol": "BTC",
                           "signals": {
                               "momentum": {"value": 0.84, "interpretation": "bullish"},
                               "trend_strength": {"value": 27.1, "interpretation": "strong"},
                               "volatility": {"value": 0.032, "interpretation": "elevated"}
                           }
                       })
        ]
    ),
    
    # --- Screener ---
    ApiEndpoint(
        endpoint_id="market_screener",
        path="/api/market/screener",
        method=HttpMethod.GET,
        title_en="Market Screener",
        title_ru="Скринер рынка",
        description_en="Get pre-computed market lists: trending, top gainers, losers, volume leaders. Ready-to-render data for widgets.",
        description_ru="Получить готовые списки рынка: трендовые, топ роста, падения, лидеры объёма. Готовые данные для виджетов.",
        category="market",
        tags=["market", "screener", "gainers", "losers"],
        parameters=[
            ApiParameter(name="view", type="string", required=False, location="query",
                        description_en="View type", description_ru="Тип просмотра", default="gainers_24h",
                        enum=["trending", "gainers_24h", "losers_24h", "volume", "new_7d"]),
            ApiParameter(name="limit", type="integer", required=False, location="query",
                        description_en="Results limit", description_ru="Лимит результатов", default=20)
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Screener results", description_ru="Результаты скринера",
                       example={
                           "view": "gainers_24h",
                           "items": [{"symbol": "WLD", "price": 1.85, "change_24h": 19.51}]
                       })
        ]
    ),
    
    # --- Pump Radar ---
    ApiEndpoint(
        endpoint_id="market_pump_radar",
        path="/api/market/pump-radar",
        method=HttpMethod.GET,
        title_en="Pump Detection Radar",
        title_ru="Радар обнаружения пампов",
        description_en="Detect potential pumps using multi-signal analysis: price velocity, volume spike, OI growth, funding shift. Score 0-100.",
        description_ru="Обнаружение потенциальных пампов с помощью мульти-сигнального анализа: скорость цены, всплеск объёма, рост OI, сдвиг фандинга. Оценка 0-100.",
        category="market",
        tags=["market", "pump", "radar", "signals"],
        parameters=[
            ApiParameter(name="window", type="string", required=False, location="query",
                        description_en="Time window", description_ru="Временное окно", default="1h"),
            ApiParameter(name="limit", type="integer", required=False, location="query",
                        description_en="Results limit", description_ru="Лимит результатов", default=20)
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Pump radar results", description_ru="Результаты радара пампов",
                       example={
                           "items": [{
                               "symbol": "WLD",
                               "pump_score": 91,
                               "signals": {"price_velocity": 0.062, "volume_spike": 4.1}
                           }]
                       })
        ]
    ),
    
    # --- Capital Rotation ---
    ApiEndpoint(
        endpoint_id="market_rotation",
        path="/api/market/rotation",
        method=HttpMethod.GET,
        title_en="Capital Rotation",
        title_ru="Ротация капитала",
        description_en="Detect capital rotation between BTC and Alts. Shows current market regime: BTC season, Alt season, or neutral.",
        description_ru="Определение ротации капитала между BTC и альткоинами. Показывает текущий режим рынка: сезон BTC, сезон альтов или нейтральный.",
        category="market",
        tags=["market", "rotation", "dominance"],
        responses=[
            ApiResponse(status_code=200, description_en="Rotation data", description_ru="Данные ротации",
                       example={
                           "btc_dominance": 52.4,
                           "alt_dominance": 42.1,
                           "regime": "neutral",
                           "regime_score": 50
                       })
        ]
    ),
    
    # --- Indicators Widget ---
    ApiEndpoint(
        endpoint_id="market_indicators",
        path="/api/market/indicators",
        method=HttpMethod.GET,
        title_en="Indicator Widgets",
        title_ru="Виджеты индикаторов",
        description_en="Get all indicator widgets in one call: trending, gainers, accumulation, new listings, token unlocks, market context.",
        description_ru="Получить все виджеты индикаторов одним запросом: трендовые, лидеры роста, накопление, новые листинги, анлоки токенов, контекст рынка.",
        category="market",
        tags=["market", "indicators", "widgets"],
        parameters=[
            ApiParameter(name="set", type="string", required=False, location="query",
                        description_en="Indicator set", description_ru="Набор индикаторов", default="base"),
            ApiParameter(name="limit", type="integer", required=False, location="query",
                        description_en="Items per widget", description_ru="Элементов на виджет", default=10)
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Indicator widgets", description_ru="Виджеты индикаторов",
                       example={
                           "widgets": [
                               {"key": "trending", "title": "Trending", "items": []},
                               {"key": "gainers_24h", "title": "Top Gainers", "items": []}
                           ]
                       })
        ]
    ),
    
    # ═══════════════════════════════════════════════════════════════
    # DERIVATIVES API
    # ═══════════════════════════════════════════════════════════════
    
    ApiEndpoint(
        endpoint_id="derivatives_snapshot",
        path="/api/derivatives/snapshot/{symbol}",
        method=HttpMethod.GET,
        title_en="Derivatives Snapshot",
        title_ru="Снимок деривативов",
        description_en="Get full derivatives snapshot: Open Interest, Funding Rate, Mark Price, Index Price, Basis.",
        description_ru="Получить полный снимок деривативов: Open Interest, Funding Rate, Mark Price, Index Price, Basis.",
        category="derivatives",
        tags=["derivatives", "funding", "oi"],
        parameters=[
            ApiParameter(name="symbol", type="string", required=True, location="path",
                        description_en="Symbol", description_ru="Символ", example="BTC")
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Derivatives snapshot", description_ru="Снимок деривативов",
                       example={
                           "symbol": "BTC",
                           "oi_usd": 830000000,
                           "funding_rate": 0.0001,
                           "mark_price": 64010
                       })
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="derivatives_funding_global",
        path="/api/derivatives/funding/global",
        method=HttpMethod.GET,
        title_en="Global Funding Rates",
        title_ru="Глобальные ставки фандинга",
        description_en="Get aggregated funding rates across all exchanges, weighted by Open Interest. Shows market sentiment (overlong/overshort).",
        description_ru="Получить агрегированные ставки фандинга по всем биржам, взвешенные по Open Interest. Показывает настроение рынка (перекупленность/перепроданность).",
        category="derivatives",
        tags=["derivatives", "funding", "global"],
        responses=[
            ApiResponse(status_code=200, description_en="Global funding", description_ru="Глобальный фандинг",
                       example={
                           "market_funding": 0.017,
                           "sentiment": "overlong",
                           "top_extremes": [{"symbol": "PEPE", "funding": 0.12}]
                       })
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="derivatives_funding_pressure",
        path="/api/derivatives/funding/pressure",
        method=HttpMethod.GET,
        title_en="Funding Pressure Index",
        title_ru="Индекс давления фандинга",
        description_en="Funding Pressure Index (FPI) - market-wide funding pressure weighted by OI. Indicates crowded positions.",
        description_ru="Индекс давления фандинга (FPI) - давление фандинга по всему рынку, взвешенное по OI. Указывает на переполненные позиции.",
        category="derivatives",
        tags=["derivatives", "funding", "pressure"],
        responses=[
            ApiResponse(status_code=200, description_en="Funding pressure", description_ru="Давление фандинга",
                       example={
                           "market_fpi": 0.018,
                           "sentiment": "overlong",
                           "by_exchange": {"hyperliquid": 0.021, "binance": 0.015}
                       })
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="derivatives_liquidations",
        path="/api/derivatives/liquidations/global",
        method=HttpMethod.GET,
        title_en="Global Liquidations",
        title_ru="Глобальные ликвидации",
        description_en="Aggregated liquidation data: total liquidations, long/short breakdown, imbalance indicator.",
        description_ru="Агрегированные данные ликвидаций: общие ликвидации, разбивка long/short, индикатор дисбаланса.",
        category="derivatives",
        tags=["derivatives", "liquidations"],
        parameters=[
            ApiParameter(name="window", type="string", required=False, location="query",
                        description_en="Time window", description_ru="Временное окно", default="24h")
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Liquidations data", description_ru="Данные ликвидаций",
                       example={
                           "total_liquidations": 1823000000,
                           "long_liq": 1120000000,
                           "short_liq": 703000000,
                           "imbalance": -0.23
                       })
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="derivatives_oi_spikes",
        path="/api/derivatives/oi-spikes",
        method=HttpMethod.GET,
        title_en="Open Interest Spikes",
        title_ru="Всплески Open Interest",
        description_en="Detect Open Interest spikes - large position openings/closings. OI spike > 1.5 indicates large new positions.",
        description_ru="Обнаружение всплесков Open Interest - крупные открытия/закрытия позиций. OI spike > 1.5 указывает на крупные новые позиции.",
        category="derivatives",
        tags=["derivatives", "oi", "spikes"],
        responses=[
            ApiResponse(status_code=200, description_en="OI spikes", description_ru="Всплески OI",
                       example={
                           "tokens": [{"symbol": "SOL", "oi_spike": 2.1, "oi_usd": 830000000}]
                       })
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="derivatives_crowding",
        path="/api/derivatives/crowding",
        method=HttpMethod.GET,
        title_en="Crowded Trades",
        title_ru="Переполненные позиции",
        description_en="Detect crowded trades: extreme funding + growing OI = potential squeeze. Shows risk level.",
        description_ru="Обнаружение переполненных позиций: экстремальный фандинг + рост OI = потенциальный сквиз. Показывает уровень риска.",
        category="derivatives",
        tags=["derivatives", "crowding", "risk"],
        responses=[
            ApiResponse(status_code=200, description_en="Crowded trades", description_ru="Переполненные позиции",
                       example={
                           "crowded_trades": [{"symbol": "PEPE", "side": "crowded_long", "funding": 0.12, "risk": "high"}]
                       })
        ]
    ),
    
    # ═══════════════════════════════════════════════════════════════
    # INDICES API
    # ═══════════════════════════════════════════════════════════════
    
    ApiEndpoint(
        endpoint_id="indices_fear_greed",
        path="/api/indices/fear-greed",
        method=HttpMethod.GET,
        title_en="Fear & Greed Index",
        title_ru="Индекс страха и жадности",
        description_en="Crypto Fear & Greed Index: 0-24 Extreme Fear, 25-49 Fear, 50-74 Greed, 75-100 Extreme Greed. Includes 7-day history.",
        description_ru="Индекс страха и жадности: 0-24 Крайний страх, 25-49 Страх, 50-74 Жадность, 75-100 Крайняя жадность. Включает историю за 7 дней.",
        category="indices",
        tags=["indices", "fear", "greed", "sentiment"],
        responses=[
            ApiResponse(status_code=200, description_en="Fear & Greed data", description_ru="Данные Fear & Greed",
                       example={
                           "value": 34,
                           "label": "Fear",
                           "history": [{"value": 32, "label": "Fear", "date": "1772150400"}]
                       })
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="indices_btc_dominance",
        path="/api/indices/dominance/btc",
        method=HttpMethod.GET,
        title_en="BTC Dominance",
        title_ru="Доминация BTC",
        description_en="Bitcoin market dominance percentage. >55% = BTC season, <45% = Alt season.",
        description_ru="Процент доминации Bitcoin на рынке. >55% = сезон BTC, <45% = сезон альтов.",
        category="indices",
        tags=["indices", "dominance", "btc"],
        responses=[
            ApiResponse(status_code=200, description_en="BTC dominance", description_ru="Доминация BTC",
                       example={
                           "btc_dominance": 52.4,
                           "btc_market_cap": 1200000000000,
                           "trend": "neutral"
                       })
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="indices_stable_dominance",
        path="/api/indices/dominance/stables",
        method=HttpMethod.GET,
        title_en="Stablecoin Dominance",
        title_ru="Доминация стейблкоинов",
        description_en="Stablecoin dominance (USDT + USDC). High = 'cash on sidelines' (risk off), Low = 'risk on'.",
        description_ru="Доминация стейблкоинов (USDT + USDC). Высокая = 'деньги на обочине' (risk off), Низкая = 'risk on'.",
        category="indices",
        tags=["indices", "dominance", "stablecoins"],
        parameters=[
            ApiParameter(name="symbols", type="string", required=False, location="query",
                        description_en="Stablecoin symbols", description_ru="Символы стейблкоинов", default="USDT,USDC")
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Stable dominance", description_ru="Доминация стейблкоинов",
                       example={
                           "stable_dominance": 5.2,
                           "breakdown": {"USDT": 85000000000, "USDC": 32000000000},
                           "sentiment": "neutral"
                       })
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="indices_alt_dominance",
        path="/api/indices/dominance/alts-clean",
        method=HttpMethod.GET,
        title_en="Clean Alt Dominance",
        title_ru="Чистая доминация альтов",
        description_en="Alt dominance excluding BTC and stablecoins. Shows 'real' alt market share without distortion.",
        description_ru="Доминация альтов без BTC и стейблкоинов. Показывает 'реальную' долю рынка альтов без искажений.",
        category="indices",
        tags=["indices", "dominance", "alts"],
        responses=[
            ApiResponse(status_code=200, description_en="Alt dominance", description_ru="Доминация альтов",
                       example={
                           "alt_dominance": 42.1,
                           "alt_market_cap": 1200000000000,
                           "season": "neutral"
                       })
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="indices_overview",
        path="/api/indices/overview",
        method=HttpMethod.GET,
        title_en="Market Indices Overview",
        title_ru="Обзор рыночных индексов",
        description_en="Full market indices overview: total market cap, volume, dominance metrics, Fear & Greed.",
        description_ru="Полный обзор рыночных индексов: общая капитализация, объём, метрики доминации, Fear & Greed.",
        category="indices",
        tags=["indices", "overview"],
        responses=[
            ApiResponse(status_code=200, description_en="Indices overview", description_ru="Обзор индексов",
                       example={
                           "total_market_cap": 3000000000000,
                           "dominance": {"btc": 52.4, "eth": 18.3},
                           "fear_greed": 34
                       })
        ]
    ),
    
    # ═══════════════════════════════════════════════════════════════
    # EXCHANGE-SPECIFIC API
    # ═══════════════════════════════════════════════════════════════
    
    ApiEndpoint(
        endpoint_id="exchange_hot",
        path="/api/exchanges/{exchange}/hot",
        method=HttpMethod.GET,
        title_en="Hot Tokens on Exchange",
        title_ru="Горячие токены на бирже",
        description_en="Get top traded tokens on specific exchange (Binance, Bybit, HyperLiquid, Coinbase).",
        description_ru="Получить топ торгуемых токенов на конкретной бирже (Binance, Bybit, HyperLiquid, Coinbase).",
        category="exchange",
        tags=["exchange", "hot", "volume"],
        parameters=[
            ApiParameter(name="exchange", type="string", required=True, location="path",
                        description_en="Exchange name", description_ru="Название биржи", example="binance"),
            ApiParameter(name="limit", type="integer", required=False, location="query",
                        description_en="Results limit", description_ru="Лимит результатов", default=50)
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Hot tokens", description_ru="Горячие токены",
                       example={
                           "exchange": "binance",
                           "tokens": [{"symbol": "PEPE", "volume_24h": 820000000}]
                       })
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="exchange_instruments",
        path="/api/exchanges/{exchange}/instruments",
        method=HttpMethod.GET,
        title_en="Exchange Instruments",
        title_ru="Инструменты биржи",
        description_en="Get all trading instruments on exchange with tick size, step size, min notional.",
        description_ru="Получить все торговые инструменты биржи с tick size, step size, min notional.",
        category="exchange",
        tags=["exchange", "instruments"],
        parameters=[
            ApiParameter(name="exchange", type="string", required=True, location="path",
                        description_en="Exchange name", description_ru="Название биржи", example="hyperliquid"),
            ApiParameter(name="type", type="string", required=False, location="query",
                        description_en="Instrument type", description_ru="Тип инструмента", enum=["spot", "perp"])
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Instruments list", description_ru="Список инструментов",
                       example={
                           "exchange": "hyperliquid",
                           "count": 150,
                           "instruments": [{"symbol": "BTC-PERP", "type": "perp"}]
                       })
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="exchange_status",
        path="/api/exchanges/{exchange}/status",
        method=HttpMethod.GET,
        title_en="Exchange Health Status",
        title_ru="Статус здоровья биржи",
        description_en="Get exchange health status: connectivity, latency, proxy usage.",
        description_ru="Получить статус здоровья биржи: соединение, задержка, использование прокси.",
        category="exchange",
        tags=["exchange", "status", "health"],
        parameters=[
            ApiParameter(name="exchange", type="string", required=True, location="path",
                        description_en="Exchange name", description_ru="Название биржи", example="binance")
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Exchange status", description_ru="Статус биржи",
                       example={
                           "exchange": "binance",
                           "healthy": True,
                           "latency_ms": 150,
                           "using_proxy": True
                       })
        ]
    ),
    
    # ═══════════════════════════════════════════════════════════════
    # SPOT MARKET API
    # ═══════════════════════════════════════════════════════════════
    
    ApiEndpoint(
        endpoint_id="spot_activity",
        path="/api/spot/activity",
        method=HttpMethod.GET,
        title_en="Spot Market Activity",
        title_ru="Активность спот-рынка",
        description_en="Get spot market activity - where the action is across exchanges.",
        description_ru="Получить активность спот-рынка - где сейчас происходит торговля на биржах.",
        category="spot",
        tags=["spot", "activity"],
        parameters=[
            ApiParameter(name="exchange", type="string", required=False, location="query",
                        description_en="Exchange filter", description_ru="Фильтр по бирже", default="all")
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Spot activity", description_ru="Активность спота",
                       example={
                           "items": [{"symbol": "BTCUSDT", "exchange": "binance", "volume_24h": 18000000000}]
                       })
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="spot_volume_leaders",
        path="/api/spot/leaders/volume",
        method=HttpMethod.GET,
        title_en="Volume Leaders",
        title_ru="Лидеры по объёму",
        description_en="Get top tokens by trading volume.",
        description_ru="Получить топ токенов по объёму торгов.",
        category="spot",
        tags=["spot", "volume", "leaders"],
        parameters=[
            ApiParameter(name="limit", type="integer", required=False, location="query",
                        description_en="Results limit", description_ru="Лимит результатов", default=50)
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Volume leaders", description_ru="Лидеры объёма",
                       example={
                           "items": [{"symbol": "BTC", "volume_24h": 31000000000, "rank": 1}]
                       })
        ]
    ),
    
    # ═══════════════════════════════════════════════════════════════
    # ON-CHAIN DATA API (Layer 4)
    # ═══════════════════════════════════════════════════════════════
    
    ApiEndpoint(
        endpoint_id="onchain_realized_cap",
        path="/api/onchain/realized-cap/{symbol}",
        method=HttpMethod.GET,
        title_en="Realized Capitalization",
        title_ru="Реализованная капитализация",
        description_en="Get Realized Capitalization - valuation based on price when coins last moved. Unlike market cap, realized cap filters out lost coins and long-term holdings. Ratio > 1 indicates overvaluation.",
        description_ru="Получить реализованную капитализацию - оценку на основе цены в момент последнего перемещения монет. В отличие от рыночной капитализации, фильтрует потерянные монеты и долгосрочные холдинги. Ratio > 1 означает переоценку.",
        category="onchain",
        tags=["onchain", "realized_cap", "valuation"],
        parameters=[
            ApiParameter(name="symbol", type="string", required=True, location="path",
                        description_en="Cryptocurrency symbol", description_ru="Символ криптовалюты", example="BTC")
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Realized cap data", description_ru="Данные реализованной капитализации",
                       example={
                           "symbol": "BTC",
                           "realized_cap": 450000000000,
                           "market_cap": 650000000000,
                           "ratio": 1.44,
                           "interpretation": "moderately_overvalued"
                       })
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="onchain_mvrv",
        path="/api/onchain/mvrv/{symbol}",
        method=HttpMethod.GET,
        title_en="MVRV Ratio",
        title_ru="Коэффициент MVRV",
        description_en="Market Value to Realized Value ratio. Key on-chain indicator: >3.5 = market top signal, <1.0 = buying opportunity. Historical BTC tops occurred at MVRV 3.5-4.2.",
        description_ru="Отношение рыночной стоимости к реализованной. Ключевой ончейн-индикатор: >3.5 = сигнал вершины, <1.0 = возможность покупки. Исторические вершины BTC были при MVRV 3.5-4.2.",
        category="onchain",
        tags=["onchain", "mvrv", "valuation", "signal"],
        parameters=[
            ApiParameter(name="symbol", type="string", required=True, location="path",
                        description_en="Cryptocurrency symbol", description_ru="Символ криптовалюты", example="BTC")
        ],
        responses=[
            ApiResponse(status_code=200, description_en="MVRV data", description_ru="Данные MVRV",
                       example={
                           "symbol": "BTC",
                           "mvrv": 1.44,
                           "zone": "fair_value",
                           "signal": "neutral",
                           "historical_context": {"btc_2021_top": 3.5}
                       })
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="onchain_nvt",
        path="/api/onchain/nvt/{symbol}",
        method=HttpMethod.GET,
        title_en="NVT Ratio",
        title_ru="Коэффициент NVT",
        description_en="Network Value to Transactions ratio - similar to P/E ratio for stocks. High NVT (>150) = overvalued relative to usage. Low NVT (<50) = undervalued.",
        description_ru="Отношение стоимости сети к объёму транзакций - аналог P/E для акций. Высокий NVT (>150) = переоценка относительно использования. Низкий NVT (<50) = недооценка.",
        category="onchain",
        tags=["onchain", "nvt", "valuation"],
        parameters=[
            ApiParameter(name="symbol", type="string", required=True, location="path",
                        description_en="Cryptocurrency symbol", description_ru="Символ криптовалюты", example="ETH")
        ],
        responses=[
            ApiResponse(status_code=200, description_en="NVT data", description_ru="Данные NVT",
                       example={
                           "symbol": "ETH",
                           "nvt": 65.4,
                           "signal": "fair_value",
                           "interpretation": "Network fairly valued relative to usage"
                       })
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="onchain_whale_transfers",
        path="/api/onchain/whale-transfers/{symbol}",
        method=HttpMethod.GET,
        title_en="Whale Transfers",
        title_ru="Переводы китов",
        description_en="Track large wallet transfers. Exchange inflows = potential sell pressure, outflows = accumulation signal. Essential for whale watching and market sentiment.",
        description_ru="Отслеживание крупных переводов. Приток на биржи = потенциальное давление продаж, отток = сигнал накопления. Важно для мониторинга китов и настроения рынка.",
        category="onchain",
        tags=["onchain", "whales", "transfers", "exchange_flow"],
        parameters=[
            ApiParameter(name="symbol", type="string", required=True, location="path",
                        description_en="Cryptocurrency symbol", description_ru="Символ криптовалюты", example="BTC"),
            ApiParameter(name="min_usd", type="number", required=False, location="query",
                        description_en="Minimum transfer value in USD", description_ru="Минимальная сумма перевода в USD", default=1000000)
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Whale transfer data", description_ru="Данные переводов китов",
                       example={
                           "symbol": "BTC",
                           "summary": {
                               "net_flow_direction": "outflow",
                               "exchange_inflows_usd": 150000000,
                               "exchange_outflows_usd": 200000000
                           },
                           "interpretation": {"signal": "bullish"}
                       })
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="onchain_stablecoin_flows",
        path="/api/onchain/stablecoin-flows",
        method=HttpMethod.GET,
        title_en="Stablecoin Flows",
        title_ru="Потоки стейблкоинов",
        description_en="Monitor stablecoin flows to/from exchanges. High stablecoin reserves = buying power accumulating (bullish). Includes USDT, USDC, DAI aggregated metrics.",
        description_ru="Мониторинг потоков стейблкоинов на/с бирж. Высокие резервы = накопление покупательной способности (бычий сигнал). Включает агрегированные метрики USDT, USDC, DAI.",
        category="onchain",
        tags=["onchain", "stablecoins", "exchange_flow", "liquidity"],
        parameters=[],
        responses=[
            ApiResponse(status_code=200, description_en="Stablecoin flow data", description_ru="Данные потоков стейблкоинов",
                       example={
                           "stablecoins": [{"symbol": "USDT", "market_cap": 110000000000}],
                           "aggregated": {"total_market_cap": 150000000000},
                           "activity_level": "high"
                       })
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="onchain_exchange_flows",
        path="/api/onchain/exchange-flows/{symbol}",
        method=HttpMethod.GET,
        title_en="Exchange Flows",
        title_ru="Потоки на биржах",
        description_en="Get exchange inflow/outflow metrics. Inflows = coins moving to exchanges (selling). Outflows = coins leaving exchanges (accumulation). Net positive = bullish.",
        description_ru="Метрики притока/оттока на биржах. Приток = монеты идут на биржи (продажа). Отток = монеты уходят с бирж (накопление). Чистый положительный = бычий.",
        category="onchain",
        tags=["onchain", "exchange", "flows"],
        parameters=[
            ApiParameter(name="symbol", type="string", required=True, location="path",
                        description_en="Cryptocurrency symbol", description_ru="Символ криптовалюты", example="ETH")
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Exchange flow data", description_ru="Данные потоков на биржах",
                       example={
                           "symbol": "ETH",
                           "exchange_flows": {
                               "inflows_24h_usd": 50000000,
                               "outflows_24h_usd": 75000000,
                               "net_flow_usd": 25000000,
                               "direction": "outflow"
                           },
                           "signal": "bullish"
                       })
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="onchain_active_addresses",
        path="/api/onchain/active-addresses/{symbol}",
        method=HttpMethod.GET,
        title_en="Active Addresses",
        title_ru="Активные адреса",
        description_en="Get active address metrics. Rising active addresses = growing network usage (bullish). Falling = declining interest (bearish). Key adoption indicator.",
        description_ru="Метрики активных адресов. Рост активных адресов = растущее использование сети (бычий). Падение = снижение интереса (медвежий). Ключевой индикатор адаптации.",
        category="onchain",
        tags=["onchain", "addresses", "activity", "adoption"],
        parameters=[
            ApiParameter(name="symbol", type="string", required=True, location="path",
                        description_en="Cryptocurrency symbol", description_ru="Символ криптовалюты", example="BTC")
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Active address data", description_ru="Данные активных адресов",
                       example={
                           "symbol": "BTC",
                           "active_addresses": {
                               "estimated_24h": 850000,
                               "change_24h_pct": 5.2
                           }
                       })
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="onchain_supply_distribution",
        path="/api/onchain/supply-distribution/{symbol}",
        method=HttpMethod.GET,
        title_en="Supply Distribution",
        title_ru="Распределение предложения",
        description_en="Get supply distribution by wallet size: Whales (>1000 BTC equiv), Large holders, Medium, Small, Retail. Includes Gini coefficient and decentralization score.",
        description_ru="Распределение по размеру кошельков: Киты (>1000 BTC эквив.), Крупные, Средние, Мелкие, Розница. Включает коэффициент Джини и оценку децентрализации.",
        category="onchain",
        tags=["onchain", "distribution", "whales", "decentralization"],
        parameters=[
            ApiParameter(name="symbol", type="string", required=True, location="path",
                        description_en="Cryptocurrency symbol", description_ru="Символ криптовалюты", example="ETH")
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Supply distribution", description_ru="Распределение предложения",
                       example={
                           "symbol": "ETH",
                           "distribution": {
                               "whales": {"estimated_pct_supply": 30}
                           },
                           "concentration_metrics": {"gini_coefficient_estimate": 0.75}
                       })
        ]
    ),
    
    # ═══════════════════════════════════════════════════════════════
    # TOKENOMICS API (P2)
    # ═══════════════════════════════════════════════════════════════
    
    ApiEndpoint(
        endpoint_id="tokenomics_overview",
        path="/api/tokenomics/overview/{symbol}",
        method=HttpMethod.GET,
        title_en="Tokenomics Overview",
        title_ru="Обзор токеномики",
        description_en="Comprehensive tokenomics overview: supply metrics, distribution estimates, vesting status, market metrics (market cap, FDV), and risk indicators.",
        description_ru="Полный обзор токеномики: метрики предложения, оценки распределения, статус вестинга, рыночные метрики (капитализация, FDV) и индикаторы риска.",
        category="tokenomics",
        tags=["tokenomics", "overview", "supply", "fdv"],
        parameters=[
            ApiParameter(name="symbol", type="string", required=True, location="path",
                        description_en="Token symbol", description_ru="Символ токена", example="ARB")
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Tokenomics overview", description_ru="Обзор токеномики",
                       example={
                           "symbol": "ARB",
                           "supply": {"circulating_pct": 42.5, "locked_pct": 57.5},
                           "valuation": {"mcap_fdv_ratio": 0.42},
                           "risk_assessment": {"level": "moderate"}
                       })
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="tokenomics_vesting_pressure",
        path="/api/tokenomics/vesting-pressure/{symbol}",
        method=HttpMethod.GET,
        title_en="Vesting Pressure",
        title_ru="Давление вестинга",
        description_en="Calculate vesting unlock pressure score. High pressure = more tokens unlocking relative to volume. Score >100 = critical (unlocks > daily volume).",
        description_ru="Расчёт давления разблокировок вестинга. Высокое давление = больше разблокировок относительно объёма. Score >100 = критический (разблокировки > дневного объёма).",
        category="tokenomics",
        tags=["tokenomics", "vesting", "pressure", "unlocks"],
        parameters=[
            ApiParameter(name="symbol", type="string", required=True, location="path",
                        description_en="Token symbol", description_ru="Символ токена", example="OP")
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Vesting pressure", description_ru="Давление вестинга",
                       example={
                           "symbol": "OP",
                           "vesting_pressure": {"score": 45.2, "level": "moderate"},
                           "unlock_estimates": {"estimated_monthly_unlock_usd": 50000000}
                       })
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="tokenomics_insider_supply",
        path="/api/tokenomics/insider-supply/{symbol}",
        method=HttpMethod.GET,
        title_en="Insider Supply",
        title_ru="Инсайдерское предложение",
        description_en="Estimate insider (team + investors) token holdings. Breakdown: team, investors, treasury, advisors. High insider supply = higher sell pressure risk.",
        description_ru="Оценка инсайдерских (команда + инвесторы) владений. Разбивка: команда, инвесторы, казна, советники. Высокое инсайдерское предложение = выше риск продаж.",
        category="tokenomics",
        tags=["tokenomics", "insider", "team", "investors"],
        parameters=[
            ApiParameter(name="symbol", type="string", required=True, location="path",
                        description_en="Token symbol", description_ru="Символ токена", example="SUI")
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Insider supply data", description_ru="Данные инсайдерского предложения",
                       example={
                           "symbol": "SUI",
                           "insider_supply": {
                               "total_insider_pct": 48,
                               "breakdown": {"team": {"pct": 18}, "investors": {"pct": 25}}
                           },
                           "risk_assessment": {"level": "moderate"}
                       })
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="tokenomics_sell_pressure_score",
        path="/api/tokenomics/sell-pressure-score/{symbol}",
        method=HttpMethod.GET,
        title_en="Sell Pressure Score",
        title_ru="Оценка давления продаж",
        description_en="Aggregated Sell Pressure Score (0-100). Components: vesting pressure (30%), insider holdings (25%), profit-taking potential (25%), inflation rate (20%).",
        description_ru="Агрегированная оценка давления продаж (0-100). Компоненты: давление вестинга (30%), инсайдерские владения (25%), потенциал фиксации прибыли (25%), инфляция (20%).",
        category="tokenomics",
        tags=["tokenomics", "sell_pressure", "risk"],
        parameters=[
            ApiParameter(name="symbol", type="string", required=True, location="path",
                        description_en="Token symbol", description_ru="Символ токена", example="APT")
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Sell pressure score", description_ru="Оценка давления продаж",
                       example={
                           "symbol": "APT",
                           "sell_pressure_score": {"total": 62.5, "level": "high"},
                           "components": {"vesting_pressure": {"score": 55}, "insider_holdings": {"score": 70}}
                       })
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="tokenomics_decentralization_score",
        path="/api/tokenomics/decentralization-score/{symbol}",
        method=HttpMethod.GET,
        title_en="Decentralization Score",
        title_ru="Оценка децентрализации",
        description_en="Token Decentralization Score (0-100). Components: distribution spread (40%), insider concentration (30%), exchange concentration (15%), governance participation (15%).",
        description_ru="Оценка децентрализации токена (0-100). Компоненты: распределение (40%), концентрация инсайдеров (30%), концентрация на биржах (15%), участие в управлении (15%).",
        category="tokenomics",
        tags=["tokenomics", "decentralization", "distribution"],
        parameters=[
            ApiParameter(name="symbol", type="string", required=True, location="path",
                        description_en="Token symbol", description_ru="Символ токена", example="UNI")
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Decentralization score", description_ru="Оценка децентрализации",
                       example={
                           "symbol": "UNI",
                           "decentralization_score": {"total": 68.5, "level": "decentralized"},
                           "components": {"distribution_spread": {"score": 75}}
                       })
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="tokenomics_inflation",
        path="/api/tokenomics/inflation/{symbol}",
        method=HttpMethod.GET,
        title_en="Token Inflation",
        title_ru="Инфляция токена",
        description_en="Get token inflation metrics: annual/daily rate, remaining inflation potential, estimated time to full dilution.",
        description_ru="Метрики инфляции токена: годовая/дневная ставка, остаточный инфляционный потенциал, примерное время до полного размывания.",
        category="tokenomics",
        tags=["tokenomics", "inflation", "supply"],
        parameters=[
            ApiParameter(name="symbol", type="string", required=True, location="path",
                        description_en="Token symbol", description_ru="Символ токена", example="SOL")
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Inflation metrics", description_ru="Метрики инфляции",
                       example={
                           "symbol": "SOL",
                           "inflation": {"annual_rate_pct": 5.5, "type": "inflationary"},
                           "dilution_impact": {"years_to_full_dilution": 8.5}
                       })
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="tokenomics_burns",
        path="/api/tokenomics/burns/{symbol}",
        method=HttpMethod.GET,
        title_en="Token Burns",
        title_ru="Сжигание токенов",
        description_en="Get token burn metrics: burn mechanism type, annual burn rate, deflationary status. Burns reduce supply, potentially increasing scarcity.",
        description_ru="Метрики сжигания токенов: тип механизма, годовая ставка сжигания, дефляционный статус. Сжигания уменьшают предложение, потенциально увеличивая дефицит.",
        category="tokenomics",
        tags=["tokenomics", "burns", "deflationary"],
        parameters=[
            ApiParameter(name="symbol", type="string", required=True, location="path",
                        description_en="Token symbol", description_ru="Символ токена", example="BNB")
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Burn metrics", description_ru="Метрики сжигания",
                       example={
                           "symbol": "BNB",
                           "burn_mechanism": {"has_burn": True, "burn_rate_annual_pct": 5},
                           "supply_trend": "deflationary"
                       })
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="tokenomics_unlock_impact",
        path="/api/tokenomics/unlock-impact/{symbol}",
        method=HttpMethod.GET,
        title_en="Unlock Market Impact",
        title_ru="Влияние разблокировки на рынок",
        description_en="Calculate market impact of upcoming unlocks. Impact = unlock_value / daily_volume. High impact (>1) means unlock exceeds daily volume - severe sell pressure expected.",
        description_ru="Расчёт влияния предстоящих разблокировок на рынок. Impact = стоимость_разблокировки / дневной_объём. Высокий impact (>1) означает превышение объёма - ожидается сильное давление продаж.",
        category="tokenomics",
        tags=["tokenomics", "unlocks", "impact", "sell_pressure"],
        parameters=[
            ApiParameter(name="symbol", type="string", required=True, location="path",
                        description_en="Token symbol", description_ru="Символ токена", example="ARB")
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Unlock impact analysis", description_ru="Анализ влияния разблокировки",
                       example={
                           "symbol": "ARB",
                           "unlock_impact": {
                               "volume_impact_ratio": 0.45,
                               "mcap_impact_pct": 2.5,
                               "severity": "moderate"
                           },
                           "next_unlock_estimate": {"value_usd": 25000000}
                       })
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="tokenomics_unlock_calendar",
        path="/api/tokenomics/unlock-calendar/{symbol}",
        method=HttpMethod.GET,
        title_en="Unlock Calendar",
        title_ru="Календарь разблокировок",
        description_en="Get upcoming token unlock events. Shows dates, amounts, USD values for scheduled vesting unlocks. Essential for anticipating sell pressure.",
        description_ru="Предстоящие разблокировки токенов. Показывает даты, суммы, USD-значения запланированных разблокировок вестинга. Важно для прогнозирования давления продаж.",
        category="tokenomics",
        tags=["tokenomics", "unlocks", "calendar", "vesting"],
        parameters=[
            ApiParameter(name="symbol", type="string", required=True, location="path",
                        description_en="Token symbol", description_ru="Символ токена", example="TIA"),
            ApiParameter(name="days", type="integer", required=False, location="query",
                        description_en="Days ahead to look", description_ru="Дней вперёд", default=90)
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Unlock calendar", description_ru="Календарь разблокировок",
                       example={
                           "symbol": "TIA",
                           "upcoming_unlocks": [{"date": "2025-01-15", "estimated_usd": 25000000}],
                           "summary": {"total_unlock_usd": 150000000}
                       })
        ]
    ),
    
    # ───────────────────────────────────────────────────────────
    # MARKET - EXCHANGE SHARE
    # ───────────────────────────────────────────────────────────
    
    ApiEndpoint(
        endpoint_id="market_exchange_share",
        path="/api/market/exchange-share/{symbol}",
        method=HttpMethod.GET,
        title_en="Exchange Market Share",
        title_ru="Доля бирж на рынке",
        description_en="Get market share of each exchange for a token. Shows volume distribution across exchanges. Useful for identifying dominant trading venues.",
        description_ru="Получить долю рынка каждой биржи для токена. Показывает распределение объёма по биржам. Полезно для определения доминирующих торговых площадок.",
        category="market",
        tags=["market", "exchanges", "volume", "share"],
        parameters=[
            ApiParameter(name="symbol", type="string", required=True, location="path",
                        description_en="Token symbol", description_ru="Символ токена", example="BTC")
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Exchange market share", description_ru="Доля бирж на рынке",
                       example={
                           "symbol": "BTC",
                           "total_volume_24h": 25000000000,
                           "exchanges": [
                               {"exchange": "binance", "volume_24h": 15000000000, "share_pct": 60},
                               {"exchange": "hyperliquid", "volume_24h": 5000000000, "share_pct": 20}
                           ],
                           "dominant_exchange": "binance"
                       })
        ]
    ),
    
    # ───────────────────────────────────────────────────────────
    # FUNDING FEED
    # ───────────────────────────────────────────────────────────
    
    ApiEndpoint(
        endpoint_id="funding_feed",
        path="/api/funding/feed",
        method=HttpMethod.GET,
        title_en="Funding Feed",
        title_ru="Лента инвестиций",
        description_en="Main funding feed with FOMO Score. Lists investment rounds with investor quality analysis, red flags detection, and smart ranking.",
        description_ru="Главная лента инвестиций с FOMO Score. Показывает инвестиционные раунды с анализом качества инвесторов, обнаружением красных флагов и умным ранжированием.",
        category="funding",
        tags=["funding", "investments", "fomo_score", "rounds"],
        parameters=[
            ApiParameter(name="mode", type="string", required=False, location="query",
                        description_en="Mode: all, trending, new7d, smart", description_ru="Режим: all, trending, new7d, smart", default="all"),
            ApiParameter(name="category", type="string", required=False, location="query",
                        description_en="Filter by category", description_ru="Фильтр по категории"),
            ApiParameter(name="page", type="integer", required=False, location="query", default=1),
            ApiParameter(name="limit", type="integer", required=False, location="query", default=20)
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Funding rounds with scores", description_ru="Раунды с оценками",
                       example={
                           "items": [{"project": {"name": "Project X"}, "fomo_score": {"score": 75}}]
                       })
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="funding_spotlight",
        path="/api/funding/spotlight",
        method=HttpMethod.GET,
        title_en="Funding Spotlight",
        title_ru="Топ инвестиции",
        description_en="Top spotlight cards - highest FOMO Score rounds from last 30 days. Featured investment opportunities.",
        description_ru="Топовые карточки - раунды с наивысшим FOMO Score за последние 30 дней. Рекомендуемые инвестиционные возможности.",
        category="funding",
        tags=["funding", "spotlight", "featured"],
        parameters=[
            ApiParameter(name="limit", type="integer", required=False, location="query", default=5)
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Top rounds", description_ru="Топовые раунды",
                       example={"items": [{"project": {"name": "Hot Project"}, "fomo_score": 85}]})
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="funding_stats",
        path="/api/funding/stats",
        method=HttpMethod.GET,
        title_en="Funding Statistics",
        title_ru="Статистика инвестиций",
        description_en="Global funding statistics including total raised, top categories, and market trends.",
        description_ru="Глобальная статистика инвестиций: общий объём, топ категории и рыночные тренды.",
        category="funding",
        tags=["funding", "stats", "analytics"],
        parameters=[],
        responses=[
            ApiResponse(status_code=200, description_en="Funding stats", description_ru="Статистика инвестиций",
                       example={"all_time": {"total_raised_usd": 50000000000}})
        ]
    ),
    
    # ───────────────────────────────────────────────────────────
    # FUNDS / VCs
    # ───────────────────────────────────────────────────────────
    
    ApiEndpoint(
        endpoint_id="funds_list_v2",
        path="/api/funds",
        method=HttpMethod.GET,
        title_en="Funds List",
        title_ru="Список фондов",
        description_en="List all venture capital funds with basic info, tier classification, and investment counts.",
        description_ru="Список всех венчурных фондов с базовой информацией, классификацией по уровню и количеством инвестиций.",
        category="funds",
        tags=["funds", "vc", "investors"],
        parameters=[
            ApiParameter(name="search", type="string", required=False, location="query"),
            ApiParameter(name="tier", type="string", required=False, location="query"),
            ApiParameter(name="page", type="integer", required=False, location="query", default=1),
            ApiParameter(name="limit", type="integer", required=False, location="query", default=20)
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Funds list", description_ru="Список фондов",
                       example={"items": [{"name": "a16z", "tier": "tier_1", "investments_count": 150}]})
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="fund_profile",
        path="/api/funds/{fundId}",
        method=HttpMethod.GET,
        title_en="Fund Profile",
        title_ru="Профиль фонда",
        description_en="Detailed fund profile with stats, categories, and investment summary.",
        description_ru="Детальный профиль фонда со статистикой, категориями и сводкой инвестиций.",
        category="funds",
        tags=["funds", "profile", "analytics"],
        parameters=[
            ApiParameter(name="fundId", type="string", required=True, location="path",
                        description_en="Fund ID or slug", description_ru="ID или slug фонда", example="a16z")
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Fund profile", description_ru="Профиль фонда",
                       example={"fund": {"name": "Andreessen Horowitz"}, "stats": {"investments_count": 150}})
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="fund_portfolio_v2",
        path="/api/funds/{fundId}/portfolio",
        method=HttpMethod.GET,
        title_en="Fund Portfolio",
        title_ru="Портфель фонда",
        description_en="Fund portfolio with investment details and ROI estimates. Shows all projects invested in with performance metrics.",
        description_ru="Портфель фонда с деталями инвестиций и оценками ROI. Показывает все проекты с метриками производительности.",
        category="funds",
        tags=["funds", "portfolio", "roi"],
        parameters=[
            ApiParameter(name="fundId", type="string", required=True, location="path"),
            ApiParameter(name="sort", type="string", required=False, location="query", default="date"),
            ApiParameter(name="limit", type="integer", required=False, location="query", default=50)
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Portfolio with ROI", description_ru="Портфель с ROI",
                       example={"summary": {"total_invested_usd": 500000000, "overall_multiple": 2.5}})
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="fund_dashboard",
        path="/api/funds/{fundId}/dashboard",
        method=HttpMethod.GET,
        title_en="Fund Dashboard",
        title_ru="Дашборд фонда",
        description_en="Fund dashboard with aggregated metrics: current value, PnL, top performers, and category distribution.",
        description_ru="Дашборд фонда с агрегированными метриками: текущая стоимость, PnL, лучшие активы и распределение по категориям.",
        category="funds",
        tags=["funds", "dashboard", "analytics"],
        parameters=[
            ApiParameter(name="fundId", type="string", required=True, location="path")
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Dashboard metrics", description_ru="Метрики дашборда",
                       example={"metrics": {"current_value_usd": 1000000000, "overall_multiple": 2.5}})
        ]
    ),
    
    # ───────────────────────────────────────────────────────────
    # PERSONS
    # ───────────────────────────────────────────────────────────
    
    ApiEndpoint(
        endpoint_id="persons_list_v2",
        path="/api/persons",
        method=HttpMethod.GET,
        title_en="Persons List",
        title_ru="Список персон",
        description_en="List all persons (founders, investors, team members) in the crypto ecosystem.",
        description_ru="Список всех персон (основатели, инвесторы, команда) в крипто-экосистеме.",
        category="persons",
        tags=["persons", "founders", "team"],
        parameters=[
            ApiParameter(name="search", type="string", required=False, location="query"),
            ApiParameter(name="role", type="string", required=False, location="query"),
            ApiParameter(name="page", type="integer", required=False, location="query", default=1),
            ApiParameter(name="limit", type="integer", required=False, location="query", default=20)
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Persons list", description_ru="Список персон",
                       example={"items": [{"name": "Vitalik Buterin", "role": "Founder"}]})
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="person_profile",
        path="/api/persons/{personId}",
        method=HttpMethod.GET,
        title_en="Person Profile",
        title_ru="Профиль персоны",
        description_en="Detailed person profile with bio, social links, and project associations.",
        description_ru="Детальный профиль персоны с биографией, соцсетями и связанными проектами.",
        category="persons",
        tags=["persons", "profile"],
        parameters=[
            ApiParameter(name="personId", type="string", required=True, location="path")
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Person profile", description_ru="Профиль персоны",
                       example={"person": {"name": "Satoshi"}, "stats": {"projects_count": 1}})
        ]
    ),
    
    # ───────────────────────────────────────────────────────────
    # ICO / ECHO
    # ───────────────────────────────────────────────────────────
    
    ApiEndpoint(
        endpoint_id="ico_projects",
        path="/api/ico/projects",
        method=HttpMethod.GET,
        title_en="ICO Projects",
        title_ru="ICO Проекты",
        description_en="List ICO/IEO/IDO projects with status (active, upcoming, ended), progress, and ROI data.",
        description_ru="Список проектов ICO/IEO/IDO со статусом (активные, предстоящие, завершённые), прогрессом и данными ROI.",
        category="ico",
        tags=["ico", "ieo", "ido", "token_sale"],
        parameters=[
            ApiParameter(name="status", type="string", required=False, location="query", default="all"),
            ApiParameter(name="category", type="string", required=False, location="query"),
            ApiParameter(name="page", type="integer", required=False, location="query", default=1),
            ApiParameter(name="limit", type="integer", required=False, location="query", default=20)
        ],
        responses=[
            ApiResponse(status_code=200, description_en="ICO projects", description_ru="ICO проекты",
                       example={"items": [{"project": {"name": "New Token"}, "sale": {"status": "upcoming"}}]})
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="ico_stats",
        path="/api/ico/stats",
        method=HttpMethod.GET,
        title_en="ICO Statistics",
        title_ru="Статистика ICO",
        description_en="Global ICO market statistics including active projects, total raised, and trending categories.",
        description_ru="Глобальная статистика рынка ICO: активные проекты, общий объём и трендовые категории.",
        category="ico",
        tags=["ico", "stats", "analytics"],
        parameters=[],
        responses=[
            ApiResponse(status_code=200, description_en="ICO stats", description_ru="Статистика ICO",
                       example={"overview": {"total_projects": 500, "active": 25}})
        ]
    ),
    
    # ───────────────────────────────────────────────────────────
    # PROJECTS
    # ───────────────────────────────────────────────────────────
    
    ApiEndpoint(
        endpoint_id="projects_list_v2",
        path="/api/projects",
        method=HttpMethod.GET,
        title_en="Projects List",
        title_ru="Список проектов",
        description_en="List all crypto projects with basic info, category, and market data.",
        description_ru="Список всех крипто-проектов с базовой информацией, категорией и рыночными данными.",
        category="projects",
        tags=["projects", "list"],
        parameters=[
            ApiParameter(name="search", type="string", required=False, location="query"),
            ApiParameter(name="category", type="string", required=False, location="query"),
            ApiParameter(name="page", type="integer", required=False, location="query", default=1),
            ApiParameter(name="limit", type="integer", required=False, location="query", default=20)
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Projects list", description_ru="Список проектов",
                       example={"items": [{"name": "Ethereum", "symbol": "ETH", "category": "l1"}]})
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="project_profile",
        path="/api/projects/{projectId}/profile",
        method=HttpMethod.GET,
        title_en="Project Profile",
        title_ru="Профиль проекта",
        description_en="Comprehensive project profile with market data, funding summary, and metadata.",
        description_ru="Полный профиль проекта с рыночными данными, сводкой инвестиций и метаданными.",
        category="projects",
        tags=["projects", "profile", "market"],
        parameters=[
            ApiParameter(name="projectId", type="string", required=True, location="path")
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Project profile", description_ru="Профиль проекта",
                       example={"project": {"name": "Bitcoin"}, "market": {"price": 65000}})
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="project_investors_v2",
        path="/api/projects/{projectId}/investors",
        method=HttpMethod.GET,
        title_en="Project Investors",
        title_ru="Инвесторы проекта",
        description_en="Get all investors who funded this project with their participation details.",
        description_ru="Получить всех инвесторов проекта с деталями их участия.",
        category="projects",
        tags=["projects", "investors"],
        parameters=[
            ApiParameter(name="projectId", type="string", required=True, location="path")
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Project investors", description_ru="Инвесторы проекта",
                       example={"investors": [{"name": "a16z", "is_lead": True}]})
        ]
    ),
    
    # ───────────────────────────────────────────────────────────
    # CUSTOM INDICATORS
    # ───────────────────────────────────────────────────────────
    
    ApiEndpoint(
        endpoint_id="indicator_momentum",
        path="/api/indicators/momentum",
        method=HttpMethod.GET,
        title_en="Momentum Heat",
        title_ru="Моментум Heat",
        description_en="Momentum Heat indicator - finds assets with price acceleration confirmed by volume. Top 5 momentum leaders.",
        description_ru="Индикатор Momentum Heat - находит активы с ускорением цены, подтверждённым объёмом. Топ-5 лидеров моментума.",
        category="indicators",
        tags=["indicators", "momentum", "signals"],
        parameters=[
            ApiParameter(name="window", type="string", required=False, location="query", default="24h"),
            ApiParameter(name="limit", type="integer", required=False, location="query", default=5)
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Momentum leaders", description_ru="Лидеры моментума",
                       example={"items": [{"symbol": "BTC", "score": 85}]})
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="indicator_accumulation",
        path="/api/indicators/accumulation",
        method=HttpMethod.GET,
        title_en="Accumulation Score",
        title_ru="Скор аккумуляции",
        description_en="Accumulation Score - finds assets being quietly accumulated without price spike. Detects smart money activity.",
        description_ru="Скор аккумуляции - находит активы в тихой аккумуляции без скачка цены. Детектор активности умных денег.",
        category="indicators",
        tags=["indicators", "accumulation", "smart_money"],
        parameters=[
            ApiParameter(name="window", type="string", required=False, location="query", default="7d"),
            ApiParameter(name="limit", type="integer", required=False, location="query", default=5)
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Accumulation candidates", description_ru="Кандидаты на аккумуляцию",
                       example={"items": [{"symbol": "ETH", "score": 72}]})
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="indicator_liquidations",
        path="/api/indicators/liquidations",
        method=HttpMethod.GET,
        title_en="Liquidation Pressure",
        title_ru="Давление ликвидаций",
        description_en="Liquidation Pressure indicator - where positions are being liquidated. Detects squeeze signals.",
        description_ru="Индикатор давления ликвидаций - где ликвидируются позиции. Детектор сигналов сжатия.",
        category="indicators",
        tags=["indicators", "liquidations", "squeeze"],
        parameters=[
            ApiParameter(name="window", type="string", required=False, location="query", default="24h"),
            ApiParameter(name="limit", type="integer", required=False, location="query", default=5)
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Liquidation hotspots", description_ru="Горячие точки ликвидаций",
                       example={"items": [{"symbol": "BTC", "score": 65, "skew_direction": "short_squeeze"}]})
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="indicator_funding_stress",
        path="/api/indicators/funding-stress",
        method=HttpMethod.GET,
        title_en="Funding Stress",
        title_ru="Стресс фандинга",
        description_en="Funding Stress indicator - overheated markets prone to squeeze. High funding + growing OI + stalling price.",
        description_ru="Индикатор стресса фандинга - перегретые рынки со склонностью к сжатию. Высокий фандинг + растущий OI + застой цены.",
        category="indicators",
        tags=["indicators", "funding", "squeeze"],
        parameters=[
            ApiParameter(name="window", type="string", required=False, location="query", default="24h"),
            ApiParameter(name="limit", type="integer", required=False, location="query", default=5)
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Funding stress hotspots", description_ru="Горячие точки стресса",
                       example={"items": [{"symbol": "ETH", "direction": "long_heavy", "squeeze_risk": "high"}]})
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="indicator_oi_shock",
        path="/api/indicators/oi-shock",
        method=HttpMethod.GET,
        title_en="OI Shock",
        title_ru="OI Шок",
        description_en="Open Interest Shock - sudden influx of leveraged positions. Often precedes big moves.",
        description_ru="OI Шок - резкий приток плечевых позиций. Часто предшествует большим движениям.",
        category="indicators",
        tags=["indicators", "oi", "leverage"],
        parameters=[
            ApiParameter(name="window", type="string", required=False, location="query", default="4h"),
            ApiParameter(name="limit", type="integer", required=False, location="query", default=5)
        ],
        responses=[
            ApiResponse(status_code=200, description_en="OI shock alerts", description_ru="Алерты OI шока",
                       example={"items": [{"symbol": "SOL", "score": 78, "direction": "bullish_leverage"}]})
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="indicator_exchange_hot",
        path="/api/indicators/exchange-hot/{exchange}",
        method=HttpMethod.GET,
        title_en="Exchange Hot Tokens",
        title_ru="Горячие токены биржи",
        description_en="Exchange Alpha Hotlist - top assets on specific exchange by volume and momentum.",
        description_ru="Горячий список биржи - топ активы на конкретной бирже по объёму и моментуму.",
        category="indicators",
        tags=["indicators", "exchange", "hot"],
        parameters=[
            ApiParameter(name="exchange", type="string", required=True, location="path",
                        description_en="Exchange name", description_ru="Название биржи", example="binance"),
            ApiParameter(name="window", type="string", required=False, location="query", default="24h"),
            ApiParameter(name="limit", type="integer", required=False, location="query", default=5)
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Hot tokens on exchange", description_ru="Горячие токены биржи",
                       example={"items": [{"symbol": "PEPE", "score": 88, "volume_24h": 500000000}]})
        ]
    ),
] + NEW_ENDPOINTS_DOCUMENTATION  # Add new endpoints


class ApiDocumentationRegistry:
    """
    Manages API documentation in MongoDB.
    
    Provides:
    - Store/retrieve structured documentation
    - Bilingual support (EN/RU)
    - Search by category/tag
    """
    
    def __init__(self, db=None):
        self.db = db
        self.collection_name = "intel_docs"
    
    async def seed_documentation(self) -> Dict[str, Any]:
        """
        Seed database with API documentation.
        Uses upsert to avoid duplicate key errors.
        """
        if self.db is None:
            return {"error": "No database connection"}
        
        collection = self.db[self.collection_name]
        
        # Clear existing
        await collection.delete_many({})
        
        # Deduplicate by endpoint_id (later definition wins)
        endpoint_map = {}
        now = datetime.now(timezone.utc).isoformat()
        
        for endpoint in API_DOCUMENTATION + NEW_ENDPOINTS_DOCUMENTATION:
            doc = {
                "endpoint_id": endpoint.endpoint_id,
                "path": endpoint.path,
                "method": endpoint.method.value,
                "title_en": endpoint.title_en,
                "title_ru": endpoint.title_ru,
                "description_en": endpoint.description_en,
                "description_ru": endpoint.description_ru,
                "category": endpoint.category,
                "tags": endpoint.tags,
                "parameters": [
                    {
                        "name": p.name,
                        "type": p.type,
                        "required": p.required,
                        "location": p.location,
                        "description_en": p.description_en,
                        "description_ru": p.description_ru,
                        "default": p.default,
                        "example": p.example,
                        "enum": p.enum
                    }
                    for p in endpoint.parameters
                ],
                "request_body": endpoint.request_body,
                "request_example": endpoint.request_example,
                "responses": [
                    {
                        "status_code": r.status_code,
                        "description_en": r.description_en,
                        "description_ru": r.description_ru,
                        "example": r.example
                    }
                    for r in endpoint.responses
                ],
                "curl_example": endpoint.curl_example,
                "version": endpoint.version,
                "deprecated": endpoint.deprecated,
                "auth_required": endpoint.auth_required,
                "rate_limit": endpoint.rate_limit,
                "created_at": now,
                "updated_at": now
            }
            # Use endpoint_id as key to deduplicate
            endpoint_map[endpoint.endpoint_id] = doc
        
        docs = list(endpoint_map.values())
        
        if docs:
            await collection.insert_many(docs)
        
        # Create indexes
        await collection.create_index("endpoint_id", unique=True)
        await collection.create_index("category")
        await collection.create_index("tags")
        await collection.create_index("method")
        
        return {
            "seeded": len(docs),
            "categories": list(set(e.category for e in API_DOCUMENTATION + NEW_ENDPOINTS_DOCUMENTATION)),
            "methods": list(set(e.method.value for e in API_DOCUMENTATION + NEW_ENDPOINTS_DOCUMENTATION))
        }
    
    async def get_all(self, lang: str = "en") -> List[Dict]:
        """Get all documentation"""
        if self.db is None:
            return self._get_from_memory(lang)
        
        cursor = self.db[self.collection_name].find({}, {"_id": 0})
        docs = await cursor.to_list(500)  # Increased from 100 to 500
        return self._localize(docs, lang)
    
    async def get_by_category(self, category: str, lang: str = "en") -> List[Dict]:
        """Get documentation by category"""
        if self.db is None:
            return [
                self._localize_single(e, lang)
                for e in API_DOCUMENTATION
                if e.category == category
            ]
        
        cursor = self.db[self.collection_name].find(
            {"category": category},
            {"_id": 0}
        )
        docs = await cursor.to_list(50)
        return self._localize(docs, lang)
    
    async def get_by_endpoint(self, endpoint_id: str, lang: str = "en") -> Optional[Dict]:
        """Get single endpoint documentation"""
        if self.db is None:
            for e in API_DOCUMENTATION:
                if e.endpoint_id == endpoint_id:
                    return self._localize_single(e, lang)
            return None
        
        doc = await self.db[self.collection_name].find_one(
            {"endpoint_id": endpoint_id},
            {"_id": 0}
        )
        return self._localize_single(doc, lang) if doc else None
    
    async def search(self, query: str, lang: str = "en") -> List[Dict]:
        """Search documentation"""
        if self.db is None:
            q = query.lower()
            results = []
            for e in API_DOCUMENTATION:
                if (q in e.title_en.lower() or q in e.title_ru.lower() or
                    q in e.description_en.lower() or q in e.path.lower() or
                    any(q in tag for tag in e.tags)):
                    results.append(self._localize_single(e, lang))
            return results
        
        cursor = self.db[self.collection_name].find(
            {
                "$or": [
                    {"title_en": {"$regex": query, "$options": "i"}},
                    {"title_ru": {"$regex": query, "$options": "i"}},
                    {"description_en": {"$regex": query, "$options": "i"}},
                    {"path": {"$regex": query, "$options": "i"}},
                    {"tags": {"$regex": query, "$options": "i"}}
                ]
            },
            {"_id": 0}
        )
        docs = await cursor.to_list(50)
        return self._localize(docs, lang)
    
    def _get_from_memory(self, lang: str) -> List[Dict]:
        """Get documentation from memory (fallback)"""
        return [self._localize_single(e, lang) for e in API_DOCUMENTATION]
    
    def _localize(self, docs: List[Dict], lang: str) -> List[Dict]:
        """Localize list of documents"""
        return [self._localize_single(d, lang) for d in docs]
    
    def _localize_single(self, doc: Any, lang: str) -> Dict:
        """Localize single document"""
        if isinstance(doc, ApiEndpoint):
            doc = {
                "endpoint_id": doc.endpoint_id,
                "path": doc.path,
                "method": doc.method.value,
                "title_en": doc.title_en,
                "title_ru": doc.title_ru,
                "description_en": doc.description_en,
                "description_ru": doc.description_ru,
                "category": doc.category,
                "tags": doc.tags,
                "parameters": [
                    {
                        "name": p.name,
                        "type": p.type,
                        "required": p.required,
                        "location": p.location,
                        "description_en": p.description_en,
                        "description_ru": p.description_ru,
                        "default": p.default,
                        "example": p.example
                    }
                    for p in doc.parameters
                ],
                "responses": [
                    {
                        "status_code": r.status_code,
                        "description_en": r.description_en,
                        "description_ru": r.description_ru,
                        "example": r.example
                    }
                    for r in doc.responses
                ]
            }
        
        if not doc:
            return doc
        
        # Select language-specific fields
        title_key = f"title_{lang}" if f"title_{lang}" in doc else "title_en"
        desc_key = f"description_{lang}" if f"description_{lang}" in doc else "description_en"
        
        result = {
            "endpoint_id": doc.get("endpoint_id"),
            "path": doc.get("path"),
            "method": doc.get("method"),
            "title": doc.get(title_key, doc.get("title_en")),
            "description": doc.get(desc_key, doc.get("description_en")),
            "category": doc.get("category"),
            "tags": doc.get("tags", []),
            "parameters": [],
            "responses": [],
            "curl_example": doc.get("curl_example")
        }
        
        # Localize parameters
        for p in doc.get("parameters", []):
            p_desc_key = f"description_{lang}" if f"description_{lang}" in p else "description_en"
            result["parameters"].append({
                "name": p.get("name"),
                "type": p.get("type"),
                "required": p.get("required"),
                "location": p.get("location"),
                "description": p.get(p_desc_key, p.get("description_en")),
                "default": p.get("default"),
                "example": p.get("example")
            })
        
        # Localize responses
        for r in doc.get("responses", []):
            r_desc_key = f"description_{lang}" if f"description_{lang}" in r else "description_en"
            result["responses"].append({
                "status_code": r.get("status_code"),
                "description": r.get(r_desc_key, r.get("description_en")),
                "example": r.get("example")
            })
        
        return result


# Singleton
_registry: Optional[ApiDocumentationRegistry] = None


def init_api_registry(db):
    """Initialize API documentation registry"""
    global _registry
    _registry = ApiDocumentationRegistry(db)
    return _registry


def get_api_registry():
    """Get API documentation registry"""
    return _registry
