#!/usr/bin/env python3
"""
DAILY ROLLING-FORECAST LOOP
============================
Runs `backfill_rolling_forecasts.py --days 5 --stride 1` every 6 hours
so the chart always has fresh past-belief snapshots covering the latest
days WITHOUT manual intervention.

This is the auto-incremental complement to the one-off backfill.
"""

from __future__ import annotations

import os
import time
import subprocess
from datetime import datetime, timezone

INTERVAL_SECONDS = int(os.environ.get("ROLLING_LOOP_INTERVAL", "21600"))  # 6h
SCRIPT = "/app/backend/scripts/backfill_rolling_forecasts.py"


def run_once():
    start = datetime.now(timezone.utc).isoformat()
    print(f"[rolling-loop] {start}  running incremental backfill (last 7d stride=1)", flush=True)
    try:
        r = subprocess.run(
            [
                "/root/.venv/bin/python3", SCRIPT,
                "--days", "7",       # update last 7 days each pass
                "--stride", "1",     # daily resolution for the recent tail
                "--horizon", "30",
                "--window", "120",
                "--topk", "10",
            ],
            capture_output=True, text=True, timeout=600,
        )
        print(r.stdout, flush=True)
        if r.returncode != 0:
            print(f"[rolling-loop] non-zero exit: {r.returncode}", flush=True)
            print(r.stderr, flush=True)
    except subprocess.TimeoutExpired:
        print("[rolling-loop] TIMEOUT (>600s)", flush=True)
    except Exception as e:
        print(f"[rolling-loop] ERROR: {e}", flush=True)


def main():
    print(f"[rolling-loop] starting (interval={INTERVAL_SECONDS}s)", flush=True)
    # First run immediately on startup
    run_once()
    while True:
        try:
            time.sleep(INTERVAL_SECONDS)
            run_once()
        except KeyboardInterrupt:
            print("[rolling-loop] stopping", flush=True)
            return


if __name__ == "__main__":
    main()
