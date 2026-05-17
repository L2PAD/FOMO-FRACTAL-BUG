"""
Wash / Manipulation Detection
==============================
Детектирует подозрительные паттерны в graph_relations:

1. Cyclical flows (A → B → A)
2. Self-routing (A → X → A через промежуточный узел)
3. Triangle routing (A → B → C → A)
4. Rapid back-and-forth (A ↔ B с коротким интервалом)

Результаты сохраняются в graph_wash_alerts.

Usage:
  python wash_detection.py
"""

import asyncio
import os
import time
import hashlib
from datetime import datetime, timezone
from collections import defaultdict
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017/intelligence_engine")
DB_NAME = os.environ.get("DB_NAME", "intelligence_engine")

# Пороги
MIN_TX_FOR_CYCLE = 2
RAPID_TRANSFER_WINDOW = 86400 * 3  # 3 дня


def make_alert_id(pattern_type, nodes_sorted):
    """Стабильный ID для алерта."""
    raw = f"{pattern_type}:{'|'.join(nodes_sorted)}"
    return hashlib.md5(raw.encode()).hexdigest()[:16]


async def detect_cyclical_flows(db):
    """A → B и B → A (back-and-forth)."""
    alerts = []
    # Построить карту source→target
    edges = defaultdict(lambda: {"tx_count": 0, "amount": 0, "last_seen": 0})
    cursor = db["graph_relations"].find(
        {}, {"_id": 0, "source_id": 1, "target_id": 1, "total_tx_count": 1,
             "total_amount_usd": 1, "last_seen": 1}
    )
    async for rel in cursor:
        src = rel.get("source_id", "")
        tgt = rel.get("target_id", "")
        edges[(src, tgt)]["tx_count"] += rel.get("total_tx_count", 1) or 1
        edges[(src, tgt)]["amount"] += rel.get("total_amount_usd", 0) or 0
        edges[(src, tgt)]["last_seen"] = max(
            edges[(src, tgt)]["last_seen"], rel.get("last_seen", 0) or 0
        )

    # Поиск пар A↔B
    seen = set()
    for (src, tgt), fwd in edges.items():
        if (tgt, src) in edges and (tgt, src) not in seen:
            rev = edges[(tgt, src)]
            if fwd["tx_count"] >= MIN_TX_FOR_CYCLE and rev["tx_count"] >= MIN_TX_FOR_CYCLE:
                nodes_sorted = sorted([src, tgt])
                alert_id = make_alert_id("cyclical_flow", nodes_sorted)
                total_amount = fwd["amount"] + rev["amount"]
                confidence = min(0.95, 0.4 + (fwd["tx_count"] + rev["tx_count"]) * 0.02)

                alerts.append({
                    "alert_id": alert_id,
                    "pattern_type": "cyclical_flow",
                    "nodes": nodes_sorted,
                    "edges": [
                        {"source": src, "target": tgt, "tx_count": fwd["tx_count"], "amount_usd": fwd["amount"]},
                        {"source": tgt, "target": src, "tx_count": rev["tx_count"], "amount_usd": rev["amount"]},
                    ],
                    "confidence": round(confidence, 3),
                    "amount_usd": round(total_amount, 2),
                    "total_tx": fwd["tx_count"] + rev["tx_count"],
                    "last_seen": max(fwd["last_seen"], rev["last_seen"]),
                })
                seen.add((src, tgt))
                seen.add((tgt, src))

    return alerts


async def detect_triangle_routing(db):
    """A → B → C → A (треугольный маршрут)."""
    alerts = []

    # Загрузить все связи в adjacency list
    adj = defaultdict(set)
    edge_data = {}
    cursor = db["graph_relations"].find(
        {"total_tx_count": {"$gte": MIN_TX_FOR_CYCLE}},
        {"_id": 0, "source_id": 1, "target_id": 1, "total_tx_count": 1,
         "total_amount_usd": 1, "last_seen": 1}
    )
    async for rel in cursor:
        src = rel.get("source_id", "")
        tgt = rel.get("target_id", "")
        adj[src].add(tgt)
        edge_data[(src, tgt)] = {
            "tx_count": rel.get("total_tx_count", 1),
            "amount": rel.get("total_amount_usd", 0) or 0,
            "last_seen": rel.get("last_seen", 0) or 0,
        }

    # Поиск треугольников: A→B, B→C, C→A
    seen_triangles = set()
    for a in adj:
        for b in adj[a]:
            if b == a:
                continue
            for c in adj.get(b, set()):
                if c == a or c == b:
                    continue
                if a in adj.get(c, set()):
                    tri_key = tuple(sorted([a, b, c]))
                    if tri_key in seen_triangles:
                        continue
                    seen_triangles.add(tri_key)

                    e_ab = edge_data.get((a, b), {})
                    e_bc = edge_data.get((b, c), {})
                    e_ca = edge_data.get((c, a), {})
                    total_amount = (e_ab.get("amount", 0) + e_bc.get("amount", 0) + e_ca.get("amount", 0))
                    total_tx = (e_ab.get("tx_count", 0) + e_bc.get("tx_count", 0) + e_ca.get("tx_count", 0))
                    confidence = min(0.95, 0.5 + total_tx * 0.01)

                    alerts.append({
                        "alert_id": make_alert_id("triangle_routing", list(tri_key)),
                        "pattern_type": "triangle_routing",
                        "nodes": list(tri_key),
                        "edges": [
                            {"source": a, "target": b, "tx_count": e_ab.get("tx_count", 0), "amount_usd": e_ab.get("amount", 0)},
                            {"source": b, "target": c, "tx_count": e_bc.get("tx_count", 0), "amount_usd": e_bc.get("amount", 0)},
                            {"source": c, "target": a, "tx_count": e_ca.get("tx_count", 0), "amount_usd": e_ca.get("amount", 0)},
                        ],
                        "confidence": round(confidence, 3),
                        "amount_usd": round(total_amount, 2),
                        "total_tx": total_tx,
                        "last_seen": max(e_ab.get("last_seen", 0), e_bc.get("last_seen", 0), e_ca.get("last_seen", 0)),
                    })

    return alerts


async def detect_self_routing(db):
    """A → X → A через промежуточный узел (с малым degree)."""
    alerts = []

    # Найти ноды с малым degree (потенциальные pass-through)
    small_nodes = set()
    cursor = db["graph_nodes"].find(
        {"degree": {"$lte": 4, "$gte": 2}},
        {"_id": 0, "id": 1}
    )
    async for n in cursor:
        small_nodes.add(n["id"])

    # Загрузить связи
    adj_in = defaultdict(list)   # target → [source]
    adj_out = defaultdict(list)  # source → [target]
    edge_data = {}
    cursor = db["graph_relations"].find(
        {}, {"_id": 0, "source_id": 1, "target_id": 1, "total_tx_count": 1,
             "total_amount_usd": 1, "last_seen": 1}
    )
    async for rel in cursor:
        src = rel.get("source_id", "")
        tgt = rel.get("target_id", "")
        adj_out[src].append(tgt)
        adj_in[tgt].append(src)
        edge_data[(src, tgt)] = {
            "tx_count": rel.get("total_tx_count", 1),
            "amount": rel.get("total_amount_usd", 0) or 0,
            "last_seen": rel.get("last_seen", 0) or 0,
        }

    seen = set()
    for x in small_nodes:
        sources = adj_in.get(x, [])
        targets = adj_out.get(x, [])
        for a in sources:
            if a in targets and a != x:
                pair_key = tuple(sorted([a, x]))
                if pair_key in seen:
                    continue
                seen.add(pair_key)

                e_ax = edge_data.get((a, x), {})
                e_xa = edge_data.get((x, a), {})
                total_amount = e_ax.get("amount", 0) + e_xa.get("amount", 0)
                total_tx = e_ax.get("tx_count", 0) + e_xa.get("tx_count", 0)
                confidence = min(0.90, 0.3 + total_tx * 0.03)

                alerts.append({
                    "alert_id": make_alert_id("self_routing", [a, x]),
                    "pattern_type": "self_routing",
                    "nodes": [a, x],
                    "edges": [
                        {"source": a, "target": x, "tx_count": e_ax.get("tx_count", 0), "amount_usd": e_ax.get("amount", 0)},
                        {"source": x, "target": a, "tx_count": e_xa.get("tx_count", 0), "amount_usd": e_xa.get("amount", 0)},
                    ],
                    "confidence": round(confidence, 3),
                    "amount_usd": round(total_amount, 2),
                    "total_tx": total_tx,
                    "last_seen": max(e_ax.get("last_seen", 0), e_xa.get("last_seen", 0)),
                })

    return alerts


async def run_detection(db=None, client=None):
    """Запуск всех детекторов. Возвращает список алертов."""
    own_client = False
    if db is None:
        client = AsyncIOMotorClient(MONGO_URL)
        db = client[DB_NAME]
        own_client = True

    start = time.time()
    print("=" * 60)
    print("WASH / MANIPULATION DETECTION")
    print("=" * 60)

    all_alerts = []

    # 1. Cyclical flows
    print("\n--- Cyclical Flows ---")
    cyclical = await detect_cyclical_flows(db)
    print(f"  Найдено: {len(cyclical)} алертов")
    all_alerts.extend(cyclical)

    # 2. Triangle routing
    print("\n--- Triangle Routing ---")
    triangles = await detect_triangle_routing(db)
    print(f"  Найдено: {len(triangles)} алертов")
    all_alerts.extend(triangles)

    # 3. Self-routing
    print("\n--- Self-Routing ---")
    self_routes = await detect_self_routing(db)
    print(f"  Найдено: {len(self_routes)} алертов")
    all_alerts.extend(self_routes)

    # Сохранить в БД
    coll = db["graph_wash_alerts"]
    saved = 0
    for alert in all_alerts:
        alert["detected_at"] = datetime.now(timezone.utc).isoformat()
        await coll.update_one(
            {"alert_id": alert["alert_id"]},
            {"$set": alert},
            upsert=True,
        )
        saved += 1

    # Индексы
    await coll.create_index("alert_id", unique=True)
    await coll.create_index("pattern_type")
    await coll.create_index([("confidence", -1)])
    await coll.create_index([("amount_usd", -1)])

    total = await coll.count_documents({})
    elapsed = round(time.time() - start, 1)

    # Статистика
    by_type = defaultdict(int)
    for a in all_alerts:
        by_type[a["pattern_type"]] += 1

    print(f"\n--- Итого ---")
    for pt, cnt in sorted(by_type.items()):
        print(f"  {pt:25s}: {cnt}")
    print(f"\n  Сохранено: {saved}")
    print(f"  Всего в БД: {total}")
    print(f"  Время: {elapsed}s")
    print("=" * 60)

    if own_client:
        client.close()

    return all_alerts


async def main():
    await run_detection()


if __name__ == "__main__":
    asyncio.run(main())
