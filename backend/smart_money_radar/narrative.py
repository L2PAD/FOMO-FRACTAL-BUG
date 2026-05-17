"""
Smart Money Narrative Engine
==============================
Sprint 1.5: Rule-based narrative that aggregates all Smart Money signals
into one clear market interpretation.

Input: brain scores + patterns + flows + routes
Output: One decisive market narrative with bias, confidence, drivers.
"""

from .brain import get_brain_signals
from .patterns import get_patterns
from .service import _fmt_usd, cache_get, cache_set


def _dominant_token(brain: list) -> dict | None:
    if not brain:
        return None
    return brain[0]


def _flow_summary(brain: list) -> dict:
    total_inflow = sum(b["net_flow_usd"] for b in brain if b["net_flow_usd"] > 0)
    total_outflow = sum(abs(b["net_flow_usd"]) for b in brain if b["net_flow_usd"] < 0)
    total_wallets = sum(b["wallet_count"] for b in brain)
    return {
        "total_inflow": total_inflow,
        "total_outflow": total_outflow,
        "net": total_inflow - total_outflow,
        "total_wallets": total_wallets,
    }


def _count_clusters(brain: list, threshold: int = 5) -> int:
    return sum(1 for b in brain if b["wallet_count"] >= threshold)


def get_narrative(chain_id: int = 1, window: str = "24h") -> dict:
    ck = f"narrative:{chain_id}:{window}"
    cached = cache_get(ck)
    if cached is not None:
        return cached

    brain = get_brain_signals(chain_id=chain_id, window=window, limit=10)
    patterns = get_patterns(chain_id=chain_id, window=window, limit=10)

    if not brain:
        no_data = {
            "narrative_type": "no_data",
            "bias": "neutral",
            "confidence": 0,
            "summary": "Insufficient smart money data for analysis.",
            "drivers": [],
            "key_token": None,
            "net_flow_usd": 0,
        }
        cache_set(ck, no_data)
        return no_data

    dom = _dominant_token(brain)
    fs = _flow_summary(brain)
    cluster_count = _count_clusters(brain)

    # Classify patterns
    accum_pats = [p for p in patterns if p["pattern_type"] == "accumulation"]
    distrib_pats = [p for p in patterns if p["pattern_type"] == "distribution"]
    rotation_pats = [p for p in patterns if p["pattern_type"] == "rotation"]
    exit_pats = [p for p in patterns if p["pattern_type"] == "exit"]

    # Count bullish/bearish brain signals
    bullish_count = sum(1 for b in brain if b["signal"] in ("strong_bullish", "bullish"))
    bearish_count = sum(1 for b in brain if b["signal"] in ("strong_bearish", "bearish"))

    # --- Determine narrative type and bias ---
    narrative_type = "neutral"
    bias = "neutral"
    confidence = 50
    summary = ""
    drivers = []

    # Strong accumulation narrative
    if dom and dom["signal"] in ("strong_bullish", "bullish") and fs["net"] > 0 and len(accum_pats) > 0:
        narrative_type = "accumulation"
        bias = "bullish"

        # Confidence from brain alpha + pattern confidence + flow strength
        brain_conf = dom["alpha_score"]
        pat_conf = max(p["confidence"] for p in accum_pats) if accum_pats else 50
        flow_factor = min(20, (fs["total_inflow"] / 10_000_000) * 20)
        confidence = min(95, int(brain_conf * 0.4 + pat_conf * 0.3 + flow_factor + 10))

        summary = f"Smart money accumulating {dom['token']}."
        drivers.append(f"net inflow {_fmt_usd(fs['net'])}")
        if cluster_count >= 2:
            drivers.append(f"{cluster_count} wallet clusters active")
        elif dom["wallet_count"] >= 3:
            drivers.append(f"{dom['wallet_count']} wallets accumulating")
        if rotation_pats:
            src = rotation_pats[0].get("from_token", "")
            if src:
                drivers.append(f"rotation from {src} detected")
        if dom.get("avg_timing", 0) >= 5:
            drivers.append("favorable entry timing")
        if bullish_count >= 3:
            drivers.append(f"{bullish_count} tokens showing bullish signals")

    # Strong distribution narrative
    elif dom and dom["signal"] in ("strong_bearish", "bearish") and fs["net"] < 0 and len(distrib_pats) > 0:
        narrative_type = "distribution"
        bias = "bearish"

        brain_conf = 100 - dom["alpha_score"]
        pat_conf = max(p["confidence"] for p in distrib_pats) if distrib_pats else 50
        flow_factor = min(20, (fs["total_outflow"] / 10_000_000) * 20)
        confidence = min(95, int(brain_conf * 0.4 + pat_conf * 0.3 + flow_factor + 10))

        summary = f"Smart money distributing {dom['token']}."
        drivers.append(f"net outflow {_fmt_usd(abs(fs['net']))}")
        if cluster_count >= 2:
            drivers.append(f"{cluster_count} wallet clusters selling")
        if bearish_count >= 3:
            drivers.append(f"{bearish_count} tokens showing bearish signals")
        if exit_pats:
            drivers.append("capital moving to safety")

    # Exit / risk-off narrative
    elif exit_pats and fs["total_outflow"] > fs["total_inflow"]:
        narrative_type = "exit"
        bias = "bearish"

        pat_conf = max(p["confidence"] for p in exit_pats)
        confidence = min(90, int(pat_conf * 0.5 + 30))

        summary = "Smart money exiting risk assets."
        drivers.append(f"stablecoin inflow detected")
        drivers.append(f"net outflow {_fmt_usd(abs(fs['net']))}")
        if bearish_count > bullish_count:
            drivers.append("majority of tokens bearish")

    # Rotation narrative
    elif rotation_pats and len(rotation_pats) >= 1:
        narrative_type = "rotation"
        bias = "neutral"
        top_rot = rotation_pats[0]

        pat_conf = top_rot["confidence"]
        confidence = min(85, int(pat_conf * 0.6 + 25))

        from_t = top_rot.get("from_token", "?")
        to_t = top_rot.get("to_token", "?")
        summary = f"Smart money rotating from {from_t} to {to_t}."
        drivers.append(f"capital reallocation {_fmt_usd(top_rot['net_flow_usd'])}")
        if top_rot.get("wallet_count", 0) >= 2:
            drivers.append(f"{top_rot['wallet_count']} wallets executing rotation")
        if bullish_count > bearish_count:
            bias = "bullish"
            drivers.append("overall bullish sentiment")
        elif bearish_count > bullish_count:
            bias = "bearish"
            drivers.append("overall bearish sentiment")

    # Mixed / accumulation without strong patterns
    elif dom and dom["signal"] in ("strong_bullish", "bullish") and fs["net"] > 0:
        narrative_type = "accumulation"
        bias = "bullish"
        confidence = min(80, int(dom["alpha_score"] * 0.5 + 20))

        summary = f"Smart money favoring {dom['token']}."
        drivers.append(f"positive net flow (+{_fmt_usd(fs['net'])})")
        if dom["wallet_count"] >= 3:
            drivers.append(f"{dom['wallet_count']} wallets active")
        if bullish_count >= 2:
            drivers.append(f"{bullish_count} tokens bullish")

    # Bearish without strong patterns
    elif dom and dom["signal"] in ("strong_bearish", "bearish") and fs["net"] < 0:
        narrative_type = "distribution"
        bias = "bearish"
        confidence = min(80, int((100 - dom["alpha_score"]) * 0.5 + 20))

        summary = f"Smart money reducing exposure to {dom['token']}."
        drivers.append(f"negative net flow ({_fmt_usd(fs['net'])})")
        if bearish_count >= 2:
            drivers.append(f"{bearish_count} tokens bearish")

    # Neutral
    else:
        narrative_type = "neutral"
        bias = "neutral"
        confidence = max(30, 50 - abs(bullish_count - bearish_count) * 5)

        summary = "Smart money activity is mixed."
        if fs["net"] > 0:
            drivers.append(f"slight net inflow (+{_fmt_usd(fs['net'])})")
        elif fs["net"] < 0:
            drivers.append(f"slight net outflow ({_fmt_usd(fs['net'])})")
        drivers.append(f"{bullish_count} bullish, {bearish_count} bearish signals")

    result = {
        "narrative_type": narrative_type,
        "bias": bias,
        "confidence": confidence,
        "summary": summary,
        "drivers": drivers[:5],
        "key_token": dom["token"] if dom else None,
        "net_flow_usd": round(fs["net"], 2),
    }
    cache_set(ck, result)
    return result
