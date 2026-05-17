"""
Portfolio Builder — Auto-assembles a 3-position portfolio.

Rules:
  - BTC always anchor (40-60% allocation)
  - Top 2 ALTs by score, diversified archetypes
  - Position sizing: confidence * (1/volatility) * risk_factor
  - Expected return, risk level, worst case
"""

import logging

logger = logging.getLogger(__name__)

BTC_MIN = 0.40
BTC_MAX = 0.60
ALT_MIN = 0.15
ALT_MAX = 0.35


def build_portfolio(btc_card: dict, alt_cards: list[dict]) -> dict:
    """Build a diversified 3-position portfolio with intelligence."""
    from services.meta_brain_service import build_snapshot
    positions = []

    # 1. BTC always first — CORE role
    btc_ts = btc_card.get("tradeSetup", {})
    btc_conf = 0.85 if btc_card.get("urgencyLevel") == "high" else 0.7

    btc_snap = build_snapshot("BTC")
    btc_drivers = btc_snap.get("drivers", {})
    fg = btc_drivers.get("sentiment", {}).get("fearGreed", 50)

    btc_thesis = []
    if fg <= 25:
        btc_thesis.append("Extreme fear — accumulation zone")
    elif fg <= 40:
        btc_thesis.append("Fear rising — contrarian opportunity")
    elif fg >= 75:
        btc_thesis.append("Euphoria — caution advised")
    else:
        btc_thesis.append("Neutral sentiment — watching for direction")

    netflow = btc_drivers.get("onchain", {}).get("stablecoinNetflow", 0)
    if netflow and netflow > 5_000_000:
        btc_thesis.append("Stablecoin inflow — capital entering")
    elif netflow and netflow < -5_000_000:
        btc_thesis.append("Capital outflow — distribution active")

    frac = btc_drivers.get("fractal", {})
    if "UP" in frac.get("forecast", ""):
        btc_thesis.append("Fractal: early reversal structure forming")
    elif "DOWN" in frac.get("forecast", ""):
        btc_thesis.append("Fractal: downside pattern active")
    else:
        btc_thesis.append("Fractal: no clear pattern yet")

    positions.append({
        "asset": "BTC",
        "direction": btc_ts.get("direction", "LONG"),
        "entry": btc_ts.get("entry", "—"),
        "entryRaw": btc_ts.get("entryRaw", 0),
        "target": btc_ts.get("target", "—"),
        "invalidation": btc_ts.get("invalidation", "—"),
        "expectedMove": btc_ts.get("expectedMove", "0%"),
        "expectedMoveRaw": btc_ts.get("expectedMoveRaw", 0),
        "confidence": btc_conf,
        "archetype": btc_card.get("archetype", "EARLY"),
        "type": "anchor",
        "role": "CORE",
        "roleLabel": "Core Position",
        "thesis": btc_thesis,
        "conclusion": "BTC is where smart money starts. Market leader, lower risk.",
        "color": "#FFFFFF",
    })

    # 2. Select top 2 ALTs with archetype diversity
    diversified = _diversify_alts(alt_cards, 2)
    roles = ["EARLY_BETA", "CONFIRMATION"]
    role_labels = ["Early Beta", "Confirmation"]
    role_conclusions = [
        "High beta. Early upside capture. Moves before the crowd.",
        "Mid-risk continuation play. Confirms the thesis.",
    ]
    role_colors = ["#00E676", "#448AFF"]

    for idx, alt in enumerate(diversified):
        alt_ts = alt.get("tradeSetup", {})
        alt_asset = alt.get("asset", "?")

        # Build thesis from alt's real data
        alt_thesis = []
        try:
            alt_snap = build_snapshot(alt_asset)
            alt_d = alt_snap.get("drivers", {})
            alt_social = alt_d.get("social", {})
            if alt_social.get("direction") == "Bullish":
                alt_thesis.append("Social attention rising fast")
            alt_exch = alt_d.get("exchange", {})
            if alt_exch.get("direction") == "Bullish":
                alt_thesis.append("Exchange flows turning positive")
            elif alt_exch.get("direction") == "Bearish":
                alt_thesis.append("Exchange distribution detected")
            alt_fg = alt_d.get("sentiment", {}).get("fearGreed", 50)
            if alt_fg <= 30:
                alt_thesis.append("Fear — contrarian setup")
            if not alt_thesis:
                alt_thesis.append("Signal forming. Not obvious yet.")
        except Exception:
            alt_thesis.append("Data loading...")

        positions.append({
            "asset": alt_asset,
            "direction": alt_ts.get("direction", "LONG"),
            "entry": alt_ts.get("entry", "—"),
            "entryRaw": alt_ts.get("entryRaw", 0),
            "target": alt_ts.get("target", "—"),
            "invalidation": alt_ts.get("invalidation", "—"),
            "expectedMove": alt_ts.get("expectedMove", "0%"),
            "expectedMoveRaw": alt_ts.get("expectedMoveRaw", 0),
            "confidence": alt.get("score", 0.3),
            "archetype": alt.get("archetype", "EARLY"),
            "type": "alt",
            "role": roles[idx] if idx < len(roles) else "BETA",
            "roleLabel": role_labels[idx] if idx < len(role_labels) else "Beta",
            "thesis": alt_thesis,
            "conclusion": role_conclusions[idx] if idx < len(role_conclusions) else "Diversification play.",
            "color": role_colors[idx] if idx < len(role_colors) else "#888",
        })

    sized = _apply_sizing(positions)
    metrics = _calc_metrics(sized)

    # Risk block
    risk = {
        "scenarios": [
            "BTC loses support — invalidates thesis",
            "No follow-through from alts",
            "Sentiment flips too fast",
        ],
        "action": "Reduce exposure. Stay defensive.",
    }

    return {
        "positions": sized,
        "count": len(sized),
        "metrics": metrics,
        "risk": risk,
    }


def _diversify_alts(alts, limit):
    if len(alts) <= limit:
        return alts[:limit]
    selected, used = [], set()
    for a in alts:
        if len(selected) >= limit:
            break
        arch = a.get("archetype", "EARLY")
        if arch not in used:
            selected.append(a)
            used.add(arch)
    for a in alts:
        if len(selected) >= limit:
            break
        if a not in selected:
            selected.append(a)
    return selected


def _apply_sizing(positions):
    if not positions:
        return positions
    scores = []
    for p in positions:
        boost = 1.3 if p["type"] == "anchor" else 1.0
        scores.append(p.get("confidence", 0.3) * boost)
    total = sum(scores) or 1

    for i, p in enumerate(positions):
        p["allocationRaw"] = scores[i] / total

    for p in positions:
        if p["type"] == "anchor":
            p["allocationRaw"] = max(BTC_MIN, min(BTC_MAX, p["allocationRaw"]))
        else:
            p["allocationRaw"] = max(ALT_MIN, min(ALT_MAX, p["allocationRaw"]))

    total_alloc = sum(p["allocationRaw"] for p in positions) or 1
    for p in positions:
        alloc = p["allocationRaw"] / total_alloc
        p["allocation"] = round(alloc * 100)
        p["allocationPct"] = f"{p['allocation']}%"
    return positions


def _calc_metrics(positions):
    if not positions:
        return {"expectedMove": "0%", "riskLevel": "—", "worstCase": "0%"}
    exp_ret = sum((p.get("allocation", 0) / 100) * p.get("expectedMoveRaw", 0) for p in positions)
    worst = sum((p.get("allocation", 0) / 100) * abs(p.get("expectedMoveRaw", 0)) * 0.4 for p in positions)
    avg_conf = sum(p.get("confidence", 0) for p in positions) / len(positions)
    risk = "Low" if avg_conf > 0.7 else "Moderate" if avg_conf > 0.4 else "High"

    return {
        "expectedMove": f"{'+' if exp_ret > 0 else ''}{exp_ret:.1f}%",
        "expectedMoveRaw": round(exp_ret, 1),
        "worstCase": f"-{worst:.1f}%",
        "riskLevel": risk,
        "positionCount": len(positions),
    }


def apply_gating(user_plan: str, portfolio: dict) -> dict:
    """FREE/PRO gating."""
    is_pro = user_plan in ("PRO", "INSTITUTIONAL")
    if is_pro:
        return {**portfolio, "gated": False, "plan": "PRO"}

    positions = portfolio.get("positions", [])
    gated = []
    for i, p in enumerate(positions):
        if p["type"] == "anchor":
            gated.append({**p, "locked": False})
        elif len(gated) == 1:
            gated.append({**p, "locked": True, "entry": "🔒", "entryRaw": 0, "target": "🔒", "invalidation": "🔒", "allocationPct": "🔒"})

    hidden = len(positions) - len(gated)
    return {
        "positions": gated,
        "count": len(gated),
        "hiddenCount": hidden,
        "metrics": {"expectedMove": portfolio["metrics"]["expectedMove"], "riskLevel": "🔒", "worstCase": "🔒"},
        "gated": True,
        "plan": "FREE",
    }
