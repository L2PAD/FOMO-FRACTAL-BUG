"""
MongoDB Candle Store - Fallback for ClickHouse
==============================================
Stores candles in MongoDB when ClickHouse is not available.
Provides same interface as ClickHouseStore.
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)


class MongoDBCandleStore:
    """
    MongoDB-based candle storage.
    Fallback when ClickHouse is not available.
    """
    
    def __init__(self, db):
        self.db = db
        self._connected = True  # MongoDB always connected via motor
    
    async def ensure_indexes(self):
        """Create indexes for efficient queries"""
        try:
            await self.db.market_candles.create_index(
                [("exchange", 1), ("symbol", 1), ("tf", 1), ("ts", -1)],
                unique=True
            )
            await self.db.market_candles.create_index([("ts", -1)])
            await self.db.market_candles.create_index([("symbol", 1)])
            logger.info("[MongoCandleStore] Indexes created")
        except Exception as e:
            logger.debug(f"[MongoCandleStore] Index creation: {e}")
    
    async def insert_candles(self, candles: List[Dict[str, Any]]) -> int:
        """
        Batch insert/update candles.
        Uses upsert to handle duplicates.
        """
        if not candles:
            return 0
        
        inserted = 0
        for candle in candles:
            try:
                # Normalize timestamp
                ts = candle.get("ts") or candle.get("timestamp")
                if isinstance(ts, (int, float)):
                    ts = datetime.fromtimestamp(ts / 1000 if ts > 1e12 else ts, tz=timezone.utc)
                
                doc = {
                    "exchange": candle.get("exchange", "unknown"),
                    "symbol": candle.get("symbol", ""),
                    "tf": candle.get("tf", "1m"),
                    "ts": ts,
                    "open": float(candle.get("open", 0)),
                    "high": float(candle.get("high", 0)),
                    "low": float(candle.get("low", 0)),
                    "close": float(candle.get("close", 0)),
                    "volume": float(candle.get("volume", 0)),
                    "updated_at": datetime.now(timezone.utc)
                }
                
                await self.db.market_candles.update_one(
                    {
                        "exchange": doc["exchange"],
                        "symbol": doc["symbol"],
                        "tf": doc["tf"],
                        "ts": doc["ts"]
                    },
                    {"$set": doc},
                    upsert=True
                )
                inserted += 1
            except Exception as e:
                logger.debug(f"[MongoCandleStore] Insert error: {e}")
        
        return inserted
    
    async def get_candles(
        self,
        exchange: str,
        symbol: str,
        tf: str = "1m",
        start: datetime = None,
        end: datetime = None,
        limit: int = 1000
    ) -> List[Dict]:
        """Query candles with time range"""
        query = {
            "exchange": exchange,
            "symbol": symbol,
            "tf": tf
        }
        
        if start or end:
            query["ts"] = {}
            if start:
                query["ts"]["$gte"] = start
            if end:
                query["ts"]["$lte"] = end
        
        cursor = self.db.market_candles.find(
            query, 
            {"_id": 0}
        ).sort("ts", -1).limit(limit)
        
        return await cursor.to_list(limit)
    
    async def get_latest_candle(
        self,
        exchange: str,
        symbol: str,
        tf: str = "1m"
    ) -> Optional[Dict]:
        """Get most recent candle"""
        return await self.db.market_candles.find_one(
            {"exchange": exchange, "symbol": symbol, "tf": tf},
            {"_id": 0},
            sort=[("ts", -1)]
        )
    
    async def get_ohlcv(
        self,
        exchange: str,
        symbol: str,
        tf: str = "1m",
        periods: int = 100
    ) -> List[List]:
        """Get OHLCV as list format [ts, o, h, l, c, v]"""
        candles = await self.get_candles(exchange, symbol, tf, limit=periods)
        
        result = []
        for c in reversed(candles):  # Oldest first
            ts = c["ts"]
            if isinstance(ts, datetime):
                ts = int(ts.timestamp() * 1000)
            result.append([
                ts,
                c["open"],
                c["high"],
                c["low"],
                c["close"],
                c["volume"]
            ])
        
        return result
    
    async def aggregate_timeframe(
        self,
        exchange: str,
        symbol: str,
        source_tf: str,
        target_tf: str,
        limit: int = 100
    ) -> List[Dict]:
        """
        Aggregate candles from lower to higher timeframe.
        e.g., 1m -> 5m, 5m -> 15m
        """
        # Timeframe multipliers
        tf_minutes = {
            "1m": 1, "5m": 5, "15m": 15, "30m": 30,
            "1h": 60, "4h": 240, "1d": 1440
        }
        
        source_min = tf_minutes.get(source_tf, 1)
        target_min = tf_minutes.get(target_tf, 5)
        ratio = target_min // source_min
        
        # Get source candles
        source_candles = await self.get_candles(
            exchange, symbol, source_tf, 
            limit=limit * ratio
        )
        
        if not source_candles:
            return []
        
        # Group and aggregate
        aggregated = []
        for i in range(0, len(source_candles), ratio):
            group = source_candles[i:i+ratio]
            if len(group) < ratio:
                continue
            
            aggregated.append({
                "exchange": exchange,
                "symbol": symbol,
                "tf": target_tf,
                "ts": group[-1]["ts"],  # Last candle's time
                "open": group[-1]["open"],
                "high": max(c["high"] for c in group),
                "low": min(c["low"] for c in group),
                "close": group[0]["close"],
                "volume": sum(c["volume"] for c in group)
            })
        
        return aggregated
    
    async def stats(self) -> Dict:
        """Get store statistics"""
        try:
            total = await self.db.market_candles.count_documents({})
            
            # Count by exchange
            pipeline = [
                {"$group": {"_id": "$exchange", "count": {"$sum": 1}}}
            ]
            by_exchange = {}
            async for doc in self.db.market_candles.aggregate(pipeline):
                by_exchange[doc["_id"]] = doc["count"]
            
            # Latest candle time
            latest = await self.db.market_candles.find_one(
                {}, {"ts": 1}, sort=[("ts", -1)]
            )
            
            return {
                "store": "mongodb",
                "total_candles": total,
                "by_exchange": by_exchange,
                "latest_ts": latest["ts"].isoformat() if latest else None
            }
        except Exception as e:
            return {"store": "mongodb", "error": str(e)}


# Factory function
def create_candle_store(db):
    """Create candle store - uses MongoDB as fallback"""
    return MongoDBCandleStore(db)
