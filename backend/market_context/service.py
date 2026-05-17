"""
Market Context Service — Market Brain Data Layer
==================================================
Aggregates CEX + Smart Money + Token + Wallet intelligence
into a single normalized context with 0-100 scores.

Architecture:
  /api/onchain/market/context
  ├── scores   (cex_score, smart_money_score, token_score, wallet_score, composite)
  ├── context  (compressed key data per module)
  ├── signals  (structured per module)
  └── drivers  (human-readable reasons for composite)

Weights: smart_money 35%, cex 30%, token 20%, wallet 15%
"""

import time

# ── Cache ──
_cache: dict = {}
_CACHE_TTL = 120


def _cache_get(key: str):
    entry = _cache.get(key)
    if entry and time.time() - entry["ts"] < _CACHE_TTL:
        return entry["data"]
    return None


def _cache_set(key: str, data):
    _cache[key] = {"data": data, "ts": time.time()}


# ── Helpers ──
def _clamp(v: float, lo: float = 0, hi: float = 100) -> int:
    return int(max(lo, min(hi, round(v))))


def _fmt_usd(v: float) -> str:
    abs_v = abs(v)
    if abs_v >= 1_000_000_000:
        return f"${abs_v / 1_000_000_000:.1f}B"
    if abs_v >= 1_000_000:
        return f"${abs_v / 1_000_000:.1f}M"
    if abs_v >= 1_000:
        return f"${abs_v / 1_000:.1f}K"
    return f"${abs_v:.0f}"


# ══════════════════════════════════════════════════════════
#  SCORE ENGINES
# ══════════════════════════════════════════════════════════

def _compute_cex_score(cex: dict) -> tuple[int, list[str], dict]:
    """
    CEX Score (0-100) from:
      - liquidity_shock state
      - inventory_change (exchange_inventory)
      - stablecoin_power
      - exchange_pressure
    """
    drivers = []
    components = {}

    # 1) Liquidity Shock → 0-100 (bullish = high)
    shock = cex.get("liquidity_shock") or {}
    shock_state = shock.get("state", "neutral")
    shock_map = {
        "strong_bullish_shock": 95,
        "bullish_shock": 75,
        "neutral": 50,
        "bearish_shock": 25,
        "strong_bearish_shock": 5,
    }
    shock_score = shock_map.get(shock_state, 50)
    components["liquidity_shock"] = shock_score
    if shock_score >= 70:
        drivers.append(f"Liquidity shock {shock.get('label', shock_state)}")

    # 2) Inventory Change → 0-100 (shrinking = bullish = high)
    inventory_items = cex.get("exchange_inventory", [])
    if inventory_items:
        avg_change = sum(i.get("change_pct", 0) for i in inventory_items) / len(inventory_items)
        # change_pct is negative when shrinking (bullish). Map: -100→100, 0→50, +100→0
        inv_score = _clamp(50 - avg_change * 0.5)
        state = inventory_items[0].get("state", "stable")
        if state == "shrinking":
            drivers.append(f"Exchange inventory shrinking ({avg_change:+.0f}%)")
    else:
        inv_score = 50
    components["inventory_change"] = inv_score

    # 3) Stablecoin Power → 0-100 (net positive = bullish = high)
    stable = cex.get("stablecoin_power") or {}
    net_power = stable.get("net_power", 0)
    total_in = stable.get("total_in", 0)
    total_out = stable.get("total_out", 0)
    if total_in + total_out > 0:
        stable_ratio = net_power / (total_in + total_out + 1)
        stable_score = _clamp(50 + stable_ratio * 50)
    else:
        stable_score = 50
    components["stablecoin_power"] = stable_score
    if stable_score >= 65:
        drivers.append(f"Stablecoin power +{_fmt_usd(net_power)}")

    # 4) Exchange Pressure → 0-100 (net outflow = bullish = high)
    pressure = cex.get("exchange_pressure") or {}
    deps = pressure.get("deposits", 0)
    withs = pressure.get("withdrawals", 0)
    total = deps + withs
    if total > 0:
        # Net outflow ratio: (withs - deps) / total → [-1, +1] → [0, 100]
        outflow_ratio = (withs - deps) / total
        pressure_score = _clamp(50 + outflow_ratio * 50)
    else:
        pressure_score = 50
    components["exchange_pressure"] = pressure_score
    if pressure_score >= 65:
        drivers.append("Exchange withdrawals exceeding deposits")
    elif pressure_score <= 35:
        drivers.append("Heavy deposit pressure on exchanges")

    # Aggregate: equal weight among 4 components
    score = _clamp(
        shock_score * 0.30 +
        inv_score * 0.25 +
        stable_score * 0.25 +
        pressure_score * 0.20
    )
    return score, drivers, components


def _compute_smart_money_score(sm: dict) -> tuple[int, list[str], dict]:
    """
    Smart Money Score (0-100) from:
      - conviction (avg signal conviction)
      - capital_weight (based on capital magnitude)
      - lead_time_bonus (from actor timing_score)
    """
    drivers = []
    components = {}

    # 1) Conviction — avg of signal convictions
    signals = sm.get("signals", [])
    if signals:
        avg_conviction = sum(s.get("conviction", 50) for s in signals) / len(signals)
        conviction_score = _clamp(avg_conviction)
    else:
        avg_conviction = 50
        conviction_score = 50
    components["conviction"] = conviction_score

    # 2) Capital Weight — logarithmic scale based on total capital
    total_capital = sum(s.get("capital_usd", 0) for s in signals)
    if total_capital > 0:
        import math
        # log scale: $1K→20, $100K→40, $10M→60, $1B→80, $100B→100
        log_cap = math.log10(max(total_capital, 1))
        cap_score = _clamp(log_cap * 10)  # log10(1M)=6 → 60, log10(100M)=8 → 80
    else:
        cap_score = 30
    components["capital_weight"] = cap_score
    if cap_score >= 60:
        drivers.append(f"Smart money inflow {_fmt_usd(total_capital)}")

    # 3) Lead Time Bonus — from actor timing scores
    actors = sm.get("actors", [])
    if actors:
        avg_timing = sum(a.get("timing_score", 0) for a in actors) / len(actors)
        # timing_score is 0-100, bonus adds up to 15 points
        lead_bonus = _clamp(avg_timing * 0.15, 0, 15)
    else:
        avg_timing = 0
        lead_bonus = 0
    components["lead_time_bonus"] = int(lead_bonus)
    if lead_bonus >= 8:
        drivers.append("High lead-time advantage from smart actors")

    # Aggregate
    base = conviction_score * 0.45 + cap_score * 0.40
    score = _clamp(base + lead_bonus)
    return score, drivers, components


def _compute_token_score(token_data: dict) -> tuple[int, list[str], dict]:
    """
    Token Score (0-100) from:
      - pattern_confidence (from brain signals)
      - regime_strength (from alpha_score / signal patterns)
      - positioning (from net_flow direction)
    """
    drivers = []
    components = {}

    brain = token_data.get("token_scores", [])

    # 1) Pattern Confidence — avg pattern_confidence from brain signals
    if brain:
        confidences = [b.get("components", {}).get("pattern_confidence", 50) if isinstance(b.get("components"), dict)
                       else 50 for b in brain]
        pattern_conf = sum(confidences) / len(confidences)
    else:
        pattern_conf = 40
    components["pattern_confidence"] = _clamp(pattern_conf)

    # 2) Regime Strength — alpha_score avg indicates directional conviction
    if brain:
        alpha_scores = [b.get("alpha_score", 50) for b in brain]
        avg_alpha = sum(alpha_scores) / len(alpha_scores)
        regime_score = _clamp(avg_alpha)
    else:
        avg_alpha = 50
        regime_score = 50
    components["regime_strength"] = regime_score

    # Determine regime type
    signals = token_data.get("signals", [])
    accum_count = sum(1 for s in signals if s.get("signal_type") == "accumulation")
    dist_count = sum(1 for s in signals if s.get("signal_type") == "distribution")
    regime = "accumulation" if accum_count > dist_count else "distribution" if dist_count > accum_count else "neutral"
    if regime == "accumulation" and regime_score >= 55:
        drivers.append("Token regime: accumulation phase")
    elif regime == "distribution" and regime_score >= 55:
        drivers.append("Token regime: distribution phase")

    # 3) Positioning — net flow direction across tokens
    if brain:
        total_buy = sum(b.get("buy_flow_usd", 0) for b in brain)
        total_sell = sum(b.get("sell_flow_usd", 0) for b in brain)
        if total_buy + total_sell > 0:
            buy_ratio = total_buy / (total_buy + total_sell)
            pos_score = _clamp(buy_ratio * 100)
        else:
            pos_score = 50
    else:
        pos_score = 50
    components["positioning"] = pos_score
    if pos_score >= 65:
        drivers.append("Strong buy-side positioning across tokens")

    score = _clamp(
        _clamp(pattern_conf) * 0.40 +
        regime_score * 0.35 +
        pos_score * 0.25
    )
    return score, drivers, components


def _compute_wallet_score(sm: dict) -> tuple[int, list[str], dict]:
    """
    Wallet Score (0-100) from:
      - actor_credibility (smart_score of actors)
      - capital_direction (net_flow direction)
      - cluster_activity (wallet counts, trades)
    """
    drivers = []
    components = {}
    actors = sm.get("actors", [])

    # 1) Actor Credibility — avg smart_score
    if actors:
        avg_smart = sum(a.get("smart_score", 40) for a in actors) / len(actors)
        cred_score = _clamp(avg_smart)
    else:
        cred_score = 40
    components["actor_credibility"] = cred_score

    # 2) Capital Direction — net flow direction of top actors
    if actors:
        total_net = sum(a.get("net_flow_usd", 0) for a in actors)
        positive_count = sum(1 for a in actors if a.get("net_flow_usd", 0) > 0)
        ratio = positive_count / len(actors)
        dir_score = _clamp(ratio * 100)
    else:
        total_net = 0
        dir_score = 50
    components["capital_direction"] = dir_score
    if dir_score >= 65:
        drivers.append(f"Smart wallets net buying ({_fmt_usd(total_net)} net)")
    elif dir_score <= 35:
        drivers.append("Smart wallets net selling")

    # 3) Cluster Activity — density of trading activity
    if actors:
        total_trades = sum(a.get("trades", 0) for a in actors)
        active_count = sum(1 for a in actors if a.get("activity_score", 0) >= 50)
        # More active actors + more trades = higher score
        activity_density = min(active_count / max(len(actors), 1), 1.0)
        trade_intensity = min(total_trades / max(len(actors) * 10, 1), 1.0)
        cluster_score = _clamp((activity_density * 0.5 + trade_intensity * 0.5) * 100)
    else:
        cluster_score = 30
    components["cluster_activity"] = cluster_score
    if cluster_score >= 60:
        drivers.append("High cluster trading activity")

    score = _clamp(
        cred_score * 0.40 +
        dir_score * 0.35 +
        cluster_score * 0.25
    )
    return score, drivers, components


# ══════════════════════════════════════════════════════════
#  CONTEXT COMPRESSION
# ══════════════════════════════════════════════════════════

def _compress_cex_context(cex: dict) -> dict:
    """Extract only key CEX data for Engine consumption."""
    shock = cex.get("liquidity_shock") or {}
    inv = cex.get("exchange_inventory", [])
    inv_state = inv[0].get("state", "stable") if inv else "unknown"
    stable = cex.get("stablecoin_power") or {}
    pressure = cex.get("exchange_pressure") or {}
    liq = cex.get("market_liquidity") or {}
    return {
        "market_bias": cex.get("market_bias", "neutral"),
        "liquidity_shock": shock.get("state", "neutral"),
        "inventory_state": inv_state,
        "stablecoin_bias": stable.get("bias", "neutral"),
        "stablecoin_net": stable.get("net_power", 0),
        "pressure_bias": pressure.get("bias", "neutral"),
        "net_liquidity": liq.get("net_liquidity", 0),
    }


def _compress_smart_money_context(sm: dict) -> dict:
    """Extract only key Smart Money data."""
    signals = sm.get("signals", [])
    total_capital = sum(s.get("capital_usd", 0) for s in signals)
    avg_conviction = (sum(s.get("conviction", 0) for s in signals) / len(signals)) if signals else 0
    clusters = len(set(s.get("token", "") for s in signals))
    return {
        "net_flow": round(total_capital, 2),
        "net_flow_fmt": _fmt_usd(total_capital),
        "conviction": round(avg_conviction),
        "clusters": clusters,
        "signal_count": len(signals),
    }


def _compress_token_context(token_data: dict) -> dict:
    """Extract only key Token data."""
    signals = token_data.get("signals", [])
    brain = token_data.get("token_scores", [])
    accum = sum(1 for s in signals if s.get("signal_type") == "accumulation")
    dist = sum(1 for s in signals if s.get("signal_type") == "distribution")
    regime = "accumulation" if accum > dist else "distribution" if dist > accum else "neutral"
    # Top pattern from brain
    top_pattern = "none"
    top_conf = 0
    if brain:
        best = max(brain, key=lambda b: b.get("alpha_score", 0))
        top_pattern = best.get("signal", "none")
        top_conf = best.get("alpha_score", 0)
    return {
        "regime": regime,
        "pattern": top_pattern,
        "confidence": round(top_conf),
        "token_count": len(brain),
    }


def _compress_wallet_context(sm: dict) -> dict:
    """Extract only key Wallet data."""
    actors = sm.get("actors", [])
    if not actors:
        return {"active_actors": 0, "direction": "neutral", "avg_smart_score": 0}
    total_net = sum(a.get("net_flow_usd", 0) for a in actors)
    direction = "buy" if total_net > 0 else "sell" if total_net < 0 else "neutral"
    avg_smart = sum(a.get("smart_score", 0) for a in actors) / len(actors)
    return {
        "active_actors": len(actors),
        "direction": direction,
        "avg_smart_score": round(avg_smart),
        "net_flow_fmt": ("+" if total_net >= 0 else "") + _fmt_usd(total_net),
    }


# ══════════════════════════════════════════════════════════
#  SIGNAL EXTRACTION
# ══════════════════════════════════════════════════════════

def _extract_signals(cex: dict, sm: dict, token_data: dict) -> dict:
    """Structure signals per module."""
    # Smart Money signals
    sm_signals = []
    for s in sm.get("signals", [])[:5]:
        sm_signals.append(f"{s.get('signal_type', 'unknown').title()} {s.get('token', '?')} — conviction {s.get('conviction', 0)}%")

    # CEX signals
    cex_signals = []
    shock = cex.get("liquidity_shock") or {}
    if shock.get("state", "neutral") != "neutral":
        cex_signals.append(f"Liquidity shock: {shock.get('label', shock.get('state'))}")
    inv = cex.get("exchange_inventory", [])
    for item in inv[:2]:
        if item.get("state") != "stable":
            cex_signals.append(f"{item.get('token')} inventory {item.get('state')} ({item.get('change_pct', 0):+.0f}%)")
    pressure = cex.get("exchange_pressure") or {}
    if pressure.get("bias") == "bearish":
        cex_signals.append(f"Net deposit pressure {pressure.get('net_fmt', '')}")
    elif pressure.get("bias") == "bullish":
        cex_signals.append(f"Net withdrawal flow {pressure.get('net_fmt', '')}")
    stable = cex.get("stablecoin_power") or {}
    if stable.get("bias") == "buying_power" and stable.get("net_power", 0) > 0:
        cex_signals.append(f"Stablecoin buying power +{_fmt_usd(stable.get('net_power', 0))}")
    pumps = cex.get("pump_setups", [])
    for p in pumps[:2]:
        if p.get("pump_probability", 0) >= 60:
            cex_signals.append(f"{p.get('token')} pump setup {p.get('pump_probability')}%")

    # Token signals
    token_signals = []
    for s in token_data.get("signals", [])[:3]:
        token_signals.append(f"{s.get('signal_type', '').title()} {s.get('token', '?')} — {s.get('conviction', 0)}% conviction")

    # Wallet signals
    wallet_signals = []
    for a in sm.get("actors", [])[:3]:
        if a.get("smart_score", 0) >= 60:
            wallet_signals.append(f"Smart actor ({a.get('name', 'unknown')[:20]}) net {a.get('net_flow_fmt', '?')}")

    return {
        "smart_money": sm_signals,
        "cex": cex_signals,
        "token": token_signals,
        "wallet": wallet_signals,
    }


# ══════════════════════════════════════════════════════════
#  MAIN ENTRY
# ══════════════════════════════════════════════════════════

WEIGHTS = {
    "smart_money": 0.35,
    "cex": 0.30,
    "token": 0.20,
    "wallet": 0.15,
}


def get_market_context(chain_id: int = 1, window: str = "30d") -> dict:
    ck = f"market_ctx:{chain_id}:{window}"
    cached = _cache_get(ck)
    if cached is not None:
        return cached

    # ── Fetch raw contexts ──
    from cex_intelligence.service import get_cex_context
    from smart_money_radar.context import get_smart_money_context
    from smart_money_radar.intelligence_context import get_token_intelligence_context

    cex_raw = get_cex_context(chain_id=chain_id, window=window)
    sm_raw = get_smart_money_context(chain_id=chain_id, window=window)
    token_raw = get_token_intelligence_context(chain_id=chain_id, window=window)

    # ── Compute normalized scores ──
    cex_score, cex_drivers, cex_components = _compute_cex_score(cex_raw)
    sm_score, sm_drivers, sm_components = _compute_smart_money_score(sm_raw)
    token_score, token_drivers, token_components = _compute_token_score(token_raw)
    wallet_score, wallet_drivers, wallet_components = _compute_wallet_score(sm_raw)

    # Weighted composite
    composite = _clamp(
        sm_score * WEIGHTS["smart_money"] +
        cex_score * WEIGHTS["cex"] +
        token_score * WEIGHTS["token"] +
        wallet_score * WEIGHTS["wallet"]
    )

    # ── Build 4-layer response ──
    all_drivers = []
    all_drivers.extend(sm_drivers)
    all_drivers.extend(cex_drivers)
    all_drivers.extend(token_drivers)
    all_drivers.extend(wallet_drivers)

    result = {
        "scores": {
            "cex_score": cex_score,
            "smart_money_score": sm_score,
            "token_score": token_score,
            "wallet_score": wallet_score,
            "composite": composite,
            "weights": WEIGHTS,
            "components": {
                "cex": cex_components,
                "smart_money": sm_components,
                "token": token_components,
                "wallet": wallet_components,
            },
        },
        "context": {
            "cex": _compress_cex_context(cex_raw),
            "smart_money": _compress_smart_money_context(sm_raw),
            "token": _compress_token_context(token_raw),
            "wallet": _compress_wallet_context(sm_raw),
        },
        "signals": _extract_signals(cex_raw, sm_raw, token_raw),
        "drivers": all_drivers[:10],
    }

    _cache_set(ck, result)
    return result
