"""
Sentiment Adapter for System Aggregator
=========================================
Fetches recent sentiment for a given asset from sentiment_training_dataset_v3.
Returns a (score, confidence) tuple.
"""


def fetch_sentiment_for_asset(db, asset: str) -> dict:
    """
    Fetch latest sentiment signal for a given asset.

    Looks in sentiment_training_dataset_v3 for recent signals matching the asset token.
    Returns: {"score": float, "confidence": float, "source_count": int}
    """
    if db is None:
        return {"score": 0.0, "confidence": 0.0, "source_count": 0}

    try:
        col = db["sentiment_training_dataset_v3"]

        # Find signals matching this asset (by market.token or text.tokens)
        asset_upper = asset.upper()
        cursor = col.find(
            {"$or": [
                {"market.token": asset_upper},
                {"text.tokens": asset_upper},
            ]},
            {"_id": 0, "sentiment": 1},
        ).sort("meta.created_at", -1).limit(20)

        docs = list(cursor)

        if not docs:
            return {"score": 0.0, "confidence": 0.0, "source_count": 0}

        # Aggregate: weighted average by confidence
        total_weight = 0.0
        weighted_score = 0.0
        confidences = []

        for d in docs:
            sent = d.get("sentiment", {})
            if not isinstance(sent, dict):
                continue
            score = sent.get("score", 0.0) or 0.0
            conf = sent.get("confidence", 0.0) or 0.0
            weighted_score += score * conf
            total_weight += conf
            confidences.append(conf)

        avg_score = weighted_score / max(total_weight, 0.001)
        avg_conf = sum(confidences) / max(len(confidences), 1)

        return {
            "score": round(max(-1.0, min(1.0, avg_score)), 4),
            "confidence": round(max(0.0, min(1.0, avg_conf)), 4),
            "source_count": len(docs),
        }

    except Exception:
        return {"score": 0.0, "confidence": 0.0, "source_count": 0}
