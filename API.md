# API.md — Полная карта endpoints FOMO OS

> 243 inline endpoints в `server.py` + 38 sub-router'ов из `routes/*.py`. Здесь только **production-relevant** маршруты по группам.

## Содержание
- [Auth & User](#auth--user)
- [MetaBrain Consensus](#metabrain-consensus)
- [Modules: TA / Fractal / OnChain / Exchange / Sentiment](#modules)
- [News & Sentiment Surface](#news--sentiment-surface)
- [Deep Parser (Funds/Persons/Unlocks)](#deep-parser)
- [Twitter (V4 + Extension)](#twitter)
- [Mobile App (Expo)](#mobile-app)
- [Telegram MiniApp](#telegram-miniapp)
- [Billing / Subscriptions](#billing--subscriptions)
- [Admin](#admin)

> ⚠️ **Router order matters.** Все production-роутеры регистрируются **до** `_legacy_compat_router` в `backend/server.py`. Иначе catch-all поглотит запрос и вернёт mock.

---

## Auth & User

| Endpoint | Метод | Файл | Назначение |
|---|---|---|---|
| `/api/mobile/auth/google` | POST | `routes/mobile_auth.py` | Google ID-token login (mobile + web) |
| `/api/mobile/auth/email` | POST | `routes/mobile_auth.py` | Email+password login |
| `/api/mobile/auth/phone` | POST | `routes/mobile_auth.py` | Phone-OTP login |
| `/api/auth/gate?surface=...` | GET | `routes/auth_gate.py` | Paywall gate (web/mobile/miniapp) |
| `/api/auth/login` | POST | `routes/auth.py` | Web email login |
| `/api/auth/register` | POST | `routes/auth.py` | Web registration |
| `/api/users/me` | GET | `routes/admin_users.py` | Текущий пользователь |

---

## MetaBrain Consensus

| Endpoint | Файл | Что отдаёт |
|---|---|---|
| `/api/meta-brain-v2/verdict/{asset}` | `routes/mbrain_verdicts.py` | Текущий verdict для актива |
| `/api/meta-brain-v2/drift` | `routes/mbrain_integrity.py` | Drift detection между модулями |
| `/api/meta-brain-v2/integrity` | `routes/mbrain_integrity.py` | Integrity check всех 5 модулей |
| `/api/meta-brain-v2/shadow` | `routes/mbrain_shadow.py` | Shadow evaluation для paper-runtime gate |
| `/api/meta-brain-v2/positions` | `routes/mbrain_positions.py` | Открытые позиции (paper) |
| `/api/meta-brain-v2/attribution` | `routes/mbrain_attribution.py` | Вклад каждого модуля в verdict |
| `/api/meta-brain-v2/attribution-realized` | `routes/mbrain_attribution_realized.py` | Реализованная attribution после outcome |
| `/api/meta-brain-v2/charts/{asset}` | `routes/metabrain_charts.py` | Charts для UI |

---

## Modules

### M1: Tech Analysis
| Endpoint | Файл |
|---|---|
| `/api/tech-analysis/{asset}` | inline в `server.py` |
| `/api/asset-intelligence/{asset}` | inline |
| `/api/ta-prediction/{asset}` | `routes/ta_prediction.py` |

### M2: Fractal
| Endpoint | Файл |
|---|---|
| `/api/fractal/runtime/{asset}` | `routes/fractal_runtime.py` |
| `/api/fractal/patterns` | inline |
| `/api/fractal/coverage` | inline |

### M3: OnChain (PER-ASSET)
| Endpoint | Файл |
|---|---|
| `/api/onchain/runtime/{asset}` | `routes/onchain_runtime.py` ⭐ |
| `/api/onchain/per-asset/{asset}` | inline |

### M4: Exchange (CEX)
| Endpoint | Файл |
|---|---|
| `/api/venues/all/health` | `routes/cex_intelligence_router.py` |
| `/api/exchange/order-flow/{asset}` | inline |
| `/api/exchange/funding/{asset}` | inline |
| `/api/exchange/liquidations` | inline |

### M5: Sentiment (core)
| Endpoint | Файл |
|---|---|
| `/api/sentiment/runtime` | `routes/sentiment_runtime.py` |
| `/api/sentiment/public` | `routes/sentiment_public.py` |
| `/api/sentiment/clusters` | `routes/sentiment_surface_adapters.py` |
| `/api/connections/clusters/intelligence` | `routes/sentiment_surface_adapters.py` |

---

## News & Sentiment Surface

| Endpoint | Файл | Что отдаёт |
|---|---|---|
| `/api/news/feed?limit=N&hours=H` | `routes/news_runtime.py` | Кластеризованные новости (3000+ articles) |
| `/api/news/digest` | `routes/news_runtime.py` | Daily digest |
| `/api/news/velocity` | `routes/news_runtime.py` | Velocity feeds (breaking) |
| `/api/news/analyze-url` | inline | LLM-анализ конкретной статьи по URL |
| `/api/ai-news/latest` | inline | AI-generated digest articles |
| `/api/narrative-flow` | `routes/narrative_flow_adapter.py` | Dominant narratives + inflow/outflow |
| `/api/backers` | `routes/backers_runtime.py` | VC funds с edge/power score |
| `/api/backers-alerts` | `routes/backers_alerts_router.py` | Alerts по фондам |

---

## Deep Parser

(`routes/deep_runtime.py`, регистрируется до `legacy_compat`)

| Endpoint | Что отдаёт |
|---|---|
| `/api/deep/stats` | Счётчики по всем коллекциям + bySource breakdown |
| `/api/deep/funds?limit=N&tier=Tier+1&minRoi=X` | VC fund profiles из DropsTab |
| `/api/deep/persons?limit=N&kind=influencer&minScore=X` | Influencers + fund partners с X handles |
| `/api/deep/unlocks?limit=N&phase=upcoming&symbol=ARB` | Vesting / unlock events |
| `/api/deep/projects?limit=N` | Список deep_projects (со всех 4 источников) |
| `/api/deep/projects/{slug}` | Полное досье проекта (инвесторы, раунды, persons, unlocks, events) |

---

## Twitter

(`routes/twitter_v4_router.py` + inline endpoints)

### Public (UI)
| Endpoint | Назначение |
|---|---|
| `/api/twitter/v4/feed` | Feed для Twitter tab |
| `/api/twitter/v4/actors` | Tracked actors |
| `/api/twitter/v4/clusters` | Cluster intelligence |
| `/api/twitter/v4/narratives` | Dominant narratives |

### Extension integration
| Endpoint | Метод | Назначение |
|---|---|---|
| `/api/v4/twitter/preflight-check/extension` | POST | Pre-sync check (API key + rate limits) |
| `/api/v4/twitter/sessions/webhook` | POST | Приём cookies от расширения |
| `/api/v4/twitter/ingest` | POST | Batch ingest tweets/profiles |
| `/api/v4/twitter/accounts` | GET | Список аккаунтов под мониторингом |

---

## Mobile App

(`backend/routes/mobile/*.py` + inline `/api/app/*`)

### Static serving (Expo build)
| Endpoint | Назначение |
|---|---|
| `/api/app/` | Mobile SPA index |
| `/api/app/_expo/*` | Expo bundles |
| `/api/app/assets/*`, `/api/app/static/*` | Mobile assets |
| `/api/app/{path:path}` | Mobile SPA routing fallback |

### Mobile-specific data endpoints
| Endpoint | Назначение |
|---|---|
| `/api/mobile/analytics/event` | Track events |
| `/api/mobile/user/profile` | User profile |
| `/api/mobile/notifications` | Push notification topics |

---

## Telegram MiniApp

| Endpoint | Файл | Назначение |
|---|---|---|
| `/api/miniapp/user/link-google` | inline | Линковка Google ↔ Telegram |
| `/api/miniapp/user/unlink-google` | inline | Unlink |
| `/api/miniapp/user/state` | inline | Текущее состояние юзера |
| `/api/miniapp/initdata/verify` | inline | Verify Telegram WebApp initData signature |

---

## Billing / Subscriptions

| Endpoint | Файл |
|---|---|
| `/api/billing/products` | `routes/billing_products.py` |
| `/api/billing/checkout` | `routes/billing_routes.py` |
| `/api/billing/webhook/stripe` | inline |
| `/api/billing/reconciliation` | `routes/billing_reconciliation.py` |
| `/api/billing/analytics` | `routes/billing_analytics.py` |
| `/api/me/billing` | `routes/me_billing.py` |

---

## Admin

(Все требуют admin auth via `routes/admin_auth.py`)

| Endpoint | Файл |
|---|---|
| `/api/admin/users` | `routes/admin_users.py` |
| `/api/admin/users/{id}` | `routes/admin_users.py` |
| `/api/admin/core7` | `routes/admin_core7.py` |
| `/api/admin/billing/*` | `routes/admin_billing_routes.py` |
| `/api/admin/extras` | `routes/admin_extras.py` |
| `/api/admin/crypto-billing` | `routes/admin_crypto_billing.py` |

---

## Trading & Markets

| Endpoint | Файл |
|---|---|
| `/api/market/prices` | `routes/market_prices.py` |
| `/api/trading-cases/{asset}` | `routes/trading_cases.py` |
| `/api/labs/*` | `routes/labs.py` (экспериментальные модели) |
| `/api/broker-bridge/status` | `routes/broker_bridge.py` (currently `noop`/`mode=off`) |
| `/api/testnet/exec` | `routes/testnet_exec_router.py` (admin-guarded) |

---

## Edge & Opportunities

| Endpoint | Файл |
|---|---|
| `/api/edge/opportunities` | inline (использует `services/edge_opportunities.py`) |
| `/api/alt-screener` | `routes/alt_season_routes.py` |
| `/api/alt-season-index` | inline |

---

## Static & Misc

| Endpoint | Назначение |
|---|---|
| `/api/` | Health/root |
| `/api/health` | Service health |
| `/api/assets/*` | Asset registry / logos |
| `/api/feed/*` | Generic feed (CoinGecko + Fear&Greed + news mix) |

---

## Legacy compat (catch-all)

`routes/legacy_compat.py` — **регистрируется ПОСЛЕДНИМ**. Содержит mock-стабы для UI-маршрутов, чьи реализации ещё не вынесены. Любой новый production endpoint **должен быть зарегистрирован раньше** этого роутера, иначе catch-all его проглотит.

Постепенно из этого файла переносится логика в специализированные адаптеры (`news_runtime`, `deep_runtime`, `backers_runtime`, `narrative_flow_adapter`, `sentiment_surface_adapters` уже вынесены).

---

## Тестирование API из CLI

```bash
BACKEND="http://localhost:8001"
# или из preview: BACKEND="https://fullstack-merge-app.preview.emergentagent.com"

# Health
curl -s "$BACKEND/api/" | jq

# Deep parser stats
curl -s "$BACKEND/api/deep/stats" | jq

# Top 5 VC funds
curl -s "$BACKEND/api/backers?limit=5" | jq '.bakers[] | {name, tier, totalRounds}'

# Latest news clusters
curl -s "$BACKEND/api/news/feed?limit=10" | jq '.data.clusters[] | {title, eventType, importance}'

# Per-asset on-chain
curl -s "$BACKEND/api/onchain/runtime/DOGE" | jq

# Sentiment for asset
curl -s "$BACKEND/api/sentiment/runtime?asset=BTC" | jq
```
