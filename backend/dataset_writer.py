"""
Dataset Writer — closes the loop: signal + context + outcome → dataset_entries

Reads resolved entries from sentiment_training_dataset_v3 and signal_log,
enriches with graph intelligence, builds production dataset rows for ML training.

Schema follows the FINAL dataset_entries format:
  meta → signal → sentiment → actor → graph → market → timing → structure → composite → outcome → quality
"""

import logging
from datetime import datetime, timezone
from ml_ops import get_db

log = logging.getLogger("dataset_writer")


# ─── Composite Feature Computation ───

def compute_composites(row):
    """Compute alpha composite features from base features."""
    s = row.get("sentiment", {})
    a = row.get("actor", {})
    t = row.get("timing", {})
    st = row.get("structure", {})

    s_conf = s.get("confidence", 0) or 0
    a_score = a.get("actor_score", 0) or 0
    coord = st.get("coordination", 0) or 0
    cluster = st.get("cluster_size", 0) or 0
    early = t.get("is_early", 0) or 0

    row["composite"] = {
        "alpha_1": round(early * a_score * s_conf, 4),
        "alpha_2": round(a_score * coord, 4),
        "alpha_3": round(s_conf * cluster, 4),
        "alpha_4": round(early * cluster * a_score, 4),
    }
    return row


# ─── Build Dataset Row from sentiment_training_dataset_v3 ───

def build_row_from_v3(sample, graph_context=None):
    """Build a dataset_entries row from a resolved v3 sample + graph enrichment."""
    meta = sample.get("meta", {})
    sentiment = sample.get("sentiment", {})
    actor = sample.get("actor", {})
    market = sample.get("market", {})
    signal = sample.get("signal", {})
    outcome = sample.get("outcome", {})
    quality = sample.get("quality", {})

    # Determine timing
    position = signal.get("position", "MID")
    is_early = 1 if position == "EARLY" else 0
    is_mid = 1 if position == "MID" else 0
    is_late = 1 if position == "LATE" else 0

    # Map sentiment intent to binary flags
    intent = sentiment.get("intent", "").upper()
    intent_bullish = 1 if intent in ("BULLISH", "BULLISH_SIGNAL") else 0
    intent_bearish = 1 if intent in ("BEARISH", "BEARISH_SIGNAL", "WARNING") else 0
    intent_hype = 1 if intent == "HYPE" else 0
    intent_warning = 1 if intent == "WARNING" else 0

    # Regime flags
    regime = (market.get("regime") or "RANGE").upper()
    regime_trending = 1 if regime == "TRENDING" else 0
    regime_range = 1 if regime == "RANGE" else 0
    regime_overheated = 1 if regime == "OVERHEATED" else 0

    # Graph features (from enrichment or defaults)
    gc = graph_context or {}

    # Compute event type for quality
    from outcome_resolver import detect_event_type
    event_type, event_type_conf = detect_event_type(sample)

    row = {
        "meta": {
            "signal_id": meta.get("source_id", ""),
            "token": market.get("token", ""),
            "project": "",
            "source": "sentiment_v3",
            "created_at": meta.get("created_at", ""),
            "resolved_at": outcome.get("resolved_at", ""),
            "written_at": datetime.now(timezone.utc).isoformat(),
        },
        "signal": {
            "type": sentiment.get("intent", "UNKNOWN"),
            "strength": round(abs(sentiment.get("score", 0)) * 100, 1),
            "confidence": round((sentiment.get("confidence", 0) or 0) * 100, 1),
        },
        "sentiment": {
            "intent_bullish": intent_bullish,
            "intent_bearish": intent_bearish,
            "intent_hype": intent_hype,
            "intent_warning": intent_warning,
            "confidence": round(sentiment.get("confidence", 0) or 0, 4),
        },
        "actor": {
            "actor_score": round(actor.get("score", 0) or 0, 4),
            "actor_hit_rate": round(actor.get("hit_rate", 0) or 0, 4),
            "actor_early_ratio": round(actor.get("early_ratio", 0) or 0, 4),
            "actor_consistency": round(actor.get("consistency", 0) or 0, 4),
            "actor_count": signal.get("unique_actors_1h", 0) or 0,
            "alpha_actor_present": 1 if (actor.get("score", 0) or 0) > 0.6 else 0,
        },
        "graph": {
            "entity_pressure": round(gc.get("entity_pressure", 0) or 0, 4),
            "attention_flow": round(gc.get("attention_flow", 0) or 0, 4),
            "alpha_source_strength": round(gc.get("alpha_source", 0) or 0, 4),
            "fund_pressure": round(gc.get("fund_pressure", 0) or 0, 4),
            "fund_count": gc.get("fund_count", 0) or 0,
        },
        "market": {
            "volatility": round(market.get("volatility", 0) or 0, 4),
            "momentum": round(market.get("momentum", 0) or 0, 4),
            "regime_trending": regime_trending,
            "regime_range": regime_range,
            "regime_overheated": regime_overheated,
        },
        "timing": {
            "is_early": is_early,
            "is_mid": is_mid,
            "is_late": is_late,
            "freshness_sec": round(signal.get("freshness_sec", 0) or 0, 1),
        },
        "structure": {
            "mentions": signal.get("mentions_1h", 0) or 0,
            "unique_actors": signal.get("unique_actors_1h", 0) or 0,
            "coordination": round(signal.get("coordination", 0) or 0, 4),
            "cluster_size": signal.get("cluster_size_1h", 0) or 0,
        },
        "composite": {},
        "outcome": {
            "tradeable": outcome.get("tradeable", False),
            "label": outcome.get("label", "NEUTRAL"),
            "pnl_1h": round(outcome.get("pnl_1h", 0) or 0, 4),
            "pnl_4h": round(outcome.get("pnl_4h", 0) or 0, 4),
            "pnl_24h": round(outcome.get("pnl_24h", 0) or 0, 4),
        },
        "quality": {
            "dqs": round(quality.get("dqs", 0) or 0, 4),
            "event_type": event_type,
            "event_type_confidence": round(event_type_conf, 4),
        },
    }

    row = compute_composites(row)
    return row


# ─── Build Dataset Row from signal_log (graph signals) ───

def build_row_from_signal_log(signal_entry, graph_context=None):
    """Build a dataset_entries row from a graph signal_log entry with outcome."""
    ctx = signal_entry.get("context", {})
    gc = graph_context or {}

    # These are graph-originated signals — less sentiment, more structure
    row = {
        "meta": {
            "signal_id": str(signal_entry.get("_id_str", signal_entry.get("entity", ""))),
            "token": signal_entry.get("entity", "").replace("token:", ""),
            "project": "",
            "source": "graph_signal",
            "created_at": signal_entry.get("timestamp", ""),
            "resolved_at": signal_entry.get("outcome", {}).get("resolved_at", ""),
            "written_at": datetime.now(timezone.utc).isoformat(),
        },
        "signal": {
            "type": signal_entry.get("type", "UNKNOWN"),
            "strength": signal_entry.get("strength", 0) or 0,
            "confidence": signal_entry.get("confidence", 0) or 0,
        },
        "sentiment": {
            "intent_bullish": 1 if signal_entry.get("direction") == "BULLISH" else 0,
            "intent_bearish": 1 if signal_entry.get("direction") == "BEARISH" else 0,
            "intent_hype": 0,
            "intent_warning": 0,
            "confidence": round((signal_entry.get("confidence", 0) or 0) / 100, 4),
        },
        "actor": {
            "actor_score": round(ctx.get("alpha", 0) or 0, 4),
            "actor_hit_rate": 0,
            "actor_early_ratio": 0,
            "actor_consistency": 0,
            "actor_count": ctx.get("actor_count", 0) or 0,
            "alpha_actor_present": 1 if (ctx.get("alpha", 0) or 0) > 0.5 else 0,
        },
        "graph": {
            "entity_pressure": round(ctx.get("pressure", 0) or gc.get("entity_pressure", 0) or 0, 4),
            "attention_flow": round(ctx.get("flow", 0) or gc.get("attention_flow", 0) or 0, 4),
            "alpha_source_strength": round(ctx.get("alpha", 0) or gc.get("alpha_source", 0) or 0, 4),
            "fund_pressure": round(gc.get("fund_pressure", 0) or 0, 4),
            "fund_count": gc.get("fund_count", 0) or 0,
        },
        "market": {
            "volatility": 0,
            "momentum": 0,
            "regime_trending": 0,
            "regime_range": 1,
            "regime_overheated": 0,
        },
        "timing": {
            "is_early": 1 if signal_entry.get("type") == "PRE_PUMP" else 0,
            "is_mid": 0 if signal_entry.get("type") == "PRE_PUMP" else 1,
            "is_late": 0,
            "freshness_sec": 0,
        },
        "structure": {
            "mentions": ctx.get("mentions", 0) or 0,
            "unique_actors": ctx.get("actor_count", 0) or 0,
            "coordination": 0,
            "cluster_size": 0,
        },
        "composite": {},
        "outcome": {
            "tradeable": signal_entry.get("outcome", {}).get("tradeable", False),
            "label": signal_entry.get("outcome", {}).get("label", "NEUTRAL"),
            "pnl_1h": round(signal_entry.get("outcome", {}).get("pnl_1h", 0) or 0, 4),
            "pnl_4h": round(signal_entry.get("outcome", {}).get("pnl_4h", 0) or 0, 4),
            "pnl_24h": round(signal_entry.get("outcome", {}).get("pnl_24h", 0) or 0, 4),
        },
        "quality": {
            "dqs": round(signal_entry.get("strength", 0) / 100 if signal_entry.get("strength") else 0, 4),
        },
    }

    row = compute_composites(row)
    return row


# ─── Graph Context Fetcher ───

async def get_graph_context_for_token(db, token_name):
    """Fetch graph intelligence for a token (entity_pressure, attention_flow, etc.)."""
    token_id = f"token:{token_name.upper()}"
    project_id = f"project:{token_name.lower()}"

    # Check graph_intelligence_overlay
    overlay = await db.graph_intelligence_overlay.find_one(
        {"node_id": {"$in": [token_id, project_id]}},
        {"_id": 0}
    )

    # Check signal_log for latest graph signals for this token
    latest_signal = await db.signal_log.find_one(
        {"entity": {"$in": [token_id, f"token:{token_name.upper()}", f"token:{token_name}"]}},
        {"_id": 0},
        sort=[("timestamp", -1)]
    )

    ctx = {}
    if overlay and overlay.get("data"):
        d = overlay["data"]
        ctx["entity_pressure"] = d.get("entity_pressure", 0)
        ctx["attention_flow"] = d.get("attention_flow", 0)
        ctx["alpha_source"] = d.get("alpha_source", 0) or d.get("smart_money_score", 0)

    if latest_signal and latest_signal.get("context"):
        sc = latest_signal["context"]
        ctx.setdefault("entity_pressure", sc.get("pressure", 0))
        ctx.setdefault("attention_flow", sc.get("flow", 0))
        ctx.setdefault("alpha_source", sc.get("alpha", 0))

    # Fund pressure from fund signals
    fund_signals = await db.signal_log.find(
        {"type": "FUND_PRESSURE", "context.tokens": {"$regex": token_name, "$options": "i"}},
        {"_id": 0}
    ).to_list(10)
    if fund_signals:
        ctx["fund_pressure"] = max(s.get("strength", 0) for s in fund_signals) / 100
        ctx["fund_count"] = len(fund_signals)

    return ctx


# ─── Main Writer ───

async def write_dataset_entries(db=None, limit=500):
    """
    Write dataset_entries from resolved signals.
    Sources: sentiment_training_dataset_v3 (resolved) + signal_log (with outcome).
    """
    if db is None:
        db = get_db()

    written = 0
    skipped = 0
    errors = 0

    # ─── Source 1: sentiment_training_dataset_v3 (resolved) ───
    resolved_v3 = await db.sentiment_training_dataset_v3.find(
        {"outcome.resolved": True},
        {"_id": 0}
    ).sort("meta.created_at", -1).limit(limit).to_list(limit)

    for sample in resolved_v3:
        try:
            signal_id = sample.get("meta", {}).get("source_id", "")
            if not signal_id:
                continue

            # Check if already written
            exists = await db.dataset_entries.find_one(
                {"meta.signal_id": signal_id},
                {"_id": 1}
            )
            if exists:
                skipped += 1
                continue

            # Get graph context for enrichment
            token = sample.get("market", {}).get("token", "")
            graph_ctx = await get_graph_context_for_token(db, token) if token else {}

            row = build_row_from_v3(sample, graph_ctx)
            await db.dataset_entries.insert_one(row)
            written += 1

            if row["outcome"]["label"] == "GOOD":
                log.info("ALPHA SIGNAL DETECTED: %s | type=%s str=%.1f dqs=%.2f",
                         row["meta"]["token"], row["signal"]["type"],
                         row["signal"]["strength"], row["quality"]["dqs"])
        except Exception:
            errors += 1

    # ─── Source 2: signal_log (with outcome resolved) ───
    resolved_signals = await db.signal_log.find(
        {"outcome.resolved": True},
        {"_id": 0}
    ).sort("timestamp", -1).limit(limit).to_list(limit)

    for sig in resolved_signals:
        try:
            sig_key = f"graph_{sig.get('entity', '')}_{sig.get('timestamp', '')}"

            exists = await db.dataset_entries.find_one(
                {"meta.signal_id": sig_key},
                {"_id": 1}
            )
            if exists:
                skipped += 1
                continue

            token = sig.get("entity", "").replace("token:", "")
            graph_ctx = await get_graph_context_for_token(db, token) if token else {}

            # Set _id_str for the builder
            sig["_id_str"] = sig_key

            row = build_row_from_signal_log(sig, graph_ctx)
            await db.dataset_entries.insert_one(row)
            written += 1

            if row["outcome"]["label"] == "GOOD":
                log.info("ALPHA SIGNAL DETECTED (graph): %s | type=%s str=%.1f",
                         row["meta"]["token"], row["signal"]["type"],
                         row["signal"]["strength"])
        except Exception:
            errors += 1

    return {
        "ok": True,
        "written": written,
        "skipped": skipped,
        "errors": errors,
        "sources": {
            "v3_resolved": len(resolved_v3),
            "signal_log_resolved": len(resolved_signals),
        },
    }


# ─── Stats ───

async def get_dataset_entries_stats(db=None):
    """Get dataset_entries collection stats."""
    if db is None:
        db = get_db()

    total = await db.dataset_entries.count_documents({})

    pipeline_label = [
        {"$group": {"_id": "$outcome.label", "count": {"$sum": 1}}}
    ]
    by_label = {r["_id"]: r["count"] async for r in db.dataset_entries.aggregate(pipeline_label)}

    pipeline_source = [
        {"$group": {"_id": "$meta.source", "count": {"$sum": 1}}}
    ]
    by_source = {r["_id"]: r["count"] async for r in db.dataset_entries.aggregate(pipeline_source)}

    pipeline_type = [
        {"$group": {"_id": "$signal.type", "count": {"$sum": 1}}}
    ]
    by_type = {r["_id"]: r["count"] async for r in db.dataset_entries.aggregate(pipeline_type)}

    # Average DQS
    pipeline_dqs = [
        {"$group": {"_id": None, "avg_dqs": {"$avg": "$quality.dqs"}}}
    ]
    dqs_result = await db.dataset_entries.aggregate(pipeline_dqs).to_list(1)
    avg_dqs = round(dqs_result[0]["avg_dqs"], 4) if dqs_result and dqs_result[0].get("avg_dqs") else 0

    return {
        "ok": True,
        "total": total,
        "by_label": dict(by_label),
        "by_source": dict(by_source),
        "by_type": dict(by_type),
        "avg_dqs": avg_dqs,
        "ready_for_ml": total >= 500,
        "dataset_distribution": {
            "good_pct": round(by_label.get("GOOD", 0) / total * 100, 1) if total > 0 else 0,
            "neutral_pct": round(by_label.get("NEUTRAL", 0) / total * 100, 1) if total > 0 else 0,
            "bad_pct": round(by_label.get("BAD", 0) / total * 100, 1) if total > 0 else 0,
        },
        "distribution_health": (
            "CRITICAL" if total > 50 and by_label.get("GOOD", 0) / max(total, 1) < 0.02 else
            "WARNING" if total > 50 and by_label.get("GOOD", 0) / max(total, 1) < 0.05 else
            "OK" if total > 50 else
            "COLLECTING"
        ),
    }
