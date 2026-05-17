"""
Risk Scoring Layer
===================
Вычисляет risk_score для каждой ноды.

Формула:
  risk_score = wash_score * 0.35 + exposure_score * 0.35 + corridor_risk * 0.20 + cluster_risk * 0.10

Где:
  - wash_score: из wash-алертов (количество и confidence)
  - exposure_score: из exposure_service (уже в graph_nodes)
  - corridor_risk: участие в подозрительных коридорах
  - cluster_risk: принадлежность к рискованному кластеру

Обновляет: graph_nodes.risk_score, graph_nodes.risk_level

Usage:
  python risk_scoring_service.py
"""

import asyncio
import os
import time
from collections import defaultdict
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017/intelligence_engine")
DB_NAME = os.environ.get("DB_NAME", "intelligence_engine")


def risk_level(score):
    if score >= 0.7:
        return "critical"
    if score >= 0.5:
        return "high"
    if score >= 0.3:
        return "medium"
    if score >= 0.1:
        return "low"
    return "clean"


async def compute_risk(db=None, client=None):
    """Вычислить risk_score для всех нод."""
    own_client = False
    if db is None:
        client = AsyncIOMotorClient(MONGO_URL)
        db = client[DB_NAME]
        own_client = True

    start = time.time()
    print("=" * 60)
    print("RISK SCORING LAYER")
    print("=" * 60)

    nodes_coll = db["graph_nodes"]
    wash_coll = db["graph_wash_alerts"]
    corridors_coll = db["graph_corridors"]
    clusters_coll = db["graph_clusters"]

    # 1. Загрузить ноды с exposure
    node_map = {}
    cursor = nodes_coll.find(
        {}, {"_id": 0, "id": 1, "label": 1, "exposure_score": 1,
             "cluster_id": 1, "type": 1}
    )
    async for n in cursor:
        node_map[n["id"]] = n
    print(f"  Загружено {len(node_map)} нод")

    # 2. Wash scores: для каждой ноды — макс confidence из алертов
    wash_scores = defaultdict(float)
    cursor = wash_coll.find({}, {"_id": 0, "nodes": 1, "confidence": 1})
    async for alert in cursor:
        conf = alert.get("confidence", 0)
        for nid in alert.get("nodes", []):
            wash_scores[nid] = max(wash_scores[nid], conf)
    print(f"  Нод с wash-score: {len(wash_scores)}")

    # 3. Corridor risk: ноды участвующие в коридорах с высоким объёмом
    corridor_risk = defaultdict(float)
    cursor = corridors_coll.find({}, {"_id": 0, "source": 1, "target": 1, "confidence": 1})
    async for c in cursor:
        conf = c.get("confidence", 0)
        corridor_risk[c.get("source", "")] = max(corridor_risk[c.get("source", "")], conf * 0.5)
        corridor_risk[c.get("target", "")] = max(corridor_risk[c.get("target", "")], conf * 0.5)

    # 4. Cluster risk
    risky_clusters = {}
    cursor = clusters_coll.find({}, {"_id": 0, "cluster_id": 1, "type": 1, "confidence": 1})
    async for c in cursor:
        ctype = c.get("type", "")
        if ctype in ("suspicious", "flagged", "mixer", "wash"):
            risky_clusters[c["cluster_id"]] = c.get("confidence", 0.5)

    # 5. Вычислить risk_score
    updated = 0
    level_counts = defaultdict(int)

    for nid, n in node_map.items():
        w_score = wash_scores.get(nid, 0)
        e_score = n.get("exposure_score", 0) or 0
        c_risk = corridor_risk.get(nid, 0)
        cl_risk = 0
        cluster_id = n.get("cluster_id")
        if cluster_id and cluster_id in risky_clusters:
            cl_risk = risky_clusters[cluster_id]

        risk_score = round(
            w_score * 0.35 +
            e_score * 0.35 +
            c_risk * 0.20 +
            cl_risk * 0.10,
            4
        )

        level = risk_level(risk_score)
        level_counts[level] += 1

        if risk_score > 0:
            await nodes_coll.update_one(
                {"id": nid},
                {"$set": {
                    "risk_score": risk_score,
                    "risk_level": level,
                    "risk_components": {
                        "wash": round(w_score, 4),
                        "exposure": round(e_score, 4),
                        "corridor": round(c_risk, 4),
                        "cluster": round(cl_risk, 4),
                    }
                }}
            )
            updated += 1

    # Топ-10
    top = await nodes_coll.find(
        {"risk_score": {"$gt": 0}},
        {"_id": 0, "id": 1, "label": 1, "risk_score": 1, "risk_level": 1, "risk_components": 1}
    ).sort("risk_score", -1).limit(10).to_list(10)

    print(f"\n--- Топ-10 по risk_score ---")
    for n in top:
        label = n.get("label", n["id"][:30])
        print(f"  {label:30s} risk={n['risk_score']:.4f} [{n.get('risk_level', '?')}]")
        rc = n.get("risk_components", {})
        print(f"    wash={rc.get('wash',0):.3f} exposure={rc.get('exposure',0):.3f} corridor={rc.get('corridor',0):.3f} cluster={rc.get('cluster',0):.3f}")

    print(f"\n--- Распределение ---")
    for level in ["critical", "high", "medium", "low", "clean"]:
        print(f"  {level:10s}: {level_counts.get(level, 0)}")

    elapsed = round(time.time() - start, 1)
    print(f"\n  Обновлено: {updated}")
    print(f"  Время: {elapsed}s")
    print("=" * 60)

    if own_client:
        client.close()

    return level_counts


async def main():
    await compute_risk()


if __name__ == "__main__":
    asyncio.run(main())
