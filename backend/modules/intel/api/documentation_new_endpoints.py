"""
API Documentation - New Endpoints
==================================
Activities, Intel Feed, Projects Extended, Unlocks Calendar
"""

from .documentation_registry import ApiEndpoint, ApiParameter, ApiResponse, HttpMethod

# ═══════════════════════════════════════════════════════════════
# CRYPTO ACTIVITIES API
# ═══════════════════════════════════════════════════════════════

ACTIVITIES_DOCUMENTATION = [
    ApiEndpoint(
        endpoint_id="activities_list",
        path="/api/activities",
        method=HttpMethod.GET,
        title_en="List Crypto Activities",
        title_ru="Список криптоактивностей",
        description_en="Get all crypto activities with filters. Includes airdrops, campaigns, testnets, listings, launches.",
        description_ru="Получить все криптоактивности с фильтрами. Включает airdrop'ы, кампании, тестнеты, листинги, запуски.",
        category="activities",
        tags=["activities", "airdrops", "campaigns", "testnets"],
        parameters=[
            ApiParameter(name="category", type="string", required=False, description_en="Filter by category: launch, campaign, exchange, ecosystem, community, development", description_ru="Фильтр по категории"),
            ApiParameter(name="type", type="string", required=False, description_en="Filter by type: airdrop, launchpool, testnet, points_program, listing", description_ru="Фильтр по типу"),
            ApiParameter(name="status", type="string", required=False, description_en="Filter: upcoming, active, ended", description_ru="Статус: upcoming, active, ended"),
            ApiParameter(name="project", type="string", required=False, description_en="Filter by project ID/name", description_ru="Фильтр по проекту"),
            ApiParameter(name="chain", type="string", required=False, description_en="Filter by blockchain", description_ru="Фильтр по блокчейну"),
            ApiParameter(name="page", type="integer", required=False, default=1, description_en="Page number", description_ru="Номер страницы"),
            ApiParameter(name="limit", type="integer", required=False, default=20, description_en="Items per page", description_ru="Элементов на странице"),
        ],
        responses=[
            ApiResponse(status_code=200, description_en="List of activities", description_ru="Список активностей",
                       example={"ts": 1234567890, "total": 10, "items": [{"id": "...", "title": "LayerZero Airdrop", "type": "airdrop", "score": 85}]})
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="activities_active",
        path="/api/activities/active",
        method=HttpMethod.GET,
        title_en="Active Activities",
        title_ru="Активные активности",
        description_en="Get currently active activities (started, not ended yet).",
        description_ru="Получить текущие активные активности (начавшиеся, не завершённые).",
        category="activities",
        tags=["activities", "active"],
        parameters=[
            ApiParameter(name="category", type="string", required=False, description_en="Filter by category", description_ru="Фильтр по категории"),
            ApiParameter(name="limit", type="integer", required=False, default=50, description_en="Limit results", description_ru="Лимит результатов"),
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Active activities", description_ru="Активные активности")
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="activities_upcoming",
        path="/api/activities/upcoming",
        method=HttpMethod.GET,
        title_en="Upcoming Activities",
        title_ru="Предстоящие активности",
        description_en="Get upcoming activities (not yet started).",
        description_ru="Получить предстоящие активности (ещё не начавшиеся).",
        category="activities",
        tags=["activities", "upcoming"],
        parameters=[
            ApiParameter(name="days", type="integer", required=False, default=30, description_en="Days ahead (1-90)", description_ru="Дней вперёд"),
            ApiParameter(name="category", type="string", required=False, description_en="Filter by category", description_ru="Фильтр по категории"),
            ApiParameter(name="limit", type="integer", required=False, default=50, description_en="Limit results", description_ru="Лимит результатов"),
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Upcoming activities", description_ru="Предстоящие активности")
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="activities_trending",
        path="/api/activities/trending",
        method=HttpMethod.GET,
        title_en="Trending Activities",
        title_ru="Трендовые активности",
        description_en="Get trending activities by score and engagement.",
        description_ru="Получить трендовые активности по рейтингу и вовлечённости.",
        category="activities",
        tags=["activities", "trending"],
        parameters=[
            ApiParameter(name="period", type="string", required=False, default="week", description_en="Period: day, week, month", description_ru="Период: day, week, month"),
            ApiParameter(name="limit", type="integer", required=False, default=20, description_en="Limit results", description_ru="Лимит результатов"),
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Trending activities ranked by score", description_ru="Трендовые активности по рейтингу")
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="activities_campaigns",
        path="/api/activities/campaigns",
        method=HttpMethod.GET,
        title_en="Active Campaigns",
        title_ru="Активные кампании",
        description_en="Get active campaigns: airdrops, points programs, quests, testnets.",
        description_ru="Получить активные кампании: airdrop'ы, программы поинтов, квесты, тестнеты.",
        category="activities",
        tags=["campaigns", "airdrops", "points", "quests"],
        parameters=[
            ApiParameter(name="type", type="string", required=False, description_en="Filter: airdrop, points_program, quest, testnet", description_ru="Тип кампании"),
            ApiParameter(name="status", type="string", required=False, default="active", description_en="Status: active, upcoming, all", description_ru="Статус"),
            ApiParameter(name="chain", type="string", required=False, description_en="Filter by blockchain", description_ru="Фильтр по блокчейну"),
            ApiParameter(name="difficulty", type="string", required=False, description_en="Filter: easy, medium, hard", description_ru="Сложность"),
            ApiParameter(name="limit", type="integer", required=False, default=50, description_en="Limit results", description_ru="Лимит"),
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Active campaigns with rewards and difficulty", description_ru="Активные кампании с наградами и сложностью")
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="activities_project",
        path="/api/activities/project/{project_id}",
        method=HttpMethod.GET,
        title_en="Project Activities",
        title_ru="Активности проекта",
        description_en="Get all activities for a specific project.",
        description_ru="Получить все активности для конкретного проекта.",
        category="activities",
        tags=["activities", "project"],
        parameters=[
            ApiParameter(name="project_id", type="string", location="path", required=True, description_en="Project ID or slug", description_ru="ID или slug проекта"),
            ApiParameter(name="status", type="string", required=False, description_en="Filter: active, upcoming, ended", description_ru="Статус"),
            ApiParameter(name="limit", type="integer", required=False, default=20, description_en="Limit results", description_ru="Лимит"),
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Project activities", description_ru="Активности проекта")
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="activities_detail",
        path="/api/activities/{activity_id}",
        method=HttpMethod.GET,
        title_en="Activity Detail",
        title_ru="Детали активности",
        description_en="Get detailed information about a specific activity.",
        description_ru="Получить детальную информацию об активности.",
        category="activities",
        tags=["activities", "detail"],
        parameters=[
            ApiParameter(name="activity_id", type="string", location="path", required=True, description_en="Activity ID", description_ru="ID активности"),
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Activity details", description_ru="Детали активности"),
            ApiResponse(status_code=404, description_en="Activity not found", description_ru="Активность не найдена")
        ]
    ),
]


# ═══════════════════════════════════════════════════════════════
# INTEL FEED API
# ═══════════════════════════════════════════════════════════════

INTEL_FEED_DOCUMENTATION = [
    ApiEndpoint(
        endpoint_id="intel_feed_main",
        path="/api/intel-feed",
        method=HttpMethod.GET,
        title_en="Intel Feed - Unified Event Stream",
        title_ru="Intel Feed - Единый поток событий",
        description_en="Get unified intel feed combining funding rounds, activities, unlocks, news, listings, and launches.",
        description_ru="Получить единый поток событий: раунды финансирования, активности, анлоки, новости, листинги, запуски.",
        category="feed",
        tags=["feed", "intel", "unified", "funding", "activities", "unlocks"],
        parameters=[
            ApiParameter(name="types", type="string", required=False, description_en="Filter types (comma-sep): funding,activity,unlock,news,listing,launch", description_ru="Типы событий"),
            ApiParameter(name="project", type="string", required=False, description_en="Filter by project", description_ru="Фильтр по проекту"),
            ApiParameter(name="investor", type="string", required=False, description_en="Filter by investor", description_ru="Фильтр по инвестору"),
            ApiParameter(name="importance", type="string", required=False, description_en="Filter: high, medium, low", description_ru="Важность"),
            ApiParameter(name="page", type="integer", required=False, default=1, description_en="Page number", description_ru="Номер страницы"),
            ApiParameter(name="limit", type="integer", required=False, default=30, description_en="Items per page", description_ru="Элементов на странице"),
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Unified intel feed with all event types", description_ru="Единый поток событий всех типов",
                       example={"ts": 1234567890, "total": 50, "types_available": ["funding", "activity", "unlock"], "items": []})
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="intel_feed_trending",
        path="/api/intel-feed/trending",
        method=HttpMethod.GET,
        title_en="Trending Intel Events",
        title_ru="Трендовые события",
        description_en="Get trending intel events by score and recency.",
        description_ru="Получить трендовые события по рейтингу и актуальности.",
        category="feed",
        tags=["feed", "trending"],
        parameters=[
            ApiParameter(name="period", type="string", required=False, default="day", description_en="Period: day, week, month", description_ru="Период"),
            ApiParameter(name="limit", type="integer", required=False, default=20, description_en="Limit results", description_ru="Лимит"),
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Trending events", description_ru="Трендовые события")
        ]
    ),
]


# ═══════════════════════════════════════════════════════════════
# PROJECTS EXTENDED API
# ═══════════════════════════════════════════════════════════════

PROJECTS_EXTENDED_DOCUMENTATION = [
    ApiEndpoint(
        endpoint_id="project_about",
        path="/api/projects/{project_id}/about",
        method=HttpMethod.GET,
        title_en="Project About",
        title_ru="О проекте",
        description_en="Get project about information: description, technology, consensus, whitepaper.",
        description_ru="Получить информацию о проекте: описание, технология, консенсус, whitepaper.",
        category="projects",
        tags=["projects", "about", "profile"],
        parameters=[
            ApiParameter(name="project_id", type="string", location="path", required=True, description_en="Project ID, slug, or symbol", description_ru="ID, slug или символ проекта"),
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Project about information", description_ru="Информация о проекте"),
            ApiResponse(status_code=404, description_en="Project not found", description_ru="Проект не найден")
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="project_links",
        path="/api/projects/{project_id}/links",
        method=HttpMethod.GET,
        title_en="Project Official Links",
        title_ru="Официальные ссылки проекта",
        description_en="Get project official links: website, Twitter, Discord, GitHub, Telegram, etc.",
        description_ru="Получить официальные ссылки проекта: сайт, Twitter, Discord, GitHub, Telegram и т.д.",
        category="projects",
        tags=["projects", "links", "social"],
        parameters=[
            ApiParameter(name="project_id", type="string", location="path", required=True, description_en="Project ID, slug, or symbol", description_ru="ID, slug или символ проекта"),
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Project official links", description_ru="Официальные ссылки проекта",
                       example={"links": {"website": "https://...", "twitter": "https://twitter.com/...", "discord": "https://discord.gg/..."}})
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="project_explorers",
        path="/api/projects/{project_id}/explorers",
        method=HttpMethod.GET,
        title_en="Project Blockchain Explorers",
        title_ru="Обозреватели блокчейна проекта",
        description_en="Get blockchain explorers for project: Etherscan, Solscan, etc.",
        description_ru="Получить обозреватели блокчейна проекта: Etherscan, Solscan и т.д.",
        category="projects",
        tags=["projects", "explorers", "blockchain"],
        parameters=[
            ApiParameter(name="project_id", type="string", location="path", required=True, description_en="Project ID, slug, or symbol", description_ru="ID, slug или символ проекта"),
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Blockchain explorers list", description_ru="Список обозревателей блокчейна",
                       example={"explorers": [{"name": "Etherscan", "chain": "Ethereum", "url": "https://etherscan.io"}]})
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="project_bridges",
        path="/api/projects/{project_id}/bridges",
        method=HttpMethod.GET,
        title_en="Project Cross-Chain Bridges",
        title_ru="Мосты проекта",
        description_en="Get cross-chain bridges for project token.",
        description_ru="Получить кросс-чейн мосты для токена проекта.",
        category="projects",
        tags=["projects", "bridges", "cross-chain"],
        parameters=[
            ApiParameter(name="project_id", type="string", location="path", required=True, description_en="Project ID, slug, or symbol", description_ru="ID, slug или символ проекта"),
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Cross-chain bridges list", description_ru="Список мостов",
                       example={"bridges": [{"bridge_name": "Arbitrum Bridge", "from_chain": "Ethereum", "to_chain": "Arbitrum"}]})
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="project_activities_v2",
        path="/api/projects/{project_id}/activities",
        method=HttpMethod.GET,
        title_en="Project Activities",
        title_ru="Активности проекта",
        description_en="Get all activities (airdrops, campaigns, etc.) for a project.",
        description_ru="Получить все активности (airdrop'ы, кампании) для проекта.",
        category="projects",
        tags=["projects", "activities"],
        parameters=[
            ApiParameter(name="project_id", type="string", location="path", required=True, description_en="Project ID", description_ru="ID проекта"),
            ApiParameter(name="status", type="string", required=False, description_en="Filter: active, upcoming, ended", description_ru="Статус"),
            ApiParameter(name="type", type="string", required=False, description_en="Activity type filter", description_ru="Тип активности"),
            ApiParameter(name="limit", type="integer", required=False, default=20, description_en="Limit results", description_ru="Лимит"),
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Project activities", description_ru="Активности проекта")
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="project_unlocks_v2",
        path="/api/projects/{project_id}/unlocks",
        method=HttpMethod.GET,
        title_en="Project Token Unlocks",
        title_ru="Анлоки токенов проекта",
        description_en="Get all token unlocks for a project.",
        description_ru="Получить все анлоки токенов для проекта.",
        category="projects",
        tags=["projects", "unlocks", "tokenomics"],
        parameters=[
            ApiParameter(name="project_id", type="string", location="path", required=True, description_en="Project ID", description_ru="ID проекта"),
            ApiParameter(name="include_past", type="boolean", required=False, default=False, description_en="Include past unlocks", description_ru="Включить прошлые анлоки"),
            ApiParameter(name="limit", type="integer", required=False, default=50, description_en="Limit results", description_ru="Лимит"),
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Token unlock schedule", description_ru="Расписание анлоков токенов")
        ]
    ),
]


# ═══════════════════════════════════════════════════════════════
# UNLOCKS EXTENDED API
# ═══════════════════════════════════════════════════════════════

UNLOCKS_EXTENDED_DOCUMENTATION = [
    ApiEndpoint(
        endpoint_id="unlocks_calendar",
        path="/api/unlocks/calendar",
        method=HttpMethod.GET,
        title_en="Token Unlocks Calendar",
        title_ru="Календарь анлоков",
        description_en="Get token unlocks calendar view grouped by date.",
        description_ru="Получить календарный вид анлоков токенов, сгруппированный по дате.",
        category="unlocks",
        tags=["unlocks", "calendar", "schedule"],
        parameters=[
            ApiParameter(name="year", type="integer", required=False, description_en="Year filter (default: current)", description_ru="Год"),
            ApiParameter(name="month", type="integer", required=False, description_en="Month filter 1-12 (default: current)", description_ru="Месяц 1-12"),
            ApiParameter(name="min_percent", type="number", required=False, description_en="Minimum % of supply", description_ru="Минимальный % supply"),
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Calendar with unlocks grouped by date", description_ru="Календарь с анлоками по датам",
                       example={"year": 2026, "month": 3, "days_with_unlocks": 5, "calendar": [{"date": "2026-03-15", "unlock_count": 2, "unlocks": []}]})
        ]
    ),
]


# ═══════════════════════════════════════════════════════════════
# NEWS INTELLIGENCE HEALTH MONITORING API
# ═══════════════════════════════════════════════════════════════

NEWS_HEALTH_DOCUMENTATION = [
    ApiEndpoint(
        endpoint_id="news-health-sources",
        path="/api/news-intelligence/health/sources",
        method=HttpMethod.GET,
        title_en="Get Sources Health Metrics",
        title_ru="Получить метрики здоровья источников",
        description_en="Get detailed health metrics for all news sources including fetch success rate, validation rate, parser drift detection, and sandbox statistics.",
        description_ru="Получить детальные метрики здоровья всех новостных источников, включая успешность запросов, валидацию, обнаружение дрифта парсера и статистику sandbox.",
        category="news_intelligence",
        tags=["health", "monitoring", "sources", "sandbox"],
        responses=[
            ApiResponse(
                status_code=200,
                description_en="Health metrics for all sources",
                description_ru="Метрики здоровья всех источников",
                example={
                    "ok": True,
                    "sources": [{"source_id": "coindesk", "health_score": 0.98, "status": "active"}],
                    "summary": {"total_sources": 20, "active": 15, "paused": 1}
                }
            )
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="news-health-summary",
        path="/api/news-intelligence/health/summary",
        method=HttpMethod.GET,
        title_en="Get Health Summary",
        title_ru="Получить сводку здоровья",
        description_en="Get summarized health status of the news intelligence system.",
        description_ru="Получить сводную информацию о здоровье системы новостной аналитики.",
        category="news_intelligence",
        tags=["health", "monitoring"],
        responses=[
            ApiResponse(status_code=200, description_en="Health summary", description_ru="Сводка здоровья")
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="news-health-unpause",
        path="/api/news-intelligence/health/unpause/{source_id}",
        method=HttpMethod.POST,
        title_en="Unpause Source",
        title_ru="Возобновить источник",
        description_en="Manually unpause a paused news source.",
        description_ru="Вручную возобновить приостановленный новостной источник.",
        category="news_intelligence",
        tags=["health", "admin"],
        parameters=[
            ApiParameter(name="source_id", type="string", required=True, location="path", description_en="Source ID", description_ru="ID источника")
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="news-breaking",
        path="/api/news-intelligence/breaking",
        method=HttpMethod.GET,
        title_en="Get Breaking News",
        title_ru="Получить срочные новости",
        description_en="Get latest breaking/developing news events with high importance.",
        description_ru="Получить последние срочные новостные события с высокой важностью.",
        category="news_intelligence",
        tags=["news", "breaking"],
        parameters=[
            ApiParameter(name="limit", type="integer", required=False, default=5, description_en="Max events", description_ru="Макс. событий")
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="news-events-by-asset",
        path="/api/news-intelligence/assets/{symbol}",
        method=HttpMethod.GET,
        title_en="Get Events by Asset",
        title_ru="Получить события по активу",
        description_en="Get news events related to a specific cryptocurrency asset.",
        description_ru="Получить новостные события по криптоактиву.",
        category="news_intelligence",
        tags=["news", "assets"],
        parameters=[
            ApiParameter(name="symbol", type="string", required=True, location="path", description_en="Asset symbol (BTC, ETH)", description_ru="Символ актива")
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="news-pipeline-fetch",
        path="/api/news-intelligence/pipeline/fetch",
        method=HttpMethod.POST,
        title_en="Run Fetch Pipeline",
        title_ru="Запустить пайплайн получения",
        description_en="Run fetch stage with sandbox isolation and validation.",
        description_ru="Запустить этап получения с изоляцией sandbox и валидацией.",
        category="news_intelligence",
        tags=["pipeline", "admin"]
    ),
    
    ApiEndpoint(
        endpoint_id="news-pipeline-process",
        path="/api/news-intelligence/pipeline/process",
        method=HttpMethod.POST,
        title_en="Run Process Pipeline",
        title_ru="Запустить пайплайн обработки",
        description_en="Run processing stages (normalize, embed, cluster).",
        description_ru="Запустить этапы обработки (нормализация, эмбеддинг, кластеризация).",
        category="news_intelligence",
        tags=["pipeline", "admin"]
    ),
    
    ApiEndpoint(
        endpoint_id="news-pipeline-synthesize",
        path="/api/news-intelligence/pipeline/synthesize",
        method=HttpMethod.POST,
        title_en="Run Synthesis Pipeline",
        title_ru="Запустить пайплайн синтеза",
        description_en="Run AI synthesis for confirmed events.",
        description_ru="Запустить AI синтез для подтвержденных событий.",
        category="news_intelligence",
        tags=["pipeline", "admin", "ai"]
    ),
    
    ApiEndpoint(
        endpoint_id="news-pipeline-merge",
        path="/api/news-intelligence/pipeline/merge",
        method=HttpMethod.POST,
        title_en="Run Event Merge",
        title_ru="Запустить слияние событий",
        description_en="Merge similar events to reduce duplicates.",
        description_ru="Объединить похожие события.",
        category="news_intelligence",
        tags=["pipeline", "admin"]
    ),
    
    ApiEndpoint(
        endpoint_id="news-scheduler-start",
        path="/api/news-intelligence/scheduler/start",
        method=HttpMethod.POST,
        title_en="Start Scheduler",
        title_ru="Запустить планировщик",
        description_en="Start the background news intelligence scheduler.",
        description_ru="Запустить фоновый планировщик.",
        category="news_intelligence",
        tags=["scheduler", "admin"]
    ),
    
    ApiEndpoint(
        endpoint_id="news-scheduler-stop",
        path="/api/news-intelligence/scheduler/stop",
        method=HttpMethod.POST,
        title_en="Stop Scheduler",
        title_ru="Остановить планировщик",
        description_en="Stop the background scheduler.",
        description_ru="Остановить планировщик.",
        category="news_intelligence",
        tags=["scheduler", "admin"]
    ),
    
    ApiEndpoint(
        endpoint_id="news-scheduler-status",
        path="/api/news-intelligence/scheduler/status",
        method=HttpMethod.GET,
        title_en="Get Scheduler Status",
        title_ru="Статус планировщика",
        description_en="Get scheduler status and last run info.",
        description_ru="Получить статус планировщика.",
        category="news_intelligence",
        tags=["scheduler"]
    ),
    
    ApiEndpoint(
        endpoint_id="news-event-types",
        path="/api/news-intelligence/event-types",
        method=HttpMethod.GET,
        title_en="Get Event Types",
        title_ru="Типы событий",
        description_en="Get list of available news event types.",
        description_ru="Получить список типов событий.",
        category="news_intelligence",
        tags=["news", "metadata"]
    ),
]


# ═══════════════════════════════════════════════════════════════
# INTELLIGENCE INDEX API (NEW)
# ═══════════════════════════════════════════════════════════════

INTELLIGENCE_INDEX_DOCUMENTATION = [
    ApiEndpoint(
        endpoint_id="intelligence_top",
        path="/api/intelligence/top",
        method=HttpMethod.GET,
        title_en="Top Entities by Intelligence Score",
        title_ru="Топ сущностей по индексу интеллекта",
        description_en="Get ranked list of entities by their Intelligence Score. Combines influence, momentum, narrative alignment, activity, and investor strength.",
        description_ru="Получить ранжированный список сущностей по Индексу Интеллекта. Объединяет влияние, моментум, привязку к нарративам, активность и силу инвесторов.",
        category="intelligence",
        tags=["intelligence", "ranking", "score", "top"],
        parameters=[
            ApiParameter(name="entity_type", type="string", required=False, description_en="Filter by type: project, fund, person, exchange", description_ru="Фильтр по типу: project, fund, person, exchange"),
            ApiParameter(name="limit", type="integer", required=False, default=20, description_en="Number of results", description_ru="Количество результатов"),
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Top entities with intelligence profiles", description_ru="Топ сущностей с профилями интеллекта",
                       example={"ok": True, "count": 10, "entities": [{"entity_id": "binance", "score": 59.3, "tier": "B", "influence": 45.2, "momentum": 50.0}]})
        ],
        curl_example='''# Get top 10 entities
curl -X GET "https://api.example.com/api/intelligence/top?limit=10"

# Get top 20 projects only
curl -X GET "https://api.example.com/api/intelligence/top?entity_type=project&limit=20"

# Get top funds
curl -X GET "https://api.example.com/api/intelligence/top?entity_type=fund"'''
    ),
    
    ApiEndpoint(
        endpoint_id="intelligence_entity",
        path="/api/intelligence/entity/{entity_type}/{entity_id}",
        method=HttpMethod.GET,
        title_en="Entity Intelligence Profile",
        title_ru="Профиль интеллекта сущности",
        description_en="Get full intelligence profile for an entity. Returns all score components: influence (25%), momentum (20%), narrative_alignment (20%), activity_level (20%), investor_strength (15%).",
        description_ru="Получить полный профиль интеллекта сущности. Возвращает все компоненты оценки: влияние (25%), моментум (20%), привязка к нарративам (20%), активность (20%), сила инвесторов (15%).",
        category="intelligence",
        tags=["intelligence", "profile", "entity"],
        parameters=[
            ApiParameter(name="entity_type", type="string", required=True, location="path", description_en="Entity type: project, fund, person, exchange", description_ru="Тип сущности"),
            ApiParameter(name="entity_id", type="string", required=True, location="path", description_en="Entity ID (slug)", description_ru="ID сущности (slug)"),
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Entity intelligence profile", description_ru="Профиль интеллекта",
                       example={"ok": True, "entity_key": "project:near", "score": 40.6, "tier": "B", "influence": 12.4, "momentum": 50.0, "narrative_alignment": 68.4, "activity_level": 62.1, "investor_strength": 12.4, "narratives": ["AI x Crypto", "DeFi"]})
        ],
        curl_example='''# Get NEAR Protocol profile
curl -X GET "https://api.example.com/api/intelligence/entity/project/near"

# Get a16z fund profile
curl -X GET "https://api.example.com/api/intelligence/entity/fund/a16z"

# Get Binance exchange profile
curl -X GET "https://api.example.com/api/intelligence/entity/exchange/binance"'''
    ),
    
    ApiEndpoint(
        endpoint_id="intelligence_narratives",
        path="/api/intelligence/narratives",
        method=HttpMethod.GET,
        title_en="List All Narratives",
        title_ru="Список всех нарративов",
        description_en="Get list of all 20 tracked narratives with metadata: icon, color, keywords, and current leader. Essential for understanding market themes.",
        description_ru="Получить список всех 20 отслеживаемых нарративов с метаданными: иконка, цвет, ключевые слова и текущий лидер. Важно для понимания рыночных тем.",
        category="narratives",
        tags=["narratives", "themes", "market"],
        responses=[
            ApiResponse(status_code=200, description_en="List of narratives with leaders", description_ru="Список нарративов с лидерами",
                       example={"ok": True, "count": 20, "narratives": [{"id": "ai_crypto", "name": "AI x Crypto", "icon": "🤖", "color": "#8B5CF6", "leader": "near", "leader_score": 50.0}]})
        ],
        curl_example='''# Get all tracked narratives with leaders
curl -X GET "https://api.example.com/api/intelligence/narratives"

# Response includes 20 narratives:
# ai_crypto, defi, l2, restaking, rwa, depin, gaming, memecoins, etc.'''
    ),
    
    ApiEndpoint(
        endpoint_id="intelligence_narrative_leaders",
        path="/api/intelligence/narrative/{narrative}",
        method=HttpMethod.GET,
        title_en="Narrative Leaders",
        title_ru="Лидеры нарратива",
        description_en="Get top entities dominating a specific narrative. Answers: 'Who leads in AI?' or 'Who dominates DeFi?'",
        description_ru="Получить топ сущностей, доминирующих в конкретном нарративе. Отвечает на вопросы: 'Кто лидирует в AI?' или 'Кто доминирует в DeFi?'",
        category="narratives",
        tags=["narratives", "leaders", "dominance"],
        parameters=[
            ApiParameter(name="narrative", type="string", required=True, location="path", description_en="Narrative ID: ai_crypto, defi, l2, restaking, rwa, etc.", description_ru="ID нарратива: ai_crypto, defi, l2, restaking, rwa и др."),
            ApiParameter(name="limit", type="integer", required=False, default=10, description_en="Number of results", description_ru="Количество результатов"),
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Top entities in narrative", description_ru="Топ сущностей в нарративе",
                       example={"ok": True, "narrative": "ai_crypto", "count": 5, "leaders": [{"entity_id": "near", "total_score": 68.4}]})
        ],
        curl_example='''# Who leads in AI x Crypto narrative?
curl -X GET "https://api.example.com/api/intelligence/narrative/ai_crypto"

# Who dominates DeFi?
curl -X GET "https://api.example.com/api/intelligence/narrative/defi?limit=5"

# Top projects in Layer 2 narrative
curl -X GET "https://api.example.com/api/intelligence/narrative/l2"

# Restaking leaders
curl -X GET "https://api.example.com/api/intelligence/narrative/restaking"'''
    ),
    
    ApiEndpoint(
        endpoint_id="intelligence_narrative_dominance",
        path="/api/intelligence/narrative-dominance",
        method=HttpMethod.GET,
        title_en="Narrative Dominance Map",
        title_ru="Карта доминирования нарративов",
        description_en="Get map showing which entity leads each narrative. Critical market intelligence for trend analysis.",
        description_ru="Получить карту, показывающую какая сущность лидирует в каждом нарративе. Критически важный рыночный интеллект для анализа трендов.",
        category="narratives",
        tags=["narratives", "dominance", "map", "leaders"],
        responses=[
            ApiResponse(status_code=200, description_en="Dominance map", description_ru="Карта доминирования",
                       example={"ok": True, "dominance": {"ai_crypto": {"narrative_name": "AI x Crypto", "leader": "near", "score": 50.0}, "defi": {"narrative_name": "DeFi", "leader": "aave", "score": 7.2}}})
        ],
        curl_example='''# Get narrative dominance map - who leads each theme
curl -X GET "https://api.example.com/api/intelligence/narrative-dominance"

# Example response structure:
# {
#   "ai_crypto": {"leader": "near", "score": 50.0},
#   "defi": {"leader": "aave", "score": 7.2},
#   "restaking": {"leader": "eigenlayer", "score": 5.0},
#   "l2": {"leader": "arbitrum", "score": 5.0}
# }'''
    ),
    
    ApiEndpoint(
        endpoint_id="intelligence_emerging",
        path="/api/intelligence/emerging",
        method=HttpMethod.GET,
        title_en="Emerging Entities",
        title_ru="Восходящие сущности",
        description_en="Get entities with high momentum velocity - those rapidly gaining importance. Early signal for trend detection.",
        description_ru="Получить сущности с высокой скоростью моментума - те, которые быстро набирают важность. Ранний сигнал для детекции трендов.",
        category="intelligence",
        tags=["intelligence", "emerging", "momentum", "trends"],
        parameters=[
            ApiParameter(name="entity_type", type="string", required=False, description_en="Filter by type", description_ru="Фильтр по типу"),
            ApiParameter(name="limit", type="integer", required=False, default=20, description_en="Number of results", description_ru="Количество результатов"),
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Emerging entities", description_ru="Восходящие сущности")
        ],
        curl_example='''# Get emerging entities (high momentum velocity)
curl -X GET "https://api.example.com/api/intelligence/emerging"

# Emerging projects only
curl -X GET "https://api.example.com/api/intelligence/emerging?entity_type=project&limit=10"'''
    ),
    
    ApiEndpoint(
        endpoint_id="intelligence_most_active",
        path="/api/intelligence/most-active",
        method=HttpMethod.GET,
        title_en="Most Active Entities",
        title_ru="Самые активные сущности",
        description_en="Get entities with highest activity in last 30 days. Activity = funding + partnerships + launches + unlocks (weighted).",
        description_ru="Получить сущности с наивысшей активностью за последние 30 дней. Активность = финансирование + партнёрства + запуски + анлоки (взвешенно).",
        category="activity",
        tags=["activity", "active", "events"],
        parameters=[
            ApiParameter(name="entity_type", type="string", required=False, description_en="Filter by type", description_ru="Фильтр по типу"),
            ApiParameter(name="limit", type="integer", required=False, default=20, description_en="Number of results", description_ru="Количество результатов"),
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Most active entities", description_ru="Самые активные сущности",
                       example={"ok": True, "entities": [{"entity_id": "binance", "total_score": 100.0, "activities": [{"type": "news_mentions", "score": 3.4}]}]})
        ],
        curl_example='''# Get most active entities (30 days)
curl -X GET "https://api.example.com/api/intelligence/most-active"

# Most active projects
curl -X GET "https://api.example.com/api/intelligence/most-active?entity_type=project&limit=10"

# Most active funds (investment activity)
curl -X GET "https://api.example.com/api/intelligence/most-active?entity_type=fund"'''
    ),
    
    ApiEndpoint(
        endpoint_id="intelligence_accelerating",
        path="/api/intelligence/accelerating",
        method=HttpMethod.GET,
        title_en="Accelerating Entities",
        title_ru="Ускоряющиеся сущности",
        description_en="Get entities with highest activity velocity (7d vs 30d). Detects when activity is accelerating.",
        description_ru="Получить сущности с наивысшей скоростью активности (7д vs 30д). Детектирует когда активность ускоряется.",
        category="activity",
        tags=["activity", "velocity", "acceleration"],
        parameters=[
            ApiParameter(name="entity_type", type="string", required=False, description_en="Filter by type", description_ru="Фильтр по типу"),
            ApiParameter(name="limit", type="integer", required=False, default=20, description_en="Number of results", description_ru="Количество результатов"),
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Accelerating entities", description_ru="Ускоряющиеся сущности")
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="intelligence_entity_trend",
        path="/api/intelligence/entity/{entity_type}/{entity_id}/trend",
        method=HttpMethod.GET,
        title_en="Entity Score Trend",
        title_ru="Тренд оценки сущности",
        description_en="Get historical intelligence score trend for an entity. Essential for momentum detection, trend analysis, bubble detection.",
        description_ru="Получить исторический тренд оценки интеллекта для сущности. Важно для детекции моментума, анализа трендов, обнаружения пузырей.",
        category="intelligence",
        tags=["intelligence", "trend", "history", "timeseries"],
        parameters=[
            ApiParameter(name="entity_type", type="string", required=True, location="path", description_en="Entity type", description_ru="Тип сущности"),
            ApiParameter(name="entity_id", type="string", required=True, location="path", description_en="Entity ID", description_ru="ID сущности"),
            ApiParameter(name="days", type="integer", required=False, default=30, description_en="Number of days (7-90)", description_ru="Количество дней (7-90)"),
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Score trend data", description_ru="Данные тренда оценки",
                       example={"ok": True, "entity_key": "project:near", "days": 30, "trend": [{"date": "2026-02-10", "score": 31.2}, {"date": "2026-03-10", "score": 40.6}]})
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="intelligence_compare",
        path="/api/intelligence/compare",
        method=HttpMethod.GET,
        title_en="Compare Entities",
        title_ru="Сравнение сущностей",
        description_en="Compare multiple entities side by side. Useful for competitive analysis.",
        description_ru="Сравнение нескольких сущностей. Полезно для конкурентного анализа.",
        category="intelligence",
        tags=["intelligence", "compare", "analysis"],
        parameters=[
            ApiParameter(name="entities", type="string", required=True, description_en="Comma-separated entity keys (type:id)", description_ru="Ключи сущностей через запятую (type:id)", example="project:arbitrum,project:optimism,project:base"),
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Comparison data", description_ru="Данные сравнения")
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="intelligence_tier",
        path="/api/intelligence/tier/{tier}",
        method=HttpMethod.GET,
        title_en="Entities by Tier",
        title_ru="Сущности по уровню",
        description_en="Get entities by tier classification. S=80+, A=60+, B=40+, C=20+, D<20.",
        description_ru="Получить сущности по классификации уровня. S=80+, A=60+, B=40+, C=20+, D<20.",
        category="intelligence",
        tags=["intelligence", "tier", "classification"],
        parameters=[
            ApiParameter(name="tier", type="string", required=True, location="path", description_en="Tier: S, A, B, C, D", description_ru="Уровень: S, A, B, C, D"),
            ApiParameter(name="entity_type", type="string", required=False, description_en="Filter by type", description_ru="Фильтр по типу"),
            ApiParameter(name="limit", type="integer", required=False, default=50, description_en="Number of results", description_ru="Количество результатов"),
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Entities in tier", description_ru="Сущности в уровне")
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="intelligence_bootstrap",
        path="/api/intelligence/bootstrap",
        method=HttpMethod.POST,
        title_en="Bootstrap Intelligence Engines",
        title_ru="Инициализация движков интеллекта",
        description_en="Trigger full bootstrap of all intelligence engines: Narrative Scores → Activity Scores → Intelligence Index. Use for initial setup or refresh.",
        description_ru="Запустить полную инициализацию всех движков интеллекта: Оценки нарративов → Оценки активности → Индекс интеллекта. Используйте для начальной настройки или обновления.",
        category="intelligence",
        tags=["intelligence", "bootstrap", "admin"],
        parameters=[
            ApiParameter(name="limit", type="integer", required=False, default=300, description_en="Max entities to process", description_ru="Максимум сущностей для обработки"),
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Bootstrap results", description_ru="Результаты инициализации",
                       example={"ok": True, "narrative_scores": {"processed": 195}, "activity_scores": {"processed": 195}, "intelligence_index": {"processed": 224}})
        ]
    ),
]


# ═══════════════════════════════════════════════════════════════
# CACHE & REDIS API (NEW)
# ═══════════════════════════════════════════════════════════════

CACHE_DOCUMENTATION = [
    ApiEndpoint(
        endpoint_id="cache_health",
        path="/api/cache/health",
        method=HttpMethod.GET,
        title_en="Redis Cache Health",
        title_ru="Состояние Redis кэша",
        description_en="Check Redis cache connection status. Returns healthy/unavailable.",
        description_ru="Проверить статус подключения Redis кэша. Возвращает healthy/unavailable.",
        category="cache",
        tags=["cache", "redis", "health"],
        responses=[
            ApiResponse(status_code=200, description_en="Cache health status", description_ru="Статус здоровья кэша",
                       example={"ok": True, "status": "healthy", "available": True})
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="cache_stats",
        path="/api/cache/stats",
        method=HttpMethod.GET,
        title_en="Redis Cache Statistics",
        title_ru="Статистика Redis кэша",
        description_en="Get detailed Redis cache statistics: memory, keys, hit rate.",
        description_ru="Получить детальную статистику Redis кэша: память, ключи, процент попаданий.",
        category="cache",
        tags=["cache", "redis", "stats"],
        responses=[
            ApiResponse(status_code=200, description_en="Cache statistics", description_ru="Статистика кэша",
                       example={"ok": True, "available": True, "memory_mb": 2.5, "total_keys": 156, "hit_rate": 0.85})
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="cache_precompute_stats",
        path="/api/cache/precompute/stats",
        method=HttpMethod.GET,
        title_en="Graph Precompute Statistics",
        title_ru="Статистика предвычисления графов",
        description_en="Get statistics for Layer 2 graph precomputation system.",
        description_ru="Получить статистику системы предвычисления графов Layer 2.",
        category="cache",
        tags=["cache", "precompute", "graph"],
        responses=[
            ApiResponse(status_code=200, description_en="Precompute stats", description_ru="Статистика предвычисления")
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="cache_precompute_run",
        path="/api/cache/precompute/run",
        method=HttpMethod.POST,
        title_en="Trigger Graph Precompute",
        title_ru="Запустить предвычисление графов",
        description_en="Manually trigger precomputation of hot entity graphs. Normally runs every 5 minutes via scheduler.",
        description_ru="Вручную запустить предвычисление графов горячих сущностей. Обычно запускается каждые 5 минут планировщиком.",
        category="cache",
        tags=["cache", "precompute", "admin"],
        parameters=[
            ApiParameter(name="limit", type="integer", required=False, default=100, description_en="Max entities to precompute", description_ru="Максимум сущностей для предвычисления"),
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Precompute results", description_ru="Результаты предвычисления")
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="cache_precompute_hot_list",
        path="/api/cache/precompute/hot-list",
        method=HttpMethod.GET,
        title_en="Hot Entities List",
        title_ru="Список горячих сущностей",
        description_en="Get list of entities currently in hot cache (precomputed).",
        description_ru="Получить список сущностей в горячем кэше (предвычисленных).",
        category="cache",
        tags=["cache", "precompute", "hot"],
        responses=[
            ApiResponse(status_code=200, description_en="Hot entities", description_ru="Горячие сущности",
                       example={"ok": True, "entities": ["project:bitcoin", "project:ethereum", "fund:a16z"]})
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="queue_stats",
        path="/api/cache/queue/stats",
        method=HttpMethod.GET,
        title_en="Queue Statistics",
        title_ru="Статистика очередей",
        description_en="Get statistics for Redis task queues: parser_jobs, intelligence_jobs, alerts.",
        description_ru="Получить статистику Redis очередей задач: parser_jobs, intelligence_jobs, alerts.",
        category="queues",
        tags=["queue", "redis", "tasks"],
        responses=[
            ApiResponse(status_code=200, description_en="Queue statistics", description_ru="Статистика очередей",
                       example={"ok": True, "stats": {"total_enqueued": 50, "total_processed": 48, "queue_sizes": {"parser_jobs": 0, "intelligence_jobs": 2}}})
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="queue_enqueue_parser",
        path="/api/cache/queue/enqueue/parser",
        method=HttpMethod.POST,
        title_en="Enqueue Parser Job",
        title_ru="Добавить задачу парсера",
        description_en="Manually enqueue a parser sync job. Parsers: coingecko, cryptorank, defillama, tokenunlocks, etc.",
        description_ru="Вручную добавить задачу синхронизации парсера. Парсеры: coingecko, cryptorank, defillama, tokenunlocks и др.",
        category="queues",
        tags=["queue", "parser", "sync"],
        parameters=[
            ApiParameter(name="parser", type="string", required=True, description_en="Parser name", description_ru="Имя парсера"),
            ApiParameter(name="task", type="string", required=False, default="sync", description_en="Task type", description_ru="Тип задачи"),
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Job enqueued", description_ru="Задача добавлена",
                       example={"ok": True, "job_id": "job_abc123", "parser": "coingecko"})
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="queue_enqueue_intelligence",
        path="/api/cache/queue/enqueue/intelligence",
        method=HttpMethod.POST,
        title_en="Enqueue Intelligence Job",
        title_ru="Добавить задачу интеллекта",
        description_en="Manually enqueue an intelligence job. Tasks: momentum_update, projection_update, graph_precompute, etc.",
        description_ru="Вручную добавить задачу интеллекта. Задачи: momentum_update, projection_update, graph_precompute и др.",
        category="queues",
        tags=["queue", "intelligence", "tasks"],
        parameters=[
            ApiParameter(name="task", type="string", required=True, description_en="Task name", description_ru="Имя задачи"),
        ],
        responses=[
            ApiResponse(status_code=200, description_en="Job enqueued", description_ru="Задача добавлена")
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="workers_status",
        path="/api/cache/workers/status",
        method=HttpMethod.GET,
        title_en="Queue Workers Status",
        title_ru="Статус воркеров очередей",
        description_en="Get status of queue workers: running, handlers registered, jobs processed.",
        description_ru="Получить статус воркеров очередей: запущены, обработчики зарегистрированы, задачи обработаны.",
        category="queues",
        tags=["queue", "workers", "status"],
        responses=[
            ApiResponse(status_code=200, description_en="Workers status", description_ru="Статус воркеров",
                       example={"ok": True, "running": True, "redis_available": True, "stats": {"workers_running": 3}})
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="workers_start",
        path="/api/cache/workers/start",
        method=HttpMethod.POST,
        title_en="Start Queue Workers",
        title_ru="Запустить воркеры очередей",
        description_en="Start all queue workers (parser, intelligence, alerts).",
        description_ru="Запустить все воркеры очередей (parser, intelligence, alerts).",
        category="queues",
        tags=["queue", "workers", "admin"],
        responses=[
            ApiResponse(status_code=200, description_en="Workers started", description_ru="Воркеры запущены")
        ]
    ),
    
    ApiEndpoint(
        endpoint_id="workers_stop",
        path="/api/cache/workers/stop",
        method=HttpMethod.POST,
        title_en="Stop Queue Workers",
        title_ru="Остановить воркеры очередей",
        description_en="Stop all queue workers.",
        description_ru="Остановить все воркеры очередей.",
        category="queues",
        tags=["queue", "workers", "admin"],
        responses=[
            ApiResponse(status_code=200, description_en="Workers stopped", description_ru="Воркеры остановлены")
        ]
    ),
]


# Combined list for easy import
NEW_ENDPOINTS_DOCUMENTATION = (
    ACTIVITIES_DOCUMENTATION +
    INTEL_FEED_DOCUMENTATION +
    PROJECTS_EXTENDED_DOCUMENTATION +
    UNLOCKS_EXTENDED_DOCUMENTATION +
    NEWS_HEALTH_DOCUMENTATION +
    INTELLIGENCE_INDEX_DOCUMENTATION +
    CACHE_DOCUMENTATION
)
