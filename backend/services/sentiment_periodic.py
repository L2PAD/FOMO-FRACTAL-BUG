"""
Sentiment periodic ingestion loop — TRADING-ACTIVATION-2.

Calls run_sentiment_ingestion() from sentiment_service every
SENTIMENT_PERIODIC_INTERVAL_SEC seconds (default: 15 minutes).

Sources used (own multi-source pressure model, NOT Emergent LLM):
  - Fear & Greed Index (Alternative.me, FREE)
  - CoinGecko community sentiment (FREE)
  - News headlines via CoinGecko Trending (FREE)

Explicitly does NOT call:
  - sentiment_model.backfill_events (uses Emergent LLM)
  - cron_ingestion full pipeline (includes LLM stage)

This loop is fail-safe — exceptions are caught and logged.
The next tick continues regardless of previous tick outcome.
"""

import asyncio
import os
from datetime import datetime, timezone


_DEFAULT_INTERVAL_SEC = 15 * 60  # 15 minutes
_DEFAULT_ASSETS = ["BTC", "ETH", "SOL"]


def _interval() -> int:
    try:
        v = int(os.environ.get("SENTIMENT_PERIODIC_INTERVAL_SEC", _DEFAULT_INTERVAL_SEC))
        # Floor at 60s — avoid accidental flood
        return max(60, v)
    except Exception:
        return _DEFAULT_INTERVAL_SEC


async def run_once() -> dict:
    """Single tick — kept public for manual triggers / admin endpoint."""
    from services.sentiment_service import run_sentiment_ingestion
    started = datetime.now(timezone.utc)
    try:
        result = await run_sentiment_ingestion(_DEFAULT_ASSETS)
        return {
            "ok": True,
            "ts": started.isoformat(),
            "result": result,
        }
    except Exception as exc:
        return {
            "ok": False,
            "ts": started.isoformat(),
            "error": repr(exc),
        }


async def _loop():
    interval = _interval()
    print(f"[SentimentPeriodic] starting loop interval={interval}s assets={_DEFAULT_ASSETS}")
    # Initial small delay so we don't compete with startup
    await asyncio.sleep(30)
    while True:
        try:
            tick = await run_once()
            status = "ok" if tick.get("ok") else "FAIL"
            print(f"[SentimentPeriodic] {tick.get('ts')} {status} {tick.get('result') or tick.get('error')}")
        except Exception as exc:
            # Defensive — should not happen because run_once catches its own
            print(f"[SentimentPeriodic] loop error: {exc!r}")
        try:
            await asyncio.sleep(interval)
        except asyncio.CancelledError:
            print("[SentimentPeriodic] loop cancelled")
            raise


def start_loop_if_enabled() -> dict:
    """
    Schedule the periodic loop as a background task.

    Disabled iff SENTIMENT_PERIODIC_ENABLED is explicitly set to a falsy
    value. Default is enabled (we want freshness by default once the
    system has been activated).
    """
    flag = os.environ.get("SENTIMENT_PERIODIC_ENABLED", "true").strip().lower()
    if flag in ("0", "false", "no", "off", ""):
        print("[SentimentPeriodic] disabled by SENTIMENT_PERIODIC_ENABLED")
        return {"started": False, "reason": "disabled_by_flag"}
    task = asyncio.create_task(_loop())
    return {"started": True, "task": task, "interval_sec": _interval()}
