"""
Query Engine

Enables complex queries against events and entities:
- projects funded by a16z
- projects with unlocks > $50M
- projects funded before listing
- investor portfolios

Architecture:
Client Query -> Query Parser -> Query Planner -> Aggregation Builder -> Executor -> Results
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class IntelQuery(BaseModel):
    """Query model for intel data"""
    # Entity filters
    entity: Optional[str] = None
    entity_type: Optional[str] = None
    
    # Event filters
    event_type: Optional[str] = None
    event_types: Optional[List[str]] = None
    
    # Investor filters
    investor: Optional[str] = None
    investors: Optional[List[str]] = None
    
    # Amount filters
    min_amount: Optional[float] = None
    max_amount: Optional[float] = None
    
    # Date filters
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    days_back: Optional[int] = None
    days_ahead: Optional[int] = None
    
    # Source filters
    source: Optional[str] = None
    min_confidence: Optional[float] = None
    
    # Pagination
    limit: int = 50
    offset: int = 0
    
    # Sorting
    sort_by: str = "date"
    sort_order: int = -1  # -1 = descending


class QueryParser:
    """Parses query parameters into MongoDB query format"""
    
    @staticmethod
    def parse(query: IntelQuery) -> Dict[str, Any]:
        """Convert IntelQuery to MongoDB query dict"""
        q = {}
        
        # Entity filters
        if query.entity:
            q["entity_id"] = query.entity
        
        if query.entity_type:
            q["entity_type"] = query.entity_type
        
        # Event type filters
        if query.event_type:
            q["event_type"] = query.event_type
        elif query.event_types:
            q["event_type"] = {"$in": query.event_types}
        
        # Investor filters
        if query.investor:
            q["payload.investors"] = query.investor
        elif query.investors:
            q["payload.investors"] = {"$in": query.investors}
        
        # Amount filters
        amount_filter = {}
        if query.min_amount:
            amount_filter["$gte"] = query.min_amount
        if query.max_amount:
            amount_filter["$lte"] = query.max_amount
        if amount_filter:
            q["payload.amount_usd"] = amount_filter
        
        # Date filters
        date_filter = {}
        now = datetime.now(timezone.utc)
        
        if query.start_date:
            date_filter["$gte"] = query.start_date
        elif query.days_back:
            cutoff = (now - timedelta(days=query.days_back)).isoformat()
            date_filter["$gte"] = cutoff
        
        if query.end_date:
            date_filter["$lte"] = query.end_date
        elif query.days_ahead:
            cutoff = (now + timedelta(days=query.days_ahead)).isoformat()
            date_filter["$lte"] = cutoff
        
        if date_filter:
            q["date"] = date_filter
        
        # Source filter
        if query.source:
            q["sources"] = query.source
        
        # Confidence filter
        if query.min_confidence:
            q["confidence"] = {"$gte": query.min_confidence}
        
        return q


class QueryPlanner:
    """Plans query execution strategy"""
    
    @staticmethod
    def build_pipeline(query: IntelQuery, match_query: Dict) -> List[Dict]:
        """Build MongoDB aggregation pipeline"""
        pipeline = []
        
        # Match stage
        if match_query:
            pipeline.append({"$match": match_query})
        
        # Sort stage
        sort_field = query.sort_by
        if sort_field == "amount":
            sort_field = "payload.amount_usd"
        
        pipeline.append({"$sort": {sort_field: query.sort_order}})
        
        # Skip stage (for pagination)
        if query.offset > 0:
            pipeline.append({"$skip": query.offset})
        
        # Limit stage
        pipeline.append({"$limit": query.limit})
        
        # Project stage - exclude _id
        pipeline.append({"$project": {"_id": 0}})
        
        return pipeline


class CrossEventQueryBuilder:
    """Builds queries that span multiple event types"""
    
    @staticmethod
    def funded_before_listing(entity_id: str = None) -> List[Dict]:
        """
        Find projects that received funding before exchange listing.
        
        Uses $lookup to join funding and listing events.
        """
        pipeline = [
            # Start with funding events
            {"$match": {"event_type": "funding"}},
            
            # Lookup listing events for same entity
            {
                "$lookup": {
                    "from": "intel_events",
                    "let": {"entity": "$entity_id", "fund_date": "$date"},
                    "pipeline": [
                        {
                            "$match": {
                                "$expr": {
                                    "$and": [
                                        {"$eq": ["$entity_id", "$$entity"]},
                                        {"$eq": ["$event_type", "exchange_listing"]},
                                        {"$gt": ["$date", "$$fund_date"]}
                                    ]
                                }
                            }
                        }
                    ],
                    "as": "listings"
                }
            },
            
            # Filter to only those with subsequent listings
            {"$match": {"listings": {"$ne": []}}},
            
            # Project results
            {
                "$project": {
                    "_id": 0,
                    "entity_id": 1,
                    "funding_date": "$date",
                    "funding_amount": "$payload.amount_usd",
                    "listing_date": {"$arrayElemAt": ["$listings.date", 0]},
                    "days_to_listing": {
                        "$divide": [
                            {"$subtract": [
                                {"$arrayElemAt": ["$listings.date", 0]},
                                "$date"
                            ]},
                            86400000  # ms to days
                        ]
                    }
                }
            }
        ]
        
        if entity_id:
            pipeline.insert(0, {"$match": {"entity_id": entity_id}})
        
        return pipeline
    
    @staticmethod
    def investor_portfolio(investor: str) -> List[Dict]:
        """
        Get all projects an investor has funded.
        """
        return [
            {"$match": {"payload.investors": investor}},
            {
                "$group": {
                    "_id": "$entity_id",
                    "total_invested": {"$sum": "$payload.amount_usd"},
                    "rounds": {"$push": {
                        "date": "$date",
                        "type": "$event_type",
                        "amount": "$payload.amount_usd"
                    }},
                    "round_count": {"$sum": 1}
                }
            },
            {"$sort": {"total_invested": -1}},
            {
                "$project": {
                    "_id": 0,
                    "entity_id": "$_id",
                    "total_invested": 1,
                    "round_count": 1,
                    "rounds": 1
                }
            }
        ]
    
    @staticmethod
    def unlock_exposure(days_ahead: int = 30, min_amount: float = 0) -> List[Dict]:
        """
        Find upcoming unlocks within time window.
        """
        now = datetime.now(timezone.utc)
        end_date = (now + timedelta(days=days_ahead)).timestamp() * 1000
        
        pipeline = [
            {
                "$match": {
                    "event_type": "unlock",
                    "date": {"$gte": now.timestamp() * 1000, "$lte": end_date}
                }
            }
        ]
        
        if min_amount > 0:
            pipeline[0]["$match"]["payload.amount_usd"] = {"$gte": min_amount}
        
        pipeline.extend([
            {"$sort": {"date": 1}},
            {"$project": {"_id": 0}}
        ])
        
        return pipeline


class QueryEngine:
    """
    Main query engine for intel data.
    
    Supports:
    - Simple queries (filter, sort, paginate)
    - Cross-event queries (funding -> listing)
    - Aggregations (investor portfolios)
    """
    
    def __init__(self, db=None):
        self.db = db
        self.parser = QueryParser()
        self.planner = QueryPlanner()
        self.cross_event = CrossEventQueryBuilder()
    
    async def query_events(self, query: IntelQuery) -> Dict[str, Any]:
        """
        Execute event query.
        
        Returns matching events with metadata.
        """
        if self.db is None:
            return {"error": "No database connection", "results": []}
        
        # Parse query
        match_query = self.parser.parse(query)
        
        # Build pipeline
        pipeline = self.planner.build_pipeline(query, match_query)
        
        # Execute
        cursor = self.db.intel_events.aggregate(pipeline)
        results = await cursor.to_list(query.limit)
        
        # Get total count (without pagination)
        total = await self.db.intel_events.count_documents(match_query)
        
        return {
            "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
            "query": query.model_dump(exclude_none=True),
            "total": total,
            "count": len(results),
            "results": results
        }
    
    async def query_entities(self, query: IntelQuery) -> Dict[str, Any]:
        """
        Query entities (projects, investors).
        """
        if self.db is None:
            return {"error": "No database connection", "results": []}
        
        match_query = {}
        
        if query.entity:
            match_query["entity_id"] = query.entity
        
        if query.entity_type:
            match_query["type"] = query.entity_type
        
        cursor = self.db.entities.find(match_query, {"_id": 0})
        cursor = cursor.skip(query.offset).limit(query.limit)
        
        results = await cursor.to_list(query.limit)
        total = await self.db.entities.count_documents(match_query)
        
        return {
            "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
            "total": total,
            "count": len(results),
            "results": results
        }
    
    async def funded_before_listing(self, entity_id: str = None) -> Dict[str, Any]:
        """Find projects funded before exchange listing."""
        if self.db is None:
            return {"error": "No database connection", "results": []}
        
        pipeline = self.cross_event.funded_before_listing(entity_id)
        cursor = self.db.intel_events.aggregate(pipeline)
        results = await cursor.to_list(100)
        
        return {
            "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
            "query_type": "funded_before_listing",
            "count": len(results),
            "results": results
        }
    
    async def investor_portfolio(self, investor: str) -> Dict[str, Any]:
        """Get investor's portfolio."""
        if self.db is None:
            return {"error": "No database connection", "results": []}
        
        pipeline = self.cross_event.investor_portfolio(investor)
        cursor = self.db.intel_events.aggregate(pipeline)
        results = await cursor.to_list(100)
        
        # Calculate totals
        total_invested = sum(r.get("total_invested", 0) or 0 for r in results)
        
        return {
            "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
            "investor": investor,
            "portfolio_size": len(results),
            "total_invested": total_invested,
            "portfolio": results
        }
    
    async def upcoming_unlocks(
        self, 
        days_ahead: int = 30, 
        min_amount: float = 0
    ) -> Dict[str, Any]:
        """Get upcoming token unlocks."""
        if self.db is None:
            return {"error": "No database connection", "results": []}
        
        pipeline = self.cross_event.unlock_exposure(days_ahead, min_amount)
        cursor = self.db.intel_events.aggregate(pipeline)
        results = await cursor.to_list(200)
        
        # Calculate total exposure
        total_usd = sum(r.get("payload", {}).get("amount_usd", 0) or 0 for r in results)
        
        return {
            "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
            "days_ahead": days_ahead,
            "min_amount": min_amount,
            "unlock_count": len(results),
            "total_usd_exposure": total_usd,
            "unlocks": results
        }
    
    async def run_custom_query(self, pipeline: List[Dict]) -> Dict[str, Any]:
        """
        Execute custom aggregation pipeline.
        
        WARNING: Use with caution - allows arbitrary queries.
        """
        if self.db is None:
            return {"error": "No database connection", "results": []}
        
        try:
            cursor = self.db.intel_events.aggregate(pipeline)
            results = await cursor.to_list(1000)
            
            return {
                "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
                "pipeline_stages": len(pipeline),
                "count": len(results),
                "results": results
            }
        except Exception as e:
            logger.error(f"[QueryEngine] Custom query failed: {e}")
            return {
                "error": str(e),
                "results": []
            }
    
    async def search(
        self, 
        q: str, 
        limit: int = 20
    ) -> Dict[str, Any]:
        """
        Full-text search across events and entities.
        """
        if self.db is None:
            return {"error": "No database connection", "results": []}
        
        # Search events
        event_cursor = self.db.intel_events.find(
            {"$text": {"$search": q}},
            {"_id": 0, "score": {"$meta": "textScore"}}
        ).sort([("score", {"$meta": "textScore"})]).limit(limit)
        
        try:
            events = await event_cursor.to_list(limit)
        except:
            # Text index may not exist
            events = []
        
        # Search entities
        entity_cursor = self.db.entities.find(
            {
                "$or": [
                    {"name": {"$regex": q, "$options": "i"}},
                    {"symbol": {"$regex": q, "$options": "i"}},
                    {"aliases": {"$regex": q, "$options": "i"}}
                ]
            },
            {"_id": 0}
        ).limit(limit)
        
        entities = await entity_cursor.to_list(limit)
        
        return {
            "ts": int(datetime.now(timezone.utc).timestamp() * 1000),
            "query": q,
            "events": events,
            "entities": entities,
            "total": len(events) + len(entities)
        }


# Singleton instance
query_engine: Optional[QueryEngine] = None


def init_query_engine(db):
    """Initialize query engine."""
    global query_engine
    query_engine = QueryEngine(db)
    return query_engine


def get_query_engine():
    """Get query engine instance."""
    return query_engine
