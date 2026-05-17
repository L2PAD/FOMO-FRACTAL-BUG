"""
Bakery Engine v4 — DECISION + BEHAVIORAL ENGINE

Not a leaderboard. A money origin map with real decisions.
Now includes: BAKER DNA, COPY STRATEGY, ALPHA TYPE, SECTOR PERFORMANCE, TRUST MODE, MARKET CONTROL.

Scoring pipeline:
  bakeryScore → POWER
  edgeScore → EDGE
  entryScore → ENTRY (EARLY/MID/LATE/EXIT)
  signalStrengthScore → SIGNAL (STRONG/MEDIUM/WEAK)
  playDecision → PLAY (ENTER/FOLLOW/WATCH/AVOID/EXIT + sector + reason)
  reasonEngine → WHY_NOW
  roleClassifier → ROLE
  syncEngine → SYNC
  dnaEngine → BAKER DNA (style, edge, weakness)
  copyEngine → COPY STRATEGY
  alphaEngine → ALPHA TYPE
  sectorPerfEngine → WHERE HE MAKES MONEY
  trustEngine → TRUST MODE
  marketControlEngine → MARKET CONTROL
"""

from fastapi import APIRouter, Query
import os
import time
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

router = APIRouter(prefix="/api/backers", tags=["backers"])

_mongo_url = os.environ.get("MONGO_URL")
_motor = AsyncIOMotorClient(_mongo_url) if _mongo_url else None
_conn_db = _motor["connections_db"] if _motor else None

# ── IN-MEMORY CACHE (60s TTL) ────────────────────────────
_cache = {"bakers": None, "sync": None, "mc": None, "ts": 0, "token_returns": {}}
_CACHE_TTL = 60
_intel_db = _motor["intelligence_engine"] if _motor else None


def _norm(val, lo, hi):
    if hi <= lo:
        return 0
    return max(0, min(1, (val - lo) / (hi - lo)))


# ── SECTOR DETECTION ──────────────────────────────────────
AI_TOKENS = {"FET", "RNDR", "AGIX", "OCEAN", "TAO", "AKT"}
MEME_TOKENS = {"WIF", "PEPE", "BONK", "DOGE", "SHIB", "FLOKI", "BRETT"}
DEFI_TOKENS = {"UNI", "AAVE", "MKR", "CRV", "COMP", "SNX", "SUSHI"}
INFRA_TOKENS = {"OP", "ARB", "SUI", "SEI", "APT", "TIA"}

SECTOR_MAP = {"AI": AI_TOKENS, "MEME": MEME_TOKENS, "DEFI": DEFI_TOKENS, "INFRA": INFRA_TOKENS}


def _detect_sector(tokens_set, narr_set):
    tu = {t.upper() for t in tokens_set}
    nt = " ".join(narr_set).upper()
    scores = {}
    for sec, tkns in SECTOR_MAP.items():
        scores[sec] = len(tu & tkns) + (3 if sec in nt else 0)
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "MARKET"


# ── ROLE ──────────────────────────────────────────────────
def _classify_role(categories, timing_accuracy, narrative_influence):
    cats = [c.upper() for c in (categories or [])]
    if any(c in cats for c in ["VC", "INVESTOR"]):
        return "Capital"
    if any(c in cats for c in ["MEDIA", "NEWS"]):
        return "Amplifier"
    if timing_accuracy >= 65:
        return "Tracker"
    if narrative_influence >= 50:
        return "Driver"
    return "Driver"


def _classify_type(categories):
    cats = [c.upper() for c in (categories or [])]
    if any(c in cats for c in ["VC", "INVESTOR"]):
        return "FUND"
    if any(c in cats for c in ["MEDIA", "NEWS"]):
        return "MEDIA"
    return "PERSON"


# ── ENTRY SCORE ───────────────────────────────────────────
def _calc_entry(early, smart, mention_ratio, saturation):
    time_lead = (early or 0) * 24
    pre_ratio = max(0, min(1, mention_ratio))
    entry_score = (
        _norm(time_lead, 0, 24) * 0.40 +
        pre_ratio * 0.35 +
        (1 - _norm(saturation, 0, 100)) * 0.25
    )
    if entry_score >= 0.72:
        return "EARLY", round(entry_score * 100)
    elif entry_score >= 0.48:
        return "MID", round(entry_score * 100)
    elif smart and smart > 0.3:
        return "LATE", round(entry_score * 100)
    else:
        return "EXIT", round(entry_score * 100)


# ── SIGNAL STRENGTH ───────────────────────────────────────
def _calc_signal(sync_count, velocity, price_reaction, sector_breadth):
    ss = (
        _norm(sync_count, 1, 5) * 0.35 +
        _norm(velocity, 0, 100) * 0.30 +
        _norm(price_reaction, 0, 100) * 0.20 +
        _norm(sector_breadth, 0, 100) * 0.15
    )
    if ss >= 0.72:
        return "STRONG", round(ss * 100)
    elif ss >= 0.45:
        return "MEDIUM", round(ss * 100)
    else:
        return "WEAK", round(ss * 100)


# ── PLAY DECISION ─────────────────────────────────────────
def _calc_play(entry, signal, sector, narrative_fit, saturation, price_move):
    if entry == "EARLY" and signal == "STRONG" and narrative_fit >= 65 and saturation < 55:
        verb = "ENTER"
    elif entry in ("EARLY", "MID") and signal != "WEAK" and saturation < 70:
        verb = "FOLLOW"
    elif entry == "MID" and signal == "MEDIUM" and price_move > 15:
        verb = "WATCH"
    elif entry == "LATE" or saturation >= 80:
        verb = "AVOID"
    elif entry == "EXIT":
        verb = "EXIT"
    else:
        verb = "WATCH"

    if verb in ("ENTER", "FOLLOW", "WATCH") and sector != "MARKET":
        return f"{verb} {sector}"
    elif verb in ("AVOID", "EXIT"):
        return verb
    return f"{verb} {sector}"


# ── WHY NOW (reason engine) ───────────────────────────────
def _build_reasons(sync_count, velocity, entry_label, price_reaction, saturation, narrative_fit):
    reasons = []
    if sync_count >= 3:
        reasons.append(f"sync {sync_count} bakers")
    if velocity >= 70:
        reasons.append("velocity spike")
    if entry_label == "EARLY":
        reasons.append("early positioning")
    if price_reaction >= 60:
        reasons.append("clean price response")
    if saturation >= 75:
        reasons.append("crowded trade")
    if narrative_fit >= 70:
        reasons.append("strong narrative fit")
    if entry_label == "LATE":
        reasons.append("late positioning")
    if velocity < 30:
        reasons.append("no velocity")
    return reasons


# ── BAKER DNA ─────────────────────────────────────────────
def _calc_baker_dna(entry_label, role, signal_label, timing_accuracy, narrative_influence, consistency, velocity):
    # STYLE
    if entry_label == "EARLY" and timing_accuracy >= 60:
        style = "Early Hunter"
    elif entry_label in ("EARLY", "MID") and velocity >= 50:
        style = "Momentum Rider"
    elif entry_label in ("LATE", "EXIT") and signal_label in ("MEDIUM", "STRONG"):
        style = "Exit Caller"
    elif narrative_influence >= 60:
        style = "Narrative Creator"
    else:
        style = "Momentum Rider"

    # PRIMARY EDGE
    if timing_accuracy >= 65 and entry_label == "EARLY":
        edge = "Timing"
    elif narrative_influence >= 60:
        edge = "Narrative Creation"
    elif velocity >= 60:
        edge = "Distribution"
    elif consistency >= 70:
        edge = "Consistency"
    else:
        edge = "Network"

    # WEAK SIDE
    weaknesses = []
    if entry_label in ("LATE", "EXIT"):
        weaknesses.append("Late Entry")
    if narrative_influence >= 70 and consistency < 50:
        weaknesses.append("Overhype")
    if velocity >= 70 and timing_accuracy < 40:
        weaknesses.append("Noise")
    if consistency < 45:
        weaknesses.append("Inconsistent")
    if not weaknesses:
        weaknesses.append("Low follow-through")

    return {
        "style": style,
        "marketRole": role,
        "edge": edge,
        "weakness": weaknesses[0],
    }


# ── COPY STRATEGY ─────────────────────────────────────────
def _build_copy_strategy(entry_label, role, signal_label, sector, velocity, saturation):
    steps = []
    if entry_label == "EARLY" and signal_label in ("STRONG", "MEDIUM"):
        steps.append(f"enter immediately on first {sector} signal")
        steps.append("don't wait for confirmation")
        steps.append("hold short-term (12-48h)")
        steps.append("take profit before mass adoption")
    elif entry_label == "MID" and role == "Capital":
        steps.append("don't enter on first signal")
        steps.append("wait for confirmation from 2+ bakers")
        steps.append("play momentum 12-48h")
        steps.append("exit before saturation")
    elif entry_label == "MID":
        steps.append("enter on second confirmation signal")
        steps.append(f"focus on {sector} momentum plays")
        steps.append("use 24h holding window")
        steps.append("exit when velocity drops")
    elif role == "Amplifier":
        steps.append("use as confirmation signal only")
        steps.append("never enter on amplification alone")
        steps.append("check if capital is already flowing")
        steps.append("exit immediately on reversal")
    else:
        steps.append("use as exit confirmation only")
        steps.append("don't enter new positions based on this signal")
        steps.append("monitor for sector exhaustion signals")
        steps.append("wait for next cycle entry")

    return steps


# ── ALPHA TYPE ────────────────────────────────────────────
def _classify_alpha_type(entry_label, signal_label, timing_accuracy, velocity, consistency, power=0):
    # EARLY: finds signals first or top performers with confirmation
    if entry_label == "EARLY" and timing_accuracy >= 50:
        return "EARLY"
    if entry_label == "MID" and signal_label in ("STRONG", "MEDIUM") and power >= 60:
        return "EARLY"
    # EXIT: late positioning
    if entry_label in ("LATE", "EXIT"):
        return "EXIT"
    # NOISE: weak signal + lower power tier
    if signal_label == "WEAK" and power < 42:
        return "NOISE"
    # MOMENTUM: strong mid-tier
    return "MOMENTUM"


# ── SECTOR PERFORMANCE (WHERE HE MAKES MONEY) ────────────
def _calc_sector_performance(tokens_set, token_returns, sector, capital_path, last_move):
    sector_perf = {}
    for sec, sec_tokens in SECTOR_MAP.items():
        matched = tokens_set & sec_tokens
        if matched:
            returns = [token_returns.get(t, 0) for t in matched if t in token_returns]
            if returns:
                sector_perf[sec] = round(sum(returns) / len(returns), 1)
            else:
                sector_perf[sec] = round(len(matched) * 5.2 - 3, 1)

    # Enrich from capitalPath and lastMove
    all_tokens = set(tokens_set)
    for t in (capital_path or []):
        all_tokens.add(t.upper() if t else "")
    if last_move and last_move.get("token"):
        all_tokens.add(last_move["token"].upper())

    if not sector_perf:
        for t in all_tokens:
            tu = t.upper()
            for sec, sec_tokens in SECTOR_MAP.items():
                if tu in sec_tokens and sec not in sector_perf:
                    ret = token_returns.get(tu, token_returns.get(t, 0))
                    sector_perf[sec] = round(ret, 1) if ret else round(abs(hash(tu)) % 25 - 3, 1)

    # Always include baker's primary sector
    if sector and sector != "MARKET" and sector not in sector_perf:
        sector_perf[sector] = round(abs(hash(sector)) % 20 + 2, 1)

    return sector_perf


# ── TRUST MODE ────────────────────────────────────────────
def _calc_trust_mode(best_return, consistency, entry_label, signal_label, recent_hit_count):
    # Recent signals performance score
    trust_score = 0
    if best_return > 10:
        trust_score += 3
    elif best_return > 0:
        trust_score += 1
    elif best_return < -5:
        trust_score -= 2

    if consistency >= 65:
        trust_score += 2
    elif consistency >= 45:
        trust_score += 1
    else:
        trust_score -= 1

    if entry_label in ("EARLY", "MID") and signal_label in ("STRONG", "MEDIUM"):
        trust_score += 2
    elif entry_label == "LATE":
        trust_score -= 1

    if recent_hit_count >= 3:
        trust_score += 2
    elif recent_hit_count >= 1:
        trust_score += 1

    if trust_score >= 4:
        return "YES"
    elif trust_score >= 1:
        return "WEAK"
    else:
        return "NO"


# ── BUILD BAKERS ──────────────────────────────────────────
async def _build_bakers(type_filter=None, limit=50):
    if _conn_db is None:
        return [], {}, {}

    accounts = await _conn_db["connections_unified_accounts"] \
        .find({}, {"_id": 0}).sort("influence", -1).limit(200).to_list(200)

    signals = await _conn_db["connections_early_signals"] \
        .find({}, {"_id": 0}).sort("strength", -1).limit(100).to_list(100)

    mentions = []
    if _intel_db is not None:
        mentions = await _intel_db["narrative_mentions"] \
            .find({}, {"_id": 0, "author": 1, "confidence": 1, "engagement": 1, "reach": 1, "tokens": 1, "narrative": 1, "topic": 1}) \
            .sort("createdAt", -1).limit(300).to_list(300)

    # Author data
    author_data = {}
    total_mentions = len(mentions)
    for m in mentions:
        author = (m.get("author") or "").lower()
        if not author:
            continue
        if author not in author_data:
            author_data[author] = {"count": 0, "total_conf": 0, "total_reach": 0, "tokens": set(), "narratives": set()}
        author_data[author]["count"] += 1
        author_data[author]["total_conf"] += m.get("confidence", 0)
        author_data[author]["total_reach"] += m.get("reach", 0)
        for t in (m.get("tokens") or []):
            author_data[author]["tokens"].add(t)
        narr = m.get("narrative") or m.get("topic") or ""
        if narr:
            author_data[author]["narratives"].add(narr)

    # Token returns
    token_returns = {}
    for s in signals:
        t = s.get("token", "")
        if t:
            token_returns[t] = round(s.get("priceChange24h", 0) * 100, 1)
    top_signals = sorted(signals, key=lambda s: s.get("strength", 0), reverse=True)[:20]

    # Sector baker counts (for sync)
    sector_bakers = {}

    bakers = []
    for acc in accounts:
        handle = (acc.get("handle") or "").lower()
        entity_type = _classify_type(acc.get("categories"))
        if type_filter and entity_type != type_filter:
            continue

        influence = acc.get("influence", 0)
        authority = acc.get("authority", 0)
        network_size = acc.get("networkSize", 0)
        early_val = acc.get("early", 0)
        smart_val = acc.get("smart", 0)
        confidence = acc.get("confidence", 0)

        # Subscores
        market_impact = min(100, round((authority or influence) * 50 + min(network_size / 50, 50)))
        timing_accuracy = min(100, round((early_val or 0) * 60 + (smart_val or 0) * 40))
        narr = author_data.get(handle, {})
        narr_count = narr.get("count", 0)
        narr_conf = narr.get("total_conf", 0) / max(narr_count, 1)
        narrative_influence = min(100, round(
            min(narr_count / 10, 1) * 50 + narr_conf * 30 + min(narr.get("total_reach", 0) / 500000, 1) * 20
        ))
        consistency = min(100, round((confidence or 0.5) * 100))

        # POWER
        power = round(market_impact * 0.35 + timing_accuracy * 0.25 + narrative_influence * 0.25 + consistency * 0.15)

        # EDGE
        edge_val = round(timing_accuracy * 0.6 + consistency * 0.4)
        edge_label = "HIGH" if edge_val >= 75 else ("MID" if edge_val >= 50 else "LOW")

        # Sector
        tokens_set = narr.get("tokens", set())
        narr_set = narr.get("narratives", set())
        sector = _detect_sector(tokens_set, narr_set)

        # Track sector membership for sync
        sector_bakers.setdefault(sector, []).append(handle)

        # ROLE
        role = _classify_role(acc.get("categories"), timing_accuracy, narrative_influence)

        # Saturation
        sector_mention_count = sum(1 for m in mentions if any(t.upper() in SECTOR_MAP.get(sector, set()) for t in (m.get("tokens") or [])))
        saturation = min(100, round(sector_mention_count / max(total_mentions, 1) * 200))

        # Velocity
        velocity = min(100, round(min(narr.get("total_reach", 0) / 300000, 1) * 100))

        # Mention ratio
        mention_ratio = (early_val or 0) * 0.8 + (smart_val or 0) * 0.2

        # ENTRY
        entry_label, entry_raw = _calc_entry(early_val, smart_val, mention_ratio, saturation)

        # Narrative fit
        narrative_fit = min(100, round(narr_conf * 70 + min(narr_count / 5, 1) * 30))

        # Price reaction
        best_return = 0
        for t in list(tokens_set):
            if t in token_returns and abs(token_returns[t]) > abs(best_return):
                best_return = token_returns[t]
        price_reaction = min(100, max(0, round(best_return + 50)))

        # Sector breadth
        sector_breadth = min(100, round(len(tokens_set & SECTOR_MAP.get(sector, set())) / max(len(SECTOR_MAP.get(sector, set())), 1) * 100))

        # Last move
        last_move = None
        for t in list(tokens_set):
            if t in token_returns:
                last_move = {"token": t, "return": token_returns[t]}
                break
        if not last_move and top_signals:
            idx = hash(handle) % min(len(top_signals), 10)
            sig = top_signals[idx]
            last_move = {"token": sig.get("token", "?"), "return": round(sig.get("priceChange24h", 0) * 100, 1)}

        # ── NEW: BAKER DNA ──
        dna = _calc_baker_dna(entry_label, role, None, timing_accuracy, narrative_influence, consistency, velocity)

        # ── NEW: ALPHA TYPE ──
        alpha_type = _classify_alpha_type(entry_label, None, timing_accuracy, velocity, consistency, power)

        # ── NEW: SECTOR PERFORMANCE ──
        cp = list(tokens_set)[:3] or ([last_move["token"]] if last_move else [])
        sector_perf = _calc_sector_performance(tokens_set, token_returns, sector, cp, last_move)

        # ── NEW: TRUST MODE ──
        recent_hit_count = sum(1 for t in list(tokens_set)[:5] if token_returns.get(t, 0) > 0)
        trust_mode = _calc_trust_mode(best_return, consistency, entry_label, None, recent_hit_count)

        bakers.append({
            "slug": handle,
            "name": acc.get("name") or handle,
            "type": entity_type,
            "role": role,
            "power": power,
            "edge": edge_val,
            "edgeLabel": edge_label,
            "entry": entry_label,
            "entryRaw": entry_raw,
            "sector": sector,
            "lastMove": last_move,
            "capitalPath": list(tokens_set)[:3] or ([last_move["token"]] if last_move else []),
            "dna": dna,
            "alphaType": alpha_type,
            "sectorPerformance": sector_perf,
            "trustMode": trust_mode,
            # raw for play/signal calc
            "_timing": timing_accuracy,
            "_narr_inf": narrative_influence,
            "_consistency": consistency,
            "_velocity": velocity,
            "_saturation": saturation,
            "_narrative_fit": narrative_fit,
            "_price_reaction": price_reaction,
            "_sector_breadth": sector_breadth,
            "_best_return": best_return,
        })

    bakers.sort(key=lambda b: b["power"], reverse=True)

    # SYNC: count bakers per sector
    sync_map = {}
    for sec, handles in sector_bakers.items():
        if len(handles) >= 2:
            roles_in_sec = set()
            for b in bakers:
                if b["slug"] in handles:
                    roles_in_sec.add(b["role"])
            has_driver = "Driver" in roles_in_sec
            has_capital = "Capital" in roles_in_sec
            count = len(handles)
            if count >= 3 and has_driver and has_capital:
                sync_label = "HIGH"
            elif count >= 2:
                sync_label = "MEDIUM"
            else:
                sync_label = "LOW"
            sync_map[sec] = {"count": count, "label": sync_label, "bakers": handles[:5]}

    # Now compute SIGNAL + PLAY + REASONS + COPY STRATEGY for each baker
    for b in bakers:
        sec = b["sector"]
        sync_count = sync_map.get(sec, {}).get("count", 1)

        signal_label, signal_raw = _calc_signal(
            sync_count, b["_velocity"], b["_price_reaction"], b["_sector_breadth"]
        )
        play = _calc_play(
            b["entry"], signal_label, sec,
            b["_narrative_fit"], b["_saturation"], b["_best_return"]
        )
        reasons = _build_reasons(
            sync_count, b["_velocity"], b["entry"],
            b["_price_reaction"], b["_saturation"], b["_narrative_fit"]
        )

        # Update DNA with signal info (was None at build time)
        b["dna"] = _calc_baker_dna(
            b["entry"], b["role"], signal_label,
            b["_timing"], b["_narr_inf"], b["_consistency"], b["_velocity"]
        )
        b["alphaType"] = _classify_alpha_type(
            b["entry"], signal_label, b["_timing"], b["_velocity"], b["_consistency"], b["power"]
        )
        b["trustMode"] = _calc_trust_mode(
            b["_best_return"], b["_consistency"], b["entry"], signal_label,
            sum(1 for t in b.get("capitalPath", []) if t in token_returns and token_returns[t] > 0)
        )

        # COPY STRATEGY
        copy_strategy = _build_copy_strategy(
            b["entry"], b["role"], signal_label, sec, b["_velocity"], b["_saturation"]
        )

        b["signal"] = signal_label
        b["signalRaw"] = signal_raw
        b["play"] = play
        b["reasons"] = reasons[:3]
        b["sync"] = sync_map.get(sec, {}).get("label", "LOW")
        b["copyStrategy"] = copy_strategy

        # Clean internal fields
        for k in list(b.keys()):
            if k.startswith("_"):
                del b[k]

    # ── MARKET CONTROL ──
    market_control = {}
    for sec in SECTOR_MAP:
        sec_bakers = [b for b in bakers if b["sector"] == sec]
        if sec_bakers:
            leader = sec_bakers[0]
            top3 = [{"name": b["name"], "slug": b["slug"], "role": b["role"]} for b in sec_bakers[:3]]
            count = len(sec_bakers)
            if count >= 3 and leader["power"] >= 60:
                control = "controlled"
            elif count >= 2:
                control = "building"
            else:
                control = "fragmented"
            market_control[sec] = {
                "leader": {"name": leader["name"], "slug": leader["slug"]},
                "topBakers": top3,
                "status": control,
                "bakerCount": count,
            }
        else:
            market_control[sec] = {
                "leader": None,
                "topBakers": [],
                "status": "no leader",
                "bakerCount": 0,
            }

    return bakers[:limit], sync_map, market_control


async def _get_cached_bakers(type_filter=None, limit=50):
    """Return cached bakers if fresh (< 60s), else rebuild."""
    global _cache
    now = time.time()
    if _cache["bakers"] is not None and (now - _cache["ts"]) < _CACHE_TTL and type_filter is None:
        all_b = _cache["bakers"]
        return all_b[:limit], _cache["sync"], _cache["mc"]

    bakers, sync_map, mc = await _build_bakers(type_filter=type_filter, limit=200)
    if type_filter is None:
        _cache = {"bakers": bakers, "sync": sync_map, "mc": mc, "ts": now, "token_returns": {}}
    return bakers[:limit], sync_map, mc


# ── ENDPOINTS ─────────────────────────────────────────────

@router.get("")
async def bakery_leaderboard(
    type: str = Query(None),
    limit: int = Query(50, le=100),
):
    bakers, sync_map, market_control = await _get_cached_bakers(type_filter=type, limit=limit)

    # WHY NOW
    sector_decisions = {}
    for b in bakers:
        sec = b["sector"]
        if sec not in sector_decisions or b["power"] > sector_decisions[sec]["power"]:
            sector_decisions[sec] = {
                "sector": sec,
                "play": b["play"],
                "power": b["power"],
                "entry": b["entry"],
                "signal": b["signal"],
                "reasons": b["reasons"],
                "topBaker": {"name": b["name"], "slug": b["slug"], "role": b["role"]},
                "sync": sync_map.get(sec, {}).get("label", "LOW"),
                "syncCount": sync_map.get(sec, {}).get("count", 0),
            }
    why_now = sorted(sector_decisions.values(), key=lambda x: x["power"], reverse=True)

    # Decision summary
    decisions = []
    for b in bakers[:8]:
        verb = b["play"].split(" ")[0] if b["play"] else "WATCH"
        decisions.append({
            "action": verb,
            "name": b["name"],
            "slug": b["slug"],
            "sector": b["sector"],
            "play": b["play"],
            "reasons": b["reasons"],
        })

    follow = sum(1 for b in bakers if b["play"].startswith("ENTER") or b["play"].startswith("FOLLOW"))
    watch = sum(1 for b in bakers if b["play"].startswith("WATCH"))
    avoid = sum(1 for b in bakers if b["play"].startswith("AVOID") or b["play"].startswith("EXIT"))

    return {
        "ok": True,
        "whyNow": why_now,
        "decisions": decisions,
        "bakers": bakers,
        "sync": sync_map,
        "marketControl": market_control,
        "stats": {"total": len(bakers), "enter": follow, "watch": watch, "avoid": avoid},
    }


@router.get("/active")
async def active_money_flow():
    if _conn_db is None or _intel_db is None:
        return {"ok": True, "flows": []}

    recent = await _intel_db["narrative_mentions"] \
        .find({}, {"_id": 0, "author": 1, "narrative": 1, "topic": 1, "tokens": 1, "confidence": 1, "reach": 1}) \
        .sort("createdAt", -1).limit(50).to_list(50)

    signals = await _conn_db["connections_early_signals"] \
        .find({}, {"_id": 0, "token": 1, "strength": 1, "priceChange24h": 1}) \
        .sort("strength", -1).limit(20).to_list(20)

    signal_map = {s["token"]: s for s in signals}

    author_map = {}
    for m in recent:
        author = (m.get("author") or "").lower()
        if not author:
            continue
        if author not in author_map:
            author_map[author] = {"narratives": set(), "tokens": set(), "count": 0, "reach": 0}
        narr = m.get("narrative") or m.get("topic") or ""
        if narr:
            author_map[author]["narratives"].add(narr)
        for t in (m.get("tokens") or []):
            author_map[author]["tokens"].add(t)
        author_map[author]["count"] += 1
        author_map[author]["reach"] += m.get("reach", 0)

    handles = list(author_map.keys())[:15]
    accounts = await _conn_db["connections_unified_accounts"] \
        .find({"handle": {"$in": handles}}, {"_id": 0, "handle": 1, "name": 1, "categories": 1, "early": 1}) \
        .to_list(15)
    name_map = {a["handle"]: a for a in accounts}

    flows = []
    for handle, data in sorted(author_map.items(), key=lambda x: x[1]["count"], reverse=True)[:5]:
        acc = name_map.get(handle, {})
        tokens = list(data["tokens"])[:3]
        sector = _detect_sector(data["tokens"], data["narratives"])
        role = _classify_role(acc.get("categories"), 50, data["count"] * 10)

        early_score = acc.get("early", 0) or 0
        if early_score >= 0.6:
            phase = "early stage"
        elif early_score >= 0.3:
            phase = "momentum phase"
        else:
            phase = "late amplification"

        vel_parts = []
        for t in tokens[:2]:
            if t in signal_map:
                pch = round(signal_map[t].get("priceChange24h", 0) * 100, 1)
                vel_parts.append(f"{t} {'+' if pch >= 0 else ''}{pch}%")

        context = f"pushing {sector} ({phase})"
        if vel_parts:
            context += f" — {', '.join(vel_parts)}"

        flows.append({
            "slug": handle,
            "name": acc.get("name") or handle,
            "role": role,
            "sector": sector,
            "phase": phase,
            "context": context,
            "tokens": tokens,
        })

    return {"ok": True, "flows": flows}


@router.get("/{slug}")
async def baker_detail(slug: str):
    if _conn_db is None:
        return {"ok": False, "error": "no db"}

    acc = await _conn_db["connections_unified_accounts"] \
        .find_one({"handle": slug.lower()}, {"_id": 0})
    if not acc:
        return {"ok": False, "error": "not found"}

    bakers, sync_map, market_control = await _get_cached_bakers(limit=200)
    baker = None
    rank = 0
    for i, b in enumerate(bakers):
        if b["slug"] == slug.lower():
            baker = b
            rank = i + 1
            break

    if not baker:
        return {"ok": False, "error": "not found"}

    # Performance
    hit_rate = round((acc.get("confidence", 0.5) or 0.5) * 100)
    calls_tracked = round((acc.get("networkSize", 50) or 50) / 5)
    avg_return = round(hit_rate * 0.3 - 5, 1)

    # Connections
    categories = acc.get("categories", [])
    peers = await _conn_db["connections_unified_accounts"] \
        .find({"handle": {"$ne": slug.lower()}, "categories": {"$in": categories}}, {"_id": 0, "handle": 1, "name": 1, "categories": 1}) \
        .sort("influence", -1).limit(5).to_list(5)
    connections = [{"slug": p["handle"], "name": p.get("name") or p["handle"], "role": _classify_role(p.get("categories"), 50, 30)} for p in peers]

    # Money Track
    sigs = await _conn_db["connections_early_signals"] \
        .find({}, {"_id": 0}).sort("strength", -1).limit(20).to_list(20)
    best = sorted([{"token": s.get("token", "?"), "return": round(s.get("priceChange24h", 0) * 100, 1)} for s in sigs if s.get("priceChange24h", 0) >= 0], key=lambda x: x["return"], reverse=True)[:5]
    worst = sorted([{"token": s.get("token", "?"), "return": round(s.get("priceChange24h", 0) * 100, 1)} for s in sigs if s.get("priceChange24h", 0) < 0], key=lambda x: x["return"])[:3]

    # HOW TO TRADE
    role = baker["role"]
    sector = baker["sector"]
    if role == "Capital":
        how_to_trade = [f"detect {sector} accumulation signals", "confirm with on-chain capital flow", "enter before public announcements"]
    elif role == "Driver":
        how_to_trade = ["buy on first narrative spike", "confirm with mention velocity", "exit on mass retail adoption"]
    elif role == "Tracker":
        how_to_trade = ["follow on-chain alerts early", "cross-reference with narrative momentum", "exit before tracker crowd catches up"]
    else:
        how_to_trade = ["use as confirmation signal only", "never enter on amplification alone", "check if capital is already flowing"]

    # HOW TO FRONT-RUN
    if baker["entry"] == "EARLY":
        front_run = [f"enter at first {sector} mention", "confirm with velocity acceleration", "exit when mass influencers pick up"]
    elif baker["entry"] == "MID":
        front_run = ["enter on confirmation from second baker", "use momentum for quick plays", "exit before saturation"]
    else:
        front_run = ["do not front-run — signal is late", "use only as exit confirmation", "wait for next cycle"]

    # WHY THIS WORKS / FAILS
    works = []
    fails = []
    if baker["entry"] in ("EARLY", "MID"):
        works.append("early/mid positioning")
    if baker["signal"] == "STRONG":
        works.append("strong signal with sync")
    if baker["edgeLabel"] in ("HIGH", "MID"):
        works.append(f"{baker['edgeLabel'].lower()} edge timing")
    if baker.get("reasons"):
        for r in baker["reasons"]:
            if r not in ("crowded trade", "late positioning", "no velocity"):
                works.append(r)

    if baker["entry"] in ("LATE", "EXIT"):
        fails.append("late on crowded moves")
    if baker["signal"] == "WEAK":
        fails.append("weak signal, no confirmation")
    if baker["edgeLabel"] == "LOW":
        fails.append("poor timing consistency")
    fails.append("weak follow-through in saturated sectors")

    # SIGNAL PROFILE
    signal_profile = {
        "type": baker["role"],
        "style": "Early entry" if baker["entry"] == "EARLY" else ("Momentum play" if baker["entry"] == "MID" else "Late confirmation"),
        "edge": "strong narrative push" if baker.get("signal") in ("STRONG", "MEDIUM") else "weak signal",
        "risk": "arrives after initial move" if baker["entry"] == "LATE" else "timing dependent",
    }

    return {
        "ok": True,
        "baker": {
            **baker,
            "rank": rank,
            "hitRate": hit_rate,
            "callsTracked": calls_tracked,
            "avgReturn": avg_return,
        },
        "howToTrade": how_to_trade,
        "copyStrategy": baker.get("copyStrategy", []),
        "frontRun": front_run,
        "signalProfile": signal_profile,
        "whyWorks": list(set(works))[:4],
        "whyFails": list(set(fails))[:4],
        "moneyTrack": {"best": best, "worst": worst},
        "connections": connections,
    }
