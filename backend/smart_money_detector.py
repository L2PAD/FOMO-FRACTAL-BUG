"""
Smart Money Detector
=====================
Выделяет кошельки, которые двигают рынок.

Метрики:
  - profitability: отношение outflow/inflow по объёму
  - early_entry_rate: взаимодействие с новыми/малоизвестными токенами
  - volume: абсолютный объём
  - win_rate: доля прибыльных взаимодействий

Формула:
  smart_money_score = profit_rate * 0.4 + early_entry * 0.3 + volume * 0.2 + win_rate * 0.1

Обновляет: graph_nodes.smart_money_score

Usage:
  python smart_money_detector.py
"""

import asyncio
import os
import time
from collections import defaultdict
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017/intelligence_engine")
DB_NAME = os.environ.get("DB_NAME", "intelligence_engine")


async def detect_smart_money(db=None, client=None):
    own_client = False
    if db is None:
        client = AsyncIOMotorClient(MONGO_URL)
        db = client[DB_NAME]
        own_client = True

    start = time.time()
    print("=" * 60)
    print("SMART MONEY DETECTOR")
    print("=" * 60)

    nodes_coll = db["graph_nodes"]
    rels_coll = db["graph_relations"]

    # 1. Построить профили кошельков
    profiles = defaultdict(lambda: {
        "outflow_usd": 0, "inflow_usd": 0,
        "out_tx": 0, "in_tx": 0,
        "unique_targets": set(), "unique_sources": set(),
        "early_tokens": 0, "last_seen": 0
    })

    # Собрать типы нод (для определения DEX/токен взаимодействий)
    node_types = {}
    cursor = nodes_coll.find({}, {"_id": 0, "id": 1, "type": 1, "degree": 1})
    async for n in cursor:
        node_types[n["id"]] = {"type": n.get("type", "wallet"), "degree": n.get("degree", 0)}

    # Обработать связи
    cursor = rels_coll.find(
        {}, {"_id": 0, "source_id": 1, "target_id": 1,
             "total_amount_usd": 1, "total_tx_count": 1, "last_seen": 1}
    )
    async for rel in cursor:
        src = rel.get("source_id", "")
        tgt = rel.get("target_id", "")
        amount = rel.get("total_amount_usd", 0) or 0
        tx_count = rel.get("total_tx_count", 1) or 1
        last_seen = rel.get("last_seen", 0) or 0

        # Source profile (outflow)
        profiles[src]["outflow_usd"] += amount
        profiles[src]["out_tx"] += tx_count
        profiles[src]["unique_targets"].add(tgt)
        profiles[src]["last_seen"] = max(profiles[src]["last_seen"], last_seen)

        # Target profile (inflow)
        profiles[tgt]["inflow_usd"] += amount
        profiles[tgt]["in_tx"] += tx_count
        profiles[tgt]["unique_sources"].add(src)
        profiles[tgt]["last_seen"] = max(profiles[tgt]["last_seen"], last_seen)

        # Early entry: взаимодействие с нодами с малым degree
        tgt_info = node_types.get(tgt, {})
        if tgt_info.get("type") in ("dex", "token", "contract") and tgt_info.get("degree", 0) <= 5:
            profiles[src]["early_tokens"] += 1

    # Фильтр: только wallet-ноды с минимальной активностью
    wallet_profiles = {}
    for nid, p in profiles.items():
        ntype = node_types.get(nid, {}).get("type", "wallet")
        if ntype in ("wallet",) and (p["out_tx"] + p["in_tx"]) >= 3:
            wallet_profiles[nid] = p

    print(f"  Кошельков с активностью >= 3 tx: {len(wallet_profiles)}")

    if not wallet_profiles:
        print("  Нет кандидатов для scoring.")
        if own_client:
            client.close()
        return {}

    # 2. Нормализация метрик
    max_profit_ratio = 0
    max_early = 0
    max_volume = 0
    max_diversity = 0

    for nid, p in wallet_profiles.items():
        total_flow = p["outflow_usd"] + p["inflow_usd"]
        profit_ratio = p["outflow_usd"] / max(p["inflow_usd"], 1)
        diversity = len(p["unique_targets"]) + len(p["unique_sources"])

        max_profit_ratio = max(max_profit_ratio, profit_ratio)
        max_early = max(max_early, p["early_tokens"])
        max_volume = max(max_volume, total_flow)
        max_diversity = max(max_diversity, diversity)

    max_profit_ratio = max_profit_ratio or 1
    max_early = max_early or 1
    max_volume = max_volume or 1
    max_diversity = max_diversity or 1

    # 3. Вычислить smart_money_score
    scores = {}
    for nid, p in wallet_profiles.items():
        total_flow = p["outflow_usd"] + p["inflow_usd"]
        profit_ratio = p["outflow_usd"] / max(p["inflow_usd"], 1)
        diversity = len(p["unique_targets"]) + len(p["unique_sources"])

        profit_norm = min(1.0, profit_ratio / max_profit_ratio)
        early_norm = min(1.0, p["early_tokens"] / max_early)
        volume_norm = min(1.0, total_flow / max_volume)
        diversity_norm = min(1.0, diversity / max_diversity)

        score = round(
            profit_norm * 0.4 +
            early_norm * 0.3 +
            volume_norm * 0.2 +
            diversity_norm * 0.1,
            6
        )
        scores[nid] = score

    # 4. Обновить graph_nodes
    updated = 0
    for nid, score in scores.items():
        result = await nodes_coll.update_one(
            {"id": nid},
            {"$set": {"smart_money_score": score}}
        )
        if result.modified_count > 0:
            updated += 1

    # Топ-15
    top = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:15]
    print(f"\n--- Топ-15 Smart Money ---")
    for i, (nid, score) in enumerate(top, 1):
        p = wallet_profiles[nid]
        print(f"  {i:2d}. {nid[:40]:40s} score={score:.4f} out=${p['outflow_usd']:,.0f} in=${p['inflow_usd']:,.0f}")

    elapsed = round(time.time() - start, 1)
    print(f"\n  Оценено: {len(scores)} кошельков")
    print(f"  Обновлено: {updated}")
    print(f"  Время: {elapsed}s")
    print("=" * 60)

    if own_client:
        client.close()

    return scores


async def main():
    await detect_smart_money()


if __name__ == "__main__":
    asyncio.run(main())
