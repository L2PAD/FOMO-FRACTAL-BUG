# Fractal & Meta Brain — API Reference

Полная карта endpoints системы прогнозирования FOMO.
Все endpoints возвращают **реальные данные** (no mock).

## Быстрый старт

```bash
# Развернуть с нуля
bash /app/scripts/bootstrap.sh

# Только Fractal/Meta Brain (предполагая базовый bootstrap уже выполнен)
bash /app/scripts/cold_boot_fractal.sh

# Только проверка
bash /app/scripts/cold_boot_fractal.sh --verify-only
```

---

## Архитектура

```
┌──────────────────────────┐         ┌──────────────────────────┐
│  FastAPI :8001 (Python)  │ proxy → │  Node sidecar :8003      │
│  /api/*                  │         │  Fastify + TypeScript    │
│  • routers, auth, billing│         │  • Fractal v2.1 engine   │
│  • mbrain, miniapp       │         │  • cosine-similarity     │
│  • rolling snapshots     │         │  • SPX/DXY replay        │
│  • meta-brain (real)     │         │  • BTC×SPX overlay       │
└────────────┬─────────────┘         └────────────┬─────────────┘
             │                                    │
             └──────────────┬─────────────────────┘
                            ▼
                  ┌──────────────────────┐
                  │  MongoDB             │
                  │  fomo_mobile DB      │
                  └──────────────────────┘
```

---

## Fractal Engine endpoints

### `GET /api/fractal/v2.1/overlay`

Cosine-similarity matching текущего 120-дневного окна с историческими аналогами.

**Query:**
- `symbol` — BTC / SPX / DXY
- `horizon` — 30 / 90 / 180 / 365 (дней вперёд)
- `windowLen` — длина окна для сравнения (по умолчанию 120)
- `topK` — сколько top-аналогов вернуть (по умолчанию 10)
- `aftermathDays` — длина forward-trail аналога

**Ответ:**
```json
{
  "symbol": "BTC",
  "asOf": "2026-05-17T...",
  "windowLen": 120,
  "currentWindow": { "raw": [...30 pts...], "normalized": [...] },
  "matches": [
    {
      "similarity": 0.4152,
      "startDate": "2010-10-27",
      "endDate":   "2011-02-24",
      "windowNormalized":    [...120 pts...],
      "aftermathNormalized": [...30 pts...]
    }
  ],
  "distribution": { "p10": ..., "p50": ..., "p90": ... }
}
```

### `GET /api/fractal/v2.1/terminal`

Полный verdict-пакет с decision + factors + 6 горизонтами.

### `GET /api/fractal/v2.1/chart`

OHLCV свечи актива (для рендера графика).

### `GET /api/fractal/{spx|dxy}`

DXY: synthetic + replay + hybrid (5 matches с 1973 года).
SPX: v2.1.0 contract, action LONG/SHORT/WAIT, 6 горизонтов, 5 topMatches sim 90%+.

### `GET /api/overlay/coeffs`

Cross-asset overlay для BTC × SPX.

**Реальная математика:** `R_adj = R_btc + g × w × β × R_spx`

**Ответ:**
```json
{
  "coeffs": {
    "beta": 1.2547,
    "rho":  0.3217,
    "w":    { "applied": 0.8123 },
    "guard": "NONE"
  }
}
```

---

## UI Overview & Rolling Forecast

### `GET /api/ui/overview`

Главный endpoint для chart-страницы `/fractal/overview`. Прокси на Node sidecar.

**Query:** `asset=btc&horizon=30|90|180|365`

**Ответ:**
```json
{
  "asset": "BTC",
  "asOf":  "2026-05-17T...",
  "candles":   [...],
  "charts": {
    "actual":    [{t, v}, ...],  // реальные исторические свечи
    "predicted": [{t, v}, ...]   // forward forecast curve из median analog cohort
  },
  "verdict": { "stance": "BULLISH", "confidencePct": 54 },
  "fractal": { "direction": "UP", "confidence": 0.45, "nativeMeta": { "analogCount": 15 } }
}
```

### `GET /api/prediction/snapshots`

Walk-forward история прогнозов (rolling-forecast trail).

**Query:** `asset=BTC&view=hybrid&horizon=90&limit=128`

**Ответ:**
```json
{
  "snapshots": [
    {
      "asOf":      "2026-05-17T...",
      "asOfDate":  "2026-05-17",
      "asOfPrice": 77936.0,
      "series": [
        { "t": "2026-05-17T...", "v": 77936 },
        { "t": "2026-05-18T...", "v": 78180 },
        ...
        { "t": "2026-06-16T...", "v": 83929 }
      ],
      "metadata": {
        "stance":     "BULLISH",
        "confidence": 0.781,
        "analogCount": 10,
        "source":     "rolling_v1"
      }
    }
  ]
}
```

Frontend `LivePredictionChart` рисует **каждый snapshot trimmed по asOf следующего** → формируется непрерывная чёрная линия "что модель думала тогда".

---

## Meta Brain — 15 endpoints (все real)

| Endpoint | Что считает | Источник |
|---|---|---|
| `/api/meta-brain-v2/status` | Live status + активные модули | trading_runtime + counters |
| `/api/meta-brain-v2/state` | Verdict + moduleConfidence + recent signals | build_verdict + signal_log |
| `/api/meta-brain-v2/signals` | Свежие regime signals | regime_signals |
| `/api/meta-brain-v2/signals/aligned` | Aligned-фильтр alignment ≥ 0.6 | signal_history |
| `/api/meta-brain-v2/drift` | StdDev confidence за окно | signal_log |
| `/api/meta-brain-v2/influence` | Per-actor score | actor_signal_events |
| `/api/meta-brain-v2/performance` | Hit-rate + sharpe | signal_history outcomes |
| `/api/meta-brain-v2/correlation` | Pearson на log-returns | BTC/SPX/DXY candles |
| `/api/meta-brain-v2/modules` | Health 5 модулей | trading_runtime |
| `/api/meta-brain-v2/policy` | Runtime config | static + DB |
| `/api/meta-brain-v2/dataset/stats` | Counters 8 коллекций | Mongo |
| `/api/meta-brain-v2/dataset/runs` | Recent forecast runs | fractal_forecasts + exchange |
| `/api/meta-brain-v2/forecast-table` | Forecasts by horizon | fractal_forecasts |
| `/api/ui/brain/decision` | Финальный verdict + macro fusion | Python brain service |
| `/api/v10/meta-brain/snapshots` | Joined decisions (BTC/SPX/DXY) | fractal_forecasts |

---

## MBrain Verdicts (Expo Mobile)

### `GET /api/mbrain/verdicts/list`

Список inspector-карточек по всем активам.

**Query:** `limit=50&status=OPEN`

**Ответ:**
```json
{
  "n": 50,
  "source": "native_fractal_forecasts",
  "cards": [
    {
      "symbol":    "BTC",
      "horizon":   "30D",
      "ts":        "2026-05-17T...",
      "final_action": "HOLD",
      "confidence_final": 0.32,
      "modelId":   "fractal_native_v1",
      "stages":    {...},
      "rules":     [...]
    }
  ]
}
```

---

## Telegram MiniApp

### `GET /api/miniapp/core?asset=BTC`

Сжатый combined-payload для MiniApp.

**Ответ:**
```json
{
  "asset": "BTC",
  "decision": { "action": "WAIT", "strength": "NORMAL", "confidence": 24 },
  "scenario": { "low": 78004, "high": 78395 },
  "signals":   [... 5 items ...],
  "polymarket": { "market": "Bitcoin >$70k on May 22", "prob": 0.979 }
}
```

---

## Walk-Forward Backfill (Python)

Скрипт `/app/backend/scripts/backfill_rolling_forecasts.py` вычисляет
"что модель предсказала на каждый день в прошлом" — без peek-into-future.

```bash
python3 backfill_rolling_forecasts.py \
  --days 365      # сколько дней назад идти
  --stride 3      # snapshot каждые N дней
  --horizon 30    # forecast длиной N дней вперёд
  --window 120    # similarity window
  --topk 10       # сколько top analogs
  --wipe          # очистить старые snapshots
```

Auto-update запускается каждые 6 часов supervisor-процессом `rolling_forecast_loop`.

---

## Data Sources (Mongo `fomo_mobile`)

| Collection | Объём | Период | Использование |
|---|---|---|---|
| `fractal_canonical_ohlcv` | 5,783 (BTC 1d) | 2010-07-18 → 2026-05-17 | Node Fractal engine |
| `spx_candles` | 19,242 | **1950-01-03** → 2026-02-20 | SPX engine |
| `dxy_candles` | 13,366 | **1973-01-02** → 2026-02-20 | DXY engine |
| `fractal_rolling_snapshots` | 128 (BTC) | 2025-05-17 → 2026-05-17 | Chart curve |
| `signal_history` | 14 | live | Meta Brain alignment/perf |
| `signal_log` | 36 | live | Drift |
| `actor_signal_events` | 209 | live | Influence |
| `regime_signals` | 33 | live | Status |
| `{btc,spx,dxy}_fractal_forecasts` | 5 each | live | Snapshots / verdicts |

---

## Supervisor Processes

| Process | Purpose | Default config |
|---|---|---|
| `backend` | FastAPI :8001 | `supervisord.conf` |
| `node_sidecar` | Fractal v2.1 engine :8003 | `supervisord_node_sidecar.conf` |
| `rolling_forecast_loop` | Auto-update snapshots (6h) | `supervisord_rolling_forecast.conf` |
| `news_substrate` | Sentiment ingest | `supervisord_news_substrate.conf` |
| `frontend` | React :3000 | supervisord.conf |
| `mongodb` | DB | supervisord.conf |
| `nginx-code-proxy` | Routing | `supervisord_nginx_proxy.conf` |

Управление:
```bash
supervisorctl status                       # все
supervisorctl restart node_sidecar         # один
supervisorctl tail -f node_sidecar         # логи
```
