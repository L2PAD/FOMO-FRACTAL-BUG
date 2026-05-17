"""
outcome_resolver_scheduler — Phase B · Step 3.

Quiet background memory-maintenance layer.

NOT trading automation.  NOT signal generation.  NOT sweep automation.
NOT paper execution.  NOT broker integration.  NOT UI push channel.

Sole purpose: periodically transition mature `pending` outcomes in
`mbrain_integrity_outcomes` to `resolved` or `expired` by invoking the
existing `outcome_memory.resolve_outcomes()` function.

Discipline rules (enforced):
    • Disabled by default (`OUTCOME_RESOLVER_ENABLED=false`)
    • Manual control endpoints remain authoritative
    • Only resolves; NEVER sweeps, NEVER creates outcomes
    • No mutation of decision_history
    • No synthetic prices — relies entirely on existing market_reality
      fetcher in outcome_memory (returns None → expired honestly)
    • No frontend push channel; status is pull-only
    • Background task is cancelable; double-enable is a no-op
"""
from __future__ import annotations

import asyncio
import os
import threading
from collections import deque
from datetime import datetime, timezone
from typing import Deque, Dict, Optional


# ─── Tuning (env-driven) ───────────────────────────────────────────────
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


INITIAL_ENABLED = _env_bool("OUTCOME_RESOLVER_ENABLED", False)
INTERVAL_MIN = max(1, _env_int("OUTCOME_RESOLVER_INTERVAL_MIN", 15))
RESOLVE_BATCH_LIMIT = max(1, _env_int("OUTCOME_RESOLVER_BATCH_LIMIT", 200))
RUN_HISTORY_CAP = 25


# ─── State (process-local; not persisted to Mongo) ─────────────────────
class _SchedulerState:
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.enabled: bool = INITIAL_ENABLED
        self.interval_seconds: int = INTERVAL_MIN * 60
        self.batch_limit: int = RESOLVE_BATCH_LIMIT
        self.started_at: Optional[str] = None
        self.last_run_at: Optional[str] = None
        self.next_run_eta: Optional[str] = None
        self.runs_total: int = 0
        self.errors_total: int = 0
        self.last_result: Optional[dict] = None
        self.history: Deque[dict] = deque(maxlen=RUN_HISTORY_CAP)
        self.task: Optional[asyncio.Task] = None
        self.stop_event: Optional[asyncio.Event] = None
        self.created_at_iso = datetime.now(timezone.utc).isoformat()


_state = _SchedulerState()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─── Resolver core (delegates to outcome_memory) ───────────────────────
def _do_resolve_once(limit: int) -> dict:
    """Run a single resolution pass via outcome_memory.resolve_outcomes.

    Never sweeps.  Never creates outcomes.  Honest pass-through of the
    underlying resolver result + timestamp.
    """
    try:
        from services.outcome_memory import resolve_outcomes  # type: ignore
    except Exception as e:
        return {
            "ok": False,
            "reason": f"resolver_unavailable: {e!r}",
            "asOf": _now_iso(),
        }
    try:
        result = resolve_outcomes(limit)
        result["scheduledAt"] = _now_iso()
        return result
    except Exception as e:
        return {
            "ok": False,
            "reason": f"resolver_exception: {e!r}",
            "scheduledAt": _now_iso(),
        }


def _record_run(result: dict) -> None:
    with _state.lock:
        _state.last_run_at = _now_iso()
        _state.runs_total += 1
        if not result.get("ok", False):
            _state.errors_total += 1
        _state.last_result = result
        _state.history.appendleft({
            "at": _state.last_run_at,
            "ok": bool(result.get("ok", False)),
            "resolved": int(result.get("resolved", 0) or 0),
            "expired": int(result.get("expired", 0) or 0),
            "errors": int(result.get("errors", 0) or 0),
        })


# ─── Loop ──────────────────────────────────────────────────────────────
async def _loop() -> None:
    """Background loop.  Cancelable via stop_event."""
    with _state.lock:
        _state.started_at = _now_iso()
    try:
        while True:
            # Recompute next ETA each iteration
            with _state.lock:
                interval = _state.interval_seconds
                _state.next_run_eta = datetime.fromtimestamp(
                    datetime.now(timezone.utc).timestamp() + interval, tz=timezone.utc,
                ).isoformat()

            try:
                result = await asyncio.to_thread(_do_resolve_once, _state.batch_limit)
                _record_run(result)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                _record_run({"ok": False, "reason": f"loop_exception: {e!r}"})

            # Sleep with cancel responsiveness
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


# ─── Public control ────────────────────────────────────────────────────
def enable_scheduler() -> dict:
    """Enable the background loop.  Idempotent (double-enable is no-op)."""
    with _state.lock:
        if _state.enabled and _state.task and not _state.task.done():
            return {"ok": True, "alreadyEnabled": True, "asOf": _now_iso()}

        try:
            loop = asyncio.get_event_loop()
            if not loop.is_running():
                return {
                    "ok": False,
                    "reason": "event_loop_not_running",
                    "asOf": _now_iso(),
                }
        except RuntimeError:
            return {
                "ok": False,
                "reason": "no_event_loop",
                "asOf": _now_iso(),
            }

        _state.enabled = True
        _state.stop_event = asyncio.Event()
        _state.task = asyncio.create_task(_loop())
        return {
            "ok": True,
            "enabled": True,
            "intervalMin": INTERVAL_MIN,
            "asOf": _now_iso(),
        }


def disable_scheduler() -> dict:
    """Disable the background loop.  Idempotent."""
    with _state.lock:
        if not _state.enabled:
            return {"ok": True, "alreadyDisabled": True, "asOf": _now_iso()}
        _state.enabled = False
        if _state.stop_event:
            try:
                _state.stop_event.set()
            except Exception:
                pass
        if _state.task and not _state.task.done():
            _state.task.cancel()
        _state.task = None
        _state.stop_event = None
        _state.next_run_eta = None
        return {"ok": True, "enabled": False, "asOf": _now_iso()}


def run_once() -> dict:
    """Run a single resolution pass synchronously.  Manual fallback —
    always available regardless of scheduler enabled state."""
    result = _do_resolve_once(_state.batch_limit)
    _record_run(result)
    return result


def status() -> dict:
    with _state.lock:
        task_alive = bool(_state.task and not _state.task.done())
        return {
            "ok": True,
            "enabled": bool(_state.enabled),
            "running": task_alive,
            "intervalMin": INTERVAL_MIN,
            "batchLimit": _state.batch_limit,
            "startedAt": _state.started_at,
            "lastRunAt": _state.last_run_at,
            "nextRunEta": _state.next_run_eta if task_alive else None,
            "runsTotal": int(_state.runs_total),
            "errorsTotal": int(_state.errors_total),
            "lastResult": _state.last_result,
            "history": list(_state.history),
            "createdAtIso": _state.created_at_iso,
            "asOf": _now_iso(),
            "note": (
                "memory maintenance only — resolves mature pending outcomes. "
                "does NOT sweep, does NOT mutate decisions, does NOT execute trades."
            ),
        }


async def bootstrap_if_enabled() -> None:
    """Called from FastAPI startup.  If env flag is set, enable the loop
    inside the running event loop."""
    if INITIAL_ENABLED:
        enable_scheduler()
