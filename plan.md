# plan.md — FOMO OS

> **Финальное состояние проекта на 2026-05-18 (обновлено).**  
> Все исторические audit-логи и handoff'ы перенесены в `/app/_archive_2026-05/`. Полная архитектура и описание модулей: см. [`PROJECT.md`](./PROJECT.md).

---

## 1. Текущее состояние (LIVE, production-grade)

| Компонент | Статус | Источник |
|---|---|---|
| **MetaBrain consensus** | ✅ LIVE | 5 модулей agg в `mbrain_verdicts` |
| **Tech Analysis (TA)** | ✅ LIVE (full-stack, zero stubs) | `services.technical_analysis` (native_ta_v1) + OKX/CoinGecko candles (`tech_analysis_runtime`) |
| **Fractal** | ✅ LIVE | own native engine + sidecar cosine-similarity |
| **OnChain — Light Mode (Infura)** | ✅ LIVE (full-stack, zero stubs, **без индексера**) | `onchain_lite` (Infura RPC) + DefiLlama (stablecoins/bridges/TVL/DEX) + onchain_overview runtime |
| **Exchange (CEX)** | ✅ LIVE (full-stack, **zero stubs**, 49 endpoints) | OKX public REST live + Mongo `exchange_forecasts`/`exchange_forecast_runs`/`paper_orders_v2` + live venue ping |
| **Sentiment** | ✅ LIVE | RSS×119 + Twitter Hybrid V2 + Deep parser (DropsTab/CryptoRank/ICODrops/CMC) |
| **News pipeline** | ✅ 3048+ articles | 84 уник. источников активных, 119 настроены |
| **Deep parser** | ✅ LIVE | 106 projects, 386 funding rounds, 899 persons, 26 unlocks, 20 funds |
| **Backers UI** | ✅ LIVE | real VC: Variant, a16z, Polychain, Paradigm с Tier/ROI/portfolio |
| **Google OAuth** | ✅ READY | `routes/mobile_auth.py:google_auth`, нужен `GOOGLE_CLIENT_ID` в `.env` |
| **Chrome Extension** | ✅ BUILT | `backend/admin_build/fomo_extension_v1.3.0/` (MV3) |
| **Web UI Sentiment tabs** | ✅ LIVE | Overview/Prediction/Feed/Actors/Graph/Network/Market/Backers/News — все наполнены реальными данными |
| **Telegram MiniApp** | ✅ READY | использует общий backend `/api/miniapp/*` |
| **Mobile (Expo web export /m)** | ✅ LIVE | статический экспорт + backend `/api/miniapp/*` и `/api/app/*` |

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

### Mobile (Expo) — Fractal
- Создан `mobile/src/modules/trading/intelligence/FractalScreen.tsx` (~430 строк) — Fractal dashboard.
- Route: `mobile/app/fractal.tsx` → `/api/app/fractal`.

### Telegram MiniApp — Fractal
- `/api/miniapp/fractal?asset=...` combined snapshot.
- `/api/miniapp/fractal-watchlist?symbols=...` watchlist.

### Admin — Fractal
- `/api/admin/fractal/overview` — service health + intelligence aggregate.

---

### Exchange (CEX intelligence) full-stack wire-up (P0) — **обновлено**

#### A) Core Exchange runtime (уже было)
- **Backend** — `routes/exchange_runtime.py` (≈21 endpoint), зарегистрирован ДО `legacy_compat`.
- **Источник**: OKX public REST (geo-allowed). Binance/Bybit зафиксированы как `blocked`.
- **TTL cache**: 15s/30s/60s.

#### B) Удаление legacy-стабов по Exchange (главный фикс)
- Создан `routes/exchange_extras_real.py` и **смонтирован ДО `legacy_compat`** в `backend/server.py`.
- Закрыты **15 ранее стабовых** endpoint'ов (screener/segments/operator/registry):
  - `/api/exchange/screener/{health,candidates,winners,ml/predict}`
  - `/api/exchange/{segments,segment-candles}`
  - `/api/exchange/{providers/health,proxy-config,test-connection,test-order,sync,sync-fills,fills}`
  - `/api/exchanges`, `/api/exchanges/stats`
- **Итоговый аудит**: `real=49, stubs=0` по exchange-семейству (включая prediction + miniapp).

#### C) Fix: Labs crash (Exchange)
- Исправлен баг в `/app/backend/labs/service.py`: `KeyError: totalRisk` при пустом `feature_map`.
- Теперь при отсутствии данных возвращается честный пакет:
  - `totalRisk: 0.0`, `activeRisks: []`, `integrity: CRITICAL`, без 500.

#### D) Документация + cold boot (Exchange)
- Добавлено: `/app/EXCHANGE_API.md`
- Добавлено: `/app/scripts/cold_boot_exchange.sh`
  - 6 шагов, проверяет core OKX feeds + все ранее стабовые endpoints + prediction layer.
  - Гарантирует отсутствие `legacy_compat_stub_empty`.
- `scripts/bootstrap.sh` расширен: теперь запускает `cold_boot_exchange.sh` на каждом cold-boot.

#### E) Поведение без данных — только честные ответы
- `screener/ml/predict` при отсутствии обученной модели → `{ok:false, error:"NO_MODEL"}` (UI это умеет).
- `screener/candidates` при отсутствии forecast-memory → `candidates: []` + `forecastsConsidered`.
- `segments` без нужного (asset,horizon) → `items: []` + `note` (без выдумки сегментов).

---

### Tech Analysis (TA) — FULL real-data audit + UI/API fix (P0)

#### A) Runtime TA engine (candles + indicators) — уже было
- `routes/tech_analysis_runtime.py` (11 endpoints), зарегистрирован ДО `legacy_compat`:
  - `/api/market/candles`, `/api/market/state`, `/api/market/regime`
  - `/api/tech-analysis/{symbol}`
  - `/api/ta-prediction/{symbol}`
  - **`/api/ta-engine/mtf/{symbol}?timeframes=...` (КЛЮЧЕВОЙ для Analysis tab)**
  - `/api/trade-this` (POST)
  - `/api/dashboard/regime`
  - `/api/ta/compact/{symbol}`, `/api/ta/watchlist`
  - `/api/miniapp/tech-analysis`, `/api/miniapp/tech-watchlist`
- **Источник данных**: OKX public REST primary + CoinGecko OHLC fallback.
- **Индикаторы**: RSI/EMA/MACD/SR/trend/momentum (pure Python).
- **Cache**: TTL 30s.

#### B) Удаление legacy-стабов (главный фикс)
- Создан `routes/tech_analysis_real.py` и **смонтирован ДО `legacy_compat`** в `backend/server.py`.
- Заменены **22 ранее стабовых** endpoints (включая `setupService.js` совместимость) на реальные ответы от `services.technical_analysis` (**native_ta_v1**).
- Полностью устранён `legacy_compat_stub_empty` для TA-путей, которые вызывают Web SPA/Terminal, Expo Mobile и MiniApp.

#### C) Prediction UI bugfix (Web)
- Исправлен критический баг: `frontend/src/pages/PredictionPage.jsx` был **хардкоднут на exchange + BTC**, поэтому TA Prediction tab фактически показывал exchange данные.
- Теперь `PredictionPage.jsx` data-source-aware:
  - принимает `apiPath` (`exchange|ta`) и `asset`.
  - вызывает `/api/prediction/{apiPath}/*`.

#### D) Новые TA prediction endpoints (реальные)
Добавлены в `routes/tech_analysis_real.py`:
- `/api/prediction/ta/live-price?asset=BTC`
- `/api/prediction/ta/forecast?asset=BTC`
- `/api/prediction/ta/graph4?asset=BTC&horizon=7D`

**Источники данных**:
- candles/price → `tech_analysis_runtime._fetch_candles` (OKX primary, CoinGecko fallback)
- direction/confidence/SR → `native_ta_v1`

**Математика прогнозов (без фейка/линейных прямых):**
- `target = current ± (band/2) * confidence * sqrt(days/30)`
- если TA даёт `WAIT/NEUTRAL` → `target=current`, `movePct=0` (честно, без выдумки)

#### E) UI crash fix (Web Prediction)
- Устранён runtime-crash `toFixed of undefined`:
  - Backend `/api/prediction/ta/graph4` возвращает `stats: null`, `band: null`, `riskProfile: null`.
  - Frontend `PredictionPage.jsx` усилен защитами (fmtPct/Performance блок/NaN guards).

#### F) UI crash fix (Web TA Prediction chart)
- Устранён runtime-crash lightweight-charts: `Assertion failed: time=NaN`.
- Root cause: TA graph4 возвращал `priceSeries` в форме `{ts, price}`, а UI ожидал `{t, p}`.
- Fix:
  - Backend `/api/prediction/ta/graph4` теперь отдаёт **точно** `{t, p}`.
  - Frontend `BtcForecastChart.jsx` усилен защитами: NaN-filter, sort, dedupe, безопасный прогнозный слой.

#### G) Документация + cold boot
- Добавлено: `/app/TA_API.md`
- Добавлено: `/app/scripts/cold_boot_ta.sh`
  - 6 шагов, проверяет 22 endpoint'а + mobile/miniapp + MTF candles.
  - Гарантирует отсутствие `legacy_compat_stub_empty`.
- `scripts/bootstrap.sh` расширен: теперь запускает `cold_boot_ta.sh` на каждом cold-boot.

---

### OnChain — Light Mode (Infura) full real-data audit (P0) — **НОВОЕ**

#### A) Light Mode без индексера (главное требование)
- Используется **только Light Mode**: Infura RPC + DefiLlama.
- Индексер **не разворачивается** (по требованию), но сделана диагностика состояния.

#### B) Удаление фейковой логики + реальные источники в Mobile (критический фикс)
- Обнаружено: Expo endpoint `/api/mobile/intel/onchain` ранее возвращал показатели, **вычисленные из price change**:
  - `netflow = -change7d * supply * 0.00001`
  - `txCount = max(10, round(30 + change7d*3))`
  - `lthPct = round(70 + change30d*0.1, 0)`
  Это **не on-chain data**.
- Исправлено:
  - `services/intel/onchain.py` переписан: теперь `/api/mobile/intel/onchain` строится на **реальных** данных:
    - Infura latest block summary (blockHeight, gas, TPS, pending)
    - Infura whales (single-block window) — без 24h extrapolation
    - DefiLlama stablecoin total supply
    - DefiLlama TVL + DEX volume
  - Поля, которые в Light Mode невозможно получить честно (CEX netflow, LTH cohort) → `null` + `available:false` + `source:"indexer_required"`.

#### C) Удаление «притворных» оценок в onchain_lite
- Удалены любые extrapolation-хаки:
  - убрано умножение `* 120` (фейк 24h из одного блока)
  - убрано 50/50 split `*0.5` для inflow/outflow
- `onchain_lite/service.py` теперь возвращает только реально измеренное:
  - whales: **single_block window** + честный `note`
  - flows: stablecoin total + bridge in/out (если доступно); CEX flow → `available:false` с причиной

#### D) Indexer диагностика (без деплоя)
- `/api/admin/indexer/diagnostics`:
  - Infura подключен к **4 chain**: ethereum/arbitrum/optimism/base (latency + head_block OK)
  - ingestion: `active=false` (idle) — **это правильно** для Light Mode
  - code-path health: `rpc: ok`, `sync: idle`, `signals: idle`
- Отмечено честно: worker файл для полноценного indexer режима отсутствует (не требуется в Light Mode).

#### E) Аудит endpoint'ов (OnChain)
- Sweep: `real=33, stubs=0` по onchain-overview/cex/smart-money/runtime.
- Light endpoints: `real=22, stubs=0`.

#### F) Документация + cold boot (OnChain)
- Добавлено: `/app/ONCHAIN_API.md`
- Добавлено: `/app/scripts/cold_boot_onchain.sh`
  - 7 шагов: проверка .env, restart, Infura (4 chains), onchain-lite endpoints, mobile intel, zero-stub sweep, indexer diag.
- `scripts/bootstrap.sh` расширен: теперь запускает `cold_boot_onchain.sh` на каждом cold-boot.

---

### Sentiment full real-data wire-up (P0)
- 4 surface adapter роутера, зарегистрированы ДО `legacy_compat`:
  - `routes/news_runtime.py` → `/api/news/feed|digest|velocity`
  - `routes/sentiment_surface_adapters.py` → `/api/connections/clusters/intelligence`
  - `routes/backers_runtime.py` → `/api/backers`
  - `routes/narrative_flow_adapter.py` → `/api/narrative-flow`

### Cleanup-pass
- Архивирование старых репоз/логов.
- Создан единый `PROJECT.md`.
- Создан `scripts/bootstrap.sh`.

---

## 3. Известные ограничения (честно)

1. **CoinMarketCap data-api геоблокирован** для IP датацентра. Парсер использует SSR и сохраняет `hasData=False` с причиной.
2. **Twitter Hybrid V2** требует свежих cookies (`auth_token`, `ct0`).
3. **News tab UI** lazy-load ~10–15s при холодном запуске — performance frontend.
4. **TA patterns / walk-forward**:
   - `native_ta_v1` не реализует паттерн-детектор: `/api/ta/patterns/*` возвращает пусто **с честным `note`**.
   - `native_ta_v1` не хранит историю rolling прогнозов: `/api/prediction/ta/graph4` отдаёт **реальные свечи + текущий snapshot**, но не выдумывает исторические forecast points (есть `note`).
5. **Exchange screener ML**:
   - если `screener_ml_models` не обучены → `/api/exchange/screener/ml/predict` отдаёт `{ok:false, error:"NO_MODEL"}` (это не stub; UI показывает подсказку обучения).
6. **OnChain Light Mode ограничения (без индексера)**:
   - CEX exchange-netflow, per-exchange supply, LTH cohort и 24h whale windows честно недоступны → `null` + `available:false` + `source:"indexer_required"`.

---

## 4. Что делать дальше (опционально)

| Приоритет | Задача |
|---|---|
| P1 | (Если нужно) добавить walk-forward storage для TA (аналогично fractal_rolling_snapshots) — только при наличии реального расчёта/истории, без синтетики. |
| P1 | Добавить реальный ML pipeline для Exchange Screener: обучить/заполнить `screener_ml_models` и `screener_ml_predictions` (иначе будет честный `NO_MODEL`). |
| P1 | Опционально: полный indexer режим для OnChain (если потребуется CEX netflow, address labels, 24h windows) — только после подтверждения наличия worker и storage схем, без имитаций. |
| P2 | Получить CMC pro-api ключ для полного доступа к token-unlock listings. |
| P3 | Поднять Twitter Hybrid V2 в production: добавить cookies через расширение, проверить `twitter_tweets > 0`. |
| P3 | Удалить `routes/legacy_compat.py` целиком (когда все оставшиеся legacy пути мигрируют). |
| P4 | Code-split `frontend/src/pages/twitter/NewsTab.jsx` (1265 строк) — уменьшит lazy chunk и время `Loading module...`. |

---

## 5. Quick reference

```bash
# Полное развёртывание (idempotent)
bash /app/scripts/bootstrap.sh

# TA module verify (cold boot + stubs audit)
bash /app/scripts/cold_boot_ta.sh

# Exchange module verify (cold boot + stubs audit)
bash /app/scripts/cold_boot_exchange.sh

# OnChain Light Mode verify (Infura + DefiLlama + stubs audit)
bash /app/scripts/cold_boot_onchain.sh

# Fractal verify
bash /app/scripts/cold_boot_fractal.sh --verify-only

# Только Sentiment обновить
bash /app/scripts/run_sentiment.sh

# Контроль сервисов
supervisorctl status
supervisorctl restart backend frontend

# Логи
tail -f /var/log/supervisor/backend.*.log

# DB-summary
python -c "from pymongo import MongoClient; import os; db=MongoClient(os.environ['MONGO_URL'])['fomo_mobile']; [print(c, ':', db[c].count_documents({})) for c in ['news_articles','deep_projects','deep_unlocks','deep_funds','mbrain_verdicts','exchange_forecasts','exchange_forecast_runs','paper_orders_v2']]"
```
