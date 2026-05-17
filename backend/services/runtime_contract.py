"""
Unified Runtime Contract — Phase D Pass 2 (2026-05-11)
======================================================

A single canonical *internal* shape for every cognition module so that
composers (observatory, /api/miniapp/home builder, frontend snapshots) can
consume them uniformly without each one re-doing field-by-field mapping.

CORE DISCIPLINE
---------------
1. Adapters are PURE: no DB I/O, no network calls, no recomputation,
   no `runtime_events.emit(...)`, no scheduler triggers. They only:
      normalize → validate → coerce → enforce discipline.
2. The contract is INTERNAL. Public API payloads (e.g. /api/miniapp/home)
   are NOT mutated by Pass 2 — adapters expose a *parallel* canonical view
   for composers. Pass 3 will refactor composition without changing wire
   shapes (golden snapshots in /app/memory/golden/ enforce this).
3. Truthful Degradation: every state that is not `active` carries
   `confidence=None` and `direction=None`. Adapters MUST NOT invent values
   to fill these.
4. Forbidden vocabulary is enforced centrally — see `validate_reasons()`.

CANONICAL SHAPE
---------------
    {
      "ok":         bool,            # is this snapshot semantically valid right now
      "state":      <STATE_ENUM>,    # see STATE_ENUM below
      "direction":  Optional[str],   # 'long' | 'short' | 'neutral' | None
      "confidence": Optional[float], # 0.0..1.0, None unless state == 'active'
      "reasons":    List[str],       # ordered snake_case reason codes
      "degraded":   bool,            # true when source is stale / partial / fallback
      "module":     str,             # cognition module id (ta|sentiment|fractal|shadow|...)
      "source":     str,             # provider / provenance (coingecko_30d|sentiment_events|...)
      "updatedAt":  str,             # ISO-8601 UTC, format 'YYYY-MM-DDTHH:MM:SSZ'
    }
"""

from __future__ import annotations

from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import Any, Iterable, List, Optional, Tuple

# ─────────────────────────────────────────────────────────────────────
# Enums (kept as frozen sets — DO NOT extend without architectural review)
# ─────────────────────────────────────────────────────────────────────

# Universal cognition states (Phase D Pass 2 — intentionally NOT business-domain).
# Domain semantics like 'blocked' / 'considered' / 'unresolved' belong to the
# shadow-runtime layer, NOT to the universal contract.
STATE_ENUM: frozenset = frozenset({
    "active",        # module is producing a usable, confident reading
    "wait",          # module is intact but holds (no actionable reading right now)
    "suppressed",    # module flags a non-deployment / restraint condition
    "insufficient",  # not enough substrate to produce any reading honestly
    "degraded",      # producer is unhealthy (rate limit / stale / fallback)
})

DIRECTION_ENUM: frozenset = frozenset({"long", "short", "neutral"})

KNOWN_MODULES: frozenset = frozenset({
    "ta",
    "sentiment",
    "fractal",
    "shadow",
    "outcome_memory",
    "paper",
    "observatory",
})

# Forbidden vocabulary in `reasons` (and any free-text fields adapters emit).
# Mirrors the platform-wide cognitive-restraint discipline: no marketing /
# pseudo-quantitative tokens that imply backtested edge or P&L narrative.
FORBIDDEN_REASON_TOKENS: frozenset = frozenset({
    "accuracy",
    "winrate",
    "win_rate",
    "roi",
    "pnl",
    "profit",
    "alpha",
    "edge",
    "success",
    "successful",
    "performance",
    "outperform",
    "outperforms",
    "winning",
    "winning_trade",
    "wins",
    "loss_rate",
    "sharpe",
    "sortino",
})

# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────


def utc_iso_now() -> str:
    """ISO-8601 UTC second-precision: 'YYYY-MM-DDTHH:MM:SSZ' — see A8."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def coerce_utc_iso(value: Any) -> str:
    """
    Normalize any datetime-ish input to canonical UTC ISO 'YYYY-MM-DDTHH:MM:SSZ'.
    Falls back to `utc_iso_now()` if value is None / unparseable.
    Adapters MUST route every timestamp through this — A8 acceptance.
    """
    if value is None:
        return utc_iso_now()
    if isinstance(value, datetime):
        dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if isinstance(value, (int, float)):
        # Treat as unix epoch seconds. Adapters that pass ms must divide first.
        try:
            return datetime.fromtimestamp(value, tz=timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
        except (OverflowError, OSError, ValueError):
            return utc_iso_now()
    if isinstance(value, str):
        # Accept already-normalized inputs as-is when they match the canonical pattern.
        s = value.strip()
        try:
            # fromisoformat handles 'YYYY-MM-DDTHH:MM:SS+00:00' and 'YYYY-MM-DDTHH:MM:SS'.
            # Strip trailing 'Z' (Python 3.11+ accepts it but 3.10 does not).
            if s.endswith("Z"):
                s = s[:-1] + "+00:00"
            dt = datetime.fromisoformat(s)
            if not dt.tzinfo:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            return utc_iso_now()
    return utc_iso_now()


def clamp_confidence(value: Any) -> Optional[float]:
    """Coerce confidence to [0.0, 1.0] float; return None on non-numeric input."""
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if f != f:  # NaN
        return None
    if f < 0.0:
        return 0.0
    if f > 1.0:
        return 1.0
    return round(f, 4)


def validate_reasons(reasons: Optional[Iterable[Any]]) -> List[str]:
    """
    Centralized discipline gate for `reasons`.

    Enforces:
      - reasons is a list of strings
      - each reason is snake_case-safe (lowercase, no spaces)
      - no forbidden vocabulary (accuracy/winrate/roi/pnl/profit/alpha/...)
      - de-duplication while preserving order
      - hard cap of 12 entries (composers should slice further if needed)

    Raises ValueError on any forbidden token. Callers (adapters) MUST NOT swallow
    this exception — it indicates a discipline breach in the source module that
    should be visible during development.
    """
    if reasons is None:
        return []
    out: List[str] = []
    seen: set = set()
    for raw in reasons:
        if raw is None:
            continue
        token = str(raw).strip().lower().replace(" ", "_").replace("-", "_")
        if not token:
            continue
        # Discipline check — forbidden tokens may appear anywhere in the reason
        # (e.g. 'high_winrate' must fail even though it's not equal to 'winrate').
        for forbidden in FORBIDDEN_REASON_TOKENS:
            if forbidden in token:
                raise ValueError(
                    f"runtime_contract: forbidden vocabulary in reason '{raw}' "
                    f"(matched '{forbidden}'). See runtime_contract.FORBIDDEN_REASON_TOKENS."
                )
        if token in seen:
            continue
        seen.add(token)
        out.append(token)
        if len(out) >= 12:
            break
    return out


def validate_state(state: Any) -> str:
    s = str(state or "").strip().lower()
    if s not in STATE_ENUM:
        raise ValueError(
            f"runtime_contract: invalid state '{state}'. "
            f"Allowed: {sorted(STATE_ENUM)}"
        )
    return s


def validate_direction(direction: Any) -> Optional[str]:
    if direction is None:
        return None
    d = str(direction).strip().lower()
    if d == "":
        return None
    if d not in DIRECTION_ENUM:
        raise ValueError(
            f"runtime_contract: invalid direction '{direction}'. "
            f"Allowed: {sorted(DIRECTION_ENUM)} or None"
        )
    return d


def validate_module(module: Any) -> str:
    m = str(module or "").strip().lower()
    if not m:
        raise ValueError("runtime_contract: module is required")
    # We do NOT hard-reject unknown module ids — only warn via shape check.
    # The KNOWN_MODULES set is descriptive, not exhaustive (paper/observatory
    # rollouts may legitimately add new ones in Pass 2B).
    return m


# ─────────────────────────────────────────────────────────────────────
# CognitionSnapshot — the canonical internal record
# ─────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class CognitionSnapshot:
    """
    Immutable canonical snapshot of one cognition module at one instant.

    Construct via `CognitionSnapshot.build(...)` — that route enforces all
    discipline (validate_state, validate_direction, validate_reasons,
    clamp_confidence, coerce_utc_iso). Direct dataclass construction is
    allowed but bypasses the discipline gate — only use it in tests where
    you intentionally want an invariant breach.
    """
    ok: bool
    state: str
    direction: Optional[str]
    confidence: Optional[float]
    reasons: Tuple[str, ...]
    degraded: bool
    module: str
    source: str
    updatedAt: str

    # ─── construction (the disciplined entry point) ─────────────────

    @classmethod
    def build(
        cls,
        *,
        module: str,
        source: str,
        state: str,
        direction: Any = None,
        confidence: Any = None,
        reasons: Optional[Iterable[Any]] = None,
        degraded: bool = False,
        ok: Optional[bool] = None,
        updatedAt: Any = None,
    ) -> "CognitionSnapshot":
        norm_state = validate_state(state)
        norm_direction = validate_direction(direction)
        norm_conf = clamp_confidence(confidence)
        norm_reasons = tuple(validate_reasons(reasons))
        norm_module = validate_module(module)
        norm_source = str(source or "").strip().lower() or "unknown"
        norm_ts = coerce_utc_iso(updatedAt)

        # Truthful-degradation invariants — adapters MUST NOT invent values
        # when the module is not actively producing.
        if norm_state != "active":
            norm_direction = None
            norm_conf = None

        # `ok` defaults to True for 'active' / 'wait' / 'suppressed' (intact
        # cognition surfaces), False for 'insufficient' / 'degraded'. Adapters
        # may override (e.g. shadow may be intact but degraded — still ok=True
        # with degraded=True).
        if ok is None:
            inferred_ok = norm_state not in ("insufficient", "degraded")
            norm_ok = inferred_ok
        else:
            norm_ok = bool(ok)

        # If state == 'degraded', the contract REQUIRES degraded=True (consistency).
        if norm_state == "degraded":
            degraded = True

        return cls(
            ok=norm_ok,
            state=norm_state,
            direction=norm_direction,
            confidence=norm_conf,
            reasons=norm_reasons,
            degraded=bool(degraded),
            module=norm_module,
            source=norm_source,
            updatedAt=norm_ts,
        )

    # ─── serialization ──────────────────────────────────────────────

    def to_dict(self) -> dict:
        """Public dict form. `reasons` is materialized as a list."""
        d = asdict(self)
        d["reasons"] = list(self.reasons)
        return d


# ─────────────────────────────────────────────────────────────────────
# Public convenience builders (most common cases)
# ─────────────────────────────────────────────────────────────────────


def make_insufficient(
    *, module: str, source: str, reasons: Optional[Iterable[str]] = None
) -> CognitionSnapshot:
    """
    Truthful empty-substrate snapshot. Use when a module legitimately cannot
    produce a reading (e.g. no decisions yet, no recent events).
    """
    return CognitionSnapshot.build(
        module=module,
        source=source,
        state="insufficient",
        reasons=reasons or ("insufficient_substrate",),
        degraded=False,
    )


def make_degraded(
    *, module: str, source: str, reasons: Optional[Iterable[str]] = None
) -> CognitionSnapshot:
    """Provider unhealthy / stale fallback / rate limited."""
    return CognitionSnapshot.build(
        module=module,
        source=source,
        state="degraded",
        reasons=reasons or ("source_degraded",),
        degraded=True,
    )


__all__ = [
    "STATE_ENUM",
    "DIRECTION_ENUM",
    "KNOWN_MODULES",
    "FORBIDDEN_REASON_TOKENS",
    "CognitionSnapshot",
    "utc_iso_now",
    "coerce_utc_iso",
    "clamp_confidence",
    "validate_reasons",
    "validate_state",
    "validate_direction",
    "validate_module",
    "make_insufficient",
    "make_degraded",
]
