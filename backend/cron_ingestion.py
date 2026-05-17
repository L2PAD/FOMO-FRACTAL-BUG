"""
Production Cron Ingestion Pipeline.
Runs every 6 hours as a FastAPI background task.

Pipeline:
  LOCK → INGEST → SENTIMENT → ENRICHMENT → DATASET V3 → DQS → DEDUP →
  HEALTH CHECK → LOG SNAPSHOT → TRIGGER EXPANSION → UNLOCK

Guards:
  1. Job lock (no duplicate runs)
  2. Idempotency (tweet_id dedup)
  3. Retry + fail-safe
  4. Health snapshot (ml_data_health_log)
  5. Hard guard (auto-stop on bad data)
  6. Expansion triggers (auto-expand on low diversity)
  7. Rate limit control
  8. Full stage logging with durations

NOT: retrain (wait for 500+ samples)
"""

import asyncio
import time
import traceback
from datetime import datetime, timezone
from twitter_ingestion import ingest_search, ingest_actor_tweets, get_ingestion_status
from sentiment_model import backfill_events
from enrichment_layer import run_enrichment_pipeline
from dataset_builder import build_dataset_v3, get_data_health, get_dataset_v3_stats
from outcome_resolver import run_outcome_resolution
from graph_bridge import run_graph_bridge
from ml_ops import get_db

# ─── Config ───

TOP_TOKENS = [
    "$BTC", "$ETH", "$SOL", "$ARB", "$AVAX", "$SUI",
    "$LINK", "$ONDO", "$INJ", "$TIA", "$PEPE",
]

TOP_ACTORS = [
    "CryptoHayes", "DefiIgnas", "TheCryptoDog", "inversebrah",
    "AltcoinGordon", "MoustacheXBT", "Pentosh1", "CryptoCobain",
    "RaoulGMI", "ZssBecker", "blaboratorio",
]

EXPANSION_TOKENS = [
    "$RENDER", "$FET", "$TAO", "$NEAR", "$DOT", "$ATOM",
    "$APT", "$SEI", "$STRK", "$EIGEN", "$PENDLE", "$AAVE",
]

EXPANSION_ACTORS = [
    "ledaboratorio", "CryptoGirlNova", "CryptoKaleo",
    "GCRClassic", "SmartContracter", "HsakaTrades",
    "CryptoTony__", "EmperorBTC", "DonAlt", "trader1sz",
]

SCHEDULER_INTERVAL_SEC = 6 * 3600  # 6 hours

# Hard guard thresholds
HARD_STOP_DQS = 0.4
HARD_STOP_DUPLICATES_PCT = 25
EXPANSION_ACTOR_GINI = 0.6
EXPANSION_TOKEN_DIVERSITY = 0.3
MIN_NEW_SAMPLES = 50

# ─── Job Lock ───

_lock_active = False


def _is_locked():
    return _lock_active


def _acquire_lock():
    global _lock_active
    if _lock_active:
        return False
    _lock_active = True
    return True


def _release_lock():
    global _lock_active
    _lock_active = False


# ─── Stage Runner with retry ───

async def _run_stage(name, func, max_retries=2):
    """Run a pipeline stage with retry and timing."""
    t0 = time.time()
    last_error = None

    for attempt in range(max_retries + 1):
        try:
            result = await func()
            duration = round(time.time() - t0, 2)
            return {"stage": name, "ok": True, "duration_sec": duration, "result": result, "attempt": attempt + 1}
        except Exception as e:
            last_error = str(e)[:200]
            if attempt < max_retries:
                await asyncio.sleep(3)

    duration = round(time.time() - t0, 2)
    return {"stage": name, "ok": False, "duration_sec": duration, "error": last_error, "attempt": max_retries + 1}


# ─── Main Pipeline ───

async def run_ingestion_cycle(tokens_limit=20, actor_limit=15):
    """
    Production ingestion cycle with all guards.
    """
    # 1. LOCK
    if not _acquire_lock():
        return {"ok": False, "error": "SKIPPED: another cycle is running"}

    cycle_start = datetime.now(timezone.utc)
    stages = []
    total_signals = 0
    stopped = False
    stop_reason = None

    try:
        db = get_db()

        # ─── Check if pipeline is enabled ───
        config = await db.pipeline_config.find_one({"key": "ingestion"}, {"_id": 0})
        if config and config.get("enabled") is False:
            return {"ok": False, "error": "Pipeline disabled by hard guard", "disabled_at": config.get("disabled_at")}

        # ─── 2. INGEST TOKENS ───
        async def _ingest_tokens():
            signals = 0
            details = []
            for keyword in TOP_TOKENS:
                try:
                    result = await ingest_search(keyword, tokens_limit)
                    s = result.get("signals_created", 0)
                    signals += s
                    if s > 0:
                        details.append(f"{keyword}:+{s}")
                except Exception as e:
                    details.append(f"{keyword}:err")
                await asyncio.sleep(2)
            return {"signals": signals, "details": details}

        stage = await _run_stage("ingest_tokens", _ingest_tokens)
        stages.append(stage)
        if stage["ok"]:
            total_signals += stage["result"].get("signals", 0)

        # ─── 3. INGEST ACTORS ───
        async def _ingest_actors():
            signals = 0
            details = []
            for actor in TOP_ACTORS:
                try:
                    result = await ingest_actor_tweets(actor, actor_limit)
                    s = result.get("signals_created", 0)
                    signals += s
                    if s > 0:
                        details.append(f"{actor}:+{s}")
                except Exception as e:
                    details.append(f"{actor}:err")
                await asyncio.sleep(3)
            return {"signals": signals, "details": details}

        stage = await _run_stage("ingest_actors", _ingest_actors)
        stages.append(stage)
        if stage["ok"]:
            total_signals += stage["result"].get("signals", 0)

        # ─── 4. SENTIMENT ───
        async def _sentiment():
            return await backfill_events(db, limit=100, skip_analyzed=True)

        stage = await _run_stage("sentiment", _sentiment)
        stages.append(stage)

        # ─── 5. ENRICHMENT ───
        async def _enrichment():
            return await run_enrichment_pipeline(limit=100, skip_enriched=True)

        stage = await _run_stage("enrichment", _enrichment)
        stages.append(stage)

        # ─── 6. DATASET V3 + DQS + DEDUP ───
        async def _dataset():
            return await build_dataset_v3(limit=200)

        stage = await _run_stage("dataset_v3", _dataset)
        stages.append(stage)
        ds_result = stage.get("result", {}) if stage["ok"] else {}

        # ─── 6.5. OUTCOME RESOLUTION (v3 samples) ───
        async def _outcome():
            return await run_outcome_resolution(limit=200)

        stage = await _run_stage("outcome_resolution", _outcome)
        stages.append(stage)

        # ─── 6.55. OUTCOME RESOLUTION (signal_log) ───
        async def _outcome_signals():
            from outcome_resolver import resolve_signal_log_outcomes
            return await resolve_signal_log_outcomes(limit=200)

        stage = await _run_stage("outcome_signal_log", _outcome_signals)
        stages.append(stage)

        # ─── 6.6. GRAPH BRIDGE (legacy) ───
        async def _graph():
            return await run_graph_bridge()

        stage = await _run_stage("graph_bridge", _graph)
        stages.append(stage)

        # ─── 6.7. UNIFIED GRAPH BUILD (cross-layer bridges) ───
        async def _graph_build():
            from graph.graph_builder import run_full_build
            return await run_full_build(db)

        stage = await _run_stage("graph_unified_build", _graph_build)
        stages.append(stage)

        # ─── 6.8. ENTITY RESOLUTION RECOVERY ───
        async def _resolution():
            from graph.graph_resolution import run_resolution_recovery
            return await run_resolution_recovery(db)

        stage = await _run_stage("entity_resolution", _resolution)
        stages.append(stage)
        resolution_result = stage.get("result", {}) if stage["ok"] else {}

        # ─── 6.9. GRAPH SIGNAL ENGINE ───
        async def _graph_signals():
            from signals.unified_signal_engine import run_graph_signals, run_fund_signals
            token_result = await run_graph_signals(db)
            fund_result = await run_fund_signals(db)
            return {
                "token_signals": token_result.get("signals_detected", 0),
                "fund_signals": fund_result.get("signals_detected", 0),
                "tokens_scanned": token_result.get("tokens_scanned", 0),
                "funds_scanned": fund_result.get("funds_scanned", 0),
            }

        stage = await _run_stage("graph_signal_engine", _graph_signals)
        stages.append(stage)
        signal_engine_result = stage.get("result", {}) if stage["ok"] else {}

        # ─── 6.10. EXPANSION ENGINE (conditional) ───
        async def _expansion():
            from graph.expansion_engine import run_expansion
            return await run_expansion(db)

        stage = await _run_stage("expansion_engine", _expansion)
        stages.append(stage)
        expansion_result = stage.get("result", {}) if stage["ok"] else {}

        # ─── 6.11. PRE-PUMP DETECTOR ───
        async def _pre_pump():
            from signals.pre_pump_detector import run_pre_pump_scan
            return await run_pre_pump_scan(db)

        stage = await _run_stage("pre_pump_detector", _pre_pump)
        stages.append(stage)
        pre_pump_result = stage.get("result", {}) if stage["ok"] else {}

        # ─── 6.12. DATASET ENTRIES WRITE (signal + context + outcome → ML) ───
        async def _dataset_write():
            from dataset_writer import write_dataset_entries
            return await write_dataset_entries(db)

        stage = await _run_stage("dataset_entries_write", _dataset_write)
        stages.append(stage)
        dataset_write_result = stage.get("result", {}) if stage["ok"] else {}

        # ─── 6.13. ML LIVE PREDICTIONS (shadow + signal log) ───
        async def _ml_live_predictions():
            from ml_ops import run_live_predictions
            return await run_live_predictions()

        stage = await _run_stage("ml_live_predictions", _ml_live_predictions)
        stages.append(stage)
        ml_live_result = stage.get("result", {}) if stage["ok"] else {}

        # ─── 7. HEALTH CHECK ───
        async def _health():
            return await get_data_health()

        stage = await _run_stage("health_check", _health)
        stages.append(stage)
        health = stage.get("result", {}) if stage["ok"] else {}

        # ─── 7.5. NOTIFICATION SCAN (OnChain + Sentiment → Events) ───
        async def _notification_scan():
            from notifications.notification_scanner import run_notification_scan
            return await run_notification_scan(db)

        stage = await _run_stage("notification_scan", _notification_scan)
        stages.append(stage)
        notif_scan_result = stage.get("result", {}) if stage["ok"] else {}

        # ─── 7.6. DECISION RECORDING + EVALUATION ───
        async def _decision_history():
            from notifications.decision_history import record_all_decisions, evaluate_pending
            recorded = await record_all_decisions()
            evaluated = await evaluate_pending()
            return {
                "recorded": len([r for r in recorded if "error" not in r]),
                "evaluated": evaluated.get("evaluated", 0),
            }

        stage = await _run_stage("decision_history", _decision_history)
        stages.append(stage)
        decision_history_result = stage.get("result", {}) if stage["ok"] else {}

        # ─── 8. HEALTH SNAPSHOT ───
        stats = await get_dataset_v3_stats()
        quality = stats.get("quality", {})
        diversity = stats.get("diversity", {})
        ds_total = stats.get("total", 0)

        duplicates_pct = 0
        if ds_result:
            total_processed = ds_result.get("processed", 0) + ds_result.get("duplicates", 0)
            if total_processed > 0:
                duplicates_pct = round(ds_result.get("duplicates", 0) / total_processed * 100, 1)

        snapshot = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "cycle_id": cycle_start.isoformat(),
            "new_signals": total_signals,
            "new_samples": ds_result.get("processed", 0) if ds_result else 0,
            "dataset_total": ds_total,
            "avg_dqs": quality.get("avg_dqs", 0),
            "high_pct": quality.get("high_pct", 0),
            "low_pct": quality.get("low_pct", 0),
            "actor_gini": diversity.get("actor_gini", 0),
            "token_gini": diversity.get("token_gini", 0),
            "unique_actors": diversity.get("unique_actors", 0),
            "unique_tokens": diversity.get("unique_tokens", 0),
            "duplicates_pct": duplicates_pct,
            "health_status": health.get("status", "unknown"),
            "health_alerts": health.get("alerts", []),
            "resolution": {
                "meaningful_unresolved_pct": resolution_result.get("summary", {}).get("meaningful_unresolved_pct"),
                "meaningful_orphans": resolution_result.get("summary", {}).get("meaningful_orphans"),
            } if resolution_result else None,
            "signal_engine": {
                "token_signals": signal_engine_result.get("token_signals", 0),
                "fund_signals": signal_engine_result.get("fund_signals", 0),
            } if signal_engine_result else None,
            "expansion": {
                "expanded": expansion_result.get("expanded", False),
                "reason": expansion_result.get("reason", ""),
                "new_actors": expansion_result.get("actors", {}).get("new_actors", 0),
                "new_tokens": expansion_result.get("tokens", {}).get("new_tokens", 0),
                "new_flows": expansion_result.get("links", {}).get("new_attention_flows", 0),
            } if expansion_result else None,
            "pre_pump": {
                "detected": pre_pump_result.get("pre_pumps_detected", 0),
                "scanned": pre_pump_result.get("tokens_scanned", 0),
            } if pre_pump_result else None,
            "dataset_write": {
                "written": dataset_write_result.get("written", 0),
                "skipped": dataset_write_result.get("skipped", 0),
                "errors": dataset_write_result.get("errors", 0),
            } if dataset_write_result else None,
            "notification_scan": {
                "events_emitted": notif_scan_result.get("events_emitted", 0),
                "events_skipped": notif_scan_result.get("events_skipped", 0),
            } if notif_scan_result else None,
            "decision_history": {
                "recorded": decision_history_result.get("recorded", 0),
                "evaluated": decision_history_result.get("evaluated", 0),
            } if decision_history_result else None,
        }

        await db.ml_data_health_log.insert_one({**snapshot})

        # ─── 9. HARD GUARDS ───
        avg_dqs = snapshot["avg_dqs"]
        if avg_dqs > 0 and avg_dqs < HARD_STOP_DQS:
            stopped = True
            stop_reason = f"HARD STOP: avg_dqs={avg_dqs} < {HARD_STOP_DQS}"
            await db.pipeline_config.update_one(
                {"key": "ingestion"},
                {"$set": {"key": "ingestion", "enabled": False, "disabled_at": datetime.now(timezone.utc).isoformat(), "reason": stop_reason}},
                upsert=True,
            )

        if duplicates_pct > HARD_STOP_DUPLICATES_PCT:
            stopped = True
            stop_reason = f"HARD STOP: duplicates={duplicates_pct}% > {HARD_STOP_DUPLICATES_PCT}%"
            await db.pipeline_config.update_one(
                {"key": "ingestion"},
                {"$set": {"key": "ingestion", "enabled": False, "disabled_at": datetime.now(timezone.utc).isoformat(), "reason": stop_reason}},
                upsert=True,
            )

        # ─── 10. EXPANSION TRIGGERS ───
        expansion_log = []
        if diversity.get("actor_gini", 0) > EXPANSION_ACTOR_GINI:
            expansion_log.append("actor_gini high → expanding actors")
            asyncio.create_task(_expand_actors(db))

        if diversity.get("unique_tokens", 99) < 5 or diversity.get("token_gini", 0) > 0.6:
            expansion_log.append("token diversity low → expanding tokens")
            asyncio.create_task(_expand_tokens(db))

        if ds_result and ds_result.get("processed", 0) < MIN_NEW_SAMPLES and total_signals < MIN_NEW_SAMPLES:
            expansion_log.append(f"new_samples={ds_result.get('processed', 0)} < {MIN_NEW_SAMPLES} → expanding both")

        # ─── Save cycle record ───
        cycle_record = {
            "cycle_at": cycle_start.isoformat(),
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "duration_sec": round((datetime.now(timezone.utc) - cycle_start).total_seconds(), 1),
            "total_new_signals": total_signals,
            "stages": [{k: v for k, v in s.items() if k != "result"} for s in stages],
            "snapshot": snapshot,
            "stopped": stopped,
            "stop_reason": stop_reason,
            "expansion": expansion_log,
        }
        await db.ingestion_cycles.insert_one({**cycle_record})

        # ─── 11. GRAPH HEALTH LOG ───
        try:
            from graph.graph_health import log_health, apply_saturation_penalty
            health_cycle_id = f"cron_{cycle_start.isoformat()}"
            await log_health(db, cycle_id=health_cycle_id)
            await apply_saturation_penalty(db)
        except Exception as he:
            logger.warning(f"[Cron] Health log failed: {he}")

        return {
            "ok": not stopped,
            "cycle_at": cycle_start.isoformat(),
            "duration_sec": cycle_record["duration_sec"],
            "total_new_signals": total_signals,
            "new_samples": ds_result.get("processed", 0) if ds_result else 0,
            "stages": [{k: v for k, v in s.items() if k != "result"} for s in stages],
            "health": snapshot,
            "stopped": stopped,
            "stop_reason": stop_reason,
            "expansion": expansion_log,
        }

    except Exception as e:
        # Save failed cycle
        db = get_db()
        await db.ingestion_cycles.insert_one({
            "cycle_at": cycle_start.isoformat(),
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "error": str(e)[:500],
            "traceback": traceback.format_exc()[:1000],
        })
        return {"ok": False, "error": str(e)[:200], "stages": [{k: v for k, v in s.items() if k != "result"} for s in stages]}

    finally:
        _release_lock()


# ─── Expansion Tasks ───

async def _expand_actors(db):
    """Discover new actors by searching expansion token list."""
    for keyword in EXPANSION_TOKENS[:5]:
        try:
            await ingest_search(keyword, 15)
        except Exception:
            pass
        await asyncio.sleep(3)

    for actor in EXPANSION_ACTORS[:5]:
        try:
            await ingest_actor_tweets(actor, 10)
        except Exception:
            pass
        await asyncio.sleep(3)


async def _expand_tokens(db):
    """Search for underrepresented tokens."""
    for keyword in EXPANSION_TOKENS:
        try:
            await ingest_search(keyword, 10)
        except Exception:
            pass
        await asyncio.sleep(3)


# ─── Scheduler ───

_scheduler_task = None
_scheduler_running = False


async def _scheduler_loop():
    """Background loop that runs ingestion every 6 hours."""
    global _scheduler_running
    _scheduler_running = True

    while _scheduler_running:
        try:
            result = await run_ingestion_cycle()
            if result.get("stopped"):
                _scheduler_running = False
                break
        except Exception:
            pass

        await asyncio.sleep(SCHEDULER_INTERVAL_SEC)


def start_scheduler():
    """Start the background scheduler."""
    global _scheduler_task, _scheduler_running
    if _scheduler_task and not _scheduler_task.done():
        return {"ok": False, "error": "scheduler already running"}

    _scheduler_running = True
    _scheduler_task = asyncio.create_task(_scheduler_loop())
    return {"ok": True, "message": "scheduler started", "interval_hours": SCHEDULER_INTERVAL_SEC / 3600}


def stop_scheduler():
    """Stop the background scheduler."""
    global _scheduler_running
    _scheduler_running = False
    return {"ok": True, "message": "scheduler stopping (will finish current cycle)"}


def get_scheduler_status():
    """Get scheduler status."""
    return {
        "running": _scheduler_running,
        "locked": _is_locked(),
        "interval_hours": SCHEDULER_INTERVAL_SEC / 3600,
    }


# ─── Status ───

async def get_cron_status():
    """Get full cron/scheduler status."""
    db = get_db()

    last_cycle = await db.ingestion_cycles.find_one(
        {}, {"_id": 0}, sort=[("cycle_at", -1)]
    )
    total_cycles = await db.ingestion_cycles.count_documents({})

    # Last 5 health snapshots
    snapshots = await db.ml_data_health_log.find(
        {}, {"_id": 0}
    ).sort("timestamp", -1).limit(5).to_list(5)

    status = await get_ingestion_status()
    health = await get_data_health()

    # Check if pipeline is disabled
    config = await db.pipeline_config.find_one({"key": "ingestion"}, {"_id": 0})
    pipeline_enabled = config.get("enabled", True) if config else True

    return {
        "ok": True,
        "scheduler": get_scheduler_status(),
        "pipeline_enabled": pipeline_enabled,
        "pipeline_disable_reason": config.get("reason") if config and not pipeline_enabled else None,
        "total_cycles": total_cycles,
        "last_cycle": last_cycle,
        "health_trend": snapshots,
        "data_status": status,
        "data_health": health,
    }


async def enable_pipeline():
    """Re-enable pipeline after hard stop."""
    db = get_db()
    await db.pipeline_config.update_one(
        {"key": "ingestion"},
        {"$set": {"enabled": True, "reason": None, "re_enabled_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )
    return {"ok": True, "message": "pipeline re-enabled"}
