"""
News Substrate Periodic Loop
============================
Long-running supervisor-managed worker.
Runs `run_news_substrate.py` (full RSS + ChainBroker + orchestrator +
VADER scorer pipeline) every NEWS_SUBSTRATE_INTERVAL_SEC seconds
(default: 900 s = 15 min).

Fail-safe: any exception in a tick is logged but the loop continues.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

# Reuse the single-shot substrate runner
from scripts import run_news_substrate as substrate  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(message)s",
)
log = logging.getLogger("news_substrate_loop")


def _interval() -> int:
    try:
        v = int(os.environ.get("NEWS_SUBSTRATE_INTERVAL_SEC", "900"))
        return max(120, v)
    except Exception:
        return 900


async def _loop() -> None:
    interval = _interval()
    log.info(f"=== news-substrate loop START | interval={interval}s ===")
    # initial small delay so we don't compete with backend startup
    await asyncio.sleep(20)

    while True:
        started = time.time()
        try:
            await substrate.main()
        except Exception:
            log.error("substrate tick crashed:\n" + traceback.format_exc())

        elapsed = time.time() - started
        sleep_for = max(15, interval - int(elapsed))
        log.info(f"--- tick done in {elapsed:.1f}s, next tick in {sleep_for}s ---")
        await asyncio.sleep(sleep_for)


def main() -> None:
    flag = os.environ.get("NEWS_SUBSTRATE_ENABLED", "true").strip().lower()
    if flag in ("0", "false", "no", "off"):
        log.warning(
            "NEWS_SUBSTRATE_ENABLED is falsy — exiting without scheduling loop."
        )
        return
    try:
        asyncio.run(_loop())
    except KeyboardInterrupt:
        log.info("loop interrupted, exiting cleanly")


if __name__ == "__main__":
    main()
