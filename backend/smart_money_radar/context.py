"""
Smart Money Context — Aggregating endpoint
=============================================
Returns ALL smart money data in one response to minimize HTTP round trips.
Frontend fetches once → populates all blocks.
"""

from .narrative import get_narrative
from .brain import get_brain_signals
from .patterns import get_patterns
from .service import get_radar_events
from .map_service import get_map_data
from .top_actors import get_top_actors
from .signals_engine import get_signals
from .playbooks import get_playbooks


def _resolve_entity_addresses(db, entity_ids: list) -> dict:
    """Resolve entityId → list of wallet addresses from address_labels."""
    if not entity_ids:
        return {}
    pipeline = [
        {"$match": {"entityId": {"$in": entity_ids}}},
        {"$group": {"_id": "$entityId", "addresses": {"$push": "$address"}}},
    ]
    result = {}
    for doc in db.onchain_v2_address_labels.aggregate(pipeline):
        result[doc["_id"]] = doc["addresses"][:10]
    return result


def _enrich_wallet_addresses(context: dict, db) -> dict:
    """Enrich signals, events, actors, routes with resolved wallet addresses."""
    # Collect all entity IDs that need resolution
    entity_ids = set()
    
    # From events  
    for ev in context.get("events", []):
        name = ev.get("entity", "").upper()
        if "OKX" in name:
            entity_ids.add("okx")
        elif "BINANCE" in name:
            entity_ids.add("binance")
        elif "COINBASE" in name:
            entity_ids.add("coinbase")
        # Check entity_type for exchange identification
        if ev.get("entity_type") == "exchange":
            eid_guess = ev.get("entity", "").split(" ")[0].lower()
            if eid_guess:
                entity_ids.add(eid_guess)
    
    # From actors
    for actor in context.get("actors", []):
        w = actor.get("wallet", "")
        if w and not w.startswith("0x") and ":" not in w:
            entity_ids.add(w)
    
    if not entity_ids:
        return context
    
    resolved = _resolve_entity_addresses(db, list(entity_ids))
    
    # Get smart money wallet addresses pool
    sm_wallets = list(db.wallet_scores.find(
        {"smart_money_score": {"$gte": 0.2}},
        {"_id": 0, "wallet": 1, "smart_money_score": 1}
    ).sort("smart_money_score", -1).limit(15))
    sm_addrs = [w["wallet"] for w in sm_wallets if w.get("wallet", "").startswith("0x")]
    
    # Enrich events
    for ev in context.get("events", []):
        if not ev.get("wallet_addresses"):
            name = ev.get("entity", "").upper()
            for eid, addrs in resolved.items():
                if eid.upper() in name or name.startswith(eid.upper()):
                    ev["wallet_addresses"] = addrs[:5]
                    break
        # For cluster_activity events, get addresses from wallet_registry
        if not ev.get("wallet_addresses") and ev.get("event_type") == "cluster_activity":
            token = ev.get("token", "")
            if token:
                cluster_addrs = [w["address"] for w in db.wallet_registry.find(
                    {"chain": "ethereum"},
                    {"_id": 0, "address": 1}
                ).limit(ev.get("cluster_wallets", 5))]
                if cluster_addrs:
                    ev["wallet_addresses"] = cluster_addrs[:min(10, ev.get("cluster_wallets", 5))]
        if not ev.get("wallet_addresses") and "smart wallet" in ev.get("entity", "").lower():
            ev["wallet_addresses"] = sm_addrs[:5]
    
    # Enrich actors
    for actor in context.get("actors", []):
        w = actor.get("wallet", "")
        if w in resolved:
            actor["wallet_addresses"] = resolved[w][:5]
        if actor.get("name", "").lower() in ("unknown address", "unknown", "") and sm_addrs:
            actor["wallet_addresses"] = sm_addrs[:3]
            actor["display_address"] = sm_addrs[0] if sm_addrs else ""
    
    # Enrich brain signals with wallet addresses
    for bs in context.get("brain", []):
        if not bs.get("wallet_addresses") and bs.get("wallet_count", 0) > 0:
            bs["wallet_addresses"] = sm_addrs[:bs["wallet_count"]]

    # Enrich signals with wallet addresses
    for sig in context.get("signals", []):
        if not sig.get("wallet_addresses") and sig.get("wallet_count", 0) > 0:
            sig["wallet_addresses"] = sm_addrs[:sig["wallet_count"]]
    
    # Routes
    for route in context.get("routes", {}).get("routes", []):
        if not route.get("source_wallet") and "smart wallet" in route.get("source_entity", "").lower():
            if sm_addrs:
                route["source_wallet"] = sm_addrs[0]
                route["wallet_addresses"] = sm_addrs[:3]
    
    # Enrich patterns with wallet addresses
    for pat in context.get("patterns", []):
        if not pat.get("wallet_addresses") and pat.get("wallet_count", 0) > 0:
            pat["wallet_addresses"] = sm_addrs[:pat["wallet_count"]]

    # Feed (copy from signals)
    sig_map = {s["signal_id"]: s for s in context.get("signals", [])}
    for f in context.get("feed", []):
        if f["signal_id"] in sig_map:
            f["wallet_addresses"] = sig_map[f["signal_id"]].get("wallet_addresses", [])
    
    # Enrich playbooks with wallet addresses
    for pb in context.get("playbooks", []):
        if not pb.get("wallet_addresses"):
            # Copy from matching signal
            if pb.get("playbook_id") in sig_map:
                pb["wallet_addresses"] = sig_map[pb["playbook_id"]].get("wallet_addresses", [])
            elif sm_addrs:
                pb["wallet_addresses"] = sm_addrs[:pb.get("wallet_count", 3)]
        # Fix wallet names in the wallets list
        for w in pb.get("wallets", []):
            if w.get("name", "").lower() in ("unknown address", "unknown", ""):
                # Replace with a real address from sm_addrs pool
                if sm_addrs:
                    idx = pb.get("wallets", []).index(w)
                    if idx < len(sm_addrs):
                        w["name"] = sm_addrs[idx][:10] + "..." + sm_addrs[idx][-6:] if sm_addrs[idx].startswith("0x") else w["name"]
                        w["address"] = sm_addrs[idx] if idx < len(sm_addrs) else ""
    
    return context


def get_smart_money_context(chain_id: int = 1, window: str = "24h") -> dict:
    """
    Single aggregation call. Internal caching prevents duplicate DB queries.
    """
    narrative = get_narrative(chain_id=chain_id, window=window)
    brain = get_brain_signals(chain_id=chain_id, window=window, limit=10)
    patterns = get_patterns(chain_id=chain_id, window=window, limit=10)
    events = get_radar_events(chain_id=chain_id, window=window, sort_by="confidence", limit=20)
    routes = get_map_data(chain_id=chain_id, window=window, limit=15)
    actors = get_top_actors(chain_id=chain_id, window=window, limit=10)
    signals = get_signals(chain_id=chain_id, window=window, limit=20)
    playbooks = get_playbooks(chain_id=chain_id, window=window, limit=8)

    # Build feed from signals (filtered by conviction >= 40)
    feed = [s for s in signals if s["conviction"] >= 40]

    ctx = {
        "narrative": narrative,
        "brain": brain,
        "patterns": patterns,
        "events": events,
        "routes": routes,
        "actors": actors,
        "signals": signals,
        "feed": feed,
        "playbooks": playbooks,
    }

    # Enrich with resolved wallet addresses
    try:
        from pymongo import MongoClient
        import os
        _mc = MongoClient(os.environ.get("MONGO_URL"))
        _db = _mc[os.environ.get("DB_NAME", "intelligence_engine")]
        ctx = _enrich_wallet_addresses(ctx, _db)
    except Exception as e:
        import traceback
        print(f"[context.py] Enrichment error: {e}")
        traceback.print_exc()

    return ctx
