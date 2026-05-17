"""
FOMO Intel Background Workers

Handles:
- Alias auto-learning promotion
- Graph maintenance jobs
- Scheduled data updates
"""

import asyncio
import logging
import os
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClient

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def promote_ready_aliases(db):
    """Promote alias candidates that meet thresholds"""
    from modules.knowledge_graph.alias_learning_service import AliasLearningService
    
    service = AliasLearningService(db)
    promoted = await service.promote_ready_candidates()
    
    if promoted:
        logger.info(f"Promoted {len(promoted)} aliases: {[p['alias'] for p in promoted]}")
    
    return len(promoted)


async def run_graph_health_check(db):
    """Run periodic graph health check"""
    nodes_col = db.graph_nodes
    edges_col = db.graph_edges
    
    nodes_count = await nodes_col.count_documents({})
    edges_count = await edges_col.count_documents({})
    
    # Check for potential issues
    issues = []
    
    # Check for orphan nodes (no edges)
    pipeline = [
        {"$lookup": {
            "from": "graph_edges",
            "let": {"node_id": "$id"},
            "pipeline": [
                {"$match": {"$expr": {"$or": [
                    {"$eq": ["$from_node_id", "$$node_id"]},
                    {"$eq": ["$to_node_id", "$$node_id"]}
                ]}}}
            ],
            "as": "edges"
        }},
        {"$match": {"edges": {"$size": 0}}},
        {"$count": "orphans"}
    ]
    
    result = await nodes_col.aggregate(pipeline).to_list(1)
    orphans = result[0]["orphans"] if result else 0
    
    if orphans > 0:
        issues.append(f"Found {orphans} orphan nodes")
    
    logger.info(f"Graph health: {nodes_count} nodes, {edges_count} edges, issues: {len(issues)}")
    
    return {
        "nodes": nodes_count,
        "edges": edges_count,
        "orphans": orphans,
        "issues": issues
    }


async def main():
    """Main worker loop"""
    logger.info("Starting FOMO Intel Worker...")
    
    # Connect to MongoDB
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name = os.environ.get("DB_NAME", "fomo_market")
    
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    
    logger.info(f"Connected to MongoDB: {db_name}")
    
    # Worker loop
    while True:
        try:
            logger.info("Running scheduled tasks...")
            
            # 1. Promote ready aliases
            await promote_ready_aliases(db)
            
            # 2. Graph health check
            await run_graph_health_check(db)
            
            logger.info("Scheduled tasks complete. Sleeping for 5 minutes...")
            await asyncio.sleep(300)  # Run every 5 minutes
            
        except Exception as e:
            logger.error(f"Worker error: {e}")
            await asyncio.sleep(60)  # Wait 1 minute on error


if __name__ == "__main__":
    asyncio.run(main())
