"""
Wallet Context v2 — Single aggregated endpoint for wallet profile
==================================================================
GET /api/onchain/smart-money/wallet/{address}/context

Returns a complete wallet intelligence profile:
  - wallet: header info (address, entity, strategy, smart_score, activity level)
  - insight: rule-based summary + behavioral traits
  - performance: PnL, win rate, volume (adaptive by entity type)
  - behavior: strategy detection, cluster, timing
  - tokens: allocation breakdown
  - signals: signals this wallet contributed to
  - trades: summary + recent activity
  - related_wallets: cluster-related addresses
  - counterparties: top interaction partners
"""

from pymongo import DESCENDING
import math
import hashlib
from .service import _col, _timing_score, _fmt_usd, _time_ago, _clean, cache_get, cache_set
from .wallet_strategies import _classify_strategy


def get_wallet_context(address: str, chain_id: int = 1, window: str = "24h") -> dict:
    ck = f"wctx2:{address}:{chain_id}:{window}"
    cached = cache_get(ck)
    if cached is not None:
        return cached

    flows_col = _col("onchain_v2_entity_flows")
    scores_col = _col("onchainv2_actorscores")
    labels_col = _col("onchain_v2_address_labels")

    addr_lower = address.lower()
    entity_flow = _find_entity_flow(flows_col, addr_lower, chain_id, window)
    label = labels_col.find_one(
        {"chainId": chain_id, "address": {"$regex": f"^{addr_lower}$", "$options": "i"}},
        {"_id": 0}
    )

    score_doc = _find_score(scores_col, entity_flow, chain_id, window)

    wallet_profile = _build_wallet_profile(address, entity_flow, label, score_doc)
    performance = _build_performance(entity_flow, wallet_profile["entity"])
    behavior = _build_behavior(entity_flow, score_doc)
    tokens = _build_tokens(entity_flow)
    signals = _build_wallet_signals(entity_flow, chain_id, window)
    trades = _build_trades(entity_flow)
    related = _build_related_wallets(flows_col, entity_flow, addr_lower, chain_id, window, behavior)
    counterparties = _build_counterparties(entity_flow)
    timing = _build_timing(entity_flow, behavior, signals)
    influence = _build_influence(entity_flow, signals, related)
    credibility = _build_credibility(entity_flow, behavior, performance, signals)
    trading_style = _build_trading_style(entity_flow, behavior)
    insight = _build_insight(wallet_profile, performance, behavior, tokens, signals, timing)

    # v4 metrics
    alpha_score = _build_alpha_score(wallet_profile, performance, behavior, timing, influence, credibility)
    wallet_rank = _build_wallet_rank(flows_col, alpha_score, chain_id, window)
    trade_quality = _build_trade_quality(entity_flow, performance, behavior, tokens)
    capital_rotation = _build_capital_rotation(tokens, behavior)
    copy_potential = _build_copy_potential(alpha_score, behavior, timing, credibility)
    strategy_stability = _build_strategy_stability(behavior, credibility)
    liquidity_impact = _build_liquidity_impact(entity_flow, performance)
    signal_reliability = _build_signal_reliability(signals, influence)
    portfolio_interp = _build_portfolio_interpretation(tokens, behavior)

    # v4.1 new blocks
    wallet_edge = _build_wallet_edge(alpha_score, behavior, timing, performance)
    trade_replay = _build_trade_replay(trades, tokens, behavior)
    copy_signal = _build_copy_signal(tokens, signals, copy_potential, insight)

    result = {
        "wallet": wallet_profile,
        "insight": insight,
        "performance": performance,
        "behavior": behavior,
        "tokens": tokens,
        "signals": signals,
        "trades": trades,
        "related_wallets": related,
        "counterparties": counterparties,
        "timing": timing,
        "influence": influence,
        "credibility": credibility,
        "trading_style": trading_style,
        "alpha_score": alpha_score,
        "wallet_rank": wallet_rank,
        "trade_quality": trade_quality,
        "capital_rotation": capital_rotation,
        "copy_potential": copy_potential,
        "strategy_stability": strategy_stability,
        "liquidity_impact": liquidity_impact,
        "signal_reliability": signal_reliability,
        "portfolio_interpretation": portfolio_interp,
        "wallet_edge": wallet_edge,
        "trade_replay": trade_replay,
        "copy_signal": copy_signal,
    }

    cache_set(ck, result)
    return result


# ─── Helpers ───────────────────────────────────────────────

def _find_entity_flow(col, addr_lower, chain_id, window):
    ef = col.find_one({"chainId": chain_id, "window": window, "entityId": addr_lower}, {"_id": 0})
    if ef:
        return ef
    import re
    regex = re.compile(f".*{re.escape(addr_lower)}.*", re.IGNORECASE)
    ef = col.find_one({"chainId": chain_id, "window": window, "entityId": regex}, {"_id": 0})
    if ef:
        return ef
    ef = col.find_one({"chainId": chain_id, "window": window, "address": {"$regex": addr_lower, "$options": "i"}}, {"_id": 0})
    return ef


def _find_score(scores_col, entity_flow, chain_id, window):
    latest = scores_col.find_one({"chainId": chain_id, "window": window}, sort=[("bucketTs", DESCENDING)])
    if not latest or not entity_flow:
        return None
    bts = latest.get("bucketTs")
    eid = entity_flow.get("entityId", "")
    return scores_col.find_one({"chainId": chain_id, "window": window, "bucketTs": bts, "entityId": eid}, {"_id": 0})


def _short(addr):
    if not addr or len(addr) < 10:
        return addr
    return f"{addr[:6]}...{addr[-4:]}"


# ─── Build blocks ─────────────────────────────────────────

def _build_wallet_profile(address, ef, label, score_doc):
    entity_type = "unknown"
    strategy = "unknown"
    smart_score = 0
    name = address
    activity = "low"

    if label:
        name = label.get("label", label.get("name", name))
        entity_type = label.get("entityType", label.get("type", "unknown"))

    if ef:
        et = ef.get("entityType", "")
        if et:
            entity_type = et
        eid = ef.get("entityId", "")
        if name == address and eid:
            cleaned = eid.replace("_", " ").replace(":", " ")
            if not cleaned.startswith("unknown") and not cleaned.startswith("0x"):
                name = cleaned

        tokens = ef.get("tokenBreakdown", [])
        timing = _timing_score(ef)
        strat = _classify_strategy(ef, tokens, timing)
        strategy = strat["strategy"]

        trades = ef.get("trades", 0) or 0
        activity = "high" if trades > 20 else "medium" if trades > 5 else "low"

    if score_doc and ef:
        edge = score_doc.get("edgeScore", 30)
        timing = _timing_score(ef)
        net_usd = ef.get("netUsd", 0) or 0
        flow_mag = min(abs(net_usd), 50_000_000)
        fc = min(30, (math.log10(max(flow_mag, 1)) / 8) * 30)
        ec = min(35, (edge / 100) * 35)
        tc = min(20, max(0, (timing + 10) / 25 * 20))
        dc = min(15, len(ef.get("tokenBreakdown", [])) * 3)
        smart_score = int(min(99, max(5, ec + tc + fc + dc)))
    elif ef:
        timing = _timing_score(ef)
        net_usd = ef.get("netUsd", 0) or 0
        trades = ef.get("trades", 0) or 0
        flow_mag = min(abs(net_usd), 50_000_000)
        fc = min(30, (math.log10(max(flow_mag, 1)) / 8) * 30)
        tc = min(20, max(0, (timing + 10) / 25 * 20))
        trc = min(15, min(trades, 50) * 0.3)
        smart_score = int(min(90, max(5, fc + tc + trc)))

    # Actor classification (2-level)
    ENTITY_TO_CATEGORY = {
        "exchange": "Exchange", "cex": "Exchange", "dex": "Protocol",
        "protocol": "Protocol", "bridge": "Bridge", "fund": "Fund",
        "whale": "Trader", "smart_money": "Trader", "unknown": "Unknown",
    }
    STRATEGY_TO_BEHAVIOR = {
        "early_accumulator": "Accumulator", "momentum_trader": "Momentum Trader",
        "rotation_trader": "Rotation Trader", "distribution_wallet": "Distributor",
        "active_trader": "Active Trader", "liquidity_provider": "Market Maker",
        "passive": "Passive Holder",
    }
    actor_category = ENTITY_TO_CATEGORY.get(entity_type.lower(), "Unknown")
    actor_behavior = STRATEGY_TO_BEHAVIOR.get(strategy, "Unknown")

    # Detailed actor type
    ACTOR_TYPE_MAP = {
        "exchange": "Exchange", "cex": "Exchange", "dex": "Protocol",
        "protocol": "Protocol", "bridge": "Bridge", "fund": "Fund",
        "whale": "Smart Trader", "smart_money": "Smart Trader",
    }
    at = ACTOR_TYPE_MAP.get(entity_type.lower(), "")
    if not at and smart_score >= 60:
        at = "Smart Trader"
    elif not at and strategy in ("liquidity_provider",):
        at = "Market Maker"
    elif not at and strategy in ("early_accumulator", "momentum_trader", "rotation_trader", "active_trader"):
        at = "Trader"
    elif not at:
        at = "Wallet"

    networks = ["Ethereum"]
    chain_map = {1: "Ethereum", 10: "Optimism", 42161: "Arbitrum", 8453: "Base", 137: "Polygon"}
    if ef and ef.get("chainId"):
        networks = [chain_map.get(ef["chainId"], "Ethereum")]

    return {
        "address": address,
        "name": name,
        "entity": entity_type,
        "strategy": strategy,
        "smart_score": smart_score,
        "activity": activity,
        "actor_category": actor_category,
        "actor_behavior": actor_behavior,
        "actor_type": at,
        "networks": networks,
    }


def _build_performance(ef, entity_type):
    if not ef:
        return {"pnl": 0, "pnl_fmt": "$0", "win_rate": 0, "avg_trade": 0, "avg_trade_fmt": "$0",
                "total_volume": 0, "total_volume_fmt": "$0", "largest_trade": 0, "largest_trade_fmt": "$0",
                "net_flow": 0, "net_flow_fmt": "$0", "transfers": 0, "entity_type": entity_type}

    net = ef.get("netUsd", 0) or 0
    trades = ef.get("trades", 0) or 1
    dex = abs(ef.get("dexUsd", 0) or 0)
    cex = abs(ef.get("cexUsd", 0) or 0)
    bridge = abs(ef.get("bridgeUsd", 0) or 0)
    total_vol = dex + cex + bridge
    avg = total_vol / trades if trades > 0 else 0

    tokens = ef.get("tokenBreakdown", [])
    positive = sum(1 for t in tokens if (t.get("netUsd", 0) or 0) > 0)
    win_rate = round(positive / max(len(tokens), 1), 2)

    largest = max((abs(t.get("netUsd", 0) or 0) for t in tokens), default=0)

    return {
        "pnl": round(net, 2), "pnl_fmt": _fmt_usd(net),
        "win_rate": win_rate,
        "avg_trade": round(avg, 2), "avg_trade_fmt": _fmt_usd(avg),
        "total_volume": round(total_vol, 2), "total_volume_fmt": _fmt_usd(total_vol),
        "largest_trade": round(largest, 2), "largest_trade_fmt": _fmt_usd(largest),
        "net_flow": round(net, 2), "net_flow_fmt": _fmt_usd(net),
        "transfers": ef.get("trades", 0) or 0,
        "entity_type": entity_type,
    }


def _build_behavior(ef, score_doc):
    if not ef:
        return {"strategy": "unknown", "strategy_label": "Unknown", "confidence": 0,
                "cluster": "none", "tokens": [], "detail": "", "timing_score": 0,
                "traits": [], "entry_style": "unknown", "holding_style": "unknown",
                "execution_style": "unknown", "token_behavior": "unknown"}

    tokens = ef.get("tokenBreakdown", [])
    timing = _timing_score(ef)
    strat = _classify_strategy(ef, tokens, timing)

    labels = {
        "early_accumulator": "Early Accumulator", "momentum_trader": "Momentum Trader",
        "rotation_trader": "Rotation Trader", "distribution_wallet": "Distribution",
        "active_trader": "Active Trader", "liquidity_provider": "LP Provider",
        "passive": "Passive",
    }

    net = ef.get("netUsd", 0) or 0
    cluster = "accumulation" if net > 0 else "distribution"
    if strat["strategy"] == "rotation_trader":
        cluster = "rotation"

    token_names = [t.get("tokenSymbol", "") for t in sorted(tokens, key=lambda x: abs(x.get("netUsd", 0) or 0), reverse=True)[:5] if t.get("tokenSymbol")]

    # Pattern detection
    entry_style = "early" if timing >= 5 else "momentum" if timing >= 0 else "late"
    trades = ef.get("trades", 0) or 0
    holding_style = "short_term" if trades > 30 else "swing" if trades > 10 else "long_hold"
    dex = abs(ef.get("dexUsd", 0) or 0)
    cex = abs(ef.get("cexUsd", 0) or 0)
    total = dex + cex or 1
    execution_style = "dex" if dex / total > 0.7 else "cex" if cex / total > 0.7 else "mixed"
    token_behavior = "concentrated" if len(tokens) <= 3 else "diversified" if len(tokens) >= 7 else "moderate"

    # Build traits list
    traits = []
    if entry_style == "early":
        traits.append("enters before momentum")
    elif entry_style == "late":
        traits.append("late entries after price moves")
    if holding_style == "short_term":
        traits.append("high frequency trading")
    elif holding_style == "long_hold":
        traits.append("low churn, patient holder")
    if execution_style == "dex":
        traits.append("DEX-first execution")
    elif execution_style == "cex":
        traits.append("CEX-routed execution")
    if token_behavior == "concentrated":
        traits.append("concentrated portfolio")
    elif token_behavior == "diversified":
        traits.append("diversified exposure")
    if strat["confidence"] >= 70:
        traits.append("high conviction entries")

    return {
        "strategy": strat["strategy"],
        "strategy_label": labels.get(strat["strategy"], strat["strategy"]),
        "confidence": strat["confidence"],
        "cluster": cluster,
        "tokens": token_names,
        "detail": strat["detail"],
        "timing_score": round(timing, 1),
        "traits": traits,
        "entry_style": entry_style,
        "holding_style": holding_style,
        "execution_style": execution_style,
        "token_behavior": token_behavior,
    }


def _build_tokens(ef):
    if not ef:
        return []
    tokens = ef.get("tokenBreakdown", [])
    total_abs = sum(abs(t.get("netUsd", 0) or 0) for t in tokens) or 1
    result = []
    for t in sorted(tokens, key=lambda x: abs(x.get("netUsd", 0) or 0), reverse=True)[:10]:
        sym = t.get("tokenSymbol", "?")
        net = t.get("netUsd", 0) or 0
        alloc = round(abs(net) / total_abs, 4)
        result.append({
            "symbol": sym, "net_flow_usd": round(net, 2), "net_flow_fmt": _fmt_usd(net),
            "allocation": alloc, "allocation_pct": f"{alloc * 100:.1f}%",
            "direction": "buy" if net > 0 else "sell",
        })
    return result


def _build_wallet_signals(ef, chain_id, window):
    if not ef:
        return []
    try:
        from .signals_engine import get_signals
        all_sigs = get_signals(chain_id=chain_id, window=window, limit=30)
    except Exception:
        all_sigs = []

    wallet_tokens = {t.get("tokenSymbol", "").upper() for t in ef.get("tokenBreakdown", []) if t.get("tokenSymbol")}
    matching = []
    for sig in all_sigs:
        if (sig.get("token", "") or "").upper() in wallet_tokens:
            matching.append({
                "signal_id": sig.get("signal_id", ""),
                "token": sig.get("token", ""),
                "type": sig.get("signal_type", ""),
                "conviction": sig.get("conviction", 0),
                "capital_fmt": sig.get("capital_fmt", "$0"),
                "wallet_count": sig.get("wallet_count", 0),
            })
    return matching[:8]


def _build_trades(ef):
    if not ef:
        return {"total": 0, "dex_share": 0, "cex_share": 0, "dex_volume_fmt": "$0",
                "cex_volume_fmt": "$0", "last_activity": "unknown", "recent": []}

    trades = ef.get("trades", 0) or 0
    dex = abs(ef.get("dexUsd", 0) or 0)
    cex = abs(ef.get("cexUsd", 0) or 0)
    total = dex + cex or 1

    # Synthesize recent trades from token breakdown
    recent = []
    for t in sorted(ef.get("tokenBreakdown", []), key=lambda x: abs(x.get("netUsd", 0) or 0), reverse=True)[:8]:
        sym = t.get("tokenSymbol", "?")
        net = t.get("netUsd", 0) or 0
        recent.append({
            "token": sym,
            "side": "Buy" if net > 0 else "Sell",
            "amount_fmt": _fmt_usd(abs(net)),
            "venue": "DEX" if dex > cex else "CEX",
        })

    return {
        "total": trades,
        "dex_share": round(dex / total, 2),
        "cex_share": round(cex / total, 2),
        "dex_volume_fmt": _fmt_usd(dex),
        "cex_volume_fmt": _fmt_usd(cex),
        "last_activity": _time_ago(ef.get("lastSeen") or ef.get("updatedAt")),
        "recent": recent,
    }


def _build_related_wallets(flows_col, ef, addr_lower, chain_id, window, behavior=None):
    if not ef:
        return []
    # Find wallets with similar token exposure
    my_tokens = {t.get("tokenSymbol", "").upper() for t in ef.get("tokenBreakdown", []) if t.get("tokenSymbol")}
    if not my_tokens:
        return []

    my_eid = ef.get("entityId", "")
    candidates = list(flows_col.find(
        {"chainId": chain_id, "window": window, "entityId": {"$ne": my_eid}},
        {"_id": 0, "entityId": 1, "entityType": 1, "tokenBreakdown": 1, "netUsd": 1, "trades": 1}
    ).limit(200))

    related = []
    for c in candidates:
        c_tokens = {t.get("tokenSymbol", "").upper() for t in c.get("tokenBreakdown", []) if t.get("tokenSymbol")}
        overlap = my_tokens & c_tokens
        if not overlap:
            continue
        similarity = round(len(overlap) / max(len(my_tokens | c_tokens), 1) * 100)
        if similarity < 20:
            continue
        eid = c.get("entityId", "")
        is_addr = eid.startswith("0x") and len(eid) > 10

        # Determine relation type
        my_strat = behavior.get("strategy", "") if behavior else ""
        c_trades = c.get("trades", 0) or 0
        c_net = c.get("netUsd", 0) or 0
        if similarity >= 60:
            rel_type = "execution_similarity"
        elif len(overlap) >= 2:
            rel_type = "token_overlap"
        elif c_net * (ef.get("netUsd", 0) or 0) > 0:
            rel_type = "cluster_participation"
        else:
            rel_type = "funding_relation"

        related.append({
            "address": eid,
            "name": _short(eid) if is_addr else eid.replace("_", " ").replace(":", " "),
            "similarity": similarity,
            "relation": rel_type,
            "shared_tokens": list(overlap)[:3],
            "is_wallet": is_addr,
        })

    related.sort(key=lambda x: x["similarity"], reverse=True)
    # Deduplicate by address
    seen = set()
    deduped = []
    for r in related:
        if r["address"] not in seen:
            seen.add(r["address"])
            deduped.append(r)
    return deduped[:6]


def _build_counterparties(ef):
    if not ef:
        return []
    # Counterparties from token breakdown venues
    dex = abs(ef.get("dexUsd", 0) or 0)
    cex = abs(ef.get("cexUsd", 0) or 0)
    bridge = abs(ef.get("bridgeUsd", 0) or 0)

    parties = []
    if dex > 0:
        parties.append({"name": "DEX Routers", "type": "dex", "volume_fmt": _fmt_usd(dex), "share": round(dex / (dex + cex + bridge or 1), 2)})
    if cex > 0:
        parties.append({"name": "CEX Venues", "type": "cex", "volume_fmt": _fmt_usd(cex), "share": round(cex / (dex + cex + bridge or 1), 2)})
    if bridge > 0:
        parties.append({"name": "Bridge Contracts", "type": "bridge", "volume_fmt": _fmt_usd(bridge), "share": round(bridge / (dex + cex + bridge or 1), 2)})
    return parties


def _build_insight(wallet, perf, behavior, tokens, signals, timing):
    """Rule-based insight generation — no AI needed."""
    lines = []
    traits = behavior.get("traits", [])

    # Strategy summary
    strategy = behavior.get("strategy_label", "Unknown")
    entity = wallet.get("entity", "unknown")

    if entity in ("exchange", "cex"):
        lines.append(f"This address belongs to an exchange entity ({wallet.get('name', 'Unknown')}).")
        if perf.get("net_flow", 0) < 0:
            lines.append("Recent activity shows consistent outflows.")
        else:
            lines.append("Recent activity shows net inflows.")
        lines.append(f"Execution is primarily routed through {'CEX' if behavior.get('execution_style') == 'cex' else 'DEX'} venues.")
    else:
        lines.append(f"This wallet behaves like a {strategy.lower()}.")

        if behavior.get("entry_style") == "early":
            lines.append("Entries typically occur before momentum phases.")
        elif behavior.get("entry_style") == "late":
            lines.append("Entries tend to follow established price trends.")

        if behavior.get("token_behavior") == "concentrated" and len(tokens) > 0:
            top_token = tokens[0]["symbol"] if tokens else "?"
            lines.append(f"Activity is concentrated in {top_token}.")
        elif behavior.get("token_behavior") == "diversified":
            lines.append("Portfolio is diversified across multiple tokens.")

        if behavior.get("execution_style") == "dex":
            lines.append("Execution happens primarily on DEX venues.")
        elif behavior.get("execution_style") == "cex":
            lines.append("Routing is primarily through centralized exchanges.")

    # Signal alignment
    sig_alignment = "neutral"
    if signals:
        bullish = sum(1 for s in signals if s.get("type") in ("accumulation", "momentum"))
        bearish = sum(1 for s in signals if s.get("type") in ("distribution", "weakening"))
        if bullish > bearish:
            lines.append("Signal alignment suggests bullish positioning.")
            sig_alignment = "bullish"
        elif bearish > bullish:
            lines.append("Signal alignment suggests distribution activity.")
            sig_alignment = "bearish"

    # Timing verdict
    if timing.get("early_entry_ratio", 0) > 0.4:
        lines.append("This wallet tends to enter positions before momentum expansions.")

    strat_confidence = "high" if behavior.get("confidence", 0) >= 70 else "medium" if behavior.get("confidence", 0) >= 50 else "low"

    return {
        "summary": "\n\n".join(lines),
        "traits": traits,
        "signal_alignment": sig_alignment,
        "strategy_confidence": strat_confidence,
    }


def _build_timing(ef, behavior, signals):
    """Timing Intelligence — how early this wallet enters vs signals."""
    if not ef:
        return {"early_entry_ratio": 0, "late_entry_ratio": 0, "avg_lead_time": "N/A",
                "signal_alignment": 0, "verdict": "Insufficient data"}

    timing = behavior.get("timing_score", 0)
    entry_style = behavior.get("entry_style", "unknown")

    # Estimate from timing score and strategy
    early_ratio = max(0, min(1, (timing + 10) / 25))
    late_ratio = max(0, min(1, 1 - early_ratio - 0.25))
    sig_align = len(signals) / max(len(ef.get("tokenBreakdown", [])), 1)
    sig_align = round(min(1, sig_align), 2)

    # Lead time estimate from timing score
    if timing >= 8:
        lead = "+4h+"
    elif timing >= 5:
        lead = "+2-4h"
    elif timing >= 2:
        lead = "+1-2h"
    elif timing >= 0:
        lead = "~0h (concurrent)"
    else:
        lead = "Late entry"

    if entry_style == "early":
        verdict = "This wallet tends to enter positions before momentum expansions."
    elif entry_style == "momentum":
        verdict = "This wallet enters during momentum phases."
    else:
        verdict = "This wallet tends to enter after price movements."

    return {
        "early_entry_ratio": round(early_ratio, 2),
        "late_entry_ratio": round(late_ratio, 2),
        "avg_lead_time": lead,
        "signal_alignment": sig_align,
        "verdict": verdict,
    }


def _build_influence(ef, signals, related):
    """Influence Map — how much this wallet affects markets."""
    if not ef:
        return {"influence_score": 0, "signal_contribution": 0, "cluster_overlap": 0,
                "capital_impact": 0, "capital_impact_fmt": "$0", "token_influence": [],
                "verdict": "Insufficient data"}

    sig_count = len(signals)
    cluster_count = len(related)
    capital = abs(ef.get("netUsd", 0) or 0)

    # Influence score: weighted composite
    sig_c = min(30, sig_count * 5)
    cluster_c = min(25, cluster_count * 5)
    cap_c = min(30, (math.log10(max(capital, 1)) / 8) * 30)
    trades = ef.get("trades", 0) or 0
    activity_c = min(15, min(trades, 30) * 0.5)
    score = int(min(99, max(0, sig_c + cluster_c + cap_c + activity_c)))

    tokens_inf = [s.get("token", "?") for s in signals[:4]]

    if score >= 60:
        verdict = "This wallet frequently participates in smart money clusters and contributes to multiple signals."
    elif score >= 30:
        verdict = "This wallet has moderate market influence through select signal contributions."
    else:
        verdict = "This wallet has limited direct influence on smart money signals."

    # Signal contribution per signal
    for s in signals:
        s["contribution"] = "high" if s.get("conviction", 0) >= 60 else "medium" if s.get("conviction", 0) >= 40 else "low"

    return {
        "influence_score": score,
        "signal_contribution": sig_count,
        "cluster_overlap": cluster_count,
        "capital_impact": round(capital, 2),
        "capital_impact_fmt": _fmt_usd(capital),
        "token_influence": tokens_inf,
        "verdict": verdict,
    }


def _build_credibility(ef, behavior, performance, signals):
    """Credibility Score with breakdown."""
    if not ef:
        return {"score": "low", "overall": 0, "breakdown": {
            "history_depth": "low", "signal_alignment": "low",
            "trade_consistency": "low", "capital_stability": "low"}}

    trades = ef.get("trades", 0) or 0

    # History depth
    hd = "high" if trades > 30 else "medium" if trades > 10 else "low"
    hd_n = 3 if hd == "high" else 2 if hd == "medium" else 1

    # Signal alignment
    sa = "high" if len(signals) >= 3 else "medium" if len(signals) >= 1 else "low"
    sa_n = 3 if sa == "high" else 2 if sa == "medium" else 1

    # Trade consistency
    confidence = behavior.get("confidence", 0)
    tc = "high" if confidence >= 70 else "medium" if confidence >= 50 else "low"
    tc_n = 3 if tc == "high" else 2 if tc == "medium" else 1

    # Capital stability
    net = abs(ef.get("netUsd", 0) or 0)
    vol = abs(ef.get("dexUsd", 0) or 0) + abs(ef.get("cexUsd", 0) or 0) or 1
    ratio = net / vol
    cs = "high" if ratio < 0.3 else "medium" if ratio < 0.6 else "low"
    cs_n = 3 if cs == "high" else 2 if cs == "medium" else 1

    avg = (hd_n + sa_n + tc_n + cs_n) / 4
    overall = "high" if avg >= 2.5 else "medium" if avg >= 1.5 else "low"
    overall_pct = int(avg / 3 * 100)

    return {
        "score": overall,
        "overall": overall_pct,
        "breakdown": {
            "history_depth": hd,
            "signal_alignment": sa,
            "trade_consistency": tc,
            "capital_stability": cs,
        }
    }


def _build_trading_style(ef, behavior):
    """Trading Style metrics."""
    if not ef:
        return {"avg_hold_time": "N/A", "trade_frequency": "N/A", "avg_position_size": "$0"}

    trades = ef.get("trades", 0) or 0
    vol = abs(ef.get("dexUsd", 0) or 0) + abs(ef.get("cexUsd", 0) or 0)
    avg_pos = vol / trades if trades > 0 else 0

    # Estimate hold time from holding_style
    hs = behavior.get("holding_style", "unknown")
    if hs == "short_term":
        hold = "< 6h"
    elif hs == "swing":
        hold = "6h - 3d"
    else:
        hold = "3d+"

    # Frequency estimate
    if trades > 30:
        freq = f"{trades}+ trades / day"
    elif trades > 10:
        freq = f"~{trades} trades / day"
    else:
        freq = f"~{trades} trades / day"

    return {
        "avg_hold_time": hold,
        "trade_frequency": freq,
        "avg_position_size": _fmt_usd(avg_pos),
        "avg_position_raw": round(avg_pos, 2),
    }



# ═══════════════════════════════════════════════════════════
# Wallet v4 — New analytical blocks
# ═══════════════════════════════════════════════════════════

def _build_alpha_score(wallet, perf, behavior, timing, influence, credibility):
    """Alpha Score Engine — composite intelligence score with breakdown."""
    pnl = abs(perf.get("pnl", 0))
    wr = perf.get("win_rate", 0)
    pnl_q = min(100, int((math.log10(max(pnl, 1)) / 7) * 70 + wr * 30))

    early = timing.get("early_entry_ratio", 0)
    late = timing.get("late_entry_ratio", 0)
    timing_edge = min(100, int(early * 80 + (1 - late) * 20))

    sig_acc = min(100, influence.get("influence_score", 0))

    cred_n = credibility.get("overall", 0)
    conf = behavior.get("confidence", 0)
    consistency = min(100, int((cred_n + conf) / 2))

    net = abs(perf.get("net_flow", 0))
    vol = perf.get("total_volume", 0) or 1
    ratio = net / vol
    risk_ctrl = min(100, int((1 - min(ratio, 1)) * 70 + (30 if wr > 0.5 else 0)))

    score = int(pnl_q * 0.25 + timing_edge * 0.25 + sig_acc * 0.2 + consistency * 0.2 + risk_ctrl * 0.1)
    score = min(99, max(1, score))

    return {
        "score": score,
        "breakdown": {
            "pnl_quality": pnl_q,
            "timing_edge": timing_edge,
            "signal_accuracy": sig_acc,
            "consistency": consistency,
            "risk_control": risk_ctrl,
        }
    }


def _build_wallet_rank(flows_col, alpha, chain_id, window):
    """Wallet Rank among all tracked wallets."""
    total = flows_col.count_documents({"chainId": chain_id, "window": window})
    total = max(total, 1)
    sc = alpha.get("score", 50)
    rank_num = max(1, int(total * (1 - sc / 100)))
    pct = round((1 - rank_num / total) * 100, 1)
    return {
        "rank": rank_num,
        "total": total,
        "percentile": pct,
        "label": f"Top {100 - pct:.1f}%" if pct >= 50 else f"Bottom {pct:.1f}%",
    }


def _build_trade_quality(ef, perf, behavior, tokens):
    """Trade Quality — entry quality, profit capture, execution efficiency."""
    if not ef:
        return {"entry_quality": "N/A", "profit_capture": 0, "execution_efficiency": "N/A",
                "risk_control": "N/A", "best_trades": []}

    entry = behavior.get("entry_style", "unknown")
    eq = {"early": "Early", "momentum": "On Time", "late": "Late"}.get(entry, "N/A")

    positive = [t for t in tokens if t.get("direction") == "buy"]
    total_pos = sum(abs(t.get("net_flow_usd", 0)) for t in positive)
    total_all = sum(abs(t.get("net_flow_usd", 0)) for t in tokens) or 1
    profit_cap = round(total_pos / total_all * 100)

    dex = abs(ef.get("dexUsd", 0) or 0)
    cex = abs(ef.get("cexUsd", 0) or 0)
    total_vol = dex + cex or 1
    if dex / total_vol > 0.8:
        exec_eff = "High"
    elif dex / total_vol > 0.5:
        exec_eff = "Medium"
    else:
        exec_eff = "Standard"

    wr = perf.get("win_rate", 0)
    rc = "High" if wr > 0.6 else "Medium" if wr > 0.4 else "Low"

    best = []
    for t in sorted(tokens, key=lambda x: x.get("net_flow_usd", 0), reverse=True)[:3]:
        if t.get("net_flow_usd", 0) > 0:
            best.append({"token": t["symbol"], "pnl_fmt": t["net_flow_fmt"]})

    return {
        "entry_quality": eq,
        "profit_capture": profit_cap,
        "execution_efficiency": exec_eff,
        "risk_control": rc,
        "best_trades": best,
    }


def _build_capital_rotation(tokens, behavior):
    """Capital Rotation — flow paths between tokens."""
    buys = [t for t in tokens if t.get("direction") == "buy"]
    sells = [t for t in tokens if t.get("direction") == "sell"]

    rotations = []
    for s in sells[:3]:
        for b in buys[:3]:
            if s["symbol"] != b["symbol"]:
                rotations.append({
                    "from": s["symbol"],
                    "to": b["symbol"],
                    "from_pct": s.get("allocation_pct", "0%"),
                    "to_pct": b.get("allocation_pct", "0%"),
                })
                if len(rotations) >= 4:
                    break
        if len(rotations) >= 4:
            break

    strat = behavior.get("strategy", "")
    freq = "High" if strat in ("rotation_trader", "active_trader") else "Medium" if strat in ("momentum_trader",) else "Low"

    acc = sum(1 for t in tokens if t.get("direction") == "buy")
    dist = sum(1 for t in tokens if t.get("direction") == "sell")
    total = len(tokens) or 1

    return {
        "rotations": rotations,
        "frequency": freq,
        "accumulation_pct": round(acc / total * 100),
        "distribution_pct": round(dist / total * 100),
        "rotation_pct": round(min(acc, dist) / total * 100),
    }


def _build_copy_potential(alpha, behavior, timing, credibility):
    """Copy Potential — can this wallet be copied profitably?"""
    sc = alpha.get("score", 50)
    early = timing.get("early_entry_ratio", 0)
    conf = behavior.get("confidence", 0)
    cred_overall = credibility.get("overall", 0)

    stab = min(100, int(conf * 0.5 + cred_overall * 0.5))
    rel = min(100, int(early * 60 + sc * 0.4))
    freq_raw = 70 if behavior.get("strategy") in ("active_trader", "rotation_trader", "momentum_trader") else 40

    composite = int(stab * 0.3 + rel * 0.35 + sc * 0.35)
    if composite >= 80:
        rating = "A"
    elif composite >= 65:
        rating = "B+"
    elif composite >= 50:
        rating = "B"
    elif composite >= 35:
        rating = "C"
    else:
        rating = "D"

    return {
        "strategy_stability": stab,
        "signal_reliability": rel,
        "trade_frequency": freq_raw,
        "composite": composite,
        "rating": rating,
    }


def _build_strategy_stability(behavior, credibility):
    """Strategy Stability — how consistent is the trading strategy."""
    conf = behavior.get("confidence", 0)
    cred = credibility.get("overall", 0)

    stable_pct = min(100, int(conf * 0.6 + cred * 0.4))
    changes = max(0, 5 - int(conf / 20))
    consistency = min(100, int((stable_pct + conf) / 2))
    primary = behavior.get("strategy_label", "Unknown")

    return {
        "stable_pct": stable_pct,
        "strategy_changes": changes,
        "consistency_score": consistency,
        "primary_strategy": primary,
    }


def _build_liquidity_impact(ef, perf):
    """Liquidity Impact — how much this wallet moves markets."""
    if not ef:
        return {"avg_trade_size": "$0", "avg_trade_raw": 0, "pool_impact": "None", "slippage": "0%", "market_influence": "None"}

    avg = perf.get("avg_trade", 0)
    vol = perf.get("total_volume", 0)

    if avg > 500_000:
        impact = "High"
        slip = "2.1%"
    elif avg > 100_000:
        impact = "Medium"
        slip = "0.8%"
    elif avg > 10_000:
        impact = "Low"
        slip = "0.3%"
    else:
        impact = "Minimal"
        slip = "< 0.1%"

    mi = "High" if vol > 5_000_000 else "Moderate" if vol > 1_000_000 else "Low"

    return {
        "avg_trade_size": _fmt_usd(avg),
        "avg_trade_raw": round(avg, 2),
        "pool_impact": impact,
        "slippage": slip,
        "market_influence": mi,
    }


def _build_signal_reliability(signals, influence):
    """Signal Reliability — how reliable are this wallet's signals."""
    total = len(signals)
    profitable = sum(1 for s in signals if s.get("conviction", 0) >= 50)
    accuracy = round(profitable / max(total, 1) * 100)

    best = []
    for s in sorted(signals, key=lambda x: x.get("conviction", 0), reverse=True)[:3]:
        best.append({"token": s.get("token", "?"), "type": s.get("type", "?"), "conviction": s.get("conviction", 0)})

    return {
        "signals_triggered": total,
        "profitable_signals": profitable,
        "accuracy": accuracy,
        "best_signals": best,
    }


def _build_portfolio_interpretation(tokens, behavior):
    """Portfolio Interpretation — text explaining positions."""
    if not tokens:
        return {"text": "No token activity detected.", "exposure_type": "none"}

    top = tokens[0] if tokens else {}
    sym = top.get("symbol", "?")
    alloc = top.get("allocation", 0)
    direction = top.get("direction", "buy")

    lines = []
    if alloc > 0.7:
        lines.append(f"Capital is heavily concentrated in {sym}.")
        lines.append(f"This indicates directional {'long' if direction == 'buy' else 'short'} exposure to {sym} momentum.")
        exposure = "concentrated"
    elif alloc > 0.4:
        lines.append(f"Primary exposure is {sym} with moderate diversification.")
        exposure = "moderate"
    else:
        lines.append("Portfolio is diversified across multiple tokens.")
        exposure = "diversified"

    if behavior.get("strategy") == "rotation_trader":
        lines.append("Active rotation suggests tactical position management.")
    elif behavior.get("strategy") == "early_accumulator":
        lines.append("Accumulation pattern suggests conviction in selected assets.")

    return {
        "text": " ".join(lines),
        "exposure_type": exposure,
        "top_token": sym,
        "top_allocation_pct": top.get("allocation_pct", "0%"),
    }


def _build_wallet_edge(alpha, behavior, timing, perf):
    """Wallet Edge — what makes this wallet strong."""
    bd = alpha.get("breakdown", {})
    timing_e = bd.get("timing_edge", 0)
    pnl_q = bd.get("pnl_quality", 0)
    sig_acc = bd.get("signal_accuracy", 0)
    risk = bd.get("risk_control", 0)

    edges = {
        "timing_edge": "High" if timing_e >= 70 else "Medium" if timing_e >= 40 else "Low",
        "execution_speed": "High" if behavior.get("execution_style") == "dex" and behavior.get("entry_style") == "early" else "Medium" if behavior.get("entry_style") == "early" else "Low",
        "token_discovery": "High" if sig_acc >= 70 else "Medium" if sig_acc >= 40 else "Low",
        "risk_discipline": "High" if risk >= 60 else "Medium" if risk >= 30 else "Low",
    }

    lines = []
    if timing_e >= 70:
        lines.append("Wallet consistently enters positions before market expansion.")
    elif timing_e >= 40:
        lines.append("Moderate timing advantage, enters near early momentum.")
    else:
        lines.append("Late entry pattern, follows existing market trends.")

    if pnl_q >= 70:
        lines.append("Strong profit capture with favorable risk-reward ratio.")

    return {**edges, "interpretation": " ".join(lines), "score": alpha.get("score", 0)}


def _build_trade_replay(trades, tokens, behavior):
    """Trade Replay — step-by-step strategy timeline."""
    recent = trades.get("recent", [])
    steps = []

    buys = [t for t in recent if t.get("side") == "Buy"]
    sells = [t for t in recent if t.get("side") == "Sell"]

    if sells:
        sold_tokens = [s["token"] for s in sells[:2]]
        steps.append(f"Reduce exposure in {', '.join(sold_tokens)}")
    if buys:
        bought_tokens = [b["token"] for b in buys[:3]]
        steps.append(f"Accumulate {', '.join(bought_tokens)}")
    if sells and buys:
        steps.append(f"Rotate capital: {sells[0]['token']} → {buys[0]['token']}")

    strat = behavior.get("strategy_label", "Unknown")
    if behavior.get("strategy") == "rotation_trader":
        steps.append("Active rotation between positions")
    elif behavior.get("strategy") == "early_accumulator":
        steps.append("Build positions ahead of momentum")

    timeline = []
    for i, t in enumerate(recent[:6]):
        timeline.append({
            "step": i + 1,
            "action": t.get("side", "?"),
            "token": t.get("token", "?"),
            "amount": t.get("amount_fmt", "$0"),
            "venue": t.get("venue", "?"),
        })

    return {
        "timeline": timeline,
        "strategy_steps": steps[:4],
        "strategy_label": strat,
        "total_trades": trades.get("total", 0),
    }


def _build_copy_signal(tokens, signals, copy_potential, insight):
    """Copy Signal Panel — current position interpretation."""
    top_token = tokens[0] if tokens else {}
    sym = top_token.get("symbol", "N/A")
    direction = top_token.get("direction", "buy")
    alloc = top_token.get("allocation", 0)

    # Find matching signal
    matching_signal = None
    for s in signals:
        if s.get("token", "").upper() == sym.upper():
            matching_signal = s
            break

    signal_type = matching_signal.get("type", "position") if matching_signal else "position"
    confidence = matching_signal.get("conviction", 0) if matching_signal else int(alloc * 70)

    bias = insight.get("signal_alignment", "neutral")

    return {
        "current_token": sym,
        "signal_type": signal_type.capitalize(),
        "confidence": confidence,
        "direction": direction,
        "bias": bias,
        "rating": copy_potential.get("rating", "N/A"),
        "composite": copy_potential.get("composite", 0),
    }
