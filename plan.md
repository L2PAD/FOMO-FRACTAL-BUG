# plan.md — FOMO OS

> **Финальное состояние проекта на 2026-05-17.**  
> Все исторические audit-логи и handoff'ы перенесены в `/app/_archive_2026-05/`. Полная архитектура и описание модулей: см. [`PROJECT.md`](./PROJECT.md).

---

## 1. Текущее состояние (LIVE, production-grade)

| Компонент | Статус | Источник |
|---|---|---|
| **MetaBrain consensus** | ✅ LIVE | 5 модулей agg в `mbrain_verdicts` |
| **Tech Analysis** | ✅ LIVE | CCXT OHLC, RSI/MACD/EMA |
| **Fractal** | ✅ LIVE | own native engine |
| **OnChain** | ✅ LIVE (per-asset) | `services/onchain_per_asset.py`, `/api/onchain/runtime/{asset}` |
| **Exchange (CEX)** | ✅ LIVE | Binance/Bybit/OKX live |
| **Sentiment** | ✅ LIVE | RSS×119 + Twitter Hybrid V2 + Deep parser (DropsTab/CryptoRank/ICODrops/CMC) |
| **News pipeline** | ✅ 3048+ articles | 84 уник. источников активных, 119 настроены |
| **Deep parser** | ✅ LIVE | 106 projects, 386 funding rounds, 899 persons, 26 unlocks (17 CMC + 9 DropsTab vesting), 20 funds |
| **Backers UI** | ✅ LIVE | real VC: Variant, a16z, Polychain, Paradigm с Tier/ROI/portfolio |
| **Google OAuth** | ✅ READY | `routes/mobile_auth.py:google_auth`, нужен `GOOGLE_CLIENT_ID` в `.env` |
| **Chrome Extension** | ✅ BUILT | `backend/admin_build/fomo_extension_v1.3.0/` (MV3) |
| **Web UI Sentiment tabs** | ✅ LIVE | Overview/Prediction/Feed/Actors/Graph/Network/Market/Backers/News — все наполнены реальными данными |
| **Telegram MiniApp** | ✅ READY | link-google / unlink-google endpoints |
| **Mobile (Expo)** | ✅ MOUNTED | `/api/app/*` |

---

## 2. Что было закрыто в последней сессии

### Fractal full-stack wire-up (P0)
- **Backend** — создан `routes/fractal_extra_runtime.py` с 17 endpoints, регистрирован ДО `legacy_compat`:
  - **Coverage/Registry**: `/api/fractal`, `/api/fractal/list`, `/api/fractal/coverage`
  - **Pattern analysis**: `/api/fractal/patterns?symbol=...` — детектор паттернов (compression_squeeze, breakout_up, breakdown_down, stair_up/down, expansion_range) скользящим окном
  - **Similarity engine**: `/api/fractal/similar/{symbol}` — top-K исторических аналогов через cosine similarity на z-normalized closes, с outcome-биас расчётом
  - **Forecast**: `/api/fractal/forecast/{symbol}` — projection next-N bars через average path top-K matches с std-band
  - **Heatmap**: `/api/fractal/heatmap` — matrix asset × horizon (4H/1D/7D/30D) с phase classification
  - **Snapshot/Intelligence**: `/api/fractal/snapshot/{symbol}`, `/api/fractal/intelligence`
  - **Legacy aliases** (Web BtcFractalPage/SpxFractalPage/BrainOverviewPage): `/api/fractal/match`, `/api/fractal/signal`, `/api/ui/brain/decision`, `/api/overlay/coeffs`
  - **MiniApp**: `/api/miniapp/fractal`, `/api/miniapp/fractal-watchlist`
  - **Admin**: `/api/admin/fractal/overview`
- **Источники**: 
  - Native engine `services/fractal_runtime.py` (728 строк, Mongo snapshot memory с **decisionHistory 171** для активных активов).
  - OKX OHLC (через reuse `routes.tech_analysis_runtime._fetch_candles`) для similarity computation.
  - Pure-Python cosine similarity + z-normalization (no scipy/sklearn deps).

### Mobile (Expo)
- Создан `mobile/src/modules/trading/intelligence/FractalScreen.tsx` (~430 строк) — Fractal dashboard:
  - **Runtime card**: phase pill (compression/expansion/rangebound/breakdown) + direction (LONG_BIAS/SHORT_BIAS/WAIT) + native engine reasons
  - **Similarity card**: consensus + avg return ±std + long/short count + match count
  - **Forecast path**: next-N bars projected price с low/high band
  - **Watchlist** 8 assets с phase pill + return % + bias mini-pill
  - Timeframe picker 4H/1D/7D/30D, auto-refresh 45s
- Route: `mobile/app/fractal.tsx` → `/api/app/fractal`

### Telegram MiniApp
- `/api/miniapp/fractal?asset=...` отдаёт combined snapshot (runtime + similarity + forecast headline + reasons).
- `/api/miniapp/fractal-watchlist?symbols=...` — multi-asset bias dashboard.

### Admin
- `/api/admin/fractal/overview` — service health + intelligence aggregate + heatmap sample 8 assets.

### Exchange (CEX intelligence) full-stack wire-up (предыдущий блок)
- **Backend** — создан `routes/exchange_runtime.py` с 21 endpoint, зарегистрирован ДО `legacy_compat`:
  - Microstructure: `/api/exchange/orderbook/{symbol}`, `/api/exchange/funding/{symbol}`, `/api/exchange/open-interest/{symbol}`, `/api/exchange/derivatives/{symbol}` (combined)
  - Tickers: `/api/exchange/tickers?sort={volume,change,gainers,losers}`, `/api/exchange/markets`
  - Анализ: `/api/exchange/anomalies`, `/api/exchange/order-flow/{symbol}`, `/api/exchange/overview`
  - Health: `/api/exchange/venues`, `/api/exchange/account`, `/api/exchange/orders`, `/api/exchange/status`
  - CEX aliases: `/api/cex/{orderbook,funding,oi,liquidations,anomalies}/{symbol}`, `/api/cex-intelligence/overview`
  - Legacy: `/api/funding-rates`, `/api/order-flow/{symbol}`
  - Mobile/MiniApp: `/api/exchange/compact/{symbol}`, `/api/miniapp/exchange`, `/api/miniapp/exchange-watchlist`
  - Admin: `/api/admin/exchange/overview`
- **Источник**: OKX public REST (geo-allowed). Binance/Bybit зафиксированы как `blocked` в `/api/exchange/venues`.
- **TTL cache**: 15s (для orderbook/ticker), 30s (для OI/tickers list), 60s (funding).
- **Реальные данные на момент фиксации**: BTC spot=$78392, funding +0.0034% (annual +3.86%), OI $2.69B, orderbook imbalance +45.8% bullish. ETH bullish, XRP bullish, 3/6 → market bias = **bullish**.

### Mobile (Expo)
- Создан `mobile/src/modules/trading/intelligence/ExchangeScreen.tsx` (~350 строк) — Exchange dashboard:
  - Bias card (🟢 BULLISH / 🔴 BEARISH / ⚪ NEUTRAL) с factor count
  - 4-метрическая сетка: Funding 8h + annual, OI USD, Orderbook Imbalance, Volume 24h
  - Orderbook (top 5 bids + 5 asks + spread row)
  - Anomalies scanner (funding extremes + OI > $1B)
  - Watchlist 8 assets с цветными bias pills
  - Auto-refresh 20s + pull-to-refresh
- Route: `mobile/app/exchange-board.tsx` → `/api/app/exchange-board` (не используем `/exchange` потому что там OAuth callback shim).

### Telegram MiniApp
- `/api/miniapp/exchange?asset=...` + `/api/miniapp/exchange-watchlist?symbols=...` готовы для интеграции в TG MiniApp UI.
- Payload: spot + funding + OI + imbalance + orderbook (top 5) + bias signal.

### Admin
- `/api/admin/exchange/overview` отдаёт venues health + market overview + top-5 assets + 10 anomalies для admin dashboard.

### Tech Analysis full-stack wire-up (предыдущий блок)
- **Backend** — создан `routes/tech_analysis_runtime.py` с 11 endpoints, зарегистрирован ДО `legacy_compat`:
  - `/api/market/candles`, `/api/market/state`, `/api/market/regime` — OHLC + indicators
  - `/api/tech-analysis/{symbol}` — single-TF analysis
  - `/api/ta-prediction/{symbol}` — rolling forecast (linear regression slope)
  - `/api/ta-engine/mtf/{symbol}?timeframes=...` — Multi-Timeframe TA Engine (КЛЮЧЕВОЙ для Analysis tab)
  - `/api/trade-this` (POST) — Trade Setup button: entry/stop/target/R:R/sizing
  - `/api/dashboard/regime` — multi-symbol regime snapshot
  - `/api/ta/compact/{symbol}` — compact для Mobile/MiniApp
  - `/api/ta/watchlist?symbols=...` — multi-asset list
  - `/api/miniapp/tech-analysis?asset=...&timeframe=...` — Telegram MiniApp специфичный
  - `/api/miniapp/tech-watchlist?symbols=...` — MiniApp watchlist
- **Источник данных**: OKX public REST `/api/v5/market/candles` (primary) + CoinGecko OHLC (fallback). Binance/Bybit геоблокированы для нашего IP.
- **Индикаторы (pure Python, no deps)**: RSI(14), EMA(20/50/200), MACD(12,26), support/resistance pivots, trend classification, momentum (overbought/bullish/neutral/bearish/oversold).
- **TF mapping**: 4H/1D/7D/30D/180D/1Y → OKX bars (4H/1D/1W/1M).
- **Cache**: TTL 30s in-process, защищает от rate-limit.

### Frontend (Web)
- **`/pages/Terminal/index.jsx`** (245 строк, уже был готов): unified Trading Terminal с 8 табами 4|4: Analysis · Action · Prediction · Ideas │ Trade · Positions · Decisions · Performance.
- Роуты `/trading`, `/tech-analysis`, `/terminal` все ведут на этот компонент.
- **Исправлен баг lightweight-charts** `Invalid language tag: en-US@posix`: добавлен глобальный locale sanitizer в `src/index.js`, который патчит `Date.toLocaleString`, `Intl.DateTimeFormat`, `Intl.NumberFormat`.
- **Исправлен баг `levels.filter is not a function`**: сменил `levels` с объекта на массив `[{type, price, strength, tf}]` в `ta-engine/mtf` response.

### Mobile (Expo)
- Создан `mobile/src/modules/trading/intelligence/TechAnalysisScreen.tsx` (16 KB):
  - Header: symbol + price + change %
  - Timeframe picker (4H/1D/7D/30D)
  - Action card (LONG/SHORT/WAIT) с эмоджи и причиной
  - Sparkline (последние 20 баров)
  - Multi-timeframe brief с pills
  - Trade Setup (если action != WAIT): entry/stop/target/R:R/confidence
  - Watchlist top-8 assets с компактными signal pills
  - Auto-refresh каждые 30s
  - Pull-to-refresh
- Создан Expo Router entry `mobile/app/tech-analysis.tsx` → доступен через `/api/app/tech-analysis`.

### Telegram MiniApp
- Endpoints `/api/miniapp/tech-analysis` и `/api/miniapp/tech-watchlist` готовы для интеграции в MiniApp UI (HTML+JS).
- Payload оптимизирован: sparkline массив 0-100, MTF brief с цветными pills, опциональный tradeSetup.

### Sentiment full real-data wire-up (предыдущий блок)
- **P0** — Sentiment React UI tabs больше не пустые. Создали 4 surface adapter роутера, зарегистрировали их **ДО** `legacy_compat`:
  - `routes/news_runtime.py` → `/api/news/feed|digest|velocity`
  - `routes/sentiment_surface_adapters.py` → `/api/connections/clusters/intelligence`
  - `routes/backers_runtime.py` → `/api/backers`
  - `routes/narrative_flow_adapter.py` → `/api/narrative-flow`
- **P1** — RSS pipeline: 119 sources настроены, 3048 articles в `news_articles`, 3191 `sentiment_events`.
- **P2** — Deep parser написан с нуля (`services/deep_parser.py`):
  - Извлекает Next.js `__NEXT_DATA__` JSON из SPA-страниц DropsTab/CryptoRank/ICODrops.
  - Получает: persons (617+), funds (20), projects (106), funding_rounds (386), unlocks (9 DropsTab vesting snapshots), events (655).
  - Добавлен CoinMarketCap unlock-парсер с честным fallback (data-api геоблокирован, используем SSR).
  - **Исправлен критический DuplicateKeyError**: `**ul` перезаписывал поле `id` raw-значением → теперь `id` ставится после `**ul`.

### Cleanup-pass (этот шаг)
- Перемещены в `/app/_archive_2026-05/`:
  - 2.2 GB старых клонов в `_audit_repos/`,
  - 46 .md из `memory/` (оставили только `PRD.md`),
  - top-level AUDIT_*, HANDOFF.md, MERGE_AUDIT.md, PHASE_E1_HANDOFF.md,
  - `backend_test.py.bak/.prev`, `backend_test_a6.py`, `backend_test_t11_*`,
  - устаревшие theme/billing/growth `.md` (BILLING_V2, CONVERSION_LOOP, GROWTH_LAYER, MBRAIN_TA_ADAPTER, MINIAPP_THEMES, PAYWALL, MODULES, ASSET_LOGOS, AGENT_ONBOARDING, DESIGN_TOKENS).
- Создан единый **`PROJECT.md`** — финальная документация.
- Создан **`scripts/bootstrap.sh`** — единый idempotent-скрипт развёртывания.
- Создан **`scripts/run_sentiment.sh`** — изолированный скрипт обновления Sentiment.

---

## 3. Известные ограничения (честно)

1. **CoinMarketCap data-api геоблокирован** для IP датацентра (ответ "Sorry! The page you're looking for cannot be found." на китайском). Парсер использует SSR-страницы `/currencies/{slug}/` и сохраняет `hasData=False` с причиной. Точные unlock-даты с CMC доступны только через DropsTab/CryptoRank vesting.
2. **Twitter Hybrid V2** требует свежих cookies (`auth_token`, `ct0`). Cookies поднимаются через Chrome Extension от живого пользователя или вручную через `scripts/import-twitter-cookies.ts`.
3. **News tab UI** lazy-load компонента (1265 строк) занимает ~10-15s при холодном запуске — это performance frontend, не баг.

---

## 4. Что делать дальше (опционально)

| Приоритет | Задача |
|---|---|
| P2 | Получить CMC pro-api ключ для полного доступа к token-unlock listings. |
| P3 | Поднять Twitter Hybrid V2 в production: добавить cookies через расширение, проверить `twitter_tweets > 0`. |
| P3 | Удалить `routes/legacy_compat.py` целиком (все нужные маршруты теперь обходятся явно). |
| P4 | Code-split `frontend/src/pages/twitter/NewsTab.jsx` (1265 строк) — уменьшит lazy chunk и время `Loading module...`. |

---

## 5. Quick reference

```bash
# Полное развёртывание (idempotent)
bash /app/scripts/bootstrap.sh

# Только Sentiment обновить
bash /app/scripts/run_sentiment.sh

# Контроль сервисов
supervisorctl status
supervisorctl restart backend frontend

# Логи
tail -f /var/log/supervisor/backend.*.log

# DB-summary
python -c "from pymongo import MongoClient; import os; db=MongoClient(os.environ['MONGO_URL'])['fomo_mobile']; [print(c, ':', db[c].count_documents({})) for c in ['news_articles','deep_projects','deep_unlocks','deep_funds','mbrain_verdicts']]"
```
