"""
Unit tests for backend/services/runtime_contract.py — Phase D Pass 2.

Run from /app/backend:
    /root/.venv/bin/python3 -m pytest tests/test_runtime_contract.py -q
"""

from __future__ import annotations

import json
import pytest

from services.runtime_contract import (
    CognitionSnapshot,
    DIRECTION_ENUM,
    FORBIDDEN_REASON_TOKENS,
    STATE_ENUM,
    clamp_confidence,
    coerce_utc_iso,
    make_degraded,
    make_insufficient,
    utc_iso_now,
    validate_direction,
    validate_module,
    validate_reasons,
    validate_state,
)


# ─────────────────────────────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────────────────────────────


def test_state_enum_exact():
    assert STATE_ENUM == frozenset(
        {"active", "wait", "suppressed", "insufficient", "degraded"}
    )


def test_direction_enum_exact():
    assert DIRECTION_ENUM == frozenset({"long", "short", "neutral"})


def test_forbidden_tokens_contain_business_pollution():
    for token in ("accuracy", "winrate", "roi", "pnl", "profit", "alpha", "edge"):
        assert token in FORBIDDEN_REASON_TOKENS


# ─────────────────────────────────────────────────────────────────────
# Timestamps (A8 — must be 'YYYY-MM-DDTHH:MM:SSZ')
# ─────────────────────────────────────────────────────────────────────


def test_utc_iso_now_format():
    s = utc_iso_now()
    assert len(s) == 20 and s.endswith("Z")
    assert s[4] == "-" and s[7] == "-" and s[10] == "T" and s[13] == ":" and s[16] == ":"


def test_coerce_iso_passthrough_canonical():
    assert coerce_utc_iso("2026-05-11T20:30:00Z") == "2026-05-11T20:30:00Z"


def test_coerce_iso_handles_offset():
    assert coerce_utc_iso("2026-05-11T15:30:00-05:00") == "2026-05-11T20:30:00Z"


def test_coerce_iso_handles_naive_datetime():
    from datetime import datetime
    assert coerce_utc_iso(datetime(2026, 5, 11, 20, 30, 0)) == "2026-05-11T20:30:00Z"


def test_coerce_iso_handles_epoch_int():
    # 2026-01-01T00:00:00Z = 1767225600
    assert coerce_utc_iso(1767225600) == "2026-01-01T00:00:00Z"


def test_coerce_iso_unparseable_falls_back_to_now():
    s = coerce_utc_iso("not-a-date")
    assert len(s) == 20 and s.endswith("Z")


def test_coerce_iso_none_falls_back_to_now():
    s = coerce_utc_iso(None)
    assert len(s) == 20 and s.endswith("Z")


# ─────────────────────────────────────────────────────────────────────
# Confidence clamping
# ─────────────────────────────────────────────────────────────────────


def test_clamp_confidence_basic():
    assert clamp_confidence(0.5) == 0.5
    assert clamp_confidence(0) == 0.0
    assert clamp_confidence(1) == 1.0


def test_clamp_confidence_out_of_range():
    assert clamp_confidence(-0.1) == 0.0
    assert clamp_confidence(1.5) == 1.0


def test_clamp_confidence_non_numeric():
    assert clamp_confidence(None) is None
    assert clamp_confidence("abc") is None
    assert clamp_confidence(float("nan")) is None


# ─────────────────────────────────────────────────────────────────────
# validate_reasons — centralized discipline gate
# ─────────────────────────────────────────────────────────────────────


def test_validate_reasons_basic():
    assert validate_reasons(["high_volatility", "shadow_active"]) == [
        "high_volatility",
        "shadow_active",
    ]


def test_validate_reasons_dedupe_preserve_order():
    assert validate_reasons(["a", "b", "a", "c", "b"]) == ["a", "b", "c"]


def test_validate_reasons_lowercase_snake():
    assert validate_reasons(["High Vol", "Shadow-Active"]) == [
        "high_vol",
        "shadow_active",
    ]


def test_validate_reasons_caps_at_12():
    assert len(validate_reasons([f"r{i}" for i in range(50)])) == 12


def test_validate_reasons_none_and_empty():
    assert validate_reasons(None) == []
    assert validate_reasons([]) == []
    assert validate_reasons([None, "", "  "]) == []


@pytest.mark.parametrize(
    "bad_reason",
    [
        "accuracy",
        "high_accuracy",
        "winrate",
        "win_rate",
        "high_winrate",
        "roi",
        "expected_roi",
        "pnl",
        "neg_pnl",
        "profit",
        "profitable",
        "alpha",
        "negative_alpha",
        "success",
        "successful_trade",
        "sharpe",
    ],
)
def test_validate_reasons_rejects_forbidden(bad_reason):
    with pytest.raises(ValueError, match="forbidden vocabulary"):
        validate_reasons([bad_reason])


# ─────────────────────────────────────────────────────────────────────
# validate_state / direction / module
# ─────────────────────────────────────────────────────────────────────


def test_validate_state_all_enum_values():
    for s in STATE_ENUM:
        assert validate_state(s) == s


def test_validate_state_rejects_business_semantic():
    # Per architectural decision Pass 2: blocked/considered/unresolved are
    # shadow-runtime domain concepts, NOT universal cognition states.
    for s in ("blocked", "considered", "unresolved", "neutral", ""):
        with pytest.raises(ValueError):
            validate_state(s)


def test_validate_direction_enum():
    assert validate_direction("long") == "long"
    assert validate_direction("SHORT") == "short"
    assert validate_direction("Neutral") == "neutral"
    assert validate_direction(None) is None
    assert validate_direction("") is None


def test_validate_direction_rejects_unknown():
    with pytest.raises(ValueError):
        validate_direction("up")


def test_validate_module_basic():
    assert validate_module("ta") == "ta"
    assert validate_module(" Sentiment ") == "sentiment"


def test_validate_module_requires_non_empty():
    with pytest.raises(ValueError):
        validate_module("")


# ─────────────────────────────────────────────────────────────────────
# CognitionSnapshot.build — discipline gate
# ─────────────────────────────────────────────────────────────────────


def test_snapshot_active_full():
    s = CognitionSnapshot.build(
        module="ta",
        source="coingecko_30d",
        state="active",
        direction="long",
        confidence=0.78,
        reasons=["trend_aligned", "volume_above_avg"],
        degraded=False,
    )
    d = s.to_dict()
    assert d["ok"] is True
    assert d["state"] == "active"
    assert d["direction"] == "long"
    assert d["confidence"] == 0.78
    assert d["reasons"] == ["trend_aligned", "volume_above_avg"]
    assert d["degraded"] is False
    assert d["module"] == "ta"
    assert d["source"] == "coingecko_30d"
    assert d["updatedAt"].endswith("Z")


def test_snapshot_wait_strips_direction_and_confidence():
    # Truthful Degradation: state != active => direction = None, confidence = None
    s = CognitionSnapshot.build(
        module="sentiment",
        source="sentiment_events",
        state="wait",
        direction="long",       # adapter passed it but must be stripped
        confidence=0.9,         # ditto
        reasons=["no_alignment_threshold"],
    )
    d = s.to_dict()
    assert d["direction"] is None
    assert d["confidence"] is None
    assert d["state"] == "wait"
    assert d["ok"] is True       # 'wait' is intact cognition


def test_snapshot_suppressed_truthful():
    s = CognitionSnapshot.build(
        module="shadow",
        source="shadow_verdicts",
        state="suppressed",
        direction="long",
        confidence=0.5,
        reasons=["operator_restraint_active", "regime_unstable"],
    )
    d = s.to_dict()
    assert d["state"] == "suppressed"
    assert d["direction"] is None
    assert d["confidence"] is None
    assert d["ok"] is True


def test_snapshot_insufficient_default_ok_false():
    s = CognitionSnapshot.build(
        module="fractal",
        source="fractal_events",
        state="insufficient",
    )
    d = s.to_dict()
    assert d["ok"] is False
    assert d["direction"] is None
    assert d["confidence"] is None
    assert d["degraded"] is False


def test_snapshot_degraded_forces_degraded_flag():
    s = CognitionSnapshot.build(
        module="ta",
        source="coingecko_30d",
        state="degraded",
        degraded=False,           # adapter forgot to set it — contract MUST force True
        reasons=["upstream_429"],
    )
    d = s.to_dict()
    assert d["state"] == "degraded"
    assert d["degraded"] is True
    assert d["ok"] is False


def test_snapshot_explicit_ok_override():
    s = CognitionSnapshot.build(
        module="shadow",
        source="shadow_verdicts",
        state="degraded",
        ok=True,                  # explicit override allowed (intact w/ stale source)
        reasons=["stale_substrate"],
    )
    assert s.ok is True
    assert s.degraded is True


def test_snapshot_to_dict_is_json_serializable():
    s = CognitionSnapshot.build(
        module="ta",
        source="coingecko_30d",
        state="active",
        direction="long",
        confidence=0.55,
        reasons=["a", "b"],
    )
    assert json.loads(json.dumps(s.to_dict()))["module"] == "ta"


def test_snapshot_is_immutable():
    s = CognitionSnapshot.build(module="ta", source="x", state="wait")
    with pytest.raises(Exception):
        s.ok = False  # type: ignore[misc]


def test_snapshot_reasons_pollution_raises():
    with pytest.raises(ValueError, match="forbidden vocabulary"):
        CognitionSnapshot.build(
            module="ta",
            source="coingecko_30d",
            state="active",
            direction="long",
            confidence=0.7,
            reasons=["high_winrate"],   # forbidden — must blow up loudly
        )


# ─────────────────────────────────────────────────────────────────────
# Convenience builders
# ─────────────────────────────────────────────────────────────────────


def test_make_insufficient_defaults():
    s = make_insufficient(module="fractal", source="fractal_events")
    d = s.to_dict()
    assert d["state"] == "insufficient"
    assert d["ok"] is False
    assert d["reasons"] == ["insufficient_substrate"]
    assert d["degraded"] is False


def test_make_degraded_defaults():
    s = make_degraded(module="ta", source="coingecko_30d")
    d = s.to_dict()
    assert d["state"] == "degraded"
    assert d["degraded"] is True
    assert d["ok"] is False
    assert d["reasons"] == ["source_degraded"]


# ─────────────────────────────────────────────────────────────────────
# Adapter discipline (A7) — purity / no side effects
# ─────────────────────────────────────────────────────────────────────


def test_runtime_contract_module_has_no_io_imports():
    """
    A7 — adapters built on runtime_contract MUST NOT import DB/network surfaces.
    The contract module itself is the canonical reference for purity.
    """
    import services.runtime_contract as rc
    src = open(rc.__file__).read()
    forbidden_imports = [
        "import pymongo",
        "import motor",
        "import httpx",
        "import requests",
        "from pymongo",
        "from motor",
        "from httpx",
        "from requests",
        "import asyncio",
        "from db",
    ]
    for bad in forbidden_imports:
        assert bad not in src, f"runtime_contract.py must not contain `{bad}`"
