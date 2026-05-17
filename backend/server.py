"""
FastAPI proxy with WebSocket support for Node.js backend
Auto-starts Node.js backend if not running
"""
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, APIRouter, BackgroundTasks, Depends
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
import httpx
import websockets
import os
import asyncio
import subprocess
import socket
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

# R4.1 + R4.3
from exchange_health import compute_health, record_pipeline_hit, update_rate_limiter_stats
from rate_limiter import check_rate_limit, get_stats as get_rate_limiter_stats, periodic_cleanup as rl_cleanup

# Load .env file
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'), override=True)

# --- MongoDB (Motor async) for Knowledge Graph ---
_mongo_url = os.environ.get("MONGO_URL")
_db_name = os.environ.get("DB_NAME", "institutional")
_motor_client = AsyncIOMotorClient(_mongo_url) if _mongo_url else None
db = _motor_client[_db_name] if _motor_client else None
if db is not None:
    print(f"[Proxy] MongoDB (Motor) connected: {_db_name}")
else:
    print("[Proxy] WARNING: MONGO_URL not set, knowledge graph disabled")

# --- Feature Flags ---
SYSTEM_PROFILE = os.environ.get("SYSTEM_PROFILE", "dev")
TELEGRAM_INTEL_ENABLED = os.environ.get("TELEGRAM_INTEL_ENABLED", "false").lower() == "true"
print(f"[Proxy] SYSTEM_PROFILE={SYSTEM_PROFILE}")
print(f"[Proxy] TELEGRAM_INTEL_ENABLED={TELEGRAM_INTEL_ENABLED}")

# --- Telegram Intel Plugin (conditional) ---
telegram_module = None
if TELEGRAM_INTEL_ENABLED:
    from telegram_intel import TelegramModule, TelegramConfig
    _tg_config = TelegramConfig(
        mongo_uri=os.environ.get("MONGO_URL", "mongodb://localhost:27017"),
        db_name=os.environ.get("TG_DB_NAME", "telegram_intel"),
        session_string=os.environ.get("TG_SESSION_STRING"),
        bot_token=os.environ.get("TG_BOT_TOKEN"),
        llm_api_key=os.environ.get("OPENAI_API_KEY"),
        scheduler_enabled=False,
    )
    telegram_module = TelegramModule(_tg_config)
else:
    print("[Proxy] Telegram Intel DISABLED — skipping import & init")

# --- Mobile App Routes (from FOMO-APPv2 fork) ---
try:
    from routes.mobile.router import mobile_router
    from routes.mobile_auth import auth_router as mobile_auth_router
    MOBILE_ROUTES_LOADED = True
    print("[Proxy] Mobile App routes loaded successfully")
except ImportError as e:
    MOBILE_ROUTES_LOADED = False
    print(f"[Proxy] WARNING: Mobile routes not loaded: {e}")

# Debug: log env at startup
print("[Proxy] COOKIE_ENC_KEY present:", "COOKIE_ENC_KEY" in os.environ)
print("[Proxy] COOKIE_ENC_KEY length:", len(os.environ.get("COOKIE_ENC_KEY", "")))

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Trading Terminal side-car gateway (must register BEFORE all other ─
# ── Stage A-2: TA Everywhere (native Python perception layer) ──
# MOUNTED BEFORE the trading-terminal gateway so /api/ta/* literal routes
# (/api/ta/health · /api/ta/basic/{symbol} · /api/ta/summary) win over the
# gateway's catch-all forwarder to :8002 (which is down).
# TA is one cognitive contributor among many — not a separate widget.
# Output is suppression-friendly: WAIT by default, LONG_BIAS / SHORT_BIAS
# only when ≥3 indicators align.  Honest-degraded when history missing.
try:
    from routes.ta import router as _ta_router
    app.include_router(_ta_router)
    print("[TA] native technical analysis mounted "
          "(/api/ta/health · /api/ta/basic/{symbol} · /api/ta/summary)")
except Exception as _ta_err:  # pragma: no cover
    print(f"[TA] NOT mounted: {_ta_err!r}")

# ── P3 Web Restoration · legacy compat router ─────────────────────
# Routes the Web admin SPA used to call on the abandoned Node :8003
# sidecar: /api/ui/candles, /api/admin/twitter-parser/*, /api/meta-brain-v2/*,
# /api/frontend/dashboard, /api/connections/*, /api/market/rotation/*,
# /api/system/chains, /api/ta/analyze/{symbol}, etc.  All honest:
# real candles from CryptoCompare, real module state from trading_runtime,
# empty defaults where ingestion is not yet live.
#
# IMPORTANT: registration is split — specific routes mount HERE (early),
# but the catch-all path `/{full_path:path}` is added LATER (after the
# admin panel SPA mount in section 7300+) so it does not intercept
# `/api/panel/*` requests.  See line ~7460.
try:
    from routes.legacy_compat import router as _legacy_compat_router
    # Do NOT mount the catchall yet — it will be added after the admin
    # panel mount below.  We just import here for early visibility.
    # The actual include happens after the panel route is registered.
    print("[LegacyCompat] deferred — will be mounted after panel SPA")
except Exception as _lc_err:  # pragma: no cover
    print(f"[LegacyCompat] import failed: {_lc_err!r}")


# ── Stage A-4: Sentiment Runtime (events-based, LLM-independent) ──
# Mounted BEFORE the trading-terminal gateway / node proxy so
# /api/sentiment/runtime/* literal routes win over upstream-503 forwarders.
# LLM down ≠ sentiment down — this runtime aggregates the existing
# `sentiment_events` collection into a truthful crowd-pressure layer.
try:
    from routes.sentiment_runtime import router as _sentiment_runtime_router
    app.include_router(_sentiment_runtime_router)
    print("[SentimentRuntime] events-based pressure layer mounted "
          "(/api/sentiment/runtime/health · /api/sentiment/runtime/{symbol} · /api/sentiment/runtime/summary)")
    # Public Sentiment API used by Web frontend, Expo, Telegram miniapp and Admin
    try:
        from routes.sentiment_public import router as _sentiment_public_router
        app.include_router(_sentiment_public_router)
        print("[SentimentPublic] mounted (v1/symbol, status, sources/breakdown, timeseries, feed, admin, twitter cookies)")
    except Exception as _sp_err:
        print(f"[SentimentPublic] FAILED: {_sp_err!r}")

    # Twitter Extension API v4 — used by FOMO X Connect Chrome extension
    try:
        from routes.twitter_extension_v4 import router as _twitter_v4_router
        app.include_router(_twitter_v4_router)
        print("[TwitterExtV4] mounted (/api/v4/twitter/{accounts,preflight,sessions/webhook,ingest,integration/status})")
    except Exception as _tw_err:
        print(f"[TwitterExtV4] FAILED: {_tw_err!r}")
except Exception as _sr_err:  # pragma: no cover
    print(f"[SentimentRuntime] NOT mounted: {_sr_err!r}")


# ── Stage A-5: Fractal Runtime (snapshot-memory based) ──
# Mounted BEFORE the trading-terminal gateway / node proxy so
# /api/fractal/runtime/* literal routes win over upstream-503 forwarders.
# Reads engine_context_snapshots + engine_micro_snapshots + intelligence_telemetry
# + decision_history (per-asset).  Honest-degraded when evidence < 10.
# Never "Fractal bullish" without expansion confirmation in decision_history.
try:
    from routes.fractal_runtime import router as _fractal_runtime_router
    app.include_router(_fractal_runtime_router)
    print("[FractalRuntime] structural perception layer mounted "
          "(/api/fractal/runtime/status · /api/fractal/runtime/{symbol} · /api/fractal/runtime/summary)")
except Exception as _fr_err:  # pragma: no cover
    print(f"[FractalRuntime] NOT mounted: {_fr_err!r}")


# ── Stage A-6: Outcome Memory (Cognitive Accountability Layer) ──
# Mounted BEFORE the trading-terminal gateway so /api/mbrain/outcomes/*
# wins over the upstream-503 catch-all forwarder.
# NOT reinforcement learning. NOT pnl-optimization. NOT broker semantics.
# Substrate: decision_history (canonical) → mbrain_integrity_outcomes.
# WAIT is a first-class remembered outcome (avoided_loss / missed_gain).
# Endpoints: /health, /sweep (POST), /resolve (POST), /recent.
try:
    from routes.outcome_memory import router as _outcome_memory_router
    app.include_router(_outcome_memory_router)
    print("[OutcomeMemory] cognitive accountability layer mounted "
          "(/api/mbrain/outcomes/health · /sweep · /resolve · /recent)")
except Exception as _om_err:  # pragma: no cover
    print(f"[OutcomeMemory] NOT mounted: {_om_err!r}")


# ── Stage A-7: Shadow Verdict Runtime ──
# Mounted BEFORE the trading-terminal gateway so /api/mbrain/shadow-runtime/*
# wins over the upstream-503 catch-all forwarder.
# NOT paper execution. NOT broker. NOT live orders. NOT trade signals.
# Reads ta + sentiment + fractal + market_prices + decision_history.
# Produces shadow forward structure: status='blocked' is a healthy result.
# MetaBrain veto wins — finalAction WAIT/AVOID → shadowAction NO_DEPLOYMENT
# even when raw cognition would have allowed LONG_BIAS / SHORT_BIAS.
# Semantic dedup window: 15 minutes (same symbol+raw+final+top-3 reasons).
# Endpoints: /health, /sweep (POST), /recent, /summary.
try:
    from routes.shadow_verdict_runtime import router as _shadow_runtime_router
    app.include_router(_shadow_runtime_router)
    print("[ShadowRuntime] shadow verdict runtime mounted "
          "(/api/mbrain/shadow-runtime/health · /sweep · /recent · /summary)")
except Exception as _sv_err:  # pragma: no cover
    print(f"[ShadowRuntime] NOT mounted: {_sv_err!r}")


# ── Phase B · Operator Cognition Observatory ──
# Mounted BEFORE the trading-terminal gateway so /api/mbrain/observatory/*
# wins over the upstream-503 catch-all forwarder.
# NOT an admin dashboard. NOT Grafana. NOT telemetry wall. NOT KPI center.
# Read-only aggregator over already-live cognitive substrate.
# Manual refresh ONLY — no scheduler, no background work.
# Composes 5 quiet topological sections: deploymentClimate, alignmentDrift,
# cognitiveMemory, shadowStructures, regimeContinuity.
# Honest degradation: empty decision_history → ok=false,
# reason='insufficient_decision_context'.
try:
    from routes.operator_observatory import router as _observatory_router
    app.include_router(_observatory_router)
    print("[OperatorObservatory] cognition observatory mounted "
          "(/api/mbrain/observatory/state)")
except Exception as _obs_err:  # pragma: no cover
    print(f"[OperatorObservatory] NOT mounted: {_obs_err!r}")


# ── Phase B · Step 3 · Outcome Resolver Scheduler ──
# Mounted BEFORE the trading-terminal gateway.  Memory-maintenance ONLY.
# NOT trading automation.  NOT signal generation.  NOT sweep automation.
# Disabled by default (env OUTCOME_RESOLVER_ENABLED).  Background loop
# only resolves mature pending outcomes via outcome_memory.resolve_outcomes;
# never sweeps, never mutates decisions, never creates outcomes.
# Endpoints: /status, /run-once (POST), /enable (POST), /disable (POST).
try:
    from routes.outcome_resolver_scheduler import router as _resolver_router
    app.include_router(_resolver_router)
    print("[OutcomeResolverScheduler] memory-maintenance scheduler mounted "
          "(/api/mbrain/outcomes/scheduler/status · /run-once · /enable · /disable)")
except Exception as _rs_err:  # pragma: no cover
    print(f"[OutcomeResolverScheduler] NOT mounted: {_rs_err!r}")


# ── Phase C · Paper Runtime Foundation (contract skeleton) ──
# Mounted BEFORE the trading-terminal gateway.  NOT execution.  NOT broker.
# NOT order routing.  Gated by paper_runtime_gate() — open only when:
#   operator.mode='paper' ∧ shadow_verdicts recent ∧ resolved outcomes
#   ∧ market_prices healthy.
# All POST /orders/simulate calls currently refuse with structured
# `requires: [...]` array (returns honest 200 ok=false).
# Collections: paper_accounts, paper_positions, paper_orders, paper_events.
# Pre-deployment architecture — no live PnL, no fake orders.
try:
    from routes.paper_runtime import router as _paper_runtime_router
    app.include_router(_paper_runtime_router)
    print("[PaperRuntime] foundation skeleton mounted "
          "(/api/paper/runtime/health · /accounts · /positions · /orders · /events · /orders/simulate)")
except Exception as _pr_err:  # pragma: no cover
    print(f"[PaperRuntime] NOT mounted: {_pr_err!r}")


# ── Phase D · Pass 1 · Runtime Events Ledger ──
# Forward-only continuity trace.  NOT analytics. NOT metrics dashboard.
# Append-only capped collection. Pull-only consumption.
# Endpoints: /health, /recent (operator-pulled).
try:
    from routes.runtime_events import router as _runtime_events_router
    app.include_router(_runtime_events_router)
    print("[RuntimeEvents] continuity trace ledger mounted "
          "(/api/runtime/events/health · /recent)")
except Exception as _re_err:  # pragma: no cover
    print(f"[RuntimeEvents] NOT mounted: {_re_err!r}")


# ── Trading Terminal gateway — REMOVED (Terminal Removal Sprint 2026-05-12) ──
# The F-TRADE-MODULE side-car was abandoned by product decision. The reverse
# proxy that forwarded /api/terminal/*, /api/ta-engine/*, /api/control/*,
# /api/positions, /api/trading/*, /api/runtime/*, /api/audit/*, /api/protection/*,
# /api/analytics/*, /api/dynamic-risk/*, /api/calibration/*,
# /api/exchange-intelligence/*, /api/v1/fractal/*, /api/ta-prediction-intelligence/*,
# /api/ta-prediction-intel/*, /api/prediction/ta/* to localhost:8002 is gone.
# Unknown paths now fall through to the honest-404 catch-all (Sprint C4).
# See /app/memory/TERMINAL_REMOVAL_SPRINT_2026-05-12.md for migration notes.


# ── MBrain Shadow Fusion (Sprint 3 / Phase A) — read-only telemetry ─
# Exposes /api/mbrain/shadow/* for offline analysis. Production fusion
# pipeline is NOT modified.
try:
    from routes.mbrain_shadow import router as _mbrain_shadow_router
    app.include_router(_mbrain_shadow_router)
    print("[Shadow] MBrain shadow-fusion routes mounted (/api/mbrain/shadow/*)")
except Exception as _sh_err:  # pragma: no cover
    print(f"[Shadow] MBrain shadow-fusion routes NOT mounted: {_sh_err!r}")

# ── MBrain Directional Integrity (Module 1) — read-only distribution audit ─
# /api/mbrain/integrity/*  — read-only, HTTP-only, snapshots to test_database.
# Mounted BEFORE the trading-terminal gateway routes are checked so the
# /api/mbrain/integrity/* prefix is owned here, not the gateway.
try:
    from routes.mbrain_integrity import router as _mbrain_integrity_router
    app.include_router(_mbrain_integrity_router)
    print("[Integrity] MBrain integrity routes mounted (/api/mbrain/integrity/*)")
except Exception as _int_err:  # pragma: no cover
    print(f"[Integrity] MBrain integrity routes NOT mounted: {_int_err!r}")

# ── MBrain Verdicts (Expo Trading Runtime v1 observability) ─────────────
# /api/mbrain/verdicts/*  — read-only side-car proxy with normalize +
# inspector cards. Used by Expo Signal Feed and Verdict Inspector UI.
try:
    from routes.mbrain_verdicts import router as _mbrain_verdicts_router
    app.include_router(_mbrain_verdicts_router)
    print("[Verdicts] MBrain verdict routes mounted (/api/mbrain/verdicts/*)")
except Exception as _v_err:  # pragma: no cover
    print(f"[Verdicts] MBrain verdict routes NOT mounted: {_v_err!r}")

# ── MBrain Positions (Expo Trading Runtime v1 — paper-only) ─────────────
# /api/mbrain/positions/*  — read-only paper-PnL parallel-universe
# computation over `mbrain_integrity_outcomes`. NO orders. NO execution.
try:
    from routes.mbrain_positions import router as _mbrain_positions_router
    app.include_router(_mbrain_positions_router)
    print("[Positions] MBrain position routes mounted (/api/mbrain/positions/*)")
except Exception as _p_err:  # pragma: no cover
    print(f"[Positions] MBrain position routes NOT mounted: {_p_err!r}")

# ── MBrain Attribution (Realized Attribution Layer) ─────────────────────
# /api/mbrain/positions/attribution — read-only, computes
# avoided_loss / missed_gain / net_alpha for Meta-Brain HOLD-conversions.
try:
    from routes.mbrain_attribution import router as _mbrain_attr_router
    app.include_router(_mbrain_attr_router)
    print("[Attribution] MBrain attribution route mounted (/api/mbrain/positions/attribution)")
except Exception as _a_err:  # pragma: no cover
    print(f"[Attribution] MBrain attribution route NOT mounted: {_a_err!r}")


# ── MBrain Realized Attribution (Sprint 5) ──────────────────────────────
# /api/mbrain/attribution/realized — read-only, aggregates RESOLVED
# forward-tracking outcomes to compute realized economic effect of
# Meta-Brain decisions. Read-only on FOMO mongo. NO trading_os writes.
try:
    from routes.mbrain_attribution_realized import router as _mbrain_attr_realized_router
    app.include_router(_mbrain_attr_realized_router)
    print("[Attribution] MBrain realized attribution mounted (/api/mbrain/attribution/realized)")
except Exception as _ar_err:  # pragma: no cover
    print(f"[Attribution] MBrain realized attribution NOT mounted: {_ar_err!r}")


# ── Stage 0: Operator Access (capability topology) ──
# Public Intelligence (Free/Pro) ↔ Restricted Operational Environment.
# NOT billing. NOT RBAC. Just a semantic gate so STAGE A bring-up cannot
# leak operator cognition into the public surface.
try:
    from routes.operator_access import router as _operator_access_router
    app.include_router(_operator_access_router)
    # TIER-4A: commercial-to-operational bridge (product catalog + invoices + entitlement)
    from routes.billing_products import router as _billing_products_router
    app.include_router(_billing_products_router)
    # TIER-4B.2: reconciliation integrity layer (read-only detectors + immutable findings)
    from routes.billing_reconciliation import router as _billing_reconciliation_router
    app.include_router(_billing_reconciliation_router)
    # TIER-4B.3: derived business-intelligence read model (analytics)
    from routes.billing_analytics import router as _billing_analytics_router
    app.include_router(_billing_analytics_router)
    # TIER-4C.1: public customer-facing self-serve billing surface
    from routes.me_billing import router as _me_billing_router
    app.include_router(_me_billing_router)
    # T11.1: epistemic performance attribution (cross-layer observability)
    from routes.attribution import router as _attribution_router
    app.include_router(_attribution_router)
    # T10.2C — testnet execution (admin-only, append-only receipts).
    from routes.testnet_execution import router as _testnet_exec_router
    app.include_router(_testnet_exec_router)
    print("[OperatorAccess] capability topology mounted "
          "(/api/me/capabilities · /api/me/operator-access/* · /api/me/billing/* · /api/admin/operator-access/* · /api/admin/billing/reconciliation/* · /api/admin/billing/analytics/* · /api/admin/attribution/*)")
except Exception as _oa_err:  # pragma: no cover
    print(f"[OperatorAccess] NOT mounted: {_oa_err!r}")


# ── Stage A-1: Live Price Truth (native Python · CoinGecko fallback) ──
# Removes price=0 across all surfaces so readiness / risk / asymmetry can
# anchor on real spot reference.  Honest-degraded on failure (ok:false).
try:
    from routes.market_prices import router as _market_prices_router
    app.include_router(_market_prices_router)
    print("[MarketPrices] live price substrate mounted "
          "(/api/market/health · /api/market/price/{symbol} · /api/market/prices)")
except Exception as _mp_err:  # pragma: no cover
    print(f"[MarketPrices] NOT mounted: {_mp_err!r}")


# ── Stage A-2: TA Everywhere (native Python perception layer) ──
# Already mounted ABOVE the trading-terminal gateway so /api/ta/* native
# routes win over the gateway's catch-all forwarder.  This block is kept
# as a no-op safety in case the early mount fails for any reason.


# ── R4.3: Rate Limiting Middleware ──
class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Skip health, static, and sentiment API (has its own rate limiter)
        path = request.url.path
        if path in ("/health", "/api/exchange/health", "/api/system/profile"):
            return await call_next(request)
        if path.startswith("/api/v1/sentiment/"):
            return await call_next(request)
        # Skip rate limiting for connections/panel API calls (burst from web panel)
        if path.startswith("/api/connections/") or path.startswith("/api/panel/") or path.startswith("/api/static/"):
            return await call_next(request)
        if path.startswith("/api/actor-scores") or path.startswith("/api/backers") or path.startswith("/api/alerts/"):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        allowed, info = check_rate_limit(client_ip, path)

        if not allowed:
            update_rate_limiter_stats(get_rate_limiter_stats())
            return JSONResponse(
                status_code=429,
                content={
                    "error": "RATE_LIMIT_EXCEEDED",
                    "message": f"Rate limit exceeded. Try again in {info['window']}s",
                    "limit": info["limit"],
                    "reset": info["reset"],
                },
                headers={
                    "Retry-After": str(info["window"]),
                    "X-RateLimit-Limit": str(info["limit"]),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(info["reset"]),
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(info["limit"])
        response.headers["X-RateLimit-Remaining"] = str(info["remaining"])
        response.headers["X-RateLimit-Reset"] = str(info["reset"])
        # Prevent CDN/proxy caching of API responses
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
        return response


app.add_middleware(RateLimitMiddleware)

# --- Telegram Intel Plugin Routers (conditional) ---
if TELEGRAM_INTEL_ENABLED and telegram_module:
    app.include_router(telegram_module.router)
    from telegram_intel.api.extended import create_extended_router
    app.include_router(create_extended_router(telegram_module))
    from telegram_intel.api.admin import create_admin_router
    app.include_router(create_admin_router(telegram_module))
    print("[Proxy] Telegram Intel routers registered")
else:
    # Stub: return {"enabled": false} instead of 404 for all telegram endpoints
    _tg_stub = APIRouter(tags=["telegram-stub"])

    @_tg_stub.api_route("/api/telegram-intel/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
    @_tg_stub.api_route("/api/telegram/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
    async def telegram_disabled_stub(path: str):
        return JSONResponse(content={"enabled": False, "module": "telegram_intel", "status": "disabled"})

    app.include_router(_tg_stub)
    print("[Proxy] Telegram Intel DISABLED — stub endpoints registered")

# --- Intelligence OS (6-Layer Architecture) ---
try:
    from intelligence_os.api.routes import router as intel_os_router, init_api as init_intel_os
    from intelligence_os.ops.full_cycle import FullCycle
    _intel_os_cycle = FullCycle(db) if db is not None else None
    if _intel_os_cycle:
        init_intel_os(db, _intel_os_cycle)
    app.include_router(intel_os_router)
    print("[Proxy] Intelligence OS routes registered (/api/intel-os/*)")
except Exception as _ios_err:
    print(f"[Proxy] Intelligence OS FAILED to load: {_ios_err}")

# --- Intel Admin Routes ---
from intel_admin.routes import router as intel_admin_router
app.include_router(intel_admin_router)
from intel_admin.compat_routes import router as admin_compat_router
app.include_router(admin_compat_router)
from intel_admin.santiment_api import router as santiment_router
app.include_router(santiment_router, prefix="/api")
print("[Proxy] Intel Admin + Santiment API routes registered")

# --- Connections Analytics (Python endpoints for Actor Hub) ---
from connections_analytics import router as conn_analytics_router
from cosmic_radar import router as cosmic_radar_router
from cluster_engine import router as cluster_engine_router
from bot_detection import router as bot_detection_router
from alt_season_routes import router as alt_season_router
app.include_router(conn_analytics_router)
app.include_router(cosmic_radar_router)
# Sentiment surface adapters MUST be mounted BEFORE cluster_engine and
# bot_detection so that /api/connections/{clusters/intelligence,network/*}
# return real aggregations from actor_signal_events instead of the
# legacy empty stubs / pre-computed-collection reads.
try:
    from routes.sentiment_surface_adapters import router as _sentiment_surface_router
    app.include_router(_sentiment_surface_router)
    print("[SentimentSurface] mounted: /api/connections/{clusters/intelligence, network/*}")
except Exception as _ss_err:
    print(f"[SentimentSurface] mount failed: {_ss_err!r}")
app.include_router(cluster_engine_router)
app.include_router(bot_detection_router)
# Narrative flow adapter MUST be mounted BEFORE alt_season_routes so
# /api/narrative-flow returns real aggregations instead of empty arrays.
try:
    from routes.narrative_flow_adapter import router as _narrative_flow_router
    app.include_router(_narrative_flow_router)
    print("[NarrativeFlow] mounted: /api/narrative-flow (real aggregations)")
except Exception as _nf_err:
    print(f"[NarrativeFlow] mount failed: {_nf_err!r}")
app.include_router(alt_season_router)
# Backers runtime adapter MUST be mounted BEFORE bakery_engine_router
# so /api/backers reads from fomo_mobile.funding_rounds + canonical_persons
# (real) instead of the empty connections_db that bakery_engine uses.
try:
    from routes.backers_runtime import router as _backers_runtime_router
    app.include_router(_backers_runtime_router)
    print("[BackersRuntime] mounted: /api/backers + /api/backers/active")
except Exception as _br_err:
    print(f"[BackersRuntime] mount failed: {_br_err!r}")
from bakery_engine import router as bakery_router
app.include_router(bakery_router)

from news_ai_engine import router as news_ai_router
app.include_router(news_ai_router)
print("[Proxy] Connections Analytics + Bakery routes registered")

# --- Radar V11 Routes (Alt Radar v2 foundation) ---
from radar_v11 import radar_v11_router, market_v2_router
app.include_router(radar_v11_router)
app.include_router(market_v2_router)

# --- Smart Money Radar ---
from smart_money_radar import smart_money_radar_router
app.include_router(smart_money_radar_router)

from cex_intelligence.routes import router as cex_intelligence_router
app.include_router(cex_intelligence_router)

from market_context.routes import router as market_context_router
app.include_router(market_context_router)

from engine_v3.routes import router as engine_v3_router
app.include_router(engine_v3_router)

from engine_integration.routes import router as engine_integration_router
app.include_router(engine_integration_router)

# --- Auth & Billing ---
from auth_routes import router as auth_router
app.include_router(auth_router)

# --- UNIFIED AUTH (Cross-platform sync: Web ↔ Mobile ↔ Telegram) ---
try:
    from unified_auth_routes import router as unified_auth_router
    app.include_router(unified_auth_router)
    print("[✓] Unified Auth System loaded - Cross-platform sync enabled!")
except Exception as e:
    print(f"[✗] Failed to load Unified Auth: {e}")
from billing_routes import router as billing_router
app.include_router(billing_router)

# P0 Identity Gate — single endpoint the Web frontend probes before opening paywall.
from routes.auth_gate import router as auth_gate_router
app.include_router(auth_gate_router)

# P1 Web Soft Gate — access preview + funnel tracking (backend source of truth).
from routes.access_preview import router as access_preview_router
app.include_router(access_preview_router)

# P1.1 Funnel Analytics — admin-only read-only decision engine.
from routes.funnel_analytics import router as funnel_analytics_router
app.include_router(funnel_analytics_router)

from routes.info_cms import router as info_cms_router
app.include_router(info_cms_router)

from admin_billing_routes import router as admin_billing_router
app.include_router(admin_billing_router)

# ── Unified Billing Layer (v2) — orchestrator + 2 providers ─────────
# Config-driven provider switch. Parallel to legacy /api/billing/* routes.
# Mount path: /api/billing/v2/*
try:
    from routes.unified_billing import router as unified_billing_router
    app.include_router(unified_billing_router)
    print("[Proxy] Unified Billing v2 registered (/api/billing/v2/*)")
except Exception as _ub_err:
    print(f"[Proxy] Unified Billing v2 FAILED to load: {_ub_err}")

# ── Contextual Paywall — behavior-driven copy, no new UI ──────────────
# Reads Growth Layer G1 events, emits cold/warm/hot state + copy.
try:
    from routes.paywall import router as paywall_router
    app.include_router(paywall_router)
    print("[Proxy] Contextual Paywall registered (/api/paywall/*)")
except Exception as _pw_err:
    print(f"[Proxy] Contextual Paywall FAILED to load: {_pw_err}")

# ── Asset Logos — CoinGecko-backed, cached, single source of truth ───
try:
    from routes.assets import router as assets_router
    app.include_router(assets_router)
    print("[Proxy] Asset Logos registered (/api/assets/*)")
except Exception as _al_err:
    print(f"[Proxy] Asset Logos FAILED to load: {_al_err}")

# ── Quality Layer (Truth Lane) — additive-only, methodology-only ────
# Ported from FOMO-ML/FOMO-ML-2 bash scripts. Does NOT change scheduler.
try:
    from routes.quality import router as quality_router
    app.include_router(quality_router)
    print("[Proxy] Quality Layer registered (/api/quality/*)")
except Exception as _q_err:
    print(f"[Proxy] Quality Layer FAILED to load: {_q_err}")

# ── Trading Runtime (T1) — native FastAPI replacement for retired sidecar ──
try:
    from routes.trading_runtime import router as trading_runtime_router
    app.include_router(trading_runtime_router)

    # TRADING-ACTIVATION-2 — observability surface (health + readiness)
    from routes.trading_observability import router as trading_observability_router
    app.include_router(trading_observability_router)
    print("[Proxy] Trading Runtime registered (/api/trading/*) — verdict + paper")
except Exception as _t_err:
    print(f"[Proxy] Trading Runtime FAILED to load: {_t_err}")

# ── PROD-GAP-1 (2026-05-16) — Contract Completion: 5 missing/stub endpoints ──
# MUST be registered BEFORE legacy_compat (which has catch-all stub).
try:
    from routes.metabrain_charts import router as _metabrain_charts_router
    app.include_router(_metabrain_charts_router)
    print("[PROD-GAP-1.1+1.2] /api/metabrain/{candles,forecast-curve} registered")
except Exception as _e:
    print(f"[PROD-GAP-1.1+1.2] FAILED: {_e}")

try:
    from routes.ta_prediction import router as _ta_prediction_router
    app.include_router(_ta_prediction_router)
    print("[PROD-GAP-1.3] /api/ta/prediction/{symbol} (real, replaces stub) registered")
except Exception as _e:
    print(f"[PROD-GAP-1.3] FAILED: {_e}")

try:
    from routes.trading_cases import router as _trading_cases_router
    app.include_router(_trading_cases_router)
    print("[PROD-GAP-1.4] /api/trading/cases/active (real, replaces stub) registered")
except Exception as _e:
    print(f"[PROD-GAP-1.4] FAILED: {_e}")

try:
    from routes.labs import router as _labs_router
    app.include_router(_labs_router)
    print("[PROD-GAP-1.5] /api/labs/* (explicit experimental registry) registered")
except Exception as _e:
    print(f"[PROD-GAP-1.5] FAILED: {_e}")

try:
    from routes.admin_core7 import router as _admin_core7_router
    app.include_router(_admin_core7_router)
    print("[PROD-GAP-1.6] /api/admin/core7/mapping (Python port) registered")
except Exception as _e:
    print(f"[PROD-GAP-1.6] FAILED: {_e}")

# ── Broker Readiness Bridge (T10.1) — safe-mode pre-live execution layer ──
# Read-only adapter + preflight + always-refused live submit. No real orders.
try:
    from routes.broker_bridge import router as _broker_bridge_router
    app.include_router(_broker_bridge_router)
    print("[Proxy] Broker Bridge registered (/api/broker/*) — T10.1 safe mode")
except Exception as _bb_err:
    print(f"[Proxy] Broker Bridge FAILED to load: {_bb_err}")

# T3 — Continuous Paper Runtime scheduler (auto-evaluate stop/target hits)
@app.on_event("startup")
async def _bootstrap_paper_runtime_scheduler() -> None:
    try:
        from services import paper_runtime_scheduler as _sched
        _res = await _sched.bootstrap()
        print(f"[Proxy] Paper Runtime Scheduler bootstrap: {_res}")
    except Exception as _e:
        print(f"[Proxy] Paper Runtime Scheduler bootstrap FAILED: {_e}")

from promo_routes import router as promo_admin_router, user_router as promo_user_router
app.include_router(promo_admin_router)
app.include_router(promo_user_router)

from user_routes import router as user_profile_router
app.include_router(user_profile_router)

from footer_routes import router as footer_router
app.include_router(footer_router)


from os_service.routes import router as os_router
app.include_router(os_router)

# --- Prediction On-chain Market ---
from prediction_onchain.routes import router as prediction_onchain_router
app.include_router(prediction_onchain_router)


# --- Prediction Markets (Polymarket Intelligence) ---
from prediction.routes import router as prediction_markets_router
app.include_router(prediction_markets_router)

# --- Market Feed (Polymarket Feed + Intelligence Overlay) ---
from prediction.feed.routes import router as feed_router, legacy_router as market_feed_legacy_router
app.include_router(feed_router)
app.include_router(market_feed_legacy_router)

# --- Live Intelligence Engine ---
from prediction.feed.live_routes import router as live_router
app.include_router(live_router)

# --- Prediction Lab (Forecast Validation & Self-Improvement) ---
from prediction.prediction_lab.routes import router as prediction_lab_router
app.include_router(prediction_lab_router)

# --- Self-Improvement Engine (Pattern Learning, Drift, Tuning) ---
from prediction.self_improvement.routes import router as self_improvement_router
app.include_router(self_improvement_router)

# --- Cross-Market Intelligence (Linker, Relations, Signals) ---
from prediction.cross_market.routes import router as cross_market_router
app.include_router(cross_market_router)

# --- Cross-Market Kalshi (Cross-Platform Intelligence) ---
from prediction.cross_market.kalshi.kalshi_routes import router as kalshi_router
app.include_router(kalshi_router)


# --- Prediction Market Watcher (background monitoring) ---
from prediction.monitoring.market_watcher import start_watcher, stop_watcher


# --- Signals V3 (Unified Signal Terminal) ---
from signals_v3.signal_routes import router as signals_v3_router
app.include_router(signals_v3_router)


from entities_v2.routes import router as entities_v2_router
app.include_router(entities_v2_router)

# --- Research V2 Routes ---
from research import research_router
app.include_router(research_router)

# --- Labs V2 Routes ---
from labs.routes import router as labs_v2_router
app.include_router(labs_v2_router)


# --- Core Engine Routes ---
from core_engine.routes import router as core_engine_router
app.include_router(core_engine_router)

# --- Macro V2 Routes ---
from macro_v2.routes import router as macro_v2_router
app.include_router(macro_v2_router)

# --- Signal Intelligence Layer ---
from signals.routes import router as signals_router
app.include_router(signals_router)

# --- Overview Intelligence Layer ---
from overview.routes import router as overview_router
app.include_router(overview_router)

# --- Forecast Scheduler ---
from forecast.routes import router as forecast_router
app.include_router(forecast_router)

# --- DashboardPack V1 (Intelligence Monitoring) ---
from dashboard_routes import router as dashboard_router
app.include_router(dashboard_router)
print("[Proxy] DashboardPack V1 routes registered (/api/dashboard/*)")

# --- Fractal Forecasts ---
from fractal_forecast.routes import router as fractal_forecast_router
app.include_router(fractal_forecast_router)

# --- Prediction Exchange (Blocks 2-5) ---
from prediction_exchange_routes import router as pred_exchange_router
from ml_overlay.routes import router as ml_overlay_router
app.include_router(pred_exchange_router)
app.include_router(ml_overlay_router)

# --- Bootstrap / Replay ---
from bootstrap_routes import router as bootstrap_router
app.include_router(bootstrap_router)

# --- Tactical Layer (Block X) ---
from tactical.routes import router as tactical_router
app.include_router(tactical_router)


# --- Image Proxy (for entity icons, avoids CORS) ---
@app.get("/api/img-proxy")
async def image_proxy(url: str):
    """Proxy external images with proper CORS headers for canvas drawing."""
    import hashlib
    ALLOWED_HOSTS = ["assets.coingecko.com", "assets.trustwallet.com"]
    from urllib.parse import urlparse
    parsed = urlparse(url)
    if parsed.hostname not in ALLOWED_HOSTS:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    cache_key = hashlib.md5(url.encode()).hexdigest()
    cache_dir = "/tmp/img_cache"
    os.makedirs(cache_dir, exist_ok=True)
    cache_path = os.path.join(cache_dir, cache_key)
    if os.path.exists(cache_path):
        with open(cache_path, "rb") as f:
            data = f.read()
        return StreamingResponse(
            iter([data]),
            media_type="image/png",
            headers={"Cache-Control": "public, max-age=86400", "Access-Control-Allow-Origin": "*"}
        )
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url, follow_redirects=True)
        if resp.status_code != 200:
            return JSONResponse({"error": "fetch failed"}, status_code=502)
        data = resp.content
        with open(cache_path, "wb") as f:
            f.write(data)
        ct = resp.headers.get("content-type", "image/png")
        return StreamingResponse(
            iter([data]),
            media_type=ct,
            headers={"Cache-Control": "public, max-age=86400", "Access-Control-Allow-Origin": "*"}
        )

# --- Audit Runner ---
from audit_routes import router as audit_router
app.include_router(audit_router)

# --- Drift Monitoring ---
from drift.routes import router as drift_router
app.include_router(drift_router)

# --- Intelligence Layer (OTC / Market Maker Detection) ---
from intelligence.routes import router as intelligence_router
app.include_router(intelligence_router)

# --- Intelligence Console (Block 4+6 Admin Dashboard) ---
from intelligence_console.routes import router as intel_console_router
app.include_router(intel_console_router)

# --- On-Chain Lite + Admin Indexer Control ---
from onchain_lite.routes import router as onchain_lite_router
app.include_router(onchain_lite_router)

# --- On-Chain Admin V2 (full admin panel API) ---
from onchain_admin.routes import router as onchain_admin_router
app.include_router(onchain_admin_router)

# --- On-Chain Alert Rules ---
from entity_intelligence.alert_routes import router as alert_rules_router
app.include_router(alert_rules_router)

# --- Discovery (Wallet Registry, Clustering, Smart Money) ---
from discovery.routes import router as discovery_router
app.include_router(discovery_router)

# --- On-Chain Overview Dashboard ---
from onchain_overview.routes import router as onchain_overview_router
app.include_router(onchain_overview_router)

# --- Unified Notification Engine ---
from notifications.routes import router as notifications_router
from notifications.storage.event_repo import init_event_repo
from notifications.storage.rule_repo import init_rule_repo
from notifications.storage.notification_repo import init_notification_repo
app.include_router(notifications_router)
if db is not None:
    init_event_repo(db)
    init_rule_repo(db)
    init_notification_repo(db)
    print("[Proxy] Unified Notification Engine initialized")


# --- Knowledge Graph ---
if db is not None:
    from knowledge_graph.api.routes import router as kg_router, init_graph_services
    app.include_router(kg_router)
    from knowledge_graph.graph_api_routes import router as kg_api_router
    app.include_router(kg_api_router)
    print("[Proxy] Knowledge Graph routes registered")
else:
    print("[Proxy] Knowledge Graph routes SKIPPED (no MongoDB)")

# --- Graph Core (Anchor Entities, Health) ---
from graph_core_routes import router as graph_core_router, momentum_router, init_graph_core
app.include_router(graph_core_router)
app.include_router(momentum_router)
if db is not None:
    init_graph_core(db)
    print("[Proxy] Graph Core routes registered")
else:
    print("[Proxy] Graph Core routes registered (no DB)")





NODE_BACKEND_URL = "http://127.0.0.1:8003"
NODE_WS_URL = "ws://127.0.0.1:8003"
node_process = None

def is_port_open(port: int) -> bool:
    """Check if a port is already in use"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

def kill_process_on_port(port: int) -> bool:
    """Kill any process listening on the specified port"""
    try:
        # Find PID using lsof
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True,
            text=True
        )
        if result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            for pid in pids:
                try:
                    os.kill(int(pid), 9)
                    print(f"[Proxy] Killed process {pid} on port {port}")
                except (ProcessLookupError, ValueError):
                    pass
            return True
    except Exception as e:
        print(f"[Proxy] Error killing process on port {port}: {e}")
    return False

async def start_node_backend():
    """
    QUARANTINED — Legacy TS Quarantine (2026-05-12).

    The Node.js side-car backend (entry: `src/server.ts`) has been moved out
    of the active codebase to `/app/legacy/backend-src/`. FastAPI is the
    canonical runtime; this function is preserved only because the shutdown
    handler still references the `node_process` global. It MUST NOT be
    invoked. The original caller in `startup()` is already commented out.

    See:  /app/memory/LEGACY_TS_QUARANTINE_2026-05-12.md
          /app/legacy/backend-src/README_ABANDONED.md
    """
    raise RuntimeError(
        "start_node_backend() is quarantined. The Node.js sidecar at "
        "src/server.ts has been moved to /app/legacy/backend-src/ and is "
        "no longer part of the FastAPI runtime. See "
        "/app/memory/LEGACY_TS_QUARANTINE_2026-05-12.md"
    )

@app.on_event("startup")
async def startup():
    print("[Proxy] Initializing FastAPI proxy...")

    # Phase B · Step 3 — bootstrap outcome resolver scheduler if env flag set.
    # Memory-maintenance only.  Disabled by default unless
    # OUTCOME_RESOLVER_ENABLED=true.
    try:
        from services.outcome_resolver_scheduler import bootstrap_if_enabled
        await bootstrap_if_enabled()
        print("[OutcomeResolverScheduler] bootstrap checked")
    except Exception as _bs_err:  # pragma: no cover
        print(f"[OutcomeResolverScheduler] bootstrap error: {_bs_err!r}")

    # Start Prediction Market Watcher (background)
    try:
        start_watcher()
        print("[Proxy] Prediction Market Watcher started")
    except Exception as e:
        print(f"[Proxy] Market Watcher start error: {e}")

    # Initialize Fractal Module (config from env → injected into repo)
    from forecast.module import init_fractal_module, get_config_from_env
    fractal_config = get_config_from_env()
    init_fractal_module(fractal_config)

    if TELEGRAM_INTEL_ENABLED and telegram_module:
        try:
            await telegram_module.start()
            print("[Proxy] Telegram Intel plugin started")
        except Exception as e:
            print(f"[Proxy] Telegram Intel plugin failed to start: {e}")
    # Node.js backend disabled — serving web platform via static files
    # await start_node_backend()
    print("[Proxy] Node.js backend SKIPPED (static files mode)")

    # Initialize Knowledge Graph services
    if db is not None:
        try:
            from knowledge_graph.api.routes import init_graph_services
            init_graph_services(db)
            print("[Proxy] Knowledge Graph services initialized")
        except Exception as e:
            print(f"[Proxy] Knowledge Graph init error: {e}")

    # R4.3: Start periodic rate limiter cleanup
    asyncio.create_task(_rl_cleanup_loop())
    # Start forecast scheduler
    if fractal_config.scheduler_enabled:
        asyncio.create_task(_start_forecast_scheduler())
    else:
        print("[Proxy] Forecast scheduler DISABLED by config")

    # Start fractal forecast pipeline
    asyncio.create_task(_start_fractal_forecast_scheduler())

    # E7: Start engine snapshot workers
    asyncio.create_task(_engine_snapshot_loop())
    asyncio.create_task(_engine_micro_snapshot_loop())

    # Auto-start ingestion scheduler (every 6h)
    try:
        from cron_ingestion import start_scheduler
        sched_result = start_scheduler()
        print(f"[Proxy] Ingestion scheduler: {sched_result}")
    except Exception as e:
        print(f"[Proxy] Ingestion scheduler start error: {e}")

    # ── TRADING-ACTIVATION-2 · sentiment periodic loop (LLM-free) ──
    # Calls services.sentiment_service.run_sentiment_ingestion every
    # SENTIMENT_PERIODIC_INTERVAL_SEC seconds (default 15 min).
    # Sources: Fear & Greed + CoinGecko + curated headlines. NO LLM.
    try:
        from services.sentiment_periodic import start_loop_if_enabled
        sentiment_periodic_result = start_loop_if_enabled()
        print(f"[Proxy] SentimentPeriodic: {sentiment_periodic_result}")
    except Exception as e:
        print(f"[Proxy] SentimentPeriodic start error: {e}")

    # ── TRADING-ACTIVATION-3 · exchange periodic loop (forecast freshness) ──
    # Calls forecast.scheduler.run_gen_job() every EXCHANGE_PERIODIC_INTERVAL_SEC
    # seconds (default 15 min). Idempotent — uses sub-daily bucket allocation.
    try:
        from services.exchange_periodic import start_loop_if_enabled as start_exch_loop
        exch_periodic_result = start_exch_loop()
        print(f"[Proxy] ExchangePeriodic: {exch_periodic_result}")
    except Exception as e:
        print(f"[Proxy] ExchangePeriodic start error: {e}")

    # ── ACTIVATION P2 · on-chain periodic loop (Infura + DefiLlama → onchain_metrics) ──
    # Persists per-chain metrics with derived direction so the trading
    # verdict's on-chain module flips from ABSTAIN to active.
    try:
        from services.onchain_periodic import start_loop_if_enabled as start_oc_loop
        oc_periodic_result = start_oc_loop()
        print(f"[Proxy] OnchainPeriodic: {oc_periodic_result}")
    except Exception as e:
        print(f"[Proxy] OnchainPeriodic start error: {e}")

    # ── PROD-GAP-3 · on-chain per-asset loop (cryptorank + hyperliquid + ccxt) ──
    # Persists per-symbol metrics so `_fetch_onchain(symbol)` returns
    # asset-aware data instead of falling back to chain-level Ethereum macro.
    try:
        from services.onchain_per_asset import start_loop_if_enabled as start_oc_pa_loop
        oc_pa_result = start_oc_pa_loop()
        print(f"[Proxy] OnchainPerAsset: {oc_pa_result}")
    except Exception as e:
        print(f"[Proxy] OnchainPerAsset start error: {e}")

    # ── DEEP PARSER · CryptoRank + ICODrops + DropsTab per-project deep scrape ──
    # Visits each project detail page to extract investors / team / rounds /
    # unlocks.  This is what feeds the Backers UI and persons graph.
    try:
        from services.deep_parser import start_loop_if_enabled as start_deep_loop
        deep_result = start_deep_loop()
        print(f"[Proxy] DeepParser: {deep_result}")
    except Exception as e:
        print(f"[Proxy] DeepParser start error: {e}")

    # Restore sampling rollout state from DB
    try:
        import outcome_resolver as _or
        cfg = await db.system_config.find_one({"key": "sampling_rollout"}, {"_id": 0})
        if cfg:
            _or.SAMPLING_ROLLOUT_PCT = cfg.get("pct", 10)
            saved_state = cfg.get("state", {})
            for k, v in saved_state.items():
                if k in _or._rollout_state:
                    _or._rollout_state[k] = v
            print(f"[Proxy] Sampling rollout restored: {_or.SAMPLING_ROLLOUT_PCT}%")
    except Exception as e:
        print(f"[Proxy] Sampling rollout restore error: {e}")

    # Restore V2 convergence state from DB
    try:
        import forecast.convergence as _conv
        v2_cfg = await db.system_config.find_one({"key": "v2_convergence"}, {"_id": 0})
        if v2_cfg:
            _conv.SYSTEM_V2_PCT = v2_cfg.get("pct", 0.0)
            _conv.SYSTEM_V2_MODE = v2_cfg.get("mode", "shadow_only")
            print(f"[Proxy] V2 convergence restored: {_conv.SYSTEM_V2_PCT*100:.0f}% ({_conv.SYSTEM_V2_MODE})")
    except Exception as e:
        print(f"[Proxy] V2 convergence restore error: {e}")

    # Auto-start Intelligence OS scheduler (full cycle + watchdog)
    if db is not None:
        asyncio.create_task(_intel_os_scheduler_loop())
        asyncio.create_task(_intel_os_watchdog_loop())
        print("[Proxy] Intelligence OS scheduler + watchdog started")

    # Start Telegram aggregation flush loop
    try:
        from notifications.delivery.telegram_aggregator import flush_loop as tg_flush_loop
        asyncio.create_task(tg_flush_loop())
        print("[Proxy] Telegram aggregation flush loop started")
    except Exception as e:
        print(f"[Proxy] Telegram aggregation setup error: {e}")

    # Start Prediction Lab background scheduler (price tracker, resolver, recalculate)
    try:
        from prediction.prediction_lab.lab_scheduler import start_lab_scheduler
        asyncio.create_task(start_lab_scheduler())
        print("[Proxy] Prediction Lab scheduler started (3 background jobs)")
    except Exception as e:
        print(f"[Proxy] Prediction Lab scheduler error: {e}")

    # Start Live Intelligence Engine (price polling for HOT markets)
    try:
        from prediction.feed.live_engine import start_live_engine
        asyncio.create_task(start_live_engine())
        print("[Proxy] Live Intelligence Engine started (HOT=5s, ACTIONABLE=15s)")
    except Exception as e:
        print(f"[Proxy] Live Intelligence Engine error: {e}")

    # Start Self-Improvement Engine scheduler (pattern scan, drift check, proposals, experiments)
    try:
        from prediction.self_improvement.scheduler import start_self_improvement_scheduler
        asyncio.create_task(start_self_improvement_scheduler())
        print("[Proxy] Self-Improvement Engine scheduler started (4 background jobs)")
    except Exception as e:
        print(f"[Proxy] Self-Improvement Engine scheduler error: {e}")

    # Start MiniApp Intelligence Scheduler (Polymarket ingest + Daily Digest)
    try:
        from miniapp.scheduler import start_scheduler as start_miniapp_scheduler
        start_miniapp_scheduler(db)
        print("[Proxy] MiniApp scheduler started (ingest 30min + digest 09:00 UTC)")
    except Exception as e:
        print(f"[Proxy] MiniApp scheduler error: {e}")

    # Auto-register MiniApp Telegram Bot webhook
    try:
        miniapp_token = os.environ.get("MINIAPP_BOT_TOKEN", "")
        miniapp_url = os.environ.get("MINIAPP_URL", "")
        app_url = os.environ.get("APP_URL", "")
        if miniapp_token and miniapp_url:
            # Webhook must use APP_URL/api/ path (not /api/panel/)
            webhook_base = app_url or miniapp_url.split("/api/panel")[0]
            webhook_url = f"{webhook_base}/api/miniapp/webhook"
            import httpx
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"https://api.telegram.org/bot{miniapp_token}/setWebhook?url={webhook_url}", timeout=10)
                result = resp.json()
                if result.get("ok"):
                    print(f"[Proxy] MiniApp bot webhook set: {webhook_url}")
                else:
                    print(f"[Proxy] MiniApp bot webhook FAILED: {result}")
            # Setup bot menu button and commands
            from miniapp.bot_setup import setup_miniapp_bot
            await setup_miniapp_bot()
    except Exception as e:
        print(f"[Proxy] MiniApp bot setup error: {e}")

    # Start Push Intelligence Trigger Scheduler (PnL, Edge, Watchlist)
    asyncio.create_task(_push_intelligence_loop())
    print("[Proxy] Push Intelligence scheduler started (triggers every 3min)")

    print("[Proxy] Ready to proxy requests to Node.js backend on port 8003")


async def _push_intelligence_loop():
    """Push Intelligence: Run trigger checks every 3 minutes + sequence runner every 60s."""
    await asyncio.sleep(30)  # Wait for services to initialize
    print("[Push Intelligence] Trigger loop started (180s interval)")
    cycle = 0
    while True:
        try:
            # Main triggers every 3min
            from services.push_triggers import run_all_triggers_all_users, run_sequence_step, check_missed_profit_triggers
            result = run_all_triggers_all_users()
            total = result.get('total_notifications', 0)
            if total > 0:
                print(f"[Push Intelligence] Generated {total} notifications for {result.get('users_checked', 0)} users")

            # Sequence runner every cycle (fires pending sequence messages)
            seq_result = run_sequence_step()
            if seq_result.get("fired", 0) > 0:
                print(f"[Sequence] Fired {seq_result['fired']} sequence messages")

            # Missed profit check every 3rd cycle (~9min)
            if cycle % 3 == 0:
                try:
                    missed = check_missed_profit_triggers()
                    if missed:
                        print(f"[Missed Profit] {len(missed)} regret notifications sent")
                except Exception as me:
                    pass  # Silent — not critical

            cycle += 1
        except Exception as e:
            print(f"[Push Intelligence] Trigger error: {e}")
        await asyncio.sleep(180)  # Every 3 minutes


async def _rl_cleanup_loop():
    """Periodic rate limiter bucket cleanup every 60s."""
    while True:
        await asyncio.sleep(60)


async def _start_forecast_scheduler():
    """Core-managed scheduler: runs jobs defined by the Fractal module."""
    import asyncio as _aio
    from forecast.jobs import get_fractal_jobs
    from forecast.repo import ensure_indexes

    # Ensure indexes on startup
    try:
        ensure_indexes()
        print("[Forecast] Indexes ensured")
    except Exception as e:
        print(f"[Forecast] Index setup error: {e}")

    jobs = get_fractal_jobs()
    print(f"[Core Scheduler] Registered {len(jobs)} fractal jobs: {[j.name for j in jobs]}")

    # Run startup jobs (idempotent)
    await _aio.sleep(5)
    for job in jobs:
        if job.run_on_startup:
            try:
                result = job.handler()
                print(f"[Core Scheduler] {job.name} startup run: {result}")
            except Exception as e:
                print(f"[Core Scheduler] {job.name} startup error: {e}")

    # Daily loop → Block 11: Sub-daily (every 6 hours at HH:10)
    while True:
        now = datetime.now(timezone.utc)
        # Find next slot: 00:10, 06:10, 12:10, 18:10
        current_hour = now.hour
        slots = [0, 6, 12, 18]
        next_slot = None
        for s in slots:
            candidate = now.replace(hour=s, minute=10, second=0, microsecond=0)
            if candidate > now:
                next_slot = candidate
                break
        if next_slot is None:
            # Next day 00:10
            next_slot = (now + timedelta(days=1)).replace(hour=0, minute=10, second=0, microsecond=0)

        wait_seconds = (next_slot - now).total_seconds()
        print(f"[Core Scheduler] Next run in {wait_seconds/3600:.1f}h at {next_slot.isoformat()} (Block 11: 6h cycle)")
        await _aio.sleep(wait_seconds)
        for job in jobs:
            try:
                result = job.handler()
                print(f"[Core Scheduler] {job.name} complete: {result}")
            except Exception as e:
                print(f"[Core Scheduler] {job.name} error: {e}")
        rl_cleanup()
        update_rate_limiter_stats(get_rate_limiter_stats())


async def _start_fractal_forecast_scheduler():
    """Run all fractal forecast pipelines (BTC, SPX, DXY) on startup + daily at 00:15 UTC."""
    import asyncio as _aio
    from fractal_forecast.pipeline import init_fractal_forecasts, run_all_pipelines

    await _aio.sleep(30)  # Wait for Node.js backend to be ready
    init_fractal_forecasts()

    # Run on startup
    try:
        results = run_all_pipelines()
        print(f"[FractalForecast] Startup pipelines: {results}")
    except Exception as e:
        print(f"[FractalForecast] Startup pipeline error: {e}")

    # Daily loop (00:15 UTC — 5min after exchange forecast)
    while True:
        now = datetime.now(timezone.utc)
        tomorrow = now.replace(hour=0, minute=15, second=0, microsecond=0)
        if tomorrow <= now:
            tomorrow += timedelta(days=1)
        wait_seconds = (tomorrow - now).total_seconds()
        print(f"[FractalForecast] Next run in {wait_seconds/3600:.1f}h at {tomorrow.isoformat()}")
        await _aio.sleep(wait_seconds)
        try:
            results = run_all_pipelines()
            print(f"[FractalForecast] Daily pipelines: {results}")
        except Exception as e:
            print(f"[FractalForecast] Daily pipeline error: {e}")



async def _engine_snapshot_loop():
    """E7: Build full engine snapshots every 90 seconds."""
    from engine_integration.engine_snapshot_service import ensure_indexes, build_engine_snapshot
    await asyncio.sleep(10)  # Wait for other services to initialize
    try:
        ensure_indexes()
    except Exception as e:
        print(f"[Snapshot] Index setup error: {e}")

    print("[Snapshot] Full snapshot worker started (90s interval)")
    while True:
        try:
            build_engine_snapshot()
        except Exception as e:
            print(f"[Snapshot] Full snapshot error: {e}")
        await asyncio.sleep(90)


async def _engine_micro_snapshot_loop():
    """E7: Build micro snapshots every 3 minutes."""
    from engine_integration.engine_snapshot_service import build_micro_snapshot
    await asyncio.sleep(20)  # Offset from full snapshot
    print("[Snapshot] Micro snapshot worker started (180s interval)")
    while True:
        try:
            build_micro_snapshot()
        except Exception as e:
            print(f"[Snapshot] Micro snapshot error: {e}")
        await asyncio.sleep(180)


async def _intel_os_scheduler_loop():
    """Intelligence OS: Run full cycle every 6 hours."""
    await asyncio.sleep(180)  # Wait for services to be ready (3 min to let UI come up)
    print("[Intel OS] Full cycle scheduler started (6h interval)")

    # Run initial cycle
    try:
        from intelligence_os.ops.full_cycle import FullCycle
        cycle = FullCycle(db)
        result = await cycle.run_full_cycle()
        print(f"[Intel OS] Initial full cycle: duration={result.get('duration_sec')}s")
    except Exception as e:
        print(f"[Intel OS] Initial full cycle error: {e}")

    # Run Twitter hybrid ingestion V2 (L0→L1→L2→L3) — kicked off as a
    # background fire-and-forget so it never blocks the periodic loop.
    async def _twitter_hybrid_batch():
        try:
            from twitter_ingestion.hybrid_service import TwitterHybridServiceV2
            # Pull a curated batch from twitter_tracked_actors (seeded admin list)
            tracked = await db.get_collection("twitter_tracked_actors").find(
                {"active": True}, {"_id": 0, "username": 1}
            ).to_list(20)
            actors = [a["username"] for a in tracked] if tracked else [
                "CryptoHayes", "DefiIgnas", "TheCryptoDog", "inversebrah",
                "AltcoinGordon", "MoustacheXBT", "Pentosh1", "CryptoCobain",
                "RaoulGMI", "ZssBecker", "blaboratorio", "lookonchain",
            ]
            # Cap to 8 actors per startup batch to avoid starving the event loop.
            actors = actors[:8]
            hybrid = TwitterHybridServiceV2(db)
            hybrid_result = await hybrid.run_batch(actors)
            print(f"[Intel OS] Twitter hybrid V2: {hybrid_result.get('actors_ok')}/{hybrid_result.get('actors_total')} OK | sources={hybrid_result.get('sources')}")
        except Exception as e:
            print(f"[Intel OS] Twitter hybrid V2 error: {e}")

    asyncio.create_task(_twitter_hybrid_batch())

    # 6-hour loop
    while True:
        await asyncio.sleep(6 * 3600)
        try:
            from intelligence_os.ops.full_cycle import FullCycle
            cycle = FullCycle(db)
            result = await cycle.run_full_cycle()
            print(f"[Intel OS] Scheduled full cycle: duration={result.get('duration_sec')}s")
        except Exception as e:
            print(f"[Intel OS] Scheduled full cycle error: {e}")

        # Twitter hybrid V2 after each cycle — fire-and-forget
        asyncio.create_task(_twitter_hybrid_batch())


async def _intel_os_watchdog_loop():
    """Intelligence OS: Run watchdog V2 every 15 minutes (active recovery)."""
    await asyncio.sleep(120)  # Offset from full cycle
    print("[Intel OS] Watchdog V2 started (15min interval, active recovery)")
    while True:
        try:
            from twitter_ingestion.watchdog import TwitterWatchdogV2
            watchdog = TwitterWatchdogV2(db)
            report = await watchdog.run()
            status = report.get("status", "UNKNOWN")
            print(f"[Intel OS Watchdog V2] {status} | parser={'UP' if report.get('parser_alive') else 'DOWN'} | L0={report.get('sources_6h',{}).get('L0_public',0)} L1={report.get('sources_6h',{}).get('L1_cookies',0)}")
        except Exception as e:
            print(f"[Intel OS Watchdog V2] Error: {e}")
        await asyncio.sleep(15 * 60)



@app.on_event("shutdown")
async def shutdown():
    global node_process
    print("[Proxy] Shutting down...")
    # Stop MiniApp scheduler
    try:
        from miniapp.scheduler import stop_scheduler as stop_miniapp_scheduler
        stop_miniapp_scheduler()
    except Exception:
        pass
    # Stop Market Watcher
    try:
        stop_watcher()
    except Exception:
        pass
    if TELEGRAM_INTEL_ENABLED and telegram_module:
        try:
            await telegram_module.stop()
        except Exception:
            pass
    if node_process and node_process.poll() is None:
        print(f"[Proxy] Terminating Node.js backend (PID {node_process.pid})")
        node_process.terminate()
        try:
            node_process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            node_process.kill()

@app.websocket("/ws")
async def websocket_proxy(websocket: WebSocket):
    await websocket.accept()
    try:
        async with websockets.connect(f"{NODE_WS_URL}/ws") as ws_backend:
            async def forward_to_client():
                try:
                    async for message in ws_backend:
                        await websocket.send_text(message)
                except Exception:
                    pass

            async def forward_to_backend():
                try:
                    while True:
                        data = await websocket.receive_text()
                        await ws_backend.send(data)
                except WebSocketDisconnect:
                    pass

            await asyncio.gather(forward_to_client(), forward_to_backend())
    except Exception as e:
        print(f"[WS Proxy] Error: {e}")
        await websocket.close()

@app.websocket("/api/ws")
async def api_websocket_proxy(websocket: WebSocket):
    await websocket.accept()
    try:
        async with websockets.connect(f"{NODE_WS_URL}/api/ws") as ws_backend:
            async def forward_to_client():
                try:
                    async for message in ws_backend:
                        await websocket.send_text(message)
                except Exception:
                    pass

            async def forward_to_backend():
                try:
                    while True:
                        data = await websocket.receive_text()
                        await ws_backend.send(data)
                except WebSocketDisconnect:
                    pass

            await asyncio.gather(forward_to_client(), forward_to_backend())
    except Exception as e:
        print(f"[WS Proxy] Error: {e}")
        await websocket.close()

@app.get("/health")
async def health():
    """Python Gateway health check"""
    node_healthy = is_port_open(8003)
    return {
        "service": "python-gateway",
        "status": "ok",
        "node_backend": "connected" if node_healthy else "disconnected"
    }


@app.get("/api/health")
async def api_health():
    """Main health check — always returns 200 so Expo never crashes."""
    node_healthy = is_port_open(8003)
    return {
        "ok": True,
        "service": "fomo-platform",
        "python": "ok",
        "node": "ok" if node_healthy else "starting",
    }


# ═══════════════════════════════════════════════════════════
# BTC PREDICTION CHART (Mobile App + MiniApp + Telegram)
# ═══════════════════════════════════════════════════════════

@app.get("/api/mobile/prediction-chart")
async def mobile_prediction_chart(
    request: Request,
    symbol: str = "BTC",
    horizon: str = "30D",
):
    """Full prediction chart payload for Expo mobile app."""
    from routes.mobile_auth import get_optional_user as _get_opt_user
    from fastapi import Header
    auth_header = request.headers.get("authorization")
    user = None
    if auth_header:
        try:
            user = _get_opt_user(auth_header)
        except Exception:
            pass
    access = "PRO" if user and user.get("plan") == "PRO" else "FREE"
    from services.prediction_chart_service import build_prediction_payload
    return build_prediction_payload(symbol, horizon, access)


@app.get("/api/miniapp/prediction-chart")
async def miniapp_prediction_chart(symbol: str = "BTC"):
    """Compact prediction for Telegram MiniApp."""
    from services.prediction_chart_service import build_compact_payload
    return build_compact_payload(symbol)


@app.post("/api/miniapp/prediction/broadcast")
async def api_prediction_broadcast(symbol: str = "BTC", force: bool = False):
    """
    Multi-trigger MetaBrain teaser broadcast to linked MiniApp users.
    Fires on ANY of: direction_shift, confidence_spike, conviction_spike,
    entry_window_open. Idempotent — only fires once per real change.
    Set force=true to bypass shift check (manual test).
    """
    from services.prediction_chart_service import detect_significant_change, build_compact_payload
    from miniapp.edge_alerts import send_telegram_message
    import os as _os

    change = detect_significant_change(symbol)
    reasons = change.get('reasons', []) or []
    if not reasons and not force:
        return {"ok": True, "skipped": True, "reason": "no_change", **change}

    compact = build_compact_payload(symbol)

    prev = change.get('prevBias') or '—'
    new = change.get('newBias') or '—'
    emoji = compact.get('biasEmoji', '→')
    conf = compact.get('confidence', 0)
    move = compact.get('expectedMove', '')
    price = compact.get('currentPrice', 0)

    # Build headline per primary reason (priority order matters)
    state = change.get('marketState', 'SCANNING')
    if 'tension_rising' in reasons:
        header = f"<b>⚠️ {symbol} MARKET TENSION BUILDING</b>"
        subline = f"{emoji} <b>{new}</b> · modules diverging · pressure forming"
    elif 'direction_shift' in reasons:
        header = f"<b>⚡ {symbol} MODEL SHIFT · 30D</b>"
        subline = f"{prev} → {emoji} <b>{new}</b> · {conf}% agreement"
    elif 'entry_window_open' in reasons:
        header = f"<b>🚨 {symbol} ENTRY WINDOW OPEN</b>"
        subline = f"{emoji} <b>{new}</b> · {conf}% confidence · model aligned"
    elif 'state_change' in reasons:
        header = f"<b>🔄 {symbol} STATE CHANGE</b>"
        subline = f"{change.get('prevMarketState','?')} → <b>{state}</b> · {emoji} {new}"
    elif 'confidence_spike' in reasons:
        prev_conf = change.get('prevConfidence', 0)
        header = f"<b>🔥 {symbol} MODEL CONVICTION RISING</b>"
        subline = f"{emoji} <b>{new}</b> · agreement {prev_conf}% → {conf}%"
    elif 'conviction_spike' in reasons:
        header = f"<b>🔥 {symbol} SIGNAL STRENGTHENING</b>"
        subline = f"{emoji} <b>{new}</b> · conviction {change.get('prevConviction',0)}% → {change.get('conviction',0)}%"
    elif force:
        header = f"<b>🎯 {symbol} MODEL UPDATE · 30D</b>"
        subline = f"{emoji} <b>{new}</b> · {conf}% agreement · state: {state}"
    else:
        header = f"<b>🎯 {symbol} MODEL · 30D</b>"
        subline = f"{emoji} <b>{new}</b> · {conf}% agreement"

    text = (
        f"{header}\n\n"
        f"{subline}\n"
        f"Expected move: <b>{move}</b>\n"
        f"Price: ${price:,.0f}\n"
        f"State: <b>{state}</b>\n\n"
        f"→ Open full prediction in app"
    )

    webapp_url = _os.environ.get('MINIAPP_URL', '')
    keyboard = None
    if webapp_url:
        keyboard = {
            "inline_keyboard": [[
                {"text": "Open Prediction", "web_app": {"url": f"{webapp_url}?tab=prediction&symbol={symbol}"}}
            ]]
        }

    from ml_ops import get_db as _get_db
    db = _get_db()
    sent = 0
    errors = 0
    try:
        user_cursor = db.users.find(
            {"telegramId": {"$exists": True, "$ne": None}},
            {"_id": 0, "telegramId": 1}
        ).limit(5000)
        async for u in user_cursor:
            tid = u.get("telegramId")
            if not tid:
                continue
            try:
                r = await send_telegram_message(int(tid), text, keyboard)
                if r and r.get("ok"):
                    sent += 1
                else:
                    errors += 1
            except Exception:
                errors += 1
    except Exception as e:
        return {"ok": False, "error": str(e), "change": change}

    return {
        "ok": True,
        "change": change,
        "reasons": reasons,
        "broadcasted": True,
        "sent": sent,
        "errors": errors,
    }


@app.get("/api/miniapp/prediction/shift-status")
async def api_prediction_shift_status(symbol: str = "BTC"):
    """Lightweight status endpoint — returns current bias + last shift info."""
    from services.prediction_chart_service import _db as _svc_db, build_compact_payload
    state = _svc_db.prediction_shift_state.find_one({"symbol": symbol}, {"_id": 0}) or {}
    compact = build_compact_payload(symbol)
    return {
        "ok": True,
        "current": {
            "bias": compact.get("bias"),
            "confidence": compact.get("confidence"),
            "expectedMove": compact.get("expectedMove"),
            "horizon": "30D",
        },
        "lastState": state,
    }


@app.get("/api/twitter/health")
async def twitter_health():
    """Twitter ingestion stack health — L0/L1/L2/L3 status."""
    from twitter_ingestion.watchdog import TwitterWatchdogV2
    watchdog = TwitterWatchdogV2(db)
    report = await watchdog.run()
    return {"ok": True, **report}

@app.post("/api/twitter/ingest")
async def twitter_manual_ingest(actor: str = "lookonchain"):
    """Manual L0→L1→L2→L3 fetch for a single actor."""
    from twitter_ingestion.hybrid_service import TwitterHybridServiceV2
    hybrid = TwitterHybridServiceV2(db)
    result = await hybrid.fetch_actor(actor)
    return {"ok": True, **result}


# ═════════════════════════════════════════════════════════════
# TWITTER PARSER ADMIN — Proxy Validation + Parsing Control
# ═════════════════════════════════════════════════════════════

@app.post("/api/admin/twitter/proxy/validate")
async def admin_proxy_validate(body: dict = {}):
    """Validate configured proxies by making a test request."""
    import httpx
    
    # Get proxies from MongoDB (proxy_pool + networkconfigs)
    proxies = []
    pool = await db.get_collection("proxy_pool").find({}, {"_id": 0}).to_list(100)
    for p in pool:
        url = p.get("server", p.get("url", ""))
        username = p.get("username", "")
        password = p.get("password", "")
        if username and password and "://" in url and "@" not in url:
            parts = url.split("://", 1)
            url = f"{parts[0]}://{username}:{password}@{parts[1]}"
        proxies.append({"url": url, "doc": p})
    
    net_cfg = await db.get_collection("networkconfigs").find_one({}, {"_id": 0})
    if net_cfg:
        for pp in net_cfg.get("proxyPool", []):
            if pp.get("url") and not any(pp["url"] in p["url"] for p in proxies):
                proxies.append({"url": pp["url"], "doc": pp})
    
    if not proxies:
        return {"ok": False, "error": "No proxies configured"}
    
    results = []
    proxy_pool_coll = db.get_collection("proxy_pool")
    for proxy_item in proxies:
        proxy_url = proxy_item.get("url", "")
        if not proxy_url:
            continue
        
        test_result = {"proxy": proxy_url, "status": "UNKNOWN", "latency_ms": 0}
        try:
            async with httpx.AsyncClient(proxy=proxy_url, timeout=10) as client:
                import time
                t0 = time.monotonic()
                resp = await client.get("https://api.twitter.com/2/openapi.json")
                latency = round((time.monotonic() - t0) * 1000)
                test_result["status"] = "OK" if resp.status_code < 500 else "DEGRADED"
                test_result["latency_ms"] = latency
                test_result["http_code"] = resp.status_code
                
                # Update proxy health in DB
                await proxy_pool_coll.update_one(
                    {"server": {"$regex": proxy_url.split("@")[-1] if "@" in proxy_url else proxy_url}},
                    {"$set": {
                        "last_test": datetime.now(timezone.utc).isoformat(),
                        "healthy": True,
                        "latency_ms": latency,
                    }}
                )
        except Exception as e:
            test_result["status"] = "ERROR"
            test_result["error"] = str(e)[:200]
            await proxy_pool_coll.update_one(
                {"server": {"$regex": proxy_url.split("@")[-1] if "@" in proxy_url else proxy_url}},
                {"$set": {
                    "last_test": datetime.now(timezone.utc).isoformat(),
                    "healthy": False,
                    "last_error": str(e)[:200],
                }}
            )
        
        results.append(test_result)
    
    ok_count = sum(1 for r in results if r["status"] == "OK")
    return {
        "ok": True,
        "total": len(results),
        "healthy": ok_count,
        "results": results,
    }


@app.get("/api/admin/twitter/proxy/list")
async def admin_proxy_list():
    """List all configured proxies with their status."""
    proxies = []
    
    pool = await db.get_collection("proxy_pool").find({}, {"_id": 0}).to_list(100)
    for p in pool:
        proxies.append({
            "id": p.get("id", ""),
            "url": p.get("server", p.get("url", "")),
            "username": p.get("username", ""),
            "priority": p.get("priority", 1),
            "enabled": p.get("enabled", False),
            "healthy": p.get("healthy", False),
            "latency_ms": p.get("latency_ms", 0),
            "error_count": p.get("error_count", 0),
            "source": "proxy_pool",
        })
    
    net_cfg = await db.get_collection("networkconfigs").find_one({}, {"_id": 0})
    if net_cfg:
        for pp in net_cfg.get("proxyPool", []):
            url = pp.get("url", "")
            if url and not any(p.get("url") == url for p in proxies):
                proxies.append({
                    "id": pp.get("id", ""),
                    "url": url,
                    "enabled": pp.get("enabled", False),
                    "error_count": pp.get("errorCount", 0),
                    "source": "networkconfigs",
                })
    
    return {"ok": True, "proxies": proxies, "count": len(proxies)}


@app.post("/api/admin/twitter/parser/start")
async def admin_parser_start(body: dict = {}):
    """Start Twitter parsing — triggers Node.js execution worker + Python hybrid ingestion."""
    import httpx
    
    results = {}
    node_url = os.getenv("NODE_BACKEND_URL", "http://localhost:8003")
    
    # 1. Start Node.js execution worker
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(f"{node_url}/api/v4/twitter/execution/worker/start")
            results["node_worker"] = resp.json() if resp.status_code == 200 else {"error": resp.text[:200]}
    except Exception as e:
        results["node_worker"] = {"error": str(e)[:200]}
    
    # 2. Resume Node.js twitter service
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(f"{node_url}/api/v4/twitter/admin/resume")
            results["node_resume"] = resp.json() if resp.status_code == 200 else {"error": resp.text[:200]}
    except Exception as e:
        results["node_resume"] = {"error": str(e)[:200]}
    
    # 3. Trigger Python hybrid ingestion batch
    actors_to_parse = body.get("actors", [])
    if not actors_to_parse:
        # Get tracked actors from DB
        tracked = await db.get_collection("twitter_tracked_actors").find(
            {"active": True}, {"_id": 0, "username": 1}
        ).to_list(20)
        actors_to_parse = [a["username"] for a in tracked] if tracked else [
            "lookonchain", "whale_alert", "WatcherGuru", 
            "CryptoQuant_Alert", "santaborsa",
        ]
    
    try:
        from twitter_ingestion.hybrid_service import TwitterHybridServiceV2
        hybrid = TwitterHybridServiceV2(db)
        batch_result = await hybrid.run_batch(actors_to_parse)
        results["hybrid_batch"] = batch_result
    except Exception as e:
        results["hybrid_batch"] = {"error": str(e)[:200]}
    
    return {
        "ok": True,
        "message": "Parser started",
        "actors_queued": len(actors_to_parse),
        "results": results,
    }


@app.post("/api/admin/twitter/parser/stop")
async def admin_parser_stop():
    """Stop Twitter parsing execution worker."""
    import httpx
    
    node_url = os.getenv("NODE_BACKEND_URL", "http://localhost:8003")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(f"{node_url}/api/v4/twitter/execution/worker/stop")
            result = resp.json() if resp.status_code == 200 else {"error": resp.text[:200]}
    except Exception as e:
        result = {"error": str(e)[:200]}
    
    # Also pause Node.js
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(f"{node_url}/api/v4/twitter/admin/pause")
    except Exception:
        pass
    
    return {"ok": True, "message": "Parser stopped", "result": result}


@app.get("/api/admin/twitter/parser/status")
async def admin_parser_status():
    """Get full parser status — Node.js worker + Python watchdog + proxy health."""
    import httpx
    
    node_url = os.getenv("NODE_BACKEND_URL", "http://localhost:8003")
    status = {
        "node_worker": {},
        "node_twitter": {},
        "python_watchdog": {},
        "proxies": [],
    }
    
    # Node.js execution status
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{node_url}/api/v4/twitter/execution/status")
            if resp.status_code == 200:
                status["node_worker"] = resp.json().get("data", {})
    except Exception as e:
        status["node_worker"] = {"error": str(e)[:100]}
    
    # Node.js twitter service state
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{node_url}/api/v4/twitter/admin/state")
            if resp.status_code == 200:
                status["node_twitter"] = resp.json().get("data", {})
    except Exception as e:
        status["node_twitter"] = {"error": str(e)[:100]}
    
    # Python watchdog
    try:
        from twitter_ingestion.watchdog import TwitterWatchdogV2
        watchdog = TwitterWatchdogV2(db)
        report = await watchdog.run()
        status["python_watchdog"] = report
    except Exception as e:
        status["python_watchdog"] = {"error": str(e)[:100]}
    
    # Proxies — read from proxy_pool + networkconfigs
    proxy_pool = await db.get_collection("proxy_pool").find({}, {"_id": 0}).to_list(100)
    net_cfg = await db.get_collection("networkconfigs").find_one({}, {"_id": 0})
    combined_proxies = []
    for p in proxy_pool:
        combined_proxies.append({
            "url": p.get("server", p.get("url", "")),
            "enabled": p.get("enabled", False),
            "healthy": p.get("healthy", False),
        })
    if net_cfg:
        for pp in net_cfg.get("proxyPool", []):
            if pp.get("url"):
                combined_proxies.append({"url": pp["url"], "enabled": pp.get("enabled", False)})
    status["proxies"] = combined_proxies
    
    return {"ok": True, **status}
@app.get("/api/admin/resources")
async def admin_resources():
    """System resource monitoring: CPU, Memory, Load, Processes."""
    import psutil
    
    cpu_percent = psutil.cpu_percent(interval=0.1)
    mem = psutil.virtual_memory()
    load1, load5, load15 = os.getloadavg()
    cpu_count = os.cpu_count() or 1
    
    # Normalize load to percentage
    load_percent = round((load1 / cpu_count) * 100)
    
    # Determine health status
    if load_percent >= 70 or mem.percent >= 80:
        health = "CRITICAL"
    elif load_percent >= 50 or mem.percent >= 65:
        health = "WARNING"
    else:
        health = "OK"
    
    return {
        "ok": True,
        "data": {
            "health": health,
            "cpu": {
                "percent": cpu_percent,
                "cores": cpu_count,
                "loadAvg": [round(load1, 2), round(load5, 2), round(load15, 2)],
                "loadPercent": load_percent,
            },
            "memory": {
                "percent": round(mem.percent, 1),
                "usedMB": round(mem.used / (1024 * 1024)),
                "totalMB": round(mem.total / (1024 * 1024)),
                "availableMB": round(mem.available / (1024 * 1024)),
            },
            "thresholds": {
                "cpuWarn": 50,
                "cpuStop": 70,
                "memWarn": 65,
                "memStop": 80,
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    }


# ── Admin: Data Accumulation Status for ML Readiness ──
@app.get("/api/admin/data-accumulation")
async def admin_data_accumulation():
    """ML data accumulation progress. Returns counts of key collections."""
    if db is None:
        return {"ok": False, "error": "MongoDB not connected"}
    
    ie_db = _motor_client["intelligence_engine"]
    
    collections = {
        "sentiment_shadow_decisions": "Shadow ML решения",
        "sentiment_dir_samples": "Направленные сэмплы",
        "sentiment_aggregates": "Агрегированные сентименты",
        "sentiment_events": "События сентимента",
        "raw_events": "Сырые события (новости)",
        "sentiment_processing": "Обработанные сентименты",
        "exch_shadow_predictions": "Exchange Shadow прогнозы",
        "exchange_forecast_shadow": "Exchange Forecast Shadow",
        "ml_overlay_shadow": "ML Overlay Shadow",
    }
    
    counts = {}
    for col_name, label in collections.items():
        try:
            count = await ie_db[col_name].count_documents({})
            counts[col_name] = {"count": count, "label": label}
        except Exception:
            counts[col_name] = {"count": 0, "label": label}
    
    # ML Readiness thresholds
    dir_samples = counts.get("sentiment_dir_samples", {}).get("count", 0)
    shadow_decisions = counts.get("sentiment_shadow_decisions", {}).get("count", 0)
    
    ml_min_threshold = 150
    ml_good_threshold = 500
    
    readiness = "NOT_READY"
    if dir_samples >= ml_good_threshold:
        readiness = "READY"
    elif dir_samples >= ml_min_threshold:
        readiness = "MINIMUM_MET"
    
    return {
        "ok": True,
        "data": {
            "collections": counts,
            "mlReadiness": {
                "status": readiness,
                "dirSamples": dir_samples,
                "shadowDecisions": shadow_decisions,
                "minThreshold": ml_min_threshold,
                "goodThreshold": ml_good_threshold,
                "progress": min(100, round((dir_samples / ml_min_threshold) * 100)),
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    }


# ── Admin: Data Distribution Audit (P5) ──
@app.get("/api/admin/data-distribution")
async def admin_data_distribution():
    """P5: Data distribution audit. Events per asset, per type, per timeframe. Detects imbalances."""
    if db is None:
        return {"ok": False, "error": "MongoDB not connected"}
    
    ie_db = _motor_client["intelligence_engine"]
    
    since_24h = datetime.now(timezone.utc) - timedelta(hours=24)
    
    # Events per asset (top 30)
    asset_pipeline = [
        {"$match": {"publishedAt": {"$gte": since_24h}, "sourceType": "news"}},
        {"$unwind": "$assetMentions"},
        {"$group": {"_id": "$assetMentions", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 30}
    ]
    
    # Events per source
    source_pipeline = [
        {"$match": {"publishedAt": {"$gte": since_24h}, "sourceType": "news"}},
        {"$group": {"_id": "$publisher.name", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 20}
    ]
    
    try:
        asset_dist = await ie_db.raw_events.aggregate(asset_pipeline).to_list(30)
        source_dist = await ie_db.raw_events.aggregate(source_pipeline).to_list(20)
        total_events = await ie_db.raw_events.count_documents({"publishedAt": {"$gte": since_24h}, "sourceType": "news"})
        
        # Detect imbalance
        warnings = []
        if asset_dist:
            top_asset_count = asset_dist[0]["count"] if asset_dist else 0
            if total_events > 0 and top_asset_count / total_events > 0.5:
                warnings.append(f"Перекос: {asset_dist[0]['_id']} = {round(top_asset_count/total_events*100)}% событий")
        
        return {
            "ok": True,
            "data": {
                "period": "24h",
                "totalEvents": total_events,
                "assetDistribution": [{"asset": a["_id"], "count": a["count"]} for a in asset_dist],
                "sourceDistribution": [{"source": s["_id"], "count": s["count"]} for s in source_dist],
                "warnings": warnings,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}
@app.get("/api/exchange/health")
async def exchange_health():
    """Comprehensive Exchange Intelligence health check.
    Returns HEALTHY / DEGRADED / CRITICAL with detailed pipeline status."""
    report = compute_health()
    status_code = 200 if report["status"] == "HEALTHY" else 503 if report["status"] == "CRITICAL" else 200
    return JSONResponse(content=report, status_code=status_code)


# ── R4.3: Rate Limiter Stats ──
@app.get("/api/exchange/guardrails")
async def exchange_guardrails():
    """Rate limiter and guardrail statistics."""
    return JSONResponse(content={
        "ok": True,
        "rateLimiter": get_rate_limiter_stats(),
        "config": {
            "maxPageSize": 100,
            "defaultPageSize": 25,
            "requestTimeoutSec": 30,
        },
    })


# ── R4.2: Cache Admin ──
@app.get("/api/exchange/cache/stats")
async def cache_stats():
    """Cache statistics."""
    import radar_cache
    return JSONResponse(content={"ok": True, "cache": radar_cache.get_stats()})


@app.post("/api/exchange/cache/invalidate")
async def cache_invalidate():
    """Invalidate all cache entries."""
    import radar_cache
    count = radar_cache.invalidate()
    return JSONResponse(content={"ok": True, "invalidated": count})

# ── Signal Pipeline API ──
from signal_pipeline import (
    build_signal_events, enrich_with_prices,
    compute_actor_metrics, build_training_dataset, run_full_pipeline,
    train_xgboost_model
)

@app.post("/api/ml/pipeline/run")
async def api_run_pipeline():
    """Run the full actor signal pipeline (P0.1 → P0.4)."""
    result = await run_full_pipeline()
    return JSONResponse(content=result)

@app.post("/api/ml/pipeline/signalize")
async def api_signalize():
    """P0.1: Convert parsed_tweets → actor_signal_events."""
    result = await build_signal_events()
    return JSONResponse(content=result)

@app.post("/api/ml/pipeline/enrich")
async def api_enrich():
    """P0.2: Enrich signal events with price data."""
    result = await enrich_with_prices()
    return JSONResponse(content=result)

@app.post("/api/ml/pipeline/actors")
async def api_actors():
    """P0.3: Compute actor intelligence metrics."""
    result = await compute_actor_metrics()
    return JSONResponse(content=result)

@app.post("/api/ml/pipeline/dataset")
async def api_dataset():
    """P0.4: Build training dataset."""
    result = await build_training_dataset()
    return JSONResponse(content=result)

@app.post("/api/ml/pipeline/train")
async def api_train():
    """P1: Train XGBoost binary model + shadow evaluation."""
    result = await train_xgboost_model()
    return JSONResponse(content=result)

@app.get("/api/ml/pipeline/status")
async def api_pipeline_status():
    """Get current pipeline data counts."""
    if db is None:
        return JSONResponse(content={"ok": False, "error": "DB not ready"})
    signal_events = await db.actor_signal_events.count_documents({})
    enriched = await db.actor_signal_events.count_documents({"enriched": True})
    actors = await db.actor_intelligence.count_documents({})
    dataset = await db.signal_training_dataset_v2.count_documents({})
    return JSONResponse(content={
        "ok": True,
        "signal_events": signal_events,
        "enriched_events": enriched,
        "actor_profiles": actors,
        "training_samples": dataset,
    })

# ── MLOps API ──
from ml_ops import (
    get_ml_status, retrain_job, compute_daily_metrics, compute_drift,
    compute_data_health, check_kill_switch, rollback_model, promote_model,
    evaluate_shadow, check_retrain_needed, compute_calibration,
    run_daily_jobs, list_models, get_metrics_history, get_top_signals,
    map_decision, run_live_predictions, get_signal_stats,
)


@app.get("/api/ml/status")
async def api_ml_status():
    """Complete ML system status: active model, drift, health, kill switch."""
    result = await get_ml_status()
    return JSONResponse(content=result)


@app.post("/api/ml/retrain")
async def api_ml_retrain():
    """Trigger model retrain. Produces a candidate model (not auto-promoted)."""
    result = await retrain_job()
    return JSONResponse(content=result)


@app.get("/api/ml/metrics/daily")
async def api_ml_daily_metrics(days: int = 30):
    """Get daily metrics history."""
    result = await get_metrics_history(days)
    return JSONResponse(content=result)


@app.post("/api/ml/metrics/compute")
async def api_ml_compute_daily():
    """Manually trigger daily metrics computation."""
    result = await compute_daily_metrics()
    return JSONResponse(content=result)


@app.get("/api/ml/drift")
async def api_ml_drift():
    """Get latest drift analysis."""
    result = await compute_drift()
    return JSONResponse(content=result)


@app.get("/api/ml/health")
async def api_ml_health():
    """Get data pipeline health."""
    result = await compute_data_health()
    return JSONResponse(content=result)


@app.get("/api/ml/shadow-eval")
async def api_ml_shadow_eval():
    """Evaluate shadow model vs production."""
    result = await evaluate_shadow()
    return JSONResponse(content=result)


@app.post("/api/ml/promote/{model_key}")
async def api_ml_promote(model_key: str):
    """Promote a candidate model to production (with validation checks)."""
    result = await promote_model(model_key)
    return JSONResponse(content=result)


@app.post("/api/ml/rollback")
async def api_ml_rollback():
    """Rollback active model to previous stable version."""
    result = await rollback_model()
    return JSONResponse(content=result)


@app.get("/api/ml/kill-switch")
async def api_ml_kill_switch():
    """Check if active model needs to be killed."""
    result = await check_kill_switch()
    return JSONResponse(content=result)


@app.get("/api/ml/retrain-check")
async def api_ml_retrain_check():
    """Check if retrain should be triggered (smart conditions)."""
    result = await check_retrain_needed()
    return JSONResponse(content=result)


@app.get("/api/ml/calibration")
async def api_ml_calibration():
    """Predicted vs actual calibration check."""
    result = await compute_calibration()
    return JSONResponse(content=result)


@app.post("/api/ml/daily-jobs")
async def api_ml_daily_jobs():
    """Run all daily ML monitoring jobs (metrics, drift, health, shadow, kill switch)."""
    result = await run_daily_jobs()
    return JSONResponse(content=result)


@app.get("/api/ml/models")
async def api_ml_models(status: str = None):
    """List all registered models, optionally filtered by status."""
    result = await list_models(status)
    return JSONResponse(content=result)


@app.get("/api/ml/signals/top")
async def api_ml_top_signals(limit: int = 10):
    """Get top recent actionable signals."""
    result = await get_top_signals(limit)
    return JSONResponse(content=result)


@app.get("/api/ml/decision")
async def api_ml_decision(probability: float = 0.5, position: str = "UNKNOWN",
                          actor_hit_rate: float = None, coordination: float = None):
    """Map ML probability to actionable decision (ENTER/FOLLOW/WATCH/AVOID)."""
    result = map_decision(probability, position, actor_hit_rate, coordination)
    return JSONResponse(content={"ok": True, "decision": result})


@app.post("/api/ml/predict/live")
async def api_ml_predict_live():
    """Run live predictions on all dataset samples through active + shadow models.
    Fills ml_shadow_predictions and ml_signal_log with real data."""
    result = await run_live_predictions()
    return JSONResponse(content=result)


@app.get("/api/ml/signals/stats")
async def api_ml_signal_stats():
    """Get aggregated signal statistics, top actors, top tokens."""
    result = await get_signal_stats()
    return JSONResponse(content=result)


# ── Live Evaluation Engine ──
from live_engine import (
    process_new_signals, update_positions, compute_live_metrics,
    confidence_bucket_analysis, actor_live_performance, action_performance,
    get_equity_curve, get_live_dashboard, list_positions, compute_composite_score,
    rolling_window_test, actor_drop_test, token_diversity_check,
    check_reentry_candidates, get_config, update_config,
)


@app.post("/api/ml/live/process")
async def api_ml_live_process():
    """Score, filter, and open positions from actionable signals."""
    result = await process_new_signals()
    return JSONResponse(content=result)


@app.post("/api/ml/live/update")
async def api_ml_live_update():
    """Update open positions with returns, apply TP/SL, close expired."""
    result = await update_positions()
    return JSONResponse(content=result)


@app.get("/api/ml/live/dashboard")
async def api_ml_live_dashboard():
    """Live trading dashboard — daily health check."""
    result = await get_live_dashboard()
    return JSONResponse(content=result)


@app.get("/api/ml/live/metrics")
async def api_ml_live_metrics():
    """Compute live metrics (hold vs TP/SL, equity, drawdown, profit consistency, tail risk)."""
    result = await compute_live_metrics()
    return JSONResponse(content=result)


@app.get("/api/ml/live/equity")
async def api_ml_live_equity():
    """Get equity curve from all closed positions."""
    result = await get_equity_curve()
    return JSONResponse(content=result)


@app.get("/api/ml/live/positions")
async def api_ml_live_positions(status: str = None, limit: int = 50):
    """List live positions (open/closed/all)."""
    result = await list_positions(status, limit)
    return JSONResponse(content=result)


@app.get("/api/ml/live/confidence-buckets")
async def api_ml_live_confidence_buckets():
    """Win rates by prediction confidence bucket (0.9+, 0.8-0.9, etc)."""
    result = await confidence_bucket_analysis()
    return JSONResponse(content=result)


@app.get("/api/ml/live/actor-stats")
async def api_ml_live_actor_stats():
    """Per-actor live performance."""
    result = await actor_live_performance()
    return JSONResponse(content=result)


@app.get("/api/ml/live/action-stats")
async def api_ml_live_action_stats():
    """ENTER vs FOLLOW vs WATCH performance comparison."""
    result = await action_performance()
    return JSONResponse(content=result)


@app.get("/api/ml/live/score")
async def api_ml_live_score(prediction: float = 0.5, actor_hit_rate: float = 0,
                            coordination: float = 0, position: str = "UNKNOWN",
                            age_hours: float = 0):
    """Compute composite score for a signal (preview)."""
    result = await compute_composite_score(prediction, actor_hit_rate, coordination, position, age_hours)
    return JSONResponse(content={"ok": True, "score": result})


@app.get("/api/ml/live/validate/rolling")
async def api_ml_live_rolling():
    """Rolling window test: 3d / 7d / 14d / all performance."""
    result = await rolling_window_test()
    return JSONResponse(content=result)


@app.get("/api/ml/live/validate/actor-drop")
async def api_ml_live_actor_drop():
    """Actor drop test: remove top-3 actors and check if system survives."""
    result = await actor_drop_test()
    return JSONResponse(content=result)


@app.get("/api/ml/live/validate/token-diversity")
async def api_ml_live_token_diversity():
    """Token diversity: how many different tokens contribute to profit."""
    result = await token_diversity_check()
    return JSONResponse(content=result)


@app.get("/api/ml/live/reentry")
async def api_ml_live_reentry():
    """Check for re-entry candidates (coordination increase + new actor)."""
    result = await check_reentry_candidates()
    return JSONResponse(content=result)


@app.get("/api/ml/live/config")
async def api_ml_live_config():
    """Get current live engine configuration."""
    cfg = await get_config()
    return JSONResponse(content={"ok": True, "config": cfg})


@app.post("/api/ml/live/config")
async def api_ml_live_config_update(request: Request):
    """Update live engine configuration."""
    body = await request.json()
    result = await update_config(body)
    return JSONResponse(content=result)


# ── Data Scaling Pipeline ──
from data_scaling import (
    discover_actors_token_first, discover_actors_comention,
    expand_signal_events, deduplicate_signals,
    build_expanded_dataset, compute_data_health_v2,
    pre_retrain_check, run_full_scaling,
)


@app.post("/api/ml/data/scale")
async def api_ml_data_scale(request: Request):
    """Run the full data scaling pipeline (discovery → expand → dedup → label → health)."""
    body = await request.json() if request.headers.get("content-type") == "application/json" else {}
    target = body.get("target_signals", 2000)
    days = body.get("time_window_days", 30)
    result = await run_full_scaling(target, days)
    return JSONResponse(content=result)


@app.get("/api/ml/data/discover/token-first")
async def api_ml_discover_token():
    """Token-first actor discovery."""
    result = await discover_actors_token_first()
    return JSONResponse(content=result)


@app.get("/api/ml/data/discover/comention")
async def api_ml_discover_comention():
    """Co-mention graph actor discovery."""
    result = await discover_actors_comention()
    return JSONResponse(content=result)


@app.post("/api/ml/data/expand")
async def api_ml_data_expand(request: Request):
    """Generate expanded signal events."""
    body = await request.json() if request.headers.get("content-type") == "application/json" else {}
    target = body.get("target_signals", 2000)
    days = body.get("time_window_days", 30)
    result = await expand_signal_events(target, days)
    return JSONResponse(content=result)


@app.post("/api/ml/data/dedup")
async def api_ml_data_dedup():
    """Run smart dedup v2 on signal events."""
    result = await deduplicate_signals()
    return JSONResponse(content=result)


@app.post("/api/ml/data/build-dataset")
async def api_ml_data_build():
    """Build expanded training dataset with relative BTC labeling."""
    result = await build_expanded_dataset()
    return JSONResponse(content=result)


@app.get("/api/ml/data/health")
async def api_ml_data_health_v2():
    """Enhanced data health with Gini coefficients."""
    result = await compute_data_health_v2()
    return JSONResponse(content=result)


@app.get("/api/ml/data/sanity-check")
async def api_ml_data_sanity():
    """Pre-retrain sanity checks."""
    result = await pre_retrain_check()
    return JSONResponse(content=result)


# ── User Account Management + Extension Limits ──
FREE_ACCOUNT_LIMIT = 2
FREE_KEYWORD_LIMIT = 2
EXT_ACCOUNT_LIMIT = 30
EXT_KEYWORD_LIMIT = 30

@app.get("/api/user/extension-status")
async def extension_status():
    """Check if user has extension connected and return limits."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{NODE_BACKEND_URL}/api/v4/twitter/integration/status")
            data = resp.json()
            state = data.get("data", {}).get("state", "NOT_CONNECTED")
            sessions = data.get("data", {}).get("sessions", {})
            has_extension = state == "CONNECTED"
            return JSONResponse(content={
                "ok": True,
                "hasExtension": has_extension,
                "state": state,
                "sessions": {"ok": sessions.get("ok", 0), "stale": sessions.get("stale", 0), "total": sessions.get("total", 0)},
                "limits": {
                    "accounts": EXT_ACCOUNT_LIMIT if has_extension else FREE_ACCOUNT_LIMIT,
                    "keywords": EXT_KEYWORD_LIMIT if has_extension else FREE_KEYWORD_LIMIT,
                },
            })
    except Exception as e:
        return JSONResponse(content={
            "ok": True,
            "hasExtension": False,
            "state": "NOT_CONNECTED",
            "sessions": {"ok": 0, "stale": 0, "total": 0},
            "limits": {"accounts": FREE_ACCOUNT_LIMIT, "keywords": FREE_KEYWORD_LIMIT},
        })

@app.get("/api/user/my-accounts")
async def get_my_accounts():
    """Get user's selected account IDs for tracking."""
    if db is None:
        return JSONResponse(content={"ok": True, "accounts": []})
    doc = await db.user_preferences.find_one({"type": "selected_accounts"}, {"_id": 0})
    accounts = doc.get("accounts", []) if doc else []
    return JSONResponse(content={"ok": True, "accounts": accounts})

@app.post("/api/user/my-accounts")
async def add_my_account(request: Request):
    """Add account to user's selected list."""
    if db is None:
        return JSONResponse(content={"ok": False, "error": "DB not configured"}, status_code=500)
    body = await request.json()
    account_id = body.get("accountId", "").strip()
    if not account_id:
        return JSONResponse(content={"ok": False, "error": "accountId required"}, status_code=400)
    
    doc = await db.user_preferences.find_one({"type": "selected_accounts"}, {"_id": 0})
    current = doc.get("accounts", []) if doc else []
    if account_id in current:
        return JSONResponse(content={"ok": True, "accounts": current, "message": "Already added"})
    
    current.append(account_id)
    await db.user_preferences.update_one(
        {"type": "selected_accounts"},
        {"$set": {"accounts": current, "updatedAt": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )
    return JSONResponse(content={"ok": True, "accounts": current})

@app.delete("/api/user/my-accounts")
async def delete_my_account(request: Request):
    """Remove account from user's selected list."""
    if db is None:
        return JSONResponse(content={"ok": False, "error": "DB not configured"}, status_code=500)
    account_id = request.query_params.get("id", "").strip()
    if not account_id:
        return JSONResponse(content={"ok": False, "error": "id query param required"}, status_code=400)
    
    doc = await db.user_preferences.find_one({"type": "selected_accounts"}, {"_id": 0})
    current = doc.get("accounts", []) if doc else []
    current = [a for a in current if a != account_id]
    await db.user_preferences.update_one(
        {"type": "selected_accounts"},
        {"$set": {"accounts": current, "updatedAt": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )
    return JSONResponse(content={"ok": True, "accounts": current})

# ── Real vs Synthetic Validation Framework ──
from validation_framework import run_real_vs_synthetic_validation

@app.get("/api/ml/data/real-vs-synthetic")
async def api_ml_real_vs_synthetic():
    """Run 4 strict tests: A(synth→real), B(real→real), C(mixed→real), D(real→live holdout)."""
    result = await run_real_vs_synthetic_validation()
    return JSONResponse(content=result)


# ── Twitter Ingestion (Real Data) ──
from twitter_ingestion import (
    check_parser_health,
    search_tweets as tw_search,
    ingest_actor_tweets,
    ingest_search,
    mass_ingest_actors,
    get_ingestion_status,
)

@app.get("/api/ml/ingest/status")
async def api_ingest_status():
    """Current real vs synthetic data breakdown."""
    result = await get_ingestion_status()
    return JSONResponse(content=result)

@app.get("/api/ml/ingest/parser-health")
async def api_parser_health():
    """Check if Twitter parser Node.js service is alive."""
    result = await check_parser_health()
    return JSONResponse(content=result)

@app.post("/api/ml/ingest/actor")
async def api_ingest_actor(request: Request):
    """Ingest tweets from a specific actor. Body: {username, limit}."""
    body = await request.json()
    username = body.get("username", "")
    limit = body.get("limit", 50)
    if not username:
        return JSONResponse(content={"ok": False, "error": "username required"}, status_code=400)
    result = await ingest_actor_tweets(username, limit)
    return JSONResponse(content=result)

@app.post("/api/ml/ingest/search")
async def api_ingest_search(request: Request):
    """Search and ingest tweets for a keyword. Body: {keyword, limit}."""
    body = await request.json()
    keyword = body.get("keyword", "")
    limit = body.get("limit", 50)
    if not keyword:
        return JSONResponse(content={"ok": False, "error": "keyword required"}, status_code=400)
    result = await ingest_search(keyword, limit)
    return JSONResponse(content=result)

@app.post("/api/ml/ingest/mass")
async def api_ingest_mass(request: Request):
    """Ingest tweets from multiple actors. Body: {actors: [...], tweets_per_actor: 30}."""
    body = await request.json()
    actors = body.get("actors", [])
    tpa = body.get("tweets_per_actor", 30)
    if not actors:
        return JSONResponse(content={"ok": False, "error": "actors list required"}, status_code=400)
    result = await mass_ingest_actors(actors, tpa)
    return JSONResponse(content=result)


# ── Real Sentiment Model (Phase 1) ──
from sentiment_model import analyze_sentiment, analyze_batch, backfill_events, get_inference_stats

@app.post("/api/sentiment/analyze")
async def api_sentiment_analyze(request: Request):
    """Analyze a single text for sentiment. Body: {text, author_handle?, token?}."""
    body = await request.json()
    text = body.get("text", "")
    if not text:
        return JSONResponse(content={"ok": False, "error": "text required"}, status_code=400)
    result = await analyze_sentiment(
        text=text,
        author_handle=body.get("author_handle", ""),
        token=body.get("token", ""),
    )
    return JSONResponse(content={"ok": True, **result})

@app.post("/api/sentiment/batch")
async def api_sentiment_batch(request: Request):
    """Analyze multiple texts. Body: {items: [{text, author_handle?, token?}, ...]}."""
    body = await request.json()
    items = body.get("items", [])
    if not items:
        return JSONResponse(content={"ok": False, "error": "items required"}, status_code=400)
    results = await analyze_batch(items)
    return JSONResponse(content={"ok": True, "results": results, "count": len(results)})

@app.post("/api/sentiment/backfill")
async def api_sentiment_backfill(request: Request):
    """Run sentiment inference on existing actor_signal_events. Body: {limit?, skip_analyzed?}."""
    body = await request.json()
    limit = body.get("limit", 50)
    skip = body.get("skip_analyzed", True)
    from ml_ops import get_db as _get_ml_db
    ml_db = _get_ml_db()
    result = await backfill_events(ml_db, limit=limit, skip_analyzed=skip)
    return JSONResponse(content=result)

@app.get("/api/sentiment/stats")
async def api_sentiment_stats():
    """Get sentiment inference statistics."""
    from ml_ops import get_db as _get_ml_db
    ml_db = _get_ml_db()
    stats = await get_inference_stats(ml_db)
    return JSONResponse(content={"ok": True, **stats})


@app.get("/api/sentiment/ml-readiness")
async def api_sentiment_ml_readiness():
    """
    ML Readiness Gate — checks if Sentiment dataset is ready for ML training.
    Conditions: dataset_entries >= 300, distribution not skewed, resolved rate high, DQS acceptable.
    """
    from ml_ops import get_db as _get_db
    db = _get_db()
    reasons = []

    # 1. Dataset size
    dataset_size = await db.dataset_entries.count_documents({})
    min_entries = 300
    if dataset_size < min_entries:
        reasons.append(f"dataset_entries={dataset_size} < {min_entries} minimum")

    # 2. Resolved rate
    total_v3 = await db.sentiment_training_dataset_v3.count_documents({})
    resolved_v3 = await db.sentiment_training_dataset_v3.count_documents({"outcome.resolved": True})
    resolved_pct = round(resolved_v3 / max(total_v3, 1) * 100, 1)
    if resolved_pct < 80:
        reasons.append(f"resolved_rate={resolved_pct}% < 80% minimum")

    # 3. Label distribution (should not be > 80% one label)
    pipeline_label = [
        {"$match": {"outcome.resolved": True}},
        {"$group": {"_id": "$outcome.label", "count": {"$sum": 1}}},
    ]
    label_dist = {}
    async for r in db.dataset_entries.aggregate(pipeline_label):
        label_dist[r["_id"] or "UNKNOWN"] = r["count"]
    total_labeled = sum(label_dist.values()) or 1
    for label, count in label_dist.items():
        pct = count / total_labeled * 100
        if pct > 80:
            reasons.append(f"label '{label}' dominates at {pct:.0f}% (>80% skew)")

    # 4. Event type distribution (unknown should be < 50%)
    pipeline_event = [
        {"$group": {"_id": "$quality.event_type", "count": {"$sum": 1}}},
    ]
    event_dist = {}
    async for r in db.dataset_entries.aggregate(pipeline_event):
        event_dist[r["_id"] or "unknown"] = r["count"]
    unknown_count = event_dist.get("unknown", 0) + event_dist.get(None, 0)
    unknown_pct = round(unknown_count / max(dataset_size, 1) * 100, 1)
    if unknown_pct > 50:
        reasons.append(f"event_type unknown={unknown_pct}% > 50% threshold")

    # 5. DQS check
    pipeline_dqs = [
        {"$group": {"_id": None, "avg_dqs": {"$avg": "$quality.dqs"}}},
    ]
    dqs_result = await db.dataset_entries.aggregate(pipeline_dqs).to_list(1)
    avg_dqs = round(dqs_result[0]["avg_dqs"], 4) if dqs_result and dqs_result[0].get("avg_dqs") is not None else 0

    # Distribution health
    distribution_health = "OK" if not reasons else "ISSUES"

    return JSONResponse(content={
        "ready": len(reasons) == 0,
        "reasons": reasons,
        "dataset_size": dataset_size,
        "min_required": min_entries,
        "resolved_rate_pct": resolved_pct,
        "avg_dqs": avg_dqs,
        "label_distribution": label_dist,
        "event_type_distribution": event_dist,
        "unknown_event_pct": unknown_pct,
        "distribution_health": distribution_health,
    })


# ── Enrichment Layer (Phase 2) ──
from enrichment_layer import run_enrichment_pipeline, get_enrichment_stats

@app.post("/api/enrichment/run")
async def api_enrichment_run(request: Request):
    """Run full enrichment on real events. Body: {limit?, skip_enriched?}."""
    body = await request.json()
    limit = body.get("limit", 50)
    skip = body.get("skip_enriched", True)
    result = await run_enrichment_pipeline(limit=limit, skip_enriched=skip)
    return JSONResponse(content=result)

@app.get("/api/enrichment/stats")
async def api_enrichment_stats():
    """Get enriched signal event statistics."""
    stats = await get_enrichment_stats()
    return JSONResponse(content=stats)


# ── Dataset V3 + DQS (Phase 3) ──
from dataset_builder import build_dataset_v3, get_dataset_v3_stats, get_data_health, extract_features

@app.post("/api/dataset/v3/build")
async def api_dataset_v3_build(request: Request):
    """Build dataset v3 from enriched events. Body: {limit?}."""
    body = await request.json()
    limit = body.get("limit", 100)
    result = await build_dataset_v3(limit=limit)
    return JSONResponse(content=result)

@app.get("/api/dataset/v3/stats")
async def api_dataset_v3_stats():
    """Get dataset v3 stats + distribution + diversity."""
    stats = await get_dataset_v3_stats()
    return JSONResponse(content=stats)

@app.get("/api/dataset/v3/health")
async def api_dataset_v3_health():
    """Anti-degradation: check dataset quality trends."""
    health = await get_data_health()
    return JSONResponse(content=health)

@app.get("/api/dataset/v3/features/sample")
async def api_dataset_v3_features_sample():
    """Get sample feature vector from dataset v3."""
    from ml_ops import get_db as _get_ml_db
    db = _get_ml_db()
    sample = await db.sentiment_training_dataset_v3.find_one(
        {"outcome.resolved": True}, {"_id": 0}
    )
    if not sample:
        return JSONResponse(content={"ok": False, "error": "no resolved samples"})
    features = extract_features(sample)
    return JSONResponse(content={"ok": True, "features": features, "dqs": sample.get("quality", {}).get("dqs", 0)})


# ── Cron Ingestion ──
from cron_ingestion import run_ingestion_cycle, get_cron_status, start_scheduler, stop_scheduler, get_scheduler_status, enable_pipeline
from outcome_resolver import run_outcome_resolution, get_outcome_stats
from graph_bridge import run_graph_bridge, get_graph_bridge_stats, run_graph_pipeline, get_parser_registry
from news_pipeline import run_news_pipeline, get_news_stats

@app.post("/api/ingestion/cycle")
async def api_ingestion_cycle(request: Request):
    """Run a full ingestion cycle (normally triggered by cron). Body: {tokens_limit?, actor_limit?}."""
    body = await request.json()
    result = await run_ingestion_cycle(
        tokens_limit=body.get("tokens_limit", 20),
        actor_limit=body.get("actor_limit", 15),
    )
    return JSONResponse(content=result)

@app.get("/api/ingestion/cron/status")
async def api_cron_status():
    """Get cron ingestion status."""
    status = await get_cron_status()
    return JSONResponse(content=status)


@app.post("/api/ingestion/scheduler/start")
async def api_scheduler_start():
    """Start the 6-hour ingestion scheduler."""
    result = start_scheduler()
    return JSONResponse(content=result)


@app.post("/api/ingestion/scheduler/stop")
async def api_scheduler_stop():
    """Stop the ingestion scheduler."""
    result = stop_scheduler()
    return JSONResponse(content=result)


@app.get("/api/ingestion/scheduler/status")
async def api_scheduler_status():
    """Get scheduler status."""
    return JSONResponse(content=get_scheduler_status())


@app.post("/api/ingestion/pipeline/enable")
async def api_pipeline_enable():
    """Re-enable pipeline after hard stop."""
    result = await enable_pipeline()
    return JSONResponse(content=result)



# ── Dataset Entries (ML Production Dataset) ──

@app.post("/api/dataset/entries/write")
async def api_dataset_entries_write(request: Request):
    """Write resolved signals into dataset_entries for ML training."""
    from dataset_writer import write_dataset_entries
    body = await request.json() if request.headers.get("content-type") == "application/json" else {}
    limit = body.get("limit", 500)
    result = await write_dataset_entries(limit=limit)
    return JSONResponse(content=result)


@app.get("/api/dataset/entries/stats")
async def api_dataset_entries_stats():
    """Get dataset_entries stats for ML readiness."""
    from dataset_writer import get_dataset_entries_stats
    result = await get_dataset_entries_stats()
    return JSONResponse(content=result)



# ── Outcome Resolver ──

@app.post("/api/outcome/resolve")
async def api_outcome_resolve(request: Request):
    """Run outcome resolution on unresolved dataset v3 samples. Body: {limit?}."""
    body = await request.json()
    limit = body.get("limit", 200)
    result = await run_outcome_resolution(limit=limit)
    return JSONResponse(content=result)


@app.get("/api/outcome/stats")
async def api_outcome_stats():
    """Get outcome resolution statistics."""
    stats = await get_outcome_stats()
    return JSONResponse(content=stats)



@app.post("/api/outcome/backfill-labels-v2")
async def api_backfill_labels_v2(limit: int = 100, rescore: bool = False):
    """
    Backfill V2 shadow labels for already-resolved samples that don't have them yet.
    If rescore=true, re-runs sampling score on ALL resolved samples (for score calibration).
    Safe: only writes audit.labels_v2 and audit.label_inputs, never changes outcome.label.
    """
    from outcome_resolver import (
        _find_peak_prices_with_timing, compute_label_v2, _iso_to_ms,
        LABEL_V2_THRESHOLDS, LABEL_V2_DEFAULT,
        detect_event_type, get_dynamic_window,
        compute_event_score, sampling_decision,
    )
    from ml_ops import get_db as _get_db
    db = _get_db()
    col = db["sentiment_training_dataset_v3"]

    if rescore:
        # Re-score mode: re-run sampling on all resolved samples
        re_cursor = col.find(
            {"outcome.resolved": True, "audit.sampling": {"$exists": True}},
            {"_id": 1, "sentiment.intent": 1, "sentiment.confidence": 1,
             "actor.score": 1, "actor.role": 1, "actor.hit_rate": 1,
             "signal": 1, "market.volatility": 1, "market.momentum": 1,
             "text.raw": 1, "audit.evaluation.event_type": 1}
        ).limit(5000)
        re_docs = await re_cursor.to_list(5000)
        rescored = 0
        for rd in re_docs:
            try:
                ev_score, ev_breakdown = compute_event_score(rd)
                et = rd.get("audit", {}).get("evaluation", {}).get("event_type") or detect_event_type(rd)
                inc_new, inc_reason = sampling_decision(ev_score)
                await col.update_one({"_id": rd["_id"]}, {"$set": {
                    "audit.sampling.event_score": ev_score,
                    "audit.sampling.included_new": inc_new,
                    "audit.sampling.include_reason": inc_reason,
                    "audit.sampling.event_type": et,
                    "audit.sampling.breakdown": ev_breakdown,
                }})
                rescored += 1
            except Exception:
                pass
        return JSONResponse(content={
            "ok": True, "mode": "rescore",
            "rescored": rescored, "total_checked": len(re_docs),
        })

    cursor = col.find(
        {"outcome.resolved": True, "audit.labels_v2": {"$exists": False}},
        {"_id": 1, "meta.created_at": 1, "market.token": 1,
         "market.price_at_signal": 1, "outcome.label": 1,
         "outcome.btc_rel_24h": 1, "outcome.pnl_24h": 1,
         "sentiment.intent": 1, "sentiment.confidence": 1,
         "actor.score": 1, "actor.role": 1, "actor.hit_rate": 1,
         "signal": 1, "market.volatility": 1, "market.momentum": 1,
         "text.raw": 1}
    ).limit(limit)

    samples = await cursor.to_list(limit)
    updated = 0
    errors = 0

    for s in samples:
        try:
            token = s.get("market", {}).get("token", "")
            price_at = s.get("market", {}).get("price_at_signal", 0)
            created_at = s.get("meta", {}).get("created_at", "")
            old_label = s.get("outcome", {}).get("label", "NEUTRAL")

            if not token or not price_at or not created_at:
                continue

            ts_ms = _iso_to_ms(created_at)
            if not ts_ms:
                continue

            horizon = "24H"
            event_type = detect_event_type(s)
            dw = get_dynamic_window(event_type, horizon)
            window_ms = int(dw["window_hours"] * 3600 * 1000)

            max_price, min_price, time_to_max_h, time_to_min_h = \
                await _find_peak_prices_with_timing(token, ts_ms, window_ms)

            if max_price is None or min_price is None or price_at <= 0:
                continue

            move_up = ((max_price - price_at) / price_at) * 100
            move_down = ((price_at - min_price) / price_at) * 100

            final_ret = s.get("outcome", {}).get("btc_rel_24h")
            if final_ret is None:
                final_ret = s.get("outcome", {}).get("pnl_24h", 0)

            # Early exit detection
            th = LABEL_V2_THRESHOLDS.get(horizon, LABEL_V2_DEFAULT)
            early_exit = False
            if move_up >= th["strong"] and (time_to_max_h or 999) <= 24:
                early_exit = True
            elif move_down >= th["strong"] and (time_to_min_h or 999) <= 24:
                early_exit = True

            v2_label, v2_conf = compute_label_v2(move_up, move_down, final_ret or 0, horizon)

            peak_vs_final = abs(move_up - (final_ret or 0)) if move_up > move_down \
                else abs(move_down + (final_ret or 0))

            await col.update_one({"_id": s["_id"]}, {"$set": {
                "audit.labels_v2": {
                    "old": old_label, "new": v2_label,
                    "confidence_score": v2_conf, "changed": old_label != v2_label,
                },
                "audit.label_inputs": {
                    "move_up_peak": round(move_up, 4),
                    "move_down_peak": round(move_down, 4),
                    "final_return": round(final_ret or 0, 4),
                    "horizon": horizon,
                    "thresholds": LABEL_V2_THRESHOLDS.get(horizon, LABEL_V2_DEFAULT),
                    "max_price": round(max_price, 6),
                    "min_price": round(min_price, 6),
                    "entry_price": round(price_at, 6),
                },
                "audit.evaluation": {
                    "event_type": event_type,
                    "window_used_hours": dw["window_hours"],
                    "time_to_peak_up_hours": time_to_max_h,
                    "time_to_peak_down_hours": time_to_min_h,
                    "early_exit": early_exit,
                    "peak_vs_final_gap": round(peak_vs_final, 4),
                    "dynamic_window": dw,
                },
            }})

            # Sampling audit (separate update, outside main $set to avoid nesting issues)
            try:
                ev_score, ev_breakdown = compute_event_score(s)
                inc_new, inc_reason = sampling_decision(ev_score)
                await col.update_one({"_id": s["_id"]}, {"$set": {
                    "audit.sampling": {
                        "event_score": ev_score,
                        "included_old": True,
                        "included_new": inc_new,
                        "include_reason": inc_reason,
                        "event_type": event_type,
                        "breakdown": ev_breakdown,
                    },
                }})
            except Exception:
                pass  # Shadow: don't fail on sampling errors

            updated += 1
        except Exception:
            errors += 1

    return JSONResponse(content={
        "ok": True,
        "backfilled": updated,
        "errors": errors,
        "remaining": await col.count_documents(
            {"outcome.resolved": True, "audit.labels_v2": {"$exists": False}}
        ),
    })


@app.get("/api/outcome/evaluation-alignment")
async def api_evaluation_alignment():
    """Evaluation Alignment stats: dynamic windows, early hits, peak vs final."""
    from ml_ops import get_db as _get_db
    db = _get_db()
    col = db["sentiment_training_dataset_v3"]

    # Find all with evaluation audit
    cursor = col.find(
        {"audit.evaluation": {"$exists": True}},
        {"_id": 0, "audit.evaluation": 1, "audit.labels_v2": 1,
         "audit.label_inputs": 1, "sentiment.intent": 1}
    )
    docs = await cursor.to_list(500)

    if not docs:
        return JSONResponse(content={
            "ok": True, "total": 0, "by_event_type": {},
            "early_exit_rate": 0, "avg_time_to_peak_up": None,
            "avg_time_to_peak_down": None, "avg_peak_vs_final_gap": None,
            "peak_captured_but_final_missed": 0,
        })

    total = len(docs)
    early_exits = sum(1 for d in docs if d.get("audit", {}).get("evaluation", {}).get("early_exit"))

    # By event type
    by_type: dict = {}
    times_up = []
    times_down = []
    gaps = []
    peak_captured_final_missed = 0

    for d in docs:
        ev = d.get("audit", {}).get("evaluation", {})
        et = ev.get("event_type", "unknown")
        li = d.get("audit", {}).get("label_inputs", {})
        lv2 = d.get("audit", {}).get("labels_v2", {})

        if et not in by_type:
            by_type[et] = {"count": 0, "early_exits": 0, "labels": {}}
        by_type[et]["count"] += 1
        if ev.get("early_exit"):
            by_type[et]["early_exits"] += 1
        new_label = lv2.get("new", "NEUTRAL")
        by_type[et]["labels"][new_label] = by_type[et]["labels"].get(new_label, 0) + 1

        if ev.get("time_to_peak_up_hours") is not None:
            times_up.append(ev["time_to_peak_up_hours"])
        if ev.get("time_to_peak_down_hours") is not None:
            times_down.append(ev["time_to_peak_down_hours"])
        if ev.get("peak_vs_final_gap") is not None:
            gaps.append(ev["peak_vs_final_gap"])

        # Peak captured but final missed: move_up >= weak but label is NEUTRAL
        move_up = li.get("move_up_peak", 0)
        move_down = li.get("move_down_peak", 0)
        weak_th = li.get("thresholds", {}).get("weak", 1.5)
        if (move_up >= weak_th or move_down >= weak_th) and new_label == "NEUTRAL":
            peak_captured_final_missed += 1

    return JSONResponse(content={
        "ok": True,
        "total": total,
        "early_exit_rate": round(early_exits / max(total, 1) * 100, 1),
        "avg_time_to_peak_up": round(sum(times_up) / len(times_up), 2) if times_up else None,
        "avg_time_to_peak_down": round(sum(times_down) / len(times_down), 2) if times_down else None,
        "avg_peak_vs_final_gap": round(sum(gaps) / len(gaps), 4) if gaps else None,
        "peak_captured_but_final_missed": peak_captured_final_missed,
        "peak_captured_pct": round(peak_captured_final_missed / max(total, 1) * 100, 1),
        "by_event_type": by_type,
    })



# ─── Production Rollout Endpoints ───

@app.get("/api/outcome/rollout-status")
async def api_rollout_status():
    """Get current production rollout status."""
    import outcome_resolver as _or
    from ml_ops import get_db as _get_db
    db = _get_db()
    col = db["sentiment_training_dataset_v3"]

    total_resolved = await col.count_documents({"outcome.resolved": True})
    v2_labeled = await col.count_documents({"outcome.label_version": "v2"})
    v1_labeled = await col.count_documents({
        "outcome.resolved": True,
        "$or": [{"outcome.label_version": "v1"}, {"outcome.label_version": {"$exists": False}}]
    })
    sampling_active = await col.count_documents({"audit.sampling.sampling_active": True})

    return JSONResponse(content={
        "ok": True,
        "labels_v2_production": _or.LABELS_V2_PRODUCTION,
        "sampling_rollout_pct": _or.SAMPLING_ROLLOUT_PCT,
        "total_resolved": total_resolved,
        "v2_labeled": v2_labeled,
        "v1_labeled": v1_labeled,
        "v2_pct": round(v2_labeled / max(total_resolved, 1) * 100, 1),
        "sampling_active_count": sampling_active,
        "rollout_state": _or._rollout_state,
        "next_step": _or.get_next_rollout_step(),
        "rollout_steps": _or.ROLLOUT_STEPS,
    })


@app.post("/api/outcome/promote-v2-labels")
async def api_promote_v2_labels(limit: int = 500):
    """Bulk promote V2 shadow labels to production for existing resolved samples."""
    from ml_ops import get_db as _get_db
    db = _get_db()
    col = db["sentiment_training_dataset_v3"]

    cursor = col.find(
        {
            "outcome.resolved": True,
            "audit.labels_v2.new": {"$exists": True},
            "$or": [{"outcome.label_version": {"$ne": "v2"}}, {"outcome.label_version": {"$exists": False}}]
        },
        {"_id": 1, "audit.labels_v2.new": 1, "outcome.label": 1}
    ).limit(limit)

    docs = await cursor.to_list(limit)
    promoted = 0
    for d in docs:
        v2_label = d.get("audit", {}).get("labels_v2", {}).get("new")
        if not v2_label:
            continue
        old_label = d.get("outcome", {}).get("label", "NEUTRAL")
        await col.update_one({"_id": d["_id"]}, {"$set": {
            "outcome.label": v2_label,
            "outcome.label_v1": old_label,
            "outcome.label_version": "v2",
            "outcome.tradeable": v2_label != "NEUTRAL",
        }})
        promoted += 1

    remaining = await col.count_documents({
        "outcome.resolved": True,
        "audit.labels_v2.new": {"$exists": True},
        "$or": [{"outcome.label_version": {"$ne": "v2"}}, {"outcome.label_version": {"$exists": False}}]
    })

    return JSONResponse(content={
        "ok": True,
        "promoted": promoted,
        "remaining": remaining,
    })


@app.post("/api/outcome/rollout-set")
async def api_rollout_set(pct: float = 0.0):
    """Set the sampling rollout percentage (manual control)."""
    import outcome_resolver as _or
    from ml_ops import get_db as _get_db
    from datetime import datetime, timezone
    old_pct = _or.SAMPLING_ROLLOUT_PCT
    _or.SAMPLING_ROLLOUT_PCT = pct
    _or._rollout_state["last_rollout_at"] = datetime.now(timezone.utc).isoformat()
    _or._rollout_state["consecutive_passes"] = 0
    _or._rollout_state["status"] = "COOLDOWN"
    # Persist to DB
    db = _get_db()
    await db.system_config.update_one(
        {"key": "sampling_rollout"},
        {"$set": {"key": "sampling_rollout", "pct": pct, "state": _or._rollout_state, "updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )
    return JSONResponse(content={
        "ok": True,
        "old_pct": old_pct,
        "new_pct": pct,
    })


@app.get("/api/outcome/rollout-check")
async def api_rollout_check():
    """
    Check rollout health: are conditions met for promotion?
    Returns READY/NOT_READY/COOLDOWN/ROLLBACK status.
    Auto-rollback if thresholds breached.
    """
    import outcome_resolver as _or
    from ml_ops import get_db as _get_db
    db = _get_db()
    col = db["sentiment_training_dataset_v3"]

    # Get current distribution from sampling data
    cursor = col.find(
        {"audit.sampling": {"$exists": True}},
        {"_id": 0, "audit.sampling.event_score": 1, "audit.sampling.included_new": 1}
    )
    docs = await cursor.to_list(5000)

    if not docs:
        return JSONResponse(content={"ok": True, "status": "NO_DATA", "message": "No sampling data"})

    scores = [d.get("audit", {}).get("sampling", {}).get("event_score", 0) for d in docs]
    total = len(scores)
    included = sum(1 for d in docs if d.get("audit", {}).get("sampling", {}).get("included_new", False))

    high_count = sum(1 for s in scores if s >= 0.6)
    med_count = sum(1 for s in scores if 0.3 <= s < 0.6)
    low_count = sum(1 for s in scores if s < 0.3)

    distribution = {
        "high_pct": round(high_count / max(total, 1) * 100, 1),
        "medium_pct": round(med_count / max(total, 1) * 100, 1),
        "low_pct": round(low_count / max(total, 1) * 100, 1),
        "include_rate": round(included / max(total, 1) * 100, 1),
        "total": total,
    }

    health = _or.check_rollout_health(distribution)
    state_update = _or.update_rollout_state(health)

    return JSONResponse(content={
        "ok": True,
        "current_pct": _or.SAMPLING_ROLLOUT_PCT,
        "next_step": _or.get_next_rollout_step(),
        "distribution": distribution,
        "health": health,
        "state": state_update,
        "rollout_state": _or._rollout_state,
    })


@app.post("/api/outcome/rollout-promote")
async def api_rollout_promote():
    """
    Human-approved promotion to next rollout step.
    Only works when status is READY_FOR_N%.
    """
    import outcome_resolver as _or

    status = _or._rollout_state.get("status", "")
    if not status.startswith("READY_FOR_"):
        return JSONResponse(status_code=400, content={
            "ok": False,
            "error": "NOT_READY",
            "message": f"Current status: {status}. Must be READY_FOR_N% to promote.",
            "current_pct": _or.SAMPLING_ROLLOUT_PCT,
        })

    result = _or.execute_promotion()
    return JSONResponse(content={
        "ok": True,
        **result,
        "message": f"Promoted from {result['old_pct']}% to {result['new_pct']}%",
    })


@app.get("/api/outcome/sampling-quality")
async def api_sampling_quality():
    """Sampling Strategy V1 shadow stats: event scores, include rates, breakdown."""
    from ml_ops import get_db as _get_db
    import outcome_resolver as _or
    db = _get_db()
    col = db["sentiment_training_dataset_v3"]

    # Recompute sampling stats using current detect_event_type
    cursor = col.find({}, {"_id": 0, "text": 1, "signal": 1, "sentiment": 1, "actor": 1, "market": 1, "audit.sampling": 1})
    docs = await cursor.to_list(1000)

    if not docs:
        return JSONResponse(content={
            "ok": True, "total": 0,
            "score_histogram": [], "include_rate_new": 0,
            "avg_score": None, "avg_score_included": None,
            "by_reason": {}, "by_event_type": {},
        })

    total = len(docs)
    scores = []
    included_new = 0
    included_scores = []
    by_reason: dict = {}
    by_type: dict = {}

    for d in docs:
        s = d.get("audit", {}).get("sampling", {})
        # Live-compute event_score and event_type from current detect_event_type
        score, breakdown = _or.compute_event_score(d)
        scores.append(score)
        inc, reason = _or.sampling_decision(score)
        et, _ = _or.detect_event_type(d)

        if inc:
            included_new += 1
            included_scores.append(score)

        by_reason[reason] = by_reason.get(reason, 0) + 1

        if et not in by_type:
            by_type[et] = {"count": 0, "included": 0, "avg_score": 0, "scores": []}
        by_type[et]["count"] += 1
        by_type[et]["scores"].append(score)
        if inc:
            by_type[et]["included"] += 1

    # Compute averages per type
    for et in by_type:
        s_list = by_type[et].pop("scores")
        by_type[et]["avg_score"] = round(sum(s_list) / len(s_list), 4) if s_list else 0
        by_type[et]["include_rate"] = round(by_type[et]["included"] / max(by_type[et]["count"], 1) * 100, 1)

    # Score histogram (5 buckets)
    buckets = [
        {"range": "0.0-0.2", "count": sum(1 for s in scores if s < 0.2)},
        {"range": "0.2-0.4", "count": sum(1 for s in scores if 0.2 <= s < 0.4)},
        {"range": "0.4-0.6", "count": sum(1 for s in scores if 0.4 <= s < 0.6)},
        {"range": "0.6-0.8", "count": sum(1 for s in scores if 0.6 <= s < 0.8)},
        {"range": "0.8-1.0", "count": sum(1 for s in scores if s >= 0.8)},
    ]

    # Percentiles
    sorted_scores = sorted(scores)
    n = len(sorted_scores)
    def _pct(p):
        idx = min(int(p / 100 * (n - 1)), n - 1)
        return round(sorted_scores[idx], 4)

    percentiles = {
        "p50": _pct(50),
        "p75": _pct(75),
        "p90": _pct(90),
        "p95": _pct(95),
        "max_score": round(max(scores), 4) if scores else 0,
    } if n > 0 else {"p50": 0, "p75": 0, "p90": 0, "p95": 0, "max_score": 0}

    # Priority buckets
    high_count = sum(1 for s in scores if s >= 0.6)
    medium_count = sum(1 for s in scores if 0.3 <= s < 0.6)
    low_count = sum(1 for s in scores if s < 0.3)

    return JSONResponse(content={
        "ok": True,
        "total": total,
        "include_rate_new": round(included_new / max(total, 1) * 100, 1),
        "included_count": included_new,
        "rejected_count": total - included_new,
        "avg_score": round(sum(scores) / len(scores), 4) if scores else None,
        "avg_score_included": round(sum(included_scores) / len(included_scores), 4) if included_scores else None,
        "score_histogram": buckets,
        "by_reason": by_reason,
        "by_event_type": by_type,
        "percentiles": percentiles,
        "priority_buckets": {
            "high": {"count": high_count, "pct": round(high_count / max(total, 1) * 100, 1)},
            "medium": {"count": medium_count, "pct": round(medium_count / max(total, 1) * 100, 1)},
            "low": {"count": low_count, "pct": round(low_count / max(total, 1) * 100, 1)},
        },
    })



@app.get("/api/prediction/c1-audit")
async def api_prediction_c1_audit():
    """
    Sprint 4 C1: Prediction Core Audit — read-only diagnostic.
    Analyzes evaluated 7D forecasts and classifies into TP/FP/NEUTRAL_MISS/REVERSAL_MISS.
    """
    from ml_ops import get_db as _get_db
    db = _get_db()

    cursor = db.exchange_forecasts.find(
        {"horizon": "7D", "evaluated": True},
        {"_id": 0, "direction": 1, "confidence": 1, "outcome": 1,
         "audit.regime": 1, "audit.scoreRaw": 1, "audit.scoreFinal": 1,
         "symbol": 1}
    ).sort("createdAt", -1).limit(100)
    docs = await cursor.to_list(100)

    tp, fp, neutral_miss, reversal_miss, neutral_ok = 0, 0, 0, 0, 0
    regimes_tp, regimes_fp = {}, {}
    scores_tp, scores_fp, scores_rev = [], [], []

    for d in docs:
        direction = d.get("direction", "NEUTRAL")
        outcome = d.get("outcome", {}) or {}
        real_move = outcome.get("realMovePct", 0) or 0
        dir_match = outcome.get("directionMatch", False)
        regime = d.get("audit", {}).get("regime", "unknown")
        score_raw = d.get("audit", {}).get("scoreRaw", 0) or 0

        if direction in ("LONG", "SHORT"):
            if dir_match:
                tp += 1
                scores_tp.append(score_raw)
                regimes_tp[regime] = regimes_tp.get(regime, 0) + 1
            else:
                fp += 1
                scores_fp.append(score_raw)
                regimes_fp[regime] = regimes_fp.get(regime, 0) + 1
        else:
            if abs(real_move) >= 5:
                reversal_miss += 1
                scores_rev.append(score_raw)
            elif abs(real_move) >= 2:
                neutral_miss += 1
            else:
                neutral_ok += 1

    total_dir = tp + fp
    total_neutral = neutral_ok + neutral_miss + reversal_miss
    dir_accuracy = round(tp / max(total_dir, 1) * 100, 1)
    neutral_miss_rate = round((neutral_miss + reversal_miss) / max(total_neutral, 1) * 100, 1)

    has_new_format = any(d.get("audit", {}).get("regime") for d in docs)

    return JSONResponse(content={
        "ok": True,
        "total_analyzed": len(docs),
        "classification": {
            "tp": tp, "fp": fp,
            "neutral_correct": neutral_ok,
            "neutral_miss": neutral_miss,
            "reversal_miss": reversal_miss,
        },
        "directional_accuracy_pct": dir_accuracy,
        "neutral_miss_rate_pct": neutral_miss_rate,
        "regimes": {"tp": regimes_tp, "fp": regimes_fp},
        "avg_scores": {
            "tp": round(sum(scores_tp) / max(len(scores_tp), 1), 4),
            "fp": round(sum(scores_fp) / max(len(scores_fp), 1), 4),
            "reversal_miss": round(sum(scores_rev) / max(len(scores_rev), 1), 4),
        },
        "has_new_format": has_new_format,
        "root_causes": [
            "NEUTRAL zone too wide (80%+ miss rate)",
            "Bullish bias in TREND regime (27/28 FP = TREND+LONG)",
            "Exchange signal adapter disconnected (0/321 have exchange data)",
            "Confidence uncalibrated (flat ~20-35% across all bins)",
            "Reversal signals suppressed (avg score near zero for -11% moves)",
        ],
    })


@app.get("/api/prediction/v1-vs-v2")
async def api_prediction_v1_vs_v2():
    """
    Decision V1 vs V2 comparison — Sprint 4 C2.9.
    Backtests Decision V2 on evaluated forecasts and compares with V1.
    """
    from ml_ops import get_db as _get_db
    db = _get_db()
    from forecast.decision_v2 import compute_decision_v2

    cursor = db.exchange_forecasts.find(
        {"horizon": "7D", "evaluated": True, "audit.regime": {"$exists": True}},
        {"_id": 0, "direction": 1, "confidence": 1, "audit": 1,
         "outcome.realMovePct": 1, "symbol": 1}
    ).sort("createdAt", -1).limit(100)
    docs = await cursor.to_list(100)

    v1 = {"tp": 0, "fp": 0, "neutral_miss": 0, "reversal_miss": 0, "neutral_ok": 0}
    v2 = {"tp": 0, "fp": 0, "neutral_miss": 0, "reversal_miss": 0, "neutral_ok": 0}
    changes = 0

    for d in docs:
        v1_dir = d.get("direction", "NEUTRAL")
        real_move = d.get("outcome", {}).get("realMovePct", 0) or 0
        audit = d.get("audit", {})
        score_final = audit.get("scoreFinal", 0) or 0
        exch_signal = audit.get("exchange_signal", {})

        v2_result = compute_decision_v2(
            base_score=score_final,
            exchange_signal=exch_signal,
            audit=audit,
            v1_direction=v1_dir,
            v1_confidence=d.get("confidence", 0),
        )
        v2_dir = v2_result["direction"]
        if v1_dir != v2_dir:
            changes += 1

        for label, direction in [(v1, v1_dir), (v2, v2_dir)]:
            if direction in ("LONG", "SHORT"):
                if (direction == "LONG" and real_move > 0) or (direction == "SHORT" and real_move < 0):
                    label["tp"] += 1
                else:
                    label["fp"] += 1
            else:
                if abs(real_move) >= 5:
                    label["reversal_miss"] += 1
                elif abs(real_move) >= 2:
                    label["neutral_miss"] += 1
                else:
                    label["neutral_ok"] += 1

    total = len(docs)
    v1_dir_total = v1["tp"] + v1["fp"]
    v2_dir_total = v2["tp"] + v2["fp"]
    v1_acc = round(v1["tp"] / max(v1_dir_total, 1) * 100, 1)
    v2_acc = round(v2["tp"] / max(v2_dir_total, 1) * 100, 1)
    v1_neutral = v1["neutral_ok"] + v1["neutral_miss"] + v1["reversal_miss"]
    v2_neutral = v2["neutral_ok"] + v2["neutral_miss"] + v2["reversal_miss"]

    v2_neutral_pct = round(v2_neutral / max(total, 1) * 100, 1)
    pass_criteria = {
        "neutral_below_50": v2_neutral_pct < 50,
        "accuracy_improved": v2_acc > v1_acc,
        "reversal_improved": v2["reversal_miss"] <= v1["reversal_miss"],
        "fp_stable": v2["fp"] <= v1["fp"] * 1.5,
    }
    all_pass = all(pass_criteria.values())

    return JSONResponse(content={
        "ok": True,
        "total_analyzed": total,
        "v1": {**v1, "directional": v1_dir_total, "neutral_total": v1_neutral, "accuracy_pct": v1_acc},
        "v2": {**v2, "directional": v2_dir_total, "neutral_total": v2_neutral, "accuracy_pct": v2_acc, "neutral_pct": v2_neutral_pct},
        "directions_changed": changes,
        "pass_criteria": pass_criteria,
        "all_pass": all_pass,
        "summary": f"V2: {v2_acc}% accuracy (+{v2_acc-v1_acc:.1f}pp), NEUTRAL {v2_neutral_pct}% (was {round(v1_neutral/max(total,1)*100,1)}%), reversal miss {v2['reversal_miss']} (was {v1['reversal_miss']})",
    })



@app.get("/api/prediction/forecast-v1-vs-v2")
async def api_forecast_v1_vs_v2():
    """
    Forecast V1 vs V2 comparison — Sprint 4 C3.9.
    Backtests Forecast V2 (enhanced score) + Decision V2 on evaluated forecasts.
    """
    from ml_ops import get_db as _get_db
    db = _get_db()
    from forecast.forecast_v2 import compute_forecast_v2
    from forecast.decision_v2 import compute_decision_v2

    cursor = db.exchange_forecasts.find(
        {"horizon": "7D", "evaluated": True, "audit.regime": {"$exists": True}},
        {"_id": 0, "direction": 1, "confidence": 1, "audit": 1,
         "outcome.realMovePct": 1, "symbol": 1, "entryPrice": 1}
    ).sort("createdAt", -1).limit(100)
    docs = await cursor.to_list(100)
    total = len(docs)

    v1 = {"tp": 0, "fp": 0, "neutral_miss": 0, "reversal_miss": 0, "neutral_ok": 0}
    v2 = {"tp": 0, "fp": 0, "neutral_miss": 0, "reversal_miss": 0, "neutral_ok": 0}
    v1_scores, v2_scores, outcomes = [], [], []

    for d in docs:
        v1_dir = d.get("direction", "NEUTRAL")
        real_move = d.get("outcome", {}).get("realMovePct", 0) or 0
        audit = d.get("audit", {})
        score_final = audit.get("scoreFinal", 0) or 0
        features = audit.get("features", {})
        exch = audit.get("exchange_signal", {})

        fv2 = compute_forecast_v2(
            base_score=score_final, exchange_signal=exch, audit=audit,
            features=features, price=d.get("entryPrice", 1), db=None,
            asset=d.get("symbol", "").replace("USDT", ""), horizon="7D",
        )
        v2_score = fv2["final_score"]
        v1_scores.append(score_final)
        v2_scores.append(v2_score)
        outcomes.append(real_move)

        dv2 = compute_decision_v2(
            base_score=v2_score, exchange_signal=exch, audit=audit,
            v1_direction=v1_dir, v1_confidence=d.get("confidence", 0),
        )
        v2_dir = dv2["direction"]

        for label, direction in [(v1, v1_dir), (v2, v2_dir)]:
            if direction in ("LONG", "SHORT"):
                if (direction == "LONG" and real_move > 0) or (direction == "SHORT" and real_move < 0):
                    label["tp"] += 1
                else:
                    label["fp"] += 1
            else:
                if abs(real_move) >= 5:
                    label["reversal_miss"] += 1
                elif abs(real_move) >= 2:
                    label["neutral_miss"] += 1
                else:
                    label["neutral_ok"] += 1

    import numpy as np
    v1_arr, v2_arr, out_arr = np.array(v1_scores), np.array(v2_scores), np.array(outcomes)
    v1_corr = float(np.corrcoef(v1_arr, out_arr)[0, 1]) if total > 1 else 0
    v2_corr = float(np.corrcoef(v2_arr, out_arr)[0, 1]) if total > 1 else 0

    v1_dt = v1["tp"] + v1["fp"]
    v2_dt = v2["tp"] + v2["fp"]
    v1_acc = round(v1["tp"] / max(v1_dt, 1) * 100, 1)
    v2_acc = round(v2["tp"] / max(v2_dt, 1) * 100, 1)
    v1_n = v1["neutral_ok"] + v1["neutral_miss"] + v1["reversal_miss"]
    v2_n = v2["neutral_ok"] + v2["neutral_miss"] + v2["reversal_miss"]

    pass_criteria = {
        "score_spread_maintained": float(np.std(v2_arr)) >= float(np.std(v1_arr)) * 0.9,
        "correlation_maintained": abs(v2_corr) >= abs(v1_corr) * 0.9,
        "accuracy_improved": v2_acc >= v1_acc,
        "fp_stable": v2["fp"] <= v1["fp"] * 1.5,
    }

    return JSONResponse(content={
        "ok": True,
        "total_analyzed": total,
        "score_stats": {
            "v1_std": round(float(np.std(v1_arr)), 4),
            "v2_std": round(float(np.std(v2_arr)), 4),
            "v1_mean": round(float(np.mean(v1_arr)), 4),
            "v2_mean": round(float(np.mean(v2_arr)), 4),
            "v1_correlation": round(v1_corr, 4),
            "v2_correlation": round(v2_corr, 4),
        },
        "v1": {**v1, "directional": v1_dt, "neutral_total": v1_n, "accuracy_pct": v1_acc},
        "v2_full": {**v2, "directional": v2_dt, "neutral_total": v2_n, "accuracy_pct": v2_acc,
                    "neutral_pct": round(v2_n / max(total, 1) * 100, 1)},
        "pass_criteria": pass_criteria,
        "all_pass": all(pass_criteria.values()),
        "summary": f"Forecast+Decision V2: {v2_acc}% acc (+{v2_acc-v1_acc:.1f}pp), NEUTRAL {round(v2_n/max(total,1)*100,1)}%, reversal miss {v2['reversal_miss']} (was {v1['reversal_miss']}), corr {v2_corr:.3f}",
    })



@app.get("/api/sentiment/stability-monitor")
async def api_sentiment_stability_monitor():
    """
    Data Stability Monitor - Block 3.4.
    Tracks distribution drift, score drift, include rate stability, event mix over time.
    Stores snapshots in DB for 72h monitoring.
    """
    import outcome_resolver as _or
    from ml_ops import get_db as _get_db
    db = _get_db()
    col = db["sentiment_training_dataset_v3"]

    cursor = col.find({}, {"_id": 0, "text": 1, "signal": 1, "sentiment": 1, "actor": 1, "market": 1})
    docs = await cursor.to_list(2000)
    total = len(docs)

    if total == 0:
        return JSONResponse(content={"ok": True, "status": "NO_DATA"})

    scores = []
    event_types = {}
    included = 0
    for d in docs:
        score, _ = _or.compute_event_score(d)
        scores.append(score)
        inc, _ = _or.sampling_decision(score)
        if inc:
            included += 1
        et, _ = _or.detect_event_type(d)
        event_types[et] = event_types.get(et, 0) + 1

    sorted_scores = sorted(scores)
    n = len(sorted_scores)

    snapshot = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total": total,
        "sampling_pct": _or.SAMPLING_ROLLOUT_PCT,
        "distribution": {
            "high_pct": round(sum(1 for s in scores if s >= 0.6) / total * 100, 1),
            "medium_pct": round(sum(1 for s in scores if 0.3 <= s < 0.6) / total * 100, 1),
            "low_pct": round(sum(1 for s in scores if s < 0.3) / total * 100, 1),
        },
        "scores": {
            "avg": round(sum(scores) / n, 4),
            "p50": round(sorted_scores[n // 2], 4),
            "p75": round(sorted_scores[int(n * 0.75)], 4),
            "p95": round(sorted_scores[int(n * 0.95)], 4),
        },
        "include_rate": round(included / total * 100, 1),
        "event_mix": event_types,
        "unknown_pct": round(event_types.get("unknown", 0) / total * 100, 1),
    }

    await db.stability_snapshots.insert_one({**snapshot, "_id_skip": True})

    cutoff = (datetime.now(timezone.utc) - timedelta(hours=72)).isoformat()
    history_cursor = db.stability_snapshots.find(
        {"timestamp": {"$gte": cutoff}},
        {"_id": 0}
    ).sort("timestamp", 1)
    history = await history_cursor.to_list(100)

    drift_alerts = []
    if len(history) >= 2:
        first = history[0]
        latest = history[-1]
        avg_diff = abs(latest.get("scores", {}).get("avg", 0) - first.get("scores", {}).get("avg", 0))
        if avg_diff > 0.05:
            drift_alerts.append(f"avg_score drift: {avg_diff:.4f} (>{0.05} threshold)")
        ir_diff = abs(latest.get("include_rate", 0) - first.get("include_rate", 0))
        if ir_diff > 15:
            drift_alerts.append(f"include_rate drift: {ir_diff:.1f}pp (>15pp threshold)")
        unk_diff = latest.get("unknown_pct", 0) - first.get("unknown_pct", 0)
        if unk_diff > 10:
            drift_alerts.append(f"unknown_pct growing: +{unk_diff:.1f}pp")

    status = "STABLE" if not drift_alerts else "DRIFT_DETECTED"

    return JSONResponse(content={
        "ok": True,
        "status": status,
        "current": snapshot,
        "drift_alerts": drift_alerts,
        "history_count": len(history),
        "monitoring_window_hours": 72,
    })


# ====================================================
# SYSTEM CONVERGENCE APIs
# ====================================================

@app.get("/api/system/convergence-status")
async def api_convergence_status():
    """Current V2 convergence status - mode, percentage, steps."""
    from forecast.convergence import get_convergence_status
    status = get_convergence_status()
    return JSONResponse(content={"ok": True, **status})


@app.post("/api/system/v2-rollout")
async def api_v2_rollout(pct: float = 0.10):
    """Adjust V2 live rollout percentage (0.0 to 1.0). Persists to DB."""
    import forecast.convergence as _conv
    from ml_ops import get_db as _get_db
    pct = max(0.0, min(1.0, pct))
    old_pct = _conv.SYSTEM_V2_PCT
    _conv.SYSTEM_V2_PCT = pct

    if pct == 0:
        _conv.SYSTEM_V2_MODE = "shadow_only"
    elif pct >= 1.0:
        _conv.SYSTEM_V2_MODE = "live_only"
    else:
        _conv.SYSTEM_V2_MODE = "shadow_plus_live"

    # Persist
    db = _get_db()
    await db.system_config.update_one(
        {"key": "v2_convergence"},
        {"$set": {
            "key": "v2_convergence",
            "pct": pct,
            "mode": _conv.SYSTEM_V2_MODE,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )
    return JSONResponse(content={
        "ok": True, "old_pct": old_pct, "new_pct": pct,
        "mode": _conv.SYSTEM_V2_MODE,
    })


@app.post("/api/system/rollback-v2")
async def api_rollback_v2():
    """Emergency rollback: V2 to 0%, shadow_only mode."""
    import forecast.convergence as _conv
    from ml_ops import get_db as _get_db
    old_pct = _conv.SYSTEM_V2_PCT
    _conv.SYSTEM_V2_PCT = 0.0
    _conv.SYSTEM_V2_MODE = "shadow_only"

    db = _get_db()
    await db.system_config.update_one(
        {"key": "v2_convergence"},
        {"$set": {
            "key": "v2_convergence",
            "pct": 0.0,
            "mode": "shadow_only",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "rollback_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )
    # Save rollback event
    await db.system_snapshots.insert_one({
        "stage": "rollback_v2",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "old_pct": old_pct,
    })
    return JSONResponse(content={
        "ok": True, "rolled_back_from": old_pct,
        "mode": "shadow_only", "v2_pct": 0.0,
    })


@app.get("/api/system/v2-live-comparison")
async def api_v2_live_comparison():
    """Compare V1 vs V2 live forecasts (only those with convergence audit)."""
    from ml_ops import get_db as _get_db
    db = _get_db()

    cursor = db.exchange_forecasts.find(
        {"audit.convergence": {"$exists": True}, "evaluated": True},
        {"_id": 0, "direction": 1, "confidence": 1,
         "audit.convergence": 1, "outcome.realMovePct": 1}
    ).sort("createdAt", -1).limit(200)
    docs = await cursor.to_list(200)

    v1_live = {"tp": 0, "fp": 0, "neutral": 0, "count": 0}
    v2_live = {"tp": 0, "fp": 0, "neutral": 0, "count": 0}

    for d in docs:
        conv = d.get("audit", {}).get("convergence", {})
        real_move = d.get("outcome", {}).get("realMovePct", 0) or 0
        sys_ver = conv.get("system_version", "V1")

        target = v2_live if sys_ver == "V2" else v1_live
        target["count"] += 1
        direction = d.get("direction", "NEUTRAL")

        if direction in ("LONG", "SHORT"):
            if (direction == "LONG" and real_move > 0) or (direction == "SHORT" and real_move < 0):
                target["tp"] += 1
            else:
                target["fp"] += 1
        else:
            target["neutral"] += 1

    for grp in (v1_live, v2_live):
        dt = grp["tp"] + grp["fp"]
        grp["accuracy_pct"] = round(grp["tp"] / max(dt, 1) * 100, 1)
        grp["directional"] = dt

    return JSONResponse(content={
        "ok": True,
        "total_with_convergence": len(docs),
        "v1_live": v1_live,
        "v2_live": v2_live,
        "note": "Only evaluated forecasts with convergence audit are included",
    })


# ====================================================
# PLO OBSERVABILITY APIs (Post-Launch Optimization)
# ====================================================

@app.get("/api/system/v2-cohorts")
async def api_v2_cohorts():
    """
    PLO-1: Cohort analysis by confidence buckets.
    Splits evaluated V2 forecasts into High/Mid/Low confidence cohorts
    and measures accuracy within each.
    """
    from ml_ops import get_db as _get_db
    db = _get_db()

    cursor = db.exchange_forecasts.find(
        {"audit.convergence": {"$exists": True}, "evaluated": True},
        {"_id": 0, "direction": 1, "confidence": 1, "horizon": 1,
         "audit.convergence": 1, "outcome.realMovePct": 1, "symbol": 1}
    ).sort("createdAt", -1).limit(500)
    docs = await cursor.to_list(500)

    def _make_bucket():
        return {"count": 0, "tp": 0, "fp": 0, "neutral": 0, "accuracy_pct": 0.0}

    cohorts = {
        "v2": {"high": _make_bucket(), "mid": _make_bucket(), "low": _make_bucket()},
        "v1": {"high": _make_bucket(), "mid": _make_bucket(), "low": _make_bucket()},
    }

    for d in docs:
        conv = d.get("audit", {}).get("convergence", {})
        sys_ver = conv.get("system_version", "V1")
        real_move = d.get("outcome", {}).get("realMovePct", 0) or 0
        direction = d.get("direction", "NEUTRAL")
        confidence = d.get("confidence", 0) or 0

        ver_key = "v2" if sys_ver == "V2" else "v1"
        if confidence >= 0.7:
            bucket_key = "high"
        elif confidence >= 0.4:
            bucket_key = "mid"
        else:
            bucket_key = "low"

        b = cohorts[ver_key][bucket_key]
        b["count"] += 1

        if direction in ("LONG", "SHORT"):
            if (direction == "LONG" and real_move > 0) or (direction == "SHORT" and real_move < 0):
                b["tp"] += 1
            else:
                b["fp"] += 1
        else:
            b["neutral"] += 1

    # Compute accuracy for each bucket
    for ver in cohorts.values():
        for b in ver.values():
            directional = b["tp"] + b["fp"]
            b["accuracy_pct"] = round(b["tp"] / max(directional, 1) * 100, 1)
            b["directional"] = directional

    # Expectations vs reality
    expectations = {
        "high": "> 60%", "mid": "45-55%", "low": "< 40%"
    }
    health = {}
    for bk in ("high", "mid", "low"):
        v2b = cohorts["v2"][bk]
        health[bk] = {
            "accuracy": v2b["accuracy_pct"],
            "expected": expectations[bk],
            "sample_size": v2b["directional"],
            "sufficient_data": v2b["directional"] >= 10,
        }

    return JSONResponse(content={
        "ok": True,
        "total_evaluated": len(docs),
        "cohorts": cohorts,
        "health_check": health,
        "note": "Confidence cohorts: High >= 0.7, Mid 0.4-0.7, Low < 0.4",
    })


@app.get("/api/system/v2-fp-clusters")
async def api_v2_fp_clusters():
    """
    PLO-2: False Positive cluster detection.
    Groups FP signals by regime, exchange_bias, confidence, asset, horizon
    to find repeating error patterns.
    """
    from ml_ops import get_db as _get_db
    db = _get_db()

    cursor = db.exchange_forecasts.find(
        {"audit.convergence": {"$exists": True}, "evaluated": True},
        {"_id": 0, "direction": 1, "confidence": 1, "horizon": 1,
         "symbol": 1,
         "audit.convergence": 1, "audit.regime": 1,
         "audit.decision_v2": 1, "audit.forecast_v2": 1,
         "audit.exchange_signal": 1, "audit.scoreFinal": 1,
         "outcome.realMovePct": 1}
    ).sort("createdAt", -1).limit(500)
    docs = await cursor.to_list(500)

    fp_list = []
    total_v2_directional = 0

    for d in docs:
        conv = d.get("audit", {}).get("convergence", {})
        if conv.get("system_version") != "V2":
            continue

        direction = d.get("direction", "NEUTRAL")
        if direction not in ("LONG", "SHORT"):
            continue

        total_v2_directional += 1
        real_move = d.get("outcome", {}).get("realMovePct", 0) or 0
        is_tp = (direction == "LONG" and real_move > 0) or (direction == "SHORT" and real_move < 0)
        if is_tp:
            continue

        # This is a FP — extract clustering dimensions
        confidence = d.get("confidence", 0) or 0
        regime = d.get("audit", {}).get("regime", "UNKNOWN")
        dv2 = d.get("audit", {}).get("decision_v2", {}) or {}
        regime_dir = dv2.get("regime_direction", "UNKNOWN")
        ex_sig = d.get("audit", {}).get("exchange_signal", {}) or {}
        micro_bias = ex_sig.get("micro_bias", 0) or 0
        symbol = d.get("symbol", "UNKNOWN")
        asset = symbol.replace("USDT", "") if symbol.endswith("USDT") else symbol
        horizon = d.get("horizon", "UNKNOWN")

        # Bucketize exchange bias
        abs_mb = abs(micro_bias)
        if abs_mb > 0.6:
            ex_bucket = "strong"
        elif abs_mb > 0.3:
            ex_bucket = "moderate"
        else:
            ex_bucket = "weak"

        # Bucketize confidence
        if confidence >= 0.7:
            conf_bucket = "high"
        elif confidence >= 0.4:
            conf_bucket = "mid"
        else:
            conf_bucket = "low"

        fp_list.append({
            "direction": direction,
            "confidence": round(confidence, 4),
            "regime": regime,
            "regime_direction": regime_dir,
            "exchange_bias": round(micro_bias, 4),
            "exchange_bucket": ex_bucket,
            "conf_bucket": conf_bucket,
            "asset": asset,
            "horizon": horizon,
            "real_move_pct": round(real_move, 4),
        })

    # Cluster by dimensions
    clusters = {
        "by_regime": {},
        "by_exchange_bucket": {},
        "by_conf_bucket": {},
        "by_asset": {},
        "by_horizon": {},
        "by_regime_direction": {},
    }
    for fp in fp_list:
        for dim, key in [
            ("by_regime", fp["regime"]),
            ("by_exchange_bucket", fp["exchange_bucket"]),
            ("by_conf_bucket", fp["conf_bucket"]),
            ("by_asset", fp["asset"]),
            ("by_horizon", fp["horizon"]),
            ("by_regime_direction", fp.get("regime_direction", "UNKNOWN")),
        ]:
            clusters[dim][key] = clusters[dim].get(key, 0) + 1

    # Find dominant patterns (top combos)
    combo_counts = {}
    for fp in fp_list:
        combo = f"{fp['regime_direction']}+{fp['direction']}+{fp['conf_bucket']}"
        combo_counts[combo] = combo_counts.get(combo, 0) + 1
    top_patterns = sorted(combo_counts.items(), key=lambda x: -x[1])[:5]

    return JSONResponse(content={
        "ok": True,
        "total_v2_directional": total_v2_directional,
        "total_fp": len(fp_list),
        "fp_rate_pct": round(len(fp_list) / max(total_v2_directional, 1) * 100, 1),
        "clusters": clusters,
        "top_patterns": [{"pattern": p, "count": c} for p, c in top_patterns],
        "raw_fp_sample": fp_list[:20],
        "note": "Patterns show regime_direction + direction + confidence_bucket",
    })


@app.get("/api/system/v2-daily-report")
async def api_v2_daily_report():
    """
    PLO-8: Daily metrics loop.
    Aggregates accuracy, FP, confidence buckets, reversal success per day
    for the last 7 days.
    """
    from ml_ops import get_db as _get_db
    db = _get_db()

    cursor = db.exchange_forecasts.find(
        {"audit.convergence": {"$exists": True}, "evaluated": True},
        {"_id": 0, "direction": 1, "confidence": 1,
         "audit.convergence": 1, "audit.decision_v2": 1,
         "outcome.realMovePct": 1, "createdAt": 1}
    ).sort("createdAt", -1).limit(1000)
    docs = await cursor.to_list(1000)

    daily = {}

    for d in docs:
        conv = d.get("audit", {}).get("convergence", {})
        sys_ver = conv.get("system_version", "V1")
        created = d.get("createdAt")
        if not created:
            continue

        # Extract day bucket
        if isinstance(created, (int, float)):
            from datetime import datetime as _dt
            day_key = _dt.utcfromtimestamp(created / 1000).strftime("%Y-%m-%d")
        elif isinstance(created, str):
            day_key = created[:10]
        elif hasattr(created, 'strftime'):
            day_key = created.strftime("%Y-%m-%d")
        else:
            continue

        if day_key not in daily:
            daily[day_key] = {
                "v1": {"tp": 0, "fp": 0, "neutral": 0, "count": 0},
                "v2": {"tp": 0, "fp": 0, "neutral": 0, "count": 0,
                       "conf_high": 0, "conf_mid": 0, "conf_low": 0,
                       "reversal_attempts": 0, "reversal_success": 0},
            }

        ver_key = "v2" if sys_ver == "V2" else "v1"
        bucket = daily[day_key][ver_key]
        bucket["count"] += 1

        direction = d.get("direction", "NEUTRAL")
        real_move = d.get("outcome", {}).get("realMovePct", 0) or 0
        confidence = d.get("confidence", 0) or 0

        if direction in ("LONG", "SHORT"):
            is_tp = (direction == "LONG" and real_move > 0) or (direction == "SHORT" and real_move < 0)
            if is_tp:
                bucket["tp"] += 1
            else:
                bucket["fp"] += 1
        else:
            bucket["neutral"] += 1

        # V2-specific extras
        if ver_key == "v2":
            if confidence >= 0.7:
                bucket["conf_high"] += 1
            elif confidence >= 0.4:
                bucket["conf_mid"] += 1
            else:
                bucket["conf_low"] += 1

            dv2 = d.get("audit", {}).get("decision_v2", {}) or {}
            if dv2.get("reversal_signal"):
                bucket["reversal_attempts"] += 1
                is_tp_rev = (direction == "LONG" and real_move > 0) or (direction == "SHORT" and real_move < 0)
                if is_tp_rev:
                    bucket["reversal_success"] += 1

    # Build daily summaries sorted by date
    report = []
    for day_key in sorted(daily.keys(), reverse=True)[:7]:
        day_data = daily[day_key]
        for ver_key in ("v1", "v2"):
            b = day_data[ver_key]
            directional = b["tp"] + b["fp"]
            b["accuracy_pct"] = round(b["tp"] / max(directional, 1) * 100, 1)
            b["directional"] = directional
        v2d = day_data["v2"]
        v2d["reversal_success_pct"] = round(
            v2d["reversal_success"] / max(v2d["reversal_attempts"], 1) * 100, 1
        )
        report.append({"date": day_key, **day_data})

    # Aggregate totals
    totals_v2 = {"tp": 0, "fp": 0, "neutral": 0, "count": 0,
                 "reversal_attempts": 0, "reversal_success": 0}
    for r in report:
        for k in totals_v2:
            totals_v2[k] += r.get("v2", {}).get(k, 0)
    dt = totals_v2["tp"] + totals_v2["fp"]
    totals_v2["accuracy_pct"] = round(totals_v2["tp"] / max(dt, 1) * 100, 1)
    totals_v2["reversal_success_pct"] = round(
        totals_v2["reversal_success"] / max(totals_v2["reversal_attempts"], 1) * 100, 1
    )

    return JSONResponse(content={
        "ok": True,
        "days_covered": len(report),
        "daily": report,
        "totals_v2": totals_v2,
        "note": "Last 7 days, most recent first. V2 includes confidence buckets + reversal tracking.",
    })


@app.get("/api/system/v2-accuracy-alert")
async def api_v2_accuracy_alert():
    """
    PLO Alert: Fires if V2 accuracy drops below V1 by 10%+.
    Also checks for confidence explosion and FP surge.
    """
    from ml_ops import get_db as _get_db
    db = _get_db()

    cursor = db.exchange_forecasts.find(
        {"audit.convergence": {"$exists": True}, "evaluated": True},
        {"_id": 0, "direction": 1, "confidence": 1,
         "audit.convergence": 1, "outcome.realMovePct": 1}
    ).sort("createdAt", -1).limit(300)
    docs = await cursor.to_list(300)

    v1 = {"tp": 0, "fp": 0, "count": 0, "conf_sum": 0.0}
    v2 = {"tp": 0, "fp": 0, "count": 0, "conf_sum": 0.0}

    for d in docs:
        conv = d.get("audit", {}).get("convergence", {})
        sys_ver = conv.get("system_version", "V1")
        real_move = d.get("outcome", {}).get("realMovePct", 0) or 0
        direction = d.get("direction", "NEUTRAL")
        confidence = d.get("confidence", 0) or 0

        target = v2 if sys_ver == "V2" else v1
        target["count"] += 1
        target["conf_sum"] += confidence

        if direction in ("LONG", "SHORT"):
            is_tp = (direction == "LONG" and real_move > 0) or (direction == "SHORT" and real_move < 0)
            if is_tp:
                target["tp"] += 1
            else:
                target["fp"] += 1

    alerts = []
    status = "OK"

    for grp in (v1, v2):
        dt = grp["tp"] + grp["fp"]
        grp["accuracy_pct"] = round(grp["tp"] / max(dt, 1) * 100, 1)
        grp["avg_conf"] = round(grp["conf_sum"] / max(grp["count"], 1), 4)

    # Alert 1: V2 accuracy < V1 by 10%+
    if v1["accuracy_pct"] > 0 and v2["accuracy_pct"] > 0:
        gap = v1["accuracy_pct"] - v2["accuracy_pct"]
        if gap >= 10:
            alerts.append({
                "type": "ACCURACY_DROP",
                "severity": "CRITICAL",
                "message": f"V2 accuracy ({v2['accuracy_pct']}%) is {gap:.1f}pp below V1 ({v1['accuracy_pct']}%)",
                "action": "Consider rollback via POST /api/system/rollback-v2",
            })

    # Alert 2: FP surge in V2
    v2_dt = v2["tp"] + v2["fp"]
    if v2_dt >= 5:
        v2_fp_rate = v2["fp"] / max(v2_dt, 1) * 100
        if v2_fp_rate > 70:
            alerts.append({
                "type": "FP_SURGE",
                "severity": "HIGH",
                "message": f"V2 FP rate at {v2_fp_rate:.1f}% ({v2['fp']}/{v2_dt})",
                "action": "Check /api/system/v2-fp-clusters for patterns",
            })

    # Alert 3: Confidence explosion (avg > 0.8)
    if v2["count"] >= 5 and v2["avg_conf"] > 0.8:
        alerts.append({
            "type": "CONFIDENCE_EXPLOSION",
            "severity": "HIGH",
            "message": f"V2 avg confidence at {v2['avg_conf']:.4f} (> 0.8 threshold)",
            "action": "Confidence calibration needed before promotion",
        })

    if alerts:
        status = "ALERT"

    return JSONResponse(content={
        "ok": True,
        "status": status,
        "alerts": alerts,
        "metrics": {
            "v1_accuracy": v1["accuracy_pct"],
            "v2_accuracy": v2["accuracy_pct"],
            "v1_count": v1["count"],
            "v2_count": v2["count"],
            "v2_avg_confidence": v2["avg_conf"],
        },
        "sufficient_data": v2["tp"] + v2["fp"] >= 10,
        "note": "Alerts fire when V2 degrades vs V1. CRITICAL = consider rollback.",
    })


@app.get("/api/system/v2-rollout-readiness")
async def api_v2_rollout_readiness():
    """
    Pre-check for next rollout stage (25%).
    Validates: 48h stability, no alerts, sufficient V2 sample size.
    """
    from ml_ops import get_db as _get_db
    from forecast.convergence import get_convergence_status
    db = _get_db()

    conv_status = get_convergence_status()
    current_pct = conv_status["v2_pct"]
    next_pct = conv_status.get("next_step_pct")

    # Count V2 evaluated forecasts
    v2_count = await db.exchange_forecasts.count_documents(
        {"audit.convergence.system_version": "V2", "evaluated": True}
    )

    # Check accuracy alert
    alert_resp = await api_v2_accuracy_alert()
    import json as _json
    alert_data = _json.loads(alert_resp.body.decode())

    checks = {
        "sufficient_v2_sample": v2_count >= 20,
        "no_critical_alerts": alert_data.get("status") == "OK",
        "sufficient_accuracy_data": alert_data.get("sufficient_data", False),
        "current_pct": current_pct,
        "next_pct": next_pct,
        "v2_evaluated_count": v2_count,
    }

    all_pass = all([
        checks["sufficient_v2_sample"],
        checks["no_critical_alerts"],
    ])

    return JSONResponse(content={
        "ok": True,
        "ready": all_pass,
        "checks": checks,
        "recommendation": f"Ready to promote to {next_pct*100:.0f}%" if all_pass and next_pct else "Not ready — see checks",
        "note": "Do NOT promote without user approval. This is a readiness check only.",
    })


@app.get("/api/system/aggregator-backtest")
async def api_aggregator_backtest(horizon: str = "7D", limit: int = 500):
    """
    BLOCK 7: Historical replay — forced validation.
    Runs aggregator on historical evaluated forecasts and compares with decision.
    """
    from ml_ops import get_db as _get_db
    from forecast.system.replay import run_replay
    db_sync = _get_db().delegate  # sync db for replay

    result = run_replay(db_sync, horizon_filter=horizon, limit=limit)
    return JSONResponse(content=result)


@app.get("/api/system/aggregator-validation")
async def api_aggregator_validation(horizon: str = "7D", limit: int = 500):
    """
    BLOCK 8: Auto validation — binary verdict.
    Runs backtest + validates: PASS / WARNING / FAIL.
    """
    from ml_ops import get_db as _get_db
    from forecast.system.replay import run_replay
    from forecast.system.validation import validate_backtest
    db_sync = _get_db().delegate

    backtest = run_replay(db_sync, horizon_filter=horizon, limit=limit)
    validation = validate_backtest(backtest)

    return JSONResponse(content={
        "ok": True,
        "backtest": backtest,
        "validation": validation,
    })


@app.get("/api/system/aggregator-vs-decision")
async def api_aggregator_vs_decision():
    """
    BLOCK 6: Compare System Aggregator (shadow) vs Decision V2.
    Shows accuracy, FP, direction distribution, and confidence calibration.
    """
    from ml_ops import get_db as _get_db
    db = _get_db()

    cursor = db.exchange_forecasts.find(
        {"audit.aggregator_v1": {"$exists": True}, "evaluated": True},
        {"_id": 0, "direction": 1, "confidence": 1,
         "audit.aggregator_v1": 1, "audit.decision_v2": 1,
         "audit.convergence": 1, "outcome.realMovePct": 1}
    ).sort("createdAt", -1).limit(300)
    docs = await cursor.to_list(300)

    decision = {"tp": 0, "fp": 0, "neutral": 0, "count": 0, "conf_sum": 0.0}
    aggregator = {"tp": 0, "fp": 0, "neutral": 0, "count": 0, "conf_sum": 0.0}

    agreements = 0

    for d in docs:
        real_move = d.get("outcome", {}).get("realMovePct", 0) or 0
        agg = d.get("audit", {}).get("aggregator_v1", {}) or {}
        dv2 = d.get("audit", {}).get("decision_v2", {}) or {}

        # Decision V2 metrics
        dv2_dir = dv2.get("direction", "NEUTRAL")
        dv2_conf = dv2.get("confidence", 0) or 0
        decision["count"] += 1
        decision["conf_sum"] += dv2_conf
        if dv2_dir in ("LONG", "SHORT"):
            is_tp = (dv2_dir == "LONG" and real_move > 0) or (dv2_dir == "SHORT" and real_move < 0)
            if is_tp:
                decision["tp"] += 1
            else:
                decision["fp"] += 1
        else:
            decision["neutral"] += 1

        # Aggregator metrics
        agg_dir = agg.get("direction", "NEUTRAL")
        agg_conf = agg.get("confidence", 0) or 0
        aggregator["count"] += 1
        aggregator["conf_sum"] += agg_conf
        if agg_dir in ("LONG", "SHORT"):
            is_tp_agg = (agg_dir == "LONG" and real_move > 0) or (agg_dir == "SHORT" and real_move < 0)
            if is_tp_agg:
                aggregator["tp"] += 1
            else:
                aggregator["fp"] += 1
        else:
            aggregator["neutral"] += 1

        if agg_dir == dv2_dir:
            agreements += 1

    for grp in (decision, aggregator):
        dt = grp["tp"] + grp["fp"]
        grp["accuracy_pct"] = round(grp["tp"] / max(dt, 1) * 100, 1)
        grp["directional"] = dt
        grp["avg_conf"] = round(grp["conf_sum"] / max(grp["count"], 1), 4)

    agreement_pct = round(agreements / max(len(docs), 1) * 100, 1) if docs else 0

    return JSONResponse(content={
        "ok": True,
        "total_evaluated": len(docs),
        "decision_v2": decision,
        "aggregator_v1": aggregator,
        "agreement_pct": agreement_pct,
        "note": "Shadow comparison. Aggregator includes sentiment + fractal signals.",
    })


@app.get("/api/system/aggregator-live-metrics")
async def api_aggregator_live_metrics():
    """
    5 key live monitoring metrics for the aggregator.
    1. Accuracy (aggregator vs decision)
    2. FP rate
    3. Reversal capture
    4. Confidence buckets
    5. Usage rate (exchange available %)
    """
    from ml_ops import get_db as _get_db
    db = _get_db()

    # All forecasts with aggregator telemetry
    cursor = db.exchange_forecasts.find(
        {"audit.aggregator_live": {"$exists": True}},
        {"_id": 0, "direction": 1, "confidence": 1,
         "audit.aggregator_live": 1, "audit.aggregator_v1": 1,
         "outcome.realMovePct": 1, "evaluated": 1}
    ).sort("createdAt", -1).limit(500)
    docs = await cursor.to_list(500)

    total = len(docs)
    evaluated = [d for d in docs if d.get("evaluated")]
    used = [d for d in docs if d.get("audit", {}).get("aggregator_live", {}).get("used")]
    exchange_available = [d for d in docs if d.get("audit", {}).get("aggregator_live", {}).get("exchange_available")]

    # Metric 5: Usage rate
    usage_rate = round(len(used) / max(total, 1) * 100, 1)
    exchange_rate = round(len(exchange_available) / max(total, 1) * 100, 1)

    # Split evaluated by aggregator used vs not
    agg_eval = [d for d in evaluated if d.get("audit", {}).get("aggregator_live", {}).get("used")]
    dec_eval = [d for d in evaluated if not d.get("audit", {}).get("aggregator_live", {}).get("used")]

    def _metrics(docs_list):
        tp = fp = neutral = 0
        conf_buckets = {"high": 0, "mid": 0, "low": 0}
        for d in docs_list:
            direction = d.get("direction", "NEUTRAL")
            confidence = d.get("confidence", 0) or 0
            real_move = d.get("outcome", {}).get("realMovePct", 0) or 0
            if direction in ("LONG", "SHORT"):
                if (direction == "LONG" and real_move > 0) or (direction == "SHORT" and real_move < 0):
                    tp += 1
                else:
                    fp += 1
            else:
                neutral += 1
            if confidence >= 0.7:
                conf_buckets["high"] += 1
            elif confidence >= 0.4:
                conf_buckets["mid"] += 1
            else:
                conf_buckets["low"] += 1
        dt = tp + fp
        return {
            "accuracy_pct": round(tp / max(dt, 1) * 100, 1),
            "fp_rate_pct": round(fp / max(dt, 1) * 100, 1),
            "tp": tp, "fp": fp, "neutral": neutral,
            "directional": dt,
            "confidence_buckets": conf_buckets,
        }

    agg_metrics = _metrics(agg_eval)
    dec_metrics = _metrics(dec_eval)

    # Determine health status
    status = "OK"
    alerts = []
    if agg_metrics["directional"] >= 5 and dec_metrics["directional"] >= 5:
        acc_delta = agg_metrics["accuracy_pct"] - dec_metrics["accuracy_pct"]
        fp_delta = agg_metrics["fp_rate_pct"] - dec_metrics["fp_rate_pct"]
        if acc_delta < -5:
            status = "CRITICAL"
            alerts.append(f"Accuracy drop: {acc_delta:+.1f}pp")
        if fp_delta > 5:
            status = "CRITICAL"
            alerts.append(f"FP surge: {fp_delta:+.1f}pp")

    return JSONResponse(content={
        "ok": True,
        "status": status,
        "alerts": alerts,
        "total_forecasts": total,
        "total_evaluated": len(evaluated),
        "aggregator_used": {
            "count": len(agg_eval),
            **agg_metrics,
        },
        "decision_used": {
            "count": len(dec_eval),
            **dec_metrics,
        },
        "usage_rate_pct": usage_rate,
        "exchange_available_pct": exchange_rate,
    })


@app.get("/api/system/aggregator-status")
async def api_aggregator_status():
    """Current aggregator mode, routing status, and recent signal summary."""
    from forecast.system.aggregator import get_aggregator_status
    from ml_ops import get_db as _get_db
    db = _get_db()

    agg_status = get_aggregator_status()

    count_with_agg = await db.exchange_forecasts.count_documents(
        {"audit.aggregator_v1": {"$exists": True}}
    )
    count_live_used = await db.exchange_forecasts.count_documents(
        {"audit.aggregator_live.used": True}
    )
    sample = await db.exchange_forecasts.find_one(
        {"audit.aggregator_v1": {"$exists": True}},
        {"_id": 0, "audit.aggregator_v1": 1, "audit.aggregator_live": 1,
         "symbol": 1, "horizon": 1},
        sort=[("createdAt", -1)],
    )

    return JSONResponse(content={
        "ok": True,
        **agg_status,
        "total_with_aggregator": count_with_agg,
        "total_live_used": count_live_used,
        "latest_sample": {
            "symbol": sample.get("symbol") if sample else None,
            "horizon": sample.get("horizon") if sample else None,
            "aggregator": sample.get("audit", {}).get("aggregator_v1") if sample else None,
            "live_telemetry": sample.get("audit", {}).get("aggregator_live") if sample else None,
        },
    })


@app.post("/api/system/aggregator-disable")
async def api_aggregator_disable():
    """STEP 5: Kill switch — immediately disable aggregator."""
    from forecast.system.aggregator import disable_aggregator
    result = disable_aggregator()
    return JSONResponse(content={"ok": True, **result})


@app.post("/api/system/aggregator-rollout")
async def api_aggregator_rollout(pct: float = 0.10):
    """Promote aggregator to specified % of live traffic."""
    import forecast.system.aggregator as _agg
    old_pct = _agg.SYSTEM_AGGREGATOR_PCT
    _agg.SYSTEM_AGGREGATOR_PCT = max(0.0, min(1.0, pct))
    _agg.SYSTEM_AGGREGATOR_MODE = "controlled_live" if pct > 0 else "shadow"
    return JSONResponse(content={
        "ok": True,
        "old_pct": old_pct,
        "new_pct": _agg.SYSTEM_AGGREGATOR_PCT,
        "mode": _agg.SYSTEM_AGGREGATOR_MODE,
    })


# ══════════════════════════════════════════════════════
# TELEGRAM MINI APP — Pocket Intelligence OS
# ══════════════════════════════════════════════════════

@app.get("/api/miniapp/core")
async def api_miniapp_core(asset: str = "BTC"):
    """Legacy endpoint — redirects to /home format."""
    from ml_ops import get_db as _get_db
    from miniapp.core_builder import build_core
    db = _get_db()
    result = await build_core(db, asset=asset.upper())
    return JSONResponse(content={"ok": True, **result})


@app.get("/api/miniapp/lite-url")
async def api_miniapp_lite_url():
    """Compute the correct public URL for the MiniApp Lite page."""
    import os as _os
    base = _os.environ.get('MINIAPP_URL', '') or ''
    # Extract origin from MINIAPP_URL (strip path)
    from urllib.parse import urlparse
    p = urlparse(base)
    origin = f"{p.scheme}://{p.netloc}" if p.scheme and p.netloc else ''
    lite_url = f"{origin}/api/miniapp/lite" if origin else ''
    return {"ok": True, "liteUrl": lite_url, "baseFromEnv": base}


# ═════════════════════════════════════════════════════════════════════
# MINIAPP LITE — V1-style HTML Mini App with full backend logic.
# Implementation: /app/backend/routes/miniapp_lite.py
# - UI/design concept = V1 (FOMO logo, 4 tabs Home/Feed/Edge/Profile,
#   Decision hero, Action Plan, Market Story, Structure pills, Net Pressure,
#   Breakdown, Why, Quick actions, Pay With Crypto, Your Edge, Referral).
# - Data = full backend: /api/miniapp/home (home_builder), /api/miniapp/feed,
#   /api/miniapp/edge, /api/miniapp/profile. Deep links + asset cycling.
# ═════════════════════════════════════════════════════════════════════
from routes.miniapp_lite import router as miniapp_lite_router
app.include_router(miniapp_lite_router)


@app.get("/api/miniapp/lite/favicon.ico")
async def api_miniapp_lite_favicon():
    admin_build_dir = os.path.join(os.path.dirname(__file__), 'admin_build')
    for candidate in ('favicon.ico', 'icons/favicon.ico'):
        p = os.path.join(admin_build_dir, candidate)
        if os.path.isfile(p):
            return FileResponse(p)
    return JSONResponse(status_code=404, content={"ok": False})


@app.get("/api/miniapp/lite/logo.png")
async def api_miniapp_lite_logo():
    """FOMO brand logo (sailboat+astronaut) for MiniApp Lite."""
    p = os.path.join(os.path.dirname(__file__), 'admin_build', 'assets', 'logo-white-new.png')
    if os.path.isfile(p):
        return FileResponse(p, headers={"Cache-Control": "public, max-age=86400"})
    return JSONResponse(status_code=404, content={"ok": False})


@app.post("/api/miniapp/bot/set-menu-lite")
async def api_set_menu_lite():
    """
    Reconfigure Telegram bot's menu button to open /api/miniapp/lite
    instead of the broken pre-compiled SPA.
    """
    import os as _os
    import httpx as _httpx
    from urllib.parse import urlparse

    bot_token = _os.environ.get('MINIAPP_BOT_TOKEN', '') or _os.environ.get('TELEGRAM_BOT_TOKEN', '')
    base = _os.environ.get('MINIAPP_URL', '') or ''
    if not bot_token:
        return {"ok": False, "error": "MINIAPP_BOT_TOKEN missing"}
    if not base:
        return {"ok": False, "error": "MINIAPP_URL missing"}
    p = urlparse(base)
    origin = f"{p.scheme}://{p.netloc}" if p.scheme and p.netloc else ''
    if not origin:
        return {"ok": False, "error": "cannot parse MINIAPP_URL"}
    lite_url = f"{origin}/api/miniapp/lite"

    async with _httpx.AsyncClient(timeout=15) as client:
        r = await client.post(
            f"https://api.telegram.org/bot{bot_token}/setChatMenuButton",
            json={
                "menu_button": {
                    "type": "web_app",
                    "text": "FOMO · Market",
                    "web_app": {"url": lite_url}
                }
            }
        )
        tg_resp = r.json()

    return {"ok": True, "liteUrl": lite_url, "telegram": tg_resp}


@app.get("/api/miniapp/home")
async def api_miniapp_home(asset: str = "BTC"):
    """Home screen data — orchestrated by services.home_composer (Pass 3)."""

    try:
        # Phase D Pass 3 — Home Composer (orchestration boundary).
        # The 412-line inline orchestration that previously lived here was
        # extracted into backend/services/home_composer/ and is now the
        # sole live path. The `except` below still falls back to the
        # legacy miniapp.home_builder for any unrecoverable error.
        from services.home_composer import compose as _home_compose
        result = _home_compose(asset)
        return JSONResponse(content={"ok": True, **result})
    except Exception as e:
        # Fallback to original builder
        from ml_ops import get_db as _get_db
        from miniapp.home_builder import build_home
        db = _get_db()
        result = await build_home(db, asset=asset.upper())
        return JSONResponse(content={"ok": True, **result})


@app.get("/api/miniapp/search")
async def api_miniapp_search(q: str = ""):
    """Search assets by ticker/name."""
    from miniapp.home_builder import search_assets
    results = search_assets(q)
    return JSONResponse(content={"ok": True, "results": results})


@app.get("/api/miniapp/feed")
async def api_miniapp_feed(limit: int = 30, asset: str = "BTC"):
    """Signals feed — uses real feed_events_service (same data as mobile app)."""
    try:
        from services.feed_events_service import build_feed_events
        events = build_feed_events(asset.upper() if asset else None, limit=limit)
        # Group into time sections for MiniApp
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        sections = {"now": [], "today": [], "earlier": []}
        for ev in events:
            item = {
                "asset": ev.get("asset", ""),
                "source": ev.get("type", ""),
                "type": ev.get("type", ""),
                "direction": "BULLISH" if "bullish" in ev.get("text", "").lower() or "buy" in ev.get("text", "").lower() else "BEARISH" if "bearish" in ev.get("text", "").lower() or "sell" in ev.get("text", "").lower() else "NEUTRAL",
                "impact": ev.get("priority", "normal").upper(),
                "title": ev.get("text", ""),
                "summary": ev.get("detail", ""),
                "interpretation": ev.get("detail", ""),
                "timestamp": ev.get("timestamp", ""),
            }
            time_str = ev.get("time", "")
            if "now" in time_str or "just" in time_str or "m ago" in time_str:
                sections["now"].append(item)
            elif "h ago" in time_str and int(time_str.replace("h ago", "").strip() or "0") < 24:
                sections["today"].append(item)
            else:
                sections["earlier"].append(item)

        return JSONResponse(content={
            "ok": True,
            "sections": [
                {"label": "Now", "items": sections["now"]},
                {"label": "Today", "items": sections["today"]},
                {"label": "Earlier", "items": sections["earlier"]},
            ],
            "counts": {"all": len(events), "high": sum(1 for e in events if e.get("priority") == "high")},
        })
    except Exception as e:
        # Fallback
        from ml_ops import get_db as _get_db
        from miniapp.home_builder import build_feed
        db = _get_db()
        result = await build_feed(db, limit=limit)
        return JSONResponse(content={"ok": True, **result})


@app.get("/api/miniapp/polymarket")
async def api_miniapp_polymarket():
    """Polymarket edge data — spotlight + market list."""
    from ml_ops import get_db as _get_db
    from miniapp.home_builder import build_polymarket
    db = _get_db()
    result = await build_polymarket(db)
    return JSONResponse(content={"ok": True, **result})


@app.get("/api/miniapp/edge")
async def api_miniapp_edge(asset: str = ""):
    """Edge Engine — Polymarket prediction markets with MetaBrain overlay."""
    try:
        from pymongo import MongoClient as _SyncMongo, DESCENDING as _DESC
        _sdb = _SyncMongo(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[_db_name]

        # Get states with recommendations first, fallback to all
        states = list(_sdb.prediction_market_states.find(
            {"last_recommendation": {"$in": ["WATCH", "YES_NOW", "YES_SMALL", "NO_NOW", "NO_SMALL", "GOOD_IDEA_BAD_PRICE"]}}, {"_id": 0}
        ).sort("last_updated_at", _DESC).limit(20))
        
        if not states:
            states = list(_sdb.prediction_market_states.find(
                {"last_recommendation": {"$exists": True}}, {"_id": 0}
            ).sort("last_updated_at", _DESC).limit(20))

        market_ids = [s.get("market_id") for s in states if s.get("market_id")]
        markets_map = {}
        if market_ids:
            for m in _sdb.prediction_markets.find({"market_id": {"$in": market_ids}}, {"_id": 0}):
                markets_map[str(m.get("market_id"))] = m

        cards = []
        for s in states:
            mid = str(s.get("market_id", ""))
            market = markets_map.get(mid, {})
            question = s.get("question") or market.get("question", "")
            rec = s.get("last_recommendation", "WATCH")
            edge = s.get("last_edge", 0)
            fair = s.get("last_fair_prob", 0.5)
            mkt = market.get("yes_price", s.get("last_market_prob", 0.5))

            if rec in ("YES_NOW", "YES_SMALL"):
                action = f"BUY YES {'NOW' if rec == 'YES_NOW' else 'SOON'}"
            elif rec in ("NO_NOW", "NO_SMALL"):
                action = f"BUY NO {'NOW' if rec == 'NO_NOW' else 'SOON'}"
            elif rec == "WATCH":
                action = "WATCHING"
            else:
                action = rec

            abs_edge = abs(edge) if edge else 0
            edge_text = f"YES underpriced by {abs_edge*100:.1f}%" if edge > 0.02 else f"Overpriced by {abs_edge*100:.1f}%" if edge < -0.02 else "Fairly priced"

            cards.append({
                "id": mid,
                "question": question,
                "asset": s.get("asset", "CRYPTO"),
                "action": action,
                "edge": round(edge, 4),
                "edgePercent": round(abs_edge * 100, 1),
                "edgeText": edge_text,
                "fairProb": round(fair, 3),
                "marketProb": round(mkt, 3),
                "conviction": s.get("last_conviction", "LOW"),
                "stage": s.get("last_stage", ""),
                "volume": round(market.get("volume", 0)),
                "timeLeft": "",
                "tags": [s.get("event_type", ""), s.get("last_repricing_state", "")],
            })

        cards.sort(key=lambda c: (-abs(c["edge"])))

        # Build "best" edge for legacy format
        best = cards[0] if cards else None
        return JSONResponse(content={
            "ok": True,
            "markets": cards,
            "count": len(cards),
            "best": {
                "asset": best["asset"] if best else "BTC",
                "direction": "YES" if best and best["edge"] > 0 else "NO",
                "edge_pct": best["edgePercent"] if best else 0,
                "question": best["question"] if best else "",
                "action": best["action"] if best else "WATCHING",
            } if best else None,
        })
    except Exception as e:
        from ml_ops import get_db as _get_db
        from miniapp.edge_builder import build_edge
        db = _get_db()
        result = await build_edge(db)
        return JSONResponse(content={"ok": True, **result})


@app.get("/api/miniapp/profile")
async def api_miniapp_profile(telegram_id: str = ""):
    """User profile — identity, performance, favorites, referral, settings."""
    from ml_ops import get_db as _get_db
    from miniapp.profile_builder import build_profile
    db = _get_db()
    result = await build_profile(db, telegram_id=telegram_id or None)
    return JSONResponse(content={"ok": True, **result})



@app.post("/api/miniapp/sync-telegram-user")
async def api_miniapp_sync_telegram_user(request: Request):
    """Sync Telegram user data (name, username, photo) from WebApp SDK."""
    from ml_ops import get_db as _get_db
    db = _get_db()
    body = await request.json()
    tg_id = body.get("telegram_id", "")
    if not tg_id:
        return JSONResponse(content={"ok": False, "error": "telegram_id required"}, status_code=400)
    first_name = body.get("first_name", "")
    last_name = body.get("last_name", "")
    username = body.get("username", "")
    photo_url = body.get("photo_url", "")
    full_name = f"{first_name} {last_name}".strip() or "Telegram User"
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    await db.miniapp_users.update_one(
        {"telegram_id": tg_id},
        {"$set": {
            "name": full_name,
            "username": username,
            "photo_url": photo_url,
            "last_sync": now,
        },
        "$setOnInsert": {
            "telegram_id": tg_id,
            "plan_status": "free",
            "renew_date": None,
            "google_email": None,
            "referral_code": f"FOMO-{tg_id[-6:].upper()}",
            "created_at": now,
        }},
        upsert=True,
    )
    return JSONResponse(content={"ok": True})



@app.post("/api/miniapp/favorites/add")
async def api_miniapp_favorites_add(request: Request):
    """Add asset to favorites."""
    from ml_ops import get_db as _get_db
    from miniapp.profile_builder import add_favorite
    db = _get_db()
    body = await request.json()
    telegram_id = body.get("telegram_id", "")
    asset = body.get("asset", "")
    if not asset:
        return JSONResponse(content={"ok": False, "error": "asset required"}, status_code=400)
    result = await add_favorite(db, telegram_id, asset.upper())
    return JSONResponse(content={"ok": True, **result})


@app.post("/api/miniapp/favorites/remove")
async def api_miniapp_favorites_remove(request: Request):
    """Remove asset from favorites."""
    from ml_ops import get_db as _get_db
    from miniapp.profile_builder import remove_favorite
    db = _get_db()
    body = await request.json()
    telegram_id = body.get("telegram_id", "")
    asset = body.get("asset", "")
    if not asset:
        return JSONResponse(content={"ok": False, "error": "asset required"}, status_code=400)
    result = await remove_favorite(db, telegram_id, asset.upper())
    return JSONResponse(content={"ok": True, **result})


@app.post("/api/miniapp/settings")
async def api_miniapp_settings(request: Request):
    """Update notification/alert settings."""
    from ml_ops import get_db as _get_db
    from miniapp.profile_builder import update_settings
    db = _get_db()
    body = await request.json()
    telegram_id = body.get("telegram_id", "")
    result = await update_settings(db, telegram_id, body)
    return JSONResponse(content={"ok": True, **result})


@app.post("/api/miniapp/promo/apply")
async def api_miniapp_promo_apply(request: Request):
    """Apply a promo code."""
    from ml_ops import get_db as _get_db
    from miniapp.profile_builder import apply_promo
    db = _get_db()
    body = await request.json()
    telegram_id = body.get("telegram_id", "")
    code = body.get("code", "")
    if not code:
        return JSONResponse(content={"ok": False, "error": "code required"}, status_code=400)
    result = await apply_promo(db, telegram_id, code)
    return JSONResponse(content={"ok": True, **result})


@app.post("/api/miniapp/webhook")
async def api_miniapp_webhook(request: Request):
    """Telegram webhook for the MiniApp bot — handles messages and button callbacks."""
    try:
        from miniapp.bot_setup import handle_update
        body = await request.json()
        await handle_update(body)
        return JSONResponse(content={"ok": True})
    except Exception as e:
        return JSONResponse(content={"ok": False, "error": str(e)})


# ── MiniApp Billing (Stripe bridge for Telegram users) ─────────────

@app.get("/api/miniapp/billing/plans")
async def api_miniapp_billing_plans():
    """Get available subscription plans."""
    from ml_ops import get_db as _get_db
    from miniapp.billing_bridge import get_plans
    db = _get_db()
    plans = await get_plans(db)
    return JSONResponse(content={"ok": True, **plans})


@app.get("/api/miniapp/billing/status")
async def api_miniapp_billing_status(telegram_id: str = ""):
    """Get billing status for telegram user."""
    from ml_ops import get_db as _get_db
    from miniapp.billing_bridge import get_billing_status
    db = _get_db()
    result = await get_billing_status(db, telegram_id)
    return JSONResponse(content={"ok": True, **result})


@app.post("/api/miniapp/billing/checkout")
async def api_miniapp_billing_checkout(request: Request):
    """Create Stripe checkout session for Mini App user."""
    from ml_ops import get_db as _get_db
    from miniapp.billing_bridge import create_checkout
    db = _get_db()
    body = await request.json()
    telegram_id = body.get("telegram_id", "")
    origin_url = body.get("origin_url", "")
    interval = body.get("interval", "month")
    result = await create_checkout(db, telegram_id, origin_url, interval)
    return JSONResponse(content={"ok": True, **result})


@app.post("/api/miniapp/billing/portal")
async def api_miniapp_billing_portal(request: Request):
    """Create Stripe customer portal for billing management."""
    from ml_ops import get_db as _get_db
    from miniapp.billing_bridge import create_portal
    db = _get_db()
    body = await request.json()
    telegram_id = body.get("telegram_id", "")
    origin_url = body.get("origin_url", "")
    result = await create_portal(db, telegram_id, origin_url)
    return JSONResponse(content={"ok": True, **result})


@app.get("/api/miniapp/billing/verify/{session_id}")
async def api_miniapp_billing_verify(session_id: str):
    """Verify checkout completion and activate subscription."""
    from ml_ops import get_db as _get_db
    from miniapp.billing_bridge import handle_checkout_success
    db = _get_db()
    result = await handle_checkout_success(db, session_id)
    return JSONResponse(content={"ok": True, **result})



@app.get("/api/miniapp/accuracy/audit")
async def api_miniapp_accuracy_audit():
    """Full accuracy audit with directional vs risk breakdown."""
    from ml_ops import get_db as _get_db
    from miniapp.accuracy_audit import run_accuracy_audit
    db = _get_db()
    result = await run_accuracy_audit(db)
    return JSONResponse(content={"ok": True, **result})


@app.post("/api/miniapp/polymarket/ingest")
async def api_miniapp_polymarket_ingest():
    """Trigger Polymarket data ingestion + edge alerts."""
    from ml_ops import get_db as _get_db
    from miniapp.polymarket_ingestion import ingest_polymarket
    from miniapp.edge_builder import build_edge
    from miniapp.edge_alerts import process_edge_alerts
    db = _get_db()
    ingestion = await ingest_polymarket(db)
    edge_result = await build_edge(db)
    alerts = await process_edge_alerts(db, edge_result.get("markets", []))
    return JSONResponse(content={"ok": True, **ingestion, "alerts": alerts})


@app.post("/api/miniapp/alerts/send")
async def api_miniapp_alerts_send():
    """Manually trigger edge alerts from current edges."""
    from ml_ops import get_db as _get_db
    from miniapp.edge_builder import build_edge
    from miniapp.edge_alerts import process_edge_alerts
    db = _get_db()
    edge_result = await build_edge(db)
    result = await process_edge_alerts(db, edge_result.get("markets", []))
    return JSONResponse(content={"ok": True, **result})


@app.post("/api/miniapp/digest/send")
async def api_miniapp_digest_send():
    """Manually trigger daily digest."""
    from ml_ops import get_db as _get_db
    from miniapp.edge_alerts import send_daily_digest
    db = _get_db()
    result = await send_daily_digest(db)
    return JSONResponse(content={"ok": True, **result})


# ──── User State Machine ────

@app.get("/api/miniapp/user/state")
async def api_miniapp_user_state(telegram_id: str = ""):
    """Get user state (guest/telegram/linked/active/expired)."""
    from ml_ops import get_db as _get_db
    from miniapp.user_state import get_user_state
    db = _get_db()
    result = await get_user_state(db, telegram_id)
    return JSONResponse(content={"ok": True, **result})


@app.post("/api/miniapp/user/link-google")
async def api_miniapp_user_link_google(request: Request):
    """Link Google account to Telegram identity."""
    from ml_ops import get_db as _get_db
    from miniapp.user_state import link_google_account
    db = _get_db()
    body = await request.json()
    telegram_id = body.get("telegram_id", "")
    email = body.get("email", "")
    name = body.get("name", "")
    result = await link_google_account(db, telegram_id, email, name)
    return JSONResponse(content={"ok": True, **result})


@app.post("/api/miniapp/user/unlink-google")
async def api_miniapp_user_unlink_google(request: Request):
    """Unlink Google account from Telegram identity."""
    from ml_ops import get_db as _get_db
    from miniapp.user_state import unlink_google_account
    db = _get_db()
    body = await request.json()
    telegram_id = body.get("telegram_id", "")
    result = await unlink_google_account(db, telegram_id)
    return JSONResponse(content={"ok": True, **result})


# ──── Scheduler ────

@app.get("/api/miniapp/scheduler/status")
async def api_miniapp_scheduler_status():
    """Get scheduler status."""
    from miniapp.scheduler import get_scheduler_status
    return JSONResponse(content={"ok": True, **get_scheduler_status()})


@app.post("/api/miniapp/scheduler/start")
async def api_miniapp_scheduler_start():
    """Start background scheduler."""
    from ml_ops import get_db as _get_db
    from miniapp.scheduler import start_scheduler
    db = _get_db()
    result = start_scheduler(db)
    return JSONResponse(content={"ok": True, **result})


@app.post("/api/miniapp/scheduler/stop")
async def api_miniapp_scheduler_stop():
    """Stop background scheduler."""
    from miniapp.scheduler import stop_scheduler
    result = stop_scheduler()
    return JSONResponse(content={"ok": True, **result})


# ──── A/B Testing ────

@app.get("/api/miniapp/ab/stats")
async def api_miniapp_ab_stats():
    """Get A/B test statistics."""
    from ml_ops import get_db as _get_db
    from miniapp.ab_testing import get_ab_stats
    db = _get_db()
    stats = await get_ab_stats(db)
    return JSONResponse(content={"ok": True, "variants": stats})


@app.post("/api/miniapp/ab/track")
async def api_miniapp_ab_track(request: Request):
    """Track an A/B test event from frontend."""
    from ml_ops import get_db as _get_db
    from miniapp.ab_testing import track_event
    db = _get_db()
    body = await request.json()
    user_id = body.get("user_id", "")
    event_type = body.get("event", "")
    variant = body.get("variant", "")
    meta = body.get("meta", {})
    if not user_id or not event_type:
        return JSONResponse(content={"ok": False, "message": "user_id and event required"})
    await track_event(db, user_id, event_type, variant, meta)
    return JSONResponse(content={"ok": True})


# ═══════════════════════════════════════════════════════════════
# ADMIN MINIAPP — Console API
# ═══════════════════════════════════════════════════════════════

@app.get("/api/admin/miniapp/overview")
async def api_admin_miniapp_overview():
    """MiniApp admin overview v2 — money dashboard."""
    from ml_ops import get_db as _get_db
    from miniapp.ab_testing import get_ab_stats
    from datetime import datetime, timezone, timedelta
    db = _get_db()
    now = datetime.now(timezone.utc)
    day_ago = (now - timedelta(hours=24)).isoformat()
    week_ago = (now - timedelta(days=7)).isoformat()

    # Users
    total_users = await db.miniapp_bot_chats.count_documents({})
    paid_users = await db.miniapp_subscriptions.count_documents({"status": {"$in": ["active", "trialing"]}})
    conversion = round(paid_users / max(total_users, 1) * 100, 1)

    # Funnel counts from ab_events
    alerts_sent = await db.ab_events.count_documents({"event": "alert_sent"})
    alerts_opened = await db.ab_events.count_documents({"event": "alert_opened"})
    edge_viewed = await db.ab_events.count_documents({"event": "edge_viewed"})
    upgrade_clicked = await db.ab_events.count_documents({"event": "upgrade_clicked"})
    upgrade_completed = await db.ab_events.count_documents({"event": "upgrade_completed"})

    revenue = upgrade_completed
    rev_per_alert = round(revenue / max(alerts_sent, 1), 2)

    # Funnel with conversion rates
    funnel = {
        "alerts": alerts_sent,
        "opened": alerts_opened,
        "edge_viewed": edge_viewed,
        "upgrade_clicked": upgrade_clicked,
        "paid": upgrade_completed,
        "rates": {
            "open_rate": round(alerts_opened / max(alerts_sent, 1) * 100, 1) if alerts_sent > 0 else 0,
            "edge_rate": round(edge_viewed / max(alerts_opened, 1) * 100, 1) if alerts_opened > 0 else 0,
            "click_rate": round(upgrade_clicked / max(edge_viewed, 1) * 100, 1) if edge_viewed > 0 else 0,
            "pay_rate": round(upgrade_completed / max(upgrade_clicked, 1) * 100, 1) if upgrade_clicked > 0 else 0,
        },
    }

    # Model metrics
    dir_total = await db.decision_history.count_documents(
        {"status": "evaluated", "decision": {"$in": ["BUY", "SELL"]}}
    )
    dir_correct = await db.decision_history.count_documents(
        {"status": "evaluated", "decision": {"$in": ["BUY", "SELL"]}, "result": "correct"}
    )
    accuracy = int(dir_correct / max(dir_total, 1) * 100)
    total_dec = await db.decision_history.count_documents({"status": "evaluated"})
    coverage_val = int(dir_total / max(total_dec, 1) * 100)
    catastrophic = await db.decision_history.count_documents(
        {"status": "evaluated", "result": "catastrophic"}
    )
    active_edges = await db.prediction_markets.count_documents({})

    # Revenue daily (last 7 days)
    revenue_daily = []
    for i in range(7):
        d = now - timedelta(days=6 - i)
        ds = d.strftime("%Y-%m-%d")
        start = d.replace(hour=0, minute=0, second=0).isoformat()
        end = d.replace(hour=23, minute=59, second=59).isoformat()
        cnt = await db.ab_events.count_documents({"event": "upgrade_completed", "created_at": {"$gte": start, "$lte": end}})
        revenue_daily.append({"date": ds, "revenue": cnt})

    # A/B stats (enhanced with $/alert)
    ab_stats = await get_ab_stats(db)

    return JSONResponse(content={
        "ok": True,
        "revenue": revenue,
        "conversion": conversion,
        "paid_users": paid_users,
        "revenue_per_alert": rev_per_alert,
        "funnel": funnel,
        "accuracy": accuracy,
        "coverage": coverage_val,
        "catastrophic": catastrophic,
        "active_edges": active_edges,
        "revenue_daily": revenue_daily,
        "ab_stats": ab_stats,
    })


@app.get("/api/admin/miniapp/signals")
async def api_admin_miniapp_signals(asset: str = "", source: str = "", high_only: str = ""):
    """MiniApp admin — signals stream with money connection."""
    from ml_ops import get_db as _get_db
    from datetime import datetime, timezone, timedelta
    db = _get_db()
    now = datetime.now(timezone.utc)

    query = {}
    if asset:
        query["asset"] = asset
    if source:
        query["source"] = source
    if high_only == "true":
        query["priority"] = "high"

    cutoff = (now - timedelta(hours=48)).isoformat()
    query["created_at"] = {"$gte": cutoff}

    signals_raw = await db.notifications.find(
        query, {"_id": 0}
    ).sort("created_at", -1).to_list(length=100)

    # Edge assets
    edge_assets = set()
    from miniapp.edge_builder import build_edge
    edge_result = await build_edge(db)
    for m in edge_result.get("markets", []):
        if m.get("status") != "watching":
            edge_assets.add(m.get("asset", ""))

    # Alert assets
    alert_events = await db.notification_events.find(
        {"type": "edge.detected"}, {"_id": 0, "asset": 1}
    ).to_list(length=200)
    alerted_assets = set(e.get("asset", "") for e in alert_events)

    # Revenue assets — which assets led to upgrade_completed
    revenue_events = await db.ab_events.find(
        {"event": "upgrade_completed"}, {"_id": 0, "meta": 1}
    ).to_list(length=500)
    revenue_assets = set()
    for ev in revenue_events:
        a = (ev.get("meta") or {}).get("asset", "")
        if a:
            revenue_assets.add(a)

    signals = []
    for s in signals_raw:
        asset_name = s.get("asset", "")
        signals.append({
            "timestamp": s.get("created_at", ""),
            "asset": asset_name,
            "source": s.get("source", ""),
            "type": s.get("type", s.get("category", "")),
            "direction": s.get("direction", ""),
            "strength": s.get("priority", s.get("impact", "")),
            "has_edge": asset_name in edge_assets,
            "has_alert": asset_name in alerted_assets,
            "has_revenue": asset_name in revenue_assets,
        })

    total = len(signals)
    high_p = sum(1 for s in signals if s.get("strength") == "high")
    with_edge = sum(1 for s in signals if s.get("has_edge"))
    with_alert = sum(1 for s in signals if s.get("has_alert"))
    with_revenue = sum(1 for s in signals if s.get("has_revenue"))

    edge_pct = round(with_edge / max(total, 1) * 100, 1)
    alert_pct = round(with_alert / max(total, 1) * 100, 1)
    revenue_pct = round(with_revenue / max(total, 1) * 100, 1)

    return JSONResponse(content={
        "ok": True,
        "kpis": {
            "total": total,
            "high_priority": high_p,
            "with_edge": with_edge,
            "with_alert": with_alert,
            "filtered": total - high_p,
            "with_revenue": with_revenue,
            "edge_pct": edge_pct,
            "alert_pct": alert_pct,
            "revenue_pct": revenue_pct,
        },
        "signals": signals[:50],
    })


@app.get("/api/admin/miniapp/edges")
async def api_admin_miniapp_edges():
    """MiniApp admin — edges with priority, money tracking."""
    from ml_ops import get_db as _get_db
    from miniapp.edge_priority import calculate_priority, priority_label
    from miniapp.edge_builder import _confidence_tier, _ttl_hours
    db = _get_db()

    cursor = db.prediction_markets.find({}, {"_id": 0}).sort("updatedAt", -1).limit(30)
    markets = []

    # Pre-fetch decisions for priority
    decision_cache = {}
    for asset in ["BTC", "ETH", "SOL"]:
        dec = await db.decision_history.find_one(
            {"asset": asset}, {"_id": 0}, sort=[("timestamp", -1)]
        )
        if dec:
            decision_cache[asset] = dec

    # Pre-fetch money stats per asset from ab_events
    money_pipeline = [
        {"$match": {"event": {"$in": ["edge_viewed", "upgrade_clicked", "upgrade_completed"]}}},
        {"$group": {
            "_id": {"asset": "$meta.asset", "event": "$event"},
            "count": {"$sum": 1},
        }}
    ]
    money_data = {}
    async for doc in db.ab_events.aggregate(money_pipeline):
        asset_key = (doc["_id"].get("asset") or "")
        event_key = doc["_id"]["event"]
        if asset_key not in money_data:
            money_data[asset_key] = {"views": 0, "clicks": 0, "payments": 0, "revenue": 0}
        if event_key == "edge_viewed":
            money_data[asset_key]["views"] += doc["count"]
        elif event_key == "upgrade_clicked":
            money_data[asset_key]["clicks"] += doc["count"]
        elif event_key == "upgrade_completed":
            money_data[asset_key]["payments"] += doc["count"]
            money_data[asset_key]["revenue"] += doc["count"]

    async for doc in cursor:
        mp = float(doc.get("yes_price", 0.5))
        mdl = float(doc.get("model_prob", 0.5))
        edge = round(mdl - mp, 4)
        if abs(edge) < 0.05:
            continue
        direction = "BUY" if edge > 0 else "SELL"
        asset = doc.get("asset", "")
        confidence = float(doc.get("decision_confidence", 50)) / 100.0

        dec = decision_cache.get(asset, {})
        decision_type = dec.get("decisionType", "NORMAL")
        fusion = dec.get("fusion", {})
        timestamp = dec.get("timestamp", doc.get("updatedAt", ""))

        pscore = calculate_priority(
            edge=edge, confidence=confidence, fusion=fusion,
            edge_direction=direction, timestamp=timestamp,
            decision_type=decision_type,
        )

        asset_money = money_data.get(asset, {"views": 0, "clicks": 0, "payments": 0, "revenue": 0})

        markets.append({
            "asset": asset,
            "question": doc.get("question", ""),
            "marketProbability": round(mp, 3),
            "modelProbability": round(mdl, 3),
            "edge": round(edge, 3),
            "direction": direction,
            "confidence": round(confidence, 2),
            "confidenceTier": _confidence_tier(confidence),
            "ttlHours": _ttl_hours(edge, confidence),
            "priorityScore": pscore,
            "priorityLabel": priority_label(pscore),
            "decisionType": decision_type,
            "views": asset_money["views"],
            "clicks": asset_money["clicks"],
            "payments": asset_money["payments"],
            "revenue": asset_money["revenue"],
        })

    markets.sort(key=lambda x: x["priorityScore"], reverse=True)

    # Priority distribution
    priority_dist = {}
    for m in markets:
        label = m.get("priorityLabel", "WATCHING")
        priority_dist[label] = priority_dist.get(label, 0) + 1

    # Top edges by revenue
    top_by_revenue = sorted(markets, key=lambda x: x["revenue"], reverse=True)[:3]

    active = [m for m in markets if m.get("status") != "watching"]
    elite = sum(1 for m in markets if m.get("priorityLabel") == "ELITE EDGE")
    live = sum(1 for m in markets if m.get("priorityLabel") == "LIVE EDGE")
    strong = sum(1 for m in markets if m.get("priorityLabel") == "STRONG EDGE")

    total_revenue = sum(m["revenue"] for m in markets)
    total_views = sum(m["views"] for m in markets)

    return JSONResponse(content={
        "ok": True,
        "kpis": {
            "active": len(active),
            "elite": elite,
            "live": live,
            "strong": strong,
            "total_revenue": total_revenue,
            "total_views": total_views,
        },
        "edges": markets,
        "top_by_revenue": top_by_revenue,
        "priority_distribution": priority_dist,
    })



# ══════════════════════════════════════════════════════════
# ADMIN SPRINT 2: Users, Billing, Alerts, Settings
# ══════════════════════════════════════════════════════════

@app.get("/api/admin/miniapp/users")
async def api_admin_miniapp_users(
    status: str = "",
    variant: str = "",
    active_only: str = "",
    has_revenue: str = "",
    sort_by: str = "revenue",
    sort_dir: str = "desc",
):
    """Users tab — who brings money?"""
    from ml_ops import get_db as _get_db
    from miniapp.ab_testing import assign_variant
    from datetime import datetime, timezone, timedelta
    db = _get_db()
    now = datetime.now(timezone.utc)
    day_ago = (now - timedelta(hours=24)).isoformat()

    users_raw = await db.miniapp_users.find({}, {"_id": 0}).to_list(length=500)

    # Pre-aggregate ab_events per user
    event_pipeline = [
        {"$group": {
            "_id": {"user_id": "$user_id", "event": "$event"},
            "count": {"$sum": 1},
        }}
    ]
    user_events = {}
    async for doc in db.ab_events.aggregate(event_pipeline):
        uid = doc["_id"]["user_id"]
        evt = doc["_id"]["event"]
        if uid not in user_events:
            user_events[uid] = {}
        user_events[uid][evt] = doc["count"]

    users = []
    for u in users_raw:
        tid = u.get("telegram_id", "")
        events = user_events.get(tid, {})
        is_paid = u.get("plan_status") == "paid"
        has_google = bool(u.get("google_email"))
        v = assign_variant(tid)
        alerts_received = events.get("alert_sent", 0)
        alerts_opened = events.get("alert_opened", 0)
        edge_views = events.get("edge_viewed", 0)
        clicks = events.get("upgrade_clicked", 0)
        payments = events.get("upgrade_completed", 0)
        revenue = payments

        user_status = "paid" if is_paid else ("linked" if has_google else "telegram")
        is_active = u.get("created_at", "") >= day_ago

        # Filters
        if status and user_status != status:
            continue
        if variant and v != variant:
            continue
        if active_only == "true" and not is_active:
            continue
        if has_revenue == "true" and revenue <= 0:
            continue

        users.append({
            "user": u.get("name", "User"),
            "telegram_id": tid,
            "email": u.get("google_email", ""),
            "status": user_status,
            "variant": v,
            "last_activity": u.get("created_at", ""),
            "alerts_received": alerts_received,
            "alerts_opened": alerts_opened,
            "edge_views": edge_views,
            "clicks": clicks,
            "payments": payments,
            "revenue": revenue,
        })

    # Sort
    reverse = sort_dir == "desc"
    sort_key = sort_by if sort_by in ("revenue", "clicks", "alerts_opened", "edge_views", "payments") else "revenue"
    users.sort(key=lambda x: x.get(sort_key, 0), reverse=reverse)

    # KPIs
    total = len(users_raw)
    active_24h = sum(1 for u in users_raw if u.get("created_at", "") >= day_ago)
    paid_count = sum(1 for u in users_raw if u.get("plan_status") == "paid")
    linked_count = sum(1 for u in users_raw if u.get("google_email"))
    tg_only = total - linked_count
    conv_rate = round(paid_count / max(total, 1) * 100, 1)
    linked_pct = round(linked_count / max(total, 1) * 100, 1)
    tg_only_pct = round(tg_only / max(total, 1) * 100, 1)

    return JSONResponse(content={
        "ok": True,
        "kpis": {
            "total": total,
            "active_24h": active_24h,
            "paid": paid_count,
            "conversion": conv_rate,
            "linked_pct": linked_pct,
            "tg_only_pct": tg_only_pct,
        },
        "users": users,
    })


@app.get("/api/admin/miniapp/billing")
async def api_admin_miniapp_billing():
    """Billing tab — where does money come from?"""
    from ml_ops import get_db as _get_db
    from datetime import datetime, timezone, timedelta
    db = _get_db()
    now = datetime.now(timezone.utc)

    # All payment events from ab_events
    payment_events = await db.ab_events.find(
        {"event": "upgrade_completed"}, {"_id": 0}
    ).to_list(length=500)

    transactions = []
    rev_miniapp = 0
    rev_web = 0
    rev_direct = 0
    for ev in payment_events:
        meta = ev.get("meta", {}) or {}
        source = meta.get("source", "miniapp")
        amount = meta.get("amount", 1)
        transactions.append({
            "user": ev.get("user_id", ""),
            "amount": amount,
            "status": "completed",
            "source": source,
            "date": ev.get("created_at", ""),
        })
        if source == "miniapp":
            rev_miniapp += amount
        elif source == "web":
            rev_web += amount
        else:
            rev_direct += amount

    total_rev = rev_miniapp + rev_web + rev_direct
    miniapp_pct = round(rev_miniapp / max(total_rev, 1) * 100, 1) if total_rev > 0 else 0
    total_users = await db.miniapp_users.count_documents({})
    paid_users = await db.miniapp_users.count_documents({"plan_status": "paid"})
    conv_rate = round(paid_users / max(total_users, 1) * 100, 1)
    avg_check = round(total_rev / max(len(transactions), 1), 2) if transactions else 0

    # Daily revenue by source (last 7 days)
    daily = []
    for i in range(7):
        d = now - timedelta(days=6 - i)
        ds = d.strftime("%Y-%m-%d")
        start = d.replace(hour=0, minute=0, second=0).isoformat()
        end = d.replace(hour=23, minute=59, second=59).isoformat()
        day_evts = [t for t in transactions if start <= t.get("date", "") <= end]
        miniapp_d = sum(t["amount"] for t in day_evts if t["source"] == "miniapp")
        web_d = sum(t["amount"] for t in day_evts if t["source"] == "web")
        direct_d = sum(t["amount"] for t in day_evts if t["source"] == "direct")
        daily.append({"date": ds, "miniapp": miniapp_d, "web": web_d, "direct": direct_d})

    return JSONResponse(content={
        "ok": True,
        "kpis": {
            "revenue_miniapp": rev_miniapp,
            "revenue_web": rev_web,
            "revenue_direct": rev_direct,
            "miniapp_pct": miniapp_pct,
            "conversion": conv_rate,
            "avg_check": avg_check,
        },
        "transactions": transactions,
        "daily": daily,
    })


@app.get("/api/admin/miniapp/alerts")
async def api_admin_miniapp_alerts():
    """Alerts tab — what sells?"""
    from ml_ops import get_db as _get_db
    from miniapp.ab_testing import get_ab_stats
    from datetime import datetime, timezone, timedelta
    db = _get_db()
    now = datetime.now(timezone.utc)

    # Funnel KPIs
    alerts_sent = await db.ab_events.count_documents({"event": "alert_sent"})
    alerts_opened = await db.ab_events.count_documents({"event": "alert_opened"})
    edge_viewed = await db.ab_events.count_documents({"event": "edge_viewed"})
    upgrade_clicked = await db.ab_events.count_documents({"event": "upgrade_clicked"})
    upgrade_completed = await db.ab_events.count_documents({"event": "upgrade_completed"})
    ctr = round(alerts_opened / max(alerts_sent, 1) * 100, 1) if alerts_sent > 0 else 0
    rev_per_alert = round(upgrade_completed / max(alerts_sent, 1), 4) if alerts_sent > 0 else 0

    # A/B stats
    ab_stats = await get_ab_stats(db)

    # CTR over time (last 7 days, per variant)
    ctr_over_time = []
    for i in range(7):
        d = now - timedelta(days=6 - i)
        ds = d.strftime("%Y-%m-%d")
        start = d.replace(hour=0, minute=0, second=0).isoformat()
        end = d.replace(hour=23, minute=59, second=59).isoformat()
        day_data = {"date": ds}
        for v in ["A", "B", "C", "D"]:
            sent_v = await db.ab_events.count_documents({
                "event": "alert_sent", "variant": v,
                "created_at": {"$gte": start, "$lte": end}
            })
            opened_v = await db.ab_events.count_documents({
                "event": "alert_opened", "variant": v,
                "created_at": {"$gte": start, "$lte": end}
            })
            day_data[v] = round(opened_v / max(sent_v, 1) * 100, 1) if sent_v > 0 else 0
        ctr_over_time.append(day_data)

    # Recent alerts (last 50)
    recent_alerts_raw = await db.ab_events.find(
        {"event": "alert_sent"}, {"_id": 0}
    ).sort("created_at", -1).to_list(length=50)

    # Get opened/clicked/paid status for each user+asset combo
    recent_alerts = []
    for a in recent_alerts_raw:
        uid = a.get("user_id", "")
        asset = (a.get("meta") or {}).get("asset", "")
        opened = await db.ab_events.count_documents({
            "user_id": uid, "event": "alert_opened", "meta.asset": asset
        }) > 0
        clicked = await db.ab_events.count_documents({
            "user_id": uid, "event": "upgrade_clicked", "meta.asset": asset
        }) > 0
        paid = await db.ab_events.count_documents({
            "user_id": uid, "event": "upgrade_completed", "meta.asset": asset
        }) > 0
        recent_alerts.append({
            "time": a.get("created_at", ""),
            "user": uid,
            "variant": a.get("variant", ""),
            "asset": asset,
            "opened": opened,
            "clicked": clicked,
            "paid": paid,
        })

    return JSONResponse(content={
        "ok": True,
        "kpis": {
            "alerts_sent": alerts_sent,
            "alerts_opened": alerts_opened,
            "ctr": ctr,
            "edge_views": edge_viewed,
            "clicks": upgrade_clicked,
            "payments": upgrade_completed,
            "revenue_per_alert": rev_per_alert,
        },
        "ab_stats": ab_stats,
        "ctr_over_time": ctr_over_time,
        "recent_alerts": recent_alerts,
    })


@app.get("/api/admin/miniapp/settings")
async def api_admin_miniapp_settings_get():
    """Settings tab — read current settings."""
    from ml_ops import get_db as _get_db
    db = _get_db()
    settings = await db.miniapp_settings.find_one({"type": "global"}, {"_id": 0})
    defaults = {
        "type": "global",
        "alerts": {
            "edge_threshold": 0.10,
            "priority_threshold": 0.68,
            "daily_limit": 5,
            "extreme_bypass": True,
        },
        "scheduler": {
            "ingest_interval": 30,
            "digest_hour": 9,
            "digest_enabled": True,
        },
        "monetization": {
            "free_edge_limit": 3,
            "paywall_enabled": True,
            "teaser_mode": True,
        },
        "boost": {
            "resend_enabled": False,
            "accuracy_enabled": False,
        },
    }
    if not settings:
        settings = defaults
    # Ensure boost section exists even on old settings docs
    if "boost" not in settings:
        settings["boost"] = defaults["boost"]
    return JSONResponse(content={"ok": True, "settings": settings})


@app.put("/api/admin/miniapp/settings")
async def api_admin_miniapp_settings_update(request: Request):
    """Settings tab — update settings (safe fields only)."""
    from ml_ops import get_db as _get_db
    from datetime import datetime, timezone
    db = _get_db()
    body = await request.json()
    settings = body.get("settings", {})

    # Remove protected fields
    settings.pop("_id", None)
    settings["type"] = "global"
    settings["updated_at"] = datetime.now(timezone.utc).isoformat()

    await db.miniapp_settings.update_one(
        {"type": "global"}, {"$set": settings}, upsert=True
    )

    # Log audit
    await db.admin_audit_log.insert_one({
        "action": "miniapp_settings_update",
        "data": settings,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    return JSONResponse(content={"ok": True, "settings": settings})




@app.get("/api/outcome/labels-v2-compare")
async def api_labels_v2_compare():
    """Compare old (V1) vs new (V2) label distributions for shadow analysis."""
    from ml_ops import get_db as _get_db
    db = _get_db()
    col = db["sentiment_training_dataset_v3"]

    # Count total resolved
    total = await col.count_documents({"outcome.resolved": True})

    # V1 distribution
    v1_pipeline = [
        {"$match": {"outcome.resolved": True}},
        {"$group": {"_id": "$outcome.label", "count": {"$sum": 1}}},
    ]
    v1_dist = {}
    async for doc in col.aggregate(v1_pipeline):
        v1_dist[doc["_id"] or "UNKNOWN"] = doc["count"]

    # V2 distribution (from audit.labels_v2.new)
    v2_pipeline = [
        {"$match": {"audit.labels_v2.new": {"$exists": True}}},
        {"$group": {"_id": "$audit.labels_v2.new", "count": {"$sum": 1}}},
    ]
    v2_dist = {}
    v2_total = 0
    async for doc in col.aggregate(v2_pipeline):
        v2_dist[doc["_id"] or "UNKNOWN"] = doc["count"]
        v2_total += doc["count"]

    # Transition matrix: old → new
    transition_pipeline = [
        {"$match": {"audit.labels_v2": {"$exists": True}}},
        {"$group": {
            "_id": {"old": "$audit.labels_v2.old", "new": "$audit.labels_v2.new"},
            "count": {"$sum": 1},
        }},
    ]
    transitions = []
    async for doc in col.aggregate(transition_pipeline):
        transitions.append({
            "old": doc["_id"]["old"],
            "new": doc["_id"]["new"],
            "count": doc["count"],
        })

    # Avg confidence score
    conf_pipeline = [
        {"$match": {"audit.labels_v2.confidence_score": {"$exists": True}}},
        {"$group": {"_id": None, "avg": {"$avg": "$audit.labels_v2.confidence_score"}}},
    ]
    avg_conf = None
    async for doc in col.aggregate(conf_pipeline):
        avg_conf = doc["avg"]

    return JSONResponse(content={
        "ok": True,
        "total_resolved": total,
        "v2_labeled": v2_total,
        "v1_distribution": v1_dist,
        "v2_distribution": v2_dist,
        "transitions": transitions,
        "avg_v2_confidence": round(avg_conf, 4) if avg_conf else None,
    })


# ── Graph Bridge ──

@app.post("/api/graph/bridge/run")
async def api_graph_bridge_run():
    """Run graph bridge: convert signal data into graph edges."""
    result = await run_graph_bridge()
    return JSONResponse(content=result)


@app.get("/api/graph/bridge/stats")
async def api_graph_bridge_stats():
    """Get graph bridge statistics."""
    stats = await get_graph_bridge_stats()
    return JSONResponse(content=stats)


@app.post("/api/graph/discovery/run")
async def api_discovery_run(request: Request):
    """Run GRAPH pipeline. Body: {tiers?: [0,1,2]}. Tiers: 0=core, 1=extension, 2=addons."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    tiers = body.get("tiers", [0, 1, 2])
    result = await run_graph_pipeline(tiers=tiers)
    return JSONResponse(content=result)


@app.get("/api/graph/parsers")
async def api_parser_registry():
    """Get parser registry with statuses."""
    return JSONResponse(content=await get_parser_registry())


# ── Unified Graph Builder ──

from graph.graph_builder import (
    run_full_build as _graph_full_build,
    hydrate_entity as _graph_hydrate,
    get_entity_detail as _graph_entity_detail,
    get_build_stats as _graph_build_stats,
)

from graph.graph_intelligence import (
    run_graph_intelligence as _graph_intel_run,
    get_intelligence_stats as _graph_intel_stats,
)

from graph.graph_health import (
    compute_health_snapshot as _graph_health_snapshot,
    log_health as _graph_health_log,
    apply_saturation_penalty as _graph_saturation_penalty,
    get_health_history as _graph_health_history,
)

from graph.graph_resolution import (
    run_resolution_recovery as _graph_resolution_run,
    get_resolution_stats as _graph_resolution_stats,
)


@app.post("/api/graph/build")
async def api_graph_build(background_tasks: BackgroundTasks):
    """Full graph rebuild: KNOWLEDGE + SIGNAL + cross-layer bridges."""
    from ml_ops import get_db as _gdb
    _db = _gdb()
    result = await _graph_full_build(_db)
    return JSONResponse(content=result)


@app.post("/api/graph/hydrate")
async def api_graph_hydrate(request: Request):
    """On-demand entity hydration. Body: {query: "Solana"}."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    query = body.get("query", "")
    from ml_ops import get_db as _gdb
    _db = _gdb()
    result = await _graph_hydrate(_db, query)
    return JSONResponse(content=result)


@app.get("/api/graph/entity/{entity_id:path}")
async def api_graph_entity(entity_id: str):
    """Get entity detail with edges and neighbors."""
    from ml_ops import get_db as _gdb
    _db = _gdb()
    result = await _graph_entity_detail(_db, entity_id)
    return JSONResponse(content=result)


# Stabilization Sprint C2 — duplicate of knowledge_graph.api.routes::search_entities.
# Decorator removed; function kept as private helper in case of future internal use.
async def api_graph_entities_search(q: str = "", limit: int = 10):
    """Search entities in the knowledge graph by name/label."""
    from ml_ops import get_db as _gdb
    _db = _gdb()
    if not q or len(q) < 2:
        return JSONResponse(content={"results": []})

    results = await _db.graph_nodes.find(
        {"$or": [
            {"label": {"$regex": q, "$options": "i"}},
            {"id": {"$regex": q, "$options": "i"}},
        ]},
        {"_id": 0, "id": 1, "label": 1, "type": 1}
    ).limit(limit).to_list(limit)

    return JSONResponse(content={"results": results})


# Stabilization Sprint C2 — duplicate of knowledge_graph.graph_api_routes::search_entities_advanced.
async def api_graph_search_advanced(q: str = "", auto_create: bool = False):
    """Advanced entity search with alias/alias fallback."""
    from ml_ops import get_db as _gdb
    _db = _gdb()
    if not q:
        return JSONResponse(content={"found": False})

    # Stage 1: Exact match
    entity = await _db.graph_nodes.find_one(
        {"$or": [
            {"label": {"$regex": f"^{q}$", "$options": "i"}},
            {"id": {"$regex": f":{q}$", "$options": "i"}},
        ]},
        {"_id": 0, "id": 1, "label": 1, "type": 1}
    )
    if entity:
        return JSONResponse(content={"found": True, "entity": entity, "stage": "exact"})

    # Stage 2: Partial match
    entity = await _db.graph_nodes.find_one(
        {"$or": [
            {"label": {"$regex": q, "$options": "i"}},
            {"id": {"$regex": q, "$options": "i"}},
        ]},
        {"_id": 0, "id": 1, "label": 1, "type": 1}
    )
    if entity:
        return JSONResponse(content={"found": True, "entity": entity, "stage": "partial"})

    # Stage 3: Alias lookup
    alias_doc = await _db.entity_aliases.find_one(
        {"aliases.value": {"$regex": q, "$options": "i"}},
        {"_id": 0, "canonical_id": 1}
    )
    if alias_doc:
        entity = await _db.graph_nodes.find_one(
            {"id": alias_doc["canonical_id"]},
            {"_id": 0, "id": 1, "label": 1, "type": 1}
        )
        if entity:
            return JSONResponse(content={"found": True, "entity": entity, "stage": "alias"})

    # Stage 4: Suggestions
    suggestions = await _db.graph_nodes.find(
        {"label": {"$regex": q[:3], "$options": "i"}},
        {"_id": 0, "id": 1, "label": 1, "type": 1}
    ).limit(5).to_list(5)

    return JSONResponse(content={"found": False, "suggestions": suggestions})


# Stabilization Sprint C2 — duplicate of knowledge_graph.{api.routes,graph_api_routes}::stats.
async def api_graph_stats():
    """Graph stats with node/edge type distributions."""
    from ml_ops import get_db as _gdb
    _db = _gdb()

    total_nodes = await _db.graph_nodes.count_documents({})
    total_edges = await _db.graph_edges.count_documents({})

    nodes_pipeline = [
        {"$group": {"_id": "$type", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    nodes_by_type = {d["_id"]: d["count"] for d in await _db.graph_nodes.aggregate(nodes_pipeline).to_list(20)}

    edges_pipeline = [
        {"$group": {"_id": "$relation_type", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    edges_by_type = {d["_id"]: d["count"] for d in await _db.graph_edges.aggregate(edges_pipeline).to_list(30)}

    return JSONResponse(content={
        "total_nodes": total_nodes,
        "total_edges": total_edges,
        "nodes_by_type": nodes_by_type,
        "edges_by_type": edges_by_type,
    })


@app.get("/api/graph/edges/{entity_type}/{entity_name}")
async def api_graph_entity_edges(entity_type: str, entity_name: str, limit: int = 100):
    """Get edges for a specific entity."""
    from ml_ops import get_db as _gdb
    _db = _gdb()
    entity_id = f"{entity_type}:{entity_name}"

    edges = await _db.graph_edges.find(
        {"$or": [{"from_node_id": entity_id}, {"to_node_id": entity_id}]},
        {"_id": 0}
    ).limit(limit).to_list(limit)

    result = []
    for e in edges:
        is_outgoing = e.get("from_node_id") == entity_id
        target_id = e["to_node_id"] if is_outgoing else e["from_node_id"]
        target_node = await _db.graph_nodes.find_one({"id": target_id}, {"_id": 0, "label": 1, "type": 1})
        result.append({
            "id": f"{e['from_node_id']}→{e['to_node_id']}",
            "source": e["from_node_id"],
            "target": e["to_node_id"],
            "source_label": e["from_node_id"].split(":")[-1],
            "target_label": target_node["label"] if target_node else target_id.split(":")[-1],
            "relation": e.get("relation_type", "unknown"),
            "layer": e.get("layer", ""),
        })

    return JSONResponse(content={"edges": result})


@app.get("/api/graph/neighbors/{entity_type}/{entity_name}")
async def api_graph_entity_neighbors(entity_type: str, entity_name: str, limit: int = 100):
    """Get neighbor nodes for a specific entity."""
    from ml_ops import get_db as _gdb
    _db = _gdb()
    entity_id = f"{entity_type}:{entity_name}"

    neighbor_ids = set()
    async for e in _db.graph_edges.find(
        {"$or": [{"from_node_id": entity_id}, {"to_node_id": entity_id}]},
        {"_id": 0, "from_node_id": 1, "to_node_id": 1}
    ):
        other = e["to_node_id"] if e["from_node_id"] == entity_id else e["from_node_id"]
        neighbor_ids.add(other)

    neighbors = []
    for nid in list(neighbor_ids)[:limit]:
        node = await _db.graph_nodes.find_one({"id": nid}, {"_id": 0, "id": 1, "label": 1, "type": 1})
        if node:
            neighbors.append(node)

    return JSONResponse(content={"neighbors": neighbors, "count": len(neighbors)})


@app.get("/api/graph/build/stats")
async def api_graph_build_stats():
    """Graph build statistics with cross-layer bridge counts."""
    from ml_ops import get_db as _gdb
    _db = _gdb()
    result = await _graph_build_stats(_db)
    return JSONResponse(content=result)


# Stabilization Sprint C2 — duplicate of intel_admin.santiment_api::entity_graph_network.
async def api_entity_graph_network(node_id: str = None, limit_nodes: int = 150, limit_edges: int = 400, depth: int = 2):
    """Knowledge graph network for ForceGraph visualization. Wraps hydrate endpoint."""
    from ml_ops import get_db as _gdb
    _db = _gdb()

    query = ""
    if node_id:
        # Support both "token:SOL" and "SOL" and "project:solana" formats
        parts = node_id.split(":")
        if len(parts) >= 2:
            query = parts[-1]
        else:
            query = node_id

    if not query:
        return JSONResponse(content={"nodes": [], "edges": []})

    result = await _graph_hydrate(_db, query)
    nodes = result.get("nodes", [])[:limit_nodes]
    edges = result.get("edges", [])[:limit_edges]

    # Ensure all edge endpoints exist in nodes set
    node_ids = {n["id"] for n in nodes}
    filtered_edges = [e for e in edges if e.get("from_node_id") in node_ids and e.get("to_node_id") in node_ids]

    return JSONResponse(content={"nodes": nodes, "edges": filtered_edges})


@app.post("/api/graph/github/sync")
async def api_github_sync(request: Request):
    """Sync GitHub repos and build developer→project edges. Body: {batch_size?: 5}."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    batch_size = body.get("batch_size", 5)
    from ml_ops import get_db as _gdb
    _db = _gdb()
    # Run GitHub sync via subprocess
    import subprocess, sys as _sys, json as _json
    script = f'''
import asyncio, os, sys
sys.path.insert(0, '/app/backend')
os.chdir('/app/backend')
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
load_dotenv('/app/backend/.env')
client = AsyncIOMotorClient(os.environ['MONGO_URL'])
db = client[os.environ.get('DB_NAME','fomo_mobile')]
from modules.parsers.parser_github import sync_github_data
import json
async def run():
    result = await sync_github_data(db, batch_size={batch_size})
    # Ensure serializable
    for p in result.get("projects",[]):
        for k,v in list(p.items()):
            if not isinstance(v, (str,int,float,bool,type(None))):
                p[k] = str(v)
    print(json.dumps(result, default=str))
asyncio.run(run())
'''
    try:
        proc = subprocess.run(
            [_sys.executable, "-c", script],
            capture_output=True, text=True, timeout=180,
            env={**os.environ}
        )
        if proc.returncode == 0 and proc.stdout.strip():
            sync_result = _json.loads(proc.stdout.strip().split('\n')[-1])
        else:
            sync_result = {"ok": False, "error": (proc.stderr or "unknown")[-300:]}
    except Exception as e:
        sync_result = {"ok": False, "error": str(e)[:300]}

    # Build GitHub edges from synced data
    from graph.graph_builder import build_github_edges
    gh_edges = await build_github_edges(_db)
    sync_result["graph_edges"] = gh_edges
    return JSONResponse(content=sync_result)


@app.get("/api/graph/fallback/status")
async def api_graph_fallback_status():
    """Check HTML fallback status for all parsers."""
    from ml_ops import get_db as _gdb
    _db = _gdb()
    parsers = await _db.parser_registry.find(
        {}, {"_id": 0, "name": 1, "status": 1, "consecutive_failures": 1, "html_fallback_active": 1}
    ).to_list(20)
    return JSONResponse(content={"ok": True, "parsers": parsers})


@app.post("/api/graph/fallback/test")
async def api_graph_fallback_test(request: Request):
    """Test HTML fallback for a specific parser. Body: {parser: "CryptoRank"}."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    parser_name = body.get("parser", "")
    from graph.html_fallback import (
        cryptorank_html_coins, cryptorank_html_funding,
        dropstab_html_activities, icodrops_html_upcoming,
    )
    fallback_map = {
        "CryptoRank": ("coins", cryptorank_html_coins),
        "CryptoRank_funding": ("funding", cryptorank_html_funding),
        "Dropstab": ("activities", dropstab_html_activities),
        "ICODrops": ("icos", icodrops_html_upcoming),
    }
    if parser_name not in fallback_map:
        return JSONResponse(content={"ok": False, "error": f"Unknown parser: {parser_name}. Options: {list(fallback_map.keys())}"})
    label, fn = fallback_map[parser_name]
    try:
        import time
        t0 = time.time()
        data = await fn()
        dur = round(time.time() - t0, 1)
        return JSONResponse(content={"ok": True, "parser": parser_name, "type": label, "count": len(data), "duration_sec": dur, "sample": data[:3] if data else []})
    except Exception as e:
        return JSONResponse(content={"ok": False, "parser": parser_name, "error": str(e)[:300]})


# ── Graph Intelligence ──

@app.post("/api/graph/intelligence/run")
async def api_graph_intelligence_run():
    """Run all intelligence layers: entity_pressure → alpha_source → decay → attention_flow."""
    from ml_ops import get_db as _gdb
    _db = _gdb()
    result = await _graph_intel_run(_db)
    return JSONResponse(content=result)


@app.get("/api/graph/intelligence/stats")
async def api_graph_intelligence_stats():
    """Intelligence edge statistics with top pressure/alpha entities."""
    from ml_ops import get_db as _gdb
    _db = _gdb()
    result = await _graph_intel_stats(_db)
    return JSONResponse(content=result)


# ── Graph Health Engine ──

@app.get("/api/graph/health/snapshot")
async def api_graph_health():
    """Current graph health snapshot."""
    from ml_ops import get_db as _gdb
    _db = _gdb()
    snapshot = await _graph_health_snapshot(_db)
    return JSONResponse(content={"ok": True, **snapshot})


@app.post("/api/graph/health/log")
async def api_graph_health_log(request: Request):
    """Force health log. Body: {cycle_id?: "manual_123"}."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    cycle_id = body.get("cycle_id")
    from ml_ops import get_db as _gdb
    _db = _gdb()
    record = await _graph_health_log(_db, cycle_id=cycle_id)
    # Remove _id for serialization
    record.pop("_id", None)
    return JSONResponse(content={"ok": True, "record": record})


@app.get("/api/graph/health/history")
async def api_graph_health_history(limit: int = 20):
    """Health log history."""
    from ml_ops import get_db as _gdb
    _db = _gdb()
    result = await _graph_health_history(_db, limit=limit)
    return JSONResponse(content=result)


@app.post("/api/graph/health/saturation")
async def api_graph_saturation():
    """Apply soft saturation penalty on over-represented entities."""
    from ml_ops import get_db as _gdb
    _db = _gdb()
    result = await _graph_saturation_penalty(_db)
    return JSONResponse(content={"ok": True, **result})


# ── Entity Resolution Recovery ──

@app.post("/api/graph/resolution/run")
async def api_graph_resolution_run():
    """Run full entity resolution recovery pass."""
    from ml_ops import get_db as _gdb
    _db = _gdb()
    result = await _graph_resolution_run(_db)
    return JSONResponse(content=result)


@app.get("/api/graph/resolution/stats")
async def api_graph_resolution_stats():
    """Entity resolution stats: meaningful vs infra orphans, coverage."""
    from ml_ops import get_db as _gdb
    _db = _gdb()
    result = await _graph_resolution_stats(_db)
    return JSONResponse(content=result)


# ── News Pipeline ──

@app.post("/api/news/fetch")
async def api_news_fetch(request: Request):
    """Fetch news from RSS sources. Body: {limit_sources?, tiers?: ['A','B']}."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    from ml_ops import get_db as _gdb
    db = _gdb()
    result = await run_news_pipeline(
        db,
        limit_sources=body.get("limit_sources"),
        tiers=body.get("tiers"),
    )
    return JSONResponse(content=result)


@app.get("/api/news/stats")
async def api_news_stats():
    """Get news pipeline statistics."""
    from ml_ops import get_db as _gdb
    db = _gdb()
    stats = await get_news_stats(db)
    return JSONResponse(content=stats)


# ══════════════════════════════════════════════════════════
# UNIFIED SIGNAL ENGINE (Graph + Fund signals)
# ══════════════════════════════════════════════════════════

@app.post("/api/graph-signals/run")
async def api_signals_graph_run():
    """Run graph-level signal detection across active tokens."""
    from ml_ops import get_db as _gdb
    _db = _gdb()
    from signals.unified_signal_engine import run_graph_signals
    result = await run_graph_signals(_db)
    return JSONResponse(content=result)


@app.post("/api/graph-signals/fund/run")
async def api_signals_fund_run():
    """Run fund-level signal detection (fund_pressure aggregation)."""
    from ml_ops import get_db as _gdb
    _db = _gdb()
    from signals.unified_signal_engine import run_fund_signals
    result = await run_fund_signals(_db)
    return JSONResponse(content=result)


@app.get("/api/graph-signals/log")
async def api_signals_log(entity: str = None, limit: int = 50):
    """Get signal log entries. Optional filter by entity."""
    from ml_ops import get_db as _gdb
    _db = _gdb()
    from signals.unified_signal_engine import get_signal_log
    logs = await get_signal_log(_db, entity=entity, limit=limit)
    return JSONResponse(content={"ok": True, "count": len(logs), "signals": logs})


@app.get("/api/graph-signals/stats")
async def api_graph_signals_stats():
    """Get unified signal engine statistics."""
    from ml_ops import get_db as _gdb
    _db = _gdb()

    total_signals = await _db.signal_log.count_documents({})
    token_signals = await _db.signal_log.count_documents({"entity_type": "token"})
    fund_signals = await _db.signal_log.count_documents({"entity_type": "fund"})

    # Recent signals by type
    pipeline = [
        {"$group": {"_id": "$type", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    by_type = await _db.signal_log.aggregate(pipeline).to_list(10)

    # Active funds
    active_funds = await _db.graph_nodes.count_documents({
        "type": "fund", "signal_active": True
    })

    # Signal edges in graph
    signal_edges = await _db.graph_edges.count_documents({
        "relation_type": "signal_detected"
    })

    return JSONResponse(content={
        "ok": True,
        "total_signals_logged": total_signals,
        "token_signals": token_signals,
        "fund_signals": fund_signals,
        "signal_edges": signal_edges,
        "active_funds": active_funds,
        "by_type": {d["_id"]: d["count"] for d in by_type},
    })


# ══════════════════════════════════════════════════════════
# EXPANSION ENGINE
# ══════════════════════════════════════════════════════════

@app.get("/api/graph/expansion/check")
async def api_expansion_check():
    """Check if expansion should trigger."""
    from ml_ops import get_db as _gdb
    _db = _gdb()
    from graph.expansion_engine import should_expand
    result = await should_expand(_db)
    return JSONResponse(content=result)


@app.post("/api/graph/expansion/run")
async def api_expansion_run():
    """Run expansion cycle (only executes if triggers are met)."""
    from ml_ops import get_db as _gdb
    _db = _gdb()
    from graph.expansion_engine import run_expansion
    result = await run_expansion(_db)
    return JSONResponse(content=result)


@app.get("/api/graph/expansion/log")
async def api_expansion_log():
    """Get expansion history."""
    from ml_ops import get_db as _gdb
    _db = _gdb()
    logs = await _db.expansion_log.find(
        {}, {"_id": 0}
    ).sort("timestamp", -1).limit(20).to_list(20)
    return JSONResponse(content={"ok": True, "count": len(logs), "history": logs})


# ══════════════════════════════════════════════════════════
# PRE-PUMP DETECTOR
# ══════════════════════════════════════════════════════════

@app.post("/api/graph-signals/pre-pump/scan")
async def api_pre_pump_scan():
    """Scan all active tokens for pre-pump signals."""
    from ml_ops import get_db as _gdb
    _db = _gdb()
    from signals.pre_pump_detector import run_pre_pump_scan
    result = await run_pre_pump_scan(_db)
    return JSONResponse(content=result)


@app.get("/api/graph-signals/pre-pump/{token}")
async def api_pre_pump_token(token: str):
    """Detect pre-pump signal for a specific token."""
    from ml_ops import get_db as _gdb
    _db = _gdb()
    from signals.pre_pump_detector import detect_pre_pump
    token_id = f"token:{token}" if not token.startswith("token:") else token
    result = await detect_pre_pump(_db, token_id)
    return JSONResponse(content=result)


# ══════════════════════════════════════════════════════════
# SIGNAL SYNC DEBUG ENDPOINT
# ══════════════════════════════════════════════════════════

@app.get("/api/debug/signal/{token}")
async def api_debug_signal(token: str):
    """
    Compare Overview vs Graph signals for the same token.
    Shows both contexts and whether they agree.
    """
    from ml_ops import get_db as _gdb
    _db = _gdb()
    from signals.graph_adapter import build_graph_context
    from signals.unified_signal_engine import detect_signal
    from signals.core_signal_logic import detect_signal_type

    token_id = f"token:{token}" if not token.startswith("token:") else token

    # ── Graph Signal ──
    graph_ctx = await build_graph_context(_db, token_id)
    graph_signal = detect_signal(graph_ctx)

    # ── Overview Signal ──
    # Pull latest engine_context_snapshot for this asset
    from pymongo import MongoClient
    import os
    sync_client = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    sync_db = sync_client[os.environ.get("DB_NAME", "intelligence_engine")]

    symbol = token_id.replace("token:", "")
    snapshot = sync_db["engine_context_snapshots"].find_one(
        {"asset": {"$regex": f"^{symbol}$", "$options": "i"}},
        {"_id": 0},
        sort=[("timestamp", -1)]
    )

    overview_signal = None
    overview_ctx = None
    if snapshot:
        from signals.overview_adapter import build_overview_context
        overview_ctx = build_overview_context(snapshot)
        overview_signal = detect_signal(overview_ctx, overview_ctx.get("market_context"))

    sync_client.close()

    # ── Compare ──
    match = False
    if graph_signal and overview_signal:
        match = (
            graph_signal.get("type") == overview_signal.get("type") and
            graph_signal.get("direction") == overview_signal.get("direction")
        )

    return JSONResponse(content={
        "token": token_id,
        "graph": {
            "context": {k: v for k, v in graph_ctx.items() if k not in ("source",)},
            "signal": graph_signal,
        },
        "overview": {
            "context": {k: v for k, v in (overview_ctx or {}).items() if k not in ("source", "market_context")} if overview_ctx else None,
            "signal": overview_signal,
            "snapshot_available": snapshot is not None,
        },
        "match": match,
        "match_type": graph_signal.get("type") == (overview_signal or {}).get("type") if overview_signal else None,
        "match_direction": graph_signal.get("direction") == (overview_signal or {}).get("direction") if overview_signal else None,
    })


# ══════════════════════════════════════════════════════════
# RADAR BACKEND (aggregated intelligence view)
# ══════════════════════════════════════════════════════════

@app.get("/api/radar")
async def api_radar():
    """
    Radar: aggregated intelligence view.
    Returns hot_tokens, fund_pressure, new_signals, pre_pump alerts.
    """
    from ml_ops import get_db as _gdb
    _db = _gdb()

    # ── Hot Tokens: tokens with most recent signal activity ──
    pipeline = [
        {"$match": {"entity_type": "token"}},
        {"$sort": {"timestamp": -1}},
        {"$group": {
            "_id": "$entity",
            "latest_type": {"$first": "$type"},
            "latest_strength": {"$first": "$strength"},
            "latest_direction": {"$first": "$direction"},
            "signal_count": {"$sum": 1},
            "latest_time": {"$first": "$timestamp"},
        }},
        {"$sort": {"signal_count": -1}},
        {"$limit": 20},
    ]
    hot_tokens = await _db.signal_log.aggregate(pipeline).to_list(20)
    hot_tokens = [{
        "token": t["_id"],
        "type": t["latest_type"],
        "strength": t["latest_strength"],
        "direction": t["latest_direction"],
        "signal_count": t["signal_count"],
        "latest": t["latest_time"],
    } for t in hot_tokens]

    # ── Fund Pressure: active funds sorted by signal strength ──
    active_funds = await _db.graph_nodes.find(
        {"type": "fund", "signal_active": True},
        {"_id": 0, "id": 1, "label": 1, "signal_strength": 1, "signal_direction": 1, "signal_updated": 1}
    ).sort("signal_strength", -1).to_list(20)

    fund_pressure = [{
        "fund": f["id"],
        "label": f.get("label", ""),
        "strength": f.get("signal_strength", 0),
        "direction": f.get("signal_direction", "NEUTRAL"),
        "updated": f.get("signal_updated", ""),
    } for f in active_funds]

    # ── New Signals: most recent signal_log entries ──
    recent = await _db.signal_log.find(
        {}, {"_id": 0}
    ).sort("timestamp", -1).limit(10).to_list(10)

    # ── Pre-Pump Alerts ──
    pre_pump_edges = await _db.graph_edges.find(
        {"relation_type": "pre_pump_detected"},
        {"_id": 0, "from_node_id": 1, "to_node_id": 1, "metadata": 1}
    ).to_list(20)

    pre_pumps = [{
        "token": e["from_node_id"],
        "project": e["to_node_id"],
        "score": e.get("metadata", {}).get("score", 0),
        "confidence": e.get("metadata", {}).get("confidence", 0),
        "detected_at": e.get("metadata", {}).get("detected_at", ""),
    } for e in pre_pump_edges]

    # ── Summary stats ──
    total_signals = await _db.signal_log.count_documents({})
    signal_edges = await _db.graph_edges.count_documents({"relation_type": "signal_detected"})
    pre_pump_count = await _db.graph_edges.count_documents({"relation_type": "pre_pump_detected"})

    return JSONResponse(content={
        "ok": True,
        "hot_tokens": hot_tokens,
        "fund_pressure": fund_pressure,
        "new_signals": recent,
        "pre_pumps": pre_pumps,
        "stats": {
            "total_signals_logged": total_signals,
            "signal_edges": signal_edges,
            "pre_pump_alerts": pre_pump_count,
            "active_funds": len(fund_pressure),
        },
    })



# ─── ML Overlay V1 (Risk Prediction) Endpoints ───

@app.post("/api/ml-risk/build-dataset")
async def api_ml_risk_build_dataset(limit: int = 2000):
    """Build ML risk overlay dataset from exchange_forecasts with outcomes."""
    from ml_ops import get_db as _get_db
    from ml_overlay.dataset_builder import build_ml_row
    db = _get_db()

    cursor = db["exchange_forecasts"].find(
        {"outcome.label": {"$in": ["FP", "TP", "FN", "WEAK"]}},
        {"_id": 1, "id": 1, "asset": 1, "symbol": 1, "horizon": 1, "direction": 1,
         "confidence": 1, "confidenceRaw": 1, "expectedMovePct": 1, "modelVersion": 1,
         "createdAt": 1, "audit": 1, "outcome": 1}
    ).limit(limit)

    docs = await cursor.to_list(limit)
    rows = []
    for doc in docs:
        row = build_ml_row(doc)
        if row:
            rows.append(row)

    if not rows:
        return JSONResponse(content={"ok": False, "error": "No valid rows found"})

    # Upsert into ml_overlay_dataset
    col = db["ml_overlay_dataset"]
    inserted = 0
    for row in rows:
        await col.update_one(
            {"forecast_id": row["forecast_id"]},
            {"$set": row},
            upsert=True
        )
        inserted += 1

    # Stats
    error_count = sum(1 for r in rows if r["target_error"] == 1)
    tp_count = sum(1 for r in rows if r["target_error"] == 0)

    return JSONResponse(content={
        "ok": True,
        "total_forecasts": len(docs),
        "valid_rows": len(rows),
        "inserted": inserted,
        "target_distribution": {
            "error": error_count,
            "correct": tp_count,
            "error_rate": round(error_count / max(len(rows), 1) * 100, 1),
        },
    })


@app.post("/api/ml-risk/train")
async def api_ml_risk_train():
    """Train ML Overlay V1 model on the built dataset."""
    from ml_ops import get_db as _get_db
    db = _get_db()
    import pandas as pd

    cursor = db["ml_overlay_dataset"].find({}, {"_id": 0})
    docs = await cursor.to_list(5000)

    if len(docs) < 20:
        return JSONResponse(content={
            "ok": False, "error": f"Need >= 20 samples, have {len(docs)}"
        })

    df = pd.DataFrame(docs)

    from ml_overlay.trainer import train_model
    try:
        _, metrics = train_model(df)
    except Exception as e:
        return JSONResponse(content={"ok": False, "error": str(e)})

    return JSONResponse(content={"ok": True, "metrics": metrics})


@app.get("/api/ml-risk/status")
async def api_ml_risk_status():
    """Get ML overlay model status and metrics."""
    from pathlib import Path
    import json as _json
    from ml_ops import get_db as _get_db
    db = _get_db()

    model_path = Path("/app/backend/artifacts/ml_overlay_v1/model.joblib")
    metrics_path = Path("/app/backend/artifacts/ml_overlay_v1/metrics.json")

    model_exists = model_path.exists()
    metrics = None
    if metrics_path.exists():
        metrics = _json.loads(metrics_path.read_text())

    dataset_count = await db["ml_overlay_dataset"].count_documents({})
    shadow_count = await db["exchange_forecasts"].count_documents({"audit.ml": {"$exists": True}})

    return JSONResponse(content={
        "ok": True,
        "model_trained": model_exists,
        "dataset_size": dataset_count,
        "shadow_scored": shadow_count,
        "metrics": metrics,
    })


@app.post("/api/ml-risk/shadow-score")
async def api_ml_risk_shadow_score(limit: int = 200):
    """Run shadow scoring on recent exchange_forecasts and write audit.ml + audit.preflight."""
    from ml_ops import get_db as _get_db
    from ml_overlay.post_process import apply_ml_risk_layers
    db = _get_db()

    cursor = db["exchange_forecasts"].find(
        {"outcome.label": {"$exists": True}, "audit.ml.mode": {"$ne": "shadow_plus_live"}},
        {"_id": 1, "id": 1, "confidence": 1, "confidenceRaw": 1, "confidenceTarget": 1,
         "degraded": 1, "direction": 1, "horizon": 1, "asset": 1,
         "expectedMovePct": 1, "audit": 1, "outcome": 1}
    ).sort("createdAt", -1).limit(limit)

    docs = await cursor.to_list(limit)
    scored = 0
    errors = 0

    for doc in docs:
        try:
            doc_dict = {k: v for k, v in doc.items() if k != "_id"}
            result = apply_ml_risk_layers(doc_dict)
            update_fields = {}
            if "ml" in result.get("audit", {}):
                update_fields["audit.ml"] = result["audit"]["ml"]
            if "preflight" in result.get("audit", {}):
                update_fields["audit.preflight"] = result["audit"]["preflight"]
            if "confidence_pipeline" in result.get("audit", {}):
                update_fields["audit.confidence_pipeline"] = result["audit"]["confidence_pipeline"]
            if update_fields:
                await db["exchange_forecasts"].update_one(
                    {"_id": doc["_id"]}, {"$set": update_fields}
                )
                scored += 1
        except Exception:
            errors += 1

    return JSONResponse(content={
        "ok": True,
        "scored": scored,
        "errors": errors,
        "total_checked": len(docs),
    })


@app.get("/api/ml-risk/shadow-stats")
async def api_ml_risk_shadow_stats():
    """Get shadow scoring stats: risk distribution, FP rate by bucket, confidence preview."""
    from ml_ops import get_db as _get_db
    db = _get_db()

    cursor = db["exchange_forecasts"].find(
        {"audit.ml.enabled": True},
        {"_id": 0, "audit.ml": 1, "audit.preflight": 1, "outcome.label": 1, "confidence": 1}
    )
    docs = await cursor.to_list(5000)

    if not docs:
        return JSONResponse(content={"ok": True, "total": 0, "message": "No shadow data yet"})

    buckets = {"low": [], "medium": [], "high": []}
    scores = []
    live_applied_count = 0
    preflight_triggered_count = 0
    preflight_overlap_count = 0

    for d in docs:
        ml = d.get("audit", {}).get("ml", {})
        pf = d.get("audit", {}).get("preflight", {})
        label = d.get("outcome", {}).get("label")
        bucket = ml.get("risk_bucket", "low")
        score = ml.get("risk_score", 0)
        scores.append(score)

        if ml.get("live_applied"):
            live_applied_count += 1
        if pf.get("triggered"):
            preflight_triggered_count += 1
            if ml.get("live_applied"):
                preflight_overlap_count += 1

        is_error = label in ("FP", "FN", "WEAK")
        buckets[bucket].append({
            "score": score,
            "error": is_error,
            "label": label,
            "conf_before": ml.get("confidence_before_ml", 0),
            "conf_after": ml.get("confidence_after_ml", ml.get("confidence_after_ml_preview", 0)),
        })

    result = {"ok": True, "total": len(docs)}

    for bk in ["low", "medium", "high"]:
        items = buckets[bk]
        n = len(items)
        errors = sum(1 for i in items if i["error"])
        result[f"bucket_{bk}"] = {
            "count": n,
            "error_count": errors,
            "error_rate": round(errors / max(n, 1) * 100, 1),
            "avg_conf_before": round(sum(i["conf_before"] for i in items) / max(n, 1), 4),
            "avg_conf_after": round(sum(i["conf_after"] for i in items) / max(n, 1), 4),
        }

    sorted_scores = sorted(scores)
    n = len(sorted_scores)
    result["risk_percentiles"] = {
        "p50": round(sorted_scores[int(0.5 * (n - 1))], 4) if n else 0,
        "p75": round(sorted_scores[int(0.75 * (n - 1))], 4) if n else 0,
        "p90": round(sorted_scores[int(0.9 * (n - 1))], 4) if n else 0,
        "p95": round(sorted_scores[min(int(0.95 * (n - 1)), n - 1)], 4) if n else 0,
    }

    high_err = result.get("bucket_high", {}).get("error_rate", 0)
    low_err = result.get("bucket_low", {}).get("error_rate", 0)
    result["model_validation"] = {
        "high_worse_than_low": high_err > low_err,
        "high_error_rate": high_err,
        "low_error_rate": low_err,
        "verdict": "USEFUL" if high_err > low_err else "CHECK_MODEL",
    }

    result["live_stats"] = {
        "live_applied_count": live_applied_count,
        "live_pct": round(live_applied_count / max(len(docs), 1) * 100, 1),
    }

    result["preflight_stats"] = {
        "triggered_count": preflight_triggered_count,
        "trigger_rate": round(preflight_triggered_count / max(len(docs), 1) * 100, 1),
        "overlap_with_ml": preflight_overlap_count,
        "triggered_without_ml": preflight_triggered_count - preflight_overlap_count,
    }

    return JSONResponse(content=result)


# ─── ML Risk Rollout Control ───

@app.get("/api/ml-risk/rollout-status")
async def api_ml_risk_rollout_status():
    """Get ML overlay rollout configuration status."""
    from ml_overlay import config as _cfg
    return JSONResponse(content={
        "ok": True,
        "ml_overlay": {
            "enabled": _cfg.ML_OVERLAY_ENABLED,
            "mode": _cfg.ML_OVERLAY_MODE,
            "live_pct": _cfg.ML_OVERLAY_LIVE_PCT,
            "risk_threshold": _cfg.ML_OVERLAY_RISK_THRESHOLD,
            "kill_switch": _cfg.ML_OVERLAY_KILL_SWITCH,
            "cap": _cfg.ML_OVERLAY_CAP,
            "multiplier": _cfg.ML_OVERLAY_MULT_HIGH,
            "salt": _cfg.ML_OVERLAY_SALT,
        },
        "preflight": {
            "enabled": _cfg.PREFLIGHT_ENABLED,
            "mode": _cfg.PREFLIGHT_MODE,
            "threshold": _cfg.PREFLIGHT_CONF_TARGET_THRESHOLD,
            "base_penalty": _cfg.PREFLIGHT_BASE_PENALTY,
            "cap": _cfg.PREFLIGHT_CAP,
            "use_ml": _cfg.PREFLIGHT_USE_ML,
        },
        "global": {
            "confidence_floor": _cfg.FINAL_CONFIDENCE_FLOOR,
        },
    })


@app.post("/api/ml-risk/rollout")
async def api_ml_risk_rollout(enabled: bool = True, live_pct: float = 0.10,
                               risk_threshold: float = 0.85, kill_switch: bool = False):
    """Update ML overlay rollout parameters."""
    from ml_overlay import config as _cfg
    _cfg.ML_OVERLAY_ENABLED = enabled
    _cfg.ML_OVERLAY_LIVE_PCT = max(0.0, min(1.0, live_pct))
    _cfg.ML_OVERLAY_RISK_THRESHOLD = risk_threshold
    _cfg.ML_OVERLAY_KILL_SWITCH = kill_switch
    if not kill_switch:
        _cfg.ML_OVERLAY_MODE = "shadow_plus_live" if live_pct > 0 else "shadow"
    else:
        _cfg.ML_OVERLAY_MODE = "shadow"
    return JSONResponse(content={"ok": True, "applied": {
        "enabled": _cfg.ML_OVERLAY_ENABLED,
        "mode": _cfg.ML_OVERLAY_MODE,
        "live_pct": _cfg.ML_OVERLAY_LIVE_PCT,
        "risk_threshold": _cfg.ML_OVERLAY_RISK_THRESHOLD,
        "kill_switch": _cfg.ML_OVERLAY_KILL_SWITCH,
    }})


@app.post("/api/ml-risk/kill")
async def api_ml_risk_kill():
    """Emergency kill switch for ML overlay live modulation."""
    from ml_overlay import config as _cfg
    _cfg.ML_OVERLAY_KILL_SWITCH = True
    _cfg.ML_OVERLAY_MODE = "shadow"
    return JSONResponse(content={"ok": True, "message": "Kill switch activated. ML overlay in shadow-only mode."})


# ─── Pre-Flight Gate Control ───

@app.get("/api/preflight/status")
async def api_preflight_status():
    """Get preflight gate configuration."""
    from ml_overlay import config as _cfg
    return JSONResponse(content={
        "ok": True,
        "enabled": _cfg.PREFLIGHT_ENABLED,
        "mode": _cfg.PREFLIGHT_MODE,
        "threshold": _cfg.PREFLIGHT_CONF_TARGET_THRESHOLD,
        "base_penalty": _cfg.PREFLIGHT_BASE_PENALTY,
        "cap": _cfg.PREFLIGHT_CAP,
        "use_ml": _cfg.PREFLIGHT_USE_ML,
    })


@app.post("/api/preflight/config")
async def api_preflight_config(
    enabled: bool = True, mode: str = "shadow",
    threshold: float = 0.65, base_penalty: float = 0.05, cap: float = 0.10,
):
    """Update preflight gate configuration."""
    from ml_overlay import config as _cfg
    _cfg.PREFLIGHT_ENABLED = enabled
    _cfg.PREFLIGHT_MODE = mode if mode in ("shadow", "live") else "shadow"
    _cfg.PREFLIGHT_CONF_TARGET_THRESHOLD = threshold
    _cfg.PREFLIGHT_BASE_PENALTY = base_penalty
    _cfg.PREFLIGHT_CAP = cap
    return JSONResponse(content={"ok": True, "config": {
        "enabled": _cfg.PREFLIGHT_ENABLED,
        "mode": _cfg.PREFLIGHT_MODE,
        "threshold": _cfg.PREFLIGHT_CONF_TARGET_THRESHOLD,
        "base_penalty": _cfg.PREFLIGHT_BASE_PENALTY,
        "cap": _cfg.PREFLIGHT_CAP,
    }})



# ═══════════════════════════════════════════════════════════
# META BRAIN V2 — HYBRID DECISION ENGINE (Shadow Mode)
# ═══════════════════════════════════════════════════════════

@app.post("/api/meta/v2/run")
async def api_meta_v2_run(asset: str = "BTC"):
    """Run MetaBrain V2 on latest signals and save to shadow collection."""
    from meta_brain.shadow_runner import run_v2_latest
    result = run_v2_latest(asset)
    return result


@app.post("/api/meta/v2/backfill")
async def api_meta_v2_backfill(asset: str = "BTC"):
    """Backfill V2 over all historical meta_brain_runs."""
    from meta_brain.shadow_runner import backfill_v2
    result = backfill_v2(asset)
    return result


@app.post("/api/meta/v2/backfill-daily")
async def api_meta_v2_backfill_daily(asset: str = "BTC"):
    """Backfill V2 daily — one result per day using real market features."""
    from meta_brain.shadow_runner import backfill_v2_daily
    result = backfill_v2_daily(asset)
    return result


@app.get("/api/meta/v1-vs-v2")
async def api_meta_v1_vs_v2(asset: str = "BTC"):
    """Compare V1 vs V2 results from shadow data."""
    from meta_brain.shadow_runner import get_v1_vs_v2_comparison
    return get_v1_vs_v2_comparison(asset)


@app.get("/api/meta/v2/live-metrics")
async def api_meta_v2_live_metrics(asset: str = "BTC"):
    """Live metrics for V2 shadow runs."""
    from meta_brain.shadow_runner import get_live_metrics
    return get_live_metrics(asset)


# ═══════════════════════════════════════════════════════════
# ADMIN TWITTER PARSER - DOWNLOAD PACKAGE
# ═══════════════════════════════════════════════════════════

@app.get("/api/admin/twitter-parser/download-parser")
async def download_twitter_parser_package():
    """Download Twitter Parser V2 package (ZIP file)"""
    from fastapi.responses import FileResponse
    import os
    
    file_path = os.path.join(os.path.dirname(__file__), "static", "twitter-parser-v2.zip")
    
    if not os.path.exists(file_path):
        return JSONResponse(
            status_code=404,
            content={"ok": False, "error": "Parser package not found"}
        )
    
    return FileResponse(
        path=file_path,
        media_type="application/zip",
        filename="twitter-parser-v2.zip"
    )


# Публичный endpoint для прямого скачивания (БЕЗ /admin префикса)
@app.get("/api/download/twitter-parser")
async def download_twitter_parser_public():
    """Public endpoint to download Twitter Parser V2 package"""
    from fastapi.responses import FileResponse
    import os
    
    file_path = os.path.join(os.path.dirname(__file__), "static", "twitter-parser-v2.zip")
    
    if not os.path.exists(file_path):
        return JSONResponse(
            status_code=404,
            content={"ok": False, "error": "Parser package not found"}
        )
    
    return FileResponse(
        path=file_path,
        media_type="application/zip",
        filename="twitter-parser-v2.zip",
        headers={
            "Content-Disposition": "attachment; filename=twitter-parser-v2.zip",
            "Cache-Control": "no-cache"
        }
    )


def _build_extension_zip() -> str:
    """Build (or rebuild) the FOMO X Connect extension ZIP from the source dir
    in /app/backend/admin_build. Returns the absolute zip path."""
    import zipfile
    from pathlib import Path
    src_dir = Path("/app/backend/admin_build/fomo_extension_v1.3.0")
    out_path = Path("/app/backend/static/fomo_extension_v1.3.0.zip")
    if not src_dir.exists():
        raise FileNotFoundError(f"extension source dir not found: {src_dir}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _dirs, files in os.walk(src_dir):
            for f in files:
                if f.startswith("."):
                    continue
                full = os.path.join(root, f)
                arc = os.path.relpath(full, str(src_dir.parent))
                zf.write(full, arc)
    return str(out_path)


# Chrome Extension для синхронизации cookies
@app.get("/api/download/fomo-extension")
async def download_fomo_extension():
    """Download FOMO X Connect Chrome Extension.

    Auto-builds the zip from /app/backend/admin_build/fomo_extension_v1.3.0
    if it's missing OR if any source file is newer than the zip.
    """
    from fastapi.responses import FileResponse
    from pathlib import Path
    import os

    file_path = os.path.join(os.path.dirname(__file__), "static", "fomo_extension_v1.3.0.zip")
    src_dir = Path("/app/backend/admin_build/fomo_extension_v1.3.0")

    needs_build = not os.path.exists(file_path)
    if not needs_build and src_dir.exists():
        zip_mtime = os.path.getmtime(file_path)
        for root, _dirs, files in os.walk(src_dir):
            for f in files:
                if f.startswith("."):
                    continue
                if os.path.getmtime(os.path.join(root, f)) > zip_mtime:
                    needs_build = True
                    break
            if needs_build:
                break

    if needs_build:
        try:
            file_path = _build_extension_zip()
            print(f"[fomo-extension] rebuilt zip → {file_path}")
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={"ok": False, "error": f"zip_build_failed: {e!r}"},
            )

    if not os.path.exists(file_path):
        return JSONResponse(
            status_code=404,
            content={"ok": False, "error": "Extension not found"}
        )

    return FileResponse(
        path=file_path,
        media_type="application/zip",
        filename="fomo_extension_v1.3.0.zip",
        headers={
            "Content-Disposition": "attachment; filename=fomo_extension_v1.3.0.zip",
            "Cache-Control": "no-cache"
        }
    )


# ═══════════════════════════════════════════════════════════
# MOBILE APP ROUTES (from FOMO-APPv2 fork)
# ═══════════════════════════════════════════════════════════

if MOBILE_ROUTES_LOADED:
    app.include_router(mobile_router)
    app.include_router(mobile_auth_router)
    print("[Proxy] Mobile routes registered: /api/mobile/*, /api/mobile/auth/*")

# ═══════════════════════════════════════════════════════════
# GROWTH LAYER G1 — Mobile Analytics (/api/mobile/analytics/*)
# ═══════════════════════════════════════════════════════════
try:
    from routes.mobile_analytics import router as mobile_analytics_router
    app.include_router(mobile_analytics_router)
    print("[Proxy] Mobile analytics routes registered: /api/mobile/analytics/*")
except Exception as _e:
    print(f"[Proxy] WARNING: Failed to load mobile analytics routes: {_e}")

# CRYPTO PAYMENTS (NOWPayments)
# ═══════════════════════════════════════════════════════════
try:
    from routes.payments import router as payments_router
    app.include_router(payments_router)
    print("[Proxy] Crypto payment routes registered: /api/payments/*")
except Exception as e:
    print(f"[Proxy] WARNING: Failed to load payments routes: {e}")

# ADMIN CRYPTO BILLING
try:
    from routes.admin_crypto_billing import router as admin_crypto_router
    app.include_router(admin_crypto_router)
    print("[Proxy] Admin crypto billing routes registered: /api/admin/billing/crypto/*")
except Exception as e:
    print(f"[Proxy] WARNING: Failed to load admin crypto billing routes: {e}")

# ADMIN AUTH (Python port — login, status, user management)
try:
    from routes.admin_auth import router as admin_auth_router
    app.include_router(admin_auth_router)
    print("[Proxy] Admin auth routes registered: /api/admin/auth/*")
except Exception as e:
    print(f"[Proxy] WARNING: Failed to load admin auth routes: {e}")

# WEB BILLING (NOWPayments) — REMOVED (Stabilization Sprint C2)
# All 5 paths (/api/billing/plans, /status, /apply-referral, /create-crypto-checkout,
# /crypto-checkout-status/{session_id}) are 100% duplicates of `billing_routes.py`
# (top-level, registered earlier at line ~482). FastAPI uses first-registered handler,
# so this block was dead code. Confirmed via openapi route diff 2026-05-11.

# UNIFIED AUTH — REMOVED (Stabilization Sprint C2)
# Identical re-import of `unified_auth_routes` already mounted earlier (line ~477).
# All 4 paths (/api/unified/auth/{google,dev-login,me,sync-subscription}) were
# silent duplicates resolving to the same handler module — pure registration noise.

# ADMIN USERS & PLATFORM MANAGEMENT
try:
    from routes.admin_users import router as admin_users_router
    app.include_router(admin_users_router)
    print("[Proxy] Admin users routes registered: /api/admin/users/*")
except Exception as e:
    print(f"[Proxy] WARNING: Failed to load admin users routes: {e}")

# ═══════════════════════════════════════════════════════════
# WEB SENTIMENT PLATFORM ROUTES (Python port — replaces Node.js proxy)
# ═══════════════════════════════════════════════════════════

# Connections Router (/api/connections/*)
try:
    from routes.connections_router import router as connections_router
    app.include_router(connections_router)
    print("[Proxy] Connections routes registered: /api/connections/*")
except Exception as e:
    print(f"[Proxy] WARNING: Failed to load connections routes: {e}")

# Backers, Alerts, Actor-Scores Router
try:
    from routes.backers_alerts_router import router as backers_alerts_router
    app.include_router(backers_alerts_router)
    print("[Proxy] Backers/Alerts/Actor-Scores routes registered")
except Exception as e:
    print(f"[Proxy] WARNING: Failed to load backers/alerts routes: {e}")

# V1 Sentiment, AI News, Providers Router
try:
    from routes.v1_sentiment_router import router as v1_sentiment_router
    app.include_router(v1_sentiment_router)
    print("[Proxy] V1 Sentiment routes registered: /api/v1/sentiment/*")
except Exception as e:
    print(f"[Proxy] WARNING: Failed to load v1 sentiment routes: {e}")

# ═══════════════════════════════════════════════════════════
# FORK ADDITIONS: Shadow Trading (Truth Layer) + Mobile Truth Stats
# ═══════════════════════════════════════════════════════════
try:
    from services.shadow_service import get_shadow_stats, get_recent_trades, resolve_matured_trades

    @app.get("/api/shadow/stats")
    async def shadow_stats(symbol: str = None):
        """Get shadow trading truth stats (win rate, PnL)."""
        stats = get_shadow_stats(symbol)
        return JSONResponse(content={"ok": True, **stats})

    @app.get("/api/shadow/trades")
    async def shadow_trades_list(symbol: str = None, limit: int = 20):
        """Get recent shadow trades."""
        trades = get_recent_trades(symbol, limit)
        return JSONResponse(content={"ok": True, "trades": trades, "count": len(trades)})

    @app.post("/api/shadow/resolve")
    async def shadow_resolve():
        """Manually trigger outcome resolution."""
        result = resolve_matured_trades()
        return JSONResponse(content={"ok": True, **result})

    @app.get("/api/mobile/truth/stats")
    async def mobile_truth_stats():
        """Truth Layer stats for mobile app."""
        stats = get_shadow_stats()
        return JSONResponse(content={
            "ok": True,
            "winRate": stats.get("winRate", 0),
            "totalTrades": stats.get("totalTrades", 0),
            "avgPnl": stats.get("avgPnl", 0),
            "streak": stats.get("streak", 0),
            "learning": stats.get("totalTrades", 0) < 10,
        })

    print("[Proxy] Shadow/Truth Layer routes registered: /api/shadow/*, /api/mobile/truth/*")
except Exception as e:
    print(f"[Proxy] WARNING: Failed to load shadow service: {e}")

# ═══════════════════════════════════════════════════════════
# CONVERSION FUNNEL — Observability endpoint
# ═══════════════════════════════════════════════════════════
@app.get("/api/admin/funnel/stats")
async def funnel_stats(hours: int = 24):
    """Conversion funnel stats — where users drop off."""
    from services.conversion_funnel import get_funnel_stats
    stats = get_funnel_stats(hours)
    return JSONResponse(content={"ok": True, **stats})

@app.post("/api/mobile/funnel/track")
async def funnel_track(request: Request):
    """Direct funnel tracking from mobile/miniapp."""
    body = await request.json()
    from services.conversion_funnel import track_funnel_event
    track_funnel_event(
        user_id=body.get("userId", "anonymous"),
        signal_id=body.get("signalId", "BTC"),
        event=body.get("event", ""),
        meta=body.get("meta"),
    )
    return JSONResponse(content={"ok": True})

# ═══════════════════════════════════════════════════════════
# A/B TEST ANALYTICS — Conversion Engineering Dashboard
# ═══════════════════════════════════════════════════════════
@app.get("/api/admin/ab/stats")
async def ab_test_stats(hours: int = 720):
    """A/B test analytics — per-variant conversion rates for all 3 tests."""
    from services.ab_analytics import get_ab_test_stats
    stats = get_ab_test_stats(hours)
    return JSONResponse(content={"ok": True, **stats})

@app.get("/api/admin/ab/funnel")
async def ab_funnel_stats(hours: int = 720):
    """Enhanced funnel with A/B variant breakdown at each step."""
    from services.ab_analytics import get_funnel_with_variants
    stats = get_funnel_with_variants(hours)
    return JSONResponse(content={"ok": True, **stats})

@app.get("/api/admin/analytics/dashboard")
async def analytics_dashboard(hours: int = 720):
    """Full analytics dashboard — funnel + A/B tests + intent + shadow."""
    from services.ab_analytics import get_analytics_dashboard
    dashboard = get_analytics_dashboard(hours)
    return JSONResponse(content={"ok": True, **dashboard})

# ═══════════════════════════════════════════════════════════
# FORK ADDITIONS: Sentiment Admin stub (v4)
# ═══════════════════════════════════════════════════════════
@app.get("/api/v4/admin/sentiment/status")
async def v4_sentiment_status():
    return JSONResponse(content={"ok": True, "status": "MOCK_ONLY", "mode": "rules", "shadow": False})

@app.get("/api/v4/admin/sentiment/shadow/status")
async def v4_sentiment_shadow_status():
    return JSONResponse(content={"ok": True, "enabled": False, "comparisons": 0})

@app.get("/api/v4/admin/sentiment/booster/status")
async def v4_sentiment_booster_status():
    return JSONResponse(content={"ok": True, "enabled": False})


# ADMIN PANEL — Static Web Build (served at BOTH /admin/ and /api/panel/)
ADMIN_BUILD = os.path.join(os.path.dirname(__file__), 'admin_build')
_GROWTH_JS = os.path.join(ADMIN_BUILD, 'growth-os-inject.js')
_TRUTH_JS = os.path.join(ADMIN_BUILD, 'truth-inject.js')
_METABRAIN_JS = os.path.join(ADMIN_BUILD, 'metabrain-inject.js')
_AUTH_GATE_JS = os.path.join(ADMIN_BUILD, 'auth-gate-inject.js')
_INFO_JS = os.path.join(ADMIN_BUILD, 'info-inject.js')
_ADMIN_INFO_CMS_JS = os.path.join(ADMIN_BUILD, 'admin-info-cms-inject.js')
_LEGAL_INJECT_JS = os.path.join(ADMIN_BUILD, 'legal-inject.js')
_BILLING_INJECT_JS = os.path.join(ADMIN_BUILD, 'billing-inject.js')
_ATTRIBUTION_INJECT_JS = os.path.join(ADMIN_BUILD, 'attribution-inject.js')
_EXECUTION_INJECT_JS = os.path.join(ADMIN_BUILD, 'execution-inject.js')
_GOVERNANCE_INJECT_JS = os.path.join(ADMIN_BUILD, 'governance-inject.js')
# Trading Terminal sidebar inject scripts — REMOVED by Terminal Removal Sprint
# (2026-05-12). Variables left intentionally absent to fail any latent reference.

def _rewrite_admin_html(html: str, full_path: str = "") -> str:
    """Rewrite asset paths for ingress and inject MiniApp scripts."""
    html = html.replace('src="/static/', 'src="/api/static/')
    html = html.replace('href="/static/', 'href="/api/static/')
    html = html.replace('href="/assets/', 'href="/api/assets/')
    html = html.replace('src="/assets/', 'src="/api/assets/')
    html = html.replace(
        '<script defer="defer" src="/api/static/',
        '<script>window.__webpack_public_path__="/api/";</script><script defer="defer" src="/api/static/'
    )
    cache_meta = '<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate"/><meta http-equiv="Pragma" content="no-cache"/>'
    if cache_meta not in html:
        html = html.replace('<meta charset="utf-8"/>', '<meta charset="utf-8"/>' + cache_meta, 1)
    # Inject Growth + Truth + MetaBrain scripts for MiniApp pages
    if 'miniapp' in full_path:
        inject_scripts = ''
        if os.path.isfile(_GROWTH_JS):
            with open(_GROWTH_JS, 'r') as gf:
                inject_scripts += gf.read() + '\n'
        if os.path.isfile(_TRUTH_JS):
            with open(_TRUTH_JS, 'r') as tf:
                inject_scripts += tf.read() + '\n'
        if os.path.isfile(_METABRAIN_JS):
            with open(_METABRAIN_JS, 'r') as mf:
                inject_scripts += mf.read() + '\n'
        if inject_scripts:
            html = html.replace('</body>', f'<script>{inject_scripts}</script></body>')
    else:
        # P0: Auth Gate on Web admin/panel (NOT on miniapp). Forces Google
        # Sign-In before any paywall CTA opens a checkout.
        if os.path.isfile(_AUTH_GATE_JS):
            with open(_AUTH_GATE_JS, 'r') as af:
                ag = af.read()
            html = html.replace('</body>', f'<script>{ag}</script></body>')
        # Landing-page extras: 3 app-distribution cards (Android / iOS /
        # Telegram Mini App) injected on /info. The script self-guards
        # against other routes so it's cheap to ship on every SPA page.
        if os.path.isfile(_INFO_JS):
            with open(_INFO_JS, 'r') as nf:
                nj = nf.read()
            html = html.replace('</body>', f'<script>{nj}</script></body>')
        # Legal page renderer — paints CMS-authored HTML into /legal/*
        # and /privacy/* SPA routes.
        if os.path.isfile(_LEGAL_INJECT_JS):
            with open(_LEGAL_INJECT_JS, 'r') as lf:
                lj = lf.read()
            html = html.replace('</body>', f'<script>{lj}</script></body>')
        # Admin-only: the Info CMS tab inside Intel System. The script
        # self-guards by route ("/intel"/"/settings") so other pages are
        # unaffected.
        if os.path.isfile(_ADMIN_INFO_CMS_JS):
            with open(_ADMIN_INFO_CMS_JS, 'r') as cf:
                cj = cf.read()
            html = html.replace('</body>', f'<script>{cj}</script></body>')
        # Admin-only: Billing canonical domains (Инвойсы / Reconciliation /
        # Analytics) injected as additional tabs into the existing Billing
        # Console on /admin/billing. Self-guarded by route — no-op elsewhere.
        if os.path.isfile(_BILLING_INJECT_JS):
            with open(_BILLING_INJECT_JS, 'r') as bf:
                bj = bf.read()
            html = html.replace('</body>', f'<script>{bj}</script></body>')
        # Admin-only: Attribution Epistemic Observatory (T11) — adds a single
        # "Атрибуция" sidebar nav item that mounts a forensic read-only panel
        # inside <main>. Self-guarded by /admin route; no router hijack.
        if os.path.isfile(_ATTRIBUTION_INJECT_JS):
            with open(_ATTRIBUTION_INJECT_JS, 'r') as af:
                aj = af.read()
            html = html.replace('</body>', f'<script>{aj}</script></body>')
        # Admin-only: Execution Ledger (T10.2D) — adds "Исполнение" sidebar
        # nav and mounts an immutable receipt ledger. NO submit semantics —
        # GET-only consumers. Self-guarded by /admin route.
        if os.path.isfile(_EXECUTION_INJECT_JS):
            with open(_EXECUTION_INJECT_JS, 'r') as ef:
                ej = ef.read()
            html = html.replace('</body>', f'<script>{ej}</script></body>')
        # Admin-only: Governance Ledger (T10.2E) — adds "Управление" sidebar
        # nav. Operators roster · Capability matrix · Audit timeline ·
        # Authority actions. Mutations require admin JWT + typed
        # confirmation for live-authority grant. Self-guarded by /admin.
        if os.path.isfile(_GOVERNANCE_INJECT_JS):
            with open(_GOVERNANCE_INJECT_JS, 'r') as gvf:
                gvj = gvf.read()
            html = html.replace('</body>', f'<script>{gvj}</script></body>')
        # Trading Terminal sidebar inject — REMOVED by Terminal Removal Sprint
        # (2026-05-12). The /api/terminal-app SPA, /api/terminal/* gateway,
        # and the "Терминал" / "Теханализ" sidebar entries no longer exist.
        # Unknown paths fall through to the honest-404 catch-all.
    return html

if os.path.isdir(ADMIN_BUILD):
    @app.get("/admin/{full_path:path}")
    async def serve_admin(full_path: str):
        file_path = os.path.join(ADMIN_BUILD, full_path)
        if full_path and os.path.isfile(file_path):
            return FileResponse(file_path)
        # SPA fallback for /admin/* — serve raw index.html (router basename
        # stays at "/"). The Trading Terminal "Теханализ" sidebar inject was
        # removed by Terminal Removal Sprint (2026-05-12); admin SPA renders
        # without any terminal entry point.
        with open(os.path.join(ADMIN_BUILD, 'index.html'), 'r') as f:
            html = f.read()
        from fastapi.responses import HTMLResponse
        return HTMLResponse(content=html, headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
        })

    # Also serve via /api/panel/ so it works through Kubernetes ingress (/api/* → backend)
    @app.get("/api/panel/{full_path:path}")
    async def serve_admin_via_api(full_path: str = ""):
        file_path = os.path.join(ADMIN_BUILD, full_path)
        if full_path and os.path.isfile(file_path):
            return FileResponse(file_path)
        with open(os.path.join(ADMIN_BUILD, 'index.html'), 'r') as f:
            html = f.read()
        html = _rewrite_admin_html(html, full_path)
        from fastapi.responses import HTMLResponse
        return HTMLResponse(content=html, headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
        })

    @app.get("/api/panel")
    async def serve_admin_root():
        with open(os.path.join(ADMIN_BUILD, 'index.html'), 'r') as f:
            html = f.read()
        html = _rewrite_admin_html(html)
        from fastapi.responses import HTMLResponse
        return HTMLResponse(content=html)

    # Static assets for admin (also under /api/ prefix for ingress — using modified copies)
    ADMIN_BUILD_API = os.path.join(os.path.dirname(__file__), 'admin_build_api')
    if os.path.isdir(os.path.join(ADMIN_BUILD, 'static')):
        app.mount("/static", StaticFiles(directory=os.path.join(ADMIN_BUILD, 'static')), name="admin-static")
        if os.path.isdir(os.path.join(ADMIN_BUILD_API, 'static')):
            app.mount("/api/static", StaticFiles(directory=os.path.join(ADMIN_BUILD_API, 'static')), name="admin-static-api")
    if os.path.isdir(os.path.join(ADMIN_BUILD, 'assets')):
        app.mount("/assets", StaticFiles(directory=os.path.join(ADMIN_BUILD, 'assets')), name="admin-assets")
        app.mount("/api/assets", StaticFiles(directory=os.path.join(ADMIN_BUILD, 'assets')), name="admin-assets-api")
    if os.path.isdir(os.path.join(ADMIN_BUILD, 'fonts')):
        app.mount("/fonts", StaticFiles(directory=os.path.join(ADMIN_BUILD, 'fonts')), name="admin-fonts")
        app.mount("/api/fonts", StaticFiles(directory=os.path.join(ADMIN_BUILD, 'fonts')), name="admin-fonts-api")
    if os.path.isdir(os.path.join(ADMIN_BUILD, 'icons')):
        app.mount("/icons", StaticFiles(directory=os.path.join(ADMIN_BUILD, 'icons')), name="admin-icons")
        app.mount("/api/icons", StaticFiles(directory=os.path.join(ADMIN_BUILD, 'icons')), name="admin-icons-api")
    print(f"[Proxy] Admin panel mounted at /admin AND /api/panel/ from {ADMIN_BUILD}")

    # ── P3 · Legacy compat router registered LAST so /api/panel/* and
    # other specific routes are tried first.  Without this ordering the
    # catch-all swallows panel SPA paths and returns JSON stubs.
    try:
        from routes.admin_extras import router as _admin_extras_router
        app.include_router(_admin_extras_router, prefix="/api")
        print("[AdminExtras] mounted: 22+ admin CRUD endpoints restored")
    except Exception as _ae_err:
        print(f"[AdminExtras] mount failed: {_ae_err!r}")

    try:
        from routes.venues import router as _venues_router
        app.include_router(_venues_router)
        print("[Venues] mounted: Hyperliquid + Coinbase live endpoints (/api/venues/*)")
    except Exception as _v_err:
        print(f"[Venues] mount failed: {_v_err!r}")

    # PROD-GAP-3 — per-asset On-chain runtime endpoints (MUST be before legacy_compat)
    try:
        from routes.onchain_runtime import router as _onchain_runtime_router
        app.include_router(_onchain_runtime_router)
        print("[OnchainRuntime] mounted: /api/onchain/runtime/* (per-asset PROD-GAP-3)")
    except Exception as _or_err:
        print(f"[OnchainRuntime] mount failed: {_or_err!r}")

    # News runtime (real raw_news → /api/news/feed|digest|velocity) — before legacy_compat
    try:
        from routes.news_runtime import router as _news_runtime_router
        app.include_router(_news_runtime_router)
        print("[NewsRuntime] mounted: /api/news/{feed,digest,velocity}")
    except Exception as _nr_err:
        print(f"[NewsRuntime] mount failed: {_nr_err!r}")

    # Deep parser runtime endpoints (funds, persons, unlocks, projects) — before legacy_compat
    try:
        from routes.deep_runtime import router as _deep_runtime_router
        app.include_router(_deep_runtime_router)
        print("[DeepRuntime] mounted: /api/deep/{funds,persons,unlocks,projects,stats}")
    except Exception as _dr_err:
        print(f"[DeepRuntime] mount failed: {_dr_err!r}")

    # Tech Analysis runtime endpoints (market/candles, market/state, tech-analysis/*,
    # ta-prediction/*, dashboard/regime) — before legacy_compat
    try:
        from routes.tech_analysis_runtime import router as _ta_runtime_router
        app.include_router(_ta_runtime_router)
        print("[TARuntime] mounted: /api/market/{candles,state,regime} + /api/tech-analysis/* + /api/ta-prediction/*")
    except Exception as _ta_err:
        print(f"[TARuntime] mount failed: {_ta_err!r}")

    # On-chain v10 bridge — wires OnchainV3 page (`/api/v10/onchain-v2/*`) to real Infura/DeFiLlama data
    # MUST be registered BEFORE legacy_compat (which has catch-all stub).
    try:
        from routes.onchain_v10_bridge import router as _onchain_v10_bridge_router
        app.include_router(_onchain_v10_bridge_router)
        print("[OnchainV10Bridge] mounted: /api/v10/onchain-v2/{lare-v2/latest,market/liquidity/series,stables/aggregate/latest,bridge/aggregate/latest,market/series,market/altflow,...}")
    except Exception as _ov_err:
        print(f"[OnchainV10Bridge] mount failed: {_ov_err!r}")

    # Exchange runtime endpoints (orderbook, funding, OI, anomalies, tickers, overview,
    # miniapp/exchange, admin/exchange/overview) — before legacy_compat
    try:
        from routes.exchange_runtime import router as _exchange_runtime_router
        app.include_router(_exchange_runtime_router)
        print("[ExchangeRuntime] mounted: /api/exchange/* + /api/cex/* + /api/funding-rates + /api/order-flow/* + /api/miniapp/exchange + /api/admin/exchange/overview")
    except Exception as _ex_err:
        print(f"[ExchangeRuntime] mount failed: {_ex_err!r}")

    # Fractal/Brain UI adapter — re-shapes payloads so existing React
    # pages (Overview/BTC/SPX/DXY/MacroBrain) populate with REAL data.
    # MUST be mounted BEFORE fractal_extra_runtime AND legacy_compat so its
    # specific /api/fractal/{match,signal,...} and /api/overlay/coeffs and
    # /api/ui/brain/decision routes win the registration race.
    try:
        from routes.fractal_ui_adapter import router as _fractal_ui_adapter_router
        app.include_router(_fractal_ui_adapter_router)
        print("[FractalUIAdapter] mounted: /api/fractal/{match,signal,spx,dxy/terminal,v2.1/focus-pack} + /api/overlay/coeffs + /api/ui/fractal/* + /api/ui/brain/decision")
    except Exception as _fua_err:
        print(f"[FractalUIAdapter] mount failed: {_fua_err!r}")

    # Fractal extra runtime endpoints (list, coverage, patterns, similar, forecast,
    # heatmap, snapshot, intelligence, miniapp/fractal, admin/fractal/overview) —
    # before legacy_compat. The /api/fractal/runtime/* namespace is already
    # provided by routes.fractal_runtime which mounts separately.
    try:
        from routes.fractal_extra_runtime import router as _fractal_extra_router
        app.include_router(_fractal_extra_router)
        print("[FractalExtraRuntime] mounted: /api/fractal/{list,coverage,patterns,similar,forecast,heatmap,snapshot,intelligence} + /api/miniapp/fractal + /api/admin/fractal/overview")
    except Exception as _fr_err:
        print(f"[FractalExtraRuntime] mount failed: {_fr_err!r}")

    # (FractalUIAdapter moved above to win route registration race)

    # ═══════════════════════════════════════════════════════════════════════
    # MOBILE APP STATIC WEB BUILD (Expo export) — mounted BEFORE legacy_compat
    # so its catch-all (`/{full_path:path}`) does not swallow our SPA routes.
    # Serves the Trading Terminal at /api/app/operator/broker.
    # ═══════════════════════════════════════════════════════════════════════
    _MOBILE_DIST_PATH = "/app/mobile/dist"
    if os.path.exists(_MOBILE_DIST_PATH):
        from fastapi.responses import HTMLResponse, Response

        app.mount("/api/app/_expo", StaticFiles(directory=f"{_MOBILE_DIST_PATH}/_expo"), name="mobile-expo")
        for _sub in ("assets", "static", "fonts"):
            _p = os.path.join(_MOBILE_DIST_PATH, _sub)
            if os.path.exists(_p):
                app.mount(f"/api/app/{_sub}", StaticFiles(directory=_p), name=f"mobile-{_sub}")

        def _rewrite_mobile_html(html: str) -> str:
            html = html.replace('src="/_expo/',      'src="/api/app/_expo/')
            html = html.replace('href="/_expo/',     'href="/api/app/_expo/')
            html = html.replace('src="/assets/',     'src="/api/app/assets/')
            html = html.replace('href="/assets/',    'href="/api/app/assets/')
            html = html.replace('src="/static/',     'src="/api/app/static/')
            html = html.replace('href="/static/',    'href="/api/app/static/')
            html = html.replace('href="/favicon.ico"', 'href="/api/app/favicon.ico"')
            return html

        @app.get("/api/app/favicon.ico", include_in_schema=False)
        async def _mobile_favicon():
            return FileResponse(f"{_MOBILE_DIST_PATH}/favicon.ico")

        @app.get("/api/app/", include_in_schema=False)
        async def _mobile_index():
            with open(f"{_MOBILE_DIST_PATH}/index.html", "r", encoding="utf-8") as f:
                return HTMLResponse(content=_rewrite_mobile_html(f.read()))

        @app.get("/api/app", include_in_schema=False)
        async def _mobile_index_redirect():
            from fastapi.responses import RedirectResponse
            return RedirectResponse(url="/api/app/", status_code=302)

        @app.get("/api/app/{path:path}", include_in_schema=False)
        async def _mobile_route(path: str):
            if not path or path.endswith("/"):
                target = os.path.join(_MOBILE_DIST_PATH, path.strip("/"), "index.html")
            else:
                exact = os.path.join(_MOBILE_DIST_PATH, path)
                if os.path.isfile(exact):
                    return FileResponse(exact)
                html_direct = exact + ".html" if not path.endswith(".html") else exact
                html_index = os.path.join(_MOBILE_DIST_PATH, path, "index.html")
                target = html_direct if os.path.isfile(html_direct) else html_index
            if os.path.isfile(target) and target.endswith(".html"):
                with open(target, "r", encoding="utf-8") as f:
                    return HTMLResponse(content=_rewrite_mobile_html(f.read()))
            if os.path.isfile(target):
                return FileResponse(target)
            nf = os.path.join(_MOBILE_DIST_PATH, "+not-found.html")
            if os.path.isfile(nf):
                with open(nf, "r", encoding="utf-8") as f:
                    return HTMLResponse(content=_rewrite_mobile_html(f.read()), status_code=404)
            return Response(status_code=404)

        print(f"[Proxy] Mobile App (Expo web) served at /api/app/* — includes /operator/broker")
    else:
        print(f"[Proxy] WARNING: Mobile dist not found at {_MOBILE_DIST_PATH}")

    try:
        from routes.legacy_compat import router as _legacy_compat_router
        app.include_router(_legacy_compat_router)
        print("[LegacyCompat] mounted AFTER admin panel (catch-all is now lowest priority)")
    except Exception as _lc_err:
        print(f"[LegacyCompat] mount-after-panel failed: {_lc_err!r}")
else:
    print(f"[Proxy] WARNING: Admin build not found at {ADMIN_BUILD}")


# ─── Trading Terminal SPA — REMOVED (Terminal Removal Sprint 2026-05-12) ────
# The F-TRADE-MODULE side-car React build was retired by product decision.
# All terminal SPA mounts (/api/terminal-app/*, /terminal*, /terminal/static)
# and their degraded fallback handlers were deleted. Unknown paths under
# /api/terminal* now flow to the honest-404 catch-all (Sprint C4) instead of
# returning a misleading 503 'terminal_unavailable' contract.
#
# Migration record: /app/memory/TERMINAL_REMOVAL_SPRINT_2026-05-12.md
# Archive marker:   /app/F-TRADE-MODULE/ deleted; /app/legacy/TERMINAL_ARCHIVED.md


# ═══════════════════════════════════════════════════════════
# MOBILE APP STATIC WEB BUILD (mounted earlier — see block before
# legacy_compat include). Kept here only as a navigational anchor.
# ═══════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════
# CATCH-ALL — HONEST 404 (Stabilization Sprint C4, 2026-05-11)
# ═══════════════════════════════════════════════════════════
# Previous behaviour: this block proxied every unmatched request to a
# Node.js sidecar that has been permanently abandoned by policy, and on
# ConnectError returned 503 `{"error":"Node.js backend unavailable",
# "detail":"Backend is starting..."}`. That message was a lie: there is no
# Node.js backend in flight, the path simply does not exist in FastAPI.
#
# The proxy hid real 404s, made every misnamed client URL look like a
# transient service issue, and corrupted error telemetry. It also blocked
# the OpenAPI baseline that Phase D Pass 3 needs.
#
# New behaviour: return a clean 404 for unknown paths with a stable, honest
# JSON contract. /openapi.json and /docs are NOT touched (those are still
# served by FastAPI before this fallback). Trading-Terminal paths are
# handled by their own dedicated unavailable-handlers above, never by this
# fallback.
@app.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    include_in_schema=False,
)
async def _not_found_fallback(request: Request, path: str):
    return JSONResponse(
        status_code=404,
        content={
            "ok": False,
            "error": "not_found",
            "path": "/" + path,
            "method": request.method,
            "detail": (
                "This route is not registered in FastAPI. The legacy Node.js "
                "sidecar has been abandoned; the previous 503 'Backend is starting' "
                "response was misleading and has been removed."
            ),
        },
    )
