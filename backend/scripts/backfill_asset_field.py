"""Backfill asset field for existing exchange_observations."""
import os
from dotenv import load_dotenv
from pathlib import Path
from pymongo import MongoClient

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
col = db["exchange_observations"]

# Backfill USDT pairs: "BTCUSDT" → asset = "BTC"
result = col.update_many(
    {"asset": {"$exists": False}, "symbol": {"$regex": "^[A-Z]+USDT$"}},
    [{"$set": {"asset": {"$substrBytes": ["$symbol", 0, {"$subtract": [{"$strLenBytes": "$symbol"}, 4]}]}}}],
)
print(f"Updated {result.modified_count} documents with asset field")

# Verify
assets = col.distinct("asset")
print(f"Unique assets: {len(assets)}")

for a in ["BTC", "ETH", "SOL"]:
    n = col.count_documents({"asset": a})
    print(f"  {a}: {n}")
