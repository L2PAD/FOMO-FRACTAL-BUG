"""
One-shot manual trigger for polymarket ingestion.

Used by `module_manager.sh run polymarket`. Loads env from /app/backend/.env
implicitly via cwd, then calls the async ingest_polymarket(db) entry.
"""
import asyncio
import os
import sys

sys.path.insert(0, '/app/backend')

from motor.motor_asyncio import AsyncIOMotorClient
from miniapp.polymarket_ingestion import ingest_polymarket


async def main():
    mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
    db_name = os.environ.get('DB_NAME', 'fomo_mobile')
    db = AsyncIOMotorClient(mongo_url)[db_name]
    result = await ingest_polymarket(db)
    print(result)


if __name__ == '__main__':
    asyncio.run(main())
