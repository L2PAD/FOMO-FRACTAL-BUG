"""
Run the Intelligence-OS Orchestrator once, executing all enabled specialized parsers
(CryptoRank, Dropstab, ICODrops, CoinGecko, news_rss, etc.).

Targets the same MongoDB instance/database that the FastAPI backend uses
(MONGO_URL + DB_NAME from /app/backend/.env).
"""

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from motor.motor_asyncio import AsyncIOMotorClient

from intelligence_os.ingestion.orchestrator import IngestionOrchestrator
from intelligence_os.ingestion.parser_factory import create_parser_factory


async def main():
    mongo_url = os.environ["MONGO_URL"]
    db_name = os.environ.get("DB_NAME", "fomo_mobile")
    print(f"[orchestrator] target db = {db_name} @ {mongo_url}")

    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    factory = create_parser_factory(db)
    orch = IngestionOrchestrator(db, factory)
    result = await orch.run_all()

    print("\n=========== ORCHESTRATOR RESULT ===========")
    print(json.dumps(result, indent=2, default=str)[:5000])
    print("===========================================\n")

    # Per-collection counts after run
    for col in [
        "raw_funding",
        "raw_unlocks",
        "raw_activities",
        "raw_projects",
        "raw_ico",
        "raw_market_data",
        "raw_news",
    ]:
        cnt = await db[col].count_documents({})
        print(f"  {col}: {cnt} docs")

    client.close()


if __name__ == "__main__":
    asyncio.run(main())
