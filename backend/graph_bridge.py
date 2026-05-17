"""
Graph Bridge — converts signal data into graph edges.

ONE GRAPH, THREE LAYERS:
  SOCIAL     — twitter relationships (follows, retweets, co-mentions)
  KNOWLEDGE  — investment data (fund→project, person→fund)
  SIGNAL     — ML pipeline output (MENTIONED_TOKEN, signal_correlated, alpha_source)

This module builds SIGNAL layer edges from:
  actor_signal_events    → MENTIONED_TOKEN edges
  actor_intelligence     → node metadata enrichment
  co-mention analysis    → signal_correlated edges
  dataset_v3 outcomes    → alpha_source edges

All edges go into graph_edges with layer="SIGNAL".
Idempotent: safe to run multiple times.
"""

import logging
import math
import os
import sys
from datetime import datetime, timezone, timedelta
from collections import defaultdict, Counter
from ml_ops import get_db

logger = logging.getLogger(__name__)

LAYER = "SIGNAL"


def _actor_node_id(handle):
    return f"twitter:{handle.lower()}"


def _token_node_id(symbol):
    return f"token:{symbol.upper()}"


async def _ensure_node(db, node_id, node_type, label, metadata=None):
    """Upsert a graph node. Merges metadata, never overwrites."""
    now = datetime.now(timezone.utc)
    update = {
        "$set": {
            "id": node_id,
            "type": node_type,
            "label": label,
            "updated_at": now,
        },
        "$setOnInsert": {"created_at": now},
    }
    if metadata:
        for k, v in metadata.items():
            update["$set"][f"metadata.{k}"] = v
    await db.graph_nodes.update_one({"id": node_id}, update, upsert=True)


async def _upsert_edge(db, from_id, to_id, relation_type, weight, source_ref, metadata=None):
    """Upsert a SIGNAL layer edge. Dedup by (from, to, relation_type, layer)."""
    now = datetime.now(timezone.utc)
    filt = {
        "from_node_id": from_id,
        "to_node_id": to_id,
        "relation_type": relation_type,
        "layer": LAYER,
    }
    update = {
        "$set": {
            "weight": weight,
            "source_type": "signal",
            "source_ref": source_ref,
            "layer": LAYER,
            "updated_at": now,
            **({"metadata": metadata} if metadata else {}),
        },
        "$setOnInsert": {
            "from_node_id": from_id,
            "to_node_id": to_id,
            "relation_type": relation_type,
            "created_at": now,
        },
    }
    await db.graph_edges.update_one(filt, update, upsert=True)


# ─── P0: MENTIONED_TOKEN edges ───

async def build_mention_edges(db):
    """
    actor_signal_events → graph_edges (MENTIONED_TOKEN).
    Weight = log(1 + count) * 0.6 + recency * 0.4
    """
    now = datetime.now(timezone.utc)

    pipeline = [
        {"$group": {
            "_id": {"actor": "$actor_handle", "token": "$token"},
            "count": {"$sum": 1},
            "avg_likes": {"$avg": "$metrics.likes"},
            "avg_views": {"$avg": "$metrics.views"},
            "last_seen": {"$max": "$created_at"},
            "signal_types": {"$push": "$signal_type"},
        }},
    ]

    pairs = []
    async for doc in db.actor_signal_events.aggregate(pipeline):
        pairs.append(doc)

    if not pairs:
        return {"edges_created": 0}

    # Normalize log(1+count) to [0,1]
    max_log = max(math.log(1 + p["count"]) for p in pairs)
    edges_created = 0

    for p in pairs:
        actor = p["_id"]["actor"]
        token = p["_id"]["token"]
        count = p["count"]
        last_seen = p["last_seen"]

        # Recency: exp(-hours/24)
        recency = 0.0
        if last_seen:
            try:
                if isinstance(last_seen, str):
                    ls_dt = datetime.fromisoformat(last_seen.replace("Z", "+00:00"))
                elif isinstance(last_seen, datetime):
                    ls_dt = last_seen if last_seen.tzinfo else last_seen.replace(tzinfo=timezone.utc)
                else:
                    ls_dt = now
                hours = max((now - ls_dt).total_seconds() / 3600, 0)
                recency = math.exp(-hours / 24)
            except (ValueError, TypeError):
                recency = 0.0

        # Weight: log component + recency
        log_norm = math.log(1 + count) / max(max_log, 1) if max_log > 0 else 0
        weight = round(log_norm * 0.6 + recency * 0.4, 4)

        from_id = _actor_node_id(actor)
        to_id = _token_node_id(token)

        await _ensure_node(db, from_id, "twitter_account", f"@{actor}",
                           {"source": "signal_pipeline"})
        await _ensure_node(db, to_id, "token", token,
                           {"source": "signal_pipeline"})

        type_dist = dict(Counter(p["signal_types"]))

        await _upsert_edge(
            db, from_id, to_id, "MENTIONED_TOKEN", weight,
            source_ref=f"mention:{actor}:{token}",
            metadata={
                "count": count,
                "avg_likes": round(p["avg_likes"] or 0, 1),
                "avg_views": round(p["avg_views"] or 0, 1),
                "last_seen": last_seen,
                "signal_types": type_dist,
                "recency": round(recency, 4),
            },
        )
        edges_created += 1

    return {"edges_created": edges_created, "pairs_processed": len(pairs)}


# ─── P0: Enrich actor nodes with intelligence ───

async def enrich_actor_nodes(db):
    """
    actor_intelligence → graph_nodes metadata.
    Adds: actor_score, hit_rate, early_ratio, role, total_signals.
    """
    actors = await db.actor_intelligence.find({}, {"_id": 0}).to_list(1000)
    enriched = 0

    for a in actors:
        handle = a.get("actor_handle")
        if not handle:
            continue

        node_id = _actor_node_id(handle)

        # Compute composite actor_score (same formula as enrichment_layer)
        hit_rate = a.get("hit_rate_24h", 0)
        early_ratio = a.get("early_ratio", 0)
        avg_ret = a.get("avg_rel_ret_24h", 0)
        signals = a.get("total_signals", 0)
        role = a.get("role", "UNKNOWN")

        score = (
            hit_rate * 0.35
            + early_ratio * 0.25
            + min(abs(avg_ret) / 5, 1.0) * 0.20
            + min(signals / 20, 1.0) * 0.10
            + (1.0 if role == "DRIVER" else 0.5 if role == "AMPLIFIER" else 0.2) * 0.10
        )

        await _ensure_node(db, node_id, "twitter_account", f"@{handle}", {
            "actor_score": round(score, 4),
            "hit_rate_24h": round(hit_rate, 4),
            "early_ratio": round(early_ratio, 4),
            "avg_rel_ret_24h": round(avg_ret, 6),
            "total_signals": signals,
            "role": role,
            "avg_likes": round(a.get("avg_likes", 0), 0),
        })
        enriched += 1

    return {"actors_enriched": enriched}


# ─── P1: signal_correlated edges ───

async def build_correlation_edges(db, window_minutes=60, min_shared=2):
    """
    Find actors who mention the same token within `window_minutes`.
    Creates signal_correlated edges between them.
    """
    events = await db.actor_signal_events.find(
        {}, {"_id": 0, "actor_handle": 1, "token": 1, "timestamp": 1}
    ).sort("timestamp", 1).to_list(10000)

    if not events:
        return {"edges_created": 0}

    # Build (token, time_bucket) → [actors] map
    window_ms = window_minutes * 60 * 1000
    bucket_actors = defaultdict(set)

    for e in events:
        ts = e.get("timestamp")
        if not ts:
            continue
        try:
            if isinstance(ts, str):
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                ts_ms = int(dt.timestamp() * 1000)
            elif isinstance(ts, (int, float)):
                ts_ms = int(ts)
            else:
                continue
        except (ValueError, TypeError):
            continue

        bucket = ts_ms // window_ms
        token = e["token"]
        actor = e["actor_handle"]
        bucket_actors[(token, bucket)].add(actor)

    # Count co-occurrences
    pair_tokens = defaultdict(set)
    pair_count = defaultdict(int)

    for (token, _bucket), actors in bucket_actors.items():
        actors = sorted(actors)
        for i in range(len(actors)):
            for j in range(i + 1, len(actors)):
                pair = (actors[i], actors[j])
                pair_tokens[pair].add(token)
                pair_count[pair] += 1

    edges_created = 0

    for (a1, a2), tokens in pair_tokens.items():
        if len(tokens) < min_shared:
            continue

        count = pair_count[(a1, a2)]
        # Correlation strength: shared_tokens / total_unique_tokens of both actors
        a1_tokens = set()
        a2_tokens = set()
        for (tok, _b), acts in bucket_actors.items():
            if a1 in acts:
                a1_tokens.add(tok)
            if a2 in acts:
                a2_tokens.add(tok)
        union = a1_tokens | a2_tokens
        strength = len(tokens) / len(union) if union else 0

        weight = round(min(count / 20, 1.0) * 0.6 + strength * 0.4, 4)

        await _upsert_edge(
            db, _actor_node_id(a1), _actor_node_id(a2),
            "signal_correlated", weight,
            source_ref=f"corr:{a1}:{a2}",
            metadata={
                "shared_tokens": sorted(tokens),
                "co_mention_count": count,
                "shared_token_count": len(tokens),
                "correlation_strength": round(strength, 4),
            },
        )
        edges_created += 1

    return {"edges_created": edges_created, "pairs_checked": len(pair_count)}


# ─── P2: alpha_source edges + alpha_score on MENTIONED_TOKEN ───

async def build_alpha_edges(db):
    """
    1. dataset_v3 EARLY + GOOD → alpha_source edge (actor → token)
    2. dataset_v3 resolved outcomes → alpha_score on MENTIONED_TOKEN edges (EMA)
    """
    # Gather all resolved outcomes for alpha_score update
    resolved = db.sentiment_training_dataset_v3.find(
        {"outcome.resolved": True},
        {"_id": 0, "meta": 1, "market": 1, "outcome": 1, "quality": 1, "signal": 1},
    )

    alpha_map = defaultdict(list)      # (actor,token) → EARLY+GOOD entries
    outcome_map = defaultdict(list)    # (actor,token) → all resolved outcomes

    async for doc in resolved:
        actor = doc.get("meta", {}).get("actor_handle", "")
        token = doc.get("market", {}).get("token", "")
        if not actor or not token:
            continue

        pnl_1h = doc.get("outcome", {}).get("pnl_1h", 0) or 0
        tradeable = doc.get("outcome", {}).get("tradeable", False)
        position = doc.get("signal", {}).get("position", "")
        label = doc.get("outcome", {}).get("label", "")

        outcome_map[(actor, token)].append(pnl_1h)

        if tradeable and label == "GOOD" and position == "EARLY":
            alpha_map[(actor, token)].append({
                "pnl_24h": doc.get("outcome", {}).get("pnl_24h", 0),
                "dqs": doc.get("quality", {}).get("dqs", 0),
            })

    # Update alpha_score on MENTIONED_TOKEN edges (EMA: 0.8 old + 0.2 new)
    alpha_updated = 0
    for (actor, token), pnls in outcome_map.items():
        if not pnls:
            continue

        from_id = _actor_node_id(actor)
        to_id = _token_node_id(token)

        # Get existing alpha_score
        existing = await db.graph_edges.find_one(
            {"from_node_id": from_id, "to_node_id": to_id,
             "relation_type": "MENTIONED_TOKEN", "layer": LAYER},
            {"_id": 0, "metadata.alpha_score": 1}
        )
        old_alpha = (existing or {}).get("metadata", {}).get("alpha_score", 0) or 0

        # EMA update: for each resolved outcome
        alpha = old_alpha
        for pnl in pnls:
            alpha = alpha * 0.8 + pnl * 0.2

        await db.graph_edges.update_one(
            {"from_node_id": from_id, "to_node_id": to_id,
             "relation_type": "MENTIONED_TOKEN", "layer": LAYER},
            {"$set": {"metadata.alpha_score": round(alpha, 6)}}
        )
        alpha_updated += 1

    # Create alpha_source edges for EARLY + GOOD
    edges_created = 0
    for (actor, token), entries in alpha_map.items():
        avg_pnl = sum(e["pnl_24h"] for e in entries) / len(entries) if entries else 0
        avg_dqs = sum(e["dqs"] for e in entries) / len(entries) if entries else 0
        weight = round(min(len(entries) / 5, 1.0), 4)

        await _upsert_edge(
            db, _actor_node_id(actor), _token_node_id(token),
            "alpha_source", weight,
            source_ref=f"alpha:{actor}:{token}",
            metadata={
                "alpha_count": len(entries),
                "avg_pnl_24h": round(avg_pnl, 4),
                "avg_dqs": round(avg_dqs, 4),
            },
        )
        edges_created += 1

    return {
        "edges_created": edges_created,
        "alpha_pairs": len(alpha_map),
        "alpha_scores_updated": alpha_updated,
    }


# ─── NODE SCORE ───

async def compute_node_scores(db):
    """
    node_score = alpha * 0.5 + influence * 0.3 + activity * 0.2
    Stored in graph_nodes.metadata.node_score
    """
    now = datetime.now(timezone.utc)
    cutoff_24h = now - timedelta(hours=24)

    # Get all twitter_account nodes
    actors = await db.graph_nodes.find(
        {"type": "twitter_account"},
        {"_id": 0, "id": 1}
    ).to_list(5000)

    if not actors:
        return {"scored": 0}

    scored = 0

    for actor in actors:
        node_id = actor["id"]

        # Get all MENTIONED_TOKEN edges from this actor
        edges = await db.graph_edges.find(
            {"from_node_id": node_id, "relation_type": "MENTIONED_TOKEN", "layer": LAYER},
            {"_id": 0, "weight": 1, "metadata.alpha_score": 1, "metadata.last_seen": 1}
        ).to_list(500)

        if not edges:
            continue

        # Alpha: avg of alpha_scores
        alpha_vals = [
            e.get("metadata", {}).get("alpha_score", 0)
            for e in edges
            if e.get("metadata", {}).get("alpha_score") is not None
        ]
        alpha = sum(alpha_vals) / len(alpha_vals) if alpha_vals else 0

        # Influence: log(1 + total_weight)
        total_weight = sum(e.get("weight", 0) for e in edges)
        influence = math.log(1 + total_weight)
        # Normalize to ~[0,1] (log(1+30) ≈ 3.4)
        influence = min(influence / 3.5, 1.0)

        # Activity: count of edges with last_seen in last 24h
        recent = 0
        for e in edges:
            ls = e.get("metadata", {}).get("last_seen")
            if not ls:
                continue
            try:
                if isinstance(ls, str):
                    ls_dt = datetime.fromisoformat(ls.replace("Z", "+00:00"))
                elif isinstance(ls, datetime):
                    ls_dt = ls if ls.tzinfo else ls.replace(tzinfo=timezone.utc)
                else:
                    continue
                if ls_dt > cutoff_24h:
                    recent += 1
            except (ValueError, TypeError):
                continue

        activity = math.log(1 + recent)
        activity = min(activity / 3.0, 1.0)  # normalize

        # Final score
        node_score = round(alpha * 0.5 + influence * 0.3 + activity * 0.2, 4)

        await db.graph_nodes.update_one(
            {"id": node_id},
            {"$set": {"metadata.node_score": node_score}}
        )
        scored += 1

    return {"scored": scored}


# ─── KNOWLEDGE LAYER: sync entity_graph_relations → graph_edges ───

async def sync_knowledge_edges(db):
    """
    Sync entity_graph_relations → graph_edges (layer=KNOWLEDGE).
    Maps: source_id/target_id → from_node_id/to_node_id.
    """
    cursor = db.entity_graph_relations.find({}, {"_id": 0})
    relations = await cursor.to_list(5000)

    if not relations:
        return {"synced": 0}

    synced = 0
    for r in relations:
        from_id = r.get("source_id", "")
        to_id = r.get("target_id", "")
        rel_type = r.get("relation_type", "unknown")
        weight = r.get("weight", 1)

        if not from_id or not to_id:
            continue

        now = datetime.now(timezone.utc)
        filt = {
            "from_node_id": from_id,
            "to_node_id": to_id,
            "relation_type": rel_type,
            "layer": "KNOWLEDGE",
        }
        update = {
            "$set": {
                "weight": weight,
                "source_type": r.get("source", "discovery"),
                "source_ref": f"knowledge:{from_id}:{to_id}",
                "layer": "KNOWLEDGE",
                "metadata": r.get("metadata", {}),
                "updated_at": now,
            },
            "$setOnInsert": {
                "from_node_id": from_id,
                "to_node_id": to_id,
                "relation_type": rel_type,
                "created_at": now,
            },
        }
        await db.graph_edges.update_one(filt, update, upsert=True)
        synced += 1

    return {"synced": synced}


# ─── PARSER REGISTRY ───

PARSER_TIERS = {
    # TIER 0 — CORE GRAPH
    "CryptoRank":    {"tier": 0, "type": "GRAPH", "module": "parser_cryptorank",    "func": "sync_cryptorank_data",    "role": "funding, investors, persons"},
    "Dropstab":      {"tier": 0, "type": "GRAPH", "module": "parser_activities",    "func": "sync_activities_data",    "role": "activities, campaigns, narratives"},
    # TIER 1 — CORE EXTENSION
    "RootData":      {"tier": 1, "type": "GRAPH", "module": "parser_rootdata",      "func": "sync_rootdata_data",      "role": "funds, founders, team"},
    "GitHub":        {"tier": 1, "type": "GRAPH", "module": "parser_github",        "func": "sync_github_data",        "role": "developers, contributors"},
    # TIER 2 — STRUCTURAL ADDONS
    "DefiLlama":     {"tier": 2, "type": "GRAPH", "module": "parser_defillama",     "func": "sync_defillama_data",     "role": "protocols, chains, TVL"},
    "ICODrops":      {"tier": 2, "type": "GRAPH", "module": "parser_icodrops",      "func": "sync_icodrops_data",      "role": "ICO, token sales"},
    "DropsEarn":     {"tier": 2, "type": "GRAPH", "module": "parser_dropsearn",     "func": "sync_dropsearn_data",     "role": "airdrops, campaigns"},
    "AirdropAlert":  {"tier": 2, "type": "GRAPH", "module": "parser_airdropalert",  "func": "sync_airdropalert_data",  "role": "airdrops"},
    "TokenUnlocks":  {"tier": 2, "type": "GRAPH", "module": "parser_tokenunlocks",  "func": "sync_tokenunlocks_data",  "role": "unlock schedules, vesting"},
}


async def _update_parser_registry(db, name, ok, result_str, duration, error=None):
    """Update parser_registry collection with run status."""
    now = datetime.now(timezone.utc).isoformat()
    info = PARSER_TIERS.get(name, {})
    await db.parser_registry.update_one(
        {"name": name},
        {"$set": {
            "name": name,
            "tier": info.get("tier", 99),
            "type": info.get("type", "UNKNOWN"),
            "role": info.get("role", ""),
            "status": "ACTIVE" if ok else "ERROR",
            "last_run": now,
            "last_result": result_str[:300] if result_str else "",
            "last_error": error[:300] if error else None,
            "last_duration_sec": round(duration, 1),
            "enabled": True,
            "updated_at": now,
        },
        "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )


async def get_parser_registry():
    """Get all parsers from registry."""
    db = get_db()
    parsers = await db.parser_registry.find({}, {"_id": 0}).sort("tier", 1).to_list(50)
    # Serialize datetimes
    for p in parsers:
        for k, v in list(p.items()):
            if isinstance(v, datetime):
                p[k] = v.isoformat()
    return {"ok": True, "parsers": parsers}


# ─── GRAPH PIPELINE ───

async def run_graph_pipeline(tiers=None):
    """
    Run GRAPH parsers by tier.
    tiers: list of tiers to run (default: [0,1,2] = all)
    Graph = only entity relations. NOT prices, NOT news.
    """
    import time
    import subprocess
    import json as _json
    import sys as _sys

    if tiers is None:
        tiers = [0, 1, 2]

    db = get_db()
    results = []
    start = time.time()

    # Build parser list for requested tiers
    parsers_to_run = []
    for name, info in PARSER_TIERS.items():
        if info["tier"] in tiers and info["type"] == "GRAPH":
            parsers_to_run.append((name, info["module"], info["func"]))

    if not parsers_to_run:
        return {"ok": True, "parsers": [], "message": "no parsers for requested tiers"}

    # Build subprocess script
    parser_entries = ",\n        ".join(
        f'("{name}", "modules.parsers.{mod}", "{func}")'
        for name, mod, func in parsers_to_run
    )

    parser_script = f'''
import asyncio, os, sys, json, time
sys.path.insert(0, '/app/backend')
os.chdir('/app/backend')
from motor.motor_asyncio import AsyncIOMotorClient
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME   = os.environ.get('DB_NAME', 'fomo_mobile')
client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]
results = []
async def run_all():
    import importlib
    parsers = [
        {parser_entries}
    ]
    for label, mod_path, func_name in parsers:
        t0 = time.time()
        try:
            mod = importlib.import_module(mod_path)
            fn = getattr(mod, func_name)
            r = await fn(db)
            results.append({{"name": label, "ok": True, "result": str(r)[:200], "duration": round(time.time()-t0,1)}})
        except Exception as e:
            results.append({{"name": label, "ok": False, "error": str(e)[:200], "duration": round(time.time()-t0,1)}})
    client.close()
asyncio.run(run_all())
print(json.dumps(results))
'''

    try:
        proc = subprocess.run(
            [_sys.executable, "-c", parser_script],
            capture_output=True, text=True, timeout=300,
            env={**os.environ}
        )
        if proc.returncode == 0 and proc.stdout.strip():
            parser_results = _json.loads(proc.stdout.strip().split('\n')[-1])
            results.extend(parser_results)
        else:
            err = (proc.stderr or "unknown error")[-300:]
            results.append({"name": "SubprocessError", "ok": False, "error": err})
    except subprocess.TimeoutExpired:
        results.append({"name": "SubprocessError", "ok": False, "error": "timeout 300s"})
    except Exception as e:
        results.append({"name": "SubprocessError", "ok": False, "error": str(e)[:200]})

    # Update parser_registry for each result
    for r in results:
        if r.get("name") != "SubprocessError":
            await _update_parser_registry(
                db, r["name"], r.get("ok", False),
                r.get("result", ""), r.get("duration", 0),
                error=r.get("error")
            )

    # HTML Fallback for failed parsers
    try:
        from graph.html_fallback import (
            FallbackManager, cryptorank_html_coins, cryptorank_html_funding,
            dropstab_html_activities, icodrops_html_upcoming,
        )
        from modules.parsers.proxy_helper import get_proxy_url as _get_proxy
        _proxy = _get_proxy()
        fallback_mgr = FallbackManager(db)

        failed_parsers = {r["name"] for r in results if not r.get("ok") and r.get("name") != "SubprocessError"}

        if "CryptoRank" in failed_parsers:
            should = await fallback_mgr.record_failure("CryptoRank")
            if should:
                try:
                    coins = await cryptorank_html_coins(proxy_url=_proxy)
                    for c in coins:
                        if c.get("symbol"):
                            await db.cryptorank_projects.update_one(
                                {"symbol": c["symbol"]}, {"$set": c}, upsert=True
                            )
                    results.append({"name": "CryptoRank_HTML", "ok": bool(coins), "result": f"{len(coins)} coins", "duration": 0})
                except Exception as e:
                    results.append({"name": "CryptoRank_HTML", "ok": False, "error": str(e)[:200]})
        else:
            await fallback_mgr.record_success("CryptoRank")

        if "Dropstab" in failed_parsers:
            should = await fallback_mgr.record_failure("Dropstab")
            if should:
                try:
                    acts = await dropstab_html_activities(proxy_url=_proxy)
                    for a in acts:
                        if a.get("project_id"):
                            await db.crypto_activities.update_one(
                                {"id": a["id"]}, {"$set": a}, upsert=True
                            )
                    results.append({"name": "Dropstab_HTML", "ok": bool(acts), "result": f"{len(acts)} activities", "duration": 0})
                except Exception as e:
                    results.append({"name": "Dropstab_HTML", "ok": False, "error": str(e)[:200]})
        else:
            await fallback_mgr.record_success("Dropstab")

        if "ICODrops" in failed_parsers:
            should = await fallback_mgr.record_failure("ICODrops")
            if should:
                try:
                    icos = await icodrops_html_upcoming(proxy_url=_proxy)
                    for i in icos:
                        if i.get("name"):
                            doc_id = f"icodrops_{i['name'].lower().replace(' ', '_')}"
                            await db.intel_events.update_one(
                                {"id": doc_id}, {"$set": {**i, "id": doc_id, "source": "icodrops_html"}}, upsert=True
                            )
                    results.append({"name": "ICODrops_HTML", "ok": bool(icos), "result": f"{len(icos)} icos", "duration": 0})
                except Exception as e:
                    results.append({"name": "ICODrops_HTML", "ok": False, "error": str(e)[:200]})
        else:
            await fallback_mgr.record_success("ICODrops")

    except Exception as e:
        logger.warning(f"[Fallback] Integration error: {e}")

    # Rebuild graph from funding data
    try:
        from scripts.run_data_pipeline import build_graph_from_funding, enrich_graph_from_protocols
        graph_r = await build_graph_from_funding(db)
        await enrich_graph_from_protocols(db)
        results.append({"name": "GraphRebuild", "ok": True, "result": str(graph_r)[:200]})
    except Exception as e:
        results.append({"name": "GraphRebuild", "ok": False, "error": str(e)[:200]})

    # Sync KNOWLEDGE edges into unified graph
    knowledge_sync = await sync_knowledge_edges(db)
    results.append({"name": "KnowledgeSync", "ok": True, "result": knowledge_sync})

    elapsed = time.time() - start
    ok_count = sum(1 for r in results if r.get("ok"))

    return {
        "ok": True,
        "pipeline": "GRAPH",
        "tiers_run": tiers,
        "parsers": results,
        "ok_count": ok_count,
        "total": len(results),
        "duration_sec": round(elapsed, 1),
    }


# Keep old name for backward compatibility
async def run_discovery_parsers():
    return await run_graph_pipeline()

    # Rebuild graph from funding data
    try:
        import sys
        sys.path.insert(0, '/app/backend')
        from scripts.run_data_pipeline import build_graph_from_funding, enrich_graph_from_protocols
        graph_r = await build_graph_from_funding(db)
        enrich_r = await enrich_graph_from_protocols(db)
        results.append({"name": "GraphRebuild", "ok": True, "result": str(graph_r)})
    except Exception as e:
        results.append({"name": "GraphRebuild", "ok": False, "error": str(e)})

    # Sync KNOWLEDGE edges into unified graph
    knowledge_sync = await sync_knowledge_edges(db)
    results.append({"name": "KnowledgeSync", "ok": True, "result": knowledge_sync})

    elapsed = time.time() - start
    ok_count = sum(1 for r in results if r.get("ok"))

    return {
        "ok": True,
        "parsers": results,
        "ok_count": ok_count,
        "total": len(results),
        "duration_sec": round(elapsed, 1),
    }


# ─── Orchestrator ───

async def run_graph_bridge():
    """
    Run full graph bridge: signals → edges.
    Safe to call repeatedly (idempotent upserts).
    """
    db = get_db()

    # Ensure indexes (safe: ignore conflicts)
    try:
        await db.graph_edges.create_index(
            [("from_node_id", 1), ("to_node_id", 1), ("relation_type", 1), ("layer", 1)],
            unique=True, name="idx_edge_layer_dedup"
        )
    except Exception:
        pass
    try:
        await db.graph_edges.create_index("layer", name="idx_layer")
    except Exception:
        pass
    try:
        await db.graph_edges.create_index("relation_type", name="idx_rel_type")
    except Exception:
        pass

    results = {}

    # KNOWLEDGE layer: build graph entities from raw data + sync
    try:
        from graph_entity_builder import build_all_graph_entities
        entity_result = await build_all_graph_entities(db)
        results["entity_builder"] = entity_result
    except Exception as e:
        results["entity_builder"] = {"ok": False, "error": str(e)[:200]}

    results["knowledge_edges"] = await sync_knowledge_edges(db)

    # SIGNAL layer: mention edges + actor enrichment
    results["mention_edges"] = await build_mention_edges(db)
    results["actor_enrichment"] = await enrich_actor_nodes(db)

    # P1: correlation edges
    results["correlation_edges"] = await build_correlation_edges(db)

    # P2: alpha edges + alpha_score EMA
    results["alpha_edges"] = await build_alpha_edges(db)

    # Node scores: alpha * 0.5 + influence * 0.3 + activity * 0.2
    results["node_scores"] = await compute_node_scores(db)

    # Stats
    total_signal_edges = await db.graph_edges.count_documents({"layer": LAYER})
    total_nodes = await db.graph_nodes.count_documents({})

    results["totals"] = {
        "signal_edges": total_signal_edges,
        "total_nodes": total_nodes,
    }

    return {"ok": True, **results}


async def get_graph_bridge_stats():
    """Get current graph bridge statistics."""
    db = get_db()

    total_nodes = await db.graph_nodes.count_documents({})
    total_edges = await db.graph_edges.count_documents({})
    signal_edges = await db.graph_edges.count_documents({"layer": LAYER})

    # Edge type breakdown (ALL layers)
    edge_types = {}
    pipeline = [
        {"$group": {"_id": {"layer": "$layer", "type": "$relation_type"}, "count": {"$sum": 1}}},
    ]
    async for doc in db.graph_edges.aggregate(pipeline):
        layer = doc["_id"].get("layer", "UNKNOWN")
        rtype = doc["_id"]["type"]
        key = f"{layer}:{rtype}"
        edge_types[key] = doc["count"]

    # Layer breakdown
    layer_counts = {}
    pipeline = [
        {"$group": {"_id": "$layer", "count": {"$sum": 1}}},
    ]
    async for doc in db.graph_edges.aggregate(pipeline):
        layer_counts[doc["_id"] or "UNKNOWN"] = doc["count"]

    # Node type breakdown
    node_types = {}
    pipeline = [
        {"$group": {"_id": "$type", "count": {"$sum": 1}}},
    ]
    async for doc in db.graph_nodes.aggregate(pipeline):
        node_types[doc["_id"]] = doc["count"]

    # Top actors by edge count
    pipeline = [
        {"$match": {"layer": LAYER, "relation_type": "MENTIONED_TOKEN"}},
        {"$group": {"_id": "$from_node_id", "tokens": {"$sum": 1}, "total_weight": {"$sum": "$weight"}}},
        {"$sort": {"tokens": -1}},
        {"$limit": 10},
    ]
    top_actors = []
    async for doc in db.graph_edges.aggregate(pipeline):
        top_actors.append({
            "actor": doc["_id"],
            "tokens_mentioned": doc["tokens"],
            "total_weight": round(doc["total_weight"], 3),
        })

    # Top actors by NODE SCORE
    pipeline = [
        {"$match": {"type": "twitter_account", "metadata.node_score": {"$exists": True}}},
        {"$sort": {"metadata.node_score": -1}},
        {"$limit": 10},
        {"$project": {"_id": 0, "id": 1, "label": 1, "metadata.node_score": 1,
                       "metadata.role": 1, "metadata.hit_rate_24h": 1}},
    ]
    top_scored = []
    async for doc in db.graph_nodes.aggregate(pipeline):
        top_scored.append({
            "actor": doc["id"],
            "label": doc.get("label", ""),
            "node_score": doc.get("metadata", {}).get("node_score", 0),
            "role": doc.get("metadata", {}).get("role", ""),
            "hit_rate": doc.get("metadata", {}).get("hit_rate_24h", 0),
        })

    return {
        "ok": True,
        "nodes": total_nodes,
        "edges_total": total_edges,
        "edges_signal": signal_edges,
        "layers": layer_counts,
        "edge_types": edge_types,
        "node_types": node_types,
        "top_actors": top_actors,
        "top_scored": top_scored,
    }
