"""
Catalyst Feature Builder — extracts probability axes from related events.

7 axes:
  1. official_signal_score
  2. source_credibility_score
  3. narrative_pressure_score
  4. timeline_pressure_score
  5. readiness_score
  6. precedent_score
  7. blocker_penalty / contradiction_score
"""
from datetime import datetime, timezone


OFFICIAL_SOURCES = {
    "sec", "blackrock", "fidelity", "grayscale", "coinbase", "binance", "official",
}

POSITIVE_TERMS = [
    "approved", "approval", "filed", "filing", "confirmed",
    "launch confirmed", "mainnet live", "listing confirmed",
    "roadmap complete", "deployed", "submitted", "accepted",
]

NEGATIVE_TERMS = [
    "rejected", "delay", "delayed", "postponed", "denied",
    "lawsuit", "blocked", "regulatory pressure", "issue",
    "exploit", "hack", "not approved", "not filed",
]


def build(decoded: dict, related_events: list[dict]) -> dict:
    """Build catalyst feature vector from decoded market and related events."""
    official_signal_count = 0
    high_quality_signal_count = 0
    blocker_count = 0

    weighted_quality = 0.0
    narrative_pressure = 0.0
    contradiction = 0.0

    for e in related_events:
        text = f"{e.get('title', '')} {e.get('text', '')}".lower()
        rel = e.get("relevance_score", 0.5)
        sq = e.get("source_quality", 0.5)

        weighted_quality += sq * rel

        src = e.get("source", "").lower()
        stype = e.get("source_type", "").lower()
        if src in OFFICIAL_SOURCES or stype == "official":
            official_signal_count += 1

        if sq >= 0.75 and rel >= 0.65:
            high_quality_signal_count += 1

        pos_hits = sum(1 for t in POSITIVE_TERMS if t in text)
        neg_hits = sum(1 for t in NEGATIVE_TERMS if t in text)

        if pos_hits > 0:
            narrative_pressure += min(0.15, 0.03 * pos_hits) * sq
        if neg_hits > 0:
            blocker_count += 1
            contradiction += min(0.18, 0.04 * neg_hits) * sq

    total = max(1, len(related_events))
    avg_quality = weighted_quality / total
    signal_density = min(1.0, len(related_events) / 12.0)

    official_signal_score = min(1.0, official_signal_count * 0.22)
    source_credibility_score = min(1.0, avg_quality)
    narrative_pressure_score = min(1.0, narrative_pressure + signal_density * 0.15)
    timeline_pressure_score = _timeline_pressure(decoded.get("deadline"))
    readiness_score = _readiness_score(decoded, related_events)
    precedent_score = _precedent_score(decoded)
    blocker_penalty = min(1.0, contradiction)

    return {
        "official_signal_score": round(official_signal_score, 4),
        "source_credibility_score": round(source_credibility_score, 4),
        "narrative_pressure_score": round(narrative_pressure_score, 4),
        "timeline_pressure_score": round(timeline_pressure_score, 4),
        "readiness_score": round(readiness_score, 4),
        "precedent_score": round(precedent_score, 4),
        "blocker_penalty": round(blocker_penalty, 4),
        "contradiction_score": round(min(1.0, contradiction), 4),
        "signal_density": round(signal_density, 4),
        "high_quality_signal_count": high_quality_signal_count,
        "official_signal_count": official_signal_count,
        "blocker_count": blocker_count,
    }


def _timeline_pressure(deadline) -> float:
    if not deadline:
        return 0.25
    try:
        if isinstance(deadline, str):
            dt = datetime.fromisoformat(deadline.replace("Z", "+00:00"))
        else:
            dt = deadline
        days_left = max(0, (dt - datetime.now(timezone.utc)).days)
        if days_left <= 3:
            return 0.90
        if days_left <= 7:
            return 0.75
        if days_left <= 14:
            return 0.58
        if days_left <= 30:
            return 0.42
        return 0.25
    except Exception:
        return 0.25


def _readiness_score(decoded: dict, events: list[dict]) -> float:
    payload = " ".join(f"{e.get('title','')} {e.get('text','')}" for e in events).lower()
    etype = decoded.get("event_type", "")

    if etype == "etf_catalyst":
        score = 0.0
        if "filed" in payload or "filing" in payload:
            score += 0.40
        if "acknowledged" in payload or "accepted" in payload:
            score += 0.20
        if "review" in payload:
            score += 0.10
        return min(1.0, score)

    if etype == "listing_catalyst":
        score = 0.0
        if "wallet support" in payload:
            score += 0.15
        if "exchange deposit" in payload:
            score += 0.25
        if "trading starts" in payload or "listing confirmed" in payload:
            score += 0.45
        return min(1.0, score)

    if etype == "launch_catalyst":
        score = 0.0
        if "testnet" in payload:
            score += 0.15
        if "audit complete" in payload:
            score += 0.20
        if "mainnet live" in payload or "launch confirmed" in payload:
            score += 0.45
        if "deploy" in payload:
            score += 0.15
        return min(1.0, score)

    return 0.20


def _precedent_score(decoded: dict) -> float:
    etype = decoded.get("event_type", "")
    if etype == "etf_catalyst":
        return 0.35
    if etype == "listing_catalyst":
        return 0.45
    if etype == "launch_catalyst":
        return 0.40
    return 0.25
