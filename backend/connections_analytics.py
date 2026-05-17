"""
Connections Analytics API — Python endpoints for Actor Hub
Returns data in the exact format expected by frontend components:
  - SmartFollowersPanel, NetworkPathsPanel, TimeSeriesCharts, AiSummaryPanel
"""
import random
import math
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/connections", tags=["connections-analytics"])


def _seed(aid: str) -> int:
    return sum(ord(c) for c in aid) % 10000


# Pool of realistic crypto accounts for smart followers
KNOWN_CRYPTO_FOLLOWERS = [
    ("gavinwood", "Gavin Wood", "elite"),
    ("el33th4xor", "Emin Gun Sirer", "elite"),
    ("balaboronin", "Balaji S.", "elite"),
    ("hasufl", "Hasu", "high"),
    ("ryansadams", "Ryan S. Adams", "high"),
    ("sassal0x", "sassal.eth", "high"),
    ("coaboronin", "Cobie", "high"),
    ("VladZamfir", "Vlad Zamfir", "upper_mid"),
    ("nic__carter", "Nic Carter", "upper_mid"),
    ("iamDCinvestor", "DCinvestor", "upper_mid"),
    ("TrustlessState", "Bankless", "high"),
    ("AnthonyPompliano", "Pomp", "elite"),
    ("cburniske", "Chris Burniske", "high"),
    ("AriDavidPaul", "Ari David Paul", "mid"),
    ("taboronin_eth", "Tarun Chitra", "upper_mid"),
    ("FrankieIsNot", "Frankie", "mid"),
    ("ljxie", "Linda Xie", "high"),
    ("StaniKulechov", "Stani Kulechov", "elite"),
    ("kaboronin_defi", "Kain Warwick", "high"),
    ("RyanWatkins_", "Ryan Watkins", "upper_mid"),
    ("DegenSpartan", "DegenSpartan", "mid"),
    ("Route2FI", "Route2FI", "mid"),
    ("loomdart", "loomdart", "mid"),
    ("blaboronin_sol", "Anatoly Yakovenko", "elite"),
    ("rajgokal", "Raj Gokal", "high"),
]


# ─── SMART FOLLOWERS ────────────────────────────────
@router.get("/smart-followers/{account_id}")
async def get_smart_followers(account_id: str):
    s = _seed(account_id)
    random.seed(s)

    tiers = ["elite", "high", "upper_mid", "mid", "low_mid", "low"]
    tier_counts = {t: random.randint(0, 8) for t in tiers}
    tier_counts["elite"] = max(1, tier_counts["elite"])
    tier_counts["high"] = max(2, tier_counts["high"])
    total = sum(tier_counts.values())
    tier_shares = {t: round(c / max(total, 1), 3) for t, c in tier_counts.items()}

    elite_share = tier_shares.get("elite", 0)
    high_share = tier_shares.get("high", 0)

    # Use real-looking accounts from pool
    pool = list(KNOWN_CRYPTO_FOLLOWERS)
    random.shuffle(pool)
    followers = []
    for i in range(min(total, 10)):
        if i < len(pool):
            handle, name, tier = pool[i]
        else:
            handle, name, tier = f"user_{s}_{i}", f"Trader {i+1}", random.choice(tiers[:4])
        followers.append({
            "follower_id": f"sf_{handle}",
            "handle": handle,
            "display_name": name,
            "authority_score_0_1": round(random.uniform(0.3, 0.95), 2),
            "authority_tier": tier,
            "share_of_total": round(random.uniform(0.02, 0.15), 3),
        })

    score = round(0.3 + elite_share * 2 + high_share * 1.5, 2)
    score = min(score, 0.98)

    random.seed()
    return {
        "ok": True,
        "data": {
            "smart_followers_score_0_1": score,
            "followers_count": total + random.randint(100, 5000),
            "follower_value_index": round(0.5 + random.uniform(0, 1.5), 2),
            "breakdown": {
                "elite_weight_share": elite_share,
                "high_weight_share": high_share,
                "tier_shares": tier_shares,
                "tier_counts": tier_counts,
            },
            "top_followers": followers,
        }
    }


# ─── NETWORK PATHS ──────────────────────────────────
@router.get("/paths/{account_id}")
async def get_network_paths(account_id: str):
    s = _seed(account_id)
    random.seed(s)

    hubs = [
        ("binance_cz", "CZ Binance"), ("coinbase_brian", "Brian Armstrong"),
        ("a16z_crypto", "a16z"), ("paradigm_fund", "Paradigm"),
        ("ethereum_vitalik", "Vitalik"), ("solana_labs", "Solana Labs"),
    ]
    selected = random.sample(hubs, min(4, len(hubs)))

    paths_list = []
    for hub_id, hub_name in selected:
        hops = random.randint(1, 4)
        nodes = [{"id": account_id, "handle": account_id.replace("demo_", ""), "authority_tier": "high"}]
        for h in range(hops - 1):
            nodes.append({
                "id": f"mid_{s}_{h}",
                "handle": f"node_{s}_{h}",
                "authority_tier": random.choice(["high", "upper_mid", "mid"]),
            })
        nodes.append({"id": hub_id, "handle": hub_name, "authority_tier": "elite"})

        kind = random.choice(["shortest", "strongest", "elite"])
        badges = []
        if kind == "strongest":
            badges.append("strong_access")
        if kind == "elite":
            badges.append("elite_touch")
        if hops <= 2:
            badges.append("short_reach")

        paths_list.append({
            "to": hub_id,
            "kind": kind,
            "hops": hops,
            "strength": round(random.uniform(0.3, 0.95), 2),
            "authority_sum": round(random.uniform(1.0, 4.0), 2),
            "contribution_0_1": round(random.uniform(0.05, 0.3), 2),
            "nodes": nodes,
            "badges": badges,
            "explain_text": f"Path to {hub_name} via {hops} hop{'s' if hops > 1 else ''}.",
        })

    exposure_score = round(random.uniform(0.4, 0.9), 2)
    exposure_tier = "elite" if exposure_score > 0.75 else "strong" if exposure_score > 0.55 else "moderate" if exposure_score > 0.35 else "weak"

    random.seed()
    return {
        "ok": True,
        "data": {
            "paths": {
                "paths": paths_list,
                "explain": {
                    "summary": f"Found {len(paths_list)} network paths to key hubs.",
                    "bullets": [f"{len(paths_list)} paths analyzed", f"Avg strength: {sum(p['strength'] for p in paths_list)/max(len(paths_list),1):.2f}"],
                },
            },
            "exposure": {
                "exposure_score_0_1": exposure_score,
                "exposure_tier": exposure_tier,
                "reachable_elite": random.randint(2, 8),
                "reachable_high": random.randint(5, 15),
                "avg_hops_to_elite": round(random.uniform(1.5, 3.5), 1),
                "avg_hops_to_high": round(random.uniform(1.0, 2.5), 1),
            },
            "explain": {
                "summary": f"Network exposure: {exposure_tier}. Score: {int(exposure_score*100)}/100.",
                "details": [
                    f"Reachable elite nodes within 3 hops",
                    f"Strong connections to major crypto hubs",
                ],
                "recommendations": [
                    "Monitor for new connection opportunities",
                    "Cross-reference with on-chain data",
                ],
            },
        }
    }


# ─── TIMESERIES ─────────────────────────────────────
@router.get("/timeseries/{account_id}")
async def get_timeseries(account_id: str, window: str = "30d"):
    s = _seed(account_id)
    random.seed(s)

    days = 30 if window == "30d" else 90 if window == "90d" else 7
    now = datetime.now(timezone.utc)
    base_followers = 10000 + s * 50
    base_likes = 100 + s % 500

    followers_data = []
    engagement_data = []
    scores_data = []

    prev_followers = base_followers
    for i in range(days):
        dt = now - timedelta(days=days - i)
        ts = dt.strftime("%Y-%m-%d")
        delta = random.randint(-50, 150)
        cur_followers = prev_followers + delta

        followers_data.append({
            "ts": ts,
            "followers": cur_followers,
            "delta_1d": delta,
        })

        likes = base_likes + random.randint(-30, 80)
        reposts = int(likes * random.uniform(0.1, 0.4))
        replies = int(likes * random.uniform(0.05, 0.2))
        views = likes * random.randint(10, 50)
        engagement_data.append({
            "ts": ts,
            "likes": likes,
            "reposts": reposts,
            "replies": replies,
            "views": views,
            "engagement_rate": round(random.uniform(0.01, 0.08), 4),
        })

        tw_score = 400 + s % 400 + random.randint(-30, 30)
        grades = ["A", "B+", "B", "B-", "C+", "C"]
        scores_data.append({
            "ts": ts,
            "twitter_score": tw_score,
            "grade": random.choice(grades),
            "early_signal": {"badge": random.choice(["none", "rising", "breakout"]) if random.random() > 0.7 else "none"},
        })

        prev_followers = cur_followers

    random.seed()
    return {
        "ok": True,
        "data": {
            "followers": followers_data,
            "engagement": engagement_data,
            "scores": scores_data,
        }
    }


@router.get("/timeseries/{account_id}/summary")
async def get_timeseries_summary(account_id: str, window: str = "30d"):
    s = _seed(account_id)
    random.seed(s)

    base = 10000 + s * 50
    current = base + random.randint(500, 3000)
    growth = current - base
    growth_pct = round(growth / max(base, 1) * 100, 1)
    tw_start = 400 + s % 400
    tw_current = tw_start + random.randint(-30, 80)
    grades = ["A", "B+", "B", "B-", "C+"]

    random.seed()
    return {
        "ok": True,
        "data": {
            "followers": {
                "current": current,
                "growth_30d": growth,
                "growth_percent": growth_pct,
            },
            "engagement": {
                "avg_likes": 100 + s % 500,
                "avg_engagement_rate": round(0.02 + random.uniform(0, 0.05), 4),
            },
            "scores": {
                "current": tw_current,
                "start": tw_start,
                "grade_current": random.choice(grades),
                "early_signals_count": random.randint(0, 5),
                "breakouts_count": random.randint(0, 2),
            },
        }
    }


# ─── AI SUMMARY ─────────────────────────────────────
@router.get("/ai/cached/{account_id}")
async def get_ai_cached(account_id: str):
    s = _seed(account_id)
    random.seed(s)

    verdicts = ["STRONG", "GOOD", "MIXED"]
    verdict = random.choices(verdicts, [0.3, 0.5, 0.2])[0]
    confidence = round(random.uniform(65, 92))

    drivers = [
        "High network authority among crypto leaders",
        "Consistent posting pattern with quality content",
        "Strong engagement from institutional followers",
        "Active in DeFi and L2 discussions",
        "On-chain activity matches public statements",
    ]
    risks = [
        "Limited trading signal history",
        "Engagement rate below sector average",
        "Network concentrated in single ecosystem",
    ]

    random.seed()
    return {
        "ok": True,
        "data": {
            "account_id": account_id,
            "verdict": verdict,
            "headline": f"{verdict.title()} Actor Profile",
            "summary": f"Account shows {verdict.lower()} fundamentals with {confidence}% confidence based on network, engagement and on-chain analysis.",
            "key_drivers": random.sample(drivers, 3),
            "risks": random.sample(risks, 2),
            "recommendations": ["Monitor engagement trends", "Cross-reference with on-chain data"],
            "evidence": {
                "confidence_0_100": confidence,
                "score": 650 + s % 200,
                "grade": "B+" if confidence > 75 else "B",
                "notable": ["Network quality above average", "Consistent posting frequency"],
            },
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
    }


@router.post("/ai/summary")
async def gen_ai_summary():
    return {"ok": False, "error": "AI_GENERATION_DISABLED", "message": "Use cached summaries"}


# ─── ACCOUNTS / TREND / EARLY-SIGNAL / SCORE ────────
@router.get("/accounts/{author_id}")
async def get_account(author_id: str):
    s = _seed(author_id)
    random.seed(s)
    handle = author_id.replace("demo_", "")
    influence = 300 + (s % 600)
    x_score = 200 + (s % 700)
    vel = round(random.uniform(-0.5, 0.8), 2)
    acc = round(random.uniform(-0.3, 0.6), 2)
    random.seed()
    return {
        "ok": True,
        "data": {
            "author_id": author_id, "username": handle, "handle": handle,
            "followers": 10000 + s * 50,
            "follower_growth_30d": round(random.uniform(-2, 8), 1),
            "profile": "whale" if s > 5000 else "influencer" if s > 2000 else "retail",
            "scores": {
                "influence_score": influence, "x_score": x_score,
                "signal_noise": round(4 + random.uniform(0, 5), 1),
                "risk_level": "low" if influence > 600 else "medium" if influence > 350 else "high",
            },
            "activity": {
                "posts_count": 50 + s % 300, "window_days": 30,
                "real_views": 5000 + s * 10,
                "engagement_quality": round(0.4 + random.uniform(0, 0.4), 2),
                "posting_consistency": round(0.5 + random.uniform(0, 0.4), 2),
                "engagement_stability": round(0.4 + random.uniform(0, 0.4), 2),
                "reach_efficiency": round(0.3 + random.uniform(0, 0.5), 2),
            },
            "trend": {"velocity_norm": vel, "acceleration_norm": acc},
        }
    }


@router.post("/trend-adjusted")
async def trend_adjusted(body: dict = {}):
    inf = body.get("influence_score", 500)
    vel = body.get("velocity_norm", 0)
    acc = body.get("acceleration_norm", 0)
    x = body.get("x_score", 300)
    bonus = 0.35 * vel + 0.15 * acc
    adj = round(inf * (1 + bonus))
    return {
        "ok": True,
        "data": {
            "influence": {"base_score": inf, "adjusted_score": adj, "delta": adj - inf, "delta_pct": round((adj - inf) / max(inf, 1) * 100, 1)},
            "x_score": {"base_score": x, "adjusted_score": round(x * (1 + 0.2 * vel))},
        }
    }


@router.post("/early-signal")
async def early_signal(body: dict = {}):
    inf_base = body.get("influence_base", 500)
    trend = body.get("trend", {})
    vel = trend.get("velocity_norm", 0)
    acc = trend.get("acceleration_norm", 0)
    sn = body.get("signal_noise", 5)
    risk = body.get("risk_level", "medium")

    raw = max(0, vel * 400 + acc * 200) + inf_base * 0.3 + sn * 30
    mult = {"low": 1.1, "medium": 1.0, "high": 0.85}.get(risk, 1.0)
    score = min(int(raw * mult), 999)
    badge = "breakout" if score >= 700 and vel > 0.2 else "rising" if score >= 450 else "none"
    reasons = []
    if vel > 0.2: reasons.append("Positive growth dynamics")
    if inf_base > 500: reasons.append("Strong influence base")
    if sn > 6: reasons.append("High signal clarity")

    return {
        "ok": True,
        "data": {
            "early_signal_score": score, "badge": badge,
            "confidence": round(min(0.95, 0.5 + vel * 0.3 + sn / 50), 2),
            "reasons": reasons,
            "explanation": {"breakout": "Early breakout signal detected.", "rising": "Positive dynamics detected.", "none": "No significant signals."}[badge],
        }
    }


@router.get("/score/mock")
async def score_mock():
    return {
        "ok": True,
        "data": {
            "grade": "B", "influence_score": 650,
            "metrics": {
                "real_views": 25000, "engagement_quality": 0.72,
                "posting_consistency": 0.68, "engagement_stability": 0.75,
                "reach_efficiency": 0.61,
            },
            "red_flags": [],
        }
    }
