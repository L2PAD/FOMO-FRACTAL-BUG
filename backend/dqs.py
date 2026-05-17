"""
Data Quality Score (DQS) — production formula.
Each signal sample gets a quality score 0→1.
Used as sample_weight during training.
"""

import math


def clip(x, a=0.0, b=1.0):
    return max(a, min(b, float(x) if x is not None else 0.0))


def norm_ret(x):
    """Normalize return: 5% = max impact."""
    return clip(abs(float(x or 0)) / 0.05)


def freshness_score(sec):
    """Exponential decay: 5min = top, tau=10min."""
    sec = float(sec or 600)
    return math.exp(-sec / 600)


def compute_dqs(row):
    """
    Compute Data Quality Score for a dataset v3 row.
    Returns float 0→1.
    """
    actor = row.get("actor", {})
    market = row.get("market", {})
    sentiment = row.get("sentiment", {})
    signal = row.get("signal", {})

    # Actor quality (30%)
    actor_q = (
        clip(actor.get("score", 0)) * 0.4
        + clip(actor.get("hit_rate", 0)) * 0.3
        + clip(actor.get("early_ratio", 0)) * 0.3
    )

    # Price impact (25%) — uses rel_ret.h1
    rel_ret = market.get("rel_ret", {})
    price_impact = norm_ret(rel_ret.get("h1", 0))

    # Sentiment quality (20%)
    sentiment_q = clip(sentiment.get("confidence", 0))

    # Uniqueness (10%) — high coordination = more duplicates = lower uniqueness
    coordination = clip(signal.get("coordination", 0))
    uniqueness = clip(1 - coordination * 0.5)

    # Freshness (15%)
    fresh = freshness_score(signal.get("freshness_sec", 600))

    dqs = (
        actor_q * 0.30
        + price_impact * 0.25
        + sentiment_q * 0.20
        + uniqueness * 0.10
        + fresh * 0.15
    )

    return round(clip(dqs), 4)


def dqs_bucket(dqs):
    if dqs >= 0.7:
        return "HIGH"
    elif dqs >= 0.4:
        return "MEDIUM"
    return "LOW"
