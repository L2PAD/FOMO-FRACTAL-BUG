"""
Sentiment Trend Analytics
==========================
Tracks sentiment changes over time for assets and overall market.

Features:
- Sentiment history by asset
- Overall market sentiment trend
- Sentiment shift detection
- Hourly/daily/weekly aggregation

Usage:
    analytics = SentimentTrendAnalytics(db)
    trend = await analytics.get_asset_trend("BTC", period="24h")
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# SENTIMENT TREND ANALYTICS
# ═══════════════════════════════════════════════════════════════

class SentimentTrendAnalytics:
    """
    Analyzes sentiment trends over time.
    
    Provides:
    - Asset-specific sentiment history
    - Market-wide sentiment aggregation
    - Trend direction detection
    - Shift alerts
    """
    
    def __init__(self, db):
        self.db = db
    
    async def get_asset_trend(
        self,
        asset: str,
        period: str = "24h",
        interval: str = "1h"
    ) -> Dict[str, Any]:
        """
        Get sentiment trend for a specific asset.
        
        Args:
            asset: Asset symbol (BTC, ETH, etc.)
            period: Time period (1h, 6h, 24h, 7d, 30d)
            interval: Aggregation interval (15m, 1h, 4h, 1d)
        
        Returns:
            Trend data with timestamps and sentiment values
        """
        # Parse period
        period_hours = {
            "1h": 1, "6h": 6, "12h": 12, "24h": 24,
            "48h": 48, "7d": 168, "30d": 720
        }.get(period, 24)
        
        # Parse interval
        interval_minutes = {
            "15m": 15, "30m": 30, "1h": 60, "4h": 240, "1d": 1440
        }.get(interval, 60)
        
        now = datetime.now(timezone.utc)
        start_time = now - timedelta(hours=period_hours)
        
        # Query events for this asset
        cursor = self.db.news_events.find({
            "primary_assets": asset.upper(),
            "first_seen_at": {"$gte": start_time.isoformat()},
            "sentiment_score": {"$exists": True, "$ne": None}
        }).sort("first_seen_at", 1)
        
        events = await cursor.to_list(1000)
        
        if not events:
            return {
                "asset": asset.upper(),
                "period": period,
                "interval": interval,
                "data_points": [],
                "summary": {
                    "avg_sentiment": 0,
                    "trend": "neutral",
                    "event_count": 0
                }
            }
        
        # Aggregate by interval
        buckets = defaultdict(list)
        
        for event in events:
            try:
                event_time = datetime.fromisoformat(event["first_seen_at"].replace('Z', '+00:00'))
                # Round to interval
                bucket_ts = event_time.replace(
                    minute=(event_time.minute // interval_minutes) * interval_minutes if interval_minutes < 60 else 0,
                    second=0, microsecond=0
                )
                if interval_minutes >= 60:
                    bucket_ts = bucket_ts.replace(
                        hour=(event_time.hour // (interval_minutes // 60)) * (interval_minutes // 60)
                    )
                
                buckets[bucket_ts.isoformat()].append({
                    "sentiment_score": event.get("sentiment_score", 0),
                    "importance_score": event.get("importance_score", 50),
                    "event_id": event.get("id")
                })
            except Exception:
                continue
        
        # Calculate aggregates
        data_points = []
        all_sentiments = []
        
        for ts, items in sorted(buckets.items()):
            scores = [i["sentiment_score"] for i in items]
            importances = [i["importance_score"] for i in items]
            
            avg_sentiment = sum(scores) / len(scores) if scores else 0
            avg_importance = sum(importances) / len(importances) if importances else 50
            
            # Weighted average by importance
            weighted_sentiment = sum(s * (i/100) for s, i in zip(scores, importances)) / len(scores) if scores else 0
            
            all_sentiments.append(avg_sentiment)
            
            data_points.append({
                "timestamp": ts,
                "sentiment_score": round(avg_sentiment, 3),
                "weighted_sentiment": round(weighted_sentiment, 3),
                "avg_importance": round(avg_importance, 1),
                "event_count": len(items),
                "sentiment_label": "positive" if avg_sentiment > 0.1 else "negative" if avg_sentiment < -0.1 else "neutral"
            })
        
        # Calculate trend
        if len(all_sentiments) >= 2:
            first_half = all_sentiments[:len(all_sentiments)//2]
            second_half = all_sentiments[len(all_sentiments)//2:]
            first_avg = sum(first_half) / len(first_half)
            second_avg = sum(second_half) / len(second_half)
            
            if second_avg - first_avg > 0.1:
                trend = "improving"
            elif first_avg - second_avg > 0.1:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "insufficient_data"
        
        return {
            "asset": asset.upper(),
            "period": period,
            "interval": interval,
            "data_points": data_points,
            "summary": {
                "avg_sentiment": round(sum(all_sentiments) / len(all_sentiments), 3) if all_sentiments else 0,
                "min_sentiment": round(min(all_sentiments), 3) if all_sentiments else 0,
                "max_sentiment": round(max(all_sentiments), 3) if all_sentiments else 0,
                "trend": trend,
                "event_count": len(events),
                "data_point_count": len(data_points)
            }
        }
    
    async def get_market_trend(
        self,
        period: str = "24h",
        interval: str = "1h"
    ) -> Dict[str, Any]:
        """
        Get overall market sentiment trend.
        Aggregates all events regardless of asset.
        """
        # Parse period
        period_hours = {
            "1h": 1, "6h": 6, "12h": 12, "24h": 24,
            "48h": 48, "7d": 168, "30d": 720
        }.get(period, 24)
        
        now = datetime.now(timezone.utc)
        start_time = now - timedelta(hours=period_hours)
        
        # Query all events
        cursor = self.db.news_events.find({
            "first_seen_at": {"$gte": start_time.isoformat()},
            "sentiment_score": {"$exists": True, "$ne": None}
        }).sort("first_seen_at", 1)
        
        events = await cursor.to_list(2000)
        
        if not events:
            return {
                "period": period,
                "interval": interval,
                "data_points": [],
                "summary": {
                    "avg_sentiment": 0,
                    "trend": "neutral",
                    "event_count": 0
                },
                "sentiment_distribution": {
                    "positive": 0,
                    "neutral": 0,
                    "negative": 0
                }
            }
        
        # Count sentiment distribution
        positive = sum(1 for e in events if e.get("sentiment_score", 0) > 0.1)
        negative = sum(1 for e in events if e.get("sentiment_score", 0) < -0.1)
        neutral = len(events) - positive - negative
        
        # Calculate average
        sentiments = [e.get("sentiment_score", 0) for e in events]
        avg = sum(sentiments) / len(sentiments) if sentiments else 0
        
        # Calculate trend
        if len(sentiments) >= 4:
            first_half = sentiments[:len(sentiments)//2]
            second_half = sentiments[len(sentiments)//2:]
            first_avg = sum(first_half) / len(first_half)
            second_avg = sum(second_half) / len(second_half)
            
            if second_avg - first_avg > 0.05:
                trend = "improving"
            elif first_avg - second_avg > 0.05:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "stable"
        
        return {
            "period": period,
            "interval": interval,
            "summary": {
                "avg_sentiment": round(avg, 3),
                "trend": trend,
                "event_count": len(events),
                "dominant_sentiment": "positive" if positive > max(negative, neutral) else "negative" if negative > max(positive, neutral) else "neutral"
            },
            "sentiment_distribution": {
                "positive": positive,
                "neutral": neutral,
                "negative": negative,
                "positive_pct": round(positive / len(events) * 100, 1) if events else 0,
                "neutral_pct": round(neutral / len(events) * 100, 1) if events else 0,
                "negative_pct": round(negative / len(events) * 100, 1) if events else 0
            }
        }
    
    async def get_top_assets_sentiment(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get sentiment summary for top assets.
        """
        # Aggregate sentiment by asset
        pipeline = [
            {"$match": {"sentiment_score": {"$exists": True, "$ne": None}}},
            {"$unwind": "$primary_assets"},
            {"$group": {
                "_id": "$primary_assets",
                "avg_sentiment": {"$avg": "$sentiment_score"},
                "event_count": {"$sum": 1},
                "positive_count": {"$sum": {"$cond": [{"$gt": ["$sentiment_score", 0.1]}, 1, 0]}},
                "negative_count": {"$sum": {"$cond": [{"$lt": ["$sentiment_score", -0.1]}, 1, 0]}}
            }},
            {"$sort": {"event_count": -1}},
            {"$limit": limit}
        ]
        
        results = await self.db.news_events.aggregate(pipeline).to_list(limit)
        
        return [
            {
                "asset": r["_id"],
                "avg_sentiment": round(r["avg_sentiment"], 3),
                "event_count": r["event_count"],
                "positive_count": r["positive_count"],
                "negative_count": r["negative_count"],
                "sentiment_label": "positive" if r["avg_sentiment"] > 0.1 else "negative" if r["avg_sentiment"] < -0.1 else "neutral"
            }
            for r in results
        ]
    
    async def detect_sentiment_shift(
        self,
        asset: str = None,
        threshold: float = 0.3,
        window_hours: int = 6
    ) -> Dict[str, Any]:
        """
        Detect significant sentiment shifts.
        
        Args:
            asset: Specific asset or None for all
            threshold: Minimum change to trigger shift detection
            window_hours: Time window to compare
        
        Returns:
            Shift detection results
        """
        now = datetime.now(timezone.utc)
        current_window_start = now - timedelta(hours=window_hours)
        previous_window_start = current_window_start - timedelta(hours=window_hours)
        
        query = {"sentiment_score": {"$exists": True, "$ne": None}}
        if asset:
            query["primary_assets"] = asset.upper()
        
        # Current window
        current_events = await self.db.news_events.find({
            **query,
            "first_seen_at": {"$gte": current_window_start.isoformat()}
        }).to_list(500)
        
        # Previous window
        previous_events = await self.db.news_events.find({
            **query,
            "first_seen_at": {
                "$gte": previous_window_start.isoformat(),
                "$lt": current_window_start.isoformat()
            }
        }).to_list(500)
        
        current_avg = sum(e.get("sentiment_score", 0) for e in current_events) / len(current_events) if current_events else 0
        previous_avg = sum(e.get("sentiment_score", 0) for e in previous_events) / len(previous_events) if previous_events else 0
        
        change = current_avg - previous_avg
        shift_detected = abs(change) >= threshold
        
        return {
            "asset": asset or "ALL",
            "window_hours": window_hours,
            "current_sentiment": round(current_avg, 3),
            "previous_sentiment": round(previous_avg, 3),
            "change": round(change, 3),
            "shift_detected": shift_detected,
            "shift_direction": "positive" if change > 0 else "negative" if change < 0 else "none",
            "current_event_count": len(current_events),
            "previous_event_count": len(previous_events)
        }


# ═══════════════════════════════════════════════════════════════
# SINGLETON ACCESS
# ═══════════════════════════════════════════════════════════════

_sentiment_analytics: Optional[SentimentTrendAnalytics] = None


def get_sentiment_analytics(db) -> SentimentTrendAnalytics:
    """Get or create SentimentTrendAnalytics singleton."""
    global _sentiment_analytics
    if _sentiment_analytics is None:
        _sentiment_analytics = SentimentTrendAnalytics(db)
    return _sentiment_analytics
