"""
Capital Flow Signal Engine
============================
Анализирует потоки капитала и генерирует сигналы:

- DEX inflow: рост ликвидности в DEX
- CEX inflow: приток на биржи (bearish)
- CEX outflow: вывод с бирж (bullish)
- Bridge inflow: миграция ликвидности
- Cluster inflow: капитал кластеров

Сигналы:
- capital_accumulation
- liquidity_migration
- exchange_inflow_spike
- exchange_outflow_spike
- cluster_rotation

Usage:
  python flow_signal_engine.py
"""

import asyncio
import os
import time
from datetime import datetime, timezone
from collections import defaultdict
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017/intelligence_engine")
DB_NAME = os.environ.get("DB_NAME", "intelligence_engine")

SPIKE_THRESHOLD = 2.0  # 2x среднего


async def generate_flow_signals(db=None, client=None):
    own_client = False
    if db is None:
        client = AsyncIOMotorClient(MONGO_URL)
        db = client[DB_NAME]
        own_client = True

    start = time.time()
    print("=" * 60)
    print("CAPITAL FLOW SIGNAL ENGINE")
    print("=" * 60)

    rels_coll = db["graph_relations"]
    nodes_coll = db["graph_nodes"]
    signals_coll = db["graph_alpha_signals"]

    # 1. Загрузить типы нод
    node_types = {}
    cursor = nodes_coll.find(
        {}, {"_id": 0, "id": 1, "type": 1, "label": 1, "smart_money_score": 1, "cluster_id": 1}
    )
    async for n in cursor:
        node_types[n["id"]] = n

    # 2. Агрегировать потоки по типу
    flow_by_type = defaultdict(lambda: {"inflow": 0, "outflow": 0, "tx": 0, "wallets": set()})

    cursor = rels_coll.find(
        {}, {"_id": 0, "source_id": 1, "target_id": 1,
             "total_amount_usd": 1, "total_tx_count": 1, "last_seen": 1}
    )
    async for rel in cursor:
        src = rel.get("source_id", "")
        tgt = rel.get("target_id", "")
        amount = rel.get("total_amount_usd", 0) or 0
        tx = rel.get("total_tx_count", 1) or 1

        src_type = node_types.get(src, {}).get("type", "wallet")
        tgt_type = node_types.get(tgt, {}).get("type", "wallet")

        # CEX flows
        if tgt_type == "cex":
            flow_by_type["cex"]["inflow"] += amount
            flow_by_type["cex"]["tx"] += tx
            flow_by_type["cex"]["wallets"].add(src)
        if src_type == "cex":
            flow_by_type["cex"]["outflow"] += amount

        # DEX flows
        if tgt_type == "dex":
            flow_by_type["dex"]["inflow"] += amount
            flow_by_type["dex"]["tx"] += tx
            flow_by_type["dex"]["wallets"].add(src)
        if src_type == "dex":
            flow_by_type["dex"]["outflow"] += amount

        # Bridge flows
        if tgt_type == "bridge":
            flow_by_type["bridge"]["inflow"] += amount
            flow_by_type["bridge"]["tx"] += tx
        if src_type == "bridge":
            flow_by_type["bridge"]["outflow"] += amount

    # 3. Smart money flows
    smart_money_targets = defaultdict(lambda: {"amount": 0, "wallets": set(), "tx": 0})
    cursor = rels_coll.find(
        {}, {"_id": 0, "source_id": 1, "target_id": 1,
             "total_amount_usd": 1, "total_tx_count": 1}
    )
    async for rel in cursor:
        src = rel.get("source_id", "")
        tgt = rel.get("target_id", "")
        src_info = node_types.get(src, {})
        if (src_info.get("smart_money_score") or 0) > 0.5:
            tgt_info = node_types.get(tgt, {})
            tgt_label = tgt_info.get("label", tgt[:20])
            smart_money_targets[tgt_label]["amount"] += rel.get("total_amount_usd", 0) or 0
            smart_money_targets[tgt_label]["wallets"].add(src)
            smart_money_targets[tgt_label]["tx"] += rel.get("total_tx_count", 0) or 0

    # 4. Cluster flows
    cluster_flows = defaultdict(lambda: {"outflow": 0, "inflow": 0, "targets": defaultdict(float)})
    cursor = rels_coll.find(
        {}, {"_id": 0, "source_id": 1, "target_id": 1, "total_amount_usd": 1}
    )
    async for rel in cursor:
        src = rel.get("source_id", "")
        tgt = rel.get("target_id", "")
        amount = rel.get("total_amount_usd", 0) or 0
        src_cluster = node_types.get(src, {}).get("cluster_id")
        if src_cluster:
            cluster_flows[src_cluster]["outflow"] += amount
            tgt_label = node_types.get(tgt, {}).get("label", tgt[:20])
            cluster_flows[src_cluster]["targets"][tgt_label] += amount

    # 5. Генерация сигналов
    signals = []
    now_iso = datetime.now(timezone.utc).isoformat()

    # CEX outflow > inflow → bullish
    cex = flow_by_type.get("cex", {})
    if cex.get("outflow", 0) > cex.get("inflow", 0) * 1.2:
        signals.append({
            "signal_type": "exchange_outflow_spike",
            "description": f"CEX outflow (${cex['outflow']:,.0f}) превышает inflow (${cex['inflow']:,.0f})",
            "amount_usd": round(cex["outflow"] - cex.get("inflow", 0), 2),
            "confidence": min(0.9, 0.5 + (cex["outflow"] / max(cex.get("inflow", 1), 1) - 1) * 0.3),
            "direction": "bullish",
        })

    # Bridge volume
    bridge = flow_by_type.get("bridge", {})
    if bridge.get("inflow", 0) > 100000:
        signals.append({
            "signal_type": "bridge_liquidity_migration",
            "description": f"Bridge inflow ${bridge['inflow']:,.0f}",
            "amount_usd": round(bridge["inflow"], 2),
            "confidence": min(0.85, 0.4 + bridge["inflow"] / 1000000),
            "direction": "neutral",
        })

    # Smart money accumulation
    for target, data in sorted(smart_money_targets.items(), key=lambda x: x[1]["amount"], reverse=True)[:5]:
        if len(data["wallets"]) >= 2 and data["amount"] > 10000:
            signals.append({
                "signal_type": "smart_money_accumulation",
                "description": f"{len(data['wallets'])} smart wallets → {target}, ${data['amount']:,.0f}",
                "target": target,
                "wallets": len(data["wallets"]),
                "amount_usd": round(data["amount"], 2),
                "confidence": min(0.9, 0.4 + len(data["wallets"]) * 0.15),
                "direction": "bullish",
            })

    # Cluster accumulation
    for cluster_id, data in sorted(cluster_flows.items(), key=lambda x: x[1]["outflow"], reverse=True)[:3]:
        if data["outflow"] > 50000:
            top_targets = sorted(data["targets"].items(), key=lambda x: x[1], reverse=True)[:3]
            signals.append({
                "signal_type": "cluster_accumulation",
                "description": f"Cluster {cluster_id}: outflow ${data['outflow']:,.0f}",
                "cluster_id": cluster_id,
                "amount_usd": round(data["outflow"], 2),
                "top_targets": [{"target": t, "amount": round(a, 2)} for t, a in top_targets],
                "confidence": 0.6,
                "direction": "neutral",
            })

    # 6. Сохранить сигналы
    for s in signals:
        s["generated_at"] = now_iso
        s["signal_id"] = f"{s['signal_type']}:{now_iso[:10]}"

    if signals:
        # Очистить старые сигналы этого дня
        today = now_iso[:10]
        await signals_coll.delete_many({"signal_id": {"$regex": f":{today}$"}})
        await signals_coll.insert_many(signals)

    await signals_coll.create_index("signal_type")
    await signals_coll.create_index([("generated_at", -1)])
    await signals_coll.create_index("signal_id")

    elapsed = round(time.time() - start, 1)
    print(f"\n--- Сигналы ---")
    for s in signals:
        print(f"  [{s['signal_type']}] {s['description']} conf={s['confidence']:.2f} dir={s['direction']}")

    print(f"\n  Всего сигналов: {len(signals)}")
    print(f"  Время: {elapsed}s")
    print("=" * 60)

    if own_client:
        client.close()

    return signals


async def main():
    await generate_flow_signals()


if __name__ == "__main__":
    asyncio.run(main())
