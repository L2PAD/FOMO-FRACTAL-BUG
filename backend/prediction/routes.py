"""
Prediction Routes — Decision Desk API.

GET /api/prediction/markets   — raw Polymarket markets
GET /api/prediction/run       — full case pipeline with sections + repricing + timing
GET /api/prediction/alerts    — recent alerts
GET /api/prediction/watcher   — watcher status
POST /api/prediction/watcher/cycle — trigger manual watcher cycle

Routing:
  - price_threshold → quant pipeline (probability + exchange + alignment)
  - etf_catalyst / listing_catalyst / launch_catalyst → catalyst engine
  - unknown → skipped
"""
from fastapi import APIRouter, Request
import httpx

from prediction import (
    polymarket_client, event_classifier, probability_engine,
    edge_engine, alignment_engine, resolution_engine,
    pricing_engine, recommendation_engine,
)
from prediction.intelligence import catalyst_engine
from prediction import sizing_engine, execution_engine
from prediction.timing import repricing_detector, entry_timing_engine, market_stage_engine
from prediction.monitoring import snapshot_service, market_state_store, alert_engine
from prediction.timing import state_transition_engine
from prediction.monitoring import trigger_engine
from adapters import exchange_adapter, onchain_adapter, sentiment_adapter
from adapters import signal_intel_adapter
from adapters import portfolio_adapter
from adapters import case_intelligence_adapter
from adapters import social_intelligence_adapter
from adapters import event_feed_adapter
from adapters import project_intelligence_adapter
from adapters import execution_layer_adapter
from adapters import alert_engine_adapter
from adapters import weekly_digest_adapter
from adapters import execution_score_adapter
from adapters import telegram_delivery_adapter
from adapters import alert_correlation_adapter

router = APIRouter(prefix="/api/prediction", tags=["prediction"])

CATALYST_TYPES = {"etf_catalyst", "listing_catalyst", "launch_catalyst", "token_launch"}


def _opportunity_score(edge_val: float, confidence: float, align_score: float,
                       market: dict, resolution: dict, structural_risk: float = 0) -> float:
    """Normalized opportunity score 0-1."""
    net_edge = abs(edge_val)
    res_risk = resolution.get("resolution_risk_score", 0)
    edge_norm = min(net_edge / 0.20, 1.0)

    liq = market.get("liquidity", 0)
    liq_score = 1.0 if liq >= 100_000 else (0.8 if liq >= 50_000 else (0.5 if liq >= 10_000 else 0.1))
    spread_penalty = min(market.get("spread", 0) / 0.30, 1.0)

    score = (
        edge_norm * 0.30
        + confidence * 0.18
        + align_score * 0.12
        + liq_score * 0.10
        - spread_penalty * 0.08
        - structural_risk * 0.10
        - res_risk * 0.12
    )
    return max(0.0, min(1.0, round(score, 4)))


def _build_quant_case(m: dict, classified: dict, exchange, onchain, sentiment) -> dict:
    """Build a case through the quant pipeline (price threshold markets)."""
    asset = classified.get("asset", "BTC")
    resolution = resolution_engine.analyze(m.get("question", ""), m.get("raw_rules"))
    prob = probability_engine.compute_probability(m, exchange, onchain, sentiment)
    align = alignment_engine.compute_alignment(m, exchange, onchain, sentiment)
    edge = edge_engine.compute_edge(m, prob)
    pricing = pricing_engine.analyze(m, prob["fair_yes_prob"], edge["raw_edge"])

    reco = recommendation_engine.recommend(
        edge=edge["net_edge"],
        fair_prob=prob["fair_yes_prob"],
        model_confidence=prob["model_confidence"],
        alignment_score=align["alignment_score"],
        resolution=resolution,
        pricing=pricing,
        structural_risk=prob.get("structural_risk", {}),
        biases=align.get("biases"),
        onchain=onchain,
        sentiment=sentiment,
    )

    opp_score = _opportunity_score(
        edge["net_edge"], prob["model_confidence"], align["alignment_score"],
        m, resolution, prob.get("structural_risk", {}).get("combined_risk", 0),
    )

    analysis_obj = {
        "fair_prob": prob["fair_yes_prob"],
        "market_prob": edge["implied_prob"],
        "raw_edge": edge["raw_edge"],
        "net_edge": edge["net_edge"],
        "model_confidence": prob["model_confidence"],
        "alignment_score": align["alignment_score"],
        "structural_risk": prob.get("structural_risk", {}),
        "regime": prob.get("regime"),
        "components": prob.get("components"),
        "biases": align.get("biases"),
        "conflict_flags": align.get("conflict_flags"),
    }

    reco_obj = {
        "action": reco["action"],
        "conviction": reco["conviction"],
        "size": reco["size"],
    }

    sizing = sizing_engine.compute(analysis_obj, reco_obj, resolution, pricing, m)
    exec_plan = execution_engine.build_plan(reco_obj, sizing)

    return {
        "market_id": m.get("market_id"),
        "question": m.get("question"),
        "asset": asset,
        "market_type": "quant",
        "event_type": classified.get("event_type", "price_threshold"),
        "threshold": classified.get("threshold"),
        "comparator": classified.get("comparator"),
        "entities": classified.get("entities", []),
        "end_date": m.get("end_date"),
        "volume": m.get("volume"),
        "liquidity": m.get("liquidity"),
        "resolution": resolution,
        "pricing": pricing,
        "analysis": analysis_obj,
        "recommendation": reco_obj,
        "sizing": sizing,
        "execution": exec_plan,
        "why_now": reco.get("why_now", []),
        "why_not": reco.get("why_not", []),
        "reasoning": reco.get("reasoning", []),
        "opportunity_score": opp_score,
    }


async def _build_catalyst_case(m: dict, classified: dict, onchain, sentiment) -> dict:
    """Build a case through the catalyst engine (ETF/listing/launch markets)."""
    asset = classified.get("asset")
    entities = classified.get("entities", [])
    event_type = classified.get("event_type", "unknown")

    resolution = resolution_engine.analyze(m.get("question", ""), m.get("raw_rules"))

    # Build related events via Event Feed (curated, deduplicated)
    related_events = await _gather_related_events(entities, event_type)

    # Run catalyst engine
    cat_result = catalyst_engine.run(
        decoded={"event_type": event_type, "entities": entities, "deadline": m.get("end_date")},
        related_events=related_events,
    )

    fair_prob = cat_result["fair_yes_prob"]
    implied_prob = m.get("yes_price", 0.5)
    raw_edge = round(fair_prob - implied_prob, 4)

    # Catalyst alignment — use onchain/sentiment for confidence, not probability
    align = _catalyst_alignment(cat_result, onchain, sentiment)

    pricing = pricing_engine.analyze(m, fair_prob, raw_edge)

    # Net edge after confidence penalty
    conf = cat_result["model_confidence"]
    penalty = max(0, 1.0 - conf) * abs(raw_edge) * 0.15
    net_edge = round(raw_edge - penalty if raw_edge >= 0 else raw_edge + penalty, 4)

    # Recommendation
    reco = recommendation_engine.recommend(
        edge=net_edge,
        fair_prob=fair_prob,
        model_confidence=conf,
        alignment_score=align["alignment_score"],
        resolution=resolution,
        pricing=pricing,
        structural_risk=cat_result.get("structural_risk", {}),
        biases=align.get("biases"),
        onchain=onchain,
        sentiment=sentiment,
    )

    opp_score = _opportunity_score(
        net_edge, conf, align["alignment_score"],
        m, resolution, cat_result.get("structural_risk", {}).get("combined_risk", 0),
    )

    analysis_obj = {
        "fair_prob": fair_prob,
        "market_prob": implied_prob,
        "raw_edge": raw_edge,
        "net_edge": net_edge,
        "model_confidence": conf,
        "alignment_score": align["alignment_score"],
        "structural_risk": cat_result.get("structural_risk", {}),
        "regime": "CATALYST",
        "components": cat_result.get("components"),
        "biases": align.get("biases"),
        "conflict_flags": align.get("conflict_flags", []),
    }

    reco_obj = {
        "action": reco["action"],
        "conviction": reco["conviction"],
        "size": reco["size"],
    }

    sizing = sizing_engine.compute(analysis_obj, reco_obj, resolution, pricing, m)
    exec_plan = execution_engine.build_plan(reco_obj, sizing)

    return {
        "market_id": m.get("market_id"),
        "question": m.get("question"),
        "asset": asset,
        "market_type": "catalyst",
        "event_type": event_type,
        "threshold": None,
        "comparator": None,
        "entities": entities,
        "end_date": m.get("end_date"),
        "volume": m.get("volume"),
        "liquidity": m.get("liquidity"),
        "resolution": resolution,
        "pricing": pricing,
        "analysis": analysis_obj,
        "recommendation": reco_obj,
        "sizing": sizing,
        "execution": exec_plan,
        "why_now": reco.get("why_now", []) + cat_result.get("drivers", []),
        "why_not": reco.get("why_not", []) + cat_result.get("risks", []),
        "reasoning": reco.get("reasoning", []),
        "opportunity_score": opp_score,
    }


async def _gather_related_events(entities: list, event_type: str) -> list[dict]:
    """
    Gather related events via Event Feed service (curated, deduplicated).
    Falls back to direct MongoDB if Node service is unavailable.
    """
    try:
        events = await event_feed_adapter.get_related_events(entities, event_type, 48)
        if events:
            return events
    except Exception:
        pass

    # Fallback: direct MongoDB
    import os
    from pymongo import MongoClient, DESCENDING
    try:
        db = MongoClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "intelligence_engine")]
        query = {}
        if entities:
            entity_pattern = "|".join(e.lower() for e in entities)
            query["$or"] = [
                {"title": {"$regex": entity_pattern, "$options": "i"}},
                {"data.symbol": {"$in": [e.upper() for e in entities]}},
            ]

        docs = list(db["notification_events"].find(
            query, {"_id": 0}
        ).sort("timestamp", DESCENDING).limit(20))

        events = []
        for d in docs:
            events.append({
                "title": d.get("title", ""),
                "text": d.get("message", d.get("description", "")),
                "source": d.get("source", "internal"),
                "source_type": d.get("type", "signal"),
                "source_quality": 0.5,
                "relevance_score": 0.5,
            })
        return events
    except Exception:
        return []


def _catalyst_alignment(cat_result: dict, onchain: dict | None, sentiment: dict | None) -> dict:
    """Compute alignment for catalyst markets: catalyst + onchain + sentiment."""
    cat_bias = cat_result.get("bias", "neutral")
    biases = {"catalyst": cat_bias}
    conflict_flags = []
    reasoning = []

    weighted_confirm = 0.0
    weighted_oppose = 0.0
    total_weight = 0.0

    # Catalyst itself: weight 1.2
    total_weight += 1.2
    weighted_confirm += 1.2 if cat_bias in ("bullish",) else 0

    if onchain:
        oc_bias = onchain.get("bias", "neutral")
        biases["onchain"] = oc_bias
        w = 0.8 * (0.5 + onchain.get("strength", 0.3))
        total_weight += w
        if oc_bias == cat_bias:
            weighted_confirm += w
            reasoning.append(f"OnChain confirms catalyst thesis ({oc_bias})")
        elif oc_bias != "neutral":
            weighted_oppose += w
            conflict_flags.append("OnChain opposes catalyst direction")
            reasoning.append(f"OnChain conflicts ({oc_bias} vs {cat_bias})")

    if sentiment:
        s_bias = sentiment.get("bias", "neutral")
        biases["sentiment"] = s_bias
        w = 0.5 * (0.5 + sentiment.get("strength", 0.2))
        total_weight += w
        if s_bias == cat_bias:
            weighted_confirm += w
            reasoning.append(f"Sentiment aligns with catalyst ({s_bias})")
        elif s_bias != "neutral":
            weighted_oppose += w
            conflict_flags.append("Sentiment opposes catalyst direction")
            reasoning.append(f"Sentiment conflicts ({s_bias} vs {cat_bias})")

    if total_weight > 0:
        alignment_score = (weighted_confirm - weighted_oppose + total_weight) / (2 * total_weight)
    else:
        alignment_score = 0.5
    alignment_score = max(0.0, min(1.0, alignment_score))

    return {
        "alignment_score": round(alignment_score, 4),
        "biases": biases,
        "conflict_flags": conflict_flags,
        "reasoning": reasoning,
    }


@router.get("/markets")
async def get_markets(limit: int = 30):
    markets = await polymarket_client.fetch_markets(limit=limit)
    return {"ok": True, "count": len(markets), "markets": markets}


@router.get("/run")
async def run_prediction(limit: int = 50):
    """Full Decision Desk pipeline — returns sectioned case objects with repricing + timing."""
    markets = await polymarket_client.fetch_markets(limit=limit)

    exchange_btc = exchange_adapter.get_forecast("BTC", "30D")
    exchange_eth = exchange_adapter.get_forecast("ETH", "30D")
    onchain_btc = onchain_adapter.get_flow_signal("BTC")
    onchain_eth = onchain_adapter.get_flow_signal("ETH")
    sentiment_btc = sentiment_adapter.get_sentiment_signal("BTC")
    sentiment_eth = sentiment_adapter.get_sentiment_signal("ETH")

    cases = []
    skipped = 0
    alerts_fired = []

    for m in markets:
        classified = event_classifier.classify(m["question"])
        etype = classified["event_type"]
        mtype = classified.get("market_type", "unknown")

        if etype == "unknown":
            skipped += 1
            continue

        asset = classified.get("asset", "BTC")
        onchain = onchain_btc if asset in ("BTC", None) else onchain_eth
        sentiment = sentiment_btc if asset in ("BTC", None) else sentiment_eth

        try:
            if mtype == "quant":
                exchange = exchange_btc if asset == "BTC" else exchange_eth
                case = _build_quant_case(m, classified, exchange, onchain, sentiment)
            elif mtype == "catalyst" or etype in CATALYST_TYPES:
                case = await _build_catalyst_case(m, classified, onchain, sentiment)
            else:
                skipped += 1
                continue

            # --- Stage 5: Repricing + Timing ---
            # Save snapshot
            snapshot_service.save_snapshot(
                m["market_id"], m.get("yes_price", 0.5),
                m.get("volume", 0), m.get("liquidity", 0), m.get("spread", 0),
            )

            # Compute deltas
            deltas = snapshot_service.compute_deltas(
                m["market_id"], m.get("yes_price", 0.5), m.get("volume", 0),
                m.get("liquidity", 0),
            )

            # Repricing detection
            repricing = repricing_detector.analyze(
                m.get("yes_price", 0.5), case["analysis"]["fair_prob"],
                m.get("volume", 0), m.get("liquidity", 0), m.get("spread", 0),
                deltas,
            )
            case["repricing"] = repricing

            # Entry timing
            entry = entry_timing_engine.decide(
                edge=case["analysis"]["net_edge"],
                confidence=case["analysis"]["model_confidence"],
                alignment=case["analysis"]["alignment_score"],
                repricing_state=repricing["repricing_state"],
                spread=m.get("spread", 0),
                liquidity=m.get("liquidity", 0),
                resolution_risk=case["resolution"].get("resolution_risk_score", 0),
                action=case["recommendation"]["action"],
                acceleration=repricing.get("acceleration", 0),
                speed_score=repricing.get("speed_score", 0),
            )
            case["entry_timing"] = entry

            # Market stage
            stage = market_stage_engine.compute_stage(
                repricing["repricing_state"],
                case["analysis"]["net_edge"],
                case["analysis"]["model_confidence"],
                case["recommendation"]["action"],
                case["sizing"]["allowed"],
                deltas.get("snap_count", 0),
            )
            case["market_stage"] = stage

            # State transitions + alerts
            old_state = market_state_store.get_state(m["market_id"])
            transitions = state_transition_engine.detect_transitions(old_state, case)
            case["transitions"] = transitions

            if transitions:
                triggers = trigger_engine.classify_transitions(transitions)
                signal_hash = market_state_store.compute_signal_hash(case)
                for trig in triggers:
                    if trig["priority"] in ("high", "medium"):
                        if trigger_engine.should_fire(m["market_id"], trig["alert_type"], signal_hash):
                            alert = alert_engine.create_alert(case, trig)
                            alerts_fired.append(alert)
                            trigger_engine.log_alert(m["market_id"], trig["alert_type"], signal_hash, alert)

            # Update state store
            new_state = market_state_store.build_state_from_case(case)
            market_state_store.upsert_state(m["market_id"], new_state)

            # --- Stage 6: Signal Intelligence ---
            try:
                intel_batch = await signal_intel_adapter.get_market_intelligence(
                    market_id=m["market_id"],
                    asset=asset,
                    entities=classified.get("entities", [asset] if asset else []),
                    event_type=etype,
                    current_prob=m.get("yes_price", 0.5),
                    move_6h=deltas.get("delta_6h", 0),
                    move_24h=deltas.get("delta_24h", 0),
                    volume=m.get("volume", 0),
                    repricing_state=repricing.get("repricing_state"),
                )
                intel_info = signal_intel_adapter.extract_smart_drivers(intel_batch)
                case["signal_intel"] = intel_info
                # Upgrade drivers with smart explanations
                if intel_info.get("smart_drivers"):
                    case["why_now"] = intel_info["smart_drivers"][:2] + (case.get("why_now") or [])[:1]
            except Exception:
                pass

            cases.append(case)
        except Exception as e:
            import logging
            logging.getLogger("prediction").warning(f"Pipeline error for {m.get('market_id')}: {e}")
            skipped += 1

    # Sort by opportunity score
    cases.sort(key=lambda c: c["opportunity_score"], reverse=True)

    # --- Stage 7: Portfolio Brain ---
    try:
        portfolio_cases = [
            {
                "market_id": c["market_id"],
                "question": c.get("question", ""),
                "asset": c.get("asset", "BTC"),
                "event_type": c.get("event_type", "generic_crypto"),
                "entities": c.get("entities", []),
                "end_date": c.get("end_date"),
                "recommendation": c.get("recommendation", {}),
                "analysis": c.get("analysis", {}),
                "resolution": c.get("resolution", {}),
                "sizing": c.get("sizing", {}),
            }
            for c in cases
        ]
        portfolio_results = await portfolio_adapter.assess_batch(portfolio_cases)
        for c in cases:
            mid = c["market_id"]
            if mid in portfolio_results:
                c["portfolio"] = portfolio_results[mid]
    except Exception:
        pass

    # --- Case Intelligence Engine ---
    try:
        ci_cases = [
            {
                "market_id": c["market_id"],
                "question": c.get("question", ""),
                "asset": c.get("asset", "BTC"),
                "event_type": c.get("event_type", "generic_crypto"),
                "entities": c.get("entities", []),
                "end_date": c.get("end_date"),
                "current_prob": c.get("current_prob"),
                "liquidity": c.get("liquidity"),
                "volume_24h": c.get("volume_24h"),
                "spread": c.get("spread"),
                "move_1h": c.get("pricing", {}).get("move_1h"),
                "move_6h": c.get("pricing", {}).get("move_6h"),
                "pricing_state": c.get("pricing", {}),
            }
            for c in cases
        ]
        ci_results = await case_intelligence_adapter.analyze_batch(ci_cases)
        for c in cases:
            mid = c["market_id"]
            if mid in ci_results:
                c["intelligence"] = ci_results[mid]
    except Exception:
        pass

    # --- Social Intelligence 2.0 ---
    try:
        assets = list({c.get("asset", "BTC") for c in cases})
        si_results = await social_intelligence_adapter.analyze_social_batch(assets)
        for c in cases:
            asset = c.get("asset", "BTC")
            if asset in si_results:
                c["socialIntel"] = si_results[asset]
    except Exception:
        pass

    # --- Project Intelligence Engine ---
    try:
        pi_assets = list({c.get("asset", "BTC") for c in cases})
        pi_batch = await project_intelligence_adapter.batch_analyze(pi_assets)
        pi_results = pi_batch.get("results", {}) if pi_batch.get("ok") else {}
        for c in cases:
            asset = c.get("asset", "BTC").upper()
            if asset in pi_results:
                pi = pi_results[asset]
                c["projectIntel"] = {
                    "verdict": pi.get("thesis", {}).get("projectVerdict", "MIXED"),
                    "overallScore": pi.get("thesis", {}).get("overallScore", 0.5),
                    "tokenomics": pi.get("tokenomics", {}).get("verdict", "MID"),
                    "valuation": pi.get("valuation", {}).get("valuation", "FAIR"),
                    "unlockRisk": pi.get("unlockPressure", {}).get("riskLevel", "LOW"),
                    "teamFund": pi.get("teamFund", {}).get("verdict", "MID"),
                    "launch": pi.get("launch", {}).get("verdict", "MID"),
                    "bullCase": pi.get("thesis", {}).get("bullCase", []),
                    "bearCase": pi.get("thesis", {}).get("bearCase", []),
                    "keyRisks": pi.get("thesis", {}).get("keyRisks", []),
                    "whatMarketMisses": pi.get("thesis", {}).get("whatMarketMisses", []),
                }
                # Intelligence integration: append project notes to case intelligence
                if c.get("intelligence") and pi.get("thesis", {}).get("whatMarketMisses"):
                    existing_gaps = c["intelligence"].get("whatMarketMisses", [])
                    c["intelligence"]["whatMarketMisses"] = (
                        existing_gaps + pi["thesis"]["whatMarketMisses"]
                    )[:6]
    except Exception:
        pass

    # --- Execution Layer / Microstructure ---
    try:
        exec_results = await execution_layer_adapter.batch_analyze(cases)
        for c in cases:
            mid = c["market_id"]
            if mid in exec_results and exec_results[mid]:
                ex = exec_results[mid]
                c["executionLayer"] = {
                    "entryStyle": ex.get("entry", {}).get("entryStyle", "ENTER_LIMIT"),
                    "entryQualityScore": ex.get("entry", {}).get("entryQualityScore", 0),
                    "slippageRisk": ex.get("entry", {}).get("slippageRisk", 0),
                    "spreadRegime": ex.get("entry", {}).get("spreadRegime", "NORMAL"),
                    "depthQuality": ex.get("entry", {}).get("depthQuality", "OK"),
                    "chaseRisk": ex.get("entry", {}).get("chaseRisk", 0),
                    "missRisk": ex.get("entry", {}).get("missRisk", 0),
                    "maxSlippageBps": ex.get("entry", {}).get("maxSlippageBps", 0),
                    "entryNote": ex.get("entry", {}).get("note", ""),
                    "scalingBias": ex.get("scaling", {}).get("scalingBias", "HOLD"),
                    "scalingReason": ex.get("scaling", {}).get("reason", ""),
                    "exitAction": ex.get("exit", {}).get("action", "HOLD"),
                    "exitConfidence": ex.get("exit", {}).get("confidence", 0),
                    "exitReasons": ex.get("exit", {}).get("reasons", []),
                    "edgeCompression": ex.get("edgeCompression", {}).get("edgeCompression", 0),
                    "edgeCompressed": ex.get("edgeCompression", {}).get("compressed", False),
                }
    except Exception:
        pass

    # --- Alert Engine: detect state transitions and push alerts ---
    try:
        import asyncio
        asyncio.ensure_future(alert_engine_adapter.process_alerts(cases))
    except Exception:
        pass

    # --- Execution Score: evaluate execution quality ---
    try:
        score_results = await execution_score_adapter.batch_evaluate(cases)
        for c in cases:
            mid = c["market_id"]
            if mid in score_results and score_results[mid]:
                sr = score_results[mid]
                c["executionScore"] = {
                    "score": sr.get("executionScore", 0),
                    "grade": sr.get("executionGrade", "N/A"),
                    "entryQuality": sr.get("entry", {}).get("quality", ""),
                    "entryPosition": sr.get("entry", {}).get("position", ""),
                    "timingQuality": sr.get("timing", {}).get("quality", ""),
                    "missedWindow": sr.get("timing", {}).get("missedBetterWindow", False),
                    "slippageLeakage": sr.get("slippage", {}).get("leakage", 0),
                    "missedMove": sr.get("opportunity", {}).get("missedMove", 0),
                    "opportunityReason": sr.get("opportunity", {}).get("reason", "NONE"),
                    "regime": sr.get("context", {}).get("regime", ""),
                    "narrative": sr.get("context", {}).get("narrativePhase", ""),
                    "direction": sr.get("context", {}).get("direction", ""),
                    "lessons": sr.get("lessons", []),
                }
    except Exception:
        pass

    # --- Build sections on backend (expanded with timing-aware sections) ---
    best_opportunities = []
    new_mispricings = []
    emerging_opportunities = []
    entry_windows_open = []
    repricing_now = []
    watchlist = []
    late_moves = []
    avoid_zone = []
    state_changes = []

    for c in cases:
        action = c["recommendation"]["action"]
        pricing_state = c["pricing"].get("market_state", "")
        rstate = c.get("repricing", {}).get("repricing_state", "")
        entry_action = c.get("entry_timing", {}).get("entry_action", "")
        stage = c.get("market_stage", "")
        has_transitions = bool(c.get("transitions"))

        # State changes (any market with transitions)
        if has_transitions and any(t.get("priority") in ("high", "medium") for t in c.get("transitions", [])):
            state_changes.append(c)

        # Best opportunities
        if action in ("YES_NOW", "NO_NOW"):
            best_opportunities.append(c)

        # Emerging: fresh mispricing, not yet repricing
        elif rstate == "fresh_mispricing" and action not in ("AVOID",):
            emerging_opportunities.append(c)

        # Entry windows open
        elif entry_action in ("enter_now", "enter_limit") and rstate in ("fresh_mispricing", "early_repricing"):
            entry_windows_open.append(c)

        # New mispricings
        elif action in ("YES_SMALL", "NO_SMALL") and pricing_state in ("underpriced", "early_repricing"):
            new_mispricings.append(c)

        # Repricing now
        elif rstate in ("active_repricing", "early_repricing"):
            repricing_now.append(c)

        # Late moves
        elif rstate in ("late_repricing", "overheated"):
            late_moves.append(c)

        # Watchlist
        elif action in ("YES_SMALL", "NO_SMALL", "WATCH", "WAIT", "GOOD_IDEA_BAD_PRICE"):
            watchlist.append(c)

        # Avoid
        else:
            avoid_zone.append(c)

    # --- Auto-save traces for Outcome Lab (non-blocking) ---
    try:
        trace_cases = [c for c in cases if c.get("recommendation", {}).get("action") not in ("AVOID",)]
        if trace_cases:
            node_url = "http://127.0.0.1:8003"
            async with httpx.AsyncClient(timeout=5.0) as hc:
                await hc.post(f"{node_url}/api/outcome-lab/trace/batch", json={"cases": trace_cases})
    except Exception:
        pass

    return {
        "ok": True,
        "total_markets": len(markets),
        "classified": len(cases),
        "skipped": skipped,
        "alerts_count": len(alerts_fired),
        "exchange_available": {
            "BTC": exchange_btc is not None,
            "ETH": exchange_eth is not None,
        },
        "onchain_available": {
            "BTC": onchain_btc is not None,
            "ETH": onchain_eth is not None,
        },
        "sentiment_available": {
            "BTC": sentiment_btc is not None,
            "ETH": sentiment_eth is not None,
        },
        "sections": {
            "best_opportunities": best_opportunities,
            "emerging_opportunities": emerging_opportunities,
            "entry_windows_open": entry_windows_open,
            "new_mispricings": new_mispricings,
            "repricing_now": repricing_now,
            "watchlist": watchlist,
            "late_moves": late_moves,
            "avoid_zone": avoid_zone,
            "state_changes": state_changes,
        },
        "recent_alerts": alerts_fired[:10],
    }


@router.get("/alerts")
async def get_alerts(limit: int = 50):
    """Get recent prediction alerts."""
    alerts = alert_engine.get_recent_alerts(limit=limit)
    return {"ok": True, "count": len(alerts), "alerts": alerts}


@router.get("/watcher/status")
async def watcher_status():
    """Get watcher status."""
    from prediction.monitoring.market_watcher import get_watcher_status
    return {"ok": True, **get_watcher_status()}


@router.post("/watcher/cycle")
async def trigger_watcher_cycle():
    """Manually trigger a watcher cycle."""
    from prediction.monitoring.market_watcher import run_cycle
    result = await run_cycle(limit=100)
    return {
        "ok": True,
        "summary": result["summary"],
        "alerts_count": len(result["alerts"]),
        "cases_count": len(result["cases"]),
    }



@router.get("/alert-feed")
async def get_alert_feed(limit: int = 50):
    """Get alert feed from Node.js Alert Engine (new system)."""
    alerts = await alert_engine_adapter.get_history(limit)
    stats = await alert_engine_adapter.get_stats()
    return {"ok": True, "alerts": alerts, "stats": stats, "count": len(alerts)}


@router.post("/weekly-digest/generate")
async def generate_weekly_digest(from_date: str = None, to_date: str = None):
    """Generate a new weekly learning digest."""
    digest = await weekly_digest_adapter.generate(from_date, to_date)
    if digest:
        return {"ok": True, "digest": digest}
    return {"ok": False, "error": "Generation failed"}


@router.get("/weekly-digest/latest")
async def get_latest_digest():
    """Get the most recent weekly digest."""
    digest = await weekly_digest_adapter.get_latest()
    return {"ok": True, "digest": digest}


@router.get("/weekly-digest/history")
async def get_digest_history(limit: int = 10):
    """Get weekly digest history."""
    digests = await weekly_digest_adapter.get_history(limit)
    return {"ok": True, "digests": digests, "count": len(digests)}



@router.get("/execution-score/styles")
async def get_execution_styles():
    """Get execution style performance stats."""
    data = await execution_score_adapter.get_style_performance()
    return {"ok": True, **data}



# ── Telegram Delivery proxy routes ──

@router.post("/telegram-delivery/connect")
async def telegram_connect(request: Request):
    body = await request.json()
    return await telegram_delivery_adapter.connect(body.get("chatId", ""))

@router.get("/telegram-delivery/stats")
async def telegram_stats():
    return await telegram_delivery_adapter.get_stats()

@router.post("/telegram-delivery/test")
async def telegram_test(request: Request):
    body = await request.json()
    return await telegram_delivery_adapter.test_alert(body.get("chatId", ""), body.get("type", "ENTRY_ALERT"))

@router.post("/telegram-delivery/preferences")
async def telegram_prefs_update(request: Request):
    body = await request.json()
    chat_id = body.pop("chatId", "")
    return await telegram_delivery_adapter.update_preferences(chat_id, body)

@router.get("/telegram-delivery/subscribers")
async def telegram_subscribers():
    return await telegram_delivery_adapter.get_subscribers()

@router.post("/telegram-delivery/deliver")
async def telegram_deliver(request: Request):
    body = await request.json()
    return await telegram_delivery_adapter.deliver_alert(body)

@router.post("/telegram-delivery/deliver-weekly")
async def telegram_deliver_weekly(request: Request):
    body = await request.json()
    return await telegram_delivery_adapter.deliver_weekly(body)



# ── Alert Correlation proxy routes ──

@router.post("/alert-correlation/analyze")
async def correlation_analyze(request: Request):
    body = await request.json()
    return await alert_correlation_adapter.analyze(body.get("alerts", []))

@router.get("/alert-correlation/meta-alerts")
async def correlation_meta_alerts():
    return await alert_correlation_adapter.get_meta_alerts()

@router.get("/alert-correlation/history")
async def correlation_history():
    return await alert_correlation_adapter.get_history()

@router.get("/alert-correlation/regime")
async def correlation_regime():
    return await alert_correlation_adapter.get_regime()
