"""
Topic Clusterer — merges related clusters into higher-level topic groups.

Groups by entity + time_frame, merging price_target + price_range into one topic.
"""
import logging

logger = logging.getLogger("cross_market.topic_clusterer")

# Topic types that should merge (they describe the same underlying question)
MERGEABLE_TYPES = {
    frozenset({"price_target", "price_range"}): "price_ladder",
    frozenset({"price_target", "other"}): "price_ladder",
    frozenset({"price_target"}): "price_ladder",
    frozenset({"price_range"}): "price_ladder",
    frozenset({"fdv"}): "fdv_ladder",
    frozenset({"direction"}): "direction",
}


def cluster_topics(clusters: list[dict]) -> list[dict]:
    """Merge related clusters into topic-level groups."""
    # Group by entity + time_frame
    groups = {}
    for c in clusters:
        for entity in c["entities"]:
            for tf in c["time_frames"]:
                group_key = f"{entity}:{tf}"
                if group_key not in groups:
                    groups[group_key] = {
                        "topic_key": group_key,
                        "entity": entity,
                        "time_frame": tf,
                        "source_clusters": [],
                        "all_markets": [],
                        "topic_types": set(),
                    }
                g = groups[group_key]
                g["source_clusters"].append(c["cluster_key"])
                g["all_markets"].extend(c["markets"])
                g["topic_types"].update(c["topic_types"])

    # Classify and deduplicate
    result = []
    for key, g in groups.items():
        types_frozen = frozenset(g["topic_types"])
        topic_type = "mixed"
        for merge_key, label in MERGEABLE_TYPES.items():
            if types_frozen.issubset(merge_key) or merge_key.issubset(types_frozen):
                topic_type = label
                break

        # Deduplicate markets by question
        seen = set()
        unique_markets = []
        for m in g["all_markets"]:
            q = m["question"]
            if q not in seen:
                seen.add(q)
                unique_markets.append(m)

        if len(unique_markets) < 2:
            continue

        # Sort by threshold
        unique_markets.sort(key=lambda m: m.get("threshold", 0))

        result.append({
            "topic_key": key,
            "entity": g["entity"],
            "time_frame": g["time_frame"],
            "topic_type": topic_type,
            "market_count": len(unique_markets),
            "source_clusters": g["source_clusters"],
            "markets": unique_markets,
        })

    logger.info(f"[TopicClusterer] {len(clusters)} clusters → {len(result)} topics")
    return result
