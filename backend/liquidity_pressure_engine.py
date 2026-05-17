"""
Liquidity Pressure Engine
==========================
Оценивает давление ликвидности на рынок.

Метрики:
  - DEX buy pressure (inflow в DEX)
  - DEX sell pressure (outflow из DEX)
  - Exchange deposits (inflow в CEX — bearish)
  - Exchange withdrawals (outflow из CEX — bullish)
  - Bridge liquidity (cross-chain flow)

Формула:
  pressure_score = dex_buy - dex_sell + exchange_withdraw - exchange_deposit

Usage:
  python liquidity_pressure_engine.py
"""

import asyncio
import os
import time
from datetime import datetime, timezone
from collections import defaultdict
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017/intelligence_engine")
DB_NAME = os.environ.get("DB_NAME", "intelligence_engine")


async def compute_pressure(db=None, client=None):
    own_client = False
    if db is None:
        client = AsyncIOMotorClient(MONGO_URL)
        db = client[DB_NAME]
        own_client = True

    start = time.time()
    print("=" * 60)
    print("LIQUIDITY PRESSURE ENGINE")
    print("=" * 60)

    # Загрузить типы нод
    node_types = {}
    cursor = db["graph_nodes"].find({}, {"_id": 0, "id": 1, "type": 1})
    async for n in cursor:
        node_types[n["id"]] = n.get("type", "wallet")

    # Агрегация потоков
    metrics = {
        "dex_inflow": 0,     # buy pressure
        "dex_outflow": 0,    # sell pressure
        "cex_deposits": 0,   # bearish
        "cex_withdrawals": 0, # bullish
        "bridge_inflow": 0,
        "bridge_outflow": 0,
        "total_volume": 0,
        "total_tx": 0,
    }

    cursor = db["graph_relations"].find(
        {}, {"_id": 0, "source_id": 1, "target_id": 1,
             "total_amount_usd": 1, "total_tx_count": 1}
    )
    async for rel in cursor:
        src = rel.get("source_id", "")
        tgt = rel.get("target_id", "")
        amount = rel.get("total_amount_usd", 0) or 0
        tx = rel.get("total_tx_count", 1) or 1

        src_type = node_types.get(src, "wallet")
        tgt_type = node_types.get(tgt, "wallet")

        metrics["total_volume"] += amount
        metrics["total_tx"] += tx

        if tgt_type == "dex":
            metrics["dex_inflow"] += amount
        if src_type == "dex":
            metrics["dex_outflow"] += amount
        if tgt_type == "cex":
            metrics["cex_deposits"] += amount
        if src_type == "cex":
            metrics["cex_withdrawals"] += amount
        if tgt_type == "bridge":
            metrics["bridge_inflow"] += amount
        if src_type == "bridge":
            metrics["bridge_outflow"] += amount

    # Вычислить давление
    dex_pressure = metrics["dex_inflow"] - metrics["dex_outflow"]
    exchange_pressure = metrics["cex_withdrawals"] - metrics["cex_deposits"]
    net_pressure = dex_pressure + exchange_pressure

    # Нормализованный score (-1 to +1)
    max_flow = max(metrics["total_volume"], 1)
    pressure_score = round(max(-1, min(1, net_pressure / max_flow)), 4)

    # Определить тренд
    if pressure_score > 0.1:
        trend = "bullish"
    elif pressure_score < -0.1:
        trend = "bearish"
    else:
        trend = "neutral"

    result = {
        "pressure_score": pressure_score,
        "trend": trend,
        "metrics": {k: round(v, 2) for k, v in metrics.items()},
        "dex_net_pressure": round(dex_pressure, 2),
        "exchange_net_pressure": round(exchange_pressure, 2),
        "net_pressure": round(net_pressure, 2),
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }

    # Сохранить
    await db["graph_liquidity_pressure"].update_one(
        {"snapshot_type": "latest"},
        {"$set": {"snapshot_type": "latest", **result}},
        upsert=True,
    )

    elapsed = round(time.time() - start, 1)
    print(f"\n--- Результат ---")
    print(f"  Pressure Score: {pressure_score} ({trend})")
    print(f"  DEX: in=${metrics['dex_inflow']:,.0f} out=${metrics['dex_outflow']:,.0f} net=${dex_pressure:,.0f}")
    print(f"  CEX: deposits=${metrics['cex_deposits']:,.0f} withdrawals=${metrics['cex_withdrawals']:,.0f} net=${exchange_pressure:,.0f}")
    print(f"  Bridge: in=${metrics['bridge_inflow']:,.0f} out=${metrics['bridge_outflow']:,.0f}")
    print(f"  Total: ${metrics['total_volume']:,.0f} ({metrics['total_tx']} tx)")
    print(f"  Время: {elapsed}s")
    print("=" * 60)

    if own_client:
        client.close()

    return result


async def main():
    await compute_pressure()


if __name__ == "__main__":
    asyncio.run(main())
