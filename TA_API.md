# TA Module — Real-Data Deployment

> **Status:** ✅ All TA endpoints serve real data from `native_ta_v1` engine.
> **Last reviewed:** 2026-05-17
> **Audit:** zero `legacy_compat_stub_empty` responses on any endpoint
> consumed by Web SPA, Expo Mobile, or Telegram MiniApp.

---

## 1. Architecture

```
                   ┌────────────────────────────────┐
                   │  services.technical_analysis   │  ← single source of truth
                   │      (native_ta_v1)            │     (RSI · trend · momentum ·
                   │                                │      S/R · volatility · 20 syms)
                   └──────────────┬─────────────────┘
                                  │
            ┌─────────────────────┼──────────────────────┐
            │                     │                      │
            ▼                     ▼                      ▼
   /api/ta/* (legacy)    /api/ta-engine/*          /api/miniapp/tech-*
   /api/v10/ta/*         /api/indicators/*         (Expo Mobile)
   /api/prediction/ta/*  (Web SPA · /terminal)     (real candles + multi-TF)
   (Web SPA + cockpit)
            │
            ▼
   routes/tech_analysis_real.py  ← mounted BEFORE legacy_compat
   routes/tech_analysis_runtime.py (real OKX/CoinGecko candle fetch)
   routes/ta.py (basic + summary)
   routes/ta_prediction.py (multi-source prediction)
```

Routers are mounted in `backend/server.py` so the **real** handler always
wins over the `legacy_compat` catch-all:

| Router file                      | Mount order | Endpoints                                      |
| -------------------------------- | ----------- | ---------------------------------------------- |
| `routes/ta.py`                   | early       | `/api/ta/{health,basic/{sym},summary}`         |
| `routes/ta_prediction.py`        | early       | `/api/ta/prediction/{sym}`                     |
| `routes/tech_analysis_real.py`   | **early**   | *(NEW — see §2)*                               |
| `routes/tech_analysis_runtime.py`| late        | `/api/ta-engine/mtf/{sym}` (real candles)      |
| `routes/legacy_compat.py`        | last        | catch-all (now never reached for TA)           |

---

## 2. Endpoints — `routes/tech_analysis_real.py`

All of the following used to return `legacy_compat_stub_empty`.  Each is
now backed by the in-process `services.technical_analysis.analyze` call
(no HTTP hop, no fake data):

### 2.1 Multi-timeframe & per-symbol indicator packs

| Method · Path                                | Schema                                      | Used by                       |
| -------------------------------------------- | ------------------------------------------- | ----------------------------- |
| `GET /api/ta-engine/mtf?symbol=BTC`          | `tf_map[1D/4H/1H/1W].{decision,...}`        | (alias of `mtf/{sym}`)        |
| `GET /api/v10/ta/summary`                    | `{symbolsTracked, symbolsLive, results}`    | Cross-asset dashboards         |
| `GET /api/v10/ta/snapshot?symbol=BTC`        | same as `ta-engine/mtf`                     | Per-asset snapshot card        |
| `GET /api/v10/ta/full?symbols=BTC,ETH,SOL`   | `{results: {SYM: native_ta_v1, …}}`         | Bulk pulls                     |
| `GET /api/indicators/all`                    | `{symbols: 20, indicators: [...]}`          | Indicator screener             |
| `GET /api/indicators/{SYM}`                  | per-symbol indicator pack                   | Coin detail panes              |

### 2.2 Prediction (data-source-aware)

The Terminal "Prediction" tab can call **either** the exchange-side
forecaster (`/api/prediction/exchange/*`) or the TA-side forecaster
(`/api/prediction/ta/*`).  `PredictionPage.jsx` now respects the
`apiPath` prop and routes accordingly.

| Method · Path                                       | Returns                                     |
| --------------------------------------------------- | ------------------------------------------- |
| `GET /api/prediction/ta/live-price?asset=BTC`       | `{price, source: ta_engine_live}`           |
| `GET /api/prediction/ta/forecast?asset=BTC`         | multi-horizon targets (24H, 7D, 30D)        |
| `GET /api/prediction/ta/graph4?asset=BTC&horizon=…` | priceSeries (30+ real candles) + 1 forecast |
| `GET /api/prediction/ta/snapshot?symbol=BTC`        | single TA snapshot (alias)                  |
| `GET /api/prediction/ta/{SYM}`                      | TA-driven single-shot forecast              |

**Forecast math** (no magic numbers):

```
target = currentPrice ± (resistance − support) / 2 × confidence × √(days / 30)
```

- Diffusion-like √-days scaling — longer horizons widen, but with
  diminishing returns.  No straight-line extrapolation.
- When TA decision is `WAIT`, `target = current` and `movePct = 0`.
  We **do not** invent direction.

### 2.3 Setup / Structure / Levels / Confluence (legacy paths)

`setupService.js` historically called these — now all real:

| Method · Path                                          |
| ------------------------------------------------------ |
| `GET /api/ta/setup?symbol=BTC&tf=1D`                   |
| `GET /api/ta/setup/v2?symbol=BTC&tf=1D`                |
| `GET /api/ta/levels/{SYM}/{TF}`                        |
| `GET /api/ta/structure/{SYM}/{TF}`                     |
| `GET /api/ta/indicators/{SYM}/{TF}`                    |
| `GET /api/ta/confluence/{SYM}/{TF}`                    |
| `GET /api/ta/patterns/{SYM}/{TF}`  *(honest stub — see below)* |
| `GET /api/ta-engine/{regime,levels,patterns,snapshot,decision}` |
| `GET /api/ta/{regime,decision}`                        |

### 2.4 Honest Disclosures

Two endpoints carry a `note` field so callers can detect partially-real
data:

- `/api/ta/patterns/*` / `/api/ta-engine/patterns` →
  `"pattern_detection_not_implemented_in_native_ta_v1"`.
  Returns empty `patterns: []` + real `support/resistance/currentPrice`.
- `/api/prediction/ta/graph4` →
  `"ta_walk_forward_not_implemented_returning_current_snapshot_only"`.
  Returns 30+ real candles + the **current** TA forecast, but no
  fabricated historical rolling forecasts.

These notes are intentional — we will never silently return fake history.

---

## 3. Surface Coverage

| Surface          | Entry point                                  | Backend it hits                                       | Real data? |
| ---------------- | -------------------------------------------- | ----------------------------------------------------- | ---------- |
| Web SPA (`/`)    | `pages/Terminal/index.jsx` → ResearchViewNew | `GET /api/ta-engine/mtf/{sym}` (path-param, candles)  | ✅          |
| Web SPA (`/`)    | TAPredictionTab → PredictionPage             | `GET /api/prediction/ta/{graph4,forecast,live-price}` | ✅          |
| Web SPA (`/`)    | TechAnalysisModule (cockpit)                 | `GET /api/ta/setup`, `/api/ta/levels/...`             | ✅          |
| Expo Mobile      | `app/tech-analysis.tsx`                      | `GET /api/miniapp/tech-{analysis,watchlist}`          | ✅          |
| Telegram MiniApp | (no TA screen)                               | n/a                                                   | n/a        |

---

## 4. Engine Capabilities (native_ta_v1)

Per-symbol output of `services.technical_analysis.analyze(symbol)`:

```json
{
  "symbol": "BTC", "ok": true,
  "state": "neutral",  "direction": "WAIT",
  "trend": "range",    "trendSlopePct": -0.19,
  "momentum": "decelerating",
  "rsi": "neutral",    "rsiValue": 49.4,
  "volatility": "normal",
  "support": 73823.14, "resistance": 82199.99,
  "currentPrice": 78419.0,
  "confidence": 0.18,  "alignedIndicators": 0,
  "reasons": ["price inside a broad range, no directional trend", …],
  "source": "native_ta_v1",
  "asOf": "2026-05-17T20:09:06Z"
}
```

Tracked symbols (`SYMBOLS` in `services.technical_analysis`): 20 majors
(BTC, ETH, SOL, BNB, XRP, ADA, DOGE, …) with daily-bar history.

---

## 5. Health-check (one-shot)

```bash
curl -s "$BACKEND/api/ta/health"            | jq .ok
curl -s "$BACKEND/api/ta/summary"           | jq '.symbolsLive, .symbolsTracked'
curl -s "$BACKEND/api/ta-engine/mtf/BTC"    | jq '.ok, .source, .consensus.action'
curl -s "$BACKEND/api/prediction/ta/BTC"    | jq '.ok, .direction, .currentPrice'
curl -s "$BACKEND/api/indicators/all"       | jq '.symbols'
curl -s "$BACKEND/api/miniapp/tech-analysis?asset=BTC&timeframe=1D" | jq '.ok, .rsi, .action'
```

All must return `ok: true` and a real `source: native_ta_v1` (or
`ta_engine_mtf_v1` for the path-param MTF endpoint).

If any one of them returns `note: "legacy_compat_stub_empty"` → the
real router did not mount.  Check `tail -n 200 /var/log/supervisor/backend.out.log`
for `[TechAnalysisReal] import failed:` traces.

---

## 6. Cold-boot

Run `scripts/cold_boot_ta.sh` to verify a clean restart.  It restarts
the backend supervisor process and walks the health-check above.
