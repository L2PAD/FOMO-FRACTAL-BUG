"""Sentiment routes — real sentiment intelligence for mobile app."""
import asyncio
import logging
from fastapi import APIRouter, Query
from services.sentiment_service import get_sentiment_for_asset, run_sentiment_ingestion

logger = logging.getLogger(__name__)
router = APIRouter()

# Background ingestion state
_ingestion_running = False


async def _ensure_fresh_data(asset: str):
    """Auto-ingest if data is stale or missing."""
    global _ingestion_running
    data = get_sentiment_for_asset(asset)
    if data.get("status") == "no_data" and not _ingestion_running:
        _ingestion_running = True
        try:
            logger.info("[Sentiment] Auto-ingesting fresh data...")
            await run_sentiment_ingestion(["BTC", "ETH", "SOL"])
        except Exception as e:
            logger.error(f"[Sentiment] Auto-ingestion error: {e}")
        finally:
            _ingestion_running = False


@router.get("/sentiment")
async def get_sentiment(asset: str = Query(default="BTC")):
    """Get aggregated sentiment data from real sources."""
    asset = asset.upper().strip()
    data = get_sentiment_for_asset(asset)
    # Auto-ingest in background if no data
    if data.get("status") == "no_data":
        asyncio.create_task(_ensure_fresh_data(asset))
    return data


@router.post("/sentiment/ingest")
async def trigger_ingestion():
    """Manually trigger sentiment data ingestion."""
    result = await run_sentiment_ingestion(["BTC", "ETH", "SOL"])
    return result
