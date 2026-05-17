# CODE_DIAGRAM.md — Визуальная диаграмма кода FOMO OS

> Production-state: 2026-05-17. Зелёные блоки = LIVE. Жёлтые = опциональные/best-effort. Серые = legacy/будет удалено.

## 1. High-level system diagram

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                                  USERS                                       │
│                                                                              │
│   ┌─────────────────┐  ┌───────────────────┐  ┌────────────────────────┐    │
│   │   Web Browser   │  │ Mobile (Expo iOS  │  │ Telegram MiniApp       │    │
│   │  /  Chrome+Ext  │  │   / Android)      │  │                        │    │
│   └────────┬────────┘  └─────────┬─────────┘  └──────────┬─────────────┘    │
│            │ HTTPS               │ HTTPS                  │ HTTPS+initData    │
└────────────┼─────────────────────┼────────────────────────┼──────────────────┘
             │                     │                        │
             ▼                     ▼                        ▼
        ┌──────────────────────────────────────────────────────────┐
        │           NGINX / Kubernetes Ingress                    │
        │       /api/* → port 8001    │    /* → port 3000         │
        └──────────┬─────────────────┴──────────┬─────────────────┘
                   │                            │
                   ▼                            ▼
      ┌──────────────────────────┐    ┌─────────────────────────┐
      │   FastAPI (port 8001)    │    │  React CRA (port 3000)   │
      │   backend/server.py       │    │  frontend/src/App.js     │
      │   ────────────────────    │    │  ─────────────────────   │
      │   ┌──────────────────┐    │    │  Pages:                  │
      │   │ Route registry   │    │    │   • twitter/* (Sentiment)│
      │   │ (order matters!) │    │    │   • connections/*        │
      │   │                  │    │    │   • OverviewV2Page       │
      │   │ 1. _ta_router    │    │    │   • FractalIntelligence  │
      │   │ 2. _sentiment_*  │    │    │   • AltScreenerPage      │
      │   │ 3. _twitter_v4   │    │    │   • AlphaPage / Trading  │
      │   │ ...              │    │    │   • Settings / Alerts    │
      │   │ N-1. _onchain    │    │    │  Components:             │
      │   │ N.   _news_runt  │    │    │   • ui/* (Shadcn ×30+)   │
      │   │ N+1. _deep_runt  │    │    │   • charts (recharts,    │
      │   │ LAST. _legacy_   │    │    │     lightweight, echarts)│
      │   │      compat ⚠️   │    │    │   • graph (d3-force)     │
      │   └──────────────────┘    │    └──────────────────────────┘
      └──────────┬───────────────┘
                 │
                 ▼
       ┌─────────────────────────────────────────┐
       │      MongoDB (fomo_mobile)              │
       │  ─────────────────────────────────────  │
       │  Live collections:                      │
       │   • users, sessions                     │
       │   • twitter_tweets, twitter_accounts    │
       │   • news_articles (3087), news_sources  │
       │   • sentiment_events (4483)             │
       │   • deep_projects (106), funding_rounds │
       │     (386), persons (899), unlocks (26), │
       │     funds (20), project_events (655)    │
       │   • mbrain_verdicts, mbrain_calibration │
       │   • onchain_per_asset_*                 │
       │   • paper_positions, broker_state       │
       └─────────────────────────────────────────┘
                 ▲
                 │  Background jobs (supervisor):
                 │
       ┌─────────┴─────────────────────────────────────┐
       │                                                │
       │  ┌──────────────────┐  ┌──────────────────┐   │
       │  │ news_substrate   │  │ deep_parser loop │   │
       │  │ (continuous loop)│  │ (every 6h)       │   │
       │  └──────────────────┘  └──────────────────┘   │
       │                                                │
       │   External feeds (read-only HTTP):             │
       │    • 119 RSS sources                           │
       │    • DropsTab / CryptoRank / ICODrops / CMC    │
       │    • CoinGecko, CryptoCompare, Fear&Greed      │
       │    • Binance / Bybit / OKX (CCXT)              │
       └────────────────────────────────────────────────┘
```

---

## 2. Backend module tree (production-relevant only)

```
/app/backend/
├── server.py                      ← главный entry point, регистрация всех routers
├── .env                            ← MONGO_URL, DB_NAME, GOOGLE_CLIENT_ID, EMERGENT_LLM_KEY
├── requirements.txt
│
├── routes/                         ← FastAPI routers (38 production + legacy_compat)
│   ├── auth.py                    │ web auth
│   ├── auth_gate.py               │ paywall gate
│   ├── mobile_auth.py             │ ⭐ Google/Email/Phone auth (mobile + web)
│   │
│   ├── # ─── M1 TA ─────────────── 
│   ├── ta_prediction.py           │
│   │
│   ├── # ─── M2 Fractal ───────────
│   ├── fractal_runtime.py         │ /api/fractal/runtime/{asset}
│   │
│   ├── # ─── M3 OnChain ───────────
│   ├── onchain_runtime.py         │ /api/onchain/runtime/{asset} (per-asset)
│   │
│   ├── # ─── M4 Exchange ──────────
│   ├── cex_intelligence_router.py │ /api/venues/all/health (+TTL cache)
│   │
│   ├── # ─── M5 Sentiment ─────────
│   ├── news_runtime.py            │ /api/news/{feed,digest,velocity}
│   ├── sentiment_runtime.py       │ /api/sentiment/runtime
│   ├── sentiment_public.py        │ /api/sentiment/public
│   ├── sentiment_surface_adapters.py │ /api/connections/clusters/intelligence
│   ├── narrative_flow_adapter.py  │ /api/narrative-flow
│   ├── backers_runtime.py         │ /api/backers
│   ├── backers_alerts_router.py   │ /api/backers-alerts
│   ├── deep_runtime.py            │ /api/deep/{stats,funds,persons,unlocks,projects}
│   │
│   ├── # ─── MetaBrain ────────────
│   ├── mbrain_verdicts.py         │ /api/meta-brain-v2/verdict/*
│   ├── mbrain_integrity.py        │
│   ├── mbrain_shadow.py           │
│   ├── mbrain_positions.py        │
│   ├── mbrain_attribution.py      │
│   ├── mbrain_attribution_realized.py
│   ├── metabrain_charts.py        │
│   │
│   ├── # ─── Twitter ──────────────
│   ├── # (twitter_v4 — inline endpoints в server.py)
│   │
│   ├── # ─── Billing ──────────────
│   ├── billing_routes.py          │
│   ├── billing_products.py        │
│   ├── billing_analytics.py       │
│   ├── billing_reconciliation.py  │
│   ├── me_billing.py              │
│   │
│   ├── # ─── Admin ────────────────
│   ├── admin_auth.py              │
│   ├── admin_users.py             │
│   ├── admin_core7.py             │
│   ├── admin_billing_routes.py    │
│   │
│   ├── # ─── Trading / Broker ─────
│   ├── broker_bridge.py           │ currently noop
│   ├── trading_cases.py           │
│   ├── labs.py                    │
│   │
│   └── legacy_compat.py           │ ⚠️ catch-all, регистрируется ПОСЛЕДНИМ
│
├── services/                       ← бизнес-логика (без HTTP)
│   ├── # ─── M5 Sentiment ─────────
│   ├── deep_parser.py             │ ⭐ DropsTab/CryptoRank/ICODrops/CMC SPA parser (924 строки)
│   ├── feed_service.py            │ CoinGecko + Fear&Greed
│   ├── news_intelligence.py       │ CryptoCompare news enrichment
│   ├── news_substrate_loop.py     │ supervisor process — continuous RSS loop
│   ├── feed_events_service.py     │
│   ├── feed_intelligence.py       │
│   │
│   ├── # ─── M3 OnChain ───────────
│   ├── onchain_per_asset.py       │ per-symbol adapters
│   │
│   ├── # ─── M1/M4 Exchange/TA ────
│   ├── exchange/                  │ Binance/Bybit/OKX wrappers
│   ├── bar_data.py                │ OHLC cache
│   ├── asset_intelligence.py      │ TA aggregation
│   │
│   ├── # ─── M2 Fractal ───────────
│   ├── fractal_generator.py       │
│   ├── fractal_runtime.py         │
│   │
│   ├── # ─── MetaBrain ────────────
│   ├── calibration.py             │
│   ├── broker_bridge.py           │ noop / mode=off
│   ├── binance_testnet_executor.py
│   │
│   └── # ─── Прочее ───────────────
│       ├── ab_analytics.py
│       ├── adaptive_risk.py
│       ├── affinity_service.py
│       ├── alt_engine.py
│       ├── asset_registry.py
│       ├── email_service.py
│       ├── edge_opportunities.py
│       └── ...
│
├── scripts/                        ← CLI utilities
│   ├── run_rss_pipeline.py        │ ⭐ Запуск 119 RSS источников
│   ├── news_substrate_loop.py     │ Continuous loop (через supervisor)
│   ├── twitter_sentiment_step.py  │ Twitter ingestion step
│   ├── run_data_pipeline.py       │ Полный data refresh
│   ├── ensure_indexes.py          │ MongoDB indexes
│   └── ...
│
├── modules/                        ← native engines
│   ├── twitter_parser/            │ Hybrid V2 (L0-L3)
│   └── parsers/                    │ legacy specialized parsers
│
├── admin_build/
│   └── fomo_extension_v1.3.0/     │ ⭐ Chrome Extension (MV3)
│       ├── manifest.json
│       ├── background.js
│       ├── popup.html / popup.js
│       ├── twitter-fetcher.js
│       ├── cookie-quality-checker.js
│       └── backend-error-mapper.js
│
├── public/                         ← public-facing files
│   └── SENTIMENT_API_DOCS.md      │ (копия → /app/SENTIMENT_API.md)
│
├── static/                         ← serve as static
│   └── TWITTER_PARSER_INSTALL_GUIDE.md  │ (копия → /app/TWITTER_INSTALL.md)
│
├── telegram_intel/                 │ Telegram intelligence (см. /app/TELEGRAM_INTEL.md)
│
├── cex_intelligence/               │ CEX market intelligence
│
└── data/                           ← runtime data (logs, snapshots)
```

---

## 3. Frontend module tree

```
/app/frontend/
├── package.json
├── tailwind.config.js
├── craco.config.js
│
├── src/
│   ├── App.js                     ← главный router
│   ├── index.js                   ← React mount
│   ├── App.css, index.css         ← global Tailwind
│   │
│   ├── pages/
│   │   ├── twitter/               ← ⭐ Sentiment tabs
│   │   │   ├── TwitterPage.jsx           │ Главный layout с lazy tabs
│   │   │   ├── TwitterOverviewPage.jsx   │ Overview tab (live data)
│   │   │   ├── PredictionTab.jsx         │
│   │   │   ├── NewsTab.jsx               │ (1265 строк — кандидат на code-split)
│   │   │   ├── FeedTab.jsx               │
│   │   │   ├── ActorsTab.jsx             │
│   │   │   ├── GraphTab.jsx              │ d3-force network
│   │   │   ├── NetworkTab.jsx            │
│   │   │   ├── MarketTab.jsx             │
│   │   │   ├── BakersTab.jsx             │ ← рендерит /api/backers
│   │   │   ├── components/
│   │   │   │   ├── SentimentHeader.jsx
│   │   │   │   └── ...
│   │   │   └── TwitterParserWrapper.jsx
│   │   │
│   │   ├── connections/
│   │   │   ├── ClustersNetworkPage.jsx   │ Network graph
│   │   │   ├── BakeryPage.jsx            │
│   │   │   ├── ConnectionsDetailPage.jsx │
│   │   │   └── ...
│   │   │
│   │   ├── OverviewV2Page.jsx     │ Alpha (главная)
│   │   ├── FractalIntelligencePage.jsx  │ M2 Fractal
│   │   ├── AltScreenerPage.jsx    │ Alt-coin screener
│   │   ├── TradingPage.jsx        │
│   │   ├── SettingsPage.jsx       │
│   │   └── AlertsPage.jsx         │
│   │
│   ├── components/
│   │   └── ui/                    ← ⭐ Shadcn (30+ components)
│   │       ├── button.jsx
│   │       ├── card.jsx
│   │       ├── dialog.jsx
│   │       ├── tabs.jsx
│   │       └── ... (см. весь список в PROJECT.md §11)
│   │
│   ├── hooks/
│   │   └── use-toast.js
│   │
│   └── lib/
│       └── utils.js               ← cn() utility
│
└── public/
    ├── index.html
    ├── favicon.ico
    └── fomo_extension_v1.3.0/     ← extension download для пользователей
```

---

## 4. Data flow для Sentiment (детально)

```
                            ┌─────────────────────────┐
                            │   119 RSS feeds         │
                            │ (CoinDesk, Reddit, etc.)│
                            └───────────┬─────────────┘
                                        │ HTTP GET (httpx)
                                        ▼
                            ┌─────────────────────────┐
                            │ scripts/                │
                            │ run_rss_pipeline.py     │
                            │ (each batch=10, with    │
                            │ feedparser + entity     │
                            │ extraction regex)       │
                            └───────────┬─────────────┘
                                        │ upsert (motor)
                                        ▼
       ┌──────────────────────────────────────────────────────┐
       │              MongoDB / fomo_mobile                    │
       │  • news_articles    (id, source_id, title, summary,   │
       │                      entities_mentioned, published_at)│
       │  • news_sources     (id, name, rss_url, tier, weight) │
       │  • sentiment_events (entity, source, signal_strength) │
       └────────────────────────┬─────────────────────────────┘
                                │
                                │ запрашивается из:
                                ▼
       ┌──────────────────────────────────────────────────────┐
       │ routes/news_runtime.py                               │
       │ ─────────────────────                                │
       │ /api/news/feed?limit=50&hours=48                     │
       │   → clusterize by event_type + asset + 6h window     │
       │   → score importance, detect breaking                │
       │   → return: {ok:true, data:{clusters:[...]}}         │
       └────────────────────────┬─────────────────────────────┘
                                │ fetch
                                ▼
       ┌──────────────────────────────────────────────────────┐
       │ frontend/src/pages/twitter/NewsTab.jsx               │
       │ ──────────────────────────────                       │
       │ useEffect → fetchFeed() каждые 90s                   │
       │ Breaking alerts через sonner toast                   │
       │ UI: 1 card = 1 cluster, фильтры sentiment/event_type │
       └──────────────────────────────────────────────────────┘
```

```
                  ┌──────────────────────────────────────┐
                  │  External SPA sites (Next.js __NEXT_DATA__) │
                  │  • DropsTab    /coins/{slug}                  │
                  │  • DropsTab    /investors/{slug}               │
                  │  • CryptoRank  /ico/{slug}                     │
                  │  • ICODrops    /category/...                   │
                  │  • CoinMarketCap /currencies/{slug}/           │
                  └─────────┬────────────────────────────────────┘
                            │ httpx + regex __NEXT_DATA__ extraction
                            ▼
                  ┌──────────────────────────────────────┐
                  │ services/deep_parser.py              │
                  │ ────────────────────                  │
                  │ • _cryptorank_scrape_project()        │
                  │ • _icodrops_scrape_project()          │
                  │ • _dropstab_scrape_project()          │
                  │ • _dropstab_scrape_fund()             │
                  │ • _coinmarketcap_scrape_unlock()      │
                  │                                        │
                  │ Запускается:                           │
                  │  • вручную: bash run_sentiment.sh      │
                  │  • авто:    start_loop_if_enabled()    │
                  │             каждые 6 часов              │
                  └─────────┬─────────────────────────────┘
                            │ upsert (pymongo)
                            ▼
                  ┌──────────────────────────────────────┐
                  │  MongoDB:                            │
                  │  • deep_projects (106)               │
                  │  • deep_funding_rounds (386)         │
                  │  • deep_persons (899)                │
                  │  • deep_unlocks (26)                 │
                  │  • deep_funds (20)                   │
                  │  • deep_project_events (655)         │
                  └─────────┬────────────────────────────┘
                            │ exposed by:
                            ▼
                  ┌──────────────────────────────────────┐
                  │ routes/deep_runtime.py               │
                  │  /api/deep/stats                     │
                  │  /api/deep/funds                     │
                  │  /api/deep/persons                   │
                  │  /api/deep/unlocks                   │
                  │  /api/deep/projects/{slug}           │
                  └──────────────────────────────────────┘
```

---

## 5. Chrome Extension data flow

```
┌──────────────────────────────────────────────────────────────────────────┐
│                  USER'S BROWSER (Chrome ≥ 116)                            │
│                                                                          │
│  ┌──────────────────────┐         ┌──────────────────────────┐          │
│  │   Twitter / X tab    │ ◄─cookies── chrome.cookies API     │          │
│  │   (logged-in user)   │         │   (FOMO X Connect)       │          │
│  └──────────────────────┘         │                          │          │
│                                    │  popup.js   ──────────►  │          │
│  ┌──────────────────────┐ HTTPS   │  twitter-fetcher.js      │          │
│  │  twitter.com API     │ ◄──────►│  (Graph queries из       │          │
│  │  (user's IP + cookies)│         │   браузера юзера)        │          │
│  └──────────────────────┘         └──────────┬───────────────┘          │
│                                              │ POST /api/v4/twitter/*    │
└──────────────────────────────────────────────┼──────────────────────────┘
                                               │
                                               ▼
                          ┌─────────────────────────────────────┐
                          │   FOMO Backend (FastAPI)           │
                          │                                     │
                          │  /api/v4/twitter/preflight-check    │
                          │  /api/v4/twitter/sessions/webhook   │
                          │  /api/v4/twitter/ingest             │
                          │  /api/v4/twitter/accounts           │
                          │                                     │
                          │  ► store: twitter_tweets,           │
                          │           twitter_accounts          │
                          └─────────────────────────────────────┘
```

> Backend **никогда не делает прямые запросы** к Twitter — иначе IP датацентра моментально блокируется. Все запросы идут из браузера пользователя через расширение.

---

## 6. Router order in `server.py` (critical)

```python
# В порядке регистрации (упрощённо):
#
# 1. Все production routers          ← ПЕРВЫЕ
#    app.include_router(_ta_router)
#    app.include_router(_sentiment_runtime_router)
#    app.include_router(_news_runtime_router)
#    app.include_router(_deep_runtime_router)
#    app.include_router(_backers_runtime_router)
#    app.include_router(_onchain_runtime_router)
#    ...
#
# 2. Mobile static mount (/api/app/*)
#    app.mount("/api/app/_expo", ...)
#
# 3. _legacy_compat_router            ← ПОСЛЕДНИЙ (catch-all)
#    app.include_router(_legacy_compat_router)
#
# FastAPI evaluates top-down. Если новый endpoint попадает в
# catch-all раньше — он вернёт mock. Поэтому новые маршруты
# ВСЕГДА регистрируются ДО _legacy_compat_router.
```

---

## 7. Process supervision (supervisor)

```
supervisord
├── backend          (uvicorn server:app :8001 --reload)
├── frontend         (yarn start :3000)
├── mongodb          (mongod localhost:27017)
├── news_substrate   (python -m services.news_substrate_loop)
├── code-server      (STOPPED by default)
└── nginx-code-proxy (для code-server)
```
