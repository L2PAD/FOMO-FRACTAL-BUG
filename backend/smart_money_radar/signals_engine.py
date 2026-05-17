"""
Smart Money Signal Engine + Conviction
========================================
Sprint 1.6: Generates conviction-scored signals from Brain + Patterns + Events + Routes.

Each signal is a UNIQUE event (not per token), with its own conviction score.

conviction = brain_score * 0.3 + pattern_strength * 0.25 + cluster_size * 0.2 + flow_size * 0.15 + timing_score * 0.1
"""

import hashlib
import math
from .brain import get_brain_signals
from .patterns import get_patterns
from .service import get_radar_events, _fmt_usd, cache_get, cache_set


def _signal_id(token: str, signal_type: str, extra: str = "") -> str:
    raw = f"{token}:{signal_type}:{extra}"
    return f"s_{hashlib.md5(raw.encode()).hexdigest()[:8]}"


def _conviction(brain_score: float, pattern_str: float, cluster_sz: int, flow_usd: float, timing: float) -> int:
    bs = min(100, max(0, brain_score)) * 0.30
    ps = min(100, max(0, pattern_str)) * 0.25
    cs = min(100, min(cluster_sz, 20) / 20 * 100) * 0.20
    fs = min(100, (math.log10(max(abs(flow_usd), 1)) / 8) * 100) * 0.15
    ts = min(100, max(0, (timing + 10) / 25 * 100)) * 0.10
    return int(min(99, max(5, bs + ps + cs + fs + ts)))


def get_signals(chain_id: int = 1, window: str = "24h", limit: int = 15) -> list:
    ck = f"signals:{chain_id}:{window}:{limit}"
    cached = cache_get(ck)
    if cached is not None:
        return cached

    brain = get_brain_signals(chain_id=chain_id, window=window, limit=15)
    patterns = get_patterns(chain_id=chain_id, window=window, limit=15)
    events = get_radar_events(chain_id=chain_id, window=window, sort_by="confidence", limit=20)

    brain_map = {b["token"]: b for b in brain}
    signals = []

    # --- Signals from Patterns (strongest source) ---
    for p in patterns:
        token = p.get("token", "")
        ptype = p.get("pattern_type", "unknown")
        bs = brain_map.get(token, {})
        brain_score = bs.get("alpha_score", 40)
        timing = bs.get("avg_timing", 0)

        conviction = _conviction(
            brain_score=brain_score,
            pattern_str=p.get("confidence", 50),
            cluster_sz=p.get("wallet_count", 1),
            flow_usd=p.get("net_flow_usd", 0),
            timing=timing,
        )

        drivers = []
        if p.get("wallet_count", 0) >= 2:
            drivers.append(f"{p['wallet_count']} wallets in cluster")
        flow = p.get("net_flow_usd", 0)
        if abs(flow) > 0:
            drivers.append(f"{'inflow' if flow > 0 else 'outflow'} {_fmt_usd(abs(flow))}")
        if p.get("confidence", 0) >= 60:
            drivers.append("strong pattern confidence")
        if timing >= 5:
            drivers.append("favorable entry timing")

        sig = {
            "signal_id": _signal_id(token, ptype),
            "token": token,
            "signal_type": ptype,
            "conviction": conviction,
            "drivers": drivers[:4],
            "wallet_count": p.get("wallet_count", 0),
            "capital_usd": round(abs(p.get("net_flow_usd", 0)), 2),
            "capital_fmt": _fmt_usd(abs(p.get("net_flow_usd", 0))),
            "brain_score": round(brain_score, 1),
            "pattern_confidence": round(p.get("confidence", 0), 1),
            "wallet_addresses": p.get("wallet_addresses", []),
        }

        # For rotation, add from/to
        if ptype == "rotation":
            sig["from_token"] = p.get("from_token", "")
            sig["to_token"] = p.get("to_token", "")

        signals.append(sig)

    # --- Signals from Brain (tokens with strong alpha but no pattern yet) ---
    pattern_tokens = {p.get("token") for p in patterns}
    for b in brain:
        if b["token"] in pattern_tokens:
            continue
        if b["alpha_score"] < 55:
            continue

        signal_type = "momentum" if b["signal"] in ("strong_bullish", "bullish") else "weakening"
        conviction = _conviction(
            brain_score=b["alpha_score"],
            pattern_str=30,
            cluster_sz=b.get("wallet_count", 1),
            flow_usd=b.get("net_flow_usd", 0),
            timing=b.get("avg_timing", 0),
        )

        drivers = []
        drivers.append(f"alpha score {b['alpha_score']}")
        if b.get("wallet_count", 0) >= 2:
            drivers.append(f"{b['wallet_count']} wallets active")
        flow = b.get("net_flow_usd", 0)
        if abs(flow) > 0:
            drivers.append(f"net flow {_fmt_usd(flow)}")

        signals.append({
            "signal_id": _signal_id(b["token"], signal_type),
            "token": b["token"],
            "signal_type": signal_type,
            "conviction": conviction,
            "drivers": drivers[:4],
            "wallet_count": b.get("wallet_count", 0),
            "capital_usd": round(abs(b.get("net_flow_usd", 0)), 2),
            "capital_fmt": _fmt_usd(abs(b.get("net_flow_usd", 0))),
            "brain_score": round(b["alpha_score"], 1),
            "pattern_confidence": 0,
            "wallet_addresses": b.get("wallet_addresses", []),
        })

    # --- Signals from Events (cluster events not covered by patterns) ---
    covered = {s["token"] for s in signals}
    for ev in events:
        token = ev.get("token", "")
        if token in covered or not token:
            continue

        etype = ev.get("event_type", "cluster_activity")
        signal_type = "cluster_activity"
        bs = brain_map.get(token, {})
        brain_score = bs.get("alpha_score", 35)

        conviction = _conviction(
            brain_score=brain_score,
            pattern_str=ev.get("confidence", 40),
            cluster_sz=ev.get("wallet_count", 1),
            flow_usd=ev.get("net_flow_usd", 0),
            timing=ev.get("timing_score", 0),
        )

        if conviction < 30:
            continue

        drivers = []
        if ev.get("wallet_count", 0) >= 2:
            drivers.append(f"{ev['wallet_count']} wallets detected")
        flow = ev.get("net_flow_usd", 0)
        if abs(flow) > 0:
            drivers.append(f"flow {_fmt_usd(abs(flow))}")

        signals.append({
            "signal_id": _signal_id(token, signal_type, etype),
            "token": token,
            "signal_type": signal_type,
            "conviction": conviction,
            "drivers": drivers[:4],
            "wallet_count": ev.get("wallet_count", 0),
            "capital_usd": round(abs(ev.get("net_flow_usd", 0)), 2),
            "capital_fmt": _fmt_usd(abs(ev.get("net_flow_usd", 0))),
            "brain_score": round(brain_score, 1),
            "pattern_confidence": round(ev.get("confidence", 0), 1),
            "wallet_addresses": ev.get("wallet_addresses", []),
        })
        covered.add(token)

    # Sort by conviction descending
    signals.sort(key=lambda s: s["conviction"], reverse=True)
    result = signals[:limit]
    cache_set(ck, result)
    return result
