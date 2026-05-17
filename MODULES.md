# MODULES.md — Детальное описание 5 модулей FOMO OS

> Production-state на 2026-05-17. Все модули LIVE и пишут verdict в `mongo://fomo_mobile/mbrain_verdicts`.

## Диаграмма зависимостей модулей (data-flow)

```
                          ┌─────────────────────────────┐
                          │   MetaBrain Consensus Loop   │
                          │   services/consensus_*.py    │
                          └─────────────────────────────┘
                                    ▲▲▲▲▲
              ┌─────────────────────┼┼┼┼┼─────────────────────┐
              │                     ││││└─────────────────┐   │
              │            ┌────────┘│││                  │   │
              │            │    ┌────┘││                  │   │
              ▼            ▼    ▼    ▼▼                   ▼   │
       ┌────────────┐ ┌──────────┐ ┌────────────┐ ┌────────────┐
       │  M1: TA    │ │ M2:      │ │ M3:        │ │ M4:        │
       │ TechAnalys.│ │ Fractal  │ │ OnChain    │ │ Exchange   │
       └─────┬──────┘ └────┬─────┘ └─────┬──────┘ └─────┬──────┘
             │             │             │              │
             ▼             ▼             ▼              ▼
       CCXT OHLC     Native fractal  per-asset       Binance/Bybit/OKX
       (Binance/     engine over     adapters        order-flow,
        Bybit/OKX)   historical OHLC + chain-level   funding, OI, liq.
                                     fallback
                          
                          ┌──────────────────────┐
                          │  M5: SENTIMENT       │
                          │  ────────────────    │
                          │  • News (RSS×119)    │
                          │  • Twitter HybridV2  │
                          │  • Funds/Persons/    │
                          │    Unlocks (deep)    │
                          │  • Fear & Greed      │
                          │  • CoinGecko         │
                          └──────────────────────┘
                                    │
                                    ▼
                          MongoDB sentiment_events
                          + news_articles + deep_*
                                    │
                                    ▼
                          Surface adapters в /api/* →
                          React UI (Sentiment tabs)
```

---

## M1: Tech Analysis

| Параметр | Значение |
|---|---|
| **Файлы (core)** | `backend/services/exchange/__init__.py`, `backend/services/bar_data.py`, `backend/services/asset_intelligence.py` |
| **Внешние данные** | Binance/Bybit/OKX через CCXT (OHLC fallback chain) |
| **Кэширование** | `bar_data.py` TTL cache |
| **Индикаторы** | RSI(14), MACD(12,26,9), EMA(20/50/200), support/resistance pivots |
| **Verdict logic** | Если RSI < 30 → bullish bias; > 70 → bearish bias; MACD cross → trend confirm |
| **Endpoints UI** | `/api/tech-analysis/{asset}`, `/api/asset-intelligence/{asset}` |
| **Coverage** | Production universe (BTC, ETH, SOL, ARB, DOGE, etc.) |

### Зависимости
```python
ccxt>=4.0          # exchanges
pandas, numpy      # indicators
ta-lib (опц.)      # сейчас pure-python через own helpers
```

---

## M2: Fractal

| Параметр | Значение |
|---|---|
| **Файлы (core)** | `backend/services/fractal_generator.py`, `backend/services/fractal_runtime.py`, `backend/routes/fractal_runtime.py` |
| **Алгоритм** | Native fractal-similarity engine: окно N дней OHLC → косинусное сходство с историческими паттернами |
| **Хранение** | `fractal_patterns`, `fractal_runtime` collections |
| **Verdict logic** | Topology of resolution histogram: какие паттерны разрешились в LONG/SHORT за последние N циклов |
| **Endpoints UI** | `/api/fractal/runtime/{asset}`, `/api/fractal/patterns` |

### Зависимости
```python
numpy, scipy       # similarity / clustering
motor              # async mongo
```

---

## M3: On-chain (per-asset)

| Параметр | Значение |
|---|---|
| **Файлы (core)** | `backend/services/onchain_per_asset.py`, `backend/routes/onchain_runtime.py` |
| **Источники** | Per-asset adapters (DOGE, ARB, ETH, ...) + chain-level fallback |
| **Метрики** | TVL delta, активные адреса, объём транзакций, баланс китов, on-chain accumulation |
| **Verdict logic** | Если TVL delta > +5% и whales accumulating → LONG; obratno → SHORT |
| **Endpoints UI** | `/api/onchain/runtime/{asset}` (РЕГИСТРИРУЕТСЯ ДО `legacy_compat`) |
| **Validation** | DOGE/ARB реально дифференцируются как LONG (conf=0.65) на onchain_per_asset_v1 |

### Зависимости
```python
web3 (опц.)        # для прямых RPC-вызовов
httpx              # к публичным indexer'ам
```

---

## M4: Exchange (CEX)

| Параметр | Значение |
|---|---|
| **Файлы (core)** | `backend/services/exchange/*`, `backend/cex_intelligence/*` |
| **Источники** | Binance / Bybit / OKX live REST + WebSocket |
| **Метрики** | Order-flow imbalance, OI delta, funding rate, liquidations heatmap |
| **Кэширование** | TTL cache в `/api/venues/all/health` (после фикса — отвечает <1s vs 25s раньше) |
| **Verdict logic** | OI растёт + positive funding + long-side liquidations → bearish signal (over-leveraged) и наоборот |
| **Endpoints UI** | `/api/exchange/*`, `/api/venues/all/health`, `/api/cex-intelligence/*` |

### Зависимости
```python
ccxt, ccxtpro      # exchanges
websockets         # live order-flow
```

---

## M5: Sentiment ⭐

Самый большой и сложный модуль, состоящий из 4 независимых под-pipeline'ов.

### M5.1 News pipeline (RSS × 119)
| Параметр | Значение |
|---|---|
| **Скрипт** | `backend/scripts/run_rss_pipeline.py` |
| **Supervisor loop** | `backend/services/news_substrate_loop.py` (процесс `news_substrate`) |
| **Источники** | 119 RSS feeds: CoinDesk, CoinTelegraph, TheBlock, Decrypt, Blockworks, BeInCrypto (6 lang), Reddit (Bitcoin/CryptoMarkets/DeFi/Solana/Avax/Polkadot/...), Vitalik blog, YT channels, etc. |
| **Куда пишет** | `news_articles` (~3000+ статей), `sentiment_events` (~4500+) |
| **Entity extraction** | regex по 60+ ключевым словам → `entities_mentioned` |
| **Adapter** | `backend/routes/news_runtime.py` → `/api/news/feed|digest|velocity` |

### M5.2 Twitter Hybrid V2 (через Chrome Extension)
| Параметр | Значение |
|---|---|
| **Native engine** | `backend/modules/twitter_parser/*` |
| **Step script** | `backend/scripts/twitter_sentiment_step.py` |
| **Layers** | L0: cookies из Extension → L1: twscrape → L2: Playwright fallback → L3: manual |
| **Куда пишет** | `twitter_tweets`, `twitter_accounts`, `sentiment_events` |
| **Extension endpoint** | `POST /api/v4/twitter/sessions/webhook`, `POST /api/v4/twitter/ingest` |
| **Tracked actors** | seed в `twitter_tracked_actors` (24 crypto alpha-аккаунта) |

### M5.3 Deep parser (Funds + Persons + Unlocks + Projects)
| Параметр | Значение |
|---|---|
| **Core** | `backend/services/deep_parser.py` (924 строки) |
| **Подход** | Извлекает `<script id="__NEXT_DATA__">` JSON из Next.js SPA → byaspaет необходимость в Playwright |
| **Источники** | DropsTab (`/coins/*`, `/investors/*`), CryptoRank (`/ico/*`), ICODrops (`/category/*`), CoinMarketCap (`/currencies/*`) |
| **Коллекции** | `deep_projects` (106), `deep_funding_rounds` (386), `deep_persons` (899), `deep_unlocks` (26), `deep_funds` (20), `deep_project_events` (655) |
| **Auto-loop** | `start_loop_if_enabled()` — каждые 6 часов автоматически (env `DEEP_PARSER_ENABLED`, `DEEP_PARSER_INTERVAL_SEC`) |
| **Adapter** | `backend/routes/deep_runtime.py` → `/api/deep/{stats,funds,persons,unlocks,projects}` |

### M5.4 Aggregator sources
| Источник | Файл | Куда пишет |
|---|---|---|
| CoinGecko | `backend/services/feed_service.py` | `sentiment_events` |
| CryptoCompare News | `backend/services/news_intelligence.py` | `news_articles` |
| Fear & Greed Index | `backend/services/feed_service.py` | `sentiment_events` |

### M5 Surface (React UI)
| Тab | Endpoint | Adapter |
|---|---|---|
| Overview | `/api/connections/clusters/intelligence` + `/api/narrative-flow` | `sentiment_surface_adapters.py`, `narrative_flow_adapter.py` |
| News | `/api/news/feed?limit=50&hours=48` | `news_runtime.py` |
| Backers | `/api/backers` | `backers_runtime.py` |
| Graph / Network | `/api/connections/*` | `connections_router.py` |

### Зависимости (Sentiment-specific)
```python
feedparser          # RSS parsing
httpx, beautifulsoup4  # SPA scraping
emergentintegrations   # AI sentiment scoring (EMERGENT_LLM_KEY)
playwright (опц.)    # Twitter L2 fallback
twscrape (опц.)      # Twitter L1
```

---

## Cross-module: MetaBrain Consensus

| Параметр | Значение |
|---|---|
| **Файлы** | `backend/services/consensus_*.py`, `backend/services/mbrain_*.py` |
| **Калибровка** | `backend/services/calibration.py` + `backend/routes/mbrain_verdicts.py` |
| **Drift detection** | `/api/meta-brain-v2/drift` |
| **Broker bridge** | `backend/services/broker_bridge.py` — **noop**/`mode=off` by default, paper-runtime gate (`minActiveModules=3`, `minConfidence=0.45`) |
| **Verdict storage** | `mbrain_verdicts` collection |

### Verdict computation
1. Каждый модуль возвращает `{direction: LONG|SHORT|HOLD, confidence: 0..1, drivers: [...]}`
2. Aggregator weighted: `score = Σ(weight_i × confidence_i × sign(direction_i))`
3. Conflict measurement: `conflict = std(directions)` — Low / Medium / High
4. Final verdict: LONG if score > +threshold AND active_modules ≥ 3
