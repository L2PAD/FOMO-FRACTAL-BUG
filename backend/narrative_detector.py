"""
Narrative Detector
===================
Обнаруживает нарративы: паттерны группового поведения.

Ищет:
  - Sector accumulation: кластеры покупают один сектор
  - Capital rotation: переток между секторами
  - Cluster buying: группы кошельков покупают одинаковые цели

Usage:
  python narrative_detector.py
"""

import asyncio
import os
import time
from datetime import datetime, timezone
from collections import defaultdict
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017/intelligence_engine")
DB_NAME = os.environ.get("DB_NAME", "intelligence_engine")


async def detect_narratives(db=None, client=None):
    own_client = False
    if db is None:
        client = AsyncIOMotorClient(MONGO_URL)
        db = client[DB_NAME]
        own_client = True

    start = time.time()
    print("=" * 60)
    print("NARRATIVE DETECTOR")
    print("=" * 60)

    nodes_coll = db["graph_nodes"]
    rels_coll = db["graph_relations"]

    # 1. Загрузить ноды
    node_info = {}
    cursor = nodes_coll.find(
        {}, {"_id": 0, "id": 1, "type": 1, "label": 1,
             "cluster_id": 1, "smart_money_score": 1}
    )
    async for n in cursor:
        node_info[n["id"]] = n

    # 2. Агрегировать: какие цели покупают какие группы
    target_buyers = defaultdict(lambda: {
        "amount": 0, "tx": 0, "wallets": set(),
        "smart_wallets": set(), "clusters": set()
    })

    cursor = rels_coll.find(
        {}, {"_id": 0, "source_id": 1, "target_id": 1,
             "total_amount_usd": 1, "total_tx_count": 1}
    )
    async for rel in cursor:
        src = rel.get("source_id", "")
        tgt = rel.get("target_id", "")
        amount = rel.get("total_amount_usd", 0) or 0
        tx = rel.get("total_tx_count", 1) or 1

        src_info = node_info.get(src, {})
        tgt_info = node_info.get(tgt, {})

        # Только wallet/smart money → dex/token/contract
        if src_info.get("type") in ("wallet",) and tgt_info.get("type") in ("dex", "token", "contract"):
            tgt_key = tgt_info.get("label", tgt[:20])
            target_buyers[tgt_key]["amount"] += amount
            target_buyers[tgt_key]["tx"] += tx
            target_buyers[tgt_key]["wallets"].add(src)

            if (src_info.get("smart_money_score") or 0) > 0.5:
                target_buyers[tgt_key]["smart_wallets"].add(src)

            cluster_id = src_info.get("cluster_id")
            if cluster_id:
                target_buyers[tgt_key]["clusters"].add(cluster_id)

    # 3. Detect narratives
    narratives = []
    now_iso = datetime.now(timezone.utc).isoformat()

    # a) Sector accumulation: много кошельков → одна цель
    for target, data in sorted(target_buyers.items(), key=lambda x: x[1]["amount"], reverse=True):
        if len(data["wallets"]) >= 3 and data["amount"] > 10000:
            narrative = {
                "narrative_type": "sector_accumulation",
                "target": target,
                "wallets": len(data["wallets"]),
                "smart_wallets": len(data["smart_wallets"]),
                "clusters": list(data["clusters"])[:5],
                "amount_usd": round(data["amount"], 2),
                "tx_count": data["tx"],
                "confidence": min(0.9, 0.3 + len(data["wallets"]) * 0.05 + len(data["smart_wallets"]) * 0.1),
                "detected_at": now_iso,
            }
            narratives.append(narrative)

    # b) Cluster buying: несколько кластеров → одна цель
    for target, data in target_buyers.items():
        if len(data["clusters"]) >= 2 and data["amount"] > 50000:
            narrative = {
                "narrative_type": "cluster_buying",
                "target": target,
                "clusters": list(data["clusters"])[:5],
                "cluster_count": len(data["clusters"]),
                "amount_usd": round(data["amount"], 2),
                "confidence": min(0.9, 0.4 + len(data["clusters"]) * 0.15),
                "detected_at": now_iso,
            }
            narratives.append(narrative)

    # c) Capital rotation: smart money → несколько целей одного типа
    smart_targets = defaultdict(float)
    for target, data in target_buyers.items():
        if len(data["smart_wallets"]) >= 1:
            smart_targets[target] += data["amount"]

    if len(smart_targets) >= 3:
        top_smart = sorted(smart_targets.items(), key=lambda x: x[1], reverse=True)[:5]
        total_smart_flow = sum(v for _, v in top_smart)
        if total_smart_flow > 50000:
            narratives.append({
                "narrative_type": "capital_rotation",
                "targets": [{"target": t, "amount": round(a, 2)} for t, a in top_smart],
                "total_amount_usd": round(total_smart_flow, 2),
                "confidence": min(0.85, 0.4 + len(top_smart) * 0.1),
                "detected_at": now_iso,
            })

    # 4. Сохранить
    signals_coll = db["graph_alpha_signals"]
    for n in narratives:
        n["signal_type"] = n["narrative_type"]
        n["signal_id"] = f"{n['narrative_type']}:{now_iso[:10]}"
        n["generated_at"] = now_iso
        n["direction"] = "bullish" if n.get("smart_wallets", 0) > 0 else "neutral"

    if narratives:
        for n in narratives:
            await signals_coll.update_one(
                {"signal_id": n["signal_id"], "target": n.get("target", "")},
                {"$set": n},
                upsert=True,
            )

    elapsed = round(time.time() - start, 1)
    print(f"\n--- Нарративы ---")
    for n in narratives[:10]:
        desc = n.get("target", "multi-target")
        print(f"  [{n['narrative_type']}] {desc}: ${n.get('amount_usd', n.get('total_amount_usd', 0)):,.0f} conf={n.get('confidence', 0):.2f}")

    print(f"\n  Всего: {len(narratives)}")
    print(f"  Время: {elapsed}s")
    print("=" * 60)

    if own_client:
        client.close()

    return narratives


async def main():
    await detect_narratives()


if __name__ == "__main__":
    asyncio.run(main())
