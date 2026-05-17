# FOMO Platform — Deployment PRD

## Project
Crypto Prediction Intelligence OS. 10 AI layers (Fractal, Exchange, Sentiment,
On-Chain, MetaBrain, Polymarket, Bakery, Radar, Smart-Money, News AI) served
across **4 surfaces** that share one FastAPI brain.

GitHub source: https://github.com/L2PAD/APPvM

## Architecture (deployed)

```
Kubernetes ingress
  /api/*  → backend :8001 (FastAPI)
  /       → expo    :3000 (Expo Router)

Backend (FastAPI, /app/backend)
  ├── server.py — 7,485 lines, ~30 routers mounted
  ├── admin_build/ — pre-compiled React SPA (admin panel + /info landing)
  ├── miniapp-web/ — static Telegram Mini App SPA
  ├── miniapp/      — Telegram bot server-side (home_builder, edge_builder...)
  ├── modules/mbrain_adapters/trading_terminal_adapter.py — degraded stub
  └── services/quality/ — Sprint 2 merge from FOMO-ML (5+2 gates, R1-R5 integrity)

Frontend (Expo, /app/frontend)
  ├── app/index.tsx — AppGate
  ├── app/{info,exchange,ref,snapshot,legal,privacy}.tsx — Web-only shims
  └── src/ — modules, stores, services
```

## Modules deployed in this session

| # | Surface | URL | Status |
|---|---------|-----|--------|
| 1 | Expo Mobile App (Web + iOS + Android) | `/` | ✅ Running on Metro :3000 with tunnel |
| 2 | Web React Admin Panel | `/api/panel/admin` | ✅ Login page renders |
| 3 | /info landing (Continue with Google) | `/info` → `/api/panel/info` | ✅ Renders with 10 AI layers copy |
| 4 | Telegram Mini App SPA (lite) | `/api/miniapp/lite` | ✅ Renders BTC/ETH/SOL switcher + structure snapshot |
| 5 | Backend FastAPI core | `/api/health` | ✅ 200 OK, MongoDB connected |
| 6 | Trading OS (Operator Desk inside Expo) | `/` → Trade tab | ✅ Renders — Cognitive Timeline, AI Focus, Capital Posture, AI Readiness Engine |

## Merge audit verification (per MERGE_AUDIT.md + TERMINAL_REMOVAL_SPRINT)

1. **FOMO-ML / FOMO-ML-2 → /app/backend additive merge** — ✅ Verified
   - `backend/services/quality/` (5 files, ~970 lines): resolve_timing, integrity_guard, accumulation_monitor, pre_truth_check
   - `backend/routes/quality.py` — 6 admin-gated endpoints under `/api/quality/*`
   - `RESOLVE_TIMING_MODE=v1` flag in backend env (default, prod)
   - Smoke: `GET /api/quality/resolve-timing-mode` → 401 ADMIN_REQUIRED ✅

2. **Trading Terminal block** — ✅ Native FastAPI roots `/api/ta/*`, `/api/sentiment/runtime/*`, `/api/fractal/runtime/*`, `/api/mbrain/*`
   - `GET /api/ta/health` → 200 ✅
   - Legacy F-TRADE-MODULE side-car at :8002 was removed 2026-05-12 per TERMINAL_REMOVAL_SPRINT — replaced by native routes and "Operator Desk" reframe inside Expo (bottom tabs: FOMO / Command / Market / Execution / Portfolio)
   - `modules/mbrain_adapters/trading_terminal_adapter.py` is intentionally a degraded stub returning `{ok:False, error:"terminal_removed"}` — preserves `ta_shadow_fusion.py` and `routes/mbrain_shadow.py` import contracts

## Infrastructure
- MongoDB: `mongodb://localhost:27017` (DB: `test_database` per current `/app/backend/.env`)
- Supervisor: backend, expo, mongodb, nginx-code-proxy, code-server all RUNNING
- Public preview URL: https://mobile-app-core.preview.emergentagent.com

## Known / non-blocking
- Cold-boot script (`scripts/cold_boot.sh`) NOT executed yet — historical replay,
  admin seeding (`admin/admin12345`), Telegram webhook registration are
  pending. Run when ready: `bash /app/scripts/cold_boot.sh`
- Several optional intelligence modules require credentials before they
  produce data (Sentiment LLM key, On-Chain RPC, Telegram Intel MTProto,
  Proxy Pool for Exchange) — module manager toggles available.
- CoinGecko free tier hits 429 occasionally — fallback to Binance is in place.
- Expo `shadow*` style deprecation warnings — non-blocking.

## Frozen by user instruction
> "Пока не нужно ничего дорабатывать, просто разворачивай проект"
No code changes were made — pure deployment only.
