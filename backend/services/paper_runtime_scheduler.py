"""
paper_runtime_scheduler — T3 · continuous paper-trading evaluator.

Background asyncio loop that periodically calls
`trading_runtime.evaluate_stop_target_hits()` to auto-close OPEN paper
positions whose stop or target was hit.

Mirrors the disciplined pattern of `outcome_resolver_scheduler.py`:
  * env-gated default (PAPER_EVAL_ENABLED, default true)
  * interval via PAPER_EVAL_INTERVAL_SEC (default 60s)
  * cancelable via asyncio Event (no zombie tasks on reload)
  * double-enable is a no-op (idempotent control)
  * stat history (last 25 runs)
  * NEVER opens positions, NEVER mutates verdict, NEVER calls broker
"""
from __future__ import annotations

import asyncio
import logging
import os
import threading
from collections import deque
from datetime import datetime, timezone
from typing import Deque, Optional

logger = logging.getLogger("paper_runtime_scheduler")


def _env_bool(name: str, default: bool) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return str(v).strip().lower() in {"1", "true", "yes", "on", "y"}


def _env_int(name: str, default: int) -> int:
    v = os.environ.get(name)
    if v is None:
        return default
    try:
        return int(v)
    except Exception:
        return default


INITIAL_ENABLED = _env_bool("PAPER_EVAL_ENABLED", True)
INTERVAL_SEC = max(5, _env_int("PAPER_EVAL_INTERVAL_SEC", 60))
RUN_HISTORY_CAP = 25


class _SchedulerState:
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.enabled: bool = INITIAL_ENABLED
        self.interval_seconds: int = INTERVAL_SEC
        self.started_at: Optional[str] = None
        self.last_run_at: Optional[str] = None
        self.next_run_eta: Optional[str] = None
        self.runs_total: int = 0
        self.closes_total: int = 0
        self.errors_total: int = 0
        self.last_result: Optional[dict] = None
        self.history: Deque[dict] = deque(maxlen=RUN_HISTORY_CAP)
        self.task: Optional[asyncio.Task] = None
        self.stop_event: Optional[asyncio.Event] = None
        self.created_at_iso = datetime.now(timezone.utc).isoformat()


_state = _SchedulerState()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _do_evaluate_once() -> dict:
    """Single evaluation pass via trading_runtime.evaluate_stop_target_hits."""
    try:
        from services.trading_runtime import evaluate_stop_target_hits  # type: ignore
    except Exception as e:
        return {"ok": False, "reason": f"evaluator_unavailable: {e!r}", "asOf": _now_iso()}
    try:
        return evaluate_stop_target_hits()
    except Exception as e:
        return {"ok": False, "reason": f"evaluator_exception: {e!r}", "asOf": _now_iso()}


def _record_run(result: dict) -> None:
    with _state.lock:
        _state.last_run_at = _now_iso()
        _state.runs_total += 1
        if not result.get("ok", False):
            _state.errors_total += 1
        else:
            _state.closes_total += int(result.get("count", 0) or 0)
        _state.last_result = result
        _state.history.appendleft({
            "at": _state.last_run_at,
            "ok": bool(result.get("ok", False)),
            "scanned": int(result.get("scanned", 0) or 0),
            "closed": int(result.get("count", 0) or 0),
            "barUsed": int(result.get("barUsed", 0) or 0),
            "tickUsed": int(result.get("tickUsed", 0) or 0),
        })


async def _loop() -> None:
    """Background loop. Cancelable via stop_event."""
    with _state.lock:
        _state.started_at = _now_iso()
    logger.info(f"[paper_runtime_scheduler] loop start, interval={_state.interval_seconds}s")
    try:
        while True:
            with _state.lock:
                interval = _state.interval_seconds
                _state.next_run_eta = datetime.fromtimestamp(
                    datetime.now(timezone.utc).timestamp() + interval, tz=timezone.utc,
                ).isoformat()

            try:
                result = await asyncio.to_thread(_do_evaluate_once)
                _record_run(result)
                if result.get("count", 0):
                    logger.info(
                        f"[paper_runtime_scheduler] tick closed {result['count']} "
                        f"(scanned={result.get('scanned', 0)}, bar={result.get('barUsed', 0)}, tick={result.get('tickUsed', 0)})"
                    )
            except asyncio.CancelledError:
                raise
            except Exception as e:
                _record_run({"ok": False, "reason": f"loop_exception: {e!r}"})

            stop_event = _state.stop_event
            if stop_event is None:
                await asyncio.sleep(interval)
            else:
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=interval)
                    if stop_event.is_set():
                        break
                except asyncio.TimeoutError:
                    pass
    except asyncio.CancelledError:
        pass
    finally:
        with _state.lock:
            _state.next_run_eta = None
            _state.started_at = None
        logger.info("[paper_runtime_scheduler] loop stopped")


def enable_scheduler() -> dict:
    """Start the background loop. Idempotent."""
    with _state.lock:
        if _state.task and not _state.task.done():
            return {"ok": True, "alreadyEnabled": True, "asOf": _now_iso()}

        try:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.get_event_loop()
            if not loop.is_running():
                return {
                    "ok": False,
                    "reason": "event_loop_not_running",
                    "asOf": _now_iso(),
                }
            _state.stop_event = asyncio.Event()
            _state.task = loop.create_task(_loop())
            _state.enabled = True
        except Exception as e:
            return {"ok": False, "reason": f"start_failed: {e!r}", "asOf": _now_iso()}
    return {"ok": True, "enabled": True, "asOf": _now_iso()}


def disable_scheduler() -> dict:
    """Stop the background loop. Idempotent."""
    with _state.lock:
        if not (_state.task and not _state.task.done()):
            _state.enabled = False
            return {"ok": True, "alreadyDisabled": True, "asOf": _now_iso()}
        try:
            if _state.stop_event is not None:
                _state.stop_event.set()
            _state.enabled = False
        except Exception as e:
            return {"ok": False, "reason": f"stop_failed: {e!r}", "asOf": _now_iso()}
    return {"ok": True, "disabled": True, "asOf": _now_iso()}


def status() -> dict:
    with _state.lock:
        running = bool(_state.task and not _state.task.done())
        return {
            "ok": True,
            "enabled": _state.enabled,
            "running": running,
            "intervalSeconds": _state.interval_seconds,
            "startedAt": _state.started_at,
            "lastRunAt": _state.last_run_at,
            "nextRunEta": _state.next_run_eta,
            "runsTotal": _state.runs_total,
            "closesTotal": _state.closes_total,
            "errorsTotal": _state.errors_total,
            "lastResult": _state.last_result,
            "history": list(_state.history),
            "asOf": _now_iso(),
        }


def force_run_once() -> dict:
    """Synchronous one-off run — useful for tests / manual debugging."""
    result = _do_evaluate_once()
    _record_run(result)
    return result


async def bootstrap() -> dict:
    """Called at FastAPI startup. Auto-enables if INITIAL_ENABLED."""
    if INITIAL_ENABLED:
        return enable_scheduler()
    return {"ok": True, "enabled": False, "reason": "PAPER_EVAL_ENABLED=false"}
