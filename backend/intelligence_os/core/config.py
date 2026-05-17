"""
Crypto Intelligence Operating System — Core Config
"""
import os

MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME", "institutional")

INGESTION_INTERVAL_HOURS = 6
CANONICAL_BATCH_SIZE = 500
GRAPH_BUILD_BATCH_SIZE = 1000

FUZZY_MATCH_THRESHOLD = 0.85
SYMBOL_MATCH_BOOST = 0.95

SOURCE_WEIGHTS = {
    "cryptorank": 0.9,
    "dropstab": 0.85,
    "coingecko": 0.8,
    "chainbroker": 0.75,
    "icodrops": 0.7,
    "dropsearn": 0.65,
    "tokenunlocks": 0.8,
    "news_rss": 0.6,
    "manual": 1.0,
}
