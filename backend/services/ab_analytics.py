"""
A/B Test Analytics Engine — Cross-references experiment variants with conversion funnel.

Three active mobile experiments:
  TEST #1 (CTA): 4 variants of paywall button text (A/B/C/D)
  TEST #2 (Early Paywall): Control vs 3 paywall positions (A/B/C/D)
  TEST #3 (Truth Line): 4 variants of social proof text (A/B/C/D)

Variant assignment is deterministic (hash-based), so we can retroactively
compute which variant any user was in.

Key metric: conversion rate per variant at each funnel stage.
Winner = variant with highest paywall_seen→cta_clicked conversion.
"""
import hashlib
import logging
import os
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient, DESCENDING

logger = logging.getLogger(__name__)

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "fomo_mobile")
client = MongoClient(MONGO_URL)
db = client[DB_NAME]

VARIANTS = ["A", "B", "C", "D"]

FUNNEL_STEPS = [
    "seen_telegram",
    "opened_app",
    "viewed_signal",
    "opened_detail",
    "paywall_seen",
    "cta_clicked",
    "converted",
]

# Same hash logic as signals.py
def _user_hash(user_id: str) -> int:
    return int(hashlib.md5((user_id or "dev").encode()).hexdigest(), 16)


def _get_cta_variant(user_id: str) -> str:
    """TEST #1: CTA button text variant"""
    h = _user_hash(user_id)
    idx = (h >> 4) % 4
    return chr(65 + idx)


def _get_early_paywall_variant(user_id: str) -> str:
    """TEST #2: Early Paywall position variant"""
    h = _user_hash(user_id)
    idx = (h >> 8) % 4
    return chr(65 + idx)


def _get_truth_variant(user_id: str) -> str:
    """TEST #3: Truth/social proof text variant"""
    h = _user_hash(user_id)
    idx = h % 4
    return chr(65 + idx)


CTA_LABELS = {
    "A": "Unlock exact entry",
    "B": "See exact buy level",
    "C": "Enter before the move",
    "D": "Get entry, target & stop",
}

EARLY_PAYWALL_LABELS = {
    "A": "Control (no early paywall)",
    "B": "Early + entry info",
    "C": "Early + urgency",
    "D": "Early + social proof",
}

TRUTH_LABELS = {
    "A": "Last similar setup: +X%",
    "B": "N of M similar setups profitable",
    "C": "Similar setups avg + win rate",
    "D": "Top traders entered earlier",
}


def get_ab_test_stats(hours: int = 720) -> dict:
    """
    Full A/B test analytics — cross-references variants with funnel data.

    Returns per-test, per-variant:
      - users (count)
      - funnel step counts
      - conversion rates between steps
      - winner recommendation
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    cutoff_filter = {"createdAt": {"$gte": cutoff}}

    total = db.conversion_funnel.count_documents(cutoff_filter)
    if total == 0:
        cutoff_filter = {}
        total = db.conversion_funnel.count_documents({})

    if total == 0:
        return {
            "totalUsers": 0,
            "period": f"last_{hours}h",
            "tests": {},
            "recommendation": "No funnel data yet — drive traffic to collect A/B test results",
        }

    # Fetch all funnel docs
    funnels = list(db.conversion_funnel.find(cutoff_filter, {"_id": 0}))

    # Build per-test analytics
    tests = {
        "cta": _analyze_test("CTA Button Text", funnels, _get_cta_variant, CTA_LABELS),
        "early_paywall": _analyze_test("Early Paywall Position", funnels, _get_early_paywall_variant, EARLY_PAYWALL_LABELS),
        "truth_line": _analyze_test("Truth / Social Proof Text", funnels, _get_truth_variant, TRUTH_LABELS),
    }

    # Overall recommendation
    recommendations = []
    for test_key, test_data in tests.items():
        winner = test_data.get("winner")
        if winner and winner.get("variant"):
            label = test_data["variants"].get(winner["variant"], {}).get("label", "")
            recommendations.append(
                f"{test_data['name']}: Variant {winner['variant']} ({label}) — "
                f"{winner.get('metric', 'N/A')} conversion: {winner.get('rate', 0)}%"
            )
        else:
            recommendations.append(f"{test_data['name']}: Not enough data for winner")

    return {
        "totalUsers": total,
        "period": f"last_{hours}h",
        "tests": tests,
        "recommendations": recommendations,
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }


def _analyze_test(name: str, funnels: list, variant_fn, labels: dict) -> dict:
    """Analyze a single A/B test across all funnel users."""
    # Group funnels by variant
    variant_data = {v: [] for v in VARIANTS}
    for f in funnels:
        uid = f.get("userId", "")
        variant = variant_fn(uid)
        variant_data[variant].append(f)

    # Calculate metrics per variant
    variants = {}
    best_cta_rate = -1
    best_cta_variant = None
    best_paywall_rate = -1
    best_paywall_variant = None

    for v in VARIANTS:
        docs = variant_data[v]
        n = len(docs)

        steps = {}
        for step in FUNNEL_STEPS:
            count = sum(1 for d in docs if d.get("events", {}).get(step, False))
            steps[step] = count

        # Key conversion rates
        viewed = steps.get("viewed_signal", 0)
        opened = steps.get("opened_detail", 0)
        paywall = steps.get("paywall_seen", 0)
        clicked = steps.get("cta_clicked", 0)
        converted = steps.get("converted", 0)

        # viewed → opened_detail rate
        view_to_detail = round(opened / max(viewed, 1) * 100, 1)
        # opened_detail → paywall_seen rate
        detail_to_paywall = round(paywall / max(opened, 1) * 100, 1)
        # paywall_seen → cta_clicked rate (KEY METRIC)
        paywall_to_cta = round(clicked / max(paywall, 1) * 100, 1)
        # cta_clicked → converted rate
        cta_to_converted = round(converted / max(clicked, 1) * 100, 1)
        # Overall: viewed → converted
        overall = round(converted / max(viewed, 1) * 100, 1)

        variants[v] = {
            "label": labels.get(v, f"Variant {v}"),
            "users": n,
            "funnelCounts": steps,
            "rates": {
                "viewToDetail": view_to_detail,
                "detailToPaywall": detail_to_paywall,
                "paywallToCta": paywall_to_cta,
                "ctaToConverted": cta_to_converted,
                "overall": overall,
            },
        }

        # Track best CTA conversion
        if paywall > 0 and paywall_to_cta > best_cta_rate:
            best_cta_rate = paywall_to_cta
            best_cta_variant = v

        if viewed > 0 and detail_to_paywall > best_paywall_rate:
            best_paywall_rate = detail_to_paywall
            best_paywall_variant = v

    # Determine winner based on test type
    if "CTA" in name:
        winner_variant = best_cta_variant
        winner_metric = "paywallToCta"
        winner_rate = best_cta_rate
    elif "Paywall" in name:
        winner_variant = best_paywall_variant
        winner_metric = "detailToPaywall"
        winner_rate = best_paywall_rate
    else:
        # Truth line → impact on overall CTA clicks
        winner_variant = best_cta_variant
        winner_metric = "paywallToCta"
        winner_rate = best_cta_rate

    total_users = sum(len(variant_data[v]) for v in VARIANTS)
    min_sample = 5  # minimum per variant to declare winner

    has_enough_data = all(len(variant_data[v]) >= min_sample for v in VARIANTS)

    winner = None
    if winner_variant and has_enough_data:
        winner = {
            "variant": winner_variant,
            "metric": winner_metric,
            "rate": winner_rate,
            "confidence": "HIGH" if total_users >= 50 else "MEDIUM" if total_users >= 20 else "LOW",
        }
    elif winner_variant:
        winner = {
            "variant": winner_variant,
            "metric": winner_metric,
            "rate": winner_rate,
            "confidence": "INSUFFICIENT_DATA",
            "note": f"Need {min_sample}+ users per variant. Current: {[len(variant_data[v]) for v in VARIANTS]}",
        }

    return {
        "name": name,
        "totalUsers": total_users,
        "variants": variants,
        "winner": winner,
    }


def get_funnel_with_variants(hours: int = 720) -> dict:
    """
    Enhanced funnel stats with A/B variant breakdown at each step.
    Shows WHERE in the funnel each variant performs differently.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    cutoff_filter = {"createdAt": {"$gte": cutoff}}

    total = db.conversion_funnel.count_documents(cutoff_filter)
    if total == 0:
        cutoff_filter = {}
        total = db.conversion_funnel.count_documents({})

    funnels = list(db.conversion_funnel.find(cutoff_filter, {"_id": 0}))

    # Build step-by-step variant breakdown
    step_variants = {}
    for step in FUNNEL_STEPS:
        step_variants[step] = {
            "total": 0,
            "byCtaVariant": {v: 0 for v in VARIANTS},
            "byEarlyPaywallVariant": {v: 0 for v in VARIANTS},
        }

    for f in funnels:
        uid = f.get("userId", "")
        cta_v = _get_cta_variant(uid)
        ep_v = _get_early_paywall_variant(uid)

        for step in FUNNEL_STEPS:
            if f.get("events", {}).get(step, False):
                step_variants[step]["total"] += 1
                step_variants[step]["byCtaVariant"][cta_v] += 1
                step_variants[step]["byEarlyPaywallVariant"][ep_v] += 1

    # Compute drop-off per variant
    dropoffs = []
    for i in range(1, len(FUNNEL_STEPS)):
        prev_step = FUNNEL_STEPS[i - 1]
        curr_step = FUNNEL_STEPS[i]
        prev_total = step_variants[prev_step]["total"]
        curr_total = step_variants[curr_step]["total"]

        variant_drops = {}
        for v in VARIANTS:
            prev_v = step_variants[prev_step]["byCtaVariant"][v]
            curr_v = step_variants[curr_step]["byCtaVariant"][v]
            drop = prev_v - curr_v
            rate = round(drop / max(prev_v, 1) * 100, 1) if prev_v > 0 else 0
            variant_drops[v] = {"lost": drop, "dropRate": rate}

        dropoffs.append({
            "from": prev_step,
            "to": curr_step,
            "totalLost": prev_total - curr_total,
            "totalDropRate": round((prev_total - curr_total) / max(prev_total, 1) * 100, 1),
            "byCtaVariant": variant_drops,
        })

    # Intent breakdown
    intent_stats = {}
    for level in ["COLD", "WARM", "HOT", "VERY_HOT"]:
        level_funnels = [f for f in funnels if f.get("intent") == level]
        converted = sum(1 for f in level_funnels if f.get("events", {}).get("converted", False))
        cta_clicked = sum(1 for f in level_funnels if f.get("events", {}).get("cta_clicked", False))
        intent_stats[level] = {
            "total": len(level_funnels),
            "ctaClicked": cta_clicked,
            "converted": converted,
            "conversionRate": round(converted / max(len(level_funnels), 1) * 100, 1),
        }

    return {
        "period": f"last_{hours}h",
        "totalFunnels": total,
        "steps": step_variants,
        "dropoffs": dropoffs,
        "intentBreakdown": intent_stats,
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }


def get_analytics_dashboard(hours: int = 720) -> dict:
    """
    Full analytics dashboard — combines funnel, A/B tests, intent, shadow trades.
    Single endpoint for complete conversion intelligence.
    """
    from services.conversion_funnel import get_funnel_stats
    from services.shadow_service import get_shadow_stats

    funnel = get_funnel_stats(hours)
    ab_tests = get_ab_test_stats(hours)
    funnel_variants = get_funnel_with_variants(hours)
    shadow = get_shadow_stats()

    # Behavior events summary
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    behavior_total = db.behavior_events.count_documents({"createdAt": {"$gte": cutoff}})

    # Event type distribution
    pipeline = [
        {"$match": {"createdAt": {"$gte": cutoff}}},
        {"$group": {"_id": "$type", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 15},
    ]
    event_dist = {doc["_id"]: doc["count"] for doc in db.behavior_events.aggregate(pipeline)}

    # Unique users
    unique_users = len(db.behavior_events.distinct("userId", {"createdAt": {"$gte": cutoff}}))

    # Telegram sequences
    sequences_total = db.telegram_sequences.count_documents({})
    sequences_fired = db.telegram_sequences.count_documents({"fired": True})
    sequences_pending = db.telegram_sequences.count_documents({"fired": False})

    return {
        "period": f"last_{hours}h",
        "overview": {
            "totalFunnelEntries": funnel.get("totalFunnels", 0),
            "totalBehaviorEvents": behavior_total,
            "uniqueUsers": unique_users,
            "shadowTrades": shadow.get("totalTrades", 0),
            "shadowWinRate": shadow.get("winRate", 0),
            "shadowAvgPnl": shadow.get("avgPnl", 0),
        },
        "funnel": funnel,
        "funnelVariants": funnel_variants,
        "abTests": ab_tests,
        "behaviorDistribution": event_dist,
        "intent": funnel_variants.get("intentBreakdown", {}),
        "telegramSequences": {
            "total": sequences_total,
            "fired": sequences_fired,
            "pending": sequences_pending,
        },
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }
