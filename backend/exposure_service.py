"""
Compliance / Exposure Layer
============================
Рассчитывает exposure_score и exposure_flags для каждой ноды:

- mixer_exposure: взаимодействие с известными миксерами
- sanction_exposure: связи с санкционными сущностями
- flagged_cluster: участие в подозрительных кластерах
- wash_exposure: участие в wash-алертах
- counterparty_risk: среднее количество подозрительных контрагентов

Обновляет: graph_nodes.exposure_score, graph_nodes.exposure_flags

Usage:
  python exposure_service.py
"""

import asyncio
import os
import time
from collections import defaultdict
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017/intelligence_engine")
DB_NAME = os.environ.get("DB_NAME", "intelligence_engine")

# Паттерны миксеров (по лейблам и типам)
MIXER_LABELS = {"tornado", "tornado cash", "mixer", "blender", "chipmixer", "wasabi"}
SANCTION_LABELS = {"lazarus", "ofac", "sanctioned", "blacklisted"}


async def compute_exposure(db=None, client=None):
    """Вычислить exposure для всех нод."""
    own_client = False
    if db is None:
        client = AsyncIOMotorClient(MONGO_URL)
        db = client[DB_NAME]
        own_client = True

    start = time.time()
    print("=" * 60)
    print("COMPLIANCE / EXPOSURE LAYER")
    print("=" * 60)

    nodes_coll = db["graph_nodes"]
    rels_coll = db["graph_relations"]
    wash_coll = db["graph_wash_alerts"]

    # 1. Загрузить все ноды
    node_map = {}
    cursor = nodes_coll.find({}, {"_id": 0, "id": 1, "label": 1, "type": 1, "cluster_id": 1})
    async for n in cursor:
        node_map[n["id"]] = n
    print(f"  Загружено {len(node_map)} нод")

    # 2. Определить mixer/sanction ноды по лейблам
    mixer_nodes = set()
    sanction_nodes = set()
    for nid, n in node_map.items():
        label_lower = (n.get("label") or "").lower()
        if any(m in label_lower for m in MIXER_LABELS):
            mixer_nodes.add(nid)
        if any(s in label_lower for s in SANCTION_LABELS):
            sanction_nodes.add(nid)

    print(f"  Mixer ноды: {len(mixer_nodes)}")
    print(f"  Sanction ноды: {len(sanction_nodes)}")

    # 3. Построить карту контрагентов
    counterparties = defaultdict(set)
    cursor = rels_coll.find({}, {"_id": 0, "source_id": 1, "target_id": 1})
    async for rel in cursor:
        src = rel.get("source_id", "")
        tgt = rel.get("target_id", "")
        if src and tgt:
            counterparties[src].add(tgt)
            counterparties[tgt].add(src)

    # 4. Загрузить wash-алерты
    wash_nodes = defaultdict(int)  # node_id → количество алертов
    cursor = wash_coll.find({}, {"_id": 0, "nodes": 1, "confidence": 1})
    async for alert in cursor:
        for nid in alert.get("nodes", []):
            wash_nodes[nid] += 1

    print(f"  Нод в wash-алертах: {len(wash_nodes)}")

    # 5. Подозрительные кластеры
    flagged_clusters = set()
    cluster_cursor = db["graph_clusters"].find(
        {"type": {"$in": ["suspicious", "flagged", "mixer"]}},
        {"_id": 0, "cluster_id": 1}
    )
    async for c in cluster_cursor:
        flagged_clusters.add(c["cluster_id"])

    # 6. Вычислить exposure для каждой ноды
    updated = 0
    exposure_scores = {}

    for nid, n in node_map.items():
        flags = []
        scores = {}

        # Mixer exposure: сколько контрагентов — миксеры
        cps = counterparties.get(nid, set())
        mixer_count = len(cps & mixer_nodes)
        if mixer_count > 0:
            flags.append("mixer_exposure")
            scores["mixer"] = min(1.0, mixer_count * 0.3)
        else:
            scores["mixer"] = 0

        # Sanction exposure
        sanction_count = len(cps & sanction_nodes)
        if sanction_count > 0:
            flags.append("sanction_exposure")
            scores["sanction"] = min(1.0, sanction_count * 0.4)
        else:
            scores["sanction"] = 0

        # Wash exposure
        wash_count = wash_nodes.get(nid, 0)
        if wash_count > 0:
            flags.append("wash_involvement")
            scores["wash"] = min(1.0, wash_count * 0.2)
        else:
            scores["wash"] = 0

        # Flagged cluster
        cluster_id = n.get("cluster_id")
        if cluster_id and cluster_id in flagged_clusters:
            flags.append("flagged_cluster")
            scores["cluster"] = 0.5
        else:
            scores["cluster"] = 0

        # Counterparty risk: доля подозрительных контрагентов
        risky_cps = len(cps & mixer_nodes) + len(cps & sanction_nodes) + sum(1 for c in cps if wash_nodes.get(c, 0) > 0)
        total_cps = len(cps)
        if total_cps > 0:
            scores["counterparty"] = min(1.0, risky_cps / total_cps)
            if scores["counterparty"] > 0.3:
                flags.append("high_counterparty_risk")
        else:
            scores["counterparty"] = 0

        # Итоговый exposure_score
        exposure_score = round(
            scores["mixer"] * 0.25 +
            scores["sanction"] * 0.30 +
            scores["wash"] * 0.25 +
            scores["cluster"] * 0.10 +
            scores["counterparty"] * 0.10,
            4
        )

        exposure_scores[nid] = exposure_score

        if exposure_score > 0 or flags:
            await nodes_coll.update_one(
                {"id": nid},
                {"$set": {
                    "exposure_score": exposure_score,
                    "exposure_flags": flags,
                }}
            )
            updated += 1

    # Статистика
    flagged_count = sum(1 for s in exposure_scores.values() if s > 0)
    high_risk = sum(1 for s in exposure_scores.values() if s > 0.5)

    # Топ-10
    top = sorted(exposure_scores.items(), key=lambda x: x[1], reverse=True)[:10]
    print(f"\n--- Топ-10 по exposure ---")
    for nid, score in top:
        n = node_map.get(nid, {})
        label = n.get("label", nid[:30])
        print(f"  {label:30s} exposure={score:.4f}")

    elapsed = round(time.time() - start, 1)
    print(f"\n  Обновлено: {updated}")
    print(f"  С exposure > 0: {flagged_count}")
    print(f"  Высокий риск (>0.5): {high_risk}")
    print(f"  Время: {elapsed}s")
    print("=" * 60)

    if own_client:
        client.close()

    return exposure_scores


async def main():
    await compute_exposure()


if __name__ == "__main__":
    asyncio.run(main())
