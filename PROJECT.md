# FOMO OS — Финальная документация проекта

> **Статус**: Production-ready, single-repo, без зависимостей на сторонние репозитории.  
> **Текущая дата фиксации состояния**: 2026-05-17.  
> Этот документ — единственный источник правды по архитектуре, модулям и развёртыванию. Все исторические аудиты, handoff-документы и snapshot-отчёты перемещены в `/app/_archive_2026-05/` и больше не используются для принятия решений.

---

## 1. Что такое FOMO OS

FOMO OS — это **Web3-аналитическая платформа** с consensus-движком **MetaBrain**, который агрегирует сигналы из 5 независимых модулей и выдаёт verdict (LONG / SHORT / HOLD) с уровнем доверия по каждому отслеживаемому активу.

Поверх движка работают:
- **Web** (React/Tailwind/Shadcn): Alpha, Fractal, Exchange, On-chain, Sentiment, Tech Analysis, Prediction, Telegram, Alerts, Settings.
- **Mobile** (Expo): тот же UX через `/api/app/...`.
- **Telegram MiniApp**: лёгкий клиент.
- **Chrome Extension "FOMO X Connect"**: «непрямой» парсинг X.com из браузера пользователя.

---

## 2. Архитектура (high-level)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                           USERS (Web / Mobile / TG)                          │
└──────────────────────────────────────────────────────────────────────────────┘
                │  Google OAuth / Telegram WebApp / Email
                ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  FastAPI Backend (port 8001) — /api/*                                        │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │ MetaBrain Consensus Engine                                              │ │
│  │   ↓ собирает verdict по каждому символу из 5 модулей ↓                   │ │
│  │ ┌───────────┐ ┌──────────┐ ┌─────────┐ ┌──────────┐ ┌─────────────────┐ │ │
│  │ │TechAnalysis│ │ Fractal  │ │OnChain  │ │ Exchange │ │   Sentiment     │ │ │
│  │ │ (CCXT OHLC)│ │ (native) │ │per-asset│ │  (CEX)   │ │ (News+Twitter+  │ │ │
│  │ │            │ │ engine   │ │         │ │          │ │  Funds+Unlocks) │ │ │
│  │ └─────┬──────┘ └────┬─────┘ └────┬────┘ └────┬─────┘ └────────┬────────┘ │ │
│  └───────┼─────────────┼────────────┼───────────┼────────────────┼──────────┘ │
│          ▼             ▼            ▼           ▼                ▼            │
│                          MongoDB (fomo_mobile)                                │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │ Collections (живые):                                                    │ │
│  │   users, sessions, twitter_*, news_articles, news_sources,              │ │
│  │   sentiment_events, deep_projects, deep_persons, deep_funds,            │ │
│  │   deep_unlocks, deep_funding_rounds, deep_project_events,               │ │
│  │   onchain_per_asset_*, mbrain_verdicts, mbrain_calibration, ...         │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────┘
                │
                │ Supervisor управляет процессами:
                ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  • backend         (FastAPI uvicorn 0.0.0.0:8001)                            │
│  • frontend        (React dev server 0.0.0.0:3000)                           │
│  • mongodb         (локально)                                                │
│  • news_substrate  (фоновый loop парсеров новостей)                          │
│  • code-server     (опционально, по умолчанию stopped)                       │
└──────────────────────────────────────────────────────────────────────────────┘
                ▲                                              ▲
                │                                              │
   POST /api/v4/twitter/sessions/webhook       External: Binance/CCXT/CoinGecko/
   (из браузерного расширения)                  CryptoCompare/Fear&Greed/RSS/Dropstab/
                                                CryptoRank/ICODrops/CoinMarketCap
```

### Принципы

1. **Single-repo**: всё (backend, frontend, mobile, extension) в `/app`. Никаких внешних submodule.
2. **`/api/*` для backend**: kubernetes ingress маршрутизирует `/api/*` на 8001, остальное на frontend 3000.
3. **MongoDB UUIDs** (не ObjectId) — для портативности.
4. **Datetime в UTC** (`datetime.now(timezone.utc)`).
5. **Real data only**: legacy mock-стабы остаются только в `routes/legacy_compat.py` как safety-сетка и обходятся через явный порядок регистрации роутеров.

---

## 3. Пять модулей MetaBrain

Все модули **live**, генерируют сигналы по реальным данным и пишут результат в коллекцию `mbrain_verdicts`.

### 3.1 Tech Analysis (TA)
- **Файлы**: `backend/services/exchange/*`, `backend/services/asset_intelligence.py`.
- **Источник**: CCXT OHLC (Binance / Bybit / OKX) + кэш `services/bar_data.py`.
- **Что считает**: RSI, MACD, EMA-cross, support/resistance.
- **Endpoint UI**: `/api/tech-analysis/*`.

### 3.2 Fractal
- **Файлы**: `backend/services/fractal_generator.py`, `backend/services/fractal_runtime.py`, `backend/routes/fractal_runtime.py`.
- **Источник**: own native fractal engine, на исторических OHLC.
- **Что считает**: похожие паттерны и их разрешения за окно N дней.
- **Endpoint UI**: `/api/fractal/*`, `/api/fractal/runtime/{asset}`.

### 3.3 On-chain (PER-ASSET)
- **Файлы**: `backend/services/onchain_per_asset.py`, `backend/routes/onchain_runtime.py`.
- **Источник**: chain-level metrics + per-symbol адаптеры (DOGE, ARB, ETH, etc.).
- **Что считает**: TVL дельта, активные адреса, объём транзакций, баланс китов.
- **Endpoint UI**: `/api/onchain/runtime/{asset}` ← регистрируется **ДО** `legacy_compat`.

### 3.4 Exchange (CEX)
- **Файлы**: `backend/services/exchange/*`, `backend/cex_intelligence/*`.
- **Источник**: live Binance/Bybit/OKX order-flow, OI, funding, liquidations.
- **Что считает**: давление покупателей/продавцов, аномалии в funding и OI.
- **Endpoint UI**: `/api/venues/all/health`, `/api/exchange/*`.

### 3.5 Sentiment ⭐ (восстановлен в этой сессии полностью)
- **Файлы**: 
  - News: `backend/scripts/run_rss_pipeline.py`, `backend/services/news_substrate_loop.py`, `backend/routes/news_runtime.py`.
  - Twitter: `backend/scripts/twitter_sentiment_step.py`, `backend/modules/twitter_parser/*`.
  - Deep parser (Funds/Persons/Unlocks/Projects): `backend/services/deep_parser.py`, `backend/routes/deep_runtime.py`.
  - Surface adapters: `backend/routes/sentiment_surface_adapters.py`, `backend/routes/backers_runtime.py`, `backend/routes/narrative_flow_adapter.py`.
- **Источники (живые)**:
  - 119 RSS-источников (CoinDesk, CoinTelegraph, TheBlock, Decrypt, Blockworks, BeInCrypto в 6 языках, Reddit r/Bitcoin/r/CryptoMarkets/r/DeFi/..., Vitalik blog, YT channels, etc.).
  - Twitter Hybrid V2 (L0 cookies → L1 twscrape → L2 Playwright fallback → L3 manual) — данные приходят через **Chrome Extension** (см. §5).
  - CoinGecko, CryptoCompare News, Fear & Greed Index.
  - **Deep parser** для SPA-сайтов (Next.js `__NEXT_DATA__` extraction):
    - **DropsTab** → vesting/unlocks, инвесторы, фонды, портфели VC.
    - **CryptoRank** → ICO раунды, tokenomics.
    - **ICODrops** → hype/risk/ROI rates.
    - **CoinMarketCap** → token unlocks (best-effort: data-api геоблокирован для дата-центров, используем SSR + честный fallback с `hasData=False` и зафиксированной причиной).
- **Что считает**: 
  - Cluster Intelligence (organic vs pump-like координация),
  - Dominant Narratives (BTC/ETH/SOL/...),
  - Capital flow (inflow/outflow), 
  - Risk Alerts (CAS score),
  - Backers ranking (Variant, a16z, Polychain, Paradigm и т.д. с реальным Tier/ROI/Portfolio).
- **Endpoint UI**: `/api/sentiment/*`, `/api/news/feed|digest|velocity`, `/api/backers`, `/api/deep/{stats,funds,persons,unlocks,projects}`.

---

## 4. Google авторизация

### 4.1 Поток (mobile/web)
1. Клиент получает Google `id_token` через стандартный Google Identity Services SDK (web) или нативный Google Sign-In (mobile).
2. Клиент шлёт `POST /api/mobile/auth/google` с body `{ "idToken": "..." }`.
3. Backend (`routes/mobile_auth.py:google_auth`) валидирует токен через `google.oauth2.id_token.verify_oauth2_token` с публичными ключами Google.
4. Извлекаются: `email`, `name`, `picture`, `googleId` (sub), `email_verified`.
5. Find-or-create в `users` коллекции (UUID-based `_id`, поля: `plan=FREE`, `authProviders.google=True`, `access` flags, `referrals.code`).
6. Возвращается JWT-сессия + user profile.

### 4.2 Env-переменные
- `GOOGLE_CLIENT_ID` (одно значение для verify_oauth2_token; web и mobile должны использовать совпадающий audience).
- Опционально: `GOOGLE_CLIENT_SECRET` (если потребуется server-side OAuth flow; на сегодня не используется).

### 4.3 MiniApp (Telegram) linking
- `POST /api/miniapp/user/link-google` — линкует Google email с уже существующим Telegram identity.
- `POST /api/miniapp/user/unlink-google` — отвязка.
- Реализация в `miniapp/user_state.py`.

### 4.4 Что нужно сделать при добавлении нового OAuth-клиента
1. В Google Cloud Console → OAuth 2.0 Client IDs → создать "Web/Android/iOS" клиент.
2. Добавить `https://fullstack-merge-app.preview.emergentagent.com` (или production URL) в "Authorized JavaScript origins".
3. Указать redirect URI (если ожидается server-side flow): `<URL>/api/mobile/auth/google/callback`.
4. Положить `client_id` в `/app/backend/.env` как `GOOGLE_CLIENT_ID=...`.
5. Перезапустить backend: `supervisorctl restart backend`.

---

## 5. Chrome Extension "FOMO X Connect"

### 5.1 Зачем
Backend **никогда не делает прямые запросы** к Twitter/X — иначе IP датацентра моментально блокируется. Вместо этого расширение работает **из браузера живого пользователя**, видит реальный IP/cookies/fingerprint, и отдаёт собранные данные на backend для хранения.

### 5.2 Расположение
- Source: `/app/backend/admin_build/fomo_extension_v1.3.0/`
- Так же доступен через web: `/app/frontend/public/fomo_extension_v1.3.0/`
- Manifest V3, Chrome ≥ 116.

### 5.3 Структура
```
fomo_extension_v1.3.0/
├── manifest.json                   # MV3 config (cookies + storage permissions, twitter.com/x.com host)
├── background.js                   # Service worker
├── popup.html / popup.js           # UI расширения (API key + URL платформы)
├── twitter-fetcher.js              # Запросы к Twitter Graph API из браузера
├── cookie-quality-checker.js       # Проверка валидности auth_token / ct0
├── backend-error-mapper.js         # Маппинг ошибок backend ↔ UX-сообщения
└── icons/                          # Иконки расширения
```

### 5.4 Поток данных
```
[User Browser + Extension] ──(1)──> twitter.com / x.com (Graph API)
         ▲                                  │
         │                                  │ (2) response (tweets, profiles)
         │                                  ▼
         │                          [User Browser + Extension]
         │                                  │
         │   (4) sync                       │ (3) POST /api/v4/twitter/sessions/webhook
         │     ack                          ▼
         └────────────────────  FOMO Backend  ◄── store: twitter_tweets, twitter_accounts
```

### 5.5 Backend endpoints для расширения
- `POST /api/v4/twitter/preflight-check/extension` — перед синхронизацией: проверка API key и rate-limits.
- `POST /api/v4/twitter/sessions/webhook` — приём cookies для session sync.
- `POST /api/v4/twitter/ingest` — приём ботчей tweets/profiles.
- `GET  /api/v4/twitter/accounts` — список аккаунтов под мониторингом.

### 5.6 Установка для пользователя
1. `chrome://extensions/` → Developer mode ON.
2. Load unpacked → выбрать `fomo_extension_v1.3.0`.
3. Залогиниться на x.com.
4. Открыть popup → ввести `API_URL` (https://...) и `API_KEY` (выдаётся в Settings web).
5. "Sync Session" → cookies улетят на backend, далее расширение начнёт сабмиттить fetched данные.

### 5.7 Безопасность
- Cookies хранятся только в `chrome.storage.local` (зашифровано браузером).
- API key — в `chrome.storage.local`.
- Все запросы HTTPS.
- Backend никогда не возвращает cookies наружу — только идентификатор session.

---

## 6. Логика Sentiment (детально)

### 6.1 Источники → таблицы

| Источник | Скрипт | Куда пишет | Частота |
|---|---|---|---|
| 119 RSS | `scripts/run_rss_pipeline.py` | `news_articles`, `sentiment_events` | каждый запуск (вручную или supervisor `news_substrate`) |
| Twitter (через Extension) | `modules/twitter_parser/*` + `scripts/twitter_sentiment_step.py` | `twitter_tweets`, `twitter_accounts`, `sentiment_events` | непрерывно (browser-driven) |
| Twitter (Playwright L2 fallback) | `scripts/twitter_sentiment_step.py` | то же | при отсутствии extension |
| CoinGecko | `services/feed_service.py` | `sentiment_events` | feed loop |
| CryptoCompare News | `services/news_intelligence.py` | `news_articles` | каждые 15 мин |
| Fear & Greed | `services/feed_service.py` | `sentiment_events` | 1× час |
| DropsTab (vesting, funds, persons) | `services/deep_parser.py` | `deep_unlocks`, `deep_funds`, `deep_persons`, `deep_projects` | 6 час (loop) |
| CryptoRank | `services/deep_parser.py` | `deep_projects`, `deep_funding_rounds` | 6 час |
| ICODrops | `services/deep_parser.py` | `deep_projects` (+ ROI/risk/hype) | 6 час |
| CoinMarketCap unlocks | `services/deep_parser.py` (`_coinmarketcap_scrape_unlock`) | `deep_unlocks` (kind=`cmc_unlock_latest`) | 6 час, best-effort |

### 6.2 Surface adapters (то, что видит React UI)
Все эти эндпоинты регистрируются в `server.py` **ДО** `legacy_compat_router`, иначе catch-all его проглотит:

| Endpoint | Адаптер | Что отдаёт |
|---|---|---|
| `/api/news/feed`, `/digest`, `/velocity` | `routes/news_runtime.py` | кластеризованные новости из `news_articles` |
| `/api/backers` | `routes/backers_runtime.py` | объединённые VC из `deep_funds` (DropsTab) + `funds` (ICODrops legacy) с edge/power score |
| `/api/connections/clusters/intelligence` | `routes/sentiment_surface_adapters.py` | cluster intelligence (OVERHEATED/HEALTHY) |
| `/api/narrative-flow` | `routes/narrative_flow_adapter.py` | dominant narratives + inflow/outflow |
| `/api/deep/{stats,funds,persons,unlocks,projects}` | `routes/deep_runtime.py` | прямой доступ к deep_* коллекциям |
| `/api/onchain/runtime/{asset}` | `routes/onchain_runtime.py` | per-asset on-chain metrics |

### 6.3 Известные ограничения
- **CMC `data-api` геоблокирован** для дата-центров (возвращает китайскую 404). Парсер использует SSR-страницы `/currencies/{slug}/` и фиксирует `hasData=False` с причиной — это видно в `/api/deep/unlocks?source=coinmarketcap`.
- **Twitter Hybrid V2** требует свежих cookies (auth_token, ct0) от живого аккаунта; их обновляет расширение или `scripts/import-twitter-cookies.ts`.

---

## 7. Что было пройдено (история проблем)

> Намеренно не пересказываем все аудиты. Только реальные технические уроки.

| Проблема | Где было | Решение |
|---|---|---|
| Sentiment UI показывал пустые tabs | React fetched из `legacy_compat.py` mock-стабов | Создали `news_runtime`, `sentiment_surface_adapters`, `backers_runtime`, `narrative_flow_adapter`. Зарегистрировали их **до** `legacy_compat_router` в `server.py`. |
| Парсеры (DropsTab/CryptoRank/ICODrops) тянули только homepage | Next.js SPA, реальные данные в `__NEXT_DATA__` | Создан `services/deep_parser.py` который извлекает `<script id="__NEXT_DATA__">` JSON напрямую. |
| `DuplicateKeyError` в `deep_unlocks/funding_rounds/events` | `**ul` перезаписывал поле `id` raw-значением провайдера (часто `None`) | Перенесли `id: composed_uid` **после** `**ul` в payload. |
| CMC unlock data | api-домен геоблокирован | Best-effort SSR-парсер + честный fallback с `hasData=False`. |
| OnChain был chain-level заглушкой | Не дифференцировал DOGE и ARB | `services/onchain_per_asset.py` + предпочтение per-asset в `_fetch_onchain()`. |
| Twitter rate-limited при прямых запросах с backend | Datacenter IP | Chrome Extension работает из браузера пользователя. |
| `/api/venues/all/health` ~25s | Без кэширования | TTL cache + safe timeouts. |
| Frontend BTCUSDT vs BTC | Несовпадение в universe | Каноникализация символов в едином месте. |

---

## 8. Развёртывание

### 8.1 Quick start (один скрипт)
```bash
bash /app/scripts/bootstrap.sh
```
Что он делает:
1. Проверяет наличие `MONGO_URL` и `DB_NAME=fomo_mobile` в `backend/.env`.
2. Устанавливает Python зависимости (`pip install -r backend/requirements.txt`) и Node (`yarn install` в `frontend/`).
3. Запускает все supervisor-сервисы и ждёт их готовности.
4. Seed: создаёт индексы (`scripts/ensure_indexes.py`), запускает `news_sources` seed (`scripts/seed_news_sources.py` если есть), и один прогон RSS пайплайна.
5. Запускает один цикл `deep_parser` (RSS unlocks + funds + persons).
6. Verify: `curl` 7 ключевых endpoint'ов и печатает статус.

### 8.2 Sentiment-only refresh
```bash
bash /app/scripts/run_sentiment.sh
```
Гоняет: RSS pipeline (119 источников) → deep_parser cycle (CryptoRank/ICODrops/DropsTab/CMC) → twitter_sentiment_step (если есть cookies).

### 8.3 Ручной контроль сервисов
```bash
supervisorctl status                       # все процессы
supervisorctl restart backend              # backend hot reload включён, обычно не нужен
tail -n 100 /var/log/supervisor/backend.*.log
```

### 8.4 Env-переменные (backend/.env)
| Ключ | Назначение | Обязательность |
|---|---|---|
| `MONGO_URL` | mongodb://localhost:27017 | да |
| `DB_NAME` | fomo_mobile | да |
| `EMERGENT_LLM_KEY` | универсальный ключ OpenAI/Anthropic/Gemini для Sentiment Neural Model | да (для AI features) |
| `GOOGLE_CLIENT_ID` | Google OAuth audience | да (для Google login) |
| `DEEP_PARSER_ENABLED` | true/false | опционально (по умолчанию true) |
| `DEEP_PARSER_INTERVAL_SEC` | секунды между циклами deep_parser | опционально (по умолчанию 21600) |

### 8.5 Frontend env (`frontend/.env`)
- `REACT_APP_BACKEND_URL` — **не модифицировать**, управляется платформой.

---

## 9. Файловая структура (production-relevant)

```
/app/
├── PROJECT.md                ← ЭТОТ ФАЙЛ
├── README.md                 ← краткий quick-start
├── ARCHITECTURE.md           ← detailed архитектура (legacy ref)
├── DEPLOYMENT.md             ← deployment notes (legacy ref)
├── plan.md                   ← текущий план разработки
├── test_result.md            ← результаты последних тестов
│
├── scripts/                  ← deployment scripts
│   ├── bootstrap.sh          ← всё-в-одном развёртывание
│   └── run_sentiment.sh      ← полный Sentiment refresh
│
├── backend/                  ← FastAPI
│   ├── server.py             ← все роутеры регистрируются здесь
│   ├── .env                  ← MONGO_URL, DB_NAME, GOOGLE_CLIENT_ID, EMERGENT_LLM_KEY
│   ├── requirements.txt
│   ├── routes/
│   │   ├── deep_runtime.py           ← /api/deep/*
│   │   ├── news_runtime.py           ← /api/news/*
│   │   ├── sentiment_surface_adapters.py
│   │   ├── backers_runtime.py        ← /api/backers
│   │   ├── narrative_flow_adapter.py
│   │   ├── onchain_runtime.py        ← /api/onchain/runtime/*
│   │   ├── mobile_auth.py            ← Google + email + phone auth
│   │   ├── auth.py / auth_gate.py    ← web auth + paywall gate
│   │   ├── legacy_compat.py          ← catch-all safety net (регистрируется ПОСЛЕДНИМ)
│   │   └── ...
│   ├── services/
│   │   ├── deep_parser.py            ← DropsTab/CryptoRank/ICODrops/CMC parser
│   │   ├── onchain_per_asset.py
│   │   ├── feed_service.py
│   │   ├── news_intelligence.py
│   │   ├── fractal_runtime.py
│   │   └── ...
│   ├── scripts/
│   │   ├── run_rss_pipeline.py       ← 119 RSS sources → news_articles
│   │   ├── news_substrate_loop.py    ← supervisor loop
│   │   ├── twitter_sentiment_step.py ← Twitter ingestion (L0→L3)
│   │   └── ...
│   ├── modules/twitter_parser/       ← Hybrid V2 native engine
│   ├── admin_build/fomo_extension_v1.3.0/  ← Chrome Extension source
│   └── ...
│
├── frontend/                 ← React SPA (CRA)
│   ├── src/
│   │   ├── pages/
│   │   │   ├── twitter/      ← Sentiment tabs (Overview/Prediction/Feed/Actors/Graph/Network/Market/Backers/News)
│   │   │   ├── connections/  ← ClustersNetworkPage, BakeryPage
│   │   │   └── ...
│   │   └── components/ui/    ← Shadcn UI
│   ├── public/fomo_extension_v1.3.0/  ← extension доступен для скачивания пользователем
│   └── package.json
│
├── mobile/                   ← Expo build (выкладывается через /api/app/)
│
└── _archive_2026-05/         ← все старые аудиты, handoff, snapshot-отчёты (ROOT для очистки)
    ├── audit_repos_2GB/      ← старые клоны проектов (2.2GB)
    ├── memory_snapshots/     ← 46 .md из старого memory/
    ├── handoffs/
    ├── phase_reports/
    └── backend_test_legacy/
```

---

## 10. Validation checklist (то, что должно работать после bootstrap)

| # | Что проверяем | Команда / endpoint | Ожидаемо |
|---|---|---|---|
| 1 | Все процессы живы | `supervisorctl status` | backend, frontend, mongodb, news_substrate → RUNNING |
| 2 | Backend жив | `curl -s :8001/api/health` или `/api/ping` | 200 OK |
| 3 | News пайплайн | `curl :8001/api/news/feed?limit=5` | `ok:true`, clusters > 0 |
| 4 | Deep parser работает | `curl :8001/api/deep/stats` | counts по проектам/фондам/unlocks/persons > 0 |
| 5 | Backers (real VC) | `curl :8001/api/backers?limit=3` | Variant/a16z/Paradigm etc. с real twitterUrl |
| 6 | OnChain per-asset | `curl :8001/api/onchain/runtime/DOGE` | реальные метрики, не chain-level fallback |
| 7 | Sentiment Overview в UI | открыть `/twitter` в preview URL | Accounts > 0, Verified > 0, narratives > 0 |
| 8 | MongoDB | `mongo fomo_mobile --eval 'db.news_articles.count()'` | > 3000 |
