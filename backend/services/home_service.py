"""Home Service — UNIFIED Data Pipeline.

ARCHITECTURE:
  All screens (Home, Signal Detail, Edge, MiniApp) use the SAME signal engine.
  Backend = single source of truth.
  UI = pure renderer, zero logic.

  generate_signal() → 6 modules → decision framework → unified payload
"""
import logging
import os
from datetime import datetime, timezone
from pymongo import MongoClient, DESCENDING

logger = logging.getLogger(__name__)

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "fomo_mobile")
mongo_client = MongoClient(MONGO_URL)
db = mongo_client[DB_NAME]


def check_and_expire_subscription(user: dict) -> dict:
    if not user:
        return user
    if user.get("plan") != "PRO":
        return user
    expires_at = user.get("expiresAt")
    if expires_at:
        now = datetime.now(timezone.utc)
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < now:
            logger.info(f"Subscription expired for user {user.get('_id')}.")
            db.users.update_one(
                {"_id": user["_id"]},
                {"$set": {"plan": "FREE", "planStatus": "EXPIRED", "expiresAt": None}}
            )
            user["plan"] = "FREE"
            user["planStatus"] = "EXPIRED"
            user["expiresAt"] = None
    return user


def build_home_payload(asset: str, user: dict = None) -> dict:
    """
    UNIFIED HOME PAYLOAD — single source of truth.
    Uses generate_signal() from signals_service for 6-module data.
    UI renders this directly — no frontend logic.
    """
    from services.signals_service import generate_signal, get_market_state

    if user:
        user = check_and_expire_subscription(user)

    is_pro = False
    if user:
        is_pro = user.get("plan") == "PRO" or user.get("subscription", {}).get("plan") == "PRO"

    # ══════════════════════════════════════════
    # CORE: Generate signal from 6-module pipeline
    # ══════════════════════════════════════════
    sig = generate_signal(asset)

    price = sig.get("price") or 0
    direction = sig.get("direction", "Neutral")
    action = sig.get("action", "WAIT")
    confidence = sig.get("confidence", 0)
    df = sig.get("decisionFramework", {})
    conflict = sig.get("conflict", {})
    truth = sig.get("truth", {})
    drivers = sig.get("drivers", [])

    # ══════════════════════════════════════════
    # DECISION block (ready to render)
    # ══════════════════════════════════════════
    decision_block = {
        "action": action,
        "confidence": round(confidence * 100),
        "direction": direction,
        "risk": "HIGH" if confidence < 0.25 else "LOW" if confidence > 0.6 else "MEDIUM",
        "horizon": sig.get("horizon", "swing"),
    }

    # ══════════════════════════════════════════
    # SIGNAL block (stage / alignment / timing)
    # ══════════════════════════════════════════
    signal_block = {
        "stage": df.get("stage", "EARLY"),
        "stageLabel": df.get("stageLabel", "Scanning for alignment"),
        "alignment": df.get("alignedCount", 0),
        "totalModules": df.get("totalModules", 6),
        "alignmentText": df.get("alignment", "0 of 6 aligned"),
        "timing": df.get("timing", "SCANNING"),
        "timingLabel": df.get("timingLabel", "System scanning"),
    }

    # ══════════════════════════════════════════
    # SUMMARY block (ready to render, no frontend logic)
    # ══════════════════════════════════════════
    summary_block = {
        "title": sig.get("summary", ""),
        "whatMattersNow": df.get("mattersPoints", [])[:4],
    }

    # ══════════════════════════════════════════
    # MODULES block (6 modules, each ready to render)
    # ══════════════════════════════════════════
    modules = []
    for d in drivers:
        mod = {
            "type": d["module"],
            "label": d["name"],
            "state": d["direction"].upper(),
            "description": d.get("insight", d.get("reason", "")),
            "value": d.get("value", ""),
            "confidence": d.get("confidence"),
        }
        # PRO gets full data, FREE gets description only
        if not is_pro and d["module"] not in ("exchange", "fractal"):
            mod["value"] = None
            mod["confidence"] = None
        modules.append(mod)

    # ══════════════════════════════════════════
    # STRUCTURE block (multi-timeframe from exchange forecasts)
    # ══════════════════════════════════════════
    intel_db = mongo_client.get_database("intelligence_engine")
    forecasts = list(intel_db.exchange_forecasts.find(
        {"asset": asset.upper()}, sort=[("createdAt", DESCENDING)]
    ).limit(3))

    structure = {}
    for fc in forecasts:
        h = fc.get("horizon", "7D")
        d = fc.get("direction", "NEUTRAL")
        c = fc.get("confidence", 0)
        state = "bullish" if "BULL" in d else "bearish" if "BEAR" in d else "neutral"
        structure[h.lower()] = {
            "direction": state,
            "confidence": round(c * 100),
        }
    # Ensure all timeframes present
    for tf in ["24h", "7d", "30d"]:
        if tf not in structure:
            structure[tf] = {"direction": "neutral", "confidence": 0}

    # ══════════════════════════════════════════
    # TRUTH block (system performance — always from backend)
    # ══════════════════════════════════════════
    total_trades = truth.get("totalTrades", 0)
    win_rate = truth.get("winRate", 0)
    streak = truth.get("streak", 0)
    learning = total_trades < 10

    truth_block = {
        "winRate": win_rate,
        "streak": streak,
        "totalTrades": total_trades,
        "avgPnl": truth.get("avgPnl", 0),
        "learning": learning,
        "label": f"System learning — first outcomes soon" if learning
                 else f"Last {total_trades} signals: {win_rate}% profitable",
        "recent": truth.get("recentPnl", []),
    }

    # ══════════════════════════════════════════
    # CONFLICT block
    # ══════════════════════════════════════════
    conflict_block = {
        "hasConflict": conflict.get("hasConflict", False),
        "summary": conflict.get("summary", ""),
    }

    # ══════════════════════════════════════════
    # PRESSURE block (monetization layer)
    # ══════════════════════════════════════════
    pressure_block = None
    if not is_pro:
        pressure_block = {
            "line": "PRO users already positioned",
            "entryTeaser": "Entry zone identified" if action != "WAIT" else None,
            "urgency": "Entry window active" if action != "WAIT" else "Setup evolving",
        }

    # ══════════════════════════════════════════
    # PARTIAL REVEAL (entry/target teasers for FREE)
    # ══════════════════════════════════════════
    pr = sig.get("partialReveal", {})
    partial_reveal = {
        "locked": pr.get("locked", not is_pro),
        "entryTeaser": pr.get("entryTeaser", "Entry zone identified"),
        "pressureLine": pr.get("pressureLine", "PRO users already inside this setup"),
        "potentialRange": pr.get("potentialRange", ""),
    }

    # ══════════════════════════════════════════
    # MARKET STORY (single line for compact display)
    # ══════════════════════════════════════════
    obs = db.exchange_observations.find_one(
        {"asset": asset.upper()}, sort=[("ts", DESCENDING)]
    )
    change_24h = obs.get("change24h", 0) if obs else 0

    if action == "BUY":
        market_story = f"Structure turning bullish. {signal_block['alignment']} of 6 modules aligned."
    elif action == "SELL":
        market_story = f"Bearish pressure building. {signal_block['alignment']} of 6 modules aligned."
    else:
        if conflict_block["hasConflict"]:
            market_story = conflict_block["summary"]
        else:
            market_story = f"Market scanning — {signal_block['alignment']} of 6 aligned. Watching for convergence."

    return {
        "ok": True,
        "asset": asset.upper(),
        "price": round(price, 2) if price else 0,
        "change24h": round(change_24h, 1),

        "decision": decision_block,
        "signal": signal_block,
        "summary": summary_block,
        "modules": modules,
        "structure": structure,
        "truth": truth_block,
        "conflict": conflict_block,
        "pressure": pressure_block,
        "partialReveal": partial_reveal,
        "marketStory": market_story,

        "plan": user.get("plan", "FREE") if user else "FREE",
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }


async def get_home(asset: str, user=None) -> dict:
    """Main handler for /api/mobile/home."""
    return build_home_payload(asset.upper().strip(), user)
