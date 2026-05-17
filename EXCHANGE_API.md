# Exchange Module — Real-Data Deployment

> **Status:** ✅ All 49 exchange endpoints serve real data from OKX live
> feeds, MongoDB collections (`exchange_forecasts`, `exchange_forecast_runs`,
> `paper_orders_v2`) and the in-process venue health probes.
> **Audit (2026-05-17):** real=49, stubs=0, honest-`ok:false`=1
> (`NO_MODEL` for the screener — explicitly handled by `AltScreenerPage`).

---

## 1. Architecture

```
                          OKX public REST  ← primary feed
                                │
              ┌─────────────────┴────────────────┐
              │                                  │
       routes/exchange_runtime.py        services.market_data
       (orderbook · funding · OI ·       (ticker cache · candles)
        derivatives · tickers ·
        venues · health · miniapp/exchange · cex/* · funding-rates)
              │                                  │
              └────────────┬─────────────────────┘
                           │
                ┌──────────┴──────────┐
                │                     │
   routes/exchange_extras_real.py  prediction_exchange_routes.py
   (screener · segments ·          (/api/prediction/exchange/*
    operator · registry)            forecast · alts · graph{,3,4} ·
                                    top-signals · model-health · live-price)
                │                     │
                └──────────┬──────────┘
                           │
                  routes/legacy_compat.py
                  (catch-all — now NEVER reached for /api/exchange/*)
```

Mount order in `backend/server.py` (real handlers always win):

| Router file                         | Mount line  | Scope                                              |
| ----------------------------------- | ----------- | -------------------------------------------------- |
| `prediction_exchange_routes.py`     | ~828        | `/api/prediction/exchange/*`                       |
| `routes/exchange_extras_real.py`    | **early**   | screener · segments · operator · registry          |
| `routes/exchange_runtime.py`        | ~7728       | core CEX data + miniapp/exchange + cex/* aliases   |
| `labs/routes.py`                    | ~794        | `/api/exchange/labs/*`                             |
| `routes/legacy_compat.py`           | last        | catch-all (lowest priority)                        |

---

## 2. Endpoint matrix (Web · Mobile · MiniApp)

### 2.1 Core market data — `exchange_runtime.py`
| Endpoint                                       | Surface  | Source                           |
| ---------------------------------------------- | -------- | -------------------------------- |
| `GET /api/exchange/orderbook/{SYM}`            | Web      | OKX `books`                      |
| `GET /api/exchange/funding/{SYM}`              | Web + M  | OKX `funding-rate`               |
| `GET /api/exchange/open-interest/{SYM}`        | Web      | OKX `open-interest`              |
| `GET /api/exchange/derivatives/{SYM}`          | Web      | combined funding+OI+ticker       |
| `GET /api/exchange/tickers?limit=N&sort=...`   | Web      | OKX swap tickers (top by volume) |
| `GET /api/exchange/markets`                    | Web      | OKX instruments                  |
| `GET /api/exchange/anomalies`                  | Web + M  | live funding/OI scan             |
| `GET /api/exchange/order-flow/{SYM}`           | Web      | OKX trades aggregation           |
| `GET /api/exchange/overview`                   | Web      | top markets · funding · OI       |
| `GET /api/exchange/compact/{SYM}`              | Web      | minified pack                    |
| `GET /api/exchange/venues`                     | Web      | live ping of OKX/Binance/Bybit   |
| `GET /api/exchange/health`                     | Web      | venue ping + cache status        |
| `GET /api/exchange/account`                    | Operator | paper-trading account            |
| `GET /api/exchange/orders`                     | Operator | paper-trading orders             |
| `GET /api/exchange/status`                     | Operator | engine status                    |
| `GET /api/miniapp/exchange?asset=BTC`          | Mobile   | derivatives + orderbook brief    |
| `GET /api/miniapp/exchange-watchlist?symbols=` | Mobile   | per-symbol derivative snapshot   |
| `GET /api/cex/orderbook/{SYM}`                 | Web      | alias of /api/exchange/orderbook |
| `GET /api/cex/funding/{SYM}`                   | Web      | alias                            |
| `GET /api/cex/oi/{SYM}`                        | Web      | alias                            |
| `GET /api/cex/anomalies`                       | Web      | alias                            |
| `GET /api/cex/liquidations`                    | Web      | OKX `liquidation-orders`         |
| `GET /api/cex-intelligence/overview`           | Web      | curated CEX dashboard            |
| `GET /api/funding-rates`                       | Web      | multi-symbol funding             |
| `GET /api/order-flow/{SYM}`                    | Web      | alias                            |
| `GET /api/admin/exchange/overview`             | Admin    | operator-only dashboard          |

### 2.2 Prediction — `prediction_exchange_routes.py`
| Endpoint                                                    | Schema                             |
| ----------------------------------------------------------- | ---------------------------------- |
| `GET /api/prediction/exchange/forecast?asset=BTC`           | targets (24H · 7D · 30D)           |
| `GET /api/prediction/exchange/live-price?asset=BTC`         | live price                         |
| `GET /api/prediction/exchange/graph?asset=BTC&horizon=…`    | static forecast graph              |
| `GET /api/prediction/exchange/graph3?asset=BTC&horizon=…`   | walk-forward chart (v3)            |
| `GET /api/prediction/exchange/graph4?asset=BTC&horizon=…`   | rolling-forecast chart (v4)        |
| `GET /api/prediction/exchange/top-signals?limit=N`          | best fresh signals                 |
| `GET /api/prediction/exchange/model-health?asset=BTC`       | per-asset model integrity          |
| `GET /api/prediction/exchange/alts?horizon=…&limit=N`       | alt forecasts list                 |

### 2.3 Screener · Segments · Operator · Registry — `exchange_extras_real.py`

These **used to return `legacy_compat_stub_empty`**.  Each is now backed
by `exchange_forecasts` / `paper_orders_v2` / live venue ping:

| Endpoint                                              | Source                                       |
| ----------------------------------------------------- | -------------------------------------------- |
| `GET /api/exchange/screener/ml/predict?horizon=4h`    | `screener_ml_predictions` (honest `NO_MODEL`) |
| `GET /api/exchange/screener/candidates?horizon=…`     | live OKX tickers ⊗ `exchange_forecasts`      |
| `GET /api/exchange/screener/winners?days=7`           | `exchange_forecasts.outcome.label==WIN`      |
| `GET /api/exchange/screener/health`                   | model count + winner memory                  |
| `GET /api/exchange/segments?asset=BTC&horizon=30D`    | `exchange_forecasts` per asset+horizon       |
| `GET /api/exchange/segment-candles?segmentId=…`       | OKX candles for segment window               |
| `GET /api/exchange/providers/health`                  | live OKX/Binance/Bybit ping                  |
| `GET /api/exchange/proxy-config`                      | env vars (creds masked)                      |
| `GET/POST /api/exchange/test-connection`              | live ping summary                            |
| `GET/POST /api/exchange/test-order`                   | paper dry-run (no submission)                |
| `GET/POST /api/exchange/sync`                         | `exchange_forecast_runs` last record         |
| `GET/POST /api/exchange/sync-fills`                   | alias of `/sync`                             |
| `GET /api/exchange/fills`                             | `paper_orders_v2.status==FILLED`             |
| `GET /api/exchanges`                                  | registry view of venues                      |
| `GET /api/exchanges/stats`                            | forecast/run/order counts                    |

### 2.4 Labs — `labs/routes.py`
| Endpoint                                              |
| ----------------------------------------------------- |
| `GET /api/exchange/labs?mode=global|universe|asset`   |
| `GET /api/exchange/labs/symbols`                      |
| `GET /api/exchange/labs/drilldown?lab=…&asset=…`      |

Fixed in this audit: `compute_single_asset` no longer raises
`KeyError("totalRisk")` when there is no feature data — it returns
`{totalRisk: 0.0, activeRisks: []}` honestly.

---

## 3. Honest disclosures

The Exchange module **never** falls back to fabricated metrics.  Where
real data is unavailable, the response signals so clearly:

| Endpoint                                       | Honest fallback                                            |
| ---------------------------------------------- | ---------------------------------------------------------- |
| `screener/ml/predict` (no trained model)       | `{ok: false, error: "NO_MODEL", predictions: []}`          |
| `screener/candidates` (forecast desert)        | `candidates: []` + `universeSize`, `forecastsConsidered`   |
| `segments` (asset+horizon never forecasted)    | `data.items: []` + `note: "exchange_forecasts_..."`        |
| `segment-candles` (bad/unknown segmentId)      | `{ok: false, error: "segment_not_found"}`                  |
| `labs?mode=asset` (no feature data)            | `totalRisk: 0` + `activeRisks: []`                         |
| `providers/health` (all venues blocked)        | `online: 0` + per-venue `status: "blocked"` + latency      |

These shapes match exactly what the UI already handles (e.g.
`AltScreenerPage` shows the “Run ML training job first” tip when it
sees `NO_MODEL`).

---

## 4. Health-check (one-shot)

```bash
curl -s "$BACKEND/api/exchange/health"                  | jq '.online, .total'
curl -s "$BACKEND/api/exchange/venues"                  | jq '.primary, .online'
curl -s "$BACKEND/api/exchange/providers/health"        | jq '.online, .total'
curl -s "$BACKEND/api/exchange/screener/health"         | jq '.models.count, .winnerMemory.total'
curl -s "$BACKEND/api/exchange/segments?asset=BTC&horizon=30D" | jq '.data.items | length'
curl -s "$BACKEND/api/miniapp/exchange?asset=BTC"       | jq '.spotPrice, .fundingRatePct'
curl -s "$BACKEND/api/prediction/exchange/forecast?asset=BTC" | jq '.targets | length'
```

If any returns `note: "legacy_compat_stub_empty"` → the real router did
not mount.  Check `tail -n 200 /var/log/supervisor/backend.out.log`
for `[ExchangeExtrasReal] import failed:` traces.

---

## 5. Cold-boot

Run `scripts/cold_boot_exchange.sh` after any deploy — it walks every
endpoint in §2 and fails fast if a stub creeps back in.
