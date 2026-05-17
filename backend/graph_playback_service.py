"""
Graph Playback Service — Flow Event Aggregation
=================================================
Pipeline: graph_relations → time buckets → aggregated flow events
Returns ordered events for edge-by-edge animation (NOT full graph reload).
"""

from collections import defaultdict


MAX_EVENTS = 500


async def get_playback_events(db, node_id=None, seeds=None, resolution="24h", max_events=MAX_EVENTS):
    """
    Build aggregated flow events from graph_relations.
    Groups transactions into time buckets → returns ordered events.
    
    Returns: { events: [...], time_range: {...}, total_events: int }
    """
    # Determine resolution bucket size in seconds
    bucket_seconds = {
        "1h": 3600, "6h": 21600, "24h": 86400,
        "7d": 604800, "30d": 2592000, "90d": 7776000,
    }.get(resolution, 86400)

    # Build query
    query = {}
    if node_id:
        query = {"$or": [{"source_id": node_id}, {"target_id": node_id}]}
    elif seeds:
        seed_list = [s.strip() for s in seeds.split(",") if s.strip()]
        if seed_list:
            query = {"$or": [
                {"source_id": {"$in": seed_list}},
                {"target_id": {"$in": seed_list}},
            ]}

    # Try graph_relation_buckets first (pre-aggregated)
    raw = await db["graph_relation_buckets"].find(query, {"_id": 0}).to_list(length=5000)

    if not raw:
        # Fallback to graph_relations
        raw = await db["graph_relations"].find(query, {"_id": 0}).to_list(length=5000)

    if not raw:
        return {"events": [], "time_range": {"start": 0, "end": 0}, "total_events": 0}

    # Aggregate into flow events by time bucket
    bucket_flows = defaultdict(lambda: defaultdict(lambda: {"volume_usd": 0, "tx_count": 0, "types": set()}))

    for r in raw:
        # Get timestamp
        ts = r.get("timestamp") or r.get("first_seen") or r.get("last_seen") or 0
        if isinstance(ts, str):
            try:
                from datetime import datetime, timezone
                ts = int(datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp())
            except (ValueError, TypeError):
                # Try bucket_day format
                try:
                    from datetime import datetime, timezone
                    ts = int(datetime.strptime(ts, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())
                except (ValueError, TypeError):
                    ts = 0
        if not ts:
            # Use bucket_day if available
            bd = r.get("bucket_day", "")
            if bd:
                try:
                    from datetime import datetime, timezone
                    ts = int(datetime.strptime(bd, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())
                except (ValueError, TypeError):
                    continue
            else:
                continue

        bucket = (ts // bucket_seconds) * bucket_seconds
        src = r.get("source_id", "")
        tgt = r.get("target_id", "")
        if not src or not tgt or src == tgt:
            continue

        edge_key = f"{src}->{tgt}"
        flow = bucket_flows[bucket][edge_key]
        flow["volume_usd"] += r.get("total_amount_usd", 0) or r.get("amount_usd", 0) or 0
        flow["tx_count"] += r.get("tx_count", 1) or 1
        flow["types"].add(r.get("relation_type", "transfer"))
        flow["source"] = src
        flow["target"] = tgt

    # Flatten into sorted event list
    events = []
    for bucket_ts in sorted(bucket_flows.keys()):
        for edge_key, flow in bucket_flows[bucket_ts].items():
            events.append({
                "timestamp": bucket_ts,
                "source": flow["source"],
                "target": flow["target"],
                "volume_usd": round(flow["volume_usd"], 2),
                "tx_count": flow["tx_count"],
                "type": list(flow["types"])[0] if flow["types"] else "transfer",
                "edge_key": edge_key,
            })

    # Sort by timestamp, then by volume (biggest flows first within bucket)
    events.sort(key=lambda e: (e["timestamp"], -e["volume_usd"]))

    # Cap events
    if len(events) > max_events:
        # Keep events from evenly distributed time buckets
        all_buckets = sorted(set(e["timestamp"] for e in events))
        step = max(1, len(all_buckets) // (max_events // 5))
        keep_buckets = set(all_buckets[::step])
        events = [e for e in events if e["timestamp"] in keep_buckets][:max_events]

    # Time range
    timestamps = [e["timestamp"] for e in events] if events else [0]

    return {
        "events": events,
        "time_range": {
            "start": min(timestamps),
            "end": max(timestamps),
        },
        "total_events": len(events),
        "resolution": resolution,
        "bucket_seconds": bucket_seconds,
    }


# Keep legacy function for backwards compatibility
async def get_playback_frames(db, node_id, resolution="24h", level=None, max_frames=120):
    """Legacy wrapper — converts events to frames format."""
    result = await get_playback_events(db, node_id=node_id, resolution=resolution)

    # Group events by timestamp into frames
    from collections import defaultdict as dd
    by_ts = dd(list)
    for e in result.get("events", []):
        by_ts[e["timestamp"]].append(e)

    frames = []
    for ts in sorted(by_ts.keys()):
        evts = by_ts[ts]
        nodes_set = set()
        edges = []
        flows = []
        for e in evts:
            nodes_set.add(e["source"])
            nodes_set.add(e["target"])
            edges.append({"id": e["edge_key"], "source": e["source"], "target": e["target"], "type": e["type"]})
            flows.append({"source": e["source"], "target": e["target"], "volume_usd": e["volume_usd"],
                          "tx_count": e["tx_count"], "direction": "out"})

        frames.append({
            "timestamp": ts,
            "key": str(ts),
            "nodes": [{"id": nid, "label": nid.split(":")[1][:10] if ":" in nid else nid, "type": "wallet"} for nid in nodes_set],
            "edges": edges,
            "flows": flows,
            "stats": {"node_count": len(nodes_set), "edge_count": len(edges), "flow_count": len(flows),
                       "total_volume": sum(f["volume_usd"] for f in flows)},
        })

    return {
        "node_id": node_id,
        "resolution": resolution,
        "level": level or "wallet",
        "total_frames": len(frames),
        "time_range": result.get("time_range", {}),
        "frames": frames,
    }
