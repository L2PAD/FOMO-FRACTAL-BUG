# FOMO — Modules Runbook (Single Source of Truth)
> **Версия:** 2026-05-18 · **Цель:** Один файл, в котором есть ВСЁ, чтобы развернуть и оживить 5 модулей за 10 минут без поиска по 3000 файлам.

> **ВНИМАНИЕ АГЕНТУ:** Прежде чем что-то «чинить» — прочитай разделы **«АРХИТЕКТУРА»** и **«НЕ ДЕЛАТЬ»**. Большая часть реальной логики — в **TypeScript-сайдкаре** (`/app/legacy/backend-src/`). Питон-бэкенд — это ТОЛЬКО прокси + новые роуты + scheduler. **Не пиши новые Python-эндпоинты для модулей TA/Sentiment/Exchange/On-chain/Fractal — они уже написаны на TS.**

---

## 0. БЫСТРЫЙ ЗАПУСК (TL;DR)

```bash
bash /app/scripts/bootstrap_modules.sh
```

Это:
1. Проверит `.env` (MONGO_URL, INFURA_KEY, EMERGENT_LLM_KEY).
2. Прокинет нужные feature-флаги (`SENTIMENT_INTAKE_ENABLED=true`, и т.д.) в `/app/legacy/.env`.
3. Установит зависимости (`yarn install` где нужно).
4. Перезапустит supervisor: `backend` → `node_sidecar` → `frontend`.
5. Прогонит smoke-тесты на ключевые эндпоинты всех 5 модулей.
6. Если в Mongo нет начальных forecast-ов — дёрнет `paper_runtime_scheduler` один раз.

---

## 1. АРХИТЕКТУРА (что где живёт)

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          NGINX / Ingress                                 │
│                /api/*  →  :8001 (Python FastAPI)                         │
│                /*       →  :3000 (React CRA)                             │
└──────────────────────────────────────────────────────────────────────────┘
                                  │
        ┌─────────────────────────┴───────────────────────────┐
        │                                                     │
        ▼                                                     ▼
┌───────────────────────┐                       ┌────────────────────────┐
│ Python FastAPI :8001  │                       │  React SPA :3000       │
│ /app/backend/server.py│                       │  /app/frontend/        │
│                       │                       │  • App.js (Routes)     │
│ • intelligence_real   │                       │  • AppLayout.jsx wraps │
│ • exchange_extras_real│                       │    Outlet в ErrorBoundary│
│ • fractal_sidecar_    │ ─── httpx proxy ───┐ │  • PriceExpectationV2Page│
│   proxy  (NEW MOUNTS) │                    │ │  • MetaBrainCorePanel   │
│ • meta_brain_real     │                    │ │                         │
│ • tech_analysis_real  │                    │ └────────────────────────┘
│ • legacy_compat (catch│                    │
│   ‑all stub_empty)    │                    │
│ • Schedulers:         │                    │
│   - paper_runtime     │                    ▼
│   - meta_brain        │       ┌────────────────────────────────┐
│   - outcome_resolver  │       │ Node TS Sidecar :8003          │
└───────────────────────┘       │ /app/legacy/sidecar-server.ts  │
        │                       │                                │
        ▼                       │ Регистрирует:                  │
┌───────────────────────┐       │ • bootFractalEngine            │
│ MongoDB :27017        │◀──────│ • registerSentimentUIV2Routes  │
│ db = fomo_mobile      │       │ • registerExchangeUIV2Routes   │
│                       │       │                                │
│ Collections:          │       │ Источник кода:                 │
│ • exchange_forecasts  │       │ /app/legacy/backend-src/       │
│ • intel_news_stories  │       │   modules/                     │
│ • sentiment_events    │       │   ├─ sentiment-ml/             │
│ • mbrain_verdicts     │       │   ├─ exchange-ml/              │
│ • paper_predictions   │       │   └─ fractal/                  │
│ • signal_log          │       └────────────────────────────────┘
│ • actor_signal_events │
│ • sentiment_aggregates│ ← заполняется Sentiment-ML Aggregate Worker
│ • dir_samples         │ ← заполняется Sentiment-ML Intake Worker
└───────────────────────┘
```

**Правило:** все нестандартные UI-эндпоинты модулей V2 (`/api/market/chart/exchange-v2`, `/api/market/sentiment/performance-v2`, `/api/fractal/v2.1/*`) живут в **сайдкаре**, а Python их **проксирует** через `routes/fractal_sidecar_proxy.py`.

---

## 2. ПЯТЬ МОДУЛЕЙ — РЕАЛЬНАЯ ЛОГИКА

### 2.1 Fractal (cosine-similarity, replay/synthetic/hybrid)

| | |
|---|---|
| **Source of truth** | `/app/legacy/backend-src/modules/fractal/*` (TS) |
| **Sidecar boot** | `bootFractalEngine(app)` в `/app/legacy/sidecar-server.ts` |
| **Python proxy** | `/app/backend/routes/fractal_sidecar_proxy.py` |
| **Endpoints** | `/api/fractal/v2.1/*`, `/api/fractal/{spx,dxy}/*`, `/api/overlay/*`, `/api/brain/v2/*`, `/api/ui/overview` |
| **Mongo** | `btc_fractal_forecasts`, `spx_fractal_forecasts` |
| **Зависимости** | `/app/legacy/data/fractal/bootstrap/*.csv` (BTCUSD_daily.csv, SPXUSD_daily.csv). Если CSV нет → Bootstrap пишет в лог ошибку, но движок продолжает работать на live-данных. |
| **Известная проблема** | CSV bootstrap файлов нет — историческая база fractal-cohort пуста. Качается с cryptodatadownload.com при `FRACTAL_BOOTSTRAP_AUTO=true`. |
| **UI** | `/intelligence/price-expectation-v2` → вкладка **Fractal**, `/fractal` |

### 2.2 Sentiment-ML (Block 1-4 pipeline)

| | |
|---|---|
| **Source of truth** | `/app/legacy/backend-src/modules/sentiment-ml/*` (TS) |
| **Sidecar boot** | `registerSentimentUIV2Routes(app)` + Workers (см. ниже) |
| **Python proxy** | `routes/fractal_sidecar_proxy.py` → `/market/chart/sentiment-v2`, `/market/sentiment/{performance-v2,top-alts-v2,equity-v2}` |
| **Python native (отдельно)** | `routes/sentiment_runtime.py` + `routes/v1_sentiment_router.py` (универсальный V1 API) |
| **Endpoints** | `/api/market/chart/sentiment-v2`, `/api/market/sentiment/performance-v2`, `/api/sentiment/aggregate/*`, `/api/sentiment/v1/*` |
| **Mongo** | `sentiment_events` (raw events), `sentiment_aggregates` (24H/7D/30D bars), `dir_samples` (calibration), `parser_health_state` |
| **Background workers** | `startSentimentIntakeWorker()` + `startSentimentAggregateWorker()` (TS, в sidecar). Управляются env-флагами в `/app/legacy/.env`: |
| | `SENTIMENT_ML_ENABLED=true` |
| | `SENTIMENT_INTAKE_ENABLED=true` |
| | `SENTIMENT_AGG_ENABLED=true` |
| **Known issue** | Если воркеры не запущены → `chart/sentiment-v2` возвращает `{ok:false, error: "No aggregate found for BTC/24H"}`. Это **нормальное** поведение — означает «нет данных», а не баг. Запуск воркеров требует env-флагов выше. |
| **UI** | `/intelligence/price-expectation-v2` → **Sentiment**, `/twitter`, `/twitter-ai` |

### 2.3 Exchange-ML

| | |
|---|---|
| **Source of truth** | `/app/legacy/backend-src/modules/exchange-ml/*` (TS) + `/app/backend/routes/exchange_extras_real.py` (Python real-data слой) |
| **Sidecar boot** | `registerExchangeUIV2Routes(app)` |
| **Python proxy** | `routes/fractal_sidecar_proxy.py` → `/market/chart/exchange-{v2,v3}`, `/market/chart/forecast-evolution`, `/market/exchange/{performance-v2,top-alts-v2,equity-v2}` |
| **Endpoints (Python real)** | `routes/exchange_extras_real.py` — 49 эндпоинтов: `/api/exchange/ai/*`, `/api/exchange/labs/*`, `/api/exchange/data/*` |
| **Mongo** | `exchange_forecasts` (66+ строк), `exchange_forecast_runs`, `actor_signal_events` |
| **Schedulers** | `rolling_forecast_loop` (supervisor) → каждые 5 минут пишет в `exchange_forecasts` |
| **UI** | `/intelligence/price-expectation-v2` → **Exchange**, `/exchange/*` |
| **Smoke check** | `curl -s :8001/api/market/exchange/performance-v2?symbol=BTC\&horizon=7D\&limit=10` → должен вернуть `rows[]` с реальными прогнозами |

### 2.4 On-chain Light Mode (Infura)

| | |
|---|---|
| **Source of truth** | `/app/backend/services/intel/onchain.py` + `routes/onchain_v10_bridge.py` + `routes/onchain_runtime.py` |
| **Provider** | Infura (`INFURA_KEY` в `/app/backend/.env`) + DefiLlama (free TVL/stablecoins) |
| **Endpoints** | `/api/v10/onchain/*` (bridge), `/api/onchain/*` (runtime) |
| **Mongo** | `onchain_snapshots`, `onchain_signals` |
| **UI** | `/intelligence/price-expectation-v2` → **On-chain**, `/intelligence/onchain-v3` |
| **Known issue** | Light mode — без полноценного indexer. Метрики: gas, ETH supply, stablecoin TVL, DEX volumes. Не математические экстраполяции — реальные значения. |

### 2.5 Tech Analysis (MetaBrain consensus)

| | |
|---|---|
| **Source of truth** | `/app/backend/routes/tech_analysis_real.py` + `routes/meta_brain_real.py` + `services/trading_runtime.py` |
| **Endpoints** | `/api/ta-engine/mtf/{symbol}`, `/api/miniapp/tech-analysis`, `/api/meta-brain-v2/*` |
| **Mongo** | `mbrain_verdicts` (currently empty — генерится live и не пишется), `paper_predictions` |
| **Schedulers** | `meta_brain_scheduler` (background task в `server.py`), `paper_runtime_scheduler`, `outcome_resolver_scheduler` |
| **UI** | `/tech-analysis` — **примечание: верх UI ещё не доделан**; внутри Alpha вкладка `Tech Analysis` пока fallback |
| **Веса 5-модульного консенсуса** | Exchange 0.40 · Sentiment 0.20 · Fractal 0.15 · On-chain 0.15 · TA 0.10 (см. `services/trading_runtime.build_verdict`) |

---

## 3. ОБЯЗАТЕЛЬНЫЕ ENV-ФЛАГИ

### `/app/backend/.env` (Python)

```bash
MONGO_URL="mongodb://localhost:27017"
DB_NAME="fomo_mobile"
INFURA_KEY="29976df4bb4a44b09105a34cdf31d11d"
EMERGENT_LLM_KEY="sk-emergent-..."
ONCHAIN_ENABLED="true"
DEEP_PARSER_ENABLED="true"
APP_URL="https://fomo-module-deploy.preview.emergentagent.com"
MINIAPP_URL="https://fomo-module-deploy.preview.emergentagent.com/miniapp"
NOWPAYMENTS_API_KEY="..."
COOKIE_ENC_KEY="..."
```

### `/app/frontend/.env`

```bash
REACT_APP_BACKEND_URL=https://fomo-module-deploy.preview.emergentagent.com
```

### `/app/legacy/.env` (Node sidecar)

```bash
# General
PORT=8003
HOST=127.0.0.1
MONGO_URL=mongodb://localhost:27017
DB_NAME=fomo_mobile

# Sentiment-ML (КРИТИЧНО для charts/aggregate)
SENTIMENT_ML_ENABLED=true
SENTIMENT_INTAKE_ENABLED=true     # запускает Intake Worker
SENTIMENT_AGG_ENABLED=true        # запускает Aggregate Worker (24H/7D/30D)
SENTIMENT_ENABLED=false           # legacy S2.1 — оставить false
SENTIMENT_DATASET_ENABLED=false

# Exchange-ML
EXCHANGE_ML_ENABLED=true

# Fractal
FRACTAL_BOOTSTRAP_AUTO=false      # true ⇒ скачает Kraken CSV при первом запуске
FRACTAL_BOOTSTRAP_DIR=/app/legacy/data/fractal/bootstrap

# WebSocket
WS_ENABLED=false
```

---

## 4. SUPERVISOR ПРОЦЕССЫ

| Имя | Команда | Назначение |
|---|---|---|
| `backend` | `uvicorn server:app --host 0.0.0.0 --port 8001 --reload` | FastAPI |
| `frontend` | `yarn start` | CRA dev server :3000 |
| `mongodb` | `mongod --bind_ip_all` | DB :27017 |
| `node_sidecar` | `tsx /app/legacy/sidecar-server.ts` | TS sidecar :8003 |
| `rolling_forecast_loop` | `python /app/backend/scripts/rolling_forecast_loop.py` | каждые 5 мин пишет `exchange_forecasts` |
| `news_substrate` | `python /app/backend/scripts/news_substrate_loop.py` | новости → `intel_news_stories` |
| `code-server` | code-server | dev IDE (по умолчанию `autostart=false`) |

Команды:
```bash
supervisorctl status                       # обзор
supervisorctl restart backend              # после правки .py
supervisorctl restart node_sidecar         # после правки .ts
supervisorctl tail -f node_sidecar stderr  # debug sidecar
tail -n 50 /var/log/supervisor/{backend,node_sidecar,frontend}.{out,err}.log
```

---

## 5. КАК UI ЧИТАЕТ ДАННЫЕ — КАРТА «БЛОК → ЭНДПОИНТ»

Страница `/intelligence/price-expectation-v2` (Alpha) — главный экран.

| Блок в UI | Компонент | Эндпоинт | Источник |
|---|---|---|---|
| Главный график | `BtcForecastChart.jsx` | `/api/market/chart/price-vs-expectation-v4` | `intelligence_real.py` (Python) |
| 24H Forecast (правая панель) | `MetaBrainCorePanel.jsx` | тот же + `/api/intelligence/v3/alpha` | `intelligence_real.py` |
| Model Structure (5 веса) | `MetaBrainCorePanel.jsx` | `/api/meta-brain-v2/policy` | `legacy_compat.py` (Python) — статичные веса |
| System Health (Coverage/Drift) | `MetaBrainCorePanel.jsx` | `/api/intelligence/system-health` | `intelligence_real.py` |
| Expected Range (Low/Base/High) | `MetaBrainCorePanel.jsx` | `data.candidates` (внутри v4 payload) | `intelligence_real.py` |
| Signal Drivers (Funding/OI/Regime) | `MetaBrainCorePanel.jsx` | `data.signalDrivers` (внутри v4 payload) | `intelligence_real.py` |
| **Exchange sub-tab** chart | `ExchangeForecastChartV2.jsx` | `/api/market/chart/exchange-v2` | **TS sidecar** → Python proxy |
| Exchange sub-tab perf table | `ExchangePerformanceTableV2.jsx` | `/api/market/exchange/performance-v2` | **TS sidecar** → Python proxy |
| **Sentiment sub-tab** chart | `SentimentForecastChartV2.jsx` | `/api/market/chart/sentiment-v2` | **TS sidecar** → Python proxy |
| Sentiment sub-tab perf table | `SentimentPerformanceTableV3.jsx` | `/api/market/sentiment/performance-v2` | **TS sidecar** → Python proxy |
| **On-chain sub-tab** | (компонент On-chain) | `/api/v10/onchain/*`, `/api/onchain/*` | Python `onchain_runtime.py` |
| **Fractal sub-tab** | (компонент Fractal) | `/api/fractal/v2.1/*` | **TS sidecar** → Python proxy |
| **Tech Analysis sub-tab** | (placeholder) | `/api/ta-engine/mtf/{sym}`, `/api/miniapp/tech-analysis` | Python `tech_analysis_real.py` |

---

## 6. ЧТО Я УЖЕ СДЕЛАЛ В ЭТОЙ СЕССИИ

1. **Подключил TS-модули в sidecar:** добавил в `/app/legacy/sidecar-server.ts`:
   - `await app.register(registerSentimentUIV2Routes)` ← 4 эндпоинта (Sentiment UI V2)
   - `await app.register(registerExchangeUIV2Routes)` ← 6 эндпоинтов (Exchange UI V2 + forecast-evolution)
2. **Добавил прокси в Python:** в `/app/backend/routes/fractal_sidecar_proxy.py` добавлены 10 новых проксируемых путей (`/market/chart/{sentiment,exchange}-v{2,3}`, `/market/{sentiment,exchange}/{performance,top-alts,equity}-v2`, `/market/chart/forecast-evolution`).
3. **Защита фронтенда:** обернул `<Outlet>` в `AppLayout.jsx` в **ErrorBoundary** (`/app/frontend/src/components/ErrorBoundary.jsx`), чтобы один битый блок не клал всю SPA. Re-mount на каждом смене pathname.
4. **Null-safety патчи** (без новой логики): `ExchangePerformanceTableV2.jsx`, `SentimentPerformanceTableV3.jsx`, `SentimentForecastCard.jsx`, `SentimentForecastChartV2.jsx`, `MetaBrainCorePanel.jsx` (исправлен баг `Math.abs(maxReturn)` в Expected Range).
5. **Удалил свою отсебятину:** `routes/performance_real.py` ❌, `routes/ui_telemetry.py` ❌, мои изменения в `legacy_compat.py` (policy + drift + catch-all rows) откатил, мои изменения в `intelligence_real.py` (candidates с горизонтов на «другие активы») откатил.

---

## 7. ИЗВЕСТНЫЕ ОТКРЫТЫЕ ВОПРОСЫ

| # | Проблема | Что нужно |
|---|---|---|
| 1 | Sentiment chart возвращает `{ok:false, error:"No aggregate found"}` | Запустить `SENTIMENT_INTAKE_ENABLED=true` + `SENTIMENT_AGG_ENABLED=true` в `/app/legacy/.env` и рестарт sidecar. Воркеры популируют `sentiment_aggregates`. |
| 2 | Fractal cohort пуст | Скачать `BTCUSD_daily.csv` от cryptodatadownload в `/app/legacy/data/fractal/bootstrap/`, или `FRACTAL_BOOTSTRAP_AUTO=true`. |
| 3 | Tech Analysis UI ещё не разработан | Не трогать (по слову пользователя). |
| 4 | `mbrain_verdicts` collection пуст | `meta_brain_scheduler` крутится но в Mongo не сохраняет — нужна доработка scheduler в `server.py` если хочется исторический архив. |
| 5 | `SentimentForecastChartV2` иногда даёт `body stream already read` | React StrictMode double-fetch — лечится либо отменой `StrictMode`, либо AbortController. |

---

## 8. НЕ ДЕЛАТЬ (ВАЖНО)

❌ **Не писать новые Python `*_real.py` роутеры для модулей, реализованных в TS.** Если эндпоинт `/api/market/...` уже зарегистрирован в `registerSentimentUIV2Routes` или `registerExchangeUIV2Routes` — он работает через sidecar. Просто проверь `curl http://localhost:8003/<path>`.

❌ **Не модифицировать `frontend/.env` REACT_APP_BACKEND_URL** и `backend/.env` MONGO_URL — это сломает ingress.

❌ **Не использовать `npm`** — только `yarn`. `requirements.txt` обновлять через `pip install X && pip freeze > /app/backend/requirements.txt`.

❌ **Не использовать ObjectId** в Mongo — только UUIDv4.

❌ **Не «выдумывать» данные.** Если воркер не запущен → возвращаем `{ok:false, error:"..."}`. **НИКОГДА** не мокаем числа.

❌ **Не править Prediction (Polymarket) при работе с MetaBrain.** Это разные слои.

---

## 9. ВЕРИФИКАЦИЯ ПОСЛЕ ЗАПУСКА (smoke tests)

```bash
# Backend живой
curl -fsS http://localhost:8001/api/health
curl -fsS http://localhost:8003/api/healthz   # sidecar

# 5 модулей
curl -fsS "http://localhost:8001/api/market/chart/exchange-v2?symbol=BTC&horizon=24H"     | jq '.ok'
curl -fsS "http://localhost:8001/api/market/exchange/performance-v2?symbol=BTC&horizon=7D"| jq '.rows | length'
curl -fsS "http://localhost:8001/api/market/chart/sentiment-v2?symbol=BTC&horizon=24H"    | jq '.ok'
curl -fsS "http://localhost:8001/api/market/sentiment/performance-v2?symbol=BTC"          | jq '.rows | length'
curl -fsS "http://localhost:8001/api/fractal/v2.1/terminal?symbol=BTC"                    | jq '.ok'
curl -fsS "http://localhost:8001/api/v10/onchain/snapshot"                                | jq '.ok'
curl -fsS "http://localhost:8001/api/ta-engine/mtf/BTC"                                   | jq '.ok'
curl -fsS "http://localhost:8001/api/market/chart/price-vs-expectation-v4?symbol=BTC"     | jq '.verdict'
```

Все должны вернуть `true` (или непустой массив для `rows`). Если что-то даёт `false` — см. таблицу в §7.

---

## 10. ОДНОЙ КОМАНДОЙ

Полный реcтарт стека:

```bash
bash /app/scripts/bootstrap_modules.sh
```

(Скрипт идемпотентный, можно запускать сколько угодно раз.)

---

## 11. КОНТАКТ-ПОИНТЫ ДЛЯ ОТЛАДКИ

| Симптом | Куда смотреть |
|---|---|
| Белая страница в SPA | `tail -n 100 /var/log/supervisor/frontend.err.log` + DevTools console |
| `body stream already read` | React StrictMode + double-fetch (исправить AbortController) |
| `legacy_compat_stub_empty` ответ | Эндпоинт не замаунчен или TS-роут не зарегистрирован → проверь sidecar logs |
| Sidecar упал | `tail -n 60 /var/log/supervisor/node_sidecar.err.log` (часто — отсутствует `/app/legacy/data/fractal/bootstrap/*.csv`, не критично) |
| Mongo не отвечает | `mongosh mongodb://localhost:27017/fomo_mobile --eval 'db.exchange_forecasts.count()'` |
| Эндпоинт работает на :8003 но 404 на :8001 | Добавь его в `fractal_sidecar_proxy.py` (просто `@router.get(...)`) |
