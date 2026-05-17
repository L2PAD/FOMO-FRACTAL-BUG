"""
Platform Market Linker — matches markets across Polymarket and Kalshi.

Matcher scoring:
  match_score = entity_score * 0.35 + topic_score * 0.25 + time_score * 0.20 + resolution_score * 0.20

Thresholds:
  >= 0.75 → ACCEPT
  >= 0.65 → WEAK_MATCH (debug only)
  <  0.65 → REJECT

Blocking rules:
  - entity_score == 0 → REJECT
  - resolution_score == 0 → REJECT
  - time_score == 0 → REJECT
"""
import logging
import re
from datetime import datetime, timezone

logger = logging.getLogger("cross_market.kalshi.matcher")

# Weights
W_ENTITY = 0.35
W_TOPIC = 0.25
W_TIME = 0.20
W_RESOLUTION = 0.20

# Thresholds
ACCEPT_THRESHOLD = 0.75
WEAK_THRESHOLD = 0.65

# Entity synonyms for normalization
ENTITY_ALIASES = {
    "bitcoin": "BTC", "btc": "BTC",
    "ethereum": "ETH", "eth": "ETH",
    "solana": "SOL", "sol": "SOL",
    "tiktok": "TIKTOK", "bytedance": "TIKTOK",
}


def _normalize_entity(text: str) -> str:
    """Normalize entity to canonical form."""
    text_lower = text.strip().lower()
    return ENTITY_ALIASES.get(text_lower, text.upper())


def _extract_entities_from_text(text: str) -> set[str]:
    """Extract known entities from text."""
    text_lower = text.lower()
    entities = set()
    for keyword, canonical in ENTITY_ALIASES.items():
        if keyword in text_lower:
            entities.add(canonical)
    return entities


def entity_score(poly_market: dict, kalshi_market: dict) -> float:
    """Score entity match between platforms."""
    # Get entities from both sides
    poly_entities = set()
    poly_asset = (poly_market.get("asset_group", "") or "").upper()
    if poly_asset:
        poly_entities.add(_normalize_entity(poly_asset))
    poly_entities.update(_extract_entities_from_text(
        poly_market.get("question", "") + " " + poly_market.get("title", "")
    ))

    kalshi_entity = kalshi_market.get("entity", "")
    kalshi_entities = {kalshi_entity} if kalshi_entity and kalshi_entity != "UNKNOWN" else set()
    kalshi_entities.update(_extract_entities_from_text(
        kalshi_market.get("question", "") + " " + kalshi_market.get("rules", "")
    ))

    # Find overlap
    overlap = poly_entities & kalshi_entities
    if not overlap:
        return 0.0

    # Primary entity match (exact)
    if poly_asset and _normalize_entity(poly_asset) in kalshi_entities:
        return 1.0

    return 0.7


def topic_score(poly_market: dict, kalshi_market: dict) -> float:
    """Score topic similarity using token overlap (Jaccard).

    For price threshold markets, entity match is already handled by entity_score,
    so topic_score focuses on contextual similarity (date, asset name, direction).
    """
    poly_text = (poly_market.get("question", "") + " " + poly_market.get("title", "")).lower()
    kalshi_text = (kalshi_market.get("question", "") + " " + kalshi_market.get("rules", "")).lower()

    # Tokenize and clean
    poly_tokens = set(re.findall(r'[a-z]+', poly_text))
    kalshi_tokens = set(re.findall(r'[a-z]+', kalshi_text))

    # Remove common stop words
    stop = {"the", "a", "an", "is", "to", "of", "in", "at", "on", "by",
            "for", "will", "be", "or", "and", "if", "then", "that", "this",
            "market", "resolves", "yes", "no", "before", "after",
            "price", "range", "hit", "reach", "what"}
    poly_tokens -= stop
    kalshi_tokens -= stop

    if not poly_tokens or not kalshi_tokens:
        return 0.0

    intersection = poly_tokens & kalshi_tokens
    union = poly_tokens | kalshi_tokens

    similarity = len(intersection) / len(union) if union else 0

    # For crypto price markets, even low text overlap is fine
    # if entities match and both are about price
    both_price = (
        any(w in poly_text for w in ["above", "below", "exceed", "between"])
        and any(w in kalshi_text for w in ["above", "below", "exceed", "between"])
    )

    if both_price and similarity > 0.1:
        return max(0.5, similarity)

    if similarity > 0.6:
        return 1.0
    elif similarity > 0.4:
        return 0.8
    elif similarity > 0.2:
        return 0.5
    elif similarity > 0.1:
        return 0.3
    return 0.0


def time_score(poly_market: dict, kalshi_market: dict) -> float:
    """Score time proximity between market expirations."""
    poly_expiry = _get_expiry_ms(poly_market)
    kalshi_expiry = kalshi_market.get("expiry_ts") or _get_expiry_ms(kalshi_market)

    if poly_expiry is None or kalshi_expiry is None:
        # If we can't determine either expiry, give a neutral-to-good score
        # since entity + resolution matching already filtered well
        return 0.6

    diff_hours = abs(poly_expiry - kalshi_expiry) / (3600 * 1000)

    if diff_hours <= 24:
        return 1.0
    elif diff_hours <= 72:
        return 0.8
    elif diff_hours <= 168:  # 1 week
        return 0.6
    elif diff_hours <= 720:  # 30 days
        return 0.3
    return 0.0


def resolution_score(poly_market: dict, kalshi_market: dict) -> float:
    """Score resolution similarity based on threshold/direction."""
    poly_threshold = poly_market.get("threshold", 0) or 0
    kalshi_threshold = kalshi_market.get("threshold", 0) or 0
    poly_direction = poly_market.get("direction", "")
    kalshi_direction = kalshi_market.get("direction", "")

    # Both must have thresholds for price markets
    if poly_threshold <= 0 and kalshi_threshold <= 0:
        return 0.0

    # Direction must be compatible
    if poly_direction and kalshi_direction:
        if poly_direction == kalshi_direction:
            pass  # Good
        elif poly_direction in ("ABOVE", "BELOW") and kalshi_direction in ("ABOVE", "BELOW"):
            if poly_direction != kalshi_direction:
                return 0.0  # Opposite directions

    # Threshold proximity
    if poly_threshold > 0 and kalshi_threshold > 0:
        diff_pct = abs(poly_threshold - kalshi_threshold) / max(poly_threshold, kalshi_threshold)
        if diff_pct < 0.005:  # <0.5% difference
            return 1.0
        elif diff_pct < 0.02:  # <2%
            return 0.8
        elif diff_pct < 0.05:  # <5%
            return 0.5
        return 0.0

    return 0.0


def match_markets(poly_market: dict, kalshi_market: dict) -> dict | None:
    """Try to match a Polymarket market with a Kalshi market.

    Returns match result dict or None if rejected.
    """
    e = entity_score(poly_market, kalshi_market)
    if e == 0:
        return None

    t = topic_score(poly_market, kalshi_market)
    tm = time_score(poly_market, kalshi_market)
    r = resolution_score(poly_market, kalshi_market)

    # Block: resolution must have some match
    if r == 0:
        return None

    # Block: time must have some proximity
    if tm == 0:
        return None

    score = round(e * W_ENTITY + t * W_TOPIC + tm * W_TIME + r * W_RESOLUTION, 4)

    if score < WEAK_THRESHOLD:
        return None

    return {
        "match_score": score,
        "accepted": score >= ACCEPT_THRESHOLD,
        "poly_market_id": poly_market.get("market_id", ""),
        "kalshi_market_id": kalshi_market.get("id", ""),
        "entity_score": round(e, 4),
        "topic_score": round(t, 4),
        "time_score": round(tm, 4),
        "resolution_score": round(r, 4),
        "poly_question": poly_market.get("question", ""),
        "kalshi_question": kalshi_market.get("question", ""),
        "poly_threshold": poly_market.get("threshold", 0),
        "kalshi_threshold": kalshi_market.get("threshold", 0),
        "poly_direction": poly_market.get("direction", ""),
        "kalshi_direction": kalshi_market.get("direction", ""),
        "poly_price": poly_market.get("yes_price"),
        "kalshi_price": kalshi_market.get("yes_price"),
    }


def link_platforms(poly_markets: list[dict], kalshi_markets: list[dict]) -> list[dict]:
    """Link markets across Polymarket and Kalshi.

    Returns list of CrossPlatformCluster dicts.
    """
    clusters = {}  # topic_key → cluster
    all_matches = []

    for pm in poly_markets:
        for km in kalshi_markets:
            result = match_markets(pm, km)
            if result is None:
                continue

            all_matches.append(result)

            if result["accepted"]:
                # Group by entity + approximate threshold
                entity = _normalize_entity(pm.get("asset_group", "") or pm.get("question", ""))
                threshold_key = _threshold_bucket(
                    result["poly_threshold"], result["kalshi_threshold"]
                )
                topic_key = f"{entity}_{threshold_key}"

                if topic_key not in clusters:
                    clusters[topic_key] = {
                        "cluster_id": topic_key,
                        "entity": entity,
                        "topic": f"{entity} threshold {threshold_key}",
                        "markets": [],
                        "matches": [],
                    }

                # Add markets to cluster (deduplicate)
                cluster = clusters[topic_key]
                poly_ids = {m["id"] for m in cluster["markets"] if m.get("platform") == "polymarket"}
                kalshi_ids = {m["id"] for m in cluster["markets"] if m.get("platform") == "kalshi"}

                if pm.get("market_id") not in poly_ids:
                    cluster["markets"].append({
                        "platform": "polymarket",
                        "id": pm.get("market_id", ""),
                        "question": pm.get("question", ""),
                        "price": pm.get("yes_price"),
                        "threshold": pm.get("threshold", 0),
                        "direction": pm.get("direction", ""),
                        "volume": pm.get("volume", 0),
                        "spread": pm.get("spread"),
                    })

                if km.get("id") not in kalshi_ids:
                    cluster["markets"].append({
                        "platform": "kalshi",
                        "id": km.get("id", ""),
                        "question": km.get("question", ""),
                        "price": km.get("yes_price"),
                        "threshold": km.get("threshold", 0),
                        "direction": km.get("direction", ""),
                        "volume": km.get("volume", 0),
                        "spread": km.get("spread"),
                    })

                cluster["matches"].append(result)

    # Sort clusters by match count
    result_clusters = sorted(clusters.values(), key=lambda c: len(c["matches"]), reverse=True)

    logger.info(
        f"[PlatformLinker] {len(poly_markets)} poly × {len(kalshi_markets)} kalshi → "
        f"{len(all_matches)} matches → {len(result_clusters)} clusters"
    )

    return result_clusters


# ═══ Helpers ═══

def _get_expiry_ms(market: dict) -> float | None:
    """Get expiry timestamp in ms from various market formats."""
    # Direct ISO date fields
    end_date = market.get("end_date_iso") or market.get("close_time")
    if end_date:
        try:
            dt = datetime.fromisoformat(str(end_date).replace("Z", "+00:00"))
            return dt.timestamp() * 1000
        except (ValueError, TypeError):
            pass

    # Try to parse date from question text
    question = (market.get("question", "") + " " + market.get("title", "")).lower()
    date_patterns = [
        (r'on\s+april\s+(\d+)', 4),
        (r'on\s+march\s+(\d+)', 3),
        (r'on\s+may\s+(\d+)', 5),
        (r'on\s+june\s+(\d+)', 6),
        (r'by\s+april\s+(\d+)', 4),
        (r'by\s+march\s+(\d+)', 3),
        (r'april\s+(\d+)', 4),
        (r'march\s+(\d+)', 3),
    ]
    for pattern, month in date_patterns:
        m = re.search(pattern, question)
        if m:
            day = int(m.group(1))
            try:
                dt = datetime(2026, month, min(day, 28), 21, 0, 0, tzinfo=timezone.utc)
                return dt.timestamp() * 1000
            except (ValueError, TypeError):
                pass

    # "in March" / "March 30-April 5"
    if "april 1" in question or "on april 1" in question:
        dt = datetime(2026, 4, 1, 21, 0, 0, tzinfo=timezone.utc)
        return dt.timestamp() * 1000

    return None


def _threshold_bucket(t1: float, t2: float) -> str:
    """Create a normalized threshold bucket key."""
    avg = (t1 + t2) / 2 if t1 > 0 and t2 > 0 else max(t1, t2)
    if avg <= 0:
        return "0"
    # Round to nearest 1000 for grouping
    if avg >= 10000:
        return f"{round(avg / 1000) * 1000}"
    elif avg >= 1000:
        return f"{round(avg / 100) * 100}"
    return f"{round(avg)}"
