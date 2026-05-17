"""Edge routes — proxy to Meta Brain influence data + Edge Opportunities + Prediction Markets."""
from fastapi import APIRouter, Query, Depends
from typing import Optional
from services.edge_service import get_edge, get_edge_detailed
from services.edge_opportunities import generate_edge_opportunities
from routes.auth import get_optional_user
import os
from pymongo import MongoClient, DESCENDING

router = APIRouter()

_client = MongoClient(os.getenv("MONGO_URL", "mongodb://localhost:27017"))
db = _client[os.getenv("DB_NAME", "fomo_mobile")]


@router.get("/edge")
def get_edge_endpoint(
    asset: Optional[str] = Query(default="BTC"),
    user=Depends(get_optional_user)
):
    """
    Edge endpoint - proxies to Meta Brain /influence
    Returns top opportunities sorted by impact
    
    🔒 PAYWALL: Requires PRO plan
    """
    asset_upper = asset.upper().strip()
    return get_edge(asset_upper, user)


@router.get("/edge/opportunities")
def get_edge_opportunities(
    asset: Optional[str] = Query(default=None),
    user=Depends(get_optional_user)
):
    """
    Edge Opportunities — early signals before main confirmation.
    Sources real data from sentiment, social, exchange, predictions.
    Each edge has: edgeScore, edgeState (FORMING/EARLY/CONFIRMING/SIGNAL)
    """
    asset_upper = asset.upper().strip() if asset else None
    opportunities = generate_edge_opportunities(asset_upper)
    return {"ok": True, "opportunities": opportunities, "count": len(opportunities)}


@router.post("/edge/track")
def track_edge(body: dict, user=Depends(get_optional_user)):
    """
    Track/untrack an edge opportunity.
    Body: { edgeId, symbol, action: "track"|"untrack"|"convert" }
    Feeds into behavior engine + push triggers.
    """
    from services.behavior_engine import track_event
    from pymongo import MongoClient
    import os

    user_id = str(user['_id']) if user else 'dev_user'
    edge_id = body.get('edgeId', '')
    symbol = body.get('symbol', '')
    action = body.get('action', 'track')

    client = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    db = client[os.environ.get("DB_NAME", "test_database")]

    if action == 'track':
        db.edge_tracking.update_one(
            {'userId': user_id, 'edgeId': edge_id},
            {'$set': {
                'userId': user_id, 'edgeId': edge_id, 'symbol': symbol,
                'tracked': True, 'trackedAt': __import__('datetime').datetime.now(__import__('datetime').timezone.utc),
                'converted': False,
            }},
            upsert=True,
        )
        track_event(user_id, 'TRACK_EDGE', {'symbol': symbol, 'edgeId': edge_id})
        return {"ok": True, "action": "tracked", "edgeId": edge_id}

    elif action == 'untrack':
        db.edge_tracking.update_one(
            {'userId': user_id, 'edgeId': edge_id},
            {'$set': {'tracked': False}},
        )
        return {"ok": True, "action": "untracked", "edgeId": edge_id}

    elif action == 'convert':
        db.edge_tracking.update_one(
            {'userId': user_id, 'edgeId': edge_id},
            {'$set': {
                'converted': True,
                'convertedAt': __import__('datetime').datetime.now(__import__('datetime').timezone.utc),
            }},
        )
        track_event(user_id, 'CONVERT_EDGE', {'symbol': symbol, 'edgeId': edge_id})
        return {"ok": True, "action": "converted", "edgeId": edge_id}

    return {"ok": False, "error": "Invalid action"}


@router.get("/edge/tracked")
def get_tracked_edges(user=Depends(get_optional_user)):
    """Get all tracked edges for user."""
    from pymongo import MongoClient
    import os

    user_id = str(user['_id']) if user else 'dev_user'
    client = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    db = client[os.environ.get("DB_NAME", "test_database")]

    tracked = list(db.edge_tracking.find(
        {'userId': user_id, 'tracked': True},
        {'_id': 0},
    ))
    return {"ok": True, "tracked": tracked, "count": len(tracked)}


@router.get("/edge/detailed")
def get_edge_detailed_endpoint(
    asset: Optional[str] = Query(default="BTC"),
    user=Depends(get_optional_user)
):
    """
    Detailed edge data with regime and performance
    
    🔒 PAYWALL: Requires PRO plan
    """
    asset_upper = asset.upper().strip()
    return get_edge_detailed(asset_upper)


@router.get("/prediction/markets")
async def get_prediction_markets(
    limit: int = Query(default=20),
    filter_type: str = Query(default="all"),  # all, hot, actionable
    asset: str = Query(default=None),
):
    """
    Prediction OS — Mobile API.
    Returns enriched Polymarket cards with edge, recommendation, repricing, timing.
    Reads from prediction_market_states (pre-computed by /api/prediction/run pipeline).
    """
    query = {}

    # Filter by asset
    if asset:
        query["asset"] = asset.upper()

    # Filter by type
    if filter_type == "hot":
        query["last_recommendation"] = {"$nin": ["AVOID", None]}
        query["last_stage"] = {"$nin": ["invalidated", None]}
    elif filter_type == "actionable":
        query["last_entry_action"] = {"$nin": ["do_not_enter", None]}

    states = list(db.prediction_market_states.find(
        query, {"_id": 0}
    ).sort("last_updated_at", DESCENDING).limit(limit))

    # Get market details for questions and prices
    market_ids = [s.get("market_id") for s in states if s.get("market_id")]
    markets_map = {}
    if market_ids:
        for m in db.prediction_markets.find({"market_id": {"$in": market_ids}}, {"_id": 0}):
            markets_map[str(m.get("market_id"))] = m

    # Also get recent alerts
    recent_alerts = {}
    for alert in db.prediction_alerts.find({}).sort("created_at", DESCENDING).limit(50):
        mid = str(alert.get("market_id"))
        if mid not in recent_alerts:
            recent_alerts[mid] = {
                "type": alert.get("alert_type"),
                "priority": alert.get("priority"),
                "title": alert.get("title"),
            }

    cards = []
    for s in states:
        mid = str(s.get("market_id", ""))
        market = markets_map.get(mid, {})
        question = s.get("question") or market.get("question", "")
        asset_sym = s.get("asset", "CRYPTO")

        # Recommendation → action label
        rec = s.get("last_recommendation", "WATCH")
        conv = s.get("last_conviction", "LOW")
        size = s.get("last_size", "NONE")
        edge = s.get("last_edge", 0)
        fair_prob = s.get("last_fair_prob", 0.5)
        market_prob = s.get("last_market_prob", 0.5)
        stage = s.get("last_stage", "")
        repricing = s.get("last_repricing_state", "")
        entry_action = s.get("last_entry_action", "do_not_enter")
        confidence = s.get("last_confidence", 0.3)
        alignment = s.get("last_alignment", 0)

        # Build action label like "BUY YES NOW" / "BUY NO SOON" / "WATCH"
        if rec in ("YES_NOW", "YES_SMALL"):
            action_label = f"BUY YES {'NOW' if rec == 'YES_NOW' else 'SOON'}"
            action_color = "green"
        elif rec in ("NO_NOW", "NO_SMALL"):
            action_label = f"BUY NO {'NOW' if rec == 'NO_NOW' else 'SOON'}"
            action_color = "red"
        elif rec == "WATCH":
            action_label = "WATCHING"
            action_color = "orange"
        elif rec == "GOOD_IDEA_BAD_PRICE":
            action_label = "WAIT FOR PRICE"
            action_color = "yellow"
        else:
            action_label = rec
            action_color = "gray"

        # Edge description
        abs_edge = abs(edge) if edge else 0
        if edge and edge > 0.02:
            edge_text = f"YES looks underpriced by {abs_edge * 100:.1f}%"
        elif edge and edge < -0.02:
            edge_text = f"Market appears overpriced by {abs_edge * 100:.1f}%"
        else:
            edge_text = "Market appears fairly priced"

        # Tags
        tags = []
        if stage not in ("invalidated", ""):
            tags.append(stage.upper())
        event_type = s.get("event_type", "")
        if event_type:
            tags.append(event_type.replace("_", " "))
        if repricing and repricing != "fair_value":
            tags.append(repricing.replace("_", " "))

        # Market data
        yes_price = market.get("yes_price", market_prob)
        volume = market.get("volume", 0)
        liquidity = market.get("liquidity", 0)
        end_date = market.get("end_date", "")

        # Time left
        time_left = ""
        if end_date:
            from datetime import datetime, timezone
            try:
                end = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
                now = datetime.now(timezone.utc)
                delta = end - now
                hours = int(delta.total_seconds() / 3600)
                if hours > 24:
                    time_left = f"{hours // 24}d left"
                elif hours > 0:
                    time_left = f"{hours}h left"
                else:
                    time_left = "ending soon"
            except Exception:
                pass

        # Alert
        alert_info = recent_alerts.get(mid)

        card = {
            "id": mid,
            "question": question,
            "asset": asset_sym,
            "actionLabel": action_label,
            "actionColor": action_color,
            "conviction": conv,
            "size": size,
            "edge": round(edge, 4) if edge else 0,
            "edgePercent": round(abs_edge * 100, 2),
            "edgeText": edge_text,
            "fairProb": round(fair_prob, 3),
            "marketProb": round(yes_price if yes_price else market_prob, 3),
            "modelProb": round(fair_prob, 3),
            "volume": round(volume),
            "liquidity": round(liquidity),
            "timeLeft": time_left,
            "confidence": round(confidence, 2),
            "alignment": round(alignment, 2),
            "stage": stage,
            "repricing": repricing,
            "entryAction": entry_action,
            "tags": tags[:4],
            "eventType": event_type,
            "alert": alert_info,
            "source": "polymarket",
        }
        cards.append(card)

    # Sort: actionable first, then by edge
    cards.sort(key=lambda c: (
        0 if "BUY" in c["actionLabel"] else 1 if c["actionLabel"] == "WATCHING" else 2,
        -abs(c["edge"])
    ))

    # Build outcome ladders for price_threshold markets
    # Group related markets by asset + date pattern
    from collections import defaultdict
    import re
    ladders = defaultdict(list)
    for c in cards:
        if c.get("eventType") == "price_threshold":
            # Extract date part for grouping
            q = c["question"]
            date_match = re.search(r'(on|by)\s+(April|May|June|July|August|September|October|November|December|January|February|March)\s+\d+', q, re.I)
            date_key = date_match.group(0) if date_match else ""
            group_key = f"{c['asset']}_{date_key}"
            ladders[group_key].append(c)

    # Attach ladder data to each card
    for group_key, group in ladders.items():
        if len(group) > 1:
            # Sort by threshold (extract from question)
            for gc in group:
                threshold_match = re.search(r'\$?([\d,]+)', gc["question"])
                gc["_threshold"] = int(threshold_match.group(1).replace(",", "")) if threshold_match else 0
            group.sort(key=lambda x: x["_threshold"], reverse=True)

            outcomes = []
            for gc in group:
                outcomes.append({
                    "threshold": gc["_threshold"],
                    "probability": gc["marketProb"],
                    "edge": gc["edge"],
                    "direction": "up" if gc["edge"] > 0 else "down",
                })
                # Attach ladder to each card in group
                gc["outcomes"] = outcomes
                gc["outcomeCount"] = len(group)

    hot_count = sum(1 for c in cards if "BUY" in c["actionLabel"])
    actionable_count = sum(1 for c in cards if c["entryAction"] != "do_not_enter")

    return {
        "ok": True,
        "markets": cards,
        "count": len(cards),
        "stats": {
            "hot": hot_count,
            "actionable": actionable_count,
            "total": len(cards),
        }
    }
