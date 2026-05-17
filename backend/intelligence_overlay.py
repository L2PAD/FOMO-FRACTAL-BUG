"""
Intelligence Overlay — Phase A Step 5
=======================================
Connects risk, signal, narrative, and alert layers to the graph.

Overlay Types:
  - risk: wash_patterns, mixer_exposure, sanction_exposure, anomalous_flows
  - signal: smart_money_signals, exchange_signals, token_signals, cluster_signals
  - narrative: market_phase, dominant_narrative, capital_migration, sector_rotation
  - alert: important_alert, liquidity_target, OTC_transfer, cluster_activity
"""

import time
from datetime import datetime, timezone

from graph_normalizer import normalize_node_id
import graph_storage as storage


async def build_risk_overlay(db):
    """Build risk intelligence overlay from existing wash/exposure data."""
    stats = {"entries": 0}
    now_ts = int(datetime.now(timezone.utc).timestamp())

    # Wash alerts → risk overlay
    cursor = db["graph_wash_alerts"].find({}, {"_id": 0}).limit(200)
    async for alert in cursor:
        nodes = alert.get("nodes", [])
        for node_id in nodes:
            await storage.upsert_overlay({
                "overlay_type": "risk",
                "sub_type": alert.get("pattern_type", "wash_pattern"),
                "node_id": node_id,
                "data": {
                    "alert_id": alert.get("alert_id", ""),
                    "confidence": alert.get("confidence", 0),
                    "amount_usd": alert.get("amount_usd", 0),
                    "pattern_type": alert.get("pattern_type", ""),
                },
                "severity": "high" if alert.get("confidence", 0) > 0.7 else "medium",
                "created_at": now_ts,
            })
            stats["entries"] += 1

    # High-risk nodes → risk overlay
    cursor = db["graph_nodes"].find(
        {"risk_score": {"$gt": 0.5}},
        {"_id": 0, "id": 1, "risk_score": 1, "risk_level": 1, "exposure_score": 1, "exposure_flags": 1}
    ).limit(200)
    async for node in cursor:
        await storage.upsert_overlay({
            "overlay_type": "risk",
            "sub_type": "high_risk_node",
            "node_id": node["id"],
            "data": {
                "risk_score": node.get("risk_score", 0),
                "risk_level": node.get("risk_level", ""),
                "exposure_score": node.get("exposure_score", 0),
                "exposure_flags": node.get("exposure_flags", []),
            },
            "severity": node.get("risk_level", "medium"),
            "created_at": now_ts,
        })
        stats["entries"] += 1

    return stats


async def build_signal_overlay(db):
    """Build signal intelligence overlay from alpha signals."""
    stats = {"entries": 0}
    now_ts = int(datetime.now(timezone.utc).timestamp())

    # Alpha signals → signal overlay
    cursor = db["graph_alpha_signals"].find({}, {"_id": 0}).limit(200)
    async for sig in cursor:
        node_ids = sig.get("node_ids", [])
        if not node_ids and sig.get("node_id"):
            node_ids = [sig["node_id"]]

        signal_type = sig.get("signal_type", "unknown")
        sub_type = "smart_money_signal" if "smart" in signal_type else \
                   "exchange_signal" if "exchange" in signal_type or "cex" in signal_type else \
                   "token_signal" if "token" in signal_type else \
                   "cluster_signal" if "cluster" in signal_type else signal_type

        for node_id in node_ids:
            await storage.upsert_overlay({
                "overlay_type": "signal",
                "sub_type": sub_type,
                "node_id": node_id,
                "data": {
                    "signal_type": signal_type,
                    "strength": sig.get("strength", 0),
                    "direction": sig.get("direction", ""),
                    "message": sig.get("message", ""),
                },
                "severity": "info",
                "created_at": now_ts,
            })
            stats["entries"] += 1

    # Smart money wallets → signal overlay
    cursor = db["graph_nodes"].find(
        {"smart_money_score": {"$gt": 0.3}, "type": "wallet"},
        {"_id": 0, "id": 1, "smart_money_score": 1, "label": 1}
    ).sort("smart_money_score", -1).limit(50)
    async for node in cursor:
        await storage.upsert_overlay({
            "overlay_type": "signal",
            "sub_type": "smart_money_signal",
            "node_id": node["id"],
            "data": {
                "smart_money_score": node.get("smart_money_score", 0),
                "label": node.get("label", ""),
            },
            "severity": "info",
            "created_at": now_ts,
        })
        stats["entries"] += 1

    return stats


async def build_narrative_overlay(db):
    """Build narrative intelligence overlay."""
    stats = {"entries": 0}
    now_ts = int(datetime.now(timezone.utc).timestamp())

    # Narratives from narrative collection
    cursor = db["narratives"].find({}, {"_id": 0}).limit(50)
    async for narr in cursor:
        narr_id = narr.get("narrative_id", narr.get("slug", "unknown"))
        await storage.upsert_overlay({
            "overlay_type": "narrative",
            "sub_type": narr.get("type", "market_phase"),
            "node_id": f"narrative:{narr_id}",
            "data": {
                "narrative_id": narr_id,
                "title": narr.get("title", narr.get("name", "")),
                "description": narr.get("description", ""),
                "confidence": narr.get("confidence", 0),
                "tokens": narr.get("tokens", []),
                "entities": narr.get("entities", []),
            },
            "severity": "info",
            "created_at": now_ts,
        })
        stats["entries"] += 1

        # Link narrative to related tokens
        for token in narr.get("tokens", [])[:10]:
            token_nid = normalize_node_id("token", token.lower(), "ethereum")
            narrative_nid = normalize_node_id("narrative", narr_id, "ethereum")

            # Create narrative node
            await storage.upsert_node({
                "id": narrative_nid,
                "type": "narrative",
                "label": narr.get("title", narr.get("name", narr_id)),
                "address": narr_id,
                "chain": "ethereum",
                "metadata": {
                    "description": narr.get("description", ""),
                    "confidence": narr.get("confidence", 0),
                },
                "last_seen": now_ts,
            })

            # narrative → token signal_link
            await storage.upsert_relation({
                "source_id": narrative_nid,
                "target_id": token_nid,
                "relation_type": "signal_link",
                "chain": "ethereum",
                "total_amount_usd": 0,
                "tx_count": 1,
                "confidence": narr.get("confidence", 0.5),
                "signal_strength": narr.get("confidence", 0.5),
                "first_seen": now_ts,
                "last_seen": now_ts,
            })
            stats["entries"] += 1

    return stats


async def build_alert_overlay(db):
    """Build alert intelligence overlay from engine alerts and system events."""
    stats = {"entries": 0}
    now_ts = int(datetime.now(timezone.utc).timestamp())

    # Engine alerts → alert overlay
    cursor = db["engine_alerts"].find(
        {},
        {"_id": 0, "alert_id": 1, "type": 1, "severity": 1, "message": 1,
         "node_id": 1, "entity": 1, "amount_usd": 1, "timestamp": 1}
    ).sort("timestamp", -1).limit(100)
    async for alert in cursor:
        node_id = alert.get("node_id", "")
        entity = alert.get("entity", "")

        if not node_id and entity:
            node_id = normalize_node_id("entity", entity.lower(), "ethereum")

        if not node_id:
            continue

        alert_type = alert.get("type", "important_alert")
        sub_type_map = {
            "whale": "liquidity_target",
            "large_transfer": "OTC_transfer",
            "cluster": "cluster_activity",
        }
        sub_type = sub_type_map.get(alert_type, "important_alert")

        await storage.upsert_overlay({
            "overlay_type": "alert",
            "sub_type": sub_type,
            "node_id": node_id,
            "data": {
                "alert_id": alert.get("alert_id", ""),
                "message": alert.get("message", ""),
                "amount_usd": alert.get("amount_usd", 0),
                "severity": alert.get("severity", "medium"),
            },
            "severity": alert.get("severity", "medium"),
            "created_at": alert.get("timestamp", now_ts),
        })
        stats["entries"] += 1

    # Create alert nodes for highest-severity alerts
    cursor = db["graph_intelligence_overlay"].find(
        {"overlay_type": "alert", "severity": "high"},
        {"_id": 0, "node_id": 1, "sub_type": 1, "data": 1}
    ).limit(50)
    async for ov in cursor:
        alert_nid = normalize_node_id("alert", ov.get("overlay_id", "unknown"), "ethereum")
        target_nid = ov.get("node_id", "")

        if target_nid:
            await storage.upsert_node({
                "id": alert_nid,
                "type": "alert",
                "label": f"Alert: {ov.get('sub_type', 'unknown')}",
                "address": ov.get("overlay_id", ""),
                "chain": "ethereum",
                "metadata": ov.get("data", {}),
                "last_seen": int(datetime.now(timezone.utc).timestamp()),
            })

            await storage.upsert_relation({
                "source_id": alert_nid,
                "target_id": target_nid,
                "relation_type": "alert_link",
                "chain": "ethereum",
                "total_amount_usd": ov.get("data", {}).get("amount_usd", 0),
                "tx_count": 1,
                "signal_strength": 1.0 if ov.get("severity") == "high" else 0.5,
                "first_seen": int(datetime.now(timezone.utc).timestamp()),
                "last_seen": int(datetime.now(timezone.utc).timestamp()),
            })
            stats["entries"] += 1

    return stats


async def run_intelligence_overlay(db):
    """Run all intelligence overlay builds."""
    storage.init_storage(db)

    t0 = time.time()
    results = {}

    print("[IntelOverlay] Building risk overlay...")
    results["risk"] = await build_risk_overlay(db)

    print("[IntelOverlay] Building signal overlay...")
    results["signal"] = await build_signal_overlay(db)

    print("[IntelOverlay] Building narrative overlay...")
    results["narrative"] = await build_narrative_overlay(db)

    print("[IntelOverlay] Building alert overlay...")
    results["alert"] = await build_alert_overlay(db)

    elapsed = round(time.time() - t0, 1)
    total = sum(r.get("entries", 0) for r in results.values())

    print(f"[IntelOverlay] Done in {elapsed}s: {total} overlay entries")
    return {
        "status": "completed",
        "elapsed_seconds": elapsed,
        "total_entries": total,
        "details": results,
    }
