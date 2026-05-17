"""
Narrative Decision Engine v2
─────────────────────────────
Full pipeline:
  1. narrativeScore → action (BUY EARLY / WATCH / LATE / AVOID)
  2. rotation detection with action (BUY / WATCH)
  3. front-run signals (STRONG / EARLY / WEAK)
  4. token-level actions + TOP PICKS
  5. Smart Money Origin — who moved first
  6. Trade Setup — synthesized top opportunity
"""

import os, math
from datetime import datetime, timezone
from pymongo import MongoClient
from collections import defaultdict

_client = None

def _db():
    global _client
    if _client is None:
        _client = MongoClient(os.environ.get("MONGO_URL"))
    return _client["intelligence_engine"]

def _cdb():
    global _client
    if _client is None:
        _client = MongoClient(os.environ.get("MONGO_URL"))
    return _client["connections_db"]

def _normalize(val, lo, hi):
    if hi <= lo:
        return 0
    return max(0.0, min(1.0, (val - lo) / (hi - lo)))


def _load_narratives():
    return list(_db().narratives.find({}, {"_id": 0}))

def _load_narrative_mentions():
    return list(_db().narrative_mentions.find({}, {"_id": 0}))


# ─── 1. NARRATIVE SCORE ───────────────────────────────────

def compute_narrative_scores(narratives):
    """narrativeScore = velocity*0.4 + mentionGrowth*0.3 + influencerShare*0.2 + earlyPhaseBonus*0.1"""
    if not narratives:
        return []

    max_vel = max((n.get("velocity", 0) for n in narratives), default=1) or 1
    max_mentions = max((n.get("mentionCount", 0) for n in narratives), default=1) or 1

    results = []
    for n in narratives:
        phase = n.get("state", n.get("phase", "SEEDING"))
        velocity = n.get("velocity", 0)
        mentions = n.get("mentionCount", 0)
        influencers = n.get("uniqueInfluencers", 0)
        nms = n.get("nms", 0)

        vel_score = _normalize(velocity, 0, max_vel)
        mention_score = _normalize(mentions, 0, max_mentions)
        inf_share = influencers / max(1, mentions) if mentions > 0 else 0
        inf_score = _normalize(inf_share, 0, 0.5)
        phase_bonus = {"IGNITION": 1.0, "SEEDING": 0.6}.get(phase, 0)

        score = vel_score * 0.4 + mention_score * 0.3 + inf_score * 0.2 + phase_bonus * 0.1

        if score > 0.75 and phase == "IGNITION":
            action = "BUY EARLY"
        elif score > 0.65 and phase == "IGNITION":
            action = "WATCH"
        elif phase == "EXPANSION":
            action = "LATE"
        elif phase == "SEEDING" and score > 0.5:
            action = "WATCH"
        else:
            action = "AVOID"

        confidence = "HIGH" if influencers > 20 and mentions > 100 else ("MID" if influencers > 10 else "LOW")

        results.append({
            "key": n.get("key", ""),
            "name": n.get("displayName", n.get("key", "")),
            "phase": phase,
            "score": round(score, 2),
            "action": action,
            "confidence": confidence,
            "velocity": velocity,
            "mentions": mentions,
            "influencers": influencers,
            "nms": round(nms, 2),
            "tokens": n.get("tokens", []),
        })

    results.sort(key=lambda x: -x["score"])
    return results


# ─── 2. ROTATION DETECTOR (+ action) ─────────────────────

def detect_rotations(scored):
    if len(scored) < 2:
        return []

    losing = [n for n in scored if n["phase"] in ("EXPANSION", "SATURATION", "DECAY")]
    gaining = [n for n in scored if n["phase"] in ("IGNITION", "SEEDING") and n["score"] > 0.4]

    if not losing or not gaining:
        all_sorted = sorted(scored, key=lambda x: x["velocity"])
        if len(all_sorted) >= 2:
            low, high = all_sorted[0], all_sorted[-1]
            if high["velocity"] > low["velocity"] * 1.5:
                gaining, losing = [high], [low]
            else:
                return []

    max_vel = max((n["velocity"] for n in scored), default=1) or 1
    rotations = []

    for src in losing:
        for dst in gaining:
            if src["key"] == dst["key"]:
                continue
            vel_delta = (dst["velocity"] - src["velocity"]) / max_vel
            mention_delta = (dst["mentions"] - src["mentions"]) / max(1, src["mentions"])
            rot_score = vel_delta * 0.6 + _normalize(mention_delta, 0, 2) * 0.4

            if rot_score < 0.2:
                continue

            if rot_score > 0.7 and dst["phase"] == "IGNITION":
                signal = "EARLY"
            elif rot_score > 0.5:
                signal = "FORMING"
            else:
                signal = "WEAK"

            # Action for rotation
            if rot_score > 0.65 and dst["phase"] == "IGNITION":
                rot_action = "BUY"
            elif rot_score > 0.45:
                rot_action = "WATCH"
            else:
                rot_action = "AVOID"

            rotations.append({
                "from": src["name"],
                "fromKey": src["key"],
                "to": dst["name"],
                "toKey": dst["key"],
                "score": round(rot_score, 2),
                "signal": signal,
                "action": rot_action,
                "topTokens": dst["tokens"][:3],
            })

    rotations.sort(key=lambda x: -x["score"])
    return rotations[:5]


# ─── 3. FRONT-RUN DETECTOR (STRONG/EARLY/WEAK) ───────────

def detect_front_runs(scored):
    signals = []
    max_vel = max((n["velocity"] for n in scored), default=1) or 1
    avg_mentions = sum(n["mentions"] for n in scored) / max(1, len(scored))

    for n in scored:
        velocity = n["velocity"]
        mentions = n["mentions"]
        influencers = n["influencers"]

        vel_spike = _normalize(velocity / max_vel, 0.3, 1.0)
        inf_ratio = influencers / max(1, mentions)
        inf_score = _normalize(inf_ratio, 0.05, 0.4)
        low_base = 1.0 if mentions < avg_mentions * 0.6 else (0.5 if mentions < avg_mentions else 0.0)

        if n["phase"] not in ("SEEDING", "IGNITION"):
            continue

        fr_score = vel_spike * 0.4 + inf_score * 0.3 + low_base * 0.3
        if fr_score < 0.3:
            continue

        # Tighter ranking: STRONG / EARLY / WEAK
        if fr_score > 0.7:
            label = "STRONG"
        elif fr_score > 0.55:
            label = "EARLY"
        else:
            label = "WEAK"

        signals.append({
            "name": n["name"],
            "key": n["key"],
            "score": round(fr_score, 2),
            "label": label,
            "velocity": velocity,
            "mentions": mentions,
            "influencers": influencers,
            "infRatio": round(inf_ratio, 2),
            "tokens": n["tokens"][:4],
        })

    signals.sort(key=lambda x: -x["score"])
    return signals[:5]


# ─── 4. TOKEN SCORING (+ top picks) ──────────────────────

def score_tokens(scored, mentions_data):
    narr_map = {n["key"]: n for n in scored}

    # Aggregate mentions per token
    token_data = {}
    for m in mentions_data:
        token = m.get("token", "")
        if not token:
            continue
        if token not in token_data:
            token_data[token] = {"token": token, "mentions": 0, "narratives": set(),
                                 "total_reach": 0, "total_engagement": 0, "positive": 0, "total": 0}
        td = token_data[token]
        td["mentions"] += 1
        td["total"] += 1
        narr_key = m.get("narrative", "")
        if narr_key:
            td["narratives"].add(narr_key)
        td["total_reach"] += m.get("reach", 0)
        td["total_engagement"] += m.get("engagement", 0)
        if m.get("sentiment") in ("BULLISH", "positive"):
            td["positive"] += 1

    if not token_data:
        for n in scored:
            for t in n.get("tokens", []):
                if t not in token_data:
                    token_data[t] = {"token": t, "mentions": n["mentions"] // max(1, len(n["tokens"])),
                                     "narratives": {n["key"]}, "total_reach": 0, "total_engagement": 0,
                                     "positive": 0, "total": 1}
                else:
                    token_data[t]["narratives"].add(n["key"])

    max_m = max((td["mentions"] for td in token_data.values()), default=1) or 1
    results = []

    for td in token_data.values():
        best_narr, best_score = None, -1
        for nk in td["narratives"]:
            if nk in narr_map and narr_map[nk]["score"] > best_score:
                best_narr, best_score = narr_map[nk], narr_map[nk]["score"]
        if not best_narr:
            for n in scored:
                if td["token"] in n.get("tokens", []) and n["score"] > best_score:
                    best_narr, best_score = n, n["score"]
        if not best_narr:
            continue

        social = _normalize(td["mentions"], 0, max_m)
        fit = best_narr["score"]
        vel = _normalize(best_narr["velocity"], 0, 100)
        token_score = social * 0.4 + fit * 0.3 + vel * 0.3

        phase = best_narr["phase"]
        if token_score > 0.7 and phase == "IGNITION":
            action = "BUY"
        elif token_score > 0.55 and phase == "IGNITION":
            action = "WATCH"
        elif phase == "EXPANSION":
            action = "LATE"
        elif phase == "SEEDING" and token_score > 0.5:
            action = "WATCH"
        else:
            action = "AVOID"

        results.append({
            "token": td["token"],
            "score": round(token_score, 2),
            "action": action,
            "narrative": best_narr["name"],
            "narrativeKey": best_narr["key"],
            "phase": phase,
            "mentions": td["mentions"],
            "sentiment": round(td["positive"] / max(1, td["total"]), 2),
        })

    results.sort(key=lambda x: -x["score"])
    return results


# ─── 5. SMART MONEY ORIGIN ────────────────────────────────

def detect_smart_money_origin(mentions_data, scored):
    """Find who moved first — authors who mentioned tokens EARLY before narrative spike."""
    narr_map = {n["key"]: n for n in scored}

    # Group mentions by narrative
    narr_mentions = defaultdict(list)
    for m in mentions_data:
        narr_key = m.get("narrative", "")
        if narr_key and m.get("mentionedAt"):
            narr_mentions[narr_key].append(m)

    origins = []

    for narr_key, mentions in narr_mentions.items():
        narr_info = narr_map.get(narr_key)
        if not narr_info:
            continue

        # Sort by time
        sorted_m = sorted(mentions, key=lambda x: x.get("mentionedAt", datetime.max))
        if not sorted_m:
            continue

        # First 20% = early authors
        cutoff_idx = max(1, len(sorted_m) // 5)
        early = sorted_m[:cutoff_idx]
        total_mentions = len(sorted_m)

        for m in early:
            author = m.get("author", "")
            if not author:
                continue

            reach = m.get("reach", 0)
            engagement = m.get("engagement", 0)
            mentioned_at = m.get("mentionedAt")
            peak_time = sorted_m[-1].get("mentionedAt")

            # earlyTiming: how early relative to peak
            if mentioned_at and peak_time and peak_time > mentioned_at:
                time_range = (peak_time - mentioned_at).total_seconds()
                early_timing = min(1.0, time_range / (86400 * 3))  # normalize to 3 days
            else:
                early_timing = 0.5

            # postImpact: what fraction of mentions came after this author
            author_idx = sorted_m.index(m)
            post_impact = (total_mentions - author_idx - 1) / max(1, total_mentions)

            # influenceWeight
            inf_weight = _normalize(math.log10(max(1, reach)), 3, 6)

            # First mover score
            fm_score = early_timing * 0.4 + post_impact * 0.4 + inf_weight * 0.2

            if fm_score > 0.75:
                label = "FIRST"
            elif fm_score > 0.6:
                label = "EARLY"
            else:
                label = "NOISE"

            if label == "NOISE":
                continue

            origins.append({
                "author": author,
                "narrative": narr_info["name"],
                "narrativeKey": narr_key,
                "score": round(fm_score, 2),
                "label": label,
                "reach": reach,
                "engagement": engagement,
                "token": m.get("token", ""),
                "timing": round(early_timing, 2),
                "impact": round(post_impact, 2),
            })

    # Deduplicate: keep best score per author
    best_per_author = {}
    for o in origins:
        key = o["author"]
        if key not in best_per_author or o["score"] > best_per_author[key]["score"]:
            best_per_author[key] = o

    result = sorted(best_per_author.values(), key=lambda x: -x["score"])
    return result[:10]


# ─── 6. TRADE SETUP (synthesized top opportunity) ─────────

def compute_trade_setup(scored, rotations, front_runs, tokens):
    """Synthesize all signals into ONE clear recommendation."""
    # Find the best narrative (highest score + IGNITION)
    best_narr = None
    for n in scored:
        if n["phase"] == "IGNITION" and (not best_narr or n["score"] > best_narr["score"]):
            best_narr = n

    if not best_narr:
        for n in scored:
            if not best_narr or n["score"] > best_narr["score"]:
                best_narr = n

    if not best_narr:
        return None

    # Find relevant rotation
    active_rotation = None
    for r in rotations:
        if r["toKey"] == best_narr["key"]:
            active_rotation = r
            break

    # Find relevant front-run
    active_frontrun = None
    for f in front_runs:
        if f["key"] == best_narr["key"]:
            active_frontrun = f
            break

    # Top tokens for this narrative (fallback to global top picks if empty)
    top_tokens = [t for t in tokens if t.get("narrativeKey") == best_narr["key"] and t["action"] in ("BUY", "WATCH")][:5]
    if not top_tokens:
        top_tokens = [t for t in tokens if t.get("narrativeKey") == best_narr["key"]][:3]
    if not top_tokens:
        # Fallback: use global top BUY tokens
        top_tokens = [t for t in tokens if t["action"] in ("BUY", "WATCH")][:5]

    # Determine setup action
    has_rotation = active_rotation is not None and active_rotation["signal"] in ("EARLY", "FORMING")
    has_frontrun = active_frontrun is not None and active_frontrun["label"] in ("STRONG", "EARLY")

    if best_narr["action"] == "BUY EARLY" and (has_rotation or has_frontrun):
        setup_action = "BUY EARLY"
    elif best_narr["action"] in ("BUY EARLY", "WATCH"):
        setup_action = "WATCH"
    else:
        setup_action = "AVOID"

    return {
        "narrative": best_narr["name"],
        "narrativeKey": best_narr["key"],
        "phase": best_narr["phase"],
        "score": best_narr["score"],
        "action": setup_action,
        "rotation": {"from": active_rotation["from"], "signal": active_rotation["signal"]} if active_rotation else None,
        "frontRun": active_frontrun["label"] if active_frontrun else None,
        "tokens": [{"token": t["token"], "score": t["score"], "action": t["action"]} for t in top_tokens],
    }


# ─── MAIN PIPELINE ────────────────────────────────────────

def run_narrative_flow():
    raw = _load_narratives()
    mentions = _load_narrative_mentions()

    scored = compute_narrative_scores(raw)
    rotations = detect_rotations(scored)
    front_runs = detect_front_runs(scored)
    tokens = score_tokens(scored, mentions)
    origins = detect_smart_money_origin(mentions, scored)
    setup = compute_trade_setup(scored, rotations, front_runs, tokens)

    # Top picks = top 3 BUY tokens
    top_picks = [t for t in tokens if t["action"] == "BUY"][:3]

    return {
        "ok": True,
        "tradeSetup": setup,
        "narratives": scored,
        "rotations": rotations,
        "frontRuns": front_runs,
        "topPicks": top_picks,
        "tokens": tokens,
        "origins": origins,
    }
